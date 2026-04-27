from __future__ import annotations

import unittest

from common.schemas import SegmentPoint, SegmentRequest
from common.segment_logic import build_segment
from common.utils.images import decode_data_url_to_image
from segmenter.runtime import SegmenterRuntime


class SegmentPointPromptTest(unittest.TestCase):
    def test_point_prompts_create_fallback_mask(self) -> None:
        response = build_segment(
            SegmentRequest(
                width=100,
                height=80,
                point_prompts=[
                    SegmentPoint(x=0.5, y=0.5, label="positive"),
                    SegmentPoint(x=0.2, y=0.2, label="negative"),
                ],
            )
        )

        mask = decode_data_url_to_image(response.mask_image, mode="L")

        self.assertGreater(response.coverage_ratio, 0)
        self.assertIsNotNone(response.bounding_box)
        self.assertGreater(mask.getpixel((50, 40)), 0)
        self.assertEqual(mask.getpixel((20, 16)), 0)

    def test_segment_request_without_region_signal_still_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "point prompts"):
            build_segment(SegmentRequest(width=100, height=80))

    def test_negative_points_carve_positive_fallback_mask_regardless_of_order(self) -> None:
        response = build_segment(
            SegmentRequest(
                width=100,
                height=80,
                point_prompts=[
                    SegmentPoint(x=0.5, y=0.5, label="negative"),
                    SegmentPoint(x=0.5, y=0.5, label="positive"),
                ],
            )
        )

        mask = decode_data_url_to_image(response.mask_image, mode="L")

        self.assertEqual(mask.getpixel((50, 40)), 0)

    def test_runtime_converts_normalized_points_to_sam_inputs(self) -> None:
        runtime = SegmenterRuntime()
        payload = SegmentRequest(
            width=100,
            height=80,
            point_prompts=[
                SegmentPoint(x=0.5, y=0.25, label="positive"),
                SegmentPoint(x=0.1, y=0.75, label="negative"),
            ],
        )

        point_inputs = runtime._build_prompt_points(payload, (100, 80))

        self.assertEqual(point_inputs, ([[[50, 20], [10, 60]]], [[1, 0]]))


if __name__ == "__main__":
    unittest.main()
