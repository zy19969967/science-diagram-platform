from __future__ import annotations

from .schemas import SegmentRequest, SegmentResponse
from .utils.images import decode_data_url_to_image, encode_image_to_data_url
from .utils.masks import (
    compute_mask_bbox,
    coverage_ratio,
    mask_from_box,
    mask_from_placement,
    mask_from_points,
    normalize_mask,
)


def build_segment(payload: SegmentRequest) -> SegmentResponse:
    if payload.mask_image:
        raw_mask = decode_data_url_to_image(payload.mask_image, mode="L")
        mask = normalize_mask(raw_mask, size=(payload.width, payload.height))
    elif payload.asset_placement:
        mask = mask_from_placement(payload.width, payload.height, payload.asset_placement)
    elif payload.point_prompts:
        mask = mask_from_points(payload.width, payload.height, payload.point_prompts)
    elif payload.box:
        mask = mask_from_box(payload.width, payload.height, payload.box)
    else:
        raise ValueError("A user mask, asset placement, point prompts, or box hint is required.")

    return SegmentResponse(
        mask_image=encode_image_to_data_url(mask),
        coverage_ratio=coverage_ratio(mask),
        bounding_box=compute_mask_bbox(mask),
    )
