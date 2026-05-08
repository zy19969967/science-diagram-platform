from __future__ import annotations

import unittest
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from common.schemas import GenerateRequest, PlanResponse, QwenImageEditRequest
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url

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


def _box_mask_data_url(size: tuple[int, int], box: tuple[int, int, int, int]) -> str:
    mask = Image.new("L", size, 0)
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            mask.putpixel((x, y), 255)
    return encode_image_to_data_url(mask)


class QwenImageProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_qwen_prompt_uses_mask_location_and_blocks_double_containers(self) -> None:
        provider_prompt = gateway_main._qwen_image_edit_prompt(
            instruction="replace the masked beaker with an Erlenmeyer flask",
            plan_prompt=(
                "A laboratory conical flask, positioned in the filter funnel. "
                "It should match the vector illustration style."
            ),
            task="text-guided",
        )

        self.assertIn("provided mask determines the edit location", provider_prompt)
        self.assertIn("do not draw an extra outer beaker", provider_prompt)
        self.assertNotIn("positioned in the filter funnel", provider_prompt)

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
        self.assertIsNone(payload.padding_mask_crop)

    async def test_qwen_provider_dispatches_to_qwen_image_service(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            if url.endswith("/plan"):
                return {
                    "task": "text-guided",
                    "task_prompt": "A laboratory conical flask with a narrow neck and wide base.",
                    "negative_prompt": "",
                    "mask_strategy": "user-mask",
                    "reasoning": "planner service response",
                    "warnings": [],
                }
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
        self.assertIn("fully replace the original masked object", provider_prompt)
        self.assertNotIn("including the support stand, glass rod, funnel, beaker", provider_prompt)
        self.assertEqual(calls[0][1]["negative_prompt"], " ")
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt"], provider_prompt)
        self.assertEqual(result.quality_report.prompt.parameters["provider_negative_prompt"], " ")

    async def test_qwen_provider_uses_light_negative_prompt_when_gateway_replans(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"result_image": _image_data_url("#ddeeff")}

        request = GenerateRequest(
            source_image=_image_data_url("white"),
            instruction="把烧杯换成一个倾斜的锥形瓶",
            task="text-guided",
            mask_image=_mask_data_url(),
            plan=PlanResponse(
                task="text-guided",
                task_prompt="A laboratory conical flask with a narrow neck and wide base.",
                negative_prompt="",
                reasoning="planner service response",
            ),
            generation_provider="qwen-image",
            negative_prompt="low quality, blurry, distorted, broken edges, background changed, color bleeding, watermark, text corruption",
            smart_metadata={"negative_prompt": "low quality, blurry, distorted, broken edges, background changed, color bleeding, watermark, text corruption"},
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.object(gateway_main, "post_json", fake_post_json), patch.object(
            gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"
        ):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertTrue(calls[0][0].endswith("/plan"))
        self.assertEqual(calls[-1][1]["negative_prompt"], " ")
        self.assertEqual(result.quality_report.prompt.parameters["provider_negative_prompt"], " ")

    async def test_qwen_provider_crops_and_upscales_mask_region(self) -> None:
        calls: list[tuple[str, dict, tuple[int, int], tuple[int, int]]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            mask = decode_data_url_to_image(payload["mask_image"], mode="L")
            calls.append((url, payload, image.size, mask.size))
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        source = encode_image_to_data_url(Image.new("RGB", (120, 90), "white"))
        request = GenerateRequest(
            source_image=source,
            instruction="replace the masked beaker with an Erlenmeyer flask",
            task="text-guided",
            mask_image=_box_mask_data_url((120, 90), (50, 38, 70, 58)),
            plan=PlanResponse(
                task="text-guided",
                task_prompt="A clear Erlenmeyer flask in vector diagram style.",
                negative_prompt="",
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
        self.assertNotEqual(calls[0][2], (120, 90))
        self.assertEqual(calls[0][2], calls[0][3])
        self.assertGreaterEqual(max(calls[0][2]), 768)
        self.assertEqual(decode_data_url_to_image(result.result_image, mode="RGB").size, (120, 90))
        self.assertTrue(result.quality_report.prompt.parameters["qwen_edit_crop_enabled"])
        self.assertEqual(result.quality_report.prompt.parameters["qwen_edit_crop_source_size"], [120, 90])
        self.assertFalse(result.quality_report.prompt.parameters["qwen_edit_prefill_enabled"])
        self.assertGreater(result.quality_report.prompt.parameters["qwen_edit_execution_mask_dilation_radius"], 0)
        self.assertGreater(
            result.quality_report.prompt.parameters["qwen_edit_execution_mask_coverage_ratio"],
            result.quality_report.prompt.parameters["qwen_edit_user_mask_coverage_ratio"],
        )
        self.assertIn("qwen_request_image", result.artifacts)
        self.assertIn("qwen_restored_preblend", result.artifacts)

    async def test_qwen_provider_blends_with_expanded_execution_mask(self) -> None:
        async def fake_post_json(url: str, payload: dict) -> dict:
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#0000ff"))}

        source = encode_image_to_data_url(Image.new("RGB", (120, 90), "white"))
        request = GenerateRequest(
            source_image=source,
            instruction="replace the masked beaker with an Erlenmeyer flask",
            task="text-guided",
            mask_image=_box_mask_data_url((120, 90), (50, 38, 70, 58)),
            plan=PlanResponse(
                task="text-guided",
                task_prompt="A clear Erlenmeyer flask in vector diagram style.",
                negative_prompt="",
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

        result_image = decode_data_url_to_image(result.result_image, mode="RGB")
        self.assertNotEqual(result_image.getpixel((48, 48)), (255, 255, 255))
        self.assertEqual(result_image.getpixel((10, 10)), (255, 255, 255))
        self.assertIn("qwen_final_blend_mask", result.artifacts)

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
