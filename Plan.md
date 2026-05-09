# Qwen-Image Mask Editing Data Pipeline

## Target Pipeline

```text
Frontend
  source_image + raw user mask + instruction + generation_provider
    -> Gateway /api/generate or /api/generation/jobs
    -> planner /plan for task classification and fallback hints
    -> mask normalization from user mask, asset placement, or SAM points
    -> provider-specific prompt construction
       - qwen-image: unified short Chinese prompt from the user instruction
       - powerpaint: legacy planner/inpaint prompt
    -> provider dispatch
       - qwen-image: qwen_image_service /generate
       - powerpaint: powerpaint_service /generate
    -> provider-specific postprocess
    -> evaluation, artifacts, metadata, quality report
    -> frontend result, history, project version, benchmark persistence
```

## Qwen Provider Rules

- Qwen receives the full source image and the normalized user mask.
- Qwen does not receive an expanded execution mask.
- Qwen does not use manual bbox crop, upscale, or paste-back.
- Final Qwen composition uses the raw mask as the only editable alpha boundary.
- Raw mask outside pixels are restored from the input image.
- Qwen prompts are Chinese and short.
- Qwen prompt construction is unified: delete, replace, and redraw are all expressed as the user's direct edit instruction.
- Qwen prompt source is `user-direct` by default.
- Qwen3.5 prompt enhancement is opt-in only with `QWEN_IMAGE_PROMPT_ENHANCER_ENABLED=true`.

## PowerPaint Provider Rules

- PowerPaint keeps its existing prompt and prefill behavior.
- PowerPaint remains available through manual provider selection.
- PowerPaint can keep broader edge blending because it is a separate provider lane.

## Prompt Enhancer Rules

- Gateway first builds a deterministic Chinese Qwen prompt from the user's text.
- Gateway does not call planner `/qwen-edit-prompt` by default.
- If `QWEN_IMAGE_PROMPT_ENHANCER_ENABLED=true`, gateway calls planner `/qwen-edit-prompt` for Qwen3.5 prompt rewriting.
- If the enhancer fails, returns English, reverses the user's Chinese edit action, or introduces known-wrong lab geometry, gateway uses the deterministic fallback prompt.
- The enhancer receives only instruction/task/style/plan hints/fallback prompt; it does not replace the planner or create a new scene.

## Metadata

Every Qwen run should record:

- `provider = qwen-image`
- `pipeline = qwen_image_inpaint`
- `model`
- `model_dtype`
- `provider_prompt`
- `provider_negative_prompt`
- `provider_prompt_source`
- `source_style`
- `qwen_edit_crop_enabled = false`
- `qwen_edit_execution_mask_dilation_radius = 0`
- `qwen_edit_execution_mask_bbox = null`
- `qwen_edit_user_mask_bbox`
- `qwen_edit_user_mask_coverage_ratio`

## Non-Goals For This Iteration

- No automatic mask expansion.
- No mask sufficiency check.
- No multi-target detection or component splitting.
- No provider reroute from Qwen to PowerPaint for photographic edits.
- No separate Qwen delete/replacement prompt branches.
- No frontend workflow redesign.
