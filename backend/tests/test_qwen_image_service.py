from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from common.schemas import QwenImageEditRequest
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url
from qwen_image_service import main as qwen_main
from qwen_image_service.runtime import (
    DEFAULT_QWEN_IMAGE_MODEL_REPO,
    QwenImageRuntime,
    QwenImageRuntimeConfig,
    _load_diffusers_pipeline,
)


class _FakeResult:
    def __init__(self, image: Image.Image) -> None:
        self.images = [image]


class _FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult(Image.new("RGB", (12, 10), "#336699"))


class _SignatureLimitedPipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        image: Image.Image,
        mask_image: Image.Image,
        prompt: str,
        num_inference_steps: int,
    ) -> _FakeResult:
        self.calls.append(
            {
                "image": image,
                "mask_image": mask_image,
                "prompt": prompt,
                "num_inference_steps": num_inference_steps,
            }
        )
        return _FakeResult(Image.new("RGB", (12, 10), "#224466"))


class _TrackingLock:
    def __init__(self) -> None:
        self.active = False

    def __enter__(self) -> "_TrackingLock":
        self.active = True
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.active = False


class _LockCheckingPipeline:
    def __init__(self, lock: _TrackingLock) -> None:
        self.lock = lock

    def __call__(self, **_kwargs: object) -> _FakeResult:
        if not self.lock.active:
            raise RuntimeError("pipeline call was not locked")
        return _FakeResult(Image.new("RGB", (12, 10), "#113355"))


def _request(**overrides: object) -> QwenImageEditRequest:
    payload = {
        "image": encode_image_to_data_url(Image.new("RGBA", (8, 6), "#ff0000")),
        "mask_image": encode_image_to_data_url(Image.new("RGB", (8, 6), "#ffffff")),
        "prompt": "replace the selected label with ATP",
        "negative_prompt": "blurry",
        "num_inference_steps": 7,
        "true_cfg_scale": 3.5,
        "strength": 0.8,
        "seed": 1234,
    }
    payload.update(overrides)
    return QwenImageEditRequest(**payload)


