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
            instruction="画一个酶促反应示意图，包含底物、酶、产物和箭头",
            style="flat-vector",
            candidate_count=2,
        )
    )

    assert plan.mode == "create_from_text"
    assert plan.candidate_count == 2
    assert "底物" in plan.labels
    assert "酶" in plan.labels
    assert "产物" in plan.labels
    assert "arrow" in plan.positive_prompt.lower()


def test_init_candidates_are_deterministic_and_image_data_urls():
    plan = build_scene_plan(
        ScenePlanRequest(
            instruction="画一个酶促反应示意图，包含底物、酶、产物和箭头",
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

Add a “无图生成初图” button to `ControlPanel.jsx`, disabled while initializing. Use the existing instruction text as the prompt to avoid duplicating input fields.

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

Add an “异步生成” button next to the existing synchronous PowerPaint button. Keep the existing button so users can compare both flows during development.

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

- [ ] **Step 4: Commit**

Stage only Phase 3 files and commit:

```text
Add serializable canvas state layers
```

- [ ] **Step 5: Push**

Push `codex/report-alignment-phase1` and update PR #2 with the new commit.
