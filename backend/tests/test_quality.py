from __future__ import annotations

import unittest

from PIL import Image

from common.quality import build_quality_report
from common.schemas import GenerateRequest, PlanResponse
from common.utils.masks import evaluate_edit


class QualityReportTest(unittest.TestCase):
    def test_evaluate_edit_reports_inside_and_localization_metrics(self) -> None:
        source = Image.new("RGB", (4, 4), "black")
        result = Image.new("RGB", (4, 4), "black")
        mask = Image.new("L", (4, 4), 0)
        for x in range(2):
            for y in range(2):
                result.putpixel((x, y), (255, 255, 255))
                mask.putpixel((x, y), 255)

        evaluation = evaluate_edit(source, result, mask)

        self.assertEqual(evaluation.mask_coverage_ratio, 0.25)
        self.assertEqual(evaluation.inside_mask_change_ratio, 1.0)
        self.assertEqual(evaluation.outside_mask_change_ratio, 0.0)
        self.assertEqual(evaluation.edit_localization_score, 1.0)
        self.assertEqual(evaluation.preservation_score, 1.0)

    def test_quality_report_records_mask_and_prompt_trace(self) -> None:
        mask = Image.new("L", (4, 4), 0)
        for x in range(2):
            for y in range(2):
                mask.putpixel((x, y), 255)

        payload = GenerateRequest(
            source_image="data:image/png;base64,source",
            instruction="add enzyme arrow",
            task="shape-guided",
            selected_asset_id="arrow",
            steps=20,
            guidance_scale=6.5,
            fitting_degree=0.75,
            seed=42,
        )
        plan = PlanResponse(
            task="shape-guided",
            task_prompt="draw a clean arrow",
            negative_prompt="blurry",
            reasoning="test",
        )
        evaluation = evaluate_edit(
            Image.new("RGB", (4, 4), "black"),
            Image.new("RGB", (4, 4), "black"),
            mask,
        )

        report = build_quality_report(
            run_id="run_1",
            payload=payload,
            plan=plan,
            mask=mask,
            evaluation=evaluation,
            artifacts={"mask": "http://example/mask.png"},
            planner_source="provided-plan",
        )

        self.assertEqual(report.run_id, "run_1")
        self.assertEqual(report.mask.coverage_ratio, 0.25)
        self.assertEqual(report.mask.bounding_box, [0, 0, 1, 1])
        self.assertEqual(report.prompt.task, "shape-guided")
        self.assertEqual(report.prompt.seed, 42)
        self.assertEqual(report.prompt.parameters["steps"], 20)
        self.assertEqual(report.prompt.planner_source, "provided-plan")


if __name__ == "__main__":
    unittest.main()
