from __future__ import annotations

import importlib
import inspect
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PIL import Image

from common.init_logic import FLUX_LOCAL_PROVIDER, score_and_rank_init_candidates
from common.schemas import InitCandidate, InitGenerateRequest, InitGenerateResponse, ScenePlanResponse
from common.utils.images import encode_image_to_data_url

LOGGER = logging.getLogger(__name__)
PipelineLoader = Callable[["FluxRuntimeConfig"], Any]
DEFAULT_FLUX_MODEL_REPO = "black-forest-labs/FLUX.2-klein-4B"
DEFAULT_FLUX_GUIDANCE_SCALE = 1.0
DEFAULT_FLUX_MAX_SEQUENCE_LENGTH = 512
DEFAULT_FLUX1_GUIDANCE_SCALE = 0.0
DEFAULT_FLUX1_MAX_SEQUENCE_LENGTH = 256


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _is_flux1_model_repo(model_repo: str) -> bool:
    return "flux.1" in model_repo.strip().lower()


def _default_guidance_scale_for_model(model_repo: str) -> float:
    if _is_flux1_model_repo(model_repo):
        return DEFAULT_FLUX1_GUIDANCE_SCALE
    return DEFAULT_FLUX_GUIDANCE_SCALE


def _default_max_sequence_length_for_model(model_repo: str) -> int:
    if _is_flux1_model_repo(model_repo):
        return DEFAULT_FLUX1_MAX_SEQUENCE_LENGTH
    return DEFAULT_FLUX_MAX_SEQUENCE_LENGTH


@dataclass(frozen=True)
class FluxRuntimeConfig:
    backend: str = "diffusers"
    model_repo: str = DEFAULT_FLUX_MODEL_REPO
    model_dtype: str = "bfloat16"
    local_files_only: bool = False
    num_inference_steps: int = 4
    guidance_scale: float | None = None
    max_sequence_length: int | None = None

    def __post_init__(self) -> None:
        if self.guidance_scale is None:
            object.__setattr__(self, "guidance_scale", _default_guidance_scale_for_model(self.model_repo))
        if self.max_sequence_length is None:
            object.__setattr__(self, "max_sequence_length", _default_max_sequence_length_for_model(self.model_repo))

    @classmethod
    def from_env(cls) -> "FluxRuntimeConfig":
        model_repo = os.getenv("FLUX_MODEL_REPO", DEFAULT_FLUX_MODEL_REPO)
        guidance_scale = (
            None
            if os.getenv("FLUX_GUIDANCE_SCALE") is None
            else _as_float(os.getenv("FLUX_GUIDANCE_SCALE"), _default_guidance_scale_for_model(model_repo))
        )
        max_sequence_length = (
            None
            if os.getenv("FLUX_MAX_SEQUENCE_LENGTH") is None
            else _as_int(os.getenv("FLUX_MAX_SEQUENCE_LENGTH"), _default_max_sequence_length_for_model(model_repo))
        )
        return cls(
            backend=os.getenv("FLUX_BACKEND", "diffusers"),
            model_repo=model_repo,
            model_dtype=os.getenv("FLUX_MODEL_DTYPE", "bfloat16"),
            local_files_only=_as_bool(os.getenv("FLUX_LOCAL_FILES_ONLY"), default=False),
            num_inference_steps=_as_int(os.getenv("FLUX_NUM_INFERENCE_STEPS"), 4),
            guidance_scale=guidance_scale,
            max_sequence_length=max_sequence_length,
        )


def _resolve_torch_dtype(torch_module: Any, value: str) -> Any | None:
    normalized = value.strip().lower()
    mapping = {
        "auto": None,
        "float16": getattr(torch_module, "float16", None),
        "fp16": getattr(torch_module, "float16", None),
        "bfloat16": getattr(torch_module, "bfloat16", None),
        "bf16": getattr(torch_module, "bfloat16", None),
        "float32": getattr(torch_module, "float32", None),
        "fp32": getattr(torch_module, "float32", None),
    }
    return mapping.get(normalized)


def _normalize_dimension(value: int) -> int:
    return 1024


def build_flux_prompt(plan: ScenePlanResponse) -> str:
    instruction = plan.instruction.strip()
    if instruction:
        return f"{instruction}. Clean scientific diagram style, white background, vector-like."
    return f"{plan.positive_prompt}. Clean scientific diagram, white background, vector-like."


