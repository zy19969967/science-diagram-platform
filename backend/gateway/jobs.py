from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from common.schemas import GenerateResponse, JobSnapshot, JobStatus


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
        )


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}

    def create(self, message: str) -> JobSnapshot:
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
        )
        with self._lock:
            self._jobs[record.job_id] = record
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
    ) -> JobSnapshot:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)

            if status is not None:
                record.status = status
            if progress is not None:
                record.progress = min(1.0, max(0.0, progress))
            if message is not None:
                record.message = message
            if result is not None:
                record.result = result
            if error is not None:
                record.error = error
            record.updated_at = _now_iso()
            return record.snapshot()


job_store = JobStore()
