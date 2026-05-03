from __future__ import annotations

from typing import Any

from .schemas import SmartGenerationRequest, SmartPipeline, SmartPlannerDecision, SmartTaskType


STRUCTURE_KEYWORDS = (
    "svg",
    "图标",
    "流程图",
    "结构图",
    "矢量",
    "diagram",
    "flowchart",
    "icon",
)
OUTPAINT_KEYWORDS = ("扩图", "扩展", "补边", "outpaint", "extend", "expand")
VARIATION_KEYWORDS = (
    "电影感",
    "动漫",
    "油画",
    "风格",
    "质感",
    "增强",
    "整体",
    "variation",
    "style",
)
REMOVE_KEYWORDS = ("删除", "移除", "去掉", "清除", "remove", "delete", "erase")
REPLACE_KEYWORDS = ("替换", "换成", "改成", "变成", "replace", "change")
REPAIR_KEYWORDS = ("修复", "修一下", "处理", "repair", "fix")

LOCAL_EDIT_NEGATIVE_PROMPT = "低质量，模糊，畸形，边缘破损，背景变化，颜色溢出"
TEXT_TO_IMAGE_NEGATIVE_PROMPT = "模糊，畸形，低质量，乱码文字，水印"
DEFAULT_MASK_DILATION = 16
DEFAULT_MASK_BLUR = 12


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in text or keyword in lowered for keyword in keywords)


def _subtask_for(prompt: str) -> str:
    if _contains_any(prompt, REMOVE_KEYWORDS):
        return "object_removal"
    if _contains_any(prompt, REPLACE_KEYWORDS):
        return "object_replacement"
    if _contains_any(prompt, REPAIR_KEYWORDS):
        return "repair"
    if "背景" in prompt or "background" in prompt.lower():
        return "background_edit"
    if "颜色" in prompt or "color" in prompt.lower():
        return "color_change"
    return "attribute_edit"


def _pipeline_for_task(task_type: SmartTaskType, *, has_mask: bool) -> SmartPipeline:
    if task_type == "text_to_image":
        return "flux_text_to_image"
    if task_type == "image_variation":
        return "powerpaint_variation"
    if task_type == "outpainting":
        return "powerpaint_outpaint"
    if task_type == "svg_or_structure_generation":
        return "svg_structure"
    if task_type == "local_inpaint" and has_mask:
        return "powerpaint_inpaint"
    return "needs_user_input"


def _normalized_prompt(task_type: SmartTaskType, subtask_type: str, prompt: str) -> str:
    stripped = prompt.strip()
    if task_type == "local_inpaint":
        action = stripped or "修改被涂抹区域"
        return f"将被涂抹区域{action}，保持主体、背景、光照和画面风格不变。"
    if task_type == "outpainting":
        return stripped or "扩展画布内容，保持原图结构、光照和风格一致。"
    if task_type == "image_variation":
        return stripped or "整体优化这张图，保持主体内容和构图稳定。"
    if task_type == "svg_or_structure_generation":
        return stripped or "生成清晰的结构化科学示意图。"
    return stripped or "生成一张清晰、干净的科学示意图。"


def _decision(
    *,
    request: SmartGenerationRequest,
    task_type: SmartTaskType,
    subtask_type: str,
    confidence: float,
    requires_mask: bool,
    need_user_clarification: bool = False,
    clarification_question: str = "",
    can_auto_segment: bool = False,
    warnings: list[str] | None = None,
) -> SmartPlannerDecision:
    has_mask = bool(request.mask_image)
    pipeline = _pipeline_for_task(task_type, has_mask=has_mask)
    if need_user_clarification:
        pipeline = "needs_user_input"
    return SmartPlannerDecision(
        task_type=task_type,
        subtask_type=subtask_type,
        confidence=confidence,
        need_user_clarification=need_user_clarification,
        clarification_question=clarification_question,
        normalized_prompt=_normalized_prompt(task_type, subtask_type, request.prompt),
        negative_prompt=LOCAL_EDIT_NEGATIVE_PROMPT if task_type in {"local_inpaint", "outpainting", "image_variation"} else TEXT_TO_IMAGE_NEGATIVE_PROMPT,
        pipeline=pipeline,
        requires_mask=requires_mask,
        can_auto_segment=can_auto_segment,
        preserve_background=task_type in {"local_inpaint", "outpainting"},
        preserve_identity=task_type == "local_inpaint" and subtask_type not in {"object_removal", "object_replacement"},
        preserve_style=True,
        warnings=warnings or [],
    )


