from __future__ import annotations

import os
import unittest
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


def _image_data_url(color: str = "white", size: tuple[int, int] = (8, 8)) -> str:
    return encode_image_to_data_url(Image.new("RGB", size, color))


def _mask_data_url() -> str:
    return _box_mask_data_url((8, 8), (2, 2, 6, 6))


def _box_mask_data_url(size: tuple[int, int], box: tuple[int, int, int, int]) -> str:
    mask = Image.new("L", size, 0)
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            mask.putpixel((x, y), 255)
    return encode_image_to_data_url(mask)


def _plan(
    *,
    task: str = "text-guided",
    task_prompt: str = "A clear Erlenmeyer flask in vector diagram style.",
    negative_prompt: str = "",
) -> PlanResponse:
    return PlanResponse(
        task=task,
        task_prompt=task_prompt,
        negative_prompt=negative_prompt,
        reasoning="test",
    )


class QwenImageProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_qwen_prompt_uses_unified_short_chinese_instruction(self) -> None:
        provider_prompt = gateway_main._qwen_image_edit_prompt(
            instruction="把烧杯变成锥形瓶",
            plan_prompt="A laboratory conical flask, positioned in the filter funnel.",
            task="text-guided",
        )

        self.assertIn("只修改 mask 内区域", provider_prompt)
        self.assertIn("把烧杯变成锥形瓶", provider_prompt)
        self.assertIn("锥形瓶", provider_prompt)
        self.assertIn("窄颈", provider_prompt)
        self.assertIn("宽底", provider_prompt)
        self.assertNotIn("Replace the selected content", provider_prompt)
        self.assertNotIn("Fit the complete requested content", provider_prompt)
        self.assertNotIn("Preserve all unmasked pixels exactly", provider_prompt)
        self.assertNotIn("wide mouth", provider_prompt.lower())
        self.assertNotIn("narrow base", provider_prompt.lower())
        self.assertNotIn("expanded slightly", provider_prompt)
        self.assertNotIn("distinct original object", provider_prompt)
        self.assertNotIn("positioned in the filter funnel", provider_prompt)

    def test_qwen_prompt_uses_same_template_for_deletion_instruction(self) -> None:
        provider_prompt = gateway_main._qwen_image_edit_prompt(
            instruction="删除选区里的杯子",
            plan_prompt="clean table background",
            task="object-removal",
            source_is_diagram=False,
        )

        self.assertIn("只修改 mask 内区域", provider_prompt)
        self.assertIn("删除选区里的杯子", provider_prompt)
        self.assertIn("保持照片风格", provider_prompt)
        self.assertNotIn("Replace", provider_prompt)
        self.assertNotIn("Remove the selected content", provider_prompt)
        self.assertNotIn("replacement", provider_prompt)
        self.assertNotIn("不要生成新的前景物体", provider_prompt)

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

    async def test_qwen_provider_sends_original_image_and_raw_mask_without_crop_or_dilation(self) -> None:
        calls: list[tuple[str, dict, tuple[int, int], tuple[int, int]]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            if url.endswith("/qwen-edit-prompt"):
                raise RuntimeError("planner enhancer unavailable")
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            mask = decode_data_url_to_image(payload["mask_image"], mode="L")
            calls.append((url, payload, image.size, mask.size))
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        source = encode_image_to_data_url(Image.new("RGB", (120, 90), "white"))
        raw_mask = _box_mask_data_url((120, 90), (50, 38, 70, 58))
        request = GenerateRequest(
            source_image=source,
            instruction="replace the selected beaker with an Erlenmeyer flask",
            task="text-guided",
            mask_image=raw_mask,
            plan=_plan(),
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
        self.assertEqual(calls[0][2], (120, 90))
        self.assertEqual(calls[0][3], (120, 90))
        sent_mask = decode_data_url_to_image(calls[0][1]["mask_image"], mode="L")
        expected_mask = decode_data_url_to_image(raw_mask, mode="L")
        self.assertEqual(list(sent_mask.getdata()), list(expected_mask.getdata()))
        self.assertFalse(result.quality_report.prompt.parameters["qwen_edit_crop_enabled"])
        self.assertEqual(result.quality_report.prompt.parameters["qwen_edit_execution_mask_dilation_radius"], 0)
        self.assertIsNone(result.quality_report.prompt.parameters["qwen_edit_execution_mask_bbox"])
        self.assertNotIn("qwen_execution_mask", result.artifacts)
        self.assertNotIn("qwen_restored_preblend", result.artifacts)

    async def test_qwen_provider_final_blend_changes_only_raw_mask_pixels(self) -> None:
        async def fake_post_json(url: str, payload: dict) -> dict:
            if url.endswith("/qwen-edit-prompt"):
                raise RuntimeError("planner enhancer unavailable")
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#0000ff"))}

        source = encode_image_to_data_url(Image.new("RGB", (120, 90), "white"))
        request = GenerateRequest(
            source_image=source,
            instruction="replace the selected beaker with an Erlenmeyer flask",
            task="text-guided",
            mask_image=_box_mask_data_url((120, 90), (50, 38, 70, 58)),
            plan=_plan(),
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
        self.assertEqual(result_image.getpixel((50, 38)), (0, 0, 255))
        self.assertEqual(result_image.getpixel((49, 38)), (255, 255, 255))
        self.assertEqual(result_image.getpixel((50, 37)), (255, 255, 255))
        self.assertEqual(result_image.getpixel((10, 10)), (255, 255, 255))

    async def test_qwen_provider_does_not_call_prompt_enhancer_by_default(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            if url.endswith("/qwen-edit-prompt"):
                raise AssertionError("Qwen prompt enhancer should be disabled by default")
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("white", size=(32, 32)),
            instruction="把烧杯变成锥形瓶",
            task="text-guided",
            mask_image=_box_mask_data_url((32, 32), (8, 8, 24, 24)),
            plan=_plan(task_prompt="A conical flask."),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.dict(os.environ, {"QWEN_IMAGE_PROMPT_ENHANCER_ENABLED": "false"}), patch.object(
            gateway_main, "post_json", fake_post_json
        ), patch.object(gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertEqual(calls[0][0], "http://qwen-image-test:8005/generate")
        self.assertIn("把烧杯变成锥形瓶", calls[0][1]["prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt_source"], "user-direct")

    async def test_qwen_provider_can_use_qwen35_enhanced_prompt_when_explicitly_enabled(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            if url.endswith("/qwen-edit-prompt"):
                return {
                    "prompt": "只修改 mask 内区域。把选区内容改成：锥形瓶（窄颈、宽底）。保持科学线稿风格。",
                    "negative_prompt": " ",
                    "source": "qwen3.5-enhancer",
                    "warnings": [],
                }
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("white", size=(32, 32)),
            instruction="\u628a\u70e7\u676f\u53d8\u6210\u9525\u5f62\u74f6",
            task="text-guided",
            mask_image=_box_mask_data_url((32, 32), (8, 8, 24, 24)),
            plan=_plan(task_prompt="A conical flask."),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.dict(os.environ, {"QWEN_IMAGE_PROMPT_ENHANCER_ENABLED": "true"}), patch.object(
            gateway_main, "post_json", fake_post_json
        ), patch.object(gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertTrue(calls[0][0].endswith("/qwen-edit-prompt"))
        self.assertTrue(calls[1][0].endswith("/generate"))
        self.assertEqual(
            calls[1][1]["prompt"],
            "只修改 mask 内区域。把选区内容改成：锥形瓶（窄颈、宽底）。保持科学线稿风格。",
        )
        self.assertIn("锥形瓶", calls[1][1]["prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt_source"], "qwen3.5-enhancer")

    async def test_qwen_provider_rejects_english_enhancer_prompt(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            if url.endswith("/qwen-edit-prompt"):
                return {
                    "prompt": "Replace the selected beaker content inside the mask with an Erlenmeyer flask.",
                    "negative_prompt": " ",
                    "source": "qwen3.5-enhancer",
                    "warnings": [],
                }
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("white", size=(32, 32)),
            instruction="把烧杯变成锥形瓶",
            task="text-guided",
            mask_image=_box_mask_data_url((32, 32), (8, 8, 24, 24)),
            plan=_plan(task_prompt="A conical flask."),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.dict(os.environ, {"QWEN_IMAGE_PROMPT_ENHANCER_ENABLED": "true"}), patch.object(
            gateway_main, "post_json", fake_post_json
        ), patch.object(gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertTrue(calls[0][0].endswith("/qwen-edit-prompt"))
        self.assertTrue(calls[1][0].endswith("/generate"))
        self.assertIn("把烧杯变成锥形瓶", calls[1][1]["prompt"])
        self.assertIn("锥形瓶", calls[1][1]["prompt"])
        self.assertNotIn("Replace", calls[1][1]["prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt_source"], "gateway-fallback")

    async def test_qwen_provider_rejects_enhancer_that_reverses_chinese_action(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            if url.endswith("/qwen-edit-prompt"):
                return {
                    "prompt": "将锥形瓶（窄颈宽底）替换为烧杯，保持科学线稿风格，仅修改选区内容。",
                    "negative_prompt": " ",
                    "source": "qwen3.5-enhancer",
                    "warnings": [],
                }
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("white", size=(32, 32)),
            instruction="把烧杯变成锥形瓶",
            task="text-guided",
            mask_image=_box_mask_data_url((32, 32), (8, 8, 24, 24)),
            plan=_plan(task_prompt="A conical flask."),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.dict(os.environ, {"QWEN_IMAGE_PROMPT_ENHANCER_ENABLED": "true"}), patch.object(
            gateway_main, "post_json", fake_post_json
        ), patch.object(gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertIn("把烧杯变成锥形瓶", calls[1][1]["prompt"])
        self.assertNotIn("替换为烧杯", calls[1][1]["prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt_source"], "gateway-fallback")

    async def test_qwen_provider_uses_photo_prompt_for_non_diagram_source(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            if url.endswith("/qwen-edit-prompt"):
                raise RuntimeError("planner enhancer unavailable")
            calls.append((url, payload))
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("#8a6b4a"),
            instruction="replace the selected cup with a glass cup",
            task="text-guided",
            mask_image=_mask_data_url(),
            plan=_plan(task_prompt="A transparent glass cup in the same scene lighting."),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.dict(os.environ, {"QWEN_IMAGE_PROMPT_ENHANCER_ENABLED": "true"}), patch.object(
            gateway_main, "post_json", fake_post_json
        ), patch.object(gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        provider_prompt = calls[0][1]["prompt"]
        self.assertIn("保持照片风格", provider_prompt)
        self.assertIn("光照", provider_prompt)
        self.assertIn("材质", provider_prompt)
        self.assertNotIn("photographic style", provider_prompt)
        self.assertNotIn("cartoon", provider_prompt)
        self.assertNotIn("科学线稿", provider_prompt)
        self.assertEqual(result.quality_report.prompt.parameters["source_style"], "photographic")

    async def test_qwen_provider_keeps_qwen_for_photographic_removal(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            if url.endswith("/qwen-edit-prompt"):
                raise RuntimeError("planner enhancer unavailable")
            calls.append((url, payload))
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("#8a6b4a"),
            instruction="remove the selected cups",
            task="object-removal",
            mask_image=_mask_data_url(),
            plan=_plan(task="object-removal", task_prompt="matching table background"),
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
        self.assertIn("删除选区内容", calls[0][1]["prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider"], "qwen-image")
        self.assertNotIn("provider_route_reason", result.quality_report.prompt.parameters)

    async def test_qwen_provider_uses_chinese_enhancer_prompt_without_operation_branching(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            if url.endswith("/qwen-edit-prompt"):
                return {
                    "prompt": "只修改 mask 内区域。把选区内容改成玻璃杯。保持照片风格。",
                    "negative_prompt": " ",
                    "source": "qwen3.5-enhancer",
                    "warnings": [],
                }
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("#8a6b4a"),
            instruction="把杯子变成玻璃杯",
            task="text-guided",
            mask_image=_mask_data_url(),
            plan=_plan(task_prompt="A transparent glass cup in the same scene lighting."),
            generation_provider="qwen-image",
            steps=12,
            guidance_scale=4.0,
            seed=123,
        )

        with patch.dict(os.environ, {"QWEN_IMAGE_PROMPT_ENHANCER_ENABLED": "true"}), patch.object(
            gateway_main, "post_json", fake_post_json
        ), patch.object(gateway_main, "QWEN_IMAGE_URL", "http://qwen-image-test:8005"):
            result = await gateway_main.generate_pipeline(request, "http://testserver")

        self.assertEqual(calls[1][1]["prompt"], "只修改 mask 内区域。把选区内容改成玻璃杯。保持照片风格。")
        self.assertNotIn("Replace", calls[1][1]["prompt"])
        self.assertEqual(result.quality_report.prompt.parameters["provider_prompt_source"], "qwen3.5-enhancer")

    async def test_qwen_provider_keeps_qwen_for_scientific_diagram_removal(self) -> None:
        calls: list[tuple[str, dict]] = []

        async def fake_post_json(url: str, payload: dict) -> dict:
            if url.endswith("/qwen-edit-prompt"):
                raise RuntimeError("planner enhancer unavailable")
            calls.append((url, payload))
            image = decode_data_url_to_image(payload["image"], mode="RGB")
            return {"result_image": encode_image_to_data_url(Image.new("RGB", image.size, "#ddeeff"))}

        request = GenerateRequest(
            source_image=_image_data_url("white"),
            instruction="remove the selected beaker",
            task="object-removal",
            mask_image=_mask_data_url(),
            plan=_plan(task="object-removal", task_prompt="clean white background"),
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
        self.assertEqual(result.quality_report.prompt.parameters["provider"], "qwen-image")
        self.assertEqual(result.quality_report.prompt.parameters["pipeline"], "qwen_image_inpaint")

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
            plan=_plan(task_prompt="A labeled nucleus in a clean scientific diagram style.", negative_prompt="blurry, distorted"),
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
