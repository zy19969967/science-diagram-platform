# Qwen-Image Mask Editing Documentation

## Operator Summary

Qwen-Image is the default provider for local masked edits. It receives the full input image and the user's normalized mask. The gateway does not expand the mask or crop the bbox before sending the request.

## User-Facing Behavior

- The user mask defines the editable region.
- Qwen receives a short Chinese instruction.
- Qwen3.5 automatic prompt enhancement is disabled by default; users can write more detailed prompts themselves.
- Delete, replace, repaint, and redraw are not treated as separate Qwen prompt templates; the system preserves the user's direct wording.
- Pixels outside the mask are restored from the source image.
- If a user draws too small a mask, the system will not silently edit outside the mask.
- PowerPaint remains available as a separate manual provider.

## Provider Differences

Qwen-Image:

- full source image
- raw normalized mask
- no manual crop/upscale/paste-back
- raw-mask-only final composition
- short Chinese prompt
- optional Qwen3.5 Chinese prompt enhancer, disabled by default
- light default negative prompt

PowerPaint:

- legacy planner/inpaint prompt
- existing prefill and edge-blend behavior
- available as a manual provider

## Prompt Debugging

For a generated run, inspect:

```text
metadata.json
  -> quality_report.prompt.parameters.provider_prompt
  -> quality_report.prompt.parameters.provider_negative_prompt
  -> quality_report.prompt.parameters.provider_prompt_source
  -> quality_report.prompt.parameters.source_style
```

Expected prompt sources:

- `user-direct`: default Qwen path; gateway used the user's prompt with minimal Chinese mask/style wrapping.
- `qwen3.5-enhancer`: optional path; planner service rewrote the Qwen prompt in Chinese.
- `gateway-fallback`: planner enhancer was unavailable, returned English, reversed the user's Chinese edit action, or returned invalid prompt text; gateway used deterministic Chinese fallback.
- `planner`: non-Qwen provider prompt path.

## Common Failure Modes

- If old English prompt behavior appears, restart both planner and gateway. The planner endpoint is `/qwen-edit-prompt`.
- If Qwen still generates sticker-like content on photos, inspect whether the prompt is short Chinese and includes the photographic style sentence.
- If source fragments remain outside the edited area, check whether the user's mask covered those pixels. The system does not modify pixels outside the mask.
- If the prompt mentions a wrong conical-flask shape or reverses the user's action, check whether `provider_prompt_source` fell back to `gateway-fallback`.
- If `provider_prompt_source` is `qwen3.5-enhancer` unexpectedly, check whether `QWEN_IMAGE_PROMPT_ENHANCER_ENABLED=true` is set.

## Verification Commands

On the server:

```bash
cd /root/autodl-tmp/yzhu/science-diagram-platform
PYTHONPATH=backend /root/miniconda3/bin/conda run --no-capture-output -n sci-gateway python -m unittest backend.tests.test_qwen_image_provider
PYTHONPATH=backend /root/miniconda3/bin/conda run --no-capture-output -n sci-gateway python -m py_compile backend/gateway/main.py backend/planner/runtime.py backend/tests/test_qwen_image_provider.py
```

Real-image validation should include:

- scientific diagram edit: `把烧杯变成锥形瓶`
- photographic edit: `把杯子变成玻璃杯`
- photographic edit: `删除选区里的杯子`
