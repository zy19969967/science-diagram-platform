from __future__ import annotations

import numpy as np
from PIL import Image

from common.schemas import (
    EvaluationResult,
    GenerateRequest,
    MaskQualityReport,
    PlanResponse,
    PromptTrace,
    RunQualityReport,
)
from common.utils.masks import compute_mask_bbox, coverage_ratio


def build_mask_quality(mask: Image.Image, artifact_url: str | None = None) -> MaskQualityReport:
    mask_arr = np.asarray(mask.convert("L")) > 0
    return MaskQualityReport(
        coverage_ratio=round(coverage_ratio(mask), 4),
        area_pixels=int(mask_arr.sum()),
        bounding_box=compute_mask_bbox(mask),
        artifact_url=artifact_url,
    )


def build_prompt_trace(
    payload: GenerateRequest,
    plan: PlanResponse,
    *,
    planner_source: str,
) -> PromptTrace:
    return PromptTrace(
        instruction=payload.instruction,
        task=payload.task or plan.task,
        task_prompt=plan.task_prompt,
        negative_prompt=payload.negative_prompt or plan.negative_prompt,
        selected_asset_id=payload.selected_asset_id,
        seed=payload.seed,
        planner_source=planner_source,
        parameters={
            "provider": payload.generation_provider,
            "steps": payload.steps,
            "guidance_scale": payload.guidance_scale,
            "true_cfg_scale": payload.true_cfg_scale,
            "strength": payload.strength,
            "fitting_degree": payload.fitting_degree,
            "local_files_only": payload.local_files_only,
            "horizontal_expansion_ratio": payload.horizontal_expansion_ratio,
            "vertical_expansion_ratio": payload.vertical_expansion_ratio,
        },
    )


def build_quality_report(
    *,
    run_id: str,
    payload: GenerateRequest,
    plan: PlanResponse,
    mask: Image.Image,
    evaluation: EvaluationResult,
    artifacts: dict[str, str],
    planner_source: str,
) -> RunQualityReport:
    return RunQualityReport(
        run_id=run_id,
        mask=build_mask_quality(mask, artifacts.get("mask")),
        prompt=build_prompt_trace(payload, plan, planner_source=planner_source),
        evaluation=evaluation,
        artifacts=artifacts,
    )
