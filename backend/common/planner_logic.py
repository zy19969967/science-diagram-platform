from __future__ import annotations

from .assets import get_asset
from .schemas import PlanRequest, PlanResponse

REMOVE_KEYWORDS = (
    "删除",
    "移除",
    "去掉",
    "erase",
    "remove",
    "delete",
    "清除",
)
OUTPAINT_KEYWORDS = (
    "扩图",
    "扩展",
    "补全画布",
    "outpaint",
    "extend",
    "expand",
    "补边",
)
SHAPE_GUIDED_KEYWORDS = (
    "轮廓",
    "形状",
    "mask",
    "蒙版",
    "沿着选区",
    "贴合",
)


def build_plan(payload: PlanRequest) -> PlanResponse:
    instruction = payload.instruction.strip()
    lowered = instruction.lower()
    selected_asset = get_asset(payload.selected_asset_id)
    warnings: list[str] = []

    if any(keyword in instruction for keyword in REMOVE_KEYWORDS) or any(
        keyword in lowered for keyword in REMOVE_KEYWORDS
    ):
        task = "object-removal"
    elif any(keyword in instruction for keyword in OUTPAINT_KEYWORDS) or any(
        keyword in lowered for keyword in OUTPAINT_KEYWORDS
    ):
        task = "image-outpainting"
    elif payload.selected_asset_id or any(keyword in instruction for keyword in SHAPE_GUIDED_KEYWORDS):
        task = "shape-guided"
    else:
        task = payload.preferred_task or "text-guided"

    target_label = selected_asset.name if selected_asset else None
    recommended_asset_id = selected_asset.id if selected_asset else None

    if task == "object-removal":
        task_prompt = instruction or "remove the marked object and recover a clean scientific illustration background"
        negative_prompt = "object remnants, ghost artifacts, blurry inpainting, mismatched texture, broken edges, extra object"
        reasoning = "Detected removal intent, planned as object removal with protection for labels and arrows."
    elif task == "image-outpainting":
        task_prompt = instruction or "extend the scientific illustration while preserving labels, arrows and layout"
        negative_prompt = "seam visible, mismatched style, distorted continuation, blurry extension, inconsistent lighting, extra object"
        reasoning = "Detected outpainting intent, planned as background extension."
    elif task == "shape-guided":
        if not instruction and selected_asset:
            task_prompt = f"a clean scientific illustration of {selected_asset.prompt}"
        elif selected_asset and selected_asset.name not in instruction:
            task_prompt = f"{instruction}; keep the generated object close to {selected_asset.prompt}".strip("; ")
        else:
            task_prompt = instruction or "a clean scientific illustration element"
        negative_prompt = "deformed object, blurry label, noisy edge, duplicated object, broken outline"
        reasoning = "Detected shape or asset guidance, planned as shape-constrained insertion."
    else:
        if not instruction and selected_asset:
            task_prompt = f"add {selected_asset.prompt} to the marked region in a clean scientific illustration style"
        else:
            task_prompt = instruction or "add a scientific illustration element to the marked region"
        negative_prompt = "blurry text, broken outline, distorted geometry, duplicated object, mismatched style"
        reasoning = "Default text-guided local generation with mask constraint."

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
