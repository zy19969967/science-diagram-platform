from __future__ import annotations

import importlib
import logging
import os
import threading
from typing import Any

import numpy as np
from PIL import Image

from common.schemas import SegmentRequest, SegmentResponse
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url
from common.utils.masks import compute_mask_bbox, coverage_ratio, normalize_mask, placement_to_box

LOGGER = logging.getLogger(__name__)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_torch_dtype(torch_module: Any, value: str | None) -> Any | None:
    normalized = (value or "auto").strip().lower()
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


class SegmenterRuntime:
    def __init__(self) -> None:
        self.backend = os.getenv("SEGMENTER_BACKEND", "sam2")
        self.model_repo = os.getenv("SEGMENTER_MODEL_REPO", "facebook/sam2.1-hiera-base-plus")
        self.model_dtype = os.getenv("SEGMENTER_MODEL_DTYPE", "float16")
        self.local_files_only = _as_bool(os.getenv("SEGMENTER_LOCAL_FILES_ONLY"), default=False)
        self.box_padding_ratio = float(os.getenv("SEGMENTER_BOX_PADDING_RATIO", "0.18"))
        self.mask_threshold = float(os.getenv("SEGMENTER_MASK_THRESHOLD", "0.0"))
        self.use_placement_box = _as_bool(os.getenv("SEGMENTER_USE_PLACEMENT_BOX"), default=False)
        self._lock = threading.Lock()
        self._model: Any | None = None
        self._processor: Any | None = None
        self._torch: Any | None = None
        self._device: str = "cpu"
        self._last_error: str | None = None

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "segmenter",
            "backend": self.backend,
            "model_repo": self.model_repo,
            "loaded": self._model is not None,
            "device": self._device,
            "last_error": self._last_error,
        }

    def _enabled(self) -> bool:
        return self.backend.strip().lower() not in {"heuristic", "disabled", "off"}

    def _load(self) -> bool:
        if not self._enabled():
            return False
        if self._model is not None and self._processor is not None and self._torch is not None:
            return True

        with self._lock:
            if self._model is not None and self._processor is not None and self._torch is not None:
                return True

            torch_module = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")
            load_kwargs: dict[str, Any] = {
                "local_files_only": self.local_files_only,
                "low_cpu_mem_usage": True,
            }
            torch_dtype = _resolve_torch_dtype(torch_module, self.model_dtype)
            if torch_dtype is not None:
                load_kwargs["torch_dtype"] = torch_dtype
            if torch_module.cuda.is_available():
                load_kwargs["device_map"] = "auto"
                self._device = "cuda"
            else:
                self._device = "cpu"

            self._processor = transformers.Sam2Processor.from_pretrained(
                self.model_repo,
                local_files_only=self.local_files_only,
            )
            self._model = transformers.Sam2Model.from_pretrained(
                self.model_repo,
                **load_kwargs,
            )
            if self._device == "cpu":
                self._model.to(self._device)

            self._torch = torch_module
            self._last_error = None
            return True

    def _expand_box(self, box: list[int], width: int, height: int) -> list[int]:
        x1, y1, x2, y2 = box
        pad_x = max(8, int((x2 - x1) * self.box_padding_ratio))
        pad_y = max(8, int((y2 - y1) * self.box_padding_ratio))
        return [
            max(0, x1 - pad_x),
            max(0, y1 - pad_y),
            min(width, x2 + pad_x),
            min(height, y2 + pad_y),
        ]

    def _build_prompt_box(self, payload: SegmentRequest, size: tuple[int, int]) -> list[int] | None:
        width, height = size
        if payload.mask_image:
            rough_mask = decode_data_url_to_image(payload.mask_image, mode="L")
            rough_mask = normalize_mask(rough_mask, size)
            bbox = compute_mask_bbox(rough_mask)
            if bbox:
                return self._expand_box(bbox, width, height)
        if payload.box:
            return self._expand_box(payload.box, width, height)
        if payload.asset_placement and self.use_placement_box:
            return self._expand_box(placement_to_box(width, height, payload.asset_placement), width, height)
        return None

    def _select_best_mask(self, masks: Any, scores: Any | None) -> Any | None:
        if masks is None:
            return None
        if hasattr(masks, "detach"):
            masks = masks.detach().cpu().numpy()
        masks = np.asarray(masks)
        if masks.size == 0:
            return None

        score_array = None
        if scores is not None:
            if hasattr(scores, "detach"):
                scores = scores.detach().cpu().numpy()
            score_array = np.asarray(scores)

        if masks.ndim == 4:
            mask_candidates = masks[0]
            score_candidates = score_array[0][0] if score_array is not None and score_array.ndim >= 3 else None
        elif masks.ndim == 3:
            mask_candidates = masks
            score_candidates = score_array[0] if score_array is not None and score_array.ndim >= 2 else None
        else:
            return masks

        if score_candidates is not None and len(score_candidates) == len(mask_candidates):
            return mask_candidates[int(np.argmax(score_candidates))]
        return mask_candidates[0]

    def _mask_to_image(self, mask: Any) -> Image.Image:
        array = np.asarray(mask)
        if array.ndim > 2:
            array = np.squeeze(array)
        binary = (array > self.mask_threshold).astype(np.uint8) * 255
        return Image.fromarray(binary, mode="L")

    def segment(self, payload: SegmentRequest) -> SegmentResponse | None:
        if not self._enabled() or not payload.source_image:
            return None
        try:
            self._load()
            source_image = decode_data_url_to_image(payload.source_image, mode="RGB")
            prompt_box = self._build_prompt_box(payload, source_image.size)
            if prompt_box is None:
                return None

            inputs = self._processor(images=source_image, input_boxes=[[prompt_box]], return_tensors="pt")
            original_sizes = inputs["original_sizes"]
            if hasattr(inputs, "to"):
                inputs = inputs.to(self._device)
            else:
                inputs = {name: value.to(self._device) if hasattr(value, "to") else value for name, value in inputs.items()}

            with self._torch.no_grad():
                outputs = self._model(**inputs, multimask_output=True)

            processed_masks = self._processor.post_process_masks(outputs.pred_masks.cpu(), original_sizes)
            best_mask = self._select_best_mask(processed_masks[0], getattr(outputs, "iou_scores", None))
            if best_mask is None:
                return None

            normalized_mask = normalize_mask(self._mask_to_image(best_mask), size=(payload.width, payload.height))
            bbox = compute_mask_bbox(normalized_mask)
            if bbox is None:
                return None

            self._last_error = None
            return SegmentResponse(
                mask_image=encode_image_to_data_url(normalized_mask),
                coverage_ratio=coverage_ratio(normalized_mask),
                bounding_box=bbox,
            )
        except Exception as exc:
            self._last_error = str(exc)
            LOGGER.exception("SAM2 segmenter fallback triggered: %s", exc)
            return None


segmenter_runtime = SegmenterRuntime()
