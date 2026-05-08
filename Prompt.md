# Qwen-Image Mask Editing Prompt

## Background

PowerPaint is currently the local image-editing base model for masked edits, but its base model is biased toward photorealistic images. For scientific diagrams this creates weak local edits, unstable edges, and poor diagram/text consistency.

## Locked Decisions

- Add a second local image-editing execution path using mask + Qwen-Image.
- First implementation target: `Qwen/Qwen-Image-Edit` with Diffusers `QwenImageEditInpaintPipeline`.
- Do not make `Qwen-Image-Edit-2511` the primary path in this phase because its common Plus pipeline path is not the stable mask-native inpaint interface.
- Target hardware: one dedicated 80GB GPU for the Qwen-Image service.
- Frontend provider control is manual: default `qwen-image`, legacy option `powerpaint`.
- Gateway must keep the existing plan, mask normalization, artifacts, evaluation, quality report, canvas state, project version, and benchmark flow.
- Qwen-Image prompts must be enhanced separately from PowerPaint prompts. They should preserve the user's original request, explicitly restrict edits to the mask, and emphasize unchanged scientific-diagram structure outside the mask.

## Non-Goals

- No 24GB low-VRAM quantized mode in the first implementation.
- No external Qwen API provider.
- No removal of PowerPaint.
- No rewrite of the existing editor or async job system.
