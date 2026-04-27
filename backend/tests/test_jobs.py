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
    EvaluationResult,
    GenerateResponse,
    PlanResponse,
)
from gateway import main as gateway_main
from gateway.jobs import JobStore


def sample_generate_response() -> GenerateResponse:
    return GenerateResponse(
        run_id="run_123",
        plan=PlanResponse(
            task="shape-guided",
            task_prompt="Add an enzyme arrow",
            reasoning="test fixture",
        ),
        result_image="data:image/png;base64,result",
        evaluation=EvaluationResult(
            changed_ratio=0.12,
            outside_mask_change_ratio=0.01,
            note="ok",
        ),
        artifacts={"result": "http://example/artifacts/run_123/result.png"},
    )


class JobStoreTest(unittest.TestCase):
    def test_create_and_update_job_snapshot(self) -> None:
        store = JobStore()

        created = store.create("Queued for generation")
        self.assertEqual(created.status, "CREATED")
        self.assertEqual(created.progress, 0.0)
        self.assertEqual(created.message, "Queued for generation")

        updated = store.update(
            created.job_id,
            status="EXECUTING",
            progress=0.65,
            message="PowerPaint is running",
        )
        self.assertEqual(updated.status, "EXECUTING")
        self.assertEqual(updated.progress, 0.65)
        self.assertEqual(updated.message, "PowerPaint is running")
        self.assertIsNotNone(store.get(created.job_id))

    def test_update_missing_job_raises_key_error(self) -> None:
        store = JobStore()

        with self.assertRaises(KeyError):
            store.update("missing", status="DONE")

    def test_file_backed_store_reloads_terminal_job_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JobStore(Path(temp_dir))

            created = store.create("Queued for generation", max_attempts=2)
            finished = store.update(
                created.job_id,
                status="DONE",
                progress=1.0,
                message="Generation complete",
                result=sample_generate_response(),
            )

            reloaded = JobStore(Path(temp_dir)).get(created.job_id)

            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.status, "DONE")
            self.assertEqual(reloaded.result.run_id, "run_123")
            self.assertEqual(reloaded.max_attempts, 2)
            self.assertEqual(reloaded.updated_at, finished.updated_at)

    def test_successful_retry_clears_previous_error(self) -> None:
        store = JobStore()

        created = store.create("Queued for generation", max_attempts=2)
        store.update(
            created.job_id,
            status="CREATED",
            progress=0.0,
            message="Retrying generation (2/2)",
            error="Planner timed out",
            attempt=2,
        )
        finished = store.update(
            created.job_id,
            status="DONE",
            progress=1.0,
            message="Generation complete",
            result=sample_generate_response(),
        )

        self.assertEqual(finished.status, "DONE")
        self.assertIsNone(finished.error)
        self.assertIsNone(finished.failure_stage)

    def test_file_backed_store_marks_active_jobs_failed_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JobStore(Path(temp_dir))

            created = store.create("Queued for generation")
            store.update(created.job_id, status="EXECUTING", progress=0.65, message="PowerPaint is running")

            recovered = JobStore(Path(temp_dir)).get(created.job_id)

            self.assertIsNotNone(recovered)
            self.assertEqual(recovered.status, "FAILED")
            self.assertEqual(recovered.progress, 1.0)
            self.assertEqual(recovered.failure_stage, "EXECUTING")
            self.assertIn("interrupted", recovered.error)

    def test_file_backed_store_skips_invalid_job_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            job_dir = Path(temp_dir)
            (job_dir / "broken.json").write_text("{not-valid-json", encoding="utf-8")
            with self.assertLogs("gateway.jobs", level="WARNING") as logs:
                store = JobStore(job_dir)

            created = store.create("Queued for generation")

            self.assertTrue(any("Skipping invalid job snapshot" in message for message in logs.output))
            self.assertEqual(store.get(created.job_id).status, "CREATED")

    def test_cancel_persists_cancelled_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JobStore(Path(temp_dir))

            created = store.create("Queued for generation")
            cancelled = store.cancel(created.job_id)
            reloaded = JobStore(Path(temp_dir)).get(created.job_id)

            self.assertEqual(cancelled.status, "CANCELLED")
            self.assertTrue(cancelled.cancel_requested)
            self.assertEqual(reloaded.status, "CANCELLED")
            self.assertTrue(reloaded.cancel_requested)

    def test_cancel_missing_job_raises_key_error(self) -> None:
        store = JobStore()

        with self.assertRaises(KeyError):
            store.cancel("missing")

    def test_cancel_terminal_job_is_noop(self) -> None:
        store = JobStore()

        created = store.create("Queued for generation")
        finished = store.update(created.job_id, status="DONE", progress=1.0, message="Generation complete")
        cancelled = store.cancel(created.job_id)

        self.assertEqual(cancelled.status, "DONE")
        self.assertFalse(cancelled.cancel_requested)
        self.assertEqual(cancelled.updated_at, finished.updated_at)


class JobApiTest(unittest.TestCase):
    def test_cancel_job_endpoint_marks_job_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway_main.job_store = JobStore(Path(temp_dir))
            created = gateway_main.job_store.create("Queued for generation")
            client = TestClient(gateway_main.app)

            response = client.post(f"/api/jobs/{created.job_id}/cancel")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "CANCELLED")
            self.assertTrue(body["cancel_requested"])
            self.assertEqual(gateway_main.job_store.get(created.job_id).status, "CANCELLED")

    def test_cancel_missing_job_endpoint_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway_main.job_store = JobStore(Path(temp_dir))
            client = TestClient(gateway_main.app)

            response = client.post("/api/jobs/missing/cancel")

            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
