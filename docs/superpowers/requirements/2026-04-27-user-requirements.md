# User Requirements Log

## 2026-04-27

User asked to align the project with `tech_report_v7_enhanced.docx` and the repository analysis.

Persistent requirements:

- Read and preserve the technical report alignment context.
- Save task documents and development plans locally so future conversations can resume without relying on chat memory.
- Implement in phases if one conversation cannot finish the full report alignment.
- After each completed phase:
  - review the code changes,
  - run relevant verification,
  - commit the scoped changes,
  - push to GitHub,
  - update or create a pull request.
- Do not silently include unrelated local files such as Word documents in commits.
- Subagents may be used for review or parallel analysis when useful.

Current implementation path:

- Phase 1 completed: dual-entry MVP with deterministic fallback initial-canvas candidates.
- Phase 2 completed in the current branch after Phase 1: async job skeleton with `job_id`, status polling, and front-end progress display while preserving synchronous `/api/generate`.
- Phase 3 completed in the current branch after Phase 2: serializable `canvas_state` with base image, mask, asset, and text layer metadata, plus React-first lightweight text overlays and returned state summaries. This intentionally does not claim full Fabric.js editing, project persistence, branchable versions, SVG export, or OCR validation yet.
- Phase 4 completed in the current branch after Phase 3: runtime `quality_report`, richer evaluation fields, mask quality metadata, prompt/provenance trace, metadata persistence, and result-panel display. CI, OCR validation, persistent benchmark dashboards, and dataset-level evaluation remain later phases.
- Full remaining roadmap is now captured in `docs/superpowers/specs/2026-04-27-tech-report-alignment-design.md`: CI, project persistence/version tree, durable async jobs, Fabric.js layers, richer SAM-2 interaction, OCR/vector text/SVG export, FLUX service, benchmark dashboard, and auth/deployment traceability.
- Phase 5 completed in the current branch after Phase 4: GitHub Actions CI validation baseline for backend unit tests/import checks, frontend helper tests/build, and diff hygiene without model-weight or GPU requirements.
- Phase 6 completed in the current branch after Phase 5: lightweight single-user project persistence with JSON-backed project snapshots, parent-linked versions, source/init metadata, canvas states, artifacts, and quality reports. This intentionally does not claim multi-user auth, database migrations, durable async queue state, full Fabric.js editing, or raw initial-candidate image persistence yet.
- Phase 7 completed in the current branch after Phase 6: durable file-backed async job snapshots under `JOBS_DIR`, restart recovery for terminal/interrupted jobs, cancellation endpoint and front-end cancel action, attempt metadata, and CI/Docker configuration for job state. This intentionally does not claim Redis/Celery, a separate worker service, multi-worker scheduling, cross-instance coordination, or hard interruption of in-flight model calls yet.
- Phase 8 completed in the current branch after Phase 7: first Fabric.js-backed layer editor slice with layer mode, base/mask/asset/text layer panel, visibility/lock/order metadata, Fabric asset/text transforms that write back to `canvas_state`, and frontend tests for layer ordering. This intentionally does not claim full Fabric scene JSON persistence, SVG/PPT export, OCR reconciliation, grouping, snapping, or complete vector export validation yet.
- Phase 9 completed in the current branch after Phase 8: normalized positive/negative SAM point prompts in backend schemas, segment fallback, SAM2.1 runtime inputs, gateway generate requests, front-end point modes, removable point markers, and `canvas_state` region-prompt provenance. This intentionally does not claim automatic text grounding, multi-mask candidate selection, instance segmentation lists, click history branching, or advanced refinement scoring UI yet.
- Phase 10 completed in the current branch after Phase 9: OCR-ready text reconciliation contracts, backend SVG export from `canvas_state`, frontend text validation/export actions, editable SVG `<text>` output for vector text layers, and CI coverage for export helpers. This intentionally does not claim an embedded OCR engine, bitmap text recognition without supplied OCR observations, PPTX export, full Fabric scene JSON persistence, or full raster-to-vector conversion yet.
- Phase 11 completed in the current branch after Phase 10: configurable FLUX-compatible remote initial-canvas provider via `FLUX_INIT_URL`, provider selection in `InitGenerateRequest`, candidate scoring/reranking, explicit fallback policy, and frontend provider/score display. This intentionally does not claim bundled FLUX weights, a local GPU model server, high-resolution async init regeneration, or durable initial-candidate artifact storage yet.
- Phase 12 completed in the current branch after Phase 11: file-backed benchmark run ledger under `BENCHMARKS_DIR`, `/api/benchmarks/runs` and `/api/benchmarks/summary`, aggregate quality/text/provider summaries, front-end experiment dashboard, and explicit "Record run" action. This intentionally does not claim dataset runner automation, human preference annotation, embedded OCR execution, model-version scheduling, or full CSV/report export yet.
