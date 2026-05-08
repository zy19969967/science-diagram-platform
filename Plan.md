# Qwen-Image Mask Editing Data Pipeline

## Pipeline

```text
Frontend
  source_image + mask_image + prompt + generation_provider
    -> Gateway /api/generation/jobs or /api/generate
    -> planner decision / plan fallback
    -> mask normalization from user mask, asset placement, or SAM points
    -> provider dispatch
       - qwen-image: qwen_image_service /generate
       - powerpaint: powerpaint_service /generate
    -> provider-specific postprocess
    -> evaluation and quality report
    -> artifacts source.png, mask.png, result.png, metadata.json
    -> frontend result, canvas_state, history, benchmark/project persistence
```

## Provider Rules

- `qwen-image` is the default frontend provider for local masked edits.
- `powerpaint` remains available as a manual provider.
- If the user explicitly selects a provider, the gateway reports that provider's failure clearly instead of silently pretending another provider succeeded.
- Qwen-Image receives the original source image and normalized mask. PowerPaint keeps its current pre-fill and blend path.
- Docker starts Qwen-Image only through the optional `qwen-image` profile so normal deployments are not blocked when the extra 80GB GPU is unavailable.

## Metadata

Every generated run should record:

- `provider`
- `pipeline`
- `model`
- `model_dtype`
- `steps`
- `guidance_scale`
- `true_cfg_scale`
- `strength`
- `mask_coverage`
- `mask_bbox`
- `fallback_used`
- `local_files_only`

## Current Review Fixes

- Per-request `local_files_only=true` must force the first Qwen-Image pipeline load to use local weights.
- Smart generation cancel must call `/api/generation/jobs/{job_id}/cancel`.
- Conda docs must include `run_qwen_image.sh` and port `19086`.

## Deployment Target

- Production/demo target: 2 x H20-NVLink 96GB.
- GPU 0: Qwen-Image, kept dedicated for the 80GB-class masked edit service.
- GPU 1: PowerPaint, planner, segmenter, and FLUX.