class QwenImageServiceRuntimeTest(unittest.TestCase):
    def test_health_reports_qwen_image_defaults_without_loading_pipeline(self) -> None:
        runtime = QwenImageRuntime()

        health = runtime.health()

        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["service"], "qwen-image")
        self.assertEqual(health["backend"], "diffusers")
        self.assertEqual(health["model_repo"], DEFAULT_QWEN_IMAGE_MODEL_REPO)
        self.assertEqual(health["model_repo"], "Qwen/Qwen-Image-Edit")
        self.assertFalse(health["loaded"])

    def test_generate_decodes_inputs_and_returns_result_image_data_url(self) -> None:
        fake_pipeline = _FakePipeline()
        runtime = QwenImageRuntime(
            config=QwenImageRuntimeConfig(model_repo="local-qwen-test"),
            pipeline_loader=lambda _config: fake_pipeline,
        )

        response = runtime.generate(_request())

        self.assertTrue(response["result_image"].startswith("data:image/png;base64,"))
        result_image = decode_data_url_to_image(response["result_image"], mode="RGB")
        self.assertEqual(result_image.size, (12, 10))
        self.assertEqual(len(fake_pipeline.calls), 1)
        call = fake_pipeline.calls[0]
        self.assertIsInstance(call["image"], Image.Image)
        self.assertEqual(call["image"].mode, "RGB")
        self.assertIsInstance(call["mask_image"], Image.Image)
        self.assertEqual(call["mask_image"].mode, "L")
        self.assertEqual(call["prompt"], "replace the selected label with ATP")
        self.assertEqual(call["negative_prompt"], "blurry")
        self.assertEqual(call["num_inference_steps"], 7)
        self.assertEqual(call["true_cfg_scale"], 3.5)
        self.assertEqual(call["strength"], 0.8)

    def test_generate_passes_generator_when_torch_can_create_one(self) -> None:
        fake_pipeline = _FakePipeline()
        runtime = QwenImageRuntime(
            config=QwenImageRuntimeConfig(model_repo="local-qwen-test"),
            pipeline_loader=lambda _config: fake_pipeline,
        )
        torch_module = SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False),
            Generator=lambda device: SimpleNamespace(device=device, manual_seed=lambda seed: f"seed:{seed}"),
        )

        with patch("qwen_image_service.runtime.importlib.import_module", return_value=torch_module):
            runtime.generate(_request(seed=5678))

        self.assertEqual(fake_pipeline.calls[0]["generator"], "seed:5678")

    def test_generate_filters_unsupported_pipeline_kwargs(self) -> None:
        fake_pipeline = _SignatureLimitedPipeline()
        runtime = QwenImageRuntime(
            config=QwenImageRuntimeConfig(num_inference_steps=50, true_cfg_scale=4.0, strength=1.0),
            pipeline_loader=lambda _config: fake_pipeline,
        )

        runtime.generate(_request())

        self.assertEqual(len(fake_pipeline.calls), 1)
        call = fake_pipeline.calls[0]
        self.assertEqual(set(call), {"image", "mask_image", "prompt", "num_inference_steps"})
        self.assertEqual(call["num_inference_steps"], 7)

    def test_generate_uses_runtime_defaults_when_request_omits_generation_parameters(self) -> None:
        fake_pipeline = _FakePipeline()
        runtime = QwenImageRuntime(
            config=QwenImageRuntimeConfig(num_inference_steps=6, true_cfg_scale=2.5, strength=0.7),
            pipeline_loader=lambda _config: fake_pipeline,
        )
        payload = QwenImageEditRequest(
            image=encode_image_to_data_url(Image.new("RGB", (8, 6), "#ff0000")),
            mask_image=encode_image_to_data_url(Image.new("L", (8, 6), "#ffffff")),
            prompt="replace the selected label with ATP",
        )

        runtime.generate(payload)

        call = fake_pipeline.calls[0]
        self.assertEqual(call["num_inference_steps"], 6)
        self.assertEqual(call["true_cfg_scale"], 2.5)
        self.assertEqual(call["strength"], 0.7)

    def test_request_local_files_only_forces_local_load_on_first_request(self) -> None:
        loaded_configs: list[QwenImageRuntimeConfig] = []

        def loader(config: QwenImageRuntimeConfig) -> _FakePipeline:
            loaded_configs.append(config)
            return _FakePipeline()

        runtime = QwenImageRuntime(
            config=QwenImageRuntimeConfig(local_files_only=False),
            pipeline_loader=loader,
        )

        runtime.generate(_request(local_files_only=True))

        self.assertEqual(len(loaded_configs), 1)
        self.assertTrue(loaded_configs[0].local_files_only)

    def test_generate_holds_lock_while_calling_pipeline(self) -> None:
        lock = _TrackingLock()
        runtime = QwenImageRuntime(pipeline_loader=lambda _config: _LockCheckingPipeline(lock))
        runtime._lock = lock

        response = runtime.generate(_request())

        self.assertTrue(response["result_image"].startswith("data:image/png;base64,"))

    def test_disabled_backend_raises_clear_error(self) -> None:
        runtime = QwenImageRuntime(
            config=QwenImageRuntimeConfig(backend="disabled"),
            pipeline_loader=lambda _config: _FakePipeline(),
        )

        with self.assertRaisesRegex(RuntimeError, "Local Qwen-Image backend is disabled"):
            runtime.generate(_request())

        self.assertIn("disabled", runtime.health()["last_error"])

    def test_app_health_and_generate_endpoints_use_runtime(self) -> None:
        fake_pipeline = _FakePipeline()
        runtime = QwenImageRuntime(pipeline_loader=lambda _config: fake_pipeline)

        with patch.object(qwen_main, "qwen_image_runtime", runtime):
            client = TestClient(qwen_main.app)
            health_response = client.get("/health")
            generate_response = client.post("/generate", json=_request().model_dump())

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["service"], "qwen-image")
        self.assertEqual(generate_response.status_code, 200)
        self.assertTrue(generate_response.json()["result_image"].startswith("data:image/png;base64,"))

    def test_app_generate_returns_503_when_backend_disabled(self) -> None:
        runtime = QwenImageRuntime(config=QwenImageRuntimeConfig(backend="disabled"))

        with patch.object(qwen_main, "qwen_image_runtime", runtime):
            response = TestClient(qwen_main.app).post("/generate", json=_request().model_dump())

        self.assertEqual(response.status_code, 503)
        self.assertIn("Local Qwen-Image backend is disabled", response.json()["detail"])

    def test_diffusers_loader_uses_qwen_image_edit_inpaint_pipeline(self) -> None:
        class LoadedPipeline:
            def __init__(self) -> None:
                self.device: str | None = None

            def to(self, device: str) -> None:
                self.device = device

        class QwenImageEditInpaintPipeline:
            loaded: tuple[str, dict[str, object]] | None = None

            @classmethod
            def from_pretrained(cls, repo: str, **kwargs: object) -> LoadedPipeline:
                cls.loaded = (repo, kwargs)
                return LoadedPipeline()

        torch_module = SimpleNamespace(
            bfloat16="bfloat16",
            float16="float16",
            float32="float32",
            cuda=SimpleNamespace(is_available=lambda: False),
            Generator=lambda device: SimpleNamespace(device=device, manual_seed=lambda seed: f"seed:{seed}"),
        )
        diffusers_module = SimpleNamespace(QwenImageEditInpaintPipeline=QwenImageEditInpaintPipeline)

        def fake_import_module(name: str) -> object:
            if name == "torch":
                return torch_module
            if name == "diffusers":
                return diffusers_module
            raise AssertionError(f"unexpected import: {name}")

        with patch("qwen_image_service.runtime.importlib.import_module", side_effect=fake_import_module):
            pipeline = _load_diffusers_pipeline(QwenImageRuntimeConfig(local_files_only=True))

        self.assertEqual(pipeline.device, "cpu")
        self.assertIsNotNone(QwenImageEditInpaintPipeline.loaded)
        repo, kwargs = QwenImageEditInpaintPipeline.loaded
        self.assertEqual(repo, DEFAULT_QWEN_IMAGE_MODEL_REPO)
        self.assertEqual(kwargs["torch_dtype"], "bfloat16")
        self.assertTrue(kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
