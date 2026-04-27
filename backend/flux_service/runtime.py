from __future__ import annotations

import importlib
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


@dataclass(frozen=True)
class FluxRuntimeConfig:
    backend: str = "diffusers"
    model_repo: str = "black-forest-labs/FLUX.1-schnell"
    model_dtype: str = "bfloat16"
    local_files_only: bool = False
    num_inference_steps: int = 4
    guidance_scale: float = 0.0
    max_sequence_length: int = 256

    @classmethod
    def from_env(cls) -> "FluxRuntimeConfig":
        return cls(
            backend=os.getenv("FLUX_BACKEND", "diffusers"),
            model_repo=os.getenv("FLUX_MODEL_REPO", "black-forest-labs/FLUX.1-schnell"),
            model_dtype=os.getenv("FLUX_MODEL_DTYPE", "bfloat16"),
            local_files_only=_as_bool(os.getenv("FLUX_LOCAL_FILES_ONLY"), default=False),
            num_inference_steps=_as_int(os.getenv("FLUX_NUM_INFERENCE_STEPS"), 4),
            guidance_scale=_as_float(os.getenv("FLUX_GUIDANCE_SCALE"), 0.0),
            max_sequence_length=_as_int(os.getenv("FLUX_MAX_SEQUENCE_LENGTH"), 256),
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
    clamped = min(2048, max(256, int(value)))
    return max(256, clamped - (clamped % 8))


def build_flux_prompt(plan: ScenePlanResponse) -> str:
    labels = ", ".join(plan.labels)
    objects = "; ".join(f"{item.name}: {item.visual}, {item.position}" for item in plan.objects)
    relations = "; ".join(f"{item.source} {item.type} {item.target}" for item in plan.relations)
    return (
        f"{plan.positive_prompt}. "
        f"Create a clean scientific diagram with accurate composition, crisp edges, controlled color, "
        f"white background, readable scientific labels, and vector-like layout. "
        f"Diagram type: {plan.diagram_type}. Labels: {labels}. Objects: {objects}. Relations: {relations}. "
        f"Style: {plan.style}. User instruction: {plan.instruction}."
    )


def _load_diffusers_pipeline(config: FluxRuntimeConfig) -> Any:
    torch_module = importlib.import_module("torch")
    diffusers = importlib.import_module("diffusers")
    pipeline_cls = getattr(diffusers, "FluxPipeline", None) or getattr(diffusers, "AutoPipelineForText2Image")
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
        result = pipeline(**kwargs)
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
