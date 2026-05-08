from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("ASSETS_DIR", str(Path(__file__).resolve().parents[1] / "assets"))
os.environ.setdefault("RUNS_DIR", str(_ROOT / "data" / "test-smart-runs"))
os.environ.setdefault("PROJECTS_DIR", str(_ROOT / "data" / "test-smart-projects"))
os.environ.setdefault("JOBS_DIR", str(_ROOT / "data" / "test-smart-jobs"))
os.environ.setdefault("BENCHMARKS_DIR", str(_ROOT / "data" / "test-smart-benchmarks"))

from common.generation_logic import build_smart_generation_plan, smart_metadata
from common.schemas import (
    EvaluationResult,
    GenerateResponse,
    PlanResponse,
    SmartGenerationOptions,
    SmartGenerationRequest,
)
from common.utils.images import encode_image_to_data_url
from gateway import main as gateway_main
from gateway.init_provider import InitProviderError
from gateway.jobs import JobStore


def sample_generate_response() -> GenerateResponse:
    return GenerateResponse(
        run_id="run_smart",
        plan=PlanResponse(
            task="text-guided",
            task_prompt="Replace the marked cup with a white vase",
            reasoning="test fixture",
        ),
        result_image="data:image/png;base64,result",
        evaluation=EvaluationResult(
            changed_ratio=0.2,
            outside_mask_change_ratio=0.01,
            note="ok",
        ),
        artifacts={
            "result": "http://testserver/artifacts/run_smart/result.png",
            "metadata": "http://testserver/artifacts/run_smart/metadata.json",
        },
    )


class SmartGenerationPlannerTest(unittest.TestCase):
    def test_no_image_routes_to_text_to_image(self) -> None:
        decision = build_smart_generation_plan(SmartGenerationRequest(prompt="draw a glowing cell"))

        self.assertEqual(decision.task_type, "text_to_image")
        self.assertEqual(decision.pipeline, "flux_text_to_image")
        self.assertFalse(decision.requires_mask)
        self.assertFalse(decision.need_user_clarification)

    def test_image_with_mask_routes_to_qwen_image_local_inpaint_by_default(self) -> None:
        decision = build_smart_generation_plan(
            SmartGenerationRequest(
                prompt="replace the masked beaker with a white vase",
                source_image="data:image/png;base64,source",
                mask_image="data:image/png;base64,mask",
            )
        )

        self.assertEqual(decision.task_type, "local_inpaint")
        self.assertEqual(decision.subtask_type, "object_replacement")
        self.assertEqual(decision.pipeline, "qwen_image_inpaint")
        self.assertTrue(decision.requires_mask)
        self.assertIn("white vase", decision.normalized_prompt)

    def test_image_with_mask_can_route_to_powerpaint_provider(self) -> None:
        decision = build_smart_generation_plan(
            SmartGenerationRequest(
                prompt="replace the masked beaker with a white vase",
                source_image="data:image/png;base64,source",
                mask_image="data:image/png;base64,mask",
                options=SmartGenerationOptions(generation_provider="powerpaint"),
            )
        )

        self.assertEqual(decision.task_type, "local_inpaint")
        self.assertEqual(decision.pipeline, "powerpaint_inpaint")
        self.assertTrue(decision.requires_mask)

    def test_image_without_mask_style_prompt_routes_to_image_variation(self) -> None:
        decision = build_smart_generation_plan(
            SmartGenerationRequest(
                prompt="make this image style more cinematic and textured",
                source_image="data:image/png;base64,source",
            )
        )

        self.assertEqual(decision.task_type, "image_variation")
        self.assertEqual(decision.pipeline, "powerpaint_variation")
        self.assertFalse(decision.need_user_clarification)

    def test_image_without_mask_local_object_needs_region(self) -> None:
        decision = build_smart_generation_plan(
            SmartGenerationRequest(
                prompt="remove the person on the left",
                source_image="data:image/png;base64,source",
            )
        )

        self.assertEqual(decision.task_type, "local_inpaint")
        self.assertEqual(decision.subtask_type, "object_removal")
        self.assertTrue(decision.need_user_clarification)
        self.assertEqual(decision.pipeline, "needs_user_input")

    def test_task_override_takes_precedence(self) -> None:
        decision = build_smart_generation_plan(
            SmartGenerationRequest(
                prompt="extend the background to the right",
                source_image="data:image/png;base64,source",
                options=SmartGenerationOptions(task_override="outpainting"),
            )
        )

        self.assertEqual(decision.task_type, "outpainting")
        self.assertEqual(decision.confidence, 1.0)
        self.assertEqual(decision.pipeline, "powerpaint_outpaint")

    def test_metadata_records_provider_pipeline_and_mask_parameters(self) -> None:
        request = SmartGenerationRequest(
            prompt="replace the masked beaker with a white vase",
            source_image="data:image/png;base64,source",
            mask_image="data:image/png;base64,mask",
        )
        decision = build_smart_generation_plan(request)

        metadata = smart_metadata(
            request=request,
            decision=decision,
            fallback_used=True,
            is_diagnostic_result=True,
            provider="qwen-image",
        )

        self.assertEqual(metadata["task_type"], "local_inpaint")
        self.assertEqual(metadata["planner_confidence"], decision.confidence)
        self.assertEqual(metadata["provider"], "qwen-image")
        self.assertEqual(metadata["pipeline"], "qwen_image_inpaint")
        self.assertEqual(metadata["model"], "Qwen/Qwen-Image-Edit")
        self.assertTrue(metadata["fallback_used"])
        self.assertTrue(metadata["is_diagnostic_result"])
        self.assertEqual(metadata["has_mask"], True)
        self.assertEqual(metadata["mask_dilation"], 16)
        self.assertEqual(metadata["mask_blur"], 12)


