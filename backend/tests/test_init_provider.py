from __future__ import annotations

import unittest

from common.schemas import InitGenerateRequest, ScenePlanRequest
from common.init_logic import build_scene_plan
from gateway.init_provider import InitProviderError, generate_initial_candidates


async def fake_remote_success(url: str, payload: dict) -> dict:
    scene_plan = payload["scene_plan"]
    return {
        "provider": "flux-remote",
        "scene_plan": scene_plan,
        "candidates": [
            {
                "id": "remote-low",
                "image": "data:image/png;base64,remote-low",
                "seed": 900,
                "provider": "flux-remote",
                "score": 0.95,
                "width": scene_plan["width"],
                "height": scene_plan["height"],
                "metadata": {"labels": [scene_plan["labels"][0]], "diagram_type": "other"},
            },
            {
                "id": "remote-best",
                "image": "data:image/png;base64,remote-best",
                "seed": 901,
                "provider": "flux-remote",
                "score": 0.84,
                "width": scene_plan["width"],
                "height": scene_plan["height"],
                "metadata": {"labels": scene_plan["labels"], "diagram_type": scene_plan["diagram_type"]},
            },
        ],
    }


async def fake_remote_failure(url: str, payload: dict) -> dict:
    raise RuntimeError("remote unavailable")


class InitProviderTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.plan = build_scene_plan(
            ScenePlanRequest(
                instruction="画一个酶促反应示意图，包含底物、酶、产物",
                candidate_count=2,
                seed=900,
            )
        )

    async def test_auto_uses_remote_flux_when_url_is_configured(self) -> None:
        response = await generate_initial_candidates(
            InitGenerateRequest(scene_plan=self.plan, seed=900, provider="auto"),
            flux_init_url="http://flux.example",
            post_json_func=fake_remote_success,
        )

        self.assertEqual(response.provider, "flux-remote")
        self.assertEqual(response.used_provider, "flux-remote")
        self.assertFalse(response.fallback_used)
        self.assertEqual(response.candidates[0].id, "remote-best")
        self.assertEqual(response.candidates[0].metadata["rank"], 1)

    async def test_auto_falls_back_when_flux_url_is_missing(self) -> None:
        response = await generate_initial_candidates(
            InitGenerateRequest(scene_plan=self.plan, seed=900, provider="auto"),
            flux_init_url="",
            post_json_func=fake_remote_success,
        )

        self.assertEqual(response.provider, "deterministic-fallback")
        self.assertEqual(response.requested_provider, "auto")
        self.assertEqual(response.used_provider, "deterministic-fallback")
        self.assertTrue(response.fallback_used)
        self.assertTrue(any("FLUX_INIT_URL" in warning for warning in response.warnings))

    async def test_explicit_flux_remote_fails_when_remote_unavailable(self) -> None:
        with self.assertRaises(InitProviderError):
            await generate_initial_candidates(
                InitGenerateRequest(scene_plan=self.plan, seed=900, provider="flux-remote"),
                flux_init_url="http://flux.example",
                post_json_func=fake_remote_failure,
            )


if __name__ == "__main__":
    unittest.main()