def _load_diffusers_pipeline(config: FluxRuntimeConfig) -> Any:
    torch_module = importlib.import_module("torch")
    diffusers = importlib.import_module("diffusers")
    pipeline_cls = (
        getattr(diffusers, "Flux2KleinPipeline", None)
        or getattr(diffusers, "FluxPipeline", None)
        or getattr(diffusers, "AutoPipelineForText2Image", None)
    )
    if pipeline_cls is None:
        raise RuntimeError(
            "Installed diffusers does not provide Flux2KleinPipeline, FluxPipeline, "
            "or AutoPipelineForText2Image."
        )
    load_kwargs: dict[str, Any] = {"local_files_only": config.local_files_only}
    torch_dtype = _resolve_torch_dtype(torch_module, config.model_dtype)
    if torch_dtype is not None:
        load_kwargs["torch_dtype"] = torch_dtype

    pipeline = pipeline_cls.from_pretrained(config.model_repo, **load_kwargs)
    if torch_module.cuda.is_available():
        pipeline.to("cuda")
    else:
        pipeline.to("cpu")
    return pipeline


def _supports_pipeline_kwarg(pipeline: Any, key: str) -> bool:
    try:
        signature = inspect.signature(pipeline.__call__)
    except (TypeError, ValueError):
        return True
    return key in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )


def _filter_pipeline_kwargs(pipeline: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if _supports_pipeline_kwarg(pipeline, key)}


class FluxRuntime:
    def __init__(
        self,
        config: FluxRuntimeConfig | None = None,
        pipeline_loader: PipelineLoader = _load_diffusers_pipeline,
    ) -> None:
        self.config = config or FluxRuntimeConfig.from_env()
        self._pipeline_loader = pipeline_loader
        self._lock = threading.Lock()
        self._pipeline: Any | None = None
        self._last_error: str | None = None

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "flux",
            "provider": FLUX_LOCAL_PROVIDER,
            "backend": self.config.backend,
            "model_repo": self.config.model_repo,
            "loaded": self._pipeline is not None,
            "last_error": self._last_error,
        }

    def _enabled(self) -> bool:
        return self.config.backend.strip().lower() not in {"disabled", "off", "none"}

    def _load(self) -> Any:
        if not self._enabled():
            raise RuntimeError("Local FLUX backend is disabled.")
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is None:
                self._pipeline = self._pipeline_loader(self.config)
                self._last_error = None
        return self._pipeline

    def _generator(self, seed: int) -> Any | None:
        try:
            torch_module = importlib.import_module("torch")
            device = "cuda" if torch_module.cuda.is_available() else "cpu"
            return torch_module.Generator(device=device).manual_seed(seed)
        except Exception:
            return None

    def _call_pipeline(self, pipeline: Any, *, prompt: str, seed: int, width: int, height: int) -> Image.Image:
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_inference_steps": self.config.num_inference_steps,
            "guidance_scale": self.config.guidance_scale,
            "max_sequence_length": self.config.max_sequence_length,
        }
        generator = self._generator(seed)
        if generator is not None:
            kwargs["generator"] = generator
        result = pipeline(**_filter_pipeline_kwargs(pipeline, kwargs))
        images = getattr(result, "images", None)
        if not images:
            raise RuntimeError("Local FLUX pipeline returned no images.")
        image = images[0]
        if not isinstance(image, Image.Image):
            raise RuntimeError("Local FLUX pipeline returned a non-PIL image.")
        return image.convert("RGB")

    def generate(self, payload: InitGenerateRequest) -> InitGenerateResponse:
        try:
            pipeline = self._load()
            plan = payload.scene_plan
            base_seed = plan.seed if payload.seed is None else payload.seed
            prompt = build_flux_prompt(plan)
            width = _normalize_dimension(plan.width)
            height = _normalize_dimension(plan.height)
            candidates: list[InitCandidate] = []
            for index in range(plan.candidate_count):
                candidate_seed = base_seed + index
                image = self._call_pipeline(
                    pipeline,
                    prompt=prompt,
                    seed=candidate_seed,
                    width=width,
                    height=height,
                )
                candidates.append(
                    InitCandidate(
                        id=f"flux_local_{index + 1}",
                        image=encode_image_to_data_url(image),
                        seed=candidate_seed,
                        provider=FLUX_LOCAL_PROVIDER,
                        score=0.88,
                        width=image.width,
                        height=image.height,
                        metadata={
                            "diagram_type": plan.diagram_type,
                            "labels": plan.labels,
                            "render_text_as_vector": plan.render_text_as_vector,
                            "vector_text_layer": False,
                            "provider_source": FLUX_LOCAL_PROVIDER,
                            "model_repo": self.config.model_repo,
                            "backend": self.config.backend,
                        },
                    )
                )
            response = InitGenerateResponse(
                provider=FLUX_LOCAL_PROVIDER,
                scene_plan=plan,
                candidates=candidates,
                requested_provider=payload.provider,
                used_provider=FLUX_LOCAL_PROVIDER,
                fallback_used=False,
                warnings=[],
            )
            self._last_error = None
            return score_and_rank_init_candidates(response)
        except Exception as exc:
            self._last_error = str(exc)
            if "disabled" not in str(exc).lower():
                LOGGER.exception("Local FLUX generation failed: %s", exc)
            raise


flux_runtime = FluxRuntime()
