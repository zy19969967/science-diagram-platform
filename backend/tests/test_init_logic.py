from __future__ import annotations

import unittest

from common.init_logic import build_init_candidates, build_scene_plan
from common.schemas import InitGenerateRequest, ScenePlanRequest


class InitLogicTest(unittest.TestCase):
    def test_scene_plan_extracts_labels_from_chinese_instruction(self) -> None:
        plan = build_scene_plan(
            ScenePlanRequest(
                instruction="画一个酶促反应示意图，包含底物、酶、产物和箭头",
                style="flat-vector",
                candidate_count=2,
            )
        )

        self.assertEqual(plan.mode, "create_from_text")
        self.assertEqual(plan.candidate_count, 2)
        self.assertIn("底物", plan.labels)
        self.assertIn("酶", plan.labels)
        self.assertIn("产物", plan.labels)
        self.assertIn("arrow", plan.positive_prompt.lower())

    def test_init_candidates_are_deterministic_and_image_data_urls(self) -> None:
        plan = build_scene_plan(
            ScenePlanRequest(
                instruction="画一个酶促反应示意图，包含底物、酶、产物和箭头",
                candidate_count=2,
                seed=123,
            )
        )

        first = build_init_candidates(InitGenerateRequest(scene_plan=plan, seed=123))
        second = build_init_candidates(InitGenerateRequest(scene_plan=plan, seed=123))

        self.assertEqual(first.provider, "deterministic-fallback")
        self.assertEqual(len(first.candidates), 2)
        self.assertTrue(first.candidates[0].image.startswith("data:image/png;base64,"))
        self.assertEqual(first.candidates[0].image, second.candidates[0].image)
        self.assertEqual(first.candidates[0].seed, 123)


if __name__ == "__main__":
    unittest.main()
