from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ASSETS_DIR", str(Path(__file__).resolve().parents[1] / "assets"))
os.environ.setdefault("RUNS_DIR", "/tmp/science-diagram-test-runs")
os.environ.setdefault("PROJECTS_DIR", "/tmp/science-diagram-test-projects")
os.environ.setdefault("JOBS_DIR", "/tmp/science-diagram-test-jobs")

from fastapi.testclient import TestClient
from common.schemas import (
    CanvasLayer,
    CanvasState,
    EvaluationResult,
    MaskQualityReport,
    ProjectCreateRequest,
    ProjectVersionCreateRequest,
    PromptTrace,
    RunQualityReport,
)
from pydantic import ValidationError
from gateway import main as gateway_main
from gateway.projects import ProjectStore


def sample_canvas_state(history: list[str]) -> CanvasState:
    return CanvasState(
        canvas_id="canvas-init_1",
        width=1024,
        height=768,
        source="generated" if any(item.startswith("run_") for item in history) else "init-candidate",
        layers=[
            CanvasLayer(
                id="base-image",
                type="base-image",
                name="Canvas source",
                data={
                    "source": "generated",
                    "image_url": "http://example/artifacts/run_123/result.png",
                    "embedded_source_image": False,
                },
            )
        ],
        history=history,
        metadata={"selected_init_candidate_id": "init_1", "latest_run_id": history[-1]},
    )


def sample_quality_report(run_id: str) -> RunQualityReport:
    return RunQualityReport(
        run_id=run_id,
        mask=MaskQualityReport(
            coverage_ratio=0.25,
            area_pixels=256,
            bounding_box=[10, 12, 200, 180],
            artifact_url=f"http://example/artifacts/{run_id}/mask.png",
        ),
        prompt=PromptTrace(
            instruction="Add an enzyme arrow",
            task="shape-guided",
            task_prompt="Add a clean enzyme arrow",
            seed=2026,
            planner_source="provided-plan",
        ),
        evaluation=EvaluationResult(
            changed_ratio=0.14,
            outside_mask_change_ratio=0.02,
            inside_mask_change_ratio=0.72,
            mask_coverage_ratio=0.25,
            edit_localization_score=0.9,
            preservation_score=0.98,
            note="localized edit",
        ),
        artifacts={"result": f"http://example/artifacts/{run_id}/result.png"},
    )


class ProjectStoreTest(unittest.TestCase):
    def test_project_store_persists_parent_linked_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir))
            project = store.create_project(
                ProjectCreateRequest(
                    name="Enzyme pathway",
                    source_image_metadata={
                        "width": 1024,
                        "height": 768,
                        "source": "init-candidate",
                    },
                    init_plan={"provider": "deterministic-fallback", "diagram_type": "enzyme_reaction_diagram"},
                    selected_candidate_id="init_1",
                )
            )

            first = store.append_version(
                project.project_id,
                ProjectVersionCreateRequest(
                    kind="init-candidate",
                    label="Initial candidate",
                    canvas_state=sample_canvas_state(["init_1"]),
                    artifacts={"source": "http://example/projects/init_1/source.png"},
                    metadata={"selected_init_candidate_id": "init_1"},
                ),
            )
            second = store.append_version(
                project.project_id,
                ProjectVersionCreateRequest(
                    kind="generate-result",
                    parent_version_id=first.version_id,
                    run_id="run_123",
                    label="Localized enzyme arrow",
                    canvas_state=sample_canvas_state(["init_1", "run_123"]),
                    quality_report=sample_quality_report("run_123"),
                    artifacts={"result": "http://example/artifacts/run_123/result.png"},
                    result_image="http://example/artifacts/run_123/result.png",
                ),
            )

            reloaded = ProjectStore(Path(temp_dir)).get_project(project.project_id)

            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.project_id, project.project_id)
            self.assertEqual(reloaded.latest_version_id, second.version_id)
            self.assertEqual([version.version_id for version in reloaded.versions], [first.version_id, second.version_id])
            self.assertIsNone(reloaded.versions[0].parent_version_id)
            self.assertEqual(reloaded.versions[1].parent_version_id, first.version_id)
            self.assertEqual(reloaded.versions[1].run_id, "run_123")
            self.assertEqual(reloaded.versions[1].quality_report.run_id, "run_123")

    def test_project_store_rejects_missing_parent_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir))
            project = store.create_project(ProjectCreateRequest(name="Untitled"))

            with self.assertRaises(ValueError):
                store.append_version(
                    project.project_id,
                    ProjectVersionCreateRequest(
                        kind="generate-result",
                        parent_version_id="missing-version",
                        run_id="run_123",
                        result_image="http://example/artifacts/run_123/result.png",
                        canvas_state=sample_canvas_state(["init_1", "run_123"]),
                    ),
                )

    def test_generate_result_version_requires_run_id_and_result_artifact(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectVersionCreateRequest(
                kind="generate-result",
                canvas_state=sample_canvas_state(["init_1", "run_123"]),
            )


class ProjectApiTest(unittest.TestCase):
    def test_project_routes_create_append_list_and_reject_invalid_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway_main.project_store = ProjectStore(Path(temp_dir))
            client = TestClient(gateway_main.app)

            created_response = client.post(
                "/api/projects",
                json={
                    "name": "API project",
                    "source_image_metadata": {"source": "init-candidate", "width": 1024, "height": 768},
                    "selected_candidate_id": "init_1",
                },
            )
            self.assertEqual(created_response.status_code, 200)
            project_id = created_response.json()["project_id"]

            invalid_parent_response = client.post(
                f"/api/projects/{project_id}/versions",
                json={
                    "kind": "generate-result",
                    "parent_version_id": "missing-version",
                    "run_id": "run_123",
                    "result_image": "http://example/artifacts/run_123/result.png",
                    "canvas_state": sample_canvas_state(["init_1", "run_123"]).model_dump(),
                },
            )
            self.assertEqual(invalid_parent_response.status_code, 400)

            append_response = client.post(
                f"/api/projects/{project_id}/versions",
                json={
                    "kind": "generate-result",
                    "run_id": "run_123",
                    "result_image": "http://example/artifacts/run_123/result.png",
                    "artifacts": {"result": "http://example/artifacts/run_123/result.png"},
                    "canvas_state": sample_canvas_state(["init_1", "run_123"]).model_dump(),
                },
            )
            self.assertEqual(append_response.status_code, 200)
            updated = append_response.json()
            self.assertEqual(updated["latest_version_id"], updated["versions"][0]["version_id"])

            list_response = client.get("/api/projects")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(list_response.json()[0]["project_id"], project_id)


if __name__ == "__main__":
    unittest.main()
