from __future__ import annotations

import unittest
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from common.schemas import GenerateRequest, PlanResponse, QwenImageEditRequest
from common.utils.images import encode_image_to_data_url

os.environ.setdefault("ASSETS_DIR", str(Path(__file__).resolve().parents[1] / "assets"))
_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("RUNS_DIR", str(_ROOT / "data" / "test-qwen-provider-runs"))
os.environ.setdefault("PROJECTS_DIR", str(_ROOT / "data" / "test-qwen-provider-projects"))
os.environ.setdefault("JOBS_DIR", str(_ROOT / "data" / "test-qwen-provider-jobs"))
os.environ.setdefault("BENCHMARKS_DIR", str(_ROOT / "data" / "test-qwen-provider-benchmarks"))

from gateway import main as gateway_main


def _image_data_url(color: str = "white") -> str:
    return encode_image_to_data_url(Image.new("RGB", (8, 8), color))


def _mask_data_url() -> str:
    mask = Image.new("L", (8, 8), 0)
    for x in range(2, 6):
        for y in range(2, 6):
            mask.putpixel((x, y), 255)
    return encode_image_to_data_url(mask)


class QwenImageProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_qwen_image_edit_request_contains_mask_native_fields(self) -> None:
        payload = QwenImageEditRequest(
            image="data:image/png;base64,source",
            mask_image="data:image/png;base64,mask",
            prompt="replace the masked cell with a labeled nucleus",
            negative_prompt="blurry",
            num_inference_steps=12,
            true_cfg_scale=4.0,
            strength=1.0,
            seed=123,
        )

        self.assertEqual(payload.prompt, "replace the masked cell with a labeled nucleus")
        self.assertEqual(payload.mask_image, "data:image/png;base64,mask")
        self.assertEqual(payload.num_inference_steps, 12)
        self.assertEqual(payload.true_cfg_scale, 4.0)
        self.assertEqual(payload.strength, 1.0)

    async def test_qwen_provider_dispatches_to_qwen_image_service(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"result_image": _image_data_url("#ddeeff")}

        request = GenerateRequest(
            source_image=_image_data_url("white"),
            instruction="replace the masked cell with a labeled nucleus",
            task="text-guided",
            mask_image=_mask_data_url(),
            plan=PlanResponse(
                task="text-guided",
                task_prompt="A labeled nucleus in a clean scientific diagram style.",
                negative_prompt="blurry, distorted",
                reasoning="test",
            ),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.object(gateway_main, "post_json", fake_post_json), patch.object(
            gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"
        ):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertEqual(calls[0][0], "http://qwen-image-test:8005/generate")
        self.assertIn("Edit only the masked region", calls[0][1]["prompt"])
        self.assertIn("A labeled nucleus in a clean scientific diagram style.", calls[0][1]["prompt"])
        self.assertEqual(calls[0][1]["mask_image"].split(",", 1)[0], "data:image/png;base64")
        self.assertEqual(calls[0][1]["negative_prompt"], " ")
        self.assertEqual(result.quality_report.prompt.parameters["provider"], "qwen-image")
        self.assertEqual(result.quality_report.prompt.parameters["pipeline"], "qwen_image_inpaint")
        self.assertIn("Edit only the masked region", result.quality_report.prompt.parameters["provider_prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider_negative_prompt"], " ")

    async def test_qwen_provider_enhances_chinese_replacement_prompt(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"result_image": _image_data_url("#ddeeff")}

        request = GenerateRequest(
            source_image=_image_data_url("white"),
            instruction="将这个物品换成一个倾斜的锥形瓶，并且与玻璃棒平行",
            task="text-guided",
            mask_image=_mask_data_url(),
            plan=PlanResponse(
                task="text-guided",
                task_prompt="A new object naturally placed in the masked region, seamlessly blended with the scene lighting, color, and style.",
                negative_prompt="low quality, blurry, distorted, broken edges, background changed, color bleeding, watermark, text corruption",
                reasoning="test",
            ),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.object(gateway_main, "post_json", fake_post_json), patch.object(
            gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"
        ):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        provider_prompt = calls[0][1]["prompt"]
        self.assertIn("Edit only the masked region", provider_prompt)
        self.assertIn("将这个物品换成一个倾斜的锥形瓶，并且与玻璃棒平行", provider_prompt)
        self.assertIn("Erlenmeyer flask", provider_prompt)
        self.assertIn("glass rod", provider_prompt)
        self.assertIn("parallel", provider_prompt)
        self.assertIn("Keep every unmasked part", provider_prompt)
        self.assertEqual(calls[0][1]["negative_prompt"], " ")
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt"], provider_prompt)
        self.assertEqual(result.quality_report.prompt.parameters["provider_negative_prompt"], " ")

    async def test_powerpaint_provider_still_dispatches_to_powerpaint_service(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"result_image": _image_data_url("#ffeecc")}

        request = GenerateRequest(
            source_image=_image_data_url("white"),
            instruction="replace the masked cell with a labeled nucleus",
            task="text-guided",
            mask_image=_mask_data_url(),
            plan=PlanResponse(
                task="text-guided",
                task_prompt="A labeled nucleus in a clean scientific diagram style.",
                negative_prompt="blurry, distorted",
                reasoning="test",
            ),
            generation_provider="powerpaint",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.object(gateway_main, "post_json", fake_post_json), patch.object(
            gateway_main, "POWERPAINT_URL", "http://powerpaint-test:8002"
        ):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertEqual(calls[0][0], "http://powerpaint-test:8002/generate")
        self.assertEqual(calls[0][1]["prompt"], "A labeled nucleus in a clean scientific diagram style.")
        self.assertEqual(calls[0][1]["negative_prompt"], "blurry, distorted")
        self.assertEqual(result.quality_report.prompt.parameters["provider"], "powerpaint")
        self.assertEqual(
            result.quality_report.prompt.parameters["provider_prompt"],
            "A labeled nucleus in a clean scientific diagram style.",
        )
        self.assertEqual(result.quality_report.prompt.parameters["provider_negative_prompt"], "blurry, distorted")


if __name__ == "__main__":
    unittest.main()
