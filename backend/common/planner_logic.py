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
        negative_prompt = "extra object, duplicated object, blurry text, distorted arrows"
        reasoning = "检测到删除类指令，规划为对象移除流程，并优先保护科研图中的文字与箭头。"
    elif task == "image-outpainting":
        task_prompt = instruction or "extend the scientific illustration while preserving labels, arrows and layout"
        negative_prompt = "extra object, text corruption, cluttered background"
        reasoning = "检测到扩图或补边意图，规划为背景外扩任务。"
    elif task == "shape-guided":
        if not instruction and selected_asset:
            task_prompt = f"a clean scientific illustration of {selected_asset.prompt}"
        elif selected_asset and selected_asset.name not in instruction:
            task_prompt = f"{instruction}; keep the generated object close to {selected_asset.prompt}".strip("; ")
        else:
            task_prompt = instruction or "a clean scientific illustration element"
        negative_prompt = "deformed object, blurry label, noisy edge, duplicated object"
        reasoning = "检测到素材或轮廓引导信号，规划为形状约束插入流程。"
    else:
        if not instruction and selected_asset:
            task_prompt = f"add {selected_asset.prompt} to the marked region in a clean scientific illustration style"
        else:
            task_prompt = instruction or "add a scientific illustration element to the marked region"
        negative_prompt = "blurry text, broken outline, distorted geometry, duplicated object"
        reasoning = "默认按文本引导局部生成执行，并保留手工绘制的 mask 作为约束。"

    if not instruction:
        warnings.append("当前未输入自然语言指令，系统将主要依赖任务类型和选区进行编辑。")

    if payload.selected_asset_id and not selected_asset:
        warnings.append("所选素材未在素材库中找到，已退化为纯文本引导。")

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
