from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..schemas import AssetPlacement, EvaluationResult, SegmentPoint


def normalize_mask(mask: Image.Image, size: tuple[int, int]) -> Image.Image:
    normalized = mask.convert("L").resize(size)
    binary = normalized.point(lambda pixel: 255 if pixel > 32 else 0, mode="L")
    return binary


def dilate_mask(mask: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return mask.copy()
    arr = np.asarray(mask.convert("L"))
    h, w = arr.shape
    dilated = np.zeros_like(arr)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                shifted = np.roll(np.roll(arr, dx, axis=1), dy, axis=0)
                if dx > 0:
                    shifted[:, :dx] = 0
                elif dx < 0:
                    shifted[:, dx:] = 0
                if dy > 0:
                    shifted[:dy, :] = 0
                elif dy < 0:
                    shifted[dy:, :] = 0
                dilated = np.maximum(dilated, shifted)
    return Image.fromarray(dilated.astype(np.uint8), mode="L")


def blur_mask(mask: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return mask.copy()
    return mask.filter(ImageFilter.GaussianBlur(radius=radius))


def soften_mask_edges(mask: Image.Image, *, dilation: int = 16, blur: int = 12) -> Image.Image:
    dilated = dilate_mask(mask, dilation)
    return blur_mask(dilated, blur)


def blend_with_mask(original: Image.Image, generated: Image.Image, mask: Image.Image) -> Image.Image:
    mask_arr = np.asarray(mask.convert("L").resize(original.size), dtype=np.float32) / 255.0
    mask_arr = mask_arr[:, :, np.newaxis]
    orig_arr = np.asarray(original.convert("RGB"), dtype=np.float32)
    gen_arr = np.asarray(generated.convert("RGB").resize(original.size), dtype=np.float32)
    blended = gen_arr * mask_arr + orig_arr * (1.0 - mask_arr)
    return Image.fromarray(blended.clip(0, 255).astype(np.uint8), mode="RGB")


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


def mask_from_points(width: int, height: int, points: list[SegmentPoint]) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    radius = max(6, int(min(width, height) * 0.04))
    ordered_points = [
        *[point for point in points if point.label == "positive"],
        *[point for point in points if point.label == "negative"],
    ]
    for point in ordered_points:
        x = int(point.x * width)
        y = int(point.y * height)
        box = (x - radius, y - radius, x + radius, y + radius)
        draw.ellipse(box, fill=255 if point.label == "positive" else 0)
    return mask


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
    inside_change_ratio = float(changed[mask_arr].mean()) if mask_arr.any() else 0.0
    outside_mask = ~mask_arr
    outside_change_ratio = float(changed[outside_mask].mean()) if outside_mask.any() else 0.0
    changed_pixels = int(changed.sum())
    localized_changed_pixels = int((changed & mask_arr).sum())
    edit_localization_score = (
        localized_changed_pixels / changed_pixels
        if changed_pixels > 0
        else 0.0
    )
    mask_coverage_ratio = float(mask_arr.mean())
    preservation_score = max(0.0, 1.0 - outside_change_ratio)

    if outside_change_ratio < 0.02:
        note = "Non-edited area well preserved, suitable as a controlled local editing example."
    elif outside_change_ratio < 0.08:
        note = "Minor edit spillover detected, consider refining mask precision or prompt."
    else:
        note = "Significant edit spillover detected, try adjusting the mask or lowering guidance scale."

    return EvaluationResult(
        changed_ratio=round(changed_ratio, 4),
        outside_mask_change_ratio=round(outside_change_ratio, 4),
        note=note,
        inside_mask_change_ratio=round(inside_change_ratio, 4),
        mask_coverage_ratio=round(mask_coverage_ratio, 4),
        edit_localization_score=round(edit_localization_score, 4),
        preservation_score=round(preservation_score, 4),
    )
