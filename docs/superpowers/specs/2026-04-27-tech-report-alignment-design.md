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

Phase 4 first ships the runtime quality-report slice before adding CI:

- Extend `EvaluationResult` with inside-mask change, mask coverage, edit-localization score, and preservation score.
- Add a `quality_report` object to `GenerateResponse` and async job results.
- Save mask quality and prompt/provenance metadata into `metadata.json` for each run.
- Show the richer metrics in the current React result panel.

Explicitly out of scope for this slice: CI pipelines, OCR validation, human preference scoring, dataset-level benchmark aggregation, and persistent experiment dashboards.

## Remaining Completion Roadmap

The rest of the report alignment should continue as reviewable phases. Each phase must keep the existing upload/edit path working, update this design and the implementation plan, run verification, request code review when useful, and push a scoped commit.

### Phase 5: CI Validation Baseline

Add GitHub Actions to run the current backend unit tests, Python import checks, frontend helper tests, frontend build, and diff hygiene on every pull request and push to the report-alignment branch. This phase does not install model weights or run GPU inference.

### Phase 6: Project Persistence And Version Tree

Add a lightweight persisted project/session layer that stores source image metadata, selected initial candidates, run ids, canvas states, quality reports, and parent-child version lineage. Start with file-backed JSON or SQLite before adding multi-user database concerns.

Implemented Phase 6 scope:

- `backend/gateway/projects.py` provides a file-backed JSON `ProjectStore`.
- The gateway exposes `GET /api/projects`, `POST /api/projects`, `GET /api/projects/{project_id}`, and `POST /api/projects/{project_id}/versions`.
- Project versions store parent version ids, run ids, canvas states, artifact URLs, and optional `quality_report` records.
- The front end can save the current workspace as a project version, refresh saved projects, and load persisted generated versions back into the editor.

Explicitly out of scope for Phase 6: multi-user auth, database migrations, Redis/Celery job durability, full Fabric.js editing, and durable raw storage for initial-candidate data URLs.

### Phase 7: Durable Async Jobs

Move the Phase 2 in-process job store toward durable status reads while keeping `/api/jobs` compatible. Start with file-backed snapshots, cancellation, retry metadata, and failure provenance before introducing Redis/Celery or a separate worker process.

Implemented Phase 7 scope:

- `JobStore` now supports a file-backed mode rooted at `JOBS_DIR`, with one atomic JSON snapshot per job.
- The gateway initializes durable job state from `JOBS_DIR`, so terminal job status and results remain readable after restart.
- Active non-terminal jobs found during startup are marked `FAILED` with `failure_stage` and an interruption error instead of disappearing silently.
- `JobSnapshot` includes `attempt`, `max_attempts`, `cancel_requested`, and `failure_stage` metadata while preserving the existing polling fields.
- `POST /api/jobs/{job_id}/cancel` records cancellation, and the front end can cancel the currently tracked async job.
- Docker Compose mounts `./data/jobs` and CI sets `JOBS_DIR` for backend tests/import checks.

Explicitly out of scope for Phase 7: Redis/Celery, a separate worker process, multi-worker scheduling, cross-instance locking, and hard interruption of a model call that is already executing. Cancellation is cooperative at gateway progress checkpoints.

### Phase 8: Fabric.js Layer Editor

Move from React-only overlays to a real layer editor with selectable/lockable/reorderable base, mask, asset, and text layers. Keep the Phase 3 `canvas_state` contract as the serialization boundary.

Implemented Phase 8 scope:

- The front end now depends on Fabric.js and renders the editable canvas through a Fabric canvas for base image, asset, and text objects.
- A layer mode separates Fabric selection from brush/erase mask painting, so existing mask drawing remains available.
- The editor shows base, mask, asset, and text layers with active selection, visibility toggles, lock toggles, and non-base layer reordering.
- Fabric object modifications write asset placement and text positions/font size back into React state before generation, project save, or history continuation.
- `canvas_state.layers` now preserves layer order plus visibility/lock/opacity metadata for generated and saved snapshots.

Explicitly out of scope for Phase 8: full Fabric scene JSON persistence, complex grouping, SVG/PPT export, OCR reconciliation, vector text export guarantees, and rich alignment/snapping tools.

### Phase 9: Rich SAM-2 Interaction

Add positive/negative point prompts, multi-click refinement, and explicit box/point provenance. Preserve the current box-derived fallback so existing brush and asset placement workflows still work.

Implemented Phase 9 scope:

- `SegmentRequest` and `GenerateRequest` now accept normalized positive/negative SAM point prompts.
- The SAM2.1 runtime converts normalized point prompts into pixel `input_points` and `input_labels` while retaining the existing box/mask/asset prompt path.
- The deterministic segment fallback can build a rough mask from positive points and carve negative points when SAM is unavailable.
- The front end adds positive-point and negative-point canvas modes, renders removable point markers, and allows point-only generation without painted mask pixels.
- `canvas_state` stores point prompt provenance in a `region-prompt` layer and records `point_prompt_count` metadata.

Explicitly out of scope for Phase 9: multi-mask candidate selection, automatic text-to-region grounding, instance segmentation lists, prompt history branching, and advanced SAM click refinement scoring UI.

### Phase 10: OCR, Vector Text, And SVG Export

Add OCR validation for generated labels, vector text layer reconciliation, and SVG/PPT-ready export paths. This should build on the layer editor and not treat bitmap fallback text as editable vector text.

Implemented Phase 10 scope:

- The backend exposes `/api/canvas/validate-text` for deterministic text reconciliation from `canvas_state` vector text layers and optional caller-supplied OCR observations.
- The backend exposes `/api/canvas/export-svg` and serializes visible base, asset, and text layers into SVG while preserving text layers as editable `<text>` elements.
- SVG export emits explicit warnings for embedded bitmap-only sources, raster masks, and SAM prompt provenance layers that cannot be represented as editable SVG geometry.
- The front end can validate current canvas text from a freshly built `canvas_state`, export SVG, show matched/missing labels and warnings, and download the returned SVG.
- CI now runs backend export tests and the frontend export helper test.

Explicitly out of scope for Phase 10: running a real OCR model in the gateway, validating bitmap-only text without supplied OCR observations, PPTX export, full Fabric scene JSON persistence, and complete vectorization of raster PowerPaint outputs.

### Phase 11: FLUX Initial Canvas Service

Replace the deterministic fallback with a real initial-canvas generation service, candidate scoring, low-resolution previews, and high-resolution async regeneration. Keep the existing `/api/init-plan` and `/api/init-generate` contracts stable.

Implemented Phase 11 scope:

- `InitGenerateRequest` initially supported provider selection with default `auto`, explicit `deterministic-fallback`, and explicit `flux-remote`; the post-Phase 13 correction adds explicit `flux-local`.
- The gateway can call a FLUX-compatible initial-canvas service configured by `FLUX_INIT_URL` while keeping `/api/init-generate` stable.
- `auto` mode uses the configured provider when available and falls back to deterministic candidates when it is missing or unavailable. Explicit `flux-local` or `flux-remote` fails clearly instead of silently downgrading.
- Initial candidates are scored and reranked using model score, label coverage, diagram-type match, and provider source metadata.
- The front end displays requested/used provider, fallback state, warnings, candidate rank, score, provider source, and label coverage.

Original Phase 11 out of scope before the local correction: bundling FLUX weights, running a local GPU FLUX service inside this repository, high-resolution async regeneration, and persistent candidate artifact storage beyond the existing init candidate data URLs.

### Post-Phase 13 Local FLUX Deployment Correction

- `InitGenerateRequest.provider` now also supports explicit `flux-local`.
- `backend/flux_service` provides a local FastAPI service with `GET /health` and `POST /generate`, loading `FLUX_MODEL_REPO` through diffusers only when generation is requested.
- Docker Compose now runs a local `flux` service and defaults `FLUX_INIT_URL` to `http://flux:8004`; the no-Docker path adds `CONDA_ENV_FLUX`, `scripts/run_flux.sh`, tmux startup, GPU checks, and service checks.
- Remote FLUX remains compatible through `FLUX_INIT_URL` and `flux-remote`, but the documented default deployment path is local FLUX.
- This still does not bundle model weights, solve model licensing, guarantee the configured model exists in cache, or implement high-resolution async regeneration.

### Phase 12: Benchmark And Experiment Dashboard

Aggregate `quality_report` records across runs into dataset-level metrics, model/prompt comparisons, and exportable experiment summaries. This phase turns Phase 4 per-run records into report-ready evaluation evidence.

Implemented Phase 12 scope:

- `BenchmarkRunCreateRequest` records a generated run, its `quality_report`, optional text validation report, provider/model metadata, project/version ids, seed, tags, and compact metadata.
- `backend/gateway/benchmarks.py` provides a file-backed JSON `BenchmarkStore` rooted at `BENCHMARKS_DIR`, with one atomic snapshot per recorded run.
- The gateway exposes `POST /api/benchmarks/runs`, `GET /api/benchmarks/runs`, and `GET /api/benchmarks/summary`.
- Benchmark summary aggregation computes total runs, average change/localization/preservation/mask metrics, text pass rate when text reports are present, provider-level summaries, recent runs, and empty-ledger warnings.
- The front end adds an explicit experiment ledger panel with record/refresh actions, overall summary metrics, provider comparison rows, and recent run rows. Recording is explicit and does not alter synchronous or async generation behavior.
- Docker Compose, environment examples, and CI include `BENCHMARKS_DIR`, backend benchmark tests, module import/compile checks, and the frontend benchmark helper test.

Explicitly out of scope for Phase 12: automatic dataset runners, human preference annotation, embedded OCR execution, GPU inference benchmarking, model-version experiment scheduling, CSV/PDF report export, and auth-protected multi-user experiment management.

### Phase 13: Auth, Deployment Hardening, And Final Report Traceability

Add access control, deployment smoke checks, production configuration validation, and a final traceability matrix mapping report claims to implemented code paths, tests, and known limitations.

Implemented Phase 13 scope:

- The gateway supports optional single-token API protection through `GATEWAY_API_TOKEN`. When unset, local development behavior remains open; when set, non-exempt `/api/*` routes require `Authorization: Bearer <token>` or `X-API-Token`.
- `/api/health`, static assets/artifacts, API docs, and CORS preflight remain exempt so health checks and static serving do not require secrets.
- `/api/deployment/readiness` returns read-only local checks for auth configuration, storage directories, service URL configuration, asset directory availability, and the traceability matrix file.
- The front end can include `VITE_API_TOKEN` in API requests through a shared `apiFetch` helper while leaving non-API artifact reads unchanged.
- `docs/report-traceability.md` maps Phase 1 through Phase 13 claims to concrete code paths, tests, and known limitations.
- CI compiles/imports the security and deployment modules and runs the frontend API client helper test.

Explicitly out of scope for Phase 13: multi-user login, role-based permissions, token rotation, external model uptime probes, Docker/GPU smoke tests, centralized observability, and production secret management.

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