class SmartGenerationApiTest(unittest.TestCase):
    def setUp(self) -> None:
        gateway_main.job_store = JobStore()

    def test_text_to_image_model_unavailable_returns_failed_job_not_fake_result(self) -> None:
        client = TestClient(gateway_main.app)

        async def unavailable(*args, **kwargs):
            raise InitProviderError("FLUX initial-canvas service is unavailable")

        with patch.object(gateway_main, "generate_initial_candidates", unavailable):
            response = client.post(
                "/api/generation/jobs",
                json={"prompt": "draw a glowing cell"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["task_type"], "text_to_image")
        self.assertEqual(body["error"], "TEXT_TO_IMAGE_MODEL_UNAVAILABLE")
        self.assertEqual(body["results"], [])
        self.assertTrue(body["metadata"]["provider_unavailable"])
        self.assertFalse(body["metadata"]["fallback_used"])

    def test_image_with_mask_creates_unified_generation_job_with_qwen_metadata(self) -> None:
        client = TestClient(gateway_main.app)

        async def fake_generate_pipeline(*args, **kwargs):
            return sample_generate_response()

        with patch.object(gateway_main, "generate_pipeline", fake_generate_pipeline):
            response = client.post(
                "/api/generation/jobs",
                json={
                    "prompt": "replace the masked beaker with a white vase",
                    "source_image": "data:image/png;base64,source",
                    "mask_image": "data:image/png;base64,mask",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["task_type"], "local_inpaint")
        self.assertEqual(body["metadata"]["provider"], "qwen-image")
        self.assertEqual(body["metadata"]["pipeline"], "qwen_image_inpaint")
        self.assertEqual(body["metadata"]["fallback_used"], False)

        job_response = client.get(f"/api/generation/jobs/{body['job_id']}")
        self.assertEqual(job_response.status_code, 200)
        completed = job_response.json()
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["results"][0]["image_url"], "data:image/png;base64,result")
        self.assertFalse(completed["results"][0]["is_diagnostic_result"])

    def test_smart_generate_request_carries_metadata_for_run_artifacts(self) -> None:
        smart_request = SmartGenerationRequest(
            prompt="replace the masked beaker with a white vase",
            source_image="data:image/png;base64,source",
            mask_image="data:image/png;base64,mask",
        )
        decision = build_smart_generation_plan(smart_request)

        generate_request = gateway_main._generate_request_from_smart(smart_request, decision)

        self.assertEqual(generate_request.generation_provider, "qwen-image")
        self.assertEqual(generate_request.smart_metadata["task_type"], "local_inpaint")
        self.assertEqual(generate_request.smart_metadata["normalized_prompt"], decision.normalized_prompt)
        self.assertEqual(generate_request.smart_metadata["provider"], "qwen-image")
        self.assertEqual(generate_request.smart_metadata["pipeline"], "qwen_image_inpaint")
        self.assertEqual(generate_request.smart_metadata["postprocess_blending"], "soft_mask_blend")

    def test_image_variation_without_user_mask_uses_full_image_mask_and_powerpaint_provider(self) -> None:
        source_image = encode_image_to_data_url(Image.new("RGB", (8, 6), "white"))
        smart_request = SmartGenerationRequest(
            prompt="make this image style more cinematic",
            source_image=source_image,
        )
        decision = build_smart_generation_plan(smart_request)

        generate_request = gateway_main._generate_request_from_smart(smart_request, decision)

        self.assertEqual(decision.task_type, "image_variation")
        self.assertEqual(generate_request.generation_provider, "powerpaint")
        self.assertTrue(generate_request.mask_image.startswith("data:image/png;base64,"))
        self.assertEqual(generate_request.smart_metadata["resize_strategy"], "provider_default")


if __name__ == "__main__":
    unittest.main()
