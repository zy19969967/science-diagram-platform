from __future__ import annotations

import importlib
import inspect
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from PIL import Image

from common.schemas import QwenImageEditRequest
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url

LOGGER = logging.getLogger(__name__)

PipelineLoader = Callable[["QwenImageRuntimeConfig"], Any]

DEFAULT_QWEN_IMAGE_MODEL_REPO = "Qwen/Qwen-Image-Edit"


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
class QwenImageRuntimeConfig:
    backend: str = "diffusers"
    model_repo: str = DEFAULT_QWEN_IMAGE_MODEL_REPO
    model_dtype: str = "bfloat16"
    local_files_only: bool = False
    num_inference_steps: int = 50
    true_cfg_scale: float = 4.0
    strength: float = 1.0

    @classmethod
    def from_env(cls) -> "QwenImageRuntimeConfig":
        return cls(
            backend=os.getenv("QWEN_IMAGE_BACKEND", "diffusers"),
            model_repo=os.getenv("QWEN_IMAGE_MODEL_REPO", DEFAULT_QWEN_IMAGE_MODEL_REPO),
            model_dtype=os.getenv("QWEN_IMAGE_MODEL_DTYPE", "bfloat16"),
            local_files_only=_as_bool(os.getenv("QWEN_IMAGE_LOCAL_FILES_ONLY"), default=False),
            num_inference_steps=_as_int(os.getenv("QWEN_IMAGE_NUM_INFERENCE_STEPS"), 50),
            true_cfg_scale=_as_float(os.getenv("QWEN_IMAGE_TRUE_CFG_SCALE"), 4.0),
            strength=_as_float(os.getenv("QWEN_IMAGE_STRENGTH"), 1.0),
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


def _load_diffusers_pipeline(config: QwenImageRuntimeConfig) -> Any:
    torch_module = importlib.import_module("torch")
    diffusers = importlib.import_module("diffusers")
    pipeline_cls = getattr(diffusers, "QwenImageEditInpaintPipeline", None)
    if pipeline_cls is None:
        raise RuntimeError("Installed diffusers does not provide QwenImageEditInpaintPipeline.")

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


class QwenImageRuntime:
    def __init__(
        self,
        config: QwenImageRuntimeConfig | None = None,
        pipeline_loader: PipelineLoader = _load_diffusers_pipeline,
    ) -> None:
        self.config = config or QwenImageRuntimeConfig.from_env()
        self._pipeline_loader = pipeline_loader
        self._lock = threading.Lock()
        self._pipeline: Any | None = None
        self._last_error: str | None = None

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "qwen-image",
            "backend": self.config.backend,
            "model_repo": self.config.model_repo,
            "loaded": self._pipeline is not None,
            "last_error": self._last_error,
        }

    def _enabled(self) -> bool:
        return self.config.backend.strip().lower() not in {"disabled", "off", "none"}

    def _load(self, *, local_files_only: bool | None = None) -> Any:
        if not self._enabled():
            raise RuntimeError("Local Qwen-Image backend is disabled.")
        if self._pipeline is not None:
            return self._pipeline
        load_config = self.config
        if local_files_only and not self.config.local_files_only:
            load_config = replace(self.config, local_files_only=True)
        with self._lock:
            if self._pipeline is None:
                self._pipeline = self._pipeline_loader(load_config)
                self._last_error = None
        return self._pipeline

    def _generator(self, seed: int) -> Any | None:
        try:
            torch_module = importlib.import_module("torch")
            device = "cuda" if torch_module.cuda.is_available() else "cpu"
            return torch_module.Generator(device=device).manual_seed(seed)
        except Exception:
            return None

    def _call_pipeline(self, pipeline: Any, payload: QwenImageEditRequest) -> Image.Image:
        image = decode_data_url_to_image(payload.image, mode="RGB")
        mask_image = decode_data_url_to_image(payload.mask_image, mode="L")
        request_fields = payload.model_fields_set
        kwargs: dict[str, Any] = {
            "image": image,
            "mask_image": mask_image,
            "prompt": payload.prompt,
            "negative_prompt": payload.negative_prompt,
            "num_inference_steps": (
                payload.num_inference_steps
                if "num_inference_steps" in request_fields
                else self.config.num_inference_steps
            ),
            "true_cfg_scale": (
                payload.true_cfg_scale if "true_cfg_scale" in request_fields else self.config.true_cfg_scale
            ),
            "strength": payload.strength if "strength" in request_fields else self.config.strength,
        }
        generator = self._generator(payload.seed)
        if generator is not None:
            kwargs["generator"] = generator

        result = pipeline(**_filter_pipeline_kwargs(pipeline, kwargs))
        images = getattr(result, "images", None)
        if not images:
            raise RuntimeError("Local Qwen-Image pipeline returned no images.")
        result_image = images[0]
        if not isinstance(result_image, Image.Image):
            raise RuntimeError("Local Qwen-Image pipeline returned a non-PIL image.")
        return result_image.convert("RGB")

    def generate(self, payload: QwenImageEditRequest) -> dict[str, str]:
        try:
            pipeline = self._load(local_files_only=payload.local_files_only)
            with self._lock:
                image = self._call_pipeline(pipeline, payload)
            self._last_error = None
            return {"result_image": encode_image_to_data_url(image)}
        except Exception as exc:
            self._last_error = str(exc)
            if "disabled" not in str(exc).lower():
                LOGGER.exception("Local Qwen-Image generation failed: %s", exc)
            raise


qwen_image_runtime = QwenImageRuntime()
