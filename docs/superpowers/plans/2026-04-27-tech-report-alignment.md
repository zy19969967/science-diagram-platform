# Tech Report Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the project closer to the technical report through staged, reviewable milestones.

**Architecture:** Phase 1 adds pure-text initial canvas contracts and a deterministic fallback renderer behind gateway endpoints. Phase 2 adds an in-process async job skeleton with `job_id` polling while preserving the synchronous API.

**Tech Stack:** FastAPI, Pydantic, PIL, React 18, Vite, Docker Compose.

---

## File Structure

- Create `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`: design record and phase boundaries.
- Modify `backend/common/schemas.py`: add scene-plan and init-generation models.
- Create `backend/common/init_logic.py`: deterministic scene-plan and candidate renderer.
- Modify `backend/gateway/main.py`: expose `/api/init-plan` and `/api/init-generate`.
- Create `backend/tests/test_init_logic.py`: unit tests for shared init logic.
- Modify `frontend/src/App.jsx`: add text-init state, API calls, candidate selection.
- Modify `frontend/src/components/ControlPanel.jsx`: add initial-canvas controls.
- Create or modify a result/candidate panel component for generated candidates.
- Modify `frontend/src/styles.css`: style candidate controls without disrupting the current editor.
- Modify `docs/known-issues.md`: mark Phase 1 fallback limitations and future FLUX service.

## Task 1: Backend Scene Plan And Fallback Candidates

**Files:**
- Modify: `backend/common/schemas.py`
- Create: `backend/common/init_logic.py`
- Modify: `backend/gateway/main.py`
- Test: `backend/tests/test_init_logic.py`

- [x] **Step 1: Write failing tests**

```python
from common.init_logic import build_init_candidates, build_scene_plan
from common.schemas import InitGenerateRequest, ScenePlanRequest


def test_scene_plan_extracts_labels_from_chinese_instruction():
    plan = build_scene_plan(
        ScenePlanRequest(
            instruction="鐢讳竴涓叾淇冨弽搴旂ず鎰忓浘锛屽寘鍚簳鐗┿€侀叾銆佷骇鐗╁拰绠ご",
            style="flat-vector",
            candidate_count=2,
        )
    )

    assert plan.mode == "create_from_text"
    assert plan.candidate_count == 2
    assert "搴曠墿" in plan.labels
    assert "閰? in plan.labels
    assert "浜х墿" in plan.labels
    assert "arrow" in plan.positive_prompt.lower()


def test_init_candidates_are_deterministic_and_image_data_urls():
    plan = build_scene_plan(
        ScenePlanRequest(
            instruction="鐢讳竴涓叾淇冨弽搴旂ず鎰忓浘锛屽寘鍚簳鐗┿€侀叾銆佷骇鐗╁拰绠ご",
            candidate_count=2,
            seed=123,
        )
    )

    first = build_init_candidates(InitGenerateRequest(scene_plan=plan, seed=123))
    second = build_init_candidates(InitGenerateRequest(scene_plan=plan, seed=123))

    assert first.provider == "deterministic-fallback"
    assert len(first.candidates) == 2
    assert first.candidates[0].image.startswith("data:image/png;base64,")
    assert first.candidates[0].image == second.candidates[0].image
    assert first.candidates[0].seed == 123
```

- [x] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=backend python -m unittest backend.tests.test_init_logic -v`

Expected: fails because `common.init_logic`, `ScenePlanRequest`, and `InitGenerateRequest` do not exist.

- [x] **Step 3: Implement schemas and fallback logic**

Add Pydantic request/response models, build a simple scene plan from instruction text, and render deterministic PNG candidates with PIL.

- [x] **Step 4: Add gateway endpoints**

Expose:

```text
POST /api/init-plan
POST /api/init-generate
```

Both endpoints should use the deterministic fallback logic in Phase 1.

- [x] **Step 5: Run tests and import checks**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_init_logic -v
PYTHONPATH=backend python -m py_compile backend/common/schemas.py backend/common/init_logic.py backend/gateway/main.py
```

Expected: all pass.

## Task 2: Frontend Text Initial Canvas Flow

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ControlPanel.jsx`
- Modify: `frontend/src/components/ResultPanel.jsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Write expected behavior**

The user can enter a text prompt with no uploaded image, click a button to create initial candidates, see 1-4 candidates, and choose one. Choosing a candidate sets it as `sourceImage`, clears local masks, stores init metadata, and reuses the current edit workflow.

- [x] **Step 2: Implement minimal UI state and API calls**

Add `initPrompt`, `initCandidates`, `initPlan`, `isInitializing`, and `selectedInitCandidateId` state to `App.jsx`. Add `createInitialCanvas()` and `chooseInitialCandidate(candidate)` functions.

