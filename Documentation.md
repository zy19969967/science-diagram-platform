# Qwen-Image Mask Editing Documentation Tasks

## User-Facing Documentation

- Update README current capabilities to mention Qwen-Image mask editing.
- Explain provider selection: Qwen-Image default, PowerPaint legacy.
- Explain that Qwen-Image-Edit-2511 is not the primary first-phase mask path.

## Deployment Documentation

- Update Docker deployment instructions with `qwen-image`.
- Document that Docker Qwen-Image uses `--profile qwen-image`.
- Update Conda/tmux deployment instructions with `run_qwen_image.sh`.
- Document `QWEN_IMAGE_*` environment variables.
- State that the recommended deployment uses a dedicated 80GB GPU.
- Document model cache path under `models/huggingface`.

## H20-NVLink 96GB Deployment Update

- Default deployment target is 2 x H20-NVLink 96GB.
- GPU 0 is reserved for Qwen-Image.
- GPU 1 hosts PowerPaint, planner, segmenter, and FLUX.
- Docker startup for the full editing chain should use `--profile qwen-image`.

## Operations Documentation

- Add Qwen-Image health check to service checks.
- Add Qwen-Image to model prewarm.
- Document common failures:
  - insufficient GPU memory
  - model not downloaded
  - Hugging Face access or mirror issue
  - provider selected but service unavailable

## Validation Documentation

- Record the verification commands used after implementation.
- Distinguish unit tests from real GPU smoke tests.
- Note that CI does not run real model inference.

## Prompt Diagnostics

- For Qwen-Image quality issues, inspect `metadata.json -> quality_report.prompt.parameters.provider_prompt`.
- Qwen-Image prompts should say the edit is mask-only, preserve every unmasked part, and keep the scientific diagram style.
- PowerPaint prompts are intentionally different and should remain planner-style inpainting prompts with stronger artifact negatives.
