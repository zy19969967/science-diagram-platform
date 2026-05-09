from __future__ import annotations

import importlib
import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.assets import get_asset, load_asset_catalog
from common.planner_logic import build_plan
from common.schemas import (
    PlanRequest,
    PlanResponse,
    QwenEditPromptRequest,
    QwenEditPromptResponse,
    ScenePlanRequest,
    TaskType,
)
from common.utils.images import decode_data_url_to_image

LOGGER = logging.getLogger(__name__)
QWEN_LOGS_DIR = Path("logs/qwen_plans")
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
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
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
        "task": "One of: text-guided (for adding/replacing objects), object-removal (for deleting/erasing), shape-guided (for fitting to a drawn shape), image-outpainting (for expanding canvas)",
        "task_prompt": (
            "Detailed English prompt describing WHAT to generate in the masked region. "
            "Be specific: name the object, its color, material, shape, and how it fits the scene. "
            "For replacement: describe the NEW object to place there. "
            "For removal: describe the background to fill in. "
            "Do NOT describe the action — describe the desired RESULT."
        ),
        "negative_prompt": "English negative prompt: what to avoid (blurry, distorted, artifacts, etc.)",
        "target_label": "Optional Chinese or English label for the target object",
        "recommended_asset_id": "Asset id from the provided list or null",
        "mask_strategy": "Use 'sam2-refine' ONLY when point_prompts are provided (user clicked on image). Otherwise always use 'user-mask'.",
        "reasoning": "One short Chinese sentence",
        "warnings": ["Zero or more short Chinese warnings"],
    }
    rules = [
        "If the user wants to delete, erase, remove, or clean an object, choose object-removal. The task_prompt must describe the clean background to fill in. CRITICAL: the negative_prompt MUST name the object being removed (translate to English), plus 'remnants, ghost, regenerated' to prevent the model from drawing it again.",
        "If the user wants to extend, expand, or outpaint the canvas, choose image-outpainting.",
        "If the user selected an asset or wants to follow a specific shape/silhouette, choose shape-guided.",
        "If the user wants to replace, swap, change, or transform an object into something else, choose text-guided. The task_prompt MUST describe the NEW target object in detail (color, material, type).",
        "Otherwise choose text-guided. The task_prompt must be a detailed visual description of what should appear in the masked area.",
        "Look at the user's instruction carefully. Extract the TARGET object they want (e.g., from 'replace cup with red vase' -> target is 'red vase').",
        "If the instruction is in Chinese, translate the target description into English for the task_prompt.",
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


def _qwen_edit_prompt_rewrite_prompt(payload: QwenEditPromptRequest) -> str:
    schema = {
        "prompt": "一条中文 Qwen-Image-Edit 指令，一到两句话。",
        "negative_prompt": "默认返回一个空格，除非用户明确给出要避免的内容。",
        "warnings": ["可选的简短中文提示。"],
    }
    rules = [
        "只改写 Qwen-Image-Edit 的执行指令，不重新规划画面。",
        "必须使用中文输出，用户 instruction 是唯一权威；plan_prompt 只作低优先级视觉参考，冲突时忽略 plan_prompt。",
        "保持用户原意、动作方向和数量，不要自行拆分目标。",
        "如果用户说“把 A 变成 B”，输出也必须表达“把 A 变成 B”或“把选区内容改成 B”，绝不能写成“在 B 内添加 A”。",
        "如果用户说“删除 A”，输出也必须表达删除 A，不能改成添加或替换。",
        "不要把删除、替换、重绘写成不同模板；直接保留用户要做的动作。",
        "指令要短、直接、具体，不添加长负面约束或未要求的新内容。",
        "可以加入一句很短的选区约束，例如：只修改 mask 内区域。",
        "科学图只加很短风格提示：保持科学线稿风格。",
        "写实图只加很短风格提示：保持照片风格，光照和材质一致。",
        "如果用户说锥形瓶，按常识写为窄颈、宽底，不要写成宽口、窄底。",
        "negative_prompt 返回单个空格。",
        "只返回 JSON，不要 markdown 代码块。",
    ]
    return json.dumps(
        {
            "instruction": payload.instruction.strip(),
            "task": payload.task,
            "plan_prompt": payload.plan_prompt.strip(),
            "source_style": payload.source_style,
            "has_mask": payload.has_mask,
            "fallback_prompt": payload.fallback_prompt.strip(),
            "response_schema": schema,
            "rules": rules,
        },
        ensure_ascii=False,
        indent=2,
    )


def _normalize_qwen_edit_prompt(payload: QwenEditPromptRequest, raw: dict[str, Any]) -> QwenEditPromptResponse:
    prompt = str(raw.get("prompt") or payload.fallback_prompt).strip()
    if not prompt:
        prompt = payload.fallback_prompt.strip()
    negative_prompt = str(raw.get("negative_prompt") or " ").strip() or " "
    warnings = _coerce_warning_list(raw.get("warnings"))
    return QwenEditPromptResponse(
        prompt=prompt,
        negative_prompt=negative_prompt,
        source="qwen3.5-enhancer",
        warnings=warnings,
    )


def _save_qwen_log(payload: dict[str, Any], raw: dict[str, Any], normalized: dict[str, Any], method: str) -> None:
    try:
        QWEN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{ts}_{uuid.uuid4().hex[:8]}.json"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "instruction": payload.get("instruction", ""),
            "raw_qwen_output": raw,
            "normalized_plan": normalized,
        }
        (QWEN_LOGS_DIR / filename).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        LOGGER.exception("Failed to save Qwen plan log")


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
            "You are the planning service for an image editing platform built on PowerPaint. "
            "The platform handles both scientific diagrams and real-world photos. "
            "Your job is to produce a detailed English prompt that tells PowerPaint EXACTLY what to generate "
            "in the masked region. Be specific about the object, its color, material, shape, and how it "
            "should blend into the scene. "
            "For object removal or outpainting, the prompt should be empty since PowerPaint auto-fills "
            "based on surrounding context. "
            "For replacement, describe ONLY the new target object, not the old one. "
            "IMPORTANT: the mask_strategy should ALWAYS be 'user-mask' unless the user provided "
            "point_prompts (clicked specific points on the image). "
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

    def _qwen_edit_messages(self, prompt: str) -> list[dict[str, Any]]:
        system_text = (
            "You are a prompt rewriting service for Qwen-Image-Edit. "
            "Convert user edit requests into concise mask-based image editing prompts. "
            "Preserve the user's intent, do not invent extra content, and return a compact JSON object only."
        )
        return [
            {"role": "system", "content": [{"type": "text", "text": system_text}]},
            {"role": "user", "content": [{"type": "text", "text": prompt}]},
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

        # For object removal, ensure the target object is named in the negative prompt
        if task == "object-removal" and target_label:
            suppress_terms = f"regenerated {target_label}, {target_label} remnants, ghost of {target_label}"
            if suppress_terms not in negative_prompt.lower():
                negative_prompt = f"{negative_prompt}, {suppress_terms}"

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
            template = self._processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, enable_thinking=False)

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
            normalized = self._normalize(payload, raw)
            self._last_error = None
            _save_qwen_log(
                {"instruction": payload.instruction, "selected_asset_id": payload.selected_asset_id, "preferred_task": payload.preferred_task},
                raw,
                normalized.model_dump(),
                "plan",
            )
            return normalized
        except Exception as exc:
            self._last_error = str(exc)
            LOGGER.exception("Qwen planner fallback triggered: %s", exc)
            return None

    def enhance_qwen_edit_prompt(self, payload: QwenEditPromptRequest) -> QwenEditPromptResponse | None:
        if not self._enabled():
            return None
        try:
            self._load()
            prompt = _qwen_edit_prompt_rewrite_prompt(payload)
            messages = self._qwen_edit_messages(prompt)
            template = self._processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, enable_thinking=False)
            inputs = self._processor(text=template, return_tensors="pt")
            if hasattr(inputs, "to"):
                inputs = inputs.to(self._device)
            else:
                inputs = {name: value.to(self._device) if hasattr(value, "to") else value for name, value in inputs.items()}

            with self._torch.no_grad():
                generated_ids = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)

            input_len = inputs["input_ids"].shape[-1]
            decoded = self._processor.batch_decode(generated_ids[:, input_len:], skip_special_tokens=True)[0].strip()
            raw = _extract_json_block(decoded)
            normalized = _normalize_qwen_edit_prompt(payload, raw)
            self._last_error = None
            _save_qwen_log(
                {
                    "instruction": payload.instruction,
                    "task": payload.task,
                    "source_style": payload.source_style,
                    "method": "qwen-edit-prompt",
                },
                raw,
                normalized.model_dump(),
                "qwen_edit_prompt",
            )
            return normalized
        except Exception as exc:
            self._last_error = str(exc)
            LOGGER.exception("Qwen edit prompt enhancer fallback triggered: %s", exc)
            return None

    def plan_scene(self, payload: "ScenePlanRequest") -> "ScenePlanResponse | None":
        if not self._enabled():
            return None
        try:
            self._load()
            prompt = _scene_plan_prompt(payload)
            messages = [
                {"role": "system", "content": [{"type": "text", "text": (
                    "You are the scene planning service for a scientific diagram generation platform. "
                    "Given a user's natural language description, output a structured scene plan as a single JSON object. "
                    "The plan will be consumed by FLUX.2 image generation model. "
                    "Use English for prompts and labels. Return JSON only, no markdown fences."
                )}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]},
            ]
            template = self._processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, enable_thinking=False)
            inputs = self._processor(text=template, return_tensors="pt")
            if hasattr(inputs, "to"):
                inputs = inputs.to(self._device)
            else:
                inputs = {k: v.to(self._device) if hasattr(v, "to") else v for k, v in inputs.items()}

            with self._torch.no_grad():
                generated_ids = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)

            input_len = inputs["input_ids"].shape[-1]
            decoded = self._processor.batch_decode(generated_ids[:, input_len:], skip_special_tokens=True)[0].strip()
            raw = _extract_json_block(decoded)
            normalized = _normalize_scene_plan(payload, raw)
            self._last_error = None
            _save_qwen_log(
                {"instruction": payload.instruction, "style": payload.style, "width": payload.width, "height": payload.height},
                raw,
                normalized.model_dump(),
                "plan_scene",
            )
            return normalized
        except Exception as exc:
            self._last_error = str(exc)
            LOGGER.exception("Qwen scene planner failed: %s", exc)
            return None