- [x] **Step 3: Add controls**

Add a 鈥滄棤鍥剧敓鎴愬垵鍥锯€?button to `ControlPanel.jsx`, disabled while initializing. Use the existing instruction text as the prompt to avoid duplicating input fields.

- [x] **Step 4: Render candidates**

Render candidate thumbnails in `ResultPanel.jsx` above or near the result preview. Each candidate should show its id/provider/seed and a selection button.

- [x] **Step 5: Run frontend build**

Run: `cd frontend && npm run build`

Expected: Vite build exits with code 0.

## Task 3: Documentation, Review, Commit, Push

**Files:**
- Modify: `docs/known-issues.md`
- Review: all changed files

- [x] **Step 1: Document Phase 1 limitations**

Add that pure-text initial canvas is now contractually wired through deterministic fallback, while FLUX service, multi-candidate scoring, vector labels, and async generation remain future work.

- [x] **Step 2: Review diff**

Run:

```bash
git diff --stat
git diff -- backend/common/schemas.py backend/common/init_logic.py backend/gateway/main.py backend/tests/test_init_logic.py frontend/src/App.jsx frontend/src/components/ControlPanel.jsx frontend/src/components/ResultPanel.jsx frontend/src/styles.css docs/known-issues.md docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md docs/superpowers/plans/2026-04-27-tech-report-alignment.md
```

- [x] **Step 3: Verify**

Run backend unit tests and frontend build again.

- [x] **Step 4: Commit**

Stage only Phase 1 files, not untracked Word documents.

Commit message:

```text
Add text-to-initial-canvas fallback flow
```

- [x] **Step 5: Push**

Push the current branch:

```bash
git push -u origin codex/report-alignment-phase1
```

If this is the first remote upload for the branch, open or update a draft PR against `main`.

## Task 4: Backend Async Job Skeleton

**Files:**
- Modify: `backend/common/schemas.py`
- Create: `backend/gateway/jobs.py`
- Modify: `backend/gateway/main.py`
- Test: `backend/tests/test_jobs.py`

- [x] **Step 1: Write failing tests**

```python
import unittest

from gateway.jobs import JobStore


class JobStoreTest(unittest.TestCase):
    def test_create_and_update_job_snapshot(self):
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

    def test_update_missing_job_raises_key_error(self):
        store = JobStore()

        with self.assertRaises(KeyError):
            store.update("missing", status="DONE")
```

- [x] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=backend python -m unittest backend.tests.test_jobs -v`

Expected: fails because `gateway.jobs` does not exist.

- [x] **Step 3: Add job schemas**

Add `JobStatus`, `JobCreateRequest`, and `JobSnapshot` to `backend/common/schemas.py`. `JobCreateRequest` should wrap the existing `GenerateRequest` for now:

```python
JobStatus = Literal["CREATED", "PLANNING", "SEGMENTING", "EXECUTING", "EVALUATING", "DONE", "FAILED"]

class JobCreateRequest(BaseModel):
    kind: Literal["generate"] = "generate"
    generate_request: GenerateRequest

