from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from common.schemas import ProjectCreateRequest, ProjectSnapshot, ProjectVersionCreateRequest, ProjectVersionSnapshot


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ProjectStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self._lock = threading.Lock()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, payload: ProjectCreateRequest) -> ProjectSnapshot:
        with self._lock:
            now = utc_now()
            snapshot = ProjectSnapshot(
                project_id=short_id("project"),
                name=payload.name,
                source_image_metadata=payload.source_image_metadata,
                init_plan=payload.init_plan,
                selected_candidate_id=payload.selected_candidate_id,
                latest_version_id=None,
                versions=[],
                created_at=now,
                updated_at=now,
            )
            self._write(snapshot)
            return snapshot

    def list_projects(self) -> list[ProjectSnapshot]:
        with self._lock:
            projects = [self._read(path) for path in self.root_dir.glob("project_*.json")]
        return sorted(projects, key=lambda item: item.updated_at, reverse=True)

    def get_project(self, project_id: str) -> ProjectSnapshot | None:
        with self._lock:
            path = self._path(project_id)
            if not path.exists():
                return None
            return self._read(path)

    def append_version(self, project_id: str, payload: ProjectVersionCreateRequest) -> ProjectVersionSnapshot:
        with self._lock:
            path = self._path(project_id)
            if not path.exists():
                raise KeyError(project_id)
            project = self._read(path)

            version_ids = {version.version_id for version in project.versions}
            if payload.parent_version_id and payload.parent_version_id not in version_ids:
                raise ValueError(f"Parent version not found: {payload.parent_version_id}")

            version = ProjectVersionSnapshot(
                **payload.model_dump(),
                version_id=short_id("version"),
                project_id=project_id,
                created_at=utc_now(),
            )
            project.versions.append(version)
            project.latest_version_id = version.version_id
            project.updated_at = version.created_at
            self._write(project)
            return version

    def _path(self, project_id: str) -> Path:
        if not project_id.startswith("project_") or any(character in project_id for character in ("/", "\\", os.sep)):
            raise ValueError("Invalid project id.")
        return self.root_dir / f"{project_id}.json"

    def _read(self, path: Path) -> ProjectSnapshot:
        return ProjectSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _write(self, snapshot: ProjectSnapshot) -> None:
        path = self._path(snapshot.project_id)
        temp_path = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(snapshot.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
