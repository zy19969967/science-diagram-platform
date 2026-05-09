# Qwen-Image Mask Editing Implementation Tasks

## Implemented Changes

### Task 1: Raw Mask Qwen Path

- Qwen request preparation uses the full source image and the normalized user mask.
- Qwen no longer creates or sends an expanded `qwen_execution_mask`.
- Qwen no longer performs manual bbox crop, upscale, or paste-back.
- Qwen final composition uses the raw mask directly, so pixels outside the mask are restored from the input image.
- Crop/execution-mask metadata remains explicit and reports disabled behavior.

### Task 2: Unified Chinese Qwen Prompt

- Qwen prompt construction is independent from PowerPaint.
- Qwen prompt construction is no longer split into delete and replacement templates.
- Qwen fallback prompt is now:

```text
只修改 mask 内区域。{中文直接编辑指令}。未选区保持原图不变。{短风格提示}
```

- Chinese user instructions are preserved directly.
- Common English fallback instructions are converted to concise Chinese when the enhancer is unavailable.
- Known lab-object correction for `锥形瓶` keeps the intended narrow-neck, wide-base geometry.
- Qwen negative prompt defaults to `" "`.
- Automatic Qwen3.5 prompt enhancement is disabled by default; users provide the enhanced prompt themselves.
- `QWEN_IMAGE_PROMPT_ENHANCER_ENABLED=true` can re-enable the old enhancer path for controlled comparison.

### Task 3: Qwen3.5 Prompt Enhancer

- Added `QwenEditPromptRequest` and `QwenEditPromptResponse`.
- Added planner endpoint `/qwen-edit-prompt`.
- Added planner runtime method `enhance_qwen_edit_prompt`.
- The enhancer now asks Qwen3.5 for short Chinese edit instructions.
- The enhancer is instructed to preserve original meaning, action, and count, and not to add long constraints.
- Gateway rejects enhancer output that is not Chinese, reverses the user's Chinese edit action, or contains known-wrong conical-flask geometry.
- Quality reports record `provider_prompt_source`.
- In normal operation, Qwen quality reports now record `provider_prompt_source = user-direct`.

### Task 4: Routing

- Qwen stays on Qwen when selected.
- Scientific diagram deterministic fill remains limited to the PowerPaint provider path.
- PowerPaint provider behavior is unchanged.

### Task 5: Tests

- `backend/tests/test_qwen_image_provider.py` now locks:
  - unified Chinese Qwen prompt wording
  - no separate delete/replacement prompt branch
  - full-image/raw-mask Qwen request
  - raw-mask-only final blending
  - Qwen3.5 Chinese enhancer use
  - enhancer disabled by default
  - fallback when enhancer returns English or reverses the Chinese edit action
  - Qwen provider retention for photographic edits
  - PowerPaint provider compatibility

## Verification Status

- Local syntax compile passed for:
  - `backend/gateway/main.py`
  - `backend/planner/runtime.py`
  - `backend/tests/test_qwen_image_provider.py`

Local dependency-based unit tests cannot run in the local `codex` environment because backend dependencies such as `pydantic` are missing. Run the server tests after syncing.

## Server Verification

```bash
cd /root/autodl-tmp/yzhu/science-diagram-platform
PYTHONPATH=backend /root/miniconda3/bin/conda run --no-capture-output -n sci-gateway python -m unittest backend.tests.test_qwen_image_provider
PYTHONPATH=backend /root/miniconda3/bin/conda run --no-capture-output -n sci-gateway python -m py_compile backend/gateway/main.py backend/planner/runtime.py backend/tests/test_qwen_image_provider.py
```

After passing tests, restart planner and gateway so the updated prompt enhancer and gateway fallback are active.
