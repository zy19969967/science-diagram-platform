from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from common.schemas import GenerateResponse, JobSnapshot, JobStatus

TERMINAL_JOB_STATUSES: set[JobStatus] = {"DONE", "FAILED", "CANCELLED"}
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobCancelled(Exception):
    pass


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    progress: float
    message: str
    result: GenerateResponse | None
    error: str | None
    created_at: str
    updated_at: str
    attempt: int
    max_attempts: int
    cancel_requested: bool
    failure_stage: JobStatus | None

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            job_id=self.job_id,
            status=self.status,
            progress=self.progress,
            message=self.message,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            cancel_requested=self.cancel_requested,
            failure_stage=self.failure_stage,
        )

    @classmethod
    def from_snapshot(cls, snapshot: JobSnapshot) -> "JobRecord":
        return cls(**snapshot.model_dump())


class JobStore:
    def __init__(self, root_dir: Path | None = None, *, recover_active: bool = True) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self.root_dir = root_dir
        if self.root_dir:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            self._load(recover_active=recover_active)

    def create(self, message: str, *, max_attempts: int = 1) -> JobSnapshot:
        now = _now_iso()
        record = JobRecord(
            job_id=uuid.uuid4().hex[:12],
            status="CREATED",
            progress=0.0,
            message=message,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
            attempt=1,
            max_attempts=max(1, min(3, max_attempts)),
            cancel_requested=False,
            failure_stage=None,
        )
        with self._lock:
            self._jobs[record.job_id] = record
            self._write(record)
        return record.snapshot()

    def get(self, job_id: str) -> JobSnapshot | None:
        with self._lock:
            record = self._jobs.get(job_id)
            return record.snapshot() if record else None

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        result: GenerateResponse | None = None,
        error: str | None = None,
        attempt: int | None = None,
        failure_stage: JobStatus | None = None,
    ) -> JobSnapshot:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status == "CANCELLED" and status != "CANCELLED":
                return record.snapshot()

            previous_status = record.status
            if status is not None:
                record.status = status
            if progress is not None:
                record.progress = min(1.0, max(0.0, progress))
            if message is not None:
                record.message = message
            if result is not None:
                record.result = result
                record.error = None
                record.failure_stage = None
            if error is not None:
                record.error = error
            if attempt is not None:
                record.attempt = max(1, min(record.max_attempts, attempt))
            if status == "FAILED":
                record.failure_stage = failure_stage or (
                    previous_status if previous_status not in TERMINAL_JOB_STATUSES else None
                )
            elif failure_stage is not None:
                record.failure_stage = failure_stage
            record.updated_at = _now_iso()
            self._write(record)
            return record.snapshot()

    def cancel(self, job_id: str) -> JobSnapshot:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status in TERMINAL_JOB_STATUSES:
                return record.snapshot()
            record.cancel_requested = True
            record.status = "CANCELLED"
            record.progress = 1.0
            record.message = "Job cancelled"
            record.updated_at = _now_iso()
            self._write(record)
            return record.snapshot()

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs.get(job_id)
            return bool(record.cancel_requested) if record else False

    def _path(self, job_id: str) -> Path:
        if not self.root_dir:
            raise RuntimeError("JobStore has no root_dir")
        if not job_id or any(character in job_id for character in ("/", "\\", os.sep)):
            raise ValueError("Invalid job id.")
        return self.root_dir / f"{job_id}.json"

    def _load(self, *, recover_active: bool) -> None:
        if not self.root_dir:
            return
        for path in self.root_dir.glob("*.json"):
            try:
                snapshot = JobSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
                record = JobRecord.from_snapshot(snapshot)
                if recover_active and record.status not in TERMINAL_JOB_STATUSES:
                    previous_status = record.status
                    record.status = "FAILED"
                    record.progress = 1.0
                    record.message = "Job interrupted by gateway restart"
                    record.error = f"Job was interrupted while in {previous_status} state."
                    record.failure_stage = previous_status
                    record.updated_at = _now_iso()
                self._jobs[record.job_id] = record
                self._write(record)
            except Exception as exc:
                logger.warning("Skipping invalid job snapshot %s: %s", path, exc)

    def _write(self, record: JobRecord) -> None:
        if not self.root_dir:
            return
        path = self._path(record.job_id)
        temp_path = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(record.snapshot().model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)


job_store = JobStore()