def _scene_plan_prompt(payload: "ScenePlanRequest") -> str:
    schema = {
        "diagram_type": "e.g. enzyme_reaction_diagram, cell_structure_diagram, laboratory_process_diagram, scientific_process_diagram",
        "objects": [
            {
                "id": "obj_1",
                "name": "Short label in Chinese or English",
                "role": "One of: input, process, output, container, structure, relation",
                "position": "left / center / right",
                "visual": "Brief English visual description for FLUX (e.g. 'rounded protein shape')",
            }
        ],
        "relations": [
            {"source": "obj_1", "target": "obj_2", "type": "arrow"}
        ],
        "labels": ["All object names as a flat list"],
        "positive_prompt": "Complete English prompt for FLUX text-to-image, clean scientific diagram style, white background, vector-like",
        "negative_prompt": "photorealistic, watermark, blurry text, messy labels, extra arrows, 3D rendering",
        "render_text_as_vector": False,
    }
    rules = [
        "Extract 2-5 key scientific objects from the instruction.",
        "Assign each object a spatial position (left/center/right) to form a logical flow.",
        "Connect objects with arrow relations where there is a flow or dependency.",
        "The positive_prompt must be a complete, detailed English prompt suitable for FLUX.2.",
        "Return JSON only, no markdown fences.",
    ]
    return json.dumps({
        "instruction": payload.instruction.strip(),
        "width": payload.width,
        "height": payload.height,
        "style": payload.style,
        "candidate_count": payload.candidate_count,
        "seed": payload.seed,
        "response_schema": schema,
        "rules": rules,
    }, ensure_ascii=False, indent=2)


