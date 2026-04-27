from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from common.schemas import (
    BenchmarkMetricAverages,
    BenchmarkProviderSummary,
    BenchmarkRunCreateRequest,
    BenchmarkRunSnapshot,
    BenchmarkSummaryResponse,
)

METRIC_FIELDS = (
    "changed_ratio",
    "outside_mask_change_ratio",
    "inside_mask_change_ratio",
    "mask_coverage_ratio",
    "edit_localization_score",
    "preservation_score",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def metric_averages(runs: list[BenchmarkRunSnapshot]) -> BenchmarkMetricAverages:
    values = {}
    for field in METRIC_FIELDS:
        values[field] = average(
            [
                float(getattr(run.quality_report.evaluation, field))
                for run in runs
                if getattr(run.quality_report.evaluation, field, None) is not None
            ]
        )
    return BenchmarkMetricAverages(**values)


def text_pass_rate(runs: list[BenchmarkRunSnapshot]) -> float | None:
    reports = [run.text_report for run in runs if run.text_report is not None]
    if not reports:
        return None
    passed = sum(1 for report in reports if report.status == "pass")
    return round(passed / len(reports), 4)


class BenchmarkStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self._lock = threading.Lock()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def record_run(self, payload: BenchmarkRunCreateRequest) -> BenchmarkRunSnapshot:
        with self._lock:
            now = utc_now()
            snapshot = BenchmarkRunSnapshot(
                **payload.model_dump(),
                benchmark_id=short_id("benchmark"),
                created_at=now,
                updated_at=now,
            )
            self._write(snapshot)
            return snapshot

    def list_runs(self, *, limit: int = 50) -> list[BenchmarkRunSnapshot]:
        bounded_limit = min(200, max(1, int(limit)))
        return self._all_runs()[:bounded_limit]

    def summary(self, *, recent_limit: int = 8) -> BenchmarkSummaryResponse:
        runs = self._all_runs()
        providers: dict[str, list[BenchmarkRunSnapshot]] = {}
        for run in runs:
            providers.setdefault(run.provider or "unknown", []).append(run)

        by_provider = [
            BenchmarkProviderSummary(
                provider=provider,
                run_count=len(provider_runs),
                average_metrics=metric_averages(provider_runs),
                text_pass_rate=text_pass_rate(provider_runs),
            )
            for provider, provider_runs in providers.items()
        ]
        by_provider.sort(key=lambda item: (-item.run_count, item.provider))

        warnings = [] if runs else ["No benchmark runs recorded yet."]
        return BenchmarkSummaryResponse(
            total_runs=len(runs),
            average_metrics=metric_averages(runs),
            text_pass_rate=text_pass_rate(runs),
            by_provider=by_provider,
            recent_runs=runs[:recent_limit],
            warnings=warnings,
        )

    def _all_runs(self) -> list[BenchmarkRunSnapshot]:
        with self._lock:
            runs = [self._read(path) for path in self.root_dir.glob("benchmark_*.json")]
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def _path(self, benchmark_id: str) -> Path:
        if not benchmark_id.startswith("benchmark_") or any(character in benchmark_id for character in ("/", "\\", os.sep)):
            raise ValueError("Invalid benchmark id.")
        return self.root_dir / f"{benchmark_id}.json"

    def _read(self, path: Path) -> BenchmarkRunSnapshot:
        return BenchmarkRunSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _write(self, snapshot: BenchmarkRunSnapshot) -> None:
        path = self._path(snapshot.benchmark_id)
        temp_path = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(snapshot.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
