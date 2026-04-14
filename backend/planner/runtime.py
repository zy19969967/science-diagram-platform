from __future__ import annotations

import importlib
import json
import logging
import os
import re
import threading
from typing import Any

from common.assets import get_asset, load_asset_catalog
from common.planner_logic import build_plan
from common.schemas import PlanRequest, PlanResponse, TaskType
from common.utils.images import decode_data_url_to_image

LOGGER = logging.getLogger(__name__)
VALID_TASKS: set[TaskType] = {
    "text-guided",
    "object-removal",
    "shape-guided",
    "image-outpainting",
}


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


def _extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    for candidate in (cleaned, cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]):
        if candidate and candidate.startswith("{") and candidate.endswith("}"):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("Planner model did not return a JSON object.")
    return json.loads(match.group(0))


def _coerce_warning_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                result.append(text)
        return result
    return []


def _planner_prompt(
    *,
    instruction: str,
    selected_asset: dict[str, Any] | None,
    preferred_task: str | None,
    canvas_hints: dict[str, Any],
    available_assets: list[dict[str, Any]],
) -> str:
    schema = {
        "task": "One of: text-guided, object-removal, shape-guided, image-outpainting",
        "task_prompt": "Short English prompt for PowerPaint",
        "negative_prompt": "Short English negative prompt for PowerPaint",
        "target_label": "Optional Chinese or English label for the target object",
        "recommended_asset_id": "Asset id from the provided list or null",
        "mask_strategy": "Prefer 'sam2-refine' when image/object segmentation is helpful, otherwise 'user-mask'",
        "reasoning": "One short Chinese sentence",
        "warnings": ["Zero or more short Chinese warnings"],
    }
    rules = [
        "If the user is deleting or cleaning an existing object, choose object-removal.",
        "If the user is extending the canvas or background, choose image-outpainting.",
        "If the user selected an asset or wants the result to follow a silhouette or region, choose shape-guided.",
        "Otherwise choose text-guided.",
        "Prefer clear scientific-illustration wording and protect labels, arrows, and geometry.",
        "If no listed asset is suitable, return null for recommended_asset_id.",
        "Return JSON only, with no markdown fences.",
    ]
    payload = {
        "instruction": instruction or "",
        "selected_asset": selected_asset,
        "preferred_task": preferred_task,
        "canvas_hints": canvas_hints,
        "available_assets": available_assets,
        "response_schema": schema,
        "decision_rules": rules,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


class PlannerRuntime:
    def __init__(self) -> None:
        self.backend = os.getenv("PLANNER_BACKEND", "qwen3.5")
        self.model_repo = os.getenv("PLANNER_MODEL_REPO", "Qwen/Qwen3.5-4B")
        self.model_dtype = os.getenv("PLANNER_MODEL_DTYPE", "float16")
        self.max_new_tokens = int(os.getenv("PLANNER_MAX_NEW_TOKENS", "320"))
        self.local_files_only = _as_bool(os.getenv("PLANNER_LOCAL_FILES_ONLY"), default=False)
        self.attn_impl = os.getenv("PLANNER_ATTN_IMPL", "sdpa")
        self._lock = threading.Lock()
        self._model: Any | None = None
        self._processor: Any | None = None
        self._torch: Any | None = None
        self._device: str = "cpu"
        self._last_error: str | None = None

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "planner",
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
                if self.attn_impl:
                    load_kwargs["attn_implementation"] = self.attn_impl
                self._device = "cuda"
            else:
                self._device = "cpu"

            self._processor = transformers.AutoProcessor.from_pretrained(
                self.model_repo,
                local_files_only=self.local_files_only,
            )
            self._model = transformers.AutoModelForImageTextToText.from_pretrained(
                self.model_repo,
                **load_kwargs,
            )
            if self._device == "cpu":
                self._model.to(self._device)

            self._torch = torch_module
            self._last_error = None
            return True

    def _messages(self, prompt: str, include_image: bool) -> list[dict[str, Any]]:
        system_text = (
            "You are the planning service for a scientific diagram editing platform built on PowerPaint. "
            "Return a single compact JSON object only. Use English for task_prompt and negative_prompt. "
            "Use Chinese for reasoning and warnings."
        )
        user_content: list[dict[str, str]] = []
        if include_image:
            user_content.append({"type": "image"})
        user_content.append({"type": "text", "text": prompt})
        return [
            {"role": "system", "content": [{"type": "text", "text": system_text}]},
            {"role": "user", "content": user_content},
        ]

    def _normalize(self, payload: PlanRequest, raw: dict[str, Any]) -> PlanResponse:
        fallback = build_plan(payload)
        task = raw.get("task") if raw.get("task") in VALID_TASKS else fallback.task
        task_prompt = str(raw.get("task_prompt") or fallback.task_prompt).strip()
        negative_prompt = str(raw.get("negative_prompt") or fallback.negative_prompt).strip()
        target_label = str(raw.get("target_label") or fallback.target_label or "").strip() or None

        recommended_asset_id = raw.get("recommended_asset_id")
        if recommended_asset_id and not get_asset(str(recommended_asset_id)):
            recommended_asset_id = None
        recommended_asset_id = str(recommended_asset_id).strip() if recommended_asset_id else fallback.recommended_asset_id

        mask_strategy = str(raw.get("mask_strategy") or fallback.mask_strategy).strip() or fallback.mask_strategy
        reasoning = str(raw.get("reasoning") or fallback.reasoning).strip() or fallback.reasoning
        warnings = fallback.warnings + [
            warning
            for warning in _coerce_warning_list(raw.get("warnings"))
            if warning not in fallback.warnings
        ]

        return PlanResponse(
            task=task,
            task_prompt=task_prompt,
            negative_prompt=negative_prompt,
            target_label=target_label,
            recommended_asset_id=recommended_asset_id,
            mask_strategy=mask_strategy,
            reasoning=reasoning,
            warnings=warnings,
        )

    def plan(self, payload: PlanRequest) -> PlanResponse | None:
        if not self._enabled():
            return None
        try:
            self._load()
            source_image = decode_data_url_to_image(payload.source_image, mode="RGB") if payload.source_image else None
            selected_asset = get_asset(payload.selected_asset_id)
            prompt = _planner_prompt(
                instruction=payload.instruction,
                selected_asset=selected_asset.model_dump() if selected_asset else None,
                preferred_task=payload.preferred_task,
                canvas_hints=payload.canvas_hints,
                available_assets=[
                    {
                        "id": asset.id,
                        "name": asset.name,
                        "category": asset.category,
                        "prompt": asset.prompt,
                    }
                    for asset in load_asset_catalog()
                ],
            )
            messages = self._messages(prompt, include_image=source_image is not None)
            template = self._processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

            processor_kwargs: dict[str, Any] = {"text": template, "return_tensors": "pt"}
            if source_image is not None:
                processor_kwargs["images"] = source_image

            inputs = self._processor(**processor_kwargs)
            if hasattr(inputs, "to"):
                inputs = inputs.to(self._device)
            else:
                inputs = {name: value.to(self._device) if hasattr(value, "to") else value for name, value in inputs.items()}

            with self._torch.no_grad():
                generated_ids = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)

            input_len = inputs["input_ids"].shape[-1]
            decoded = self._processor.batch_decode(generated_ids[:, input_len:], skip_special_tokens=True)[0].strip()
            raw = _extract_json_block(decoded)
            self._last_error = None
            return self._normalize(payload, raw)
        except Exception as exc:
            self._last_error = str(exc)
            LOGGER.exception("Qwen planner fallback triggered: %s", exc)
            return None


planner_runtime = PlannerRuntime()
