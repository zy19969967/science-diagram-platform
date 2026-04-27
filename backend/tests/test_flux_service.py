from __future__ import annotations

import unittest

from PIL import Image

from common.init_logic import build_scene_plan
from common.schemas import InitGenerateRequest, ScenePlanRequest
from flux_service.runtime import FluxRuntime, FluxRuntimeConfig, build_flux_prompt


class _FakeResult:
    def __init__(self, image: Image.Image) -> None:
        self.images = [image]


class _FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult(Image.new("RGB", (64, 48), "#ffffff"))


class FluxServiceRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_scene_plan(
            ScenePlanRequest(
                instruction="画一个酶促反应示意图，包含底物、酶、产物",
                candidate_count=2,
                width=512,
                height=384,
                seed=1200,
            )
        )

    def test_build_flux_prompt_uses_scene_plan_labels_and_style(self) -> None:
        prompt = build_flux_prompt(self.plan)

        self.assertIn(self.plan.positive_prompt, prompt)
        self.assertIn("底物", prompt)
        self.assertIn("酶", prompt)
        self.assertIn("clean scientific diagram", prompt)

    def test_generate_candidates_uses_local_flux_provider_metadata(self) -> None:
        fake_pipeline = _FakePipeline()
        runtime = FluxRuntime(
            config=FluxRuntimeConfig(
                backend="diffusers",
                model_repo="local-flux-test",
                num_inference_steps=2,
                guidance_scale=0.0,
            ),
            pipeline_loader=lambda _config: fake_pipeline,
        )

        response = runtime.generate(InitGenerateRequest(scene_plan=self.plan, seed=1200, provider="flux-local"))

        self.assertEqual(response.provider, "flux-local")
        self.assertEqual(response.used_provider, "flux-local")
        self.assertFalse(response.fallback_used)
        self.assertEqual(len(response.candidates), 2)
        self.assertTrue(response.candidates[0].image.startswith("data:image/png;base64,"))
        self.assertEqual(response.candidates[0].provider, "flux-local")
        self.assertEqual(response.candidates[0].metadata["provider_source"], "flux-local")
        self.assertEqual(response.candidates[0].metadata["model_repo"], "local-flux-test")
        self.assertEqual(fake_pipeline.calls[0]["num_inference_steps"], 2)

    def test_disabled_backend_raises_clear_error(self) -> None:
        runtime = FluxRuntime(config=FluxRuntimeConfig(backend="disabled"))

        with self.assertRaisesRegex(RuntimeError, "disabled"):
            runtime.generate(InitGenerateRequest(scene_plan=self.plan, seed=1200, provider="flux-local"))


if __name__ == "__main__":
    unittest.main()
