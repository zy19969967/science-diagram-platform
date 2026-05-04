from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from common.init_logic import build_scene_plan
from common.schemas import InitGenerateRequest, ScenePlanRequest
from flux_service.runtime import (
    DEFAULT_FLUX_GUIDANCE_SCALE,
    DEFAULT_FLUX_MAX_SEQUENCE_LENGTH,
    DEFAULT_FLUX_MODEL_REPO,
    FluxRuntime,
    FluxRuntimeConfig,
    _load_diffusers_pipeline,
    build_flux_prompt,
)


class _FakeResult:
    def __init__(self, image: Image.Image) -> None:
        self.images = [image]


class _FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult(Image.new("RGB", (64, 48), "#ffffff"))


class _SignatureLimitedPipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        num_inference_steps: int,
        guidance_scale: float,
    ) -> _FakeResult:
        self.calls.append(
            {
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
            }
        )
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

        self.assertIn(self.plan.instruction, prompt)
        self.assertTrue(any(phrase in prompt.lower() for phrase in ["clean scientific diagram", "scientific diagram style"]))
        self.assertIn("white background", prompt)
        self.assertIn("vector-like", prompt)

    def test_default_config_targets_flux2_klein(self) -> None:
        config = FluxRuntimeConfig()

        self.assertEqual(config.model_repo, DEFAULT_FLUX_MODEL_REPO)
        self.assertEqual(config.model_repo, "black-forest-labs/FLUX.2-klein-4B")
        self.assertEqual(config.guidance_scale, DEFAULT_FLUX_GUIDANCE_SCALE)
        self.assertEqual(config.guidance_scale, 1.0)
        self.assertEqual(config.max_sequence_length, DEFAULT_FLUX_MAX_SEQUENCE_LENGTH)
        self.assertEqual(config.max_sequence_length, 512)

    def test_flux1_model_override_uses_compatible_defaults(self) -> None:
        config = FluxRuntimeConfig(model_repo="black-forest-labs/FLUX.1-schnell")

        self.assertEqual(config.guidance_scale, 0.0)
        self.assertEqual(config.max_sequence_length, 256)

    def test_diffusers_loader_prefers_flux2_klein_pipeline(self) -> None:
        class LoadedPipeline:
            def __init__(self) -> None:
                self.device: str | None = None

            def to(self, device: str) -> None:
                self.device = device

        class Flux2KleinPipeline:
            loaded: tuple[str, dict[str, object]] | None = None

            @classmethod
            def from_pretrained(cls, repo: str, **kwargs: object) -> LoadedPipeline:
                cls.loaded = (repo, kwargs)
                return LoadedPipeline()

        class FluxPipeline:
            @classmethod
            def from_pretrained(cls, repo: str, **kwargs: object) -> LoadedPipeline:
                raise AssertionError("FluxPipeline should not be used when Flux2KleinPipeline exists")

        torch_module = SimpleNamespace(
            bfloat16="bfloat16",
            float16="float16",
            float32="float32",
            cuda=SimpleNamespace(is_available=lambda: False),
        )
        diffusers_module = SimpleNamespace(
            Flux2KleinPipeline=Flux2KleinPipeline,
            FluxPipeline=FluxPipeline,
            AutoPipelineForText2Image=None,
        )

        def fake_import_module(name: str) -> object:
            if name == "torch":
                return torch_module
            if name == "diffusers":
                return diffusers_module
            raise AssertionError(f"unexpected import: {name}")

        with patch("flux_service.runtime.importlib.import_module", side_effect=fake_import_module):
            pipeline = _load_diffusers_pipeline(FluxRuntimeConfig(local_files_only=True))

        self.assertEqual(pipeline.device, "cpu")
        self.assertIsNotNone(Flux2KleinPipeline.loaded)
        repo, kwargs = Flux2KleinPipeline.loaded
        self.assertEqual(repo, DEFAULT_FLUX_MODEL_REPO)
        self.assertEqual(kwargs["torch_dtype"], "bfloat16")
        self.assertTrue(kwargs["local_files_only"])

    def test_diffusers_loader_falls_back_to_flux_pipeline(self) -> None:
        class LoadedPipeline:
            def to(self, _device: str) -> None:
                return None

        class FluxPipeline:
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
        )
        diffusers_module = SimpleNamespace(
            Flux2KleinPipeline=None,
            FluxPipeline=FluxPipeline,
            AutoPipelineForText2Image=None,
        )

        def fake_import_module(name: str) -> object:
            if name == "torch":
                return torch_module
            if name == "diffusers":
                return diffusers_module
            raise AssertionError(f"unexpected import: {name}")

        with patch("flux_service.runtime.importlib.import_module", side_effect=fake_import_module):
            _load_diffusers_pipeline(FluxRuntimeConfig(model_repo="black-forest-labs/FLUX.1-schnell"))

        self.assertIsNotNone(FluxPipeline.loaded)
        repo, kwargs = FluxPipeline.loaded
        self.assertEqual(repo, "black-forest-labs/FLUX.1-schnell")
        self.assertEqual(kwargs["torch_dtype"], "bfloat16")

    def test_diffusers_loader_falls_back_to_auto_pipeline(self) -> None:
        class LoadedPipeline:
            def to(self, _device: str) -> None:
                return None

        class AutoPipelineForText2Image:
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
        )
        diffusers_module = SimpleNamespace(
            Flux2KleinPipeline=None,
            FluxPipeline=None,
            AutoPipelineForText2Image=AutoPipelineForText2Image,
        )

        def fake_import_module(name: str) -> object:
            if name == "torch":
                return torch_module
            if name == "diffusers":
                return diffusers_module
            raise AssertionError(f"unexpected import: {name}")

        with patch("flux_service.runtime.importlib.import_module", side_effect=fake_import_module):
            _load_diffusers_pipeline(FluxRuntimeConfig(model_repo="local-text-to-image"))

        self.assertIsNotNone(AutoPipelineForText2Image.loaded)
        repo, kwargs = AutoPipelineForText2Image.loaded
        self.assertEqual(repo, "local-text-to-image")
        self.assertEqual(kwargs["torch_dtype"], "bfloat16")

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

    def test_generate_filters_unsupported_pipeline_kwargs(self) -> None:
        fake_pipeline = _SignatureLimitedPipeline()
        runtime = FluxRuntime(
            config=FluxRuntimeConfig(
                backend="diffusers",
                model_repo="local-text-to-image",
                num_inference_steps=3,
                guidance_scale=1.0,
                max_sequence_length=512,
            ),
            pipeline_loader=lambda _config: fake_pipeline,
        )

        runtime.generate(InitGenerateRequest(scene_plan=self.plan, seed=1200, provider="flux-local"))

        self.assertNotIn("max_sequence_length", fake_pipeline.calls[0])
        self.assertEqual(fake_pipeline.calls[0]["guidance_scale"], 1.0)

    def test_disabled_backend_raises_clear_error(self) -> None:
        runtime = FluxRuntime(config=FluxRuntimeConfig(backend="disabled"))

        with self.assertRaisesRegex(RuntimeError, "disabled"):
            runtime.generate(InitGenerateRequest(scene_plan=self.plan, seed=1200, provider="flux-local"))


if __name__ == "__main__":
    unittest.main()
