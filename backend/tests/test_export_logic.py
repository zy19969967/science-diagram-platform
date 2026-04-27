from __future__ import annotations

import unittest

from common.export_logic import build_svg_export, build_text_validation_report
from common.schemas import CanvasLayer, CanvasState, SvgExportRequest, TextValidationRequest


def canvas_with_text_layers() -> CanvasState:
    return CanvasState(
        canvas_id="canvas_export_1",
        width=800,
        height=600,
        source="generated",
        layers=[
            CanvasLayer(
                id="base-image",
                type="base-image",
                name="Generated result",
                data={"image_url": "http://example.test/artifacts/run_1/result.png", "source": "generated"},
            ),
            CanvasLayer(
                id="text-1",
                type="text",
                name="Label 1",
                data={"text": "底物", "x": 0.2, "y": 0.3, "font_size": 24, "color": "#18324c"},
            ),
            CanvasLayer(
                id="text-2",
                type="text",
                name="Label 2",
                data={"text": "酶", "x": 0.5, "y": 0.5, "font_size": 28, "color": "#2b77ff"},
            ),
            CanvasLayer(
                id="text-hidden",
                type="text",
                name="Hidden label",
                visible=False,
                data={"text": "隐藏", "x": 0.8, "y": 0.8},
            ),
        ],
    )


class ExportLogicTest(unittest.TestCase):
    def test_text_validation_matches_vector_labels_without_ocr(self) -> None:
        report = build_text_validation_report(
            TextValidationRequest(
                canvas_state=canvas_with_text_layers(),
                expected_labels=["底物", "酶"],
            )
        )

        self.assertEqual(report.status, "warn")
        self.assertEqual(report.vector_labels, ["底物", "酶"])
        self.assertEqual(report.matched_labels, ["底物", "酶"])
        self.assertEqual(report.missing_labels, [])
        self.assertTrue(any("No OCR observations" in warning for warning in report.warnings))

    def test_text_validation_reports_missing_expected_labels(self) -> None:
        report = build_text_validation_report(
            TextValidationRequest(
                canvas_state=canvas_with_text_layers(),
                expected_labels=["底物", "酶", "产物"],
            )
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.missing_labels, ["产物"])

    def test_svg_export_preserves_visible_text_as_vector_text(self) -> None:
        export = build_svg_export(SvgExportRequest(canvas_state=canvas_with_text_layers()))

        self.assertEqual(export.mime_type, "image/svg+xml")
        self.assertIn("<svg", export.svg)
        self.assertIn('width="800"', export.svg)
        self.assertIn('height="600"', export.svg)
        self.assertIn("<text", export.svg)
        self.assertIn("底物", export.svg)
        self.assertIn("酶", export.svg)
        self.assertNotIn("隐藏", export.svg)
        self.assertEqual(export.text_report.vector_labels, ["底物", "酶"])

    def test_svg_export_warns_about_embedded_bitmap_only_base(self) -> None:
        state = canvas_with_text_layers().model_copy(
            deep=True,
            update={
                "layers": [
                    CanvasLayer(
                        id="base-image",
                        type="base-image",
                        name="Uploaded source",
                        data={"image_url": None, "embedded_source_image": True},
                    ),
                    *canvas_with_text_layers().layers[1:],
                ]
            },
        )

        export = build_svg_export(SvgExportRequest(canvas_state=state))

        self.assertIn("<rect", export.svg)
        self.assertTrue(any("embedded bitmap" in warning for warning in export.warnings))


if __name__ == "__main__":
    unittest.main()
