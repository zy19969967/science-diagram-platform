from __future__ import annotations

import unittest

from common.canvas_state import build_canvas_state_after_generate
from common.schemas import CanvasLayer, CanvasState
from pydantic import ValidationError


class CanvasStateTest(unittest.TestCase):
    def test_build_canvas_state_after_generate_updates_base_and_history(self) -> None:
        state = CanvasState(
            canvas_id="canvas_1",
            width=1024,
            height=768,
            source="init-candidate",
            layers=[
                CanvasLayer(
                    id="base",
                    type="base-image",
                    name="Base",
                    data={"source": "init", "embedded_source_image": True},
                ),
                CanvasLayer(
                    id="mask",
                    type="mask",
                    name="Mask",
                    data={"pixel_count": 100, "embedded_mask_image": True, "mask_image": None},
                ),
            ],
            history=["init_1"],
            metadata={"selected_init_candidate_id": "init_1"},
        )

        updated = build_canvas_state_after_generate(
            state,
            run_id="run_123",
            artifacts={
                "result": "http://example/artifacts/run_123/result.png",
                "mask": "http://example/artifacts/run_123/mask.png",
            },
        )

        self.assertEqual(updated.source, "generated")
        self.assertEqual(updated.history, ["init_1", "run_123"])
        self.assertEqual(updated.metadata["latest_run_id"], "run_123")
        self.assertEqual(updated.metadata["latest_result_url"], "http://example/artifacts/run_123/result.png")
        self.assertEqual(updated.layers[0].data["image_url"], "http://example/artifacts/run_123/result.png")
        self.assertFalse(updated.layers[0].data["embedded_source_image"])
        self.assertEqual(updated.layers[1].data["mask_url"], "http://example/artifacts/run_123/mask.png")
        self.assertFalse(updated.layers[1].data["embedded_mask_image"])
        self.assertNotIn("mask_image", updated.layers[1].data)

    def test_canvas_state_rejects_embedded_data_urls(self) -> None:
        with self.assertRaises(ValidationError):
            CanvasState(
                canvas_id="canvas_1",
                width=1024,
                height=768,
                layers=[
                    CanvasLayer(
                        id="mask",
                        type="mask",
                        name="Mask",
                        data={"mask_image": "data:image/png;base64,abc"},
                    )
                ],
            )

    def test_canvas_state_rejects_too_many_layers(self) -> None:
        with self.assertRaises(ValidationError):
            CanvasState(
                canvas_id="canvas_1",
                width=1024,
                height=768,
                layers=[
                    CanvasLayer(id=f"text_{index}", type="text", name=f"Label {index}")
                    for index in range(65)
                ],
            )

    def test_canvas_state_accepts_region_prompt_layer(self) -> None:
        state = CanvasState(
            canvas_id="canvas_1",
            width=1024,
            height=768,
            layers=[
                CanvasLayer(
                    id="region-prompts",
                    type="region-prompt",
                    name="SAM point prompts",
                    data={
                        "point_prompts": [
                            {"id": "point-1", "x": 0.5, "y": 0.5, "label": "positive"},
                            {"id": "point-2", "x": 0.6, "y": 0.5, "label": "negative"},
                        ]
                    },
                )
            ],
            metadata={"point_prompt_count": 2},
        )

        self.assertEqual(state.layers[0].type, "region-prompt")
        self.assertEqual(state.metadata["point_prompt_count"], 2)


if __name__ == "__main__":
    unittest.main()
