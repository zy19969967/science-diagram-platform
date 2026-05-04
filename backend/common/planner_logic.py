from __future__ import annotations

from .assets import get_asset
from .schemas import PlanRequest, PlanResponse

REMOVE_KEYWORDS = (
    "删除", "移除", "去掉", "清除",
    "erase", "remove", "delete",
)
REPLACE_KEYWORDS = (
    "替换", "换成", "改成", "变成",
    "replace", "change", "swap",
)
OUTPAINT_KEYWORDS = (
    "扩图", "扩展", "补全画布", "补边",
    "outpaint", "extend", "expand",
)
SHAPE_GUIDED_KEYWORDS = (
    "轮廓", "形状", "蒙版", "沿着选区", "贴合",
    "mask",
)


def _contains_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0xF900 <= cp <= 0xFAFF):
            return True
    return False


def _inpaint_prompt(instruction: str) -> str:
    if not instruction:
        return "modify the masked region to match the surrounding scene naturally"
    if not _contains_cjk(instruction):
        return f"{instruction}. High quality, seamlessly blended with the surrounding scene."
    return "A new object placed naturally in the masked region, seamlessly blending with the surrounding scene lighting, color, and style."


def build_plan(payload: PlanRequest) -> PlanResponse:
    instruction = payload.instruction.strip()
    lowered = instruction.lower()
    selected_asset = get_asset(payload.selected_asset_id)
    warnings: list[str] = []

    is_remove = any(k in instruction or k in lowered for k in REMOVE_KEYWORDS)
    is_replace = any(k in instruction or k in lowered for k in REPLACE_KEYWORDS)
    is_outpaint = any(k in instruction or k in lowered for k in OUTPAINT_KEYWORDS)
    is_shape = bool(payload.selected_asset_id) or any(k in instruction for k in SHAPE_GUIDED_KEYWORDS)

    if is_remove:
        task = "object-removal"
    elif is_outpaint:
        task = "image-outpainting"
    elif is_shape:
        task = "shape-guided"
    else:
        task = payload.preferred_task or "text-guided"

    target_label = selected_asset.name if selected_asset else None
    recommended_asset_id = selected_asset.id if selected_asset else None

    if task == "object-removal":
        task_prompt = "Remove the masked object entirely. Fill the area with the surrounding background texture. No visible seams, ghosting, or artifacts."
        negative_prompt = "object remnants, ghost artifacts, blurry inpainting, mismatched texture, broken edges, extra object"
        reasoning = "Detected removal intent."
    elif task == "image-outpainting":
        task_prompt = "Extend the canvas outward naturally. Maintain consistent lighting, structure, and style with the original image. No visible seams."
        negative_prompt = "seam visible, mismatched style, distorted continuation, blurry extension, inconsistent lighting"
        reasoning = "Detected outpainting intent."
    elif task == "shape-guided":
        if not instruction and selected_asset:
            task_prompt = f"A clean scientific illustration of {selected_asset.prompt}, precise edges, flat vector-like style."
        elif selected_asset and selected_asset.name not in instruction:
            task_prompt = f"{_inpaint_prompt(instruction)} Keep the generated object close to {selected_asset.prompt}."
        else:
            task_prompt = _inpaint_prompt(instruction)
        negative_prompt = "deformed object, blurry label, noisy edge, duplicated object, broken outline"
        reasoning = "Detected shape or asset guidance."
    else:
        if is_replace:
            task_prompt = (
                "Replace the masked object with a new object that matches the description. "
                "The new object must fit naturally into the scene — matching the lighting, perspective, scale, and color tone of the surrounding image. "
                "Seamless transition, no visible seams or artifacts."
            )
            reasoning = "Detected replacement intent."
        elif not instruction and selected_asset:
            task_prompt = f"Add {selected_asset.prompt} to the marked region, clean scientific illustration style."
        else:
            task_prompt = _inpaint_prompt(instruction)
            reasoning = "Default text-guided generation with mask constraint."
        negative_prompt = "blurry text, broken outline, distorted geometry, duplicated object, mismatched style"

    if not instruction:
        warnings.append("No natural language instruction provided, system will rely on task type and mask for editing.")
    if payload.selected_asset_id and not selected_asset:
        warnings.append("Selected asset not found in catalog, degraded to pure text guidance.")

    return PlanResponse(
        task=task,
        task_prompt=task_prompt,
        negative_prompt=negative_prompt,
        target_label=target_label,
        recommended_asset_id=recommended_asset_id,
        mask_strategy="user-mask",
        reasoning=reasoning,
        warnings=warnings,
    )