def build_smart_generation_plan(request: SmartGenerationRequest) -> SmartPlannerDecision:
    prompt = request.prompt.strip()
    has_image = bool(request.source_image or request.image_id)
    has_mask = bool(request.mask_image or request.mask_id)
    override = request.options.task_override

    if override:
        return _decision(
            request=request,
            task_type=override,
            subtask_type="user_override",
            confidence=1.0,
            requires_mask=override in {"local_inpaint", "outpainting"},
            need_user_clarification=override == "local_inpaint" and not has_mask,
            clarification_question="请涂抹你想修改的区域，这样局部编辑会更稳定。" if override == "local_inpaint" and not has_mask else "",
        )

    if not has_image:
        if _contains_any(prompt, STRUCTURE_KEYWORDS):
            return _decision(
                request=request,
                task_type="svg_or_structure_generation",
                subtask_type="structure",
                confidence=0.86,
                requires_mask=False,
            )
        return _decision(
            request=request,
            task_type="text_to_image",
            subtask_type="general",
            confidence=0.88,
            requires_mask=False,
        )

    if _contains_any(prompt, OUTPAINT_KEYWORDS):
        return _decision(
            request=request,
            task_type="outpainting",
            subtask_type="background_extension",
            confidence=0.9,
            requires_mask=False,
        )

    if has_mask:
        return _decision(
            request=request,
            task_type="local_inpaint",
            subtask_type=_subtask_for(prompt),
            confidence=0.93,
            requires_mask=True,
        )

    if _contains_any(prompt, VARIATION_KEYWORDS):
        return _decision(
            request=request,
            task_type="image_variation",
            subtask_type="style_or_quality_variation",
            confidence=0.82,
            requires_mask=False,
        )

    if _contains_any(prompt, (*REMOVE_KEYWORDS, *REPLACE_KEYWORDS, *REPAIR_KEYWORDS)):
        return _decision(
            request=request,
            task_type="local_inpaint",
            subtask_type=_subtask_for(prompt),
            confidence=0.79,
            requires_mask=True,
            need_user_clarification=True,
            clarification_question="请涂抹你想修改的区域，这样局部编辑会更稳定。",
            can_auto_segment=False,
            warnings=["当前没有可用的自动文本定位结果，建议用户补充选区。"],
        )

    return _decision(
        request=request,
        task_type="local_inpaint",
        subtask_type="ambiguous_region",
        confidence=0.55,
        requires_mask=True,
        need_user_clarification=True,
        clarification_question="请说明要修改的位置，或直接涂抹你想修改的区域。",
        warnings=["局部区域不明确，已暂停生成以避免大范围误改。"],
    )


def smart_metadata(
    *,
    request: SmartGenerationRequest,
    decision: SmartPlannerDecision,
    fallback_used: bool,
    is_diagnostic_result: bool,
    provider: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "task_type": decision.task_type,
        "subtask_type": decision.subtask_type,
        "planner_task": decision.task_type,
        "user_task_override": request.options.task_override,
        "planner_confidence": decision.confidence,
        "original_prompt": request.prompt,
        "normalized_prompt": decision.normalized_prompt,
        "negative_prompt": decision.negative_prompt,
        "provider": provider,
        "fallback_used": fallback_used,
        "is_diagnostic_result": is_diagnostic_result,
        "seed": request.options.seed,
        "steps": request.options.steps,
        "guidance_scale": request.options.guidance_scale,
        "scheduler": None,
        "resize_strategy": "crop_based" if decision.task_type == "local_inpaint" else "provider_default",
        "has_mask": bool(request.mask_image or request.mask_id),
        "mask_coverage": None,
        "mask_bbox": None,
        "mask_inverted": False,
        "mask_dilation": DEFAULT_MASK_DILATION,
        "mask_blur": DEFAULT_MASK_BLUR,
        "crop_enabled": decision.task_type == "local_inpaint",
        "crop_bbox": None,
        "postprocess_blending": "soft_mask_blend" if decision.task_type == "local_inpaint" else "provider_default",
    }
    if extra:
        metadata.update(extra)
    return metadata
