# Qwen-Image Mask Editing Implementation Tasks

## Task 1: Backend Contracts

- Add generation provider literals for `qwen-image` and `powerpaint`.
- Add `qwen_image_inpaint` to smart pipeline literals.
- Add `generation_provider` to smart generation options and generate requests.
- Add `QwenImageEditRequest`.
- Extend smart metadata and quality prompt parameters with provider and pipeline provenance.

## Task 2: Qwen-Image Service

- Add `backend/qwen_image_service`.
- Implement `/health`.
- Implement `/generate`.
- Load `QwenImageEditInpaintPipeline` lazily from `Qwen/Qwen-Image-Edit`.
- Support env configuration for model repo, dtype, local files, steps, true CFG, strength.
- Use an execution lock around pipeline calls.

## Task 3: Gateway Provider Dispatch

- Add `QWEN_IMAGE_URL`.
- Reuse existing planning and mask normalization.
- Dispatch local masked edits to Qwen-Image or PowerPaint based on `generation_provider`.
- Save artifacts and quality reports through the existing shared path.
- Preserve `/api/generate`, `/api/jobs`, and `/api/generation/jobs` response shapes.

## Task 4: Frontend Provider Selection

- Add provider state with default `qwen-image`.
- Add provider controls to the advanced panel.
- Include `generation_provider` in smart and legacy generate payloads.
- Display provider, pipeline, and model metadata in result/job panels.

## Task 5: Deployment And Docs

- Add Docker Compose `qwen-image` service.
- Keep the Compose `qwen-image` service under an optional profile so gateway can still start without the extra 80GB GPU.
- Add Conda/tmux scripts and env defaults.
- Add prewarm and service health checks.
- Document 80GB GPU requirement, model selection, and non-use of 2511 as primary path.

## Task 6: Verification

- Run backend unit tests.
- Run backend py_compile checks.
- Run frontend helper tests.
- Run frontend build.
- Run whitespace checks.
- Run real model smoke test on 80GB GPU when available.

## Review Fixes

- Qwen-Image runtime now honors request-level `local_files_only` on first load.
- Frontend result panel can cancel both legacy `/api/jobs` and smart `/api/generation/jobs`.
- Documentation now lists Qwen-Image manual Conda startup and the optional Docker profile.

## H20 Deployment Defaults

- `.env.example`, `.env.server.example`, `.env.nodocker.example`, Docker Compose, and Conda defaults now target 2 x H20-NVLink 96GB.
- Default GPU mapping is `qwen-image -> 0` and `powerpaint/planner/segmenter/flux -> 1`.

## Prompt Routing Fixes

- Qwen-Image provider prompts now follow the official prompt-enhancement guidance: keep the original user edit request, make the edit region explicit, and add scientific-diagram preservation constraints.
- PowerPaint keeps the legacy planner/inpaint prompt instead of sharing the Qwen-Image prompt.
- Qwen-Image default negative prompt is intentionally light unless the user supplies a custom negative prompt; PowerPaint keeps the stronger artifact-focused negative prompt.
- Quality reports record `provider_prompt` and `provider_negative_prompt` for debugging generated results.
