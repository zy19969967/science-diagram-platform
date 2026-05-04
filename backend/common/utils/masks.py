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
    from scipy.ndimage import maximum_filter
    arr = np.asarray(mask.convert("L"), dtype=np.uint8)
    dilated = maximum_filter(arr, size=2 * radius + 1)
    return Image.fromarray(dilated, mode="L")


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


def match_histogram(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    result = np.empty_like(source)
    for channel in range(3):
        src_ch = source[:, :, channel].ravel()
        ref_ch = reference[:, :, channel].ravel()
        src_sorted = np.sort(src_ch)
        ref_sorted = np.sort(ref_ch)
        src_indices = np.searchsorted(src_sorted, src_ch)
        src_indices = np.clip(src_indices, 0, len(ref_sorted) - 1)
        matched = ref_sorted[src_indices]
        result[:, :, channel] = matched.reshape(source.shape[:2])
    return result


def build_gaussian_pyramid(image: np.ndarray, levels: int) -> list[np.ndarray]:
    pyramid = [image]
    for _ in range(levels - 1):
        h, w = pyramid[-1].shape[:2]
        down = Image.fromarray(pyramid[-1].astype(np.uint8)).resize((w // 2, h // 2), Image.LANCZOS)
        pyramid.append(np.asarray(down, dtype=np.float32))
    return pyramid


def build_laplacian_pyramid(gaussian: list[np.ndarray]) -> list[np.ndarray]:
    laplacian = []
    for i in range(len(gaussian) - 1):
        h, w = gaussian[i].shape[:2]
        up = np.asarray(Image.fromarray(gaussian[i + 1].astype(np.uint8)).resize((w, h), Image.LANCZOS), dtype=np.float32)
        laplacian.append(gaussian[i] - up)
    laplacian.append(gaussian[-1])
    return laplacian


def reconstruct_from_laplacian(laplacian: list[np.ndarray]) -> np.ndarray:
    result = laplacian[-1]
    for i in range(len(laplacian) - 2, -1, -1):
        h, w = laplacian[i].shape[:2]
        up = np.asarray(Image.fromarray(result.astype(np.uint8)).resize((w, h), Image.LANCZOS), dtype=np.float32)
        result = laplacian[i] + up
    return result


def multiband_blend(original: Image.Image, generated: Image.Image, mask: Image.Image, levels: int = 5) -> Image.Image:
    gen = generated.convert("RGB").resize(original.size)
    orig_arr = np.asarray(original.convert("RGB"), dtype=np.float32)
    gen_arr = np.asarray(gen, dtype=np.float32)
    mask_arr = np.asarray(mask.convert("L").resize(original.size), dtype=np.float32) / 255.0
    mask_arr = mask_arr[:, :, np.newaxis]

    orig_pyr = build_gaussian_pyramid(orig_arr, levels)
    gen_pyr = build_gaussian_pyramid(gen_arr, levels)
    mask_pyr = [Image.fromarray((m[:, :, 0] * 255).astype(np.uint8)).resize(
        (orig_pyr[i].shape[1], orig_pyr[i].shape[0]), Image.LANCZOS) for i, m in enumerate(
        [mask_arr] + [np.ones((h // 2, w // 2, 1), dtype=np.float32) for h, w in
         [(orig_pyr[0].shape[0], orig_pyr[0].shape[1])] * (levels - 1)])]

    mask_pyr_arrs = [np.asarray(m, dtype=np.float32) / 255.0 for m in mask_pyr]
    mask_pyr_arrs = [m[:, :, np.newaxis] if m.ndim == 2 else m for m in mask_pyr_arrs]

    orig_lap = build_laplacian_pyramid(orig_pyr)
    gen_lap = build_laplacian_pyramid(gen_pyr)

    blended_lap = []
    for i in range(levels):
        blended_lap.append(gen_lap[i] * mask_pyr_arrs[i] + orig_lap[i] * (1.0 - mask_pyr_arrs[i]))

    result = reconstruct_from_laplacian(blended_lap)
    return Image.fromarray(result.clip(0, 255).astype(np.uint8), mode="RGB")


def color_match_generated(original: Image.Image, generated: Image.Image, mask: Image.Image) -> Image.Image:
    orig_arr = np.asarray(original.convert("RGB"), dtype=np.float32)
    gen_arr = np.asarray(generated.convert("RGB").resize(original.size), dtype=np.float32)
    mask_arr = np.asarray(mask.convert("L").resize(original.size), dtype=np.float32) / 255.0
    mask_binary = mask_arr > 0.5

    if not mask_binary.any():
        return generated

    kernel_size = max(3, min(original.width, original.height) // 20)
    dilated = np.zeros_like(mask_binary)
    for _ in range(kernel_size // 2):
        dilated = np.maximum(dilated, np.roll(mask_binary, 1, axis=0))
        dilated = np.maximum(dilated, np.roll(mask_binary, -1, axis=0))
        dilated = np.maximum(dilated, np.roll(mask_binary, 1, axis=1))
        dilated = np.maximum(dilated, np.roll(mask_binary, -1, axis=1))
        mask_binary = dilated

    border = dilated & (~mask_binary)
    if not border.any():
        return generated

    border_pixels = orig_arr[border]
    gen_pixels = gen_arr[mask_binary]
    if len(border_pixels) < 10 or len(gen_pixels) < 10:
        return generated

    matched_gen = match_histogram(gen_pixels, border_pixels)
    result = gen_arr.copy()
    flat_mask = mask_binary.ravel()
    result_flat = result.reshape(-1, 3)
    gen_indices = np.where(flat_mask)[0]
    result_flat[gen_indices] = matched_gen
    result = result_flat.reshape(gen_arr.shape)

    return Image.fromarray(result.clip(0, 255).astype(np.uint8), mode="RGB")


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
