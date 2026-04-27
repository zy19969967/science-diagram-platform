# Tech Report Alignment Design

## Context

The technical report describes a platform with two entry points:

1. Upload an existing scientific diagram and run local, mask-guided edits.
2. Start from pure text, generate an initial canvas, then enter the same edit loop.

The repository already has the upload/edit path, model-first planner and segmenter services, a PowerPaint wrapper, artifact saving, and Docker/Conda deployment scripts. The largest functional gap is the missing pure-text initial canvas path. The report also calls for FLUX, async jobs, Fabric.js layers, OCR/vector text, richer SAM-2 interaction, version trees, evaluation, and CI; these are too large to complete safely in one increment.

## Phased Approach

### Phase 1: Dual-Entry MVP

Add a pure-text creation path that is useful without requiring FLUX weights yet:

- Add scene-plan and init-generation schemas.
- Add deterministic fallback scene planning and candidate image generation.
- Expose `/api/init-plan` and `/api/init-generate` through the gateway.
- Add a front-end path that lets users create candidate initial canvases from text and select one as the source image for the existing PowerPaint edit loop.
- Keep generated candidates as data URLs and include seed/metadata so future FLUX integration can reuse the contract.

This does not claim to be FLUX. It creates the same API and UX shape that a later FLUX service can replace.

### Phase 2: Async Job Skeleton

Introduce `job_id`, task states, and polling for long-running work. Start with in-process state or file-backed state before adding Redis/Celery. Preserve compatibility with synchronous `/api/generate` until the UI is moved.

Phase 2 keeps `/api/generate` intact and adds `POST /api/jobs` plus `GET /api/jobs/{job_id}` for asynchronous generation. The first implementation is intentionally in-process and non-durable; Redis/Celery, cancellation, retries, and multi-worker scheduling are later work.

### Phase 3: Canvas State And Layers

Introduce a serializable canvas state with base image, mask layer, asset layer, and vector text layer. The front end can stay React-first initially; Fabric.js should be added only when the layer model is stable.

Phase 3 stores a `canvas_state` snapshot with generation requests and returns an updated snapshot after generation. The snapshot records layer metadata and artifact references, not a full Fabric.js scene yet. Text layers are represented as editable metadata and rendered as lightweight HTML overlays in the current React editor.

Implemented Phase 3 scope:

- `GenerateRequest` and `GenerateResponse` carry optional `canvas_state`.
- Gateway metadata stores `canvas_state_before` and `canvas_state_after`.
- The front end serializes base image, mask, asset, and text layers before synchronous and asynchronous generation.
- Initial-canvas labels become lightweight React text overlays, and history results restore text layers from returned state.
- Result UI displays the latest returned canvas state source, layer count, and history count.

Explicitly out of scope for Phase 3: Fabric.js editing, persisted project database, branchable version trees, SVG export, and OCR validation.

### Phase 4: Quality And Evaluation

Add richer evaluation records, prompt/model metadata, mask quality fields, and CI. OCR/vector text verification can land here or in a separate focused phase depending on dependency availability.

## Phase 1 Architecture

Phase 1 keeps the current service topology. The gateway owns init endpoints and uses shared common logic for deterministic fallback behavior:

- `backend/common/schemas.py` defines `ScenePlanRequest`, `ScenePlanResponse`, `InitGenerateRequest`, `InitGenerateResponse`, and `InitCandidate`.
- `backend/common/init_logic.py` converts text into a structured scene plan and renders simple scientific diagram candidates with PIL.
- `backend/gateway/main.py` exposes `/api/init-plan` and `/api/init-generate`.
- `frontend/src/App.jsx` manages init prompt, candidates, and candidate selection.
- `frontend/src/components/ControlPanel.jsx` displays text-entry controls for the initial canvas path.
- `frontend/src/components/ResultPanel.jsx` or a small new component displays init candidates.

## Constraints

- Do not remove the existing upload/edit path.
- Do not stage existing untracked Word documents.
- Do not introduce network-required runtime behavior in Phase 1.
- Do not pretend the fallback renderer is FLUX; labels and metadata must identify it as a deterministic fallback.
- Keep the first push scoped to docs plus Phase 1 code and tests.

## Verification

Phase 1 is complete when:

- Unit tests cover deterministic scene planning and candidate generation.
- Gateway import/schema checks pass.
- Frontend build passes.
- Manual code review finds no accidental unrelated changes.
- The phase is committed and pushed to GitHub on the current `codex/report-alignment-phase1` branch.