class JobSnapshot(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(ge=0.0, le=1.0)
    message: str
    result: GenerateResponse | None = None
    error: str | None = None
    created_at: str
    updated_at: str
```

- [x] **Step 4: Implement `JobStore`**

Create a thread-safe in-memory store with `create`, `update`, and `get`. It is intentionally in-process for Phase 2; Redis/Celery remains a later phase.

- [x] **Step 5: Refactor gateway generate pipeline**

Move the body of `/api/generate` into a reusable helper that accepts `base_url` and an optional progress callback. Keep `/api/generate` behavior compatible.

- [x] **Step 6: Add endpoints**

Expose:

```text
POST /api/jobs
GET /api/jobs/{job_id}
```

`POST /api/jobs` should return a created snapshot immediately and schedule a background generate task. The background task should update status through `PLANNING`, `SEGMENTING`, `EXECUTING`, `EVALUATING`, then `DONE` or `FAILED`.

- [x] **Step 7: Verify**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_init_logic backend.tests.test_jobs -v
PYTHONPATH=backend python -m py_compile backend/common/schemas.py backend/gateway/jobs.py backend/gateway/main.py
```

Expected: all pass.

## Task 5: Frontend Async Generate Flow

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ControlPanel.jsx`
- Modify: `frontend/src/components/ResultPanel.jsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Extract shared generate payload creation**

Create `buildGenerateRequestPayload()` in `App.jsx` so synchronous and async generation use identical validation and request bodies.

- [x] **Step 2: Add job state and polling**

Add `jobSnapshot` and `isJobGenerating` state. Add `startGenerateJob()` that posts to `/api/jobs`, then polls `/api/jobs/{job_id}` until `DONE` or `FAILED`.

- [x] **Step 3: Render controls**

Add an 鈥滃紓姝ョ敓鎴愨€?button next to the existing synchronous PowerPaint button. Keep the existing button so users can compare both flows during development.

- [x] **Step 4: Render progress**

Show job id, status, progress, and message in the result panel. When the job reaches `DONE`, set `latestResult` and append to history exactly like synchronous generation.

- [x] **Step 5: Verify frontend build**

Run: `cd frontend && npm run build`

Expected: Vite build exits with code 0.

## Task 6: Phase 2 Review, Docs, Commit, Push

**Files:**
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`

- [x] **Step 1: Document Phase 2 limitations**

Update known issues to say the project now has an in-process async job skeleton, but not Redis/Celery durability, cancellation, persisted queue state, or multi-worker scheduling.

- [x] **Step 2: Review**

Request code review for Phase 2 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend unit tests, backend compile checks, frontend build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 2 files and commit:

```text
Add async generation job skeleton
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Task 17: Durable Async Job State

**Files:**
- Modify: `backend/common/schemas.py`
- Modify: `backend/gateway/jobs.py`
- Modify: `backend/gateway/main.py`
- Modify: `backend/tests/test_jobs.py`
- Modify: `backend/tests/test_ci_workflow.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `docker-compose.yml`
- Modify: `.gitignore`
- Create: `data/jobs/.gitkeep`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ResultPanel.jsx`

- [x] **Step 1: Write failing durable job tests**

Add backend tests proving that file-backed jobs persist to disk, terminal results reload across a new `JobStore`, active jobs recovered after restart are marked failed with failure provenance instead of disappearing, cancellation is persisted, and missing job cancellation returns an error. Add an API-level test for `POST /api/jobs/{job_id}/cancel`.

- [x] **Step 2: Implement file-backed durable job store**

Extend `JobStore` to accept a `JOBS_DIR` path, write each job snapshot atomically to JSON, reload snapshots at startup, preserve existing in-memory behavior for tests that construct `JobStore()` with no path, and guard writes with a lock.

- [x] **Step 3: Add cancellation and retry metadata**

Extend `JobStatus` and `JobSnapshot` with cancellation and attempt metadata while keeping existing fields compatible. Add `POST /api/jobs/{job_id}/cancel`. Keep automatic retries conservative: store attempt/max-attempt metadata and preserve status provenance without introducing Redis/Celery in this phase.

- [x] **Step 4: Frontend cancel action**

Add a cancel button for the currently tracked async job. It should invalidate polling consistently and display the cancelled snapshot when the gateway accepts the cancel request.

- [x] **Step 5: Verify**

Run:

```bash
PYTHONPATH=backend ASSETS_DIR=backend/assets RUNS_DIR=/tmp/science-diagram-test-runs PROJECTS_DIR=/tmp/science-diagram-test-projects JOBS_DIR=/tmp/science-diagram-test-jobs python -m unittest discover -s backend/tests -p 'test_*.py' -v
PYTHONPATH=backend python -m py_compile backend/common/schemas.py backend/common/init_logic.py backend/common/canvas_state.py backend/common/quality.py backend/common/utils/masks.py backend/gateway/jobs.py backend/gateway/projects.py backend/gateway/main.py
cd frontend && node tests/projectState.test.mjs && node tests/canvasState.test.mjs && npm run build
git diff --check
```

Expected: all pass.

## Task 18: Phase 7 Review, Commit, Push

**Files:**
- Review: Phase 7 code and docs from Task 17
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 7 limitations**

Update docs to say Phase 7 provides durable file-backed async job status, cancellation metadata, startup recovery behavior, and resumable status reads, but not Redis/Celery, multi-worker scheduling, true process-external execution, or hard interruption of an in-flight model call yet.

- [x] **Step 2: Review**

Request spec and code-quality review for Phase 7 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend tests, backend compile checks, frontend helper tests/build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 7 files and commit:

```text
Add durable async job state
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Task 19: Fabric.js Layer Editor Slice

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Modify: `frontend/src/canvasState.js`
- Create: `frontend/src/layerState.js`
- Create: `frontend/tests/layerState.test.mjs`
- Modify: `frontend/tests/canvasState.test.mjs`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ControlPanel.jsx`
- Modify: `frontend/src/components/EditorStage.jsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Write failing layer-state tests**

Add frontend helper tests proving that layer ordering keeps the base image at the bottom, preserves valid non-base layer order, drops missing layer ids, and applies visibility/lock/opacity overrides into `canvas_state`.

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
cd frontend && node tests/layerState.test.mjs && node tests/canvasState.test.mjs
```

Expected: fails because `layerState.js`, layer ordering helpers, and `createCanvasStateSnapshot(..., layerOrder, layerOverrides)` support do not exist yet.

- [x] **Step 3: Add Fabric dependency**

Install and commit `fabric` as a front-end runtime dependency. Keep `package-lock.json` in the repo so CI installs the same dependency tree.

- [x] **Step 4: Implement layer-state helpers**

Create pure helper functions for editor layer construction, ordering, move-up/move-down, and per-layer metadata overrides. Keep these helpers independent of Fabric so they can be tested in Node.

- [x] **Step 5: Implement Fabric editor shell**

Replace the current React-only image/asset/text overlay path with a Fabric.js canvas for base image, asset, and text objects while preserving the existing native mask canvas for mask painting. Add a layer interaction mode so Fabric selection does not conflict with brush/erase mode.

- [x] **Step 6: Add layer panel actions**

Show base, mask, asset, and text layers in the editor. Support selecting a layer, toggling visibility, toggling lock state, and reordering non-base layers. Dragging or scaling Fabric objects should update asset placement or text layer positions.

- [x] **Step 7: Verify**

Run:

```bash
cd frontend && node tests/layerState.test.mjs && node tests/canvasState.test.mjs && node tests/projectState.test.mjs && npm run build
PYTHONPATH=backend ASSETS_DIR=backend/assets RUNS_DIR=/tmp/science-diagram-test-runs PROJECTS_DIR=/tmp/science-diagram-test-projects JOBS_DIR=/tmp/science-diagram-test-jobs python -m unittest discover -s backend/tests -p 'test_*.py' -v
git diff --check
```

Expected: all pass.

## Task 20: Phase 8 Review, Commit, Push

**Files:**
- Review: Phase 8 code and docs from Task 19
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 8 scope and limitations**

Update docs to say Phase 8 provides a first Fabric.js layer editor for base, mask, asset, and text layers while preserving `canvas_state`, but does not yet include OCR, SVG/PPT export, complex grouping, or full Fabric scene persistence.

- [x] **Step 2: Review**

Request code review for Phase 8 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run frontend helper tests, frontend build, backend tests, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 8 files and commit:

```text
Add Fabric layer editor
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Task 21: Rich SAM-2 Point Prompts

**Files:**
- Modify: `backend/common/schemas.py`
- Modify: `backend/common/segment_logic.py`
- Modify: `backend/common/utils/masks.py`
- Modify: `backend/segmenter/runtime.py`
- Modify: `backend/gateway/main.py`
- Create: `backend/tests/test_segment_logic.py`
- Modify: `backend/tests/test_canvas_state.py`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/canvasState.js`
- Create: `frontend/src/regionPrompts.js`
- Create: `frontend/tests/regionPrompts.test.mjs`
- Modify: `frontend/tests/canvasState.test.mjs`
- Modify: `frontend/src/components/ControlPanel.jsx`
- Modify: `frontend/src/components/EditorStage.jsx`
- Modify: `frontend/src/layerState.js`
- Modify: `frontend/src/styles.css`
- Modify: `.github/workflows/ci.yml`
- Modify: `backend/tests/test_ci_workflow.py`

- [x] **Step 1: Write failing backend point-prompt tests**

Add tests proving `SegmentRequest` accepts normalized positive/negative point prompts, `build_segment` can create a deterministic fallback mask from positive points, empty requests still fail, and `SegmenterRuntime` converts normalized points into SAM pixel coordinates and labels.

- [x] **Step 2: Run backend tests and verify failure**

Run:

```bash
PYTHONPATH=backend ASSETS_DIR=backend/assets RUNS_DIR=/tmp/science-diagram-test-runs PROJECTS_DIR=/tmp/science-diagram-test-projects JOBS_DIR=/tmp/science-diagram-test-jobs python -m unittest backend.tests.test_segment_logic -v
```

Expected: fails because `SegmentPoint`, `point_prompts`, and point prompt runtime helpers do not exist yet.

- [x] **Step 3: Implement backend point prompt contract**

Add `SegmentPoint` with normalized `x`, `y`, and `label` values. Add `point_prompts` to `SegmentRequest` and `GenerateRequest`. Preserve existing mask, asset placement, and box behavior. Gateway generation should pass `point_prompts` into `/api/segment` and planner hints.

- [x] **Step 4: Implement SAM2.1 point prompt runtime support**

Convert normalized points to pixel coordinates for the current source image. Pass both `input_points` and `input_labels` to `Sam2Processor` when points exist, while retaining box prompt fallback from mask/box/asset placement. If SAM runtime is unavailable, the deterministic fallback should draw positive disks and carve negative disks.

- [x] **Step 5: Write failing frontend point prompt tests**

Add pure helper tests for adding/removing/clamping positive and negative region points. Extend `canvasState` tests to verify point prompts are serialized as a `region-prompt` layer without embedded data URLs.

- [x] **Step 6: Implement frontend point prompt UI**

Add positive-point and negative-point canvas modes. Clicking the canvas in those modes should add normalized point prompts. Show point markers, allow removing markers, send `point_prompts` in sync/async generate payloads, and allow point-only generation without requiring painted mask pixels.

- [x] **Step 7: Verify**

Run:

```bash
PYTHONPATH=backend ASSETS_DIR=backend/assets RUNS_DIR=/tmp/science-diagram-test-runs PROJECTS_DIR=/tmp/science-diagram-test-projects JOBS_DIR=/tmp/science-diagram-test-jobs python -m unittest discover -s backend/tests -p 'test_*.py' -v
PYTHONPATH=backend python -m py_compile backend/common/schemas.py backend/common/init_logic.py backend/common/canvas_state.py backend/common/quality.py backend/common/utils/masks.py backend/gateway/jobs.py backend/gateway/projects.py backend/gateway/main.py backend/segmenter/runtime.py
cd frontend && node tests/regionPrompts.test.mjs && node tests/layerState.test.mjs && node tests/canvasState.test.mjs && node tests/projectState.test.mjs && npm run build
git diff --check
```

Expected: all pass.

## Task 22: Phase 9 Review, Commit, Push

**Files:**
- Review: Phase 9 code and docs from Task 21
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 9 scope and limitations**

Update docs to say Phase 9 supports positive/negative point prompts and provenance while preserving box/mask fallback, but does not yet provide instance candidate selection, automatic text grounding, or advanced SAM multi-mask refinement UI.

- [x] **Step 2: Review**

Request code review for Phase 9 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend tests, backend compile checks, frontend helper tests/build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 9 files and commit:

```text
Add SAM point prompt refinement
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Task 15: Project Persistence And Version Tree

**Files:**
- Create: `backend/gateway/projects.py`
- Create: `backend/tests/test_projects.py`
- Modify: `backend/common/schemas.py`
- Modify: `backend/gateway/main.py`
- Modify: `.github/workflows/ci.yml`
- Create: `frontend/src/projectState.js`
- Create: `frontend/tests/projectState.test.mjs`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ResultPanel.jsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Write failing persistence tests**

Add backend tests that prove a file-backed project store can create a project, append two parent-linked versions, reload from disk, and reject missing parents. Add frontend helper tests that prove the project create/version request payloads contain source metadata, selected initial candidate ids, parent version ids, run ids, canvas state, artifacts, and quality reports without embedding large result data URLs.

- [x] **Step 2: Implement backend project schemas and store**

Add Pydantic models for project creation, version creation, persisted versions, and project snapshots. Implement a JSON-backed `ProjectStore` rooted at `PROJECTS_DIR` with deterministic validation, atomic writes, `create_project`, `list_projects`, `get_project`, and `append_version`.

- [x] **Step 3: Expose project APIs**

Add gateway endpoints:

```text
GET /api/projects
POST /api/projects
GET /api/projects/{project_id}
POST /api/projects/{project_id}/versions
```

Keep existing generation and async job APIs compatible.

- [x] **Step 4: Add frontend save/load workflow**

Add a small project panel to the result rail so users can save the current canvas as a project version, see the current project id/latest version, refresh saved projects, and load a saved project/version back into the editing workspace.

- [x] **Step 5: Verify**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_projects -v
PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py' -v
cd frontend && node tests/projectState.test.mjs && node tests/canvasState.test.mjs && npm run build
git diff --check
```

Expected: all pass.

## Task 16: Phase 6 Review, Commit, Push

**Files:**
- Review: Phase 6 code and docs from Task 15
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 6 limitations**

Update known issues and requirements to say Phase 6 provides lightweight single-user file-backed project persistence and parent-linked version lineage, but not multi-user auth, database migrations, durable async queue state, or full Fabric.js editing yet.

- [x] **Step 2: Review**

Request spec and code-quality review for Phase 6 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend tests, frontend helper tests, frontend build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 6 files and commit:

```text
Add project persistence and version tree
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Task 7: Backend Canvas State Contract

**Files:**
- Modify: `backend/common/schemas.py`
- Create: `backend/common/canvas_state.py`
- Modify: `backend/gateway/main.py`
- Test: `backend/tests/test_canvas_state.py`

- [x] **Step 1: Write failing tests**

```python
import unittest

from common.canvas_state import build_canvas_state_after_generate
from common.schemas import CanvasLayer, CanvasState


class CanvasStateTest(unittest.TestCase):
    def test_build_canvas_state_after_generate_updates_base_and_history(self):
        state = CanvasState(
            canvas_id="canvas_1",
            width=1024,
            height=768,
            source="init-candidate",
            layers=[
                CanvasLayer(id="base", type="base-image", name="Base", data={"source": "init"}),
                CanvasLayer(id="mask", type="mask", name="Mask", data={"pixel_count": 100}),
            ],
            history=["init_1"],
            metadata={"selected_init_candidate_id": "init_1"},
        )

        updated = build_canvas_state_after_generate(
            state,
            run_id="run_123",
            artifacts={
                "result": "http://example/artifacts/run_123/result.png",
                "mask": "http://example/artifacts/run_123/mask.png",
            },
        )

        self.assertEqual(updated.source, "generated")
        self.assertEqual(updated.history, ["init_1", "run_123"])
        self.assertEqual(updated.metadata["latest_run_id"], "run_123")
        self.assertEqual(updated.metadata["latest_result_url"], "http://example/artifacts/run_123/result.png")
        self.assertEqual(updated.layers[0].data["image_url"], "http://example/artifacts/run_123/result.png")
        self.assertEqual(updated.layers[1].data["mask_url"], "http://example/artifacts/run_123/mask.png")
```

- [x] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=backend python -m unittest backend.tests.test_canvas_state -v`

Expected: fails because `common.canvas_state` and canvas state schemas do not exist.

- [x] **Step 3: Add schemas**

Add:

```python
CanvasLayerType = Literal["base-image", "mask", "asset", "text", "result"]

class CanvasLayer(BaseModel):
    id: str
    type: CanvasLayerType
    name: str
    visible: bool = True
    locked: bool = False
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    data: dict[str, Any] = Field(default_factory=dict)

class CanvasState(BaseModel):
    canvas_id: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source: Literal["upload", "init-candidate", "history", "generated"] = "upload"
    layers: list[CanvasLayer] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Add optional `canvas_state` to `GenerateRequest` and `GenerateResponse`.

- [x] **Step 4: Implement `build_canvas_state_after_generate`**

Return a deep-copied updated state. Update or add a base-image layer with result URL, update mask layer with mask URL, append `run_id` to history, and add latest artifact metadata.

- [x] **Step 5: Wire gateway metadata**

In `generate_pipeline`, save `canvas_state_before` and `canvas_state_after` into `metadata.json`, and return `canvas_state` on `GenerateResponse`.

- [x] **Step 6: Verify**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py' -v
PYTHONPATH=backend python -m py_compile backend/common/schemas.py backend/common/canvas_state.py backend/gateway/main.py
```

Expected: all pass.

## Task 8: Frontend Canvas State And Text Layers

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/EditorStage.jsx`
- Modify: `frontend/src/components/ResultPanel.jsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Add text layer state**

Add `textLayers` state to `App.jsx`. When selecting an initial candidate, create text layers from `initPlan.labels`. On upload/clear, reset text layers. On continuing from history, restore text layers from `item.canvas_state.layers` where `type === "text"` when available.

- [x] **Step 2: Build `canvas_state` snapshots**

Add `buildCanvasState(maskPayload)` in `App.jsx`. It should include base-image, mask, asset, and text layers plus metadata for task, instruction, selected asset, selected init candidate, and init provider.

- [x] **Step 3: Submit state with generation**

Add `canvas_state: buildCanvasState(maskPayload)` to the shared generate payload. This automatically covers synchronous and async generation.

- [x] **Step 4: Render text layer overlays**

Pass `textLayers` to `EditorStage` and render visible text layers as absolutely positioned overlays on the canvas stack. Keep it lightweight HTML; Fabric.js remains future work.

- [x] **Step 5: Display canvas state summary**

Show the latest returned canvas state source, layer count, and history count in `ResultPanel`.

- [x] **Step 6: Verify frontend build**

Run: `cd frontend && npm run build`

Expected: Vite build exits with code 0.

## Task 9: Phase 3 Review, Docs, Commit, Push

**Files:**
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 3 limitations**

Update known issues to say the project now records serializable canvas state and lightweight text layers, but still lacks Fabric.js editing, persisted project database, branchable version tree, SVG export, and OCR validation.

- [x] **Step 2: Review**

Request code review for Phase 3 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend unit tests, backend compile checks, frontend build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 3 files and commit:

```text
Add serializable canvas state layers
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Task 10: Backend Quality Report Contract

**Files:**
- Modify: `backend/common/schemas.py`
- Create: `backend/common/quality.py`
- Modify: `backend/common/utils/masks.py`
- Modify: `backend/gateway/main.py`
- Test: `backend/tests/test_quality.py`

- [x] **Step 1: Write failing tests**

```python
from PIL import Image

from common.quality import build_quality_report
from common.schemas import GenerateRequest, PlanResponse
from common.utils.masks import evaluate_edit


def test_evaluate_edit_reports_inside_and_localization_metrics():
    source = Image.new("RGB", (4, 4), "black")
    result = Image.new("RGB", (4, 4), "black")
    mask = Image.new("L", (4, 4), 0)
    for x in range(2):
        for y in range(2):
            result.putpixel((x, y), (255, 255, 255))
            mask.putpixel((x, y), 255)

    evaluation = evaluate_edit(source, result, mask)

    assert evaluation.mask_coverage_ratio == 0.25
    assert evaluation.inside_mask_change_ratio == 1.0
    assert evaluation.outside_mask_change_ratio == 0.0
    assert evaluation.edit_localization_score == 1.0
    assert evaluation.preservation_score == 1.0


def test_quality_report_records_mask_and_prompt_trace():
    mask = Image.new("L", (4, 4), 0)
    for x in range(2):
        for y in range(2):
            mask.putpixel((x, y), 255)

    payload = GenerateRequest(
        source_image="data:image/png;base64,source",
        instruction="add enzyme arrow",
        task="shape-guided",
        selected_asset_id="arrow",
        steps=20,
        guidance_scale=6.5,
        fitting_degree=0.75,
        seed=42,
    )
    plan = PlanResponse(
        task="shape-guided",
        task_prompt="draw a clean arrow",
        negative_prompt="blurry",
        reasoning="test",
    )

    report = build_quality_report(
        run_id="run_1",
        payload=payload,
        plan=plan,
        mask=mask,
        evaluation=evaluate_edit(Image.new("RGB", (4, 4), "black"), Image.new("RGB", (4, 4), "black"), mask),
        artifacts={"mask": "http://example/mask.png"},
        planner_source="provided-plan",
    )

    assert report.run_id == "run_1"
    assert report.mask.coverage_ratio == 0.25
    assert report.mask.bounding_box == [0, 0, 1, 1]
    assert report.prompt.task == "shape-guided"
    assert report.prompt.seed == 42
    assert report.prompt.parameters["steps"] == 20
    assert report.prompt.planner_source == "provided-plan"
```

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_quality -v
```

Expected: fails because `common.quality` and new evaluation fields do not exist.

- [x] **Step 3: Add quality schemas**

Add `MaskQualityReport`, `PromptTrace`, and `RunQualityReport` to `backend/common/schemas.py`. Add optional `quality_report` to `GenerateResponse`.

- [x] **Step 4: Extend evaluation metrics**

Update `evaluate_edit` in `backend/common/utils/masks.py` to return `inside_mask_change_ratio`, `mask_coverage_ratio`, `edit_localization_score`, and `preservation_score` while preserving existing fields.

- [x] **Step 5: Implement `build_quality_report`**

Create `backend/common/quality.py` to calculate mask quality, bounding box, prompt trace, generation parameters, artifact links, and planner source.

- [x] **Step 6: Wire gateway response and metadata**

In `generate_pipeline`, track whether the plan was supplied or produced by the planner/fallback path. Build `quality_report`, save it in `metadata.json`, and return it on `GenerateResponse`.

- [x] **Step 7: Verify backend**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_quality backend.tests.test_init_logic backend.tests.test_jobs backend.tests.test_canvas_state -v
PYTHONPATH=backend python -m py_compile backend/common/schemas.py backend/common/quality.py backend/common/utils/masks.py backend/gateway/main.py
```

Expected: all pass.

## Task 11: Frontend Quality Report Display

**Files:**
- Modify: `frontend/src/components/ResultPanel.jsx`
- Reuse existing: `frontend/src/styles.css`

- [x] **Step 1: Add richer metric cards**

In `ResultPanel.jsx`, when `latestResult.quality_report` exists, render mask coverage, inside-mask change, localization score, preservation score, prompt task, planner source, and seed.

- [x] **Step 2: Preserve existing metric fallback**

Keep the existing `latestResult.evaluation` cards so older responses without `quality_report` still render.

- [x] **Step 3: Verify frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: Vite build exits with code 0.

## Task 12: Phase 4 Review, Docs, Commit, Push

**Files:**
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 4 limitations**

Update known issues to say the project now records per-run quality reports and prompt/provenance metadata, but still lacks CI, OCR validation, dataset-level benchmark aggregation, and persistent experiment dashboards.

- [x] **Step 2: Review**

Request code review for Phase 4 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend unit tests, backend compile checks, frontend build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 4 files and commit:

```text
Add generation quality report metadata
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.

## Remaining Phase Roadmap

The rest of the report alignment should proceed in this order:

1. Phase 5: CI validation baseline.
2. Phase 6: persisted projects and version tree.
3. Phase 7: durable async queue and worker state.
4. Phase 8: Fabric.js layer editor.
5. Phase 9: richer SAM-2 point/box interaction.
6. Phase 10: OCR, vector text reconciliation, and SVG export.
7. Phase 11: real FLUX initial-canvas service and candidate scoring.
8. Phase 12: benchmark and experiment dashboard.
9. Phase 13: auth, deployment hardening, and final traceability matrix.

## Task 13: CI Validation Baseline

**Files:**
- Create: `.github/workflows/ci.yml`
- Test: `backend/tests/test_ci_workflow.py`
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Write failing workflow test**

```python
from pathlib import Path


def test_ci_workflow_runs_backend_and_frontend_checks():
    workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "Backend validation" in text
    assert "Frontend validation" in text
    assert "python -m unittest discover -s backend/tests -p 'test_*.py' -v" in text
    assert "python -m py_compile" in text
    assert "node tests/canvasState.test.mjs" in text
    assert "npm run build" in text
    assert "git diff --check" in text
```

- [x] **Step 2: Run test and verify failure**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_ci_workflow -v
```

Expected: fails because `.github/workflows/ci.yml` does not exist.

- [x] **Step 3: Add GitHub Actions workflow**

Create `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - main
      - codex/report-alignment-phase1

jobs:
  backend:
    name: Backend validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install backend test dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r backend/gateway/requirements.txt
      - name: Run backend tests
        env:
          PYTHONPATH: backend
        run: python -m unittest discover -s backend/tests -p 'test_*.py' -v
      - name: Compile backend modules
        env:
          PYTHONPATH: backend
        run: |
          python -m py_compile \
            backend/common/schemas.py \
            backend/common/init_logic.py \
            backend/common/canvas_state.py \
            backend/common/quality.py \
            backend/common/utils/masks.py \
            backend/gateway/jobs.py \
            backend/gateway/main.py
      - name: Import backend modules
        env:
          PYTHONPATH: backend
          ASSETS_DIR: backend/assets
          RUNS_DIR: /tmp/science-diagram-runs
        run: |
          python - <<'PY'
          import common.schemas
          import common.init_logic
          import common.canvas_state
          import common.quality
          import gateway.jobs
          import gateway.main
          PY

  frontend:
    name: Frontend validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install frontend dependencies
        working-directory: frontend
        run: npm install
      - name: Run frontend helper tests
        working-directory: frontend
        run: node tests/canvasState.test.mjs
      - name: Build frontend
        working-directory: frontend
        run: npm run build

  hygiene:
    name: Diff hygiene
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Check whitespace
        env:
          BASE_REF: ${{ github.base_ref }}
          BEFORE_SHA: ${{ github.event.before }}
        run: |
          if [ -n "$BASE_REF" ]; then
            git fetch --no-tags --depth=1 origin "$BASE_REF"
            git diff --check "origin/$BASE_REF...HEAD"
          elif [ -n "$BEFORE_SHA" ] && [ "$BEFORE_SHA" != "0000000000000000000000000000000000000000" ]; then
            git diff --check "$BEFORE_SHA" HEAD
          elif git rev-parse HEAD^ >/dev/null 2>&1; then
            git diff --check HEAD^ HEAD
          else
            echo "No base commit available for whitespace diff."
          fi
```

- [x] **Step 4: Run test and local verification**

Run:

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_ci_workflow -v
PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py' -v
cd frontend && node tests/canvasState.test.mjs && npm run build
git diff --check
```

Expected: all pass.

## Task 14: Phase 5 Review, Commit, Push

**Files:**
- Review: `.github/workflows/ci.yml`
- Modify: `docs/known-issues.md`
- Modify: `docs/superpowers/requirements/2026-04-27-user-requirements.md`
- Modify: `docs/superpowers/plans/2026-04-27-tech-report-alignment.md`
- Modify: `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`

- [x] **Step 1: Document Phase 5 limitations**

Update known issues to say CI now covers lightweight backend/frontend validation, but does not run GPU/model inference, Docker builds, OCR validation, or end-to-end browser tests yet.

- [x] **Step 2: Review**

Request code review for Phase 5 and fix Critical/Important findings.

- [x] **Step 3: Verify**

Run backend unit tests, backend compile checks, frontend helper test, frontend build, and `git diff --check`.

- [x] **Step 4: Commit**

Stage only Phase 5 files and commit:

```text
Add CI validation baseline
```

- [x] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.
