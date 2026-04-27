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