def _normalize_scene_plan(payload: "ScenePlanRequest", raw: dict[str, Any]) -> "ScenePlanResponse":
    from common.schemas import ScenePlanObject, ScenePlanRelation, ScenePlanResponse as SPR

    objects = []
    for obj in raw.get("objects") or []:
        objects.append(ScenePlanObject(
            id=str(obj.get("id", f"obj_{len(objects)+1}")),
            name=str(obj.get("name", "")),
            role=str(obj.get("role", "structure")),
            position=str(obj.get("position", "center")),
            visual=str(obj.get("visual", "")),
        ))

    relations = []
    for rel in raw.get("relations") or []:
        relations.append(ScenePlanRelation(
            source=str(rel.get("source", "")),
            target=str(rel.get("target", "")),
            type=str(rel.get("type", "arrow")),
        ))

    labels = [str(label) for label in (raw.get("labels") or []) if str(label).strip()]
    if not labels:
        labels = [obj.name for obj in objects if obj.name]

    return SPR(
        diagram_type=str(raw.get("diagram_type", "scientific_process_diagram")),
        width=payload.width,
        height=payload.height,
        instruction=payload.instruction.strip(),
        objects=objects,
        relations=relations,
        labels=labels,
        style=payload.style,
        positive_prompt=str(raw.get("positive_prompt", f"clean scientific diagram, {payload.style}, white background")),
        negative_prompt=str(raw.get("negative_prompt", "photorealistic, watermark, blurry text, messy labels")),
        render_text_as_vector=bool(raw.get("render_text_as_vector", False)),
        candidate_count=payload.candidate_count,
        seed=payload.seed or raw.get("seed", 42),
        provider="qwen3.5",
        warnings=[],
    )


planner_runtime = PlannerRuntime()
