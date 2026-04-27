from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ASSETS_DIR", str(Path(__file__).resolve().parents[1] / "assets"))
os.environ.setdefault("RUNS_DIR", "/tmp/science-diagram-test-runs")
os.environ.setdefault("PROJECTS_DIR", "/tmp/science-diagram-test-projects")
os.environ.setdefault("JOBS_DIR", "/tmp/science-diagram-test-jobs")
os.environ.setdefault("BENCHMARKS_DIR", "/tmp/science-diagram-test-benchmarks")

from fastapi.testclient import TestClient

from common.schemas import (
    BenchmarkRunCreateRequest,
    EvaluationResult,
    MaskQualityReport,
    PromptTrace,
    RunQualityReport,
    TextValidationReport,
)
from gateway import main as gateway_main
from gateway.benchmarks import BenchmarkStore
from pydantic import ValidationError


def sample_quality_report(
    run_id: str,
    *,
    provider: str,
    localization: float,
    preservation: float,
) -> RunQualityReport:
    return RunQualityReport(
        run_id=run_id,
        mask=MaskQualityReport(
            coverage_ratio=0.25,
            area_pixels=256,
            bounding_box=[10, 12, 200, 180],
            artifact_url=f"http://example/artifacts/{run_id}/mask.png",
        ),
        prompt=PromptTrace(
            instruction=f"Benchmark {run_id}",
            task="shape-guided",
            task_prompt="Add a clean labeled arrow",
            seed=2026,
            planner_source=provider,
        ),
        evaluation=EvaluationResult(
            changed_ratio=0.18,
            outside_mask_change_ratio=0.04,
            inside_mask_change_ratio=0.72,
            mask_coverage_ratio=0.25,
            edit_localization_score=localization,
            preservation_score=preservation,
            note="localized edit",
        ),
        artifacts={"result": f"http://example/artifacts/{run_id}/result.png"},
    )


def sample_text_report(status: str = "pass") -> TextValidationReport:
    return TextValidationReport(
        status=status,
        source="vector-text",
        expected_labels=["enzyme", "substrate"],
        vector_labels=["enzyme", "substrate"],
        matched_labels=["enzyme", "substrate"] if status == "pass" else ["enzyme"],
        missing_labels=[] if status == "pass" else ["substrate"],
    )


def sample_benchmark_record(
    run_id: str,
    *,
    provider: str = "flux-remote",
    localization: float = 0.8,
    preservation: float = 0.95,
    text_status: str | None = "pass",
) -> BenchmarkRunCreateRequest:
    return BenchmarkRunCreateRequest(
        run_id=run_id,
        project_id="project_123",
        version_id=f"version_{run_id}",
        label=f"Run {run_id}",
        scenario="enzyme-pathway",
        provider=provider,
        model="powerpaint-v2.1",
        task="shape-guided",
        seed=2026,
        quality_report=sample_quality_report(
            run_id,
            provider=provider,
            localization=localization,
            preservation=preservation,
        ),
        text_report=sample_text_report(text_status) if text_status else None,
        tags=["phase12", provider],
        metadata={
            "instruction": "Add enzyme arrow",
            "selected_init_candidate_id": "init_1",
        },
    )


class BenchmarkStoreTest(unittest.TestCase):
    def test_benchmark_store_persists_runs_and_summarizes_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = BenchmarkStore(Path(temp_dir))
            first = store.record_run(
                sample_benchmark_record(
                    "run_a",
                    provider="flux-remote",
                    localization=0.6,
                    preservation=0.9,
                    text_status="pass",
                )
            )
            second = store.record_run(
                sample_benchmark_record(
                    "run_b",
                    provider="deterministic-fallback",
                    localization=0.9,
                    preservation=1.0,
                    text_status="fail",
                )
            )

            reloaded = BenchmarkStore(Path(temp_dir)).list_runs()
            summary = BenchmarkStore(Path(temp_dir)).summary()

            self.assertEqual(first.run_id, "run_a")
            self.assertTrue(first.benchmark_id.startswith("benchmark_"))
            self.assertEqual({item.run_id for item in reloaded}, {"run_a", "run_b"})
            self.assertEqual(summary.total_runs, 2)
            self.assertEqual(summary.average_metrics.edit_localization_score, 0.75)
            self.assertEqual(summary.average_metrics.preservation_score, 0.95)
            self.assertEqual(summary.text_pass_rate, 0.5)
            self.assertEqual({item.provider for item in summary.by_provider}, {"flux-remote", "deterministic-fallback"})
            self.assertEqual(summary.recent_runs[0].run_id, second.run_id)

    def test_benchmark_record_rejects_embedded_quality_artifact_data_urls(self) -> None:
        report = sample_quality_report(
            "run_data_url",
            provider="flux-remote",
            localization=0.8,
            preservation=0.95,
        )
        report.artifacts["result"] = "data:image/png;base64,large-result"

        with self.assertRaises(ValidationError):
            BenchmarkRunCreateRequest(
                run_id="run_data_url",
                provider="flux-remote",
                quality_report=report,
            )

    def test_summary_counts_all_runs_even_when_list_is_limited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = BenchmarkStore(Path(temp_dir))
            for index in range(205):
                store.record_run(
                    sample_benchmark_record(
                        f"run_{index}",
                        provider="flux-remote",
                        localization=0.5,
                        preservation=0.9,
                        text_status=None,
                    )
                )

            self.assertEqual(len(store.list_runs()), 50)
            self.assertEqual(store.summary().total_runs, 205)


class BenchmarkApiTest(unittest.TestCase):
    def test_benchmark_routes_record_list_and_summarize_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway_main.benchmark_store = BenchmarkStore(Path(temp_dir))
            client = TestClient(gateway_main.app)

            record_response = client.post(
                "/api/benchmarks/runs",
                json=sample_benchmark_record("run_api", localization=0.82, preservation=0.96).model_dump(),
            )
            self.assertEqual(record_response.status_code, 200)
            self.assertEqual(record_response.json()["run_id"], "run_api")
            self.assertIn("benchmark_id", record_response.json())

            list_response = client.get("/api/benchmarks/runs")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(list_response.json()[0]["run_id"], "run_api")

            summary_response = client.get("/api/benchmarks/summary")
            self.assertEqual(summary_response.status_code, 200)
            summary = summary_response.json()
            self.assertEqual(summary["total_runs"], 1)
            self.assertEqual(summary["average_metrics"]["edit_localization_score"], 0.82)
            self.assertEqual(summary["by_provider"][0]["provider"], "flux-remote")


if __name__ == "__main__":
    unittest.main()
