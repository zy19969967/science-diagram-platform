from __future__ import annotations

import unittest

from common.init_logic import build_init_candidates, build_scene_plan, score_and_rank_init_candidates
from common.schemas import InitCandidate, InitGenerateRequest, InitGenerateResponse, ScenePlanRequest


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

    def test_score_and_rank_init_candidates_prefers_label_coverage_and_model_score(self) -> None:
        plan = build_scene_plan(
            ScenePlanRequest(
                instruction="画一个酶促反应示意图，包含底物、酶、产物",
                candidate_count=3,
                seed=77,
            )
        )
        response = InitGenerateResponse(
            provider="flux-remote",
            scene_plan=plan,
            candidates=[
                InitCandidate(
                    id="weak",
                    image="data:image/png;base64,weak",
                    seed=77,
                    provider="flux-remote",
                    score=0.95,
                    width=plan.width,
                    height=plan.height,
                    metadata={"labels": ["底物"], "diagram_type": "other"},
                ),
                InitCandidate(
                    id="strong",
                    image="data:image/png;base64,strong",
                    seed=78,
                    provider="flux-remote",
                    score=0.82,
                    width=plan.width,
                    height=plan.height,
                    metadata={"labels": ["底物", "酶", "产物"], "diagram_type": plan.diagram_type},
                ),
            ],
        )

        ranked = score_and_rank_init_candidates(response)

        self.assertEqual(ranked.candidates[0].id, "strong")
        self.assertEqual(ranked.candidates[0].metadata["rank"], 1)
        self.assertGreater(ranked.candidates[0].metadata["label_coverage_score"], 0.99)
        self.assertEqual(ranked.candidates[1].metadata["rank"], 2)

    def test_score_metadata_accepts_local_flux_provider(self) -> None:
        plan = build_scene_plan(
            ScenePlanRequest(
                instruction="画一个细胞结构示意图",
                candidate_count=1,
                seed=88,
            )
        )
        response = InitGenerateResponse(
            provider="flux-local",
            scene_plan=plan,
            candidates=[
                InitCandidate(
                    id="local",
                    image="data:image/png;base64,local",
                    seed=88,
                    provider="flux-local",
                    score=0.8,
                    width=plan.width,
                    height=plan.height,
                    metadata={"labels": plan.labels, "diagram_type": plan.diagram_type},
                ),
            ],
        )

        ranked = score_and_rank_init_candidates(response)

        self.assertEqual(ranked.candidates[0].metadata["provider_source"], "flux-local")
        self.assertGreater(ranked.candidates[0].score, 0.0)


if __name__ == "__main__":
    unittest.main()
