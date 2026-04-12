from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..schemas import AssetPlacement, EvaluationResult


def normalize_mask(mask: Image.Image, size: tuple[int, int]) -> Image.Image:
    normalized = mask.convert("L").resize(size)
    binary = normalized.point(lambda pixel: 255 if pixel > 32 else 0, mode="L")
    return binary


def mask_from_box(width: int, height: int, box: list[int]) -> Image.Image:
    x1, y1, x2, y2 = box
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((x1, y1, x2, y2), fill=255)
    return mask


def placement_to_box(width: int, height: int, placement: AssetPlacement) -> list[int]:
    center_x = placement.x * width
    center_y = placement.y * height
    half_w = placement.width * width / 2.0
    half_h = placement.height * height / 2.0
    x1 = max(0, int(center_x - half_w))
    y1 = max(0, int(center_y - half_h))
    x2 = min(width, int(center_x + half_w))
    y2 = min(height, int(center_y + half_h))
    return [x1, y1, x2, y2]


def mask_from_placement(width: int, height: int, placement: AssetPlacement) -> Image.Image:
    return mask_from_box(width, height, placement_to_box(width, height, placement))


def coverage_ratio(mask: Image.Image) -> float:
    arr = np.asarray(mask.convert("L")) > 0
    return float(arr.mean())


def compute_mask_bbox(mask: Image.Image) -> list[int] | None:
    arr = np.asarray(mask.convert("L")) > 0
    if not arr.any():
        return None
    ys, xs = np.where(arr)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def evaluate_edit(source: Image.Image, result: Image.Image, mask: Image.Image) -> EvaluationResult:
    source_arr = np.asarray(source.convert("RGB").resize(mask.size)).astype(np.int16)
    result_arr = np.asarray(result.convert("RGB").resize(mask.size)).astype(np.int16)
    mask_arr = np.asarray(normalize_mask(mask, mask.size).convert("L")) > 0

    pixel_delta = np.abs(source_arr - result_arr).mean(axis=2)
    changed = pixel_delta > 12

    changed_ratio = float(changed.mean())
    outside_mask = ~mask_arr
    outside_change_ratio = float(changed[outside_mask].mean()) if outside_mask.any() else 0.0

    if outside_change_ratio < 0.02:
        note = "非编辑区域保持较好，可作为论文中的局部控制性示例。"
    elif outside_change_ratio < 0.08:
        note = "存在少量编辑外溢，建议在论文实验中进一步分析 mask 精度与提示词影响。"
    else:
        note = "编辑外溢较明显，建议重新调整 mask 或 guidance scale。"

    return EvaluationResult(
        changed_ratio=round(changed_ratio, 4),
        outside_mask_change_ratio=round(outside_change_ratio, 4),
        note=note,
    )
