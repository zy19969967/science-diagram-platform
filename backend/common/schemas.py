from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TaskType = Literal["text-guided", "object-removal", "shape-guided", "image-outpainting"]


class AssetMeta(BaseModel):
    id: str
    name: str
    category: str
    description: str
    prompt: str
    tags: list[str] = Field(default_factory=list)
    file_name: str
    image_url: str | None = None


class AssetPlacement(BaseModel):
    asset_id: str
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    rotation: float = 0.0


class PlanRequest(BaseModel):
    instruction: str = ""
    selected_asset_id: str | None = None
    preferred_task: TaskType | None = None
    canvas_hints: dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    task: TaskType
    task_prompt: str
    negative_prompt: str = ""
    target_label: str | None = None
    recommended_asset_id: str | None = None
    mask_strategy: str = "user-mask"
    reasoning: str
    warnings: list[str] = Field(default_factory=list)


class SegmentRequest(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    mask_image: str | None = None
    asset_placement: AssetPlacement | None = None
    box: list[int] | None = None


class SegmentResponse(BaseModel):
    mask_image: str
    coverage_ratio: float
    bounding_box: list[int] | None = None


class EvaluationResult(BaseModel):
    changed_ratio: float
    outside_mask_change_ratio: float
    note: str


class GenerateRequest(BaseModel):
    source_image: str
    instruction: str = ""
    task: TaskType | None = None
    mask_image: str | None = None
    selected_asset_id: str | None = None
    asset_placement: AssetPlacement | None = None
    plan: PlanResponse | None = None
    steps: int = Field(default=30, ge=1, le=100)
    guidance_scale: float = Field(default=7.5, ge=0.1, le=30.0)
    fitting_degree: float = Field(default=0.85, ge=0.0, le=1.0)
    seed: int = Field(default=2026, ge=0, le=2147483647)
    negative_prompt: str = ""
    local_files_only: bool = False
    horizontal_expansion_ratio: float = Field(default=1.0, ge=1.0, le=4.0)
    vertical_expansion_ratio: float = Field(default=1.0, ge=1.0, le=4.0)


class PowerPaintGenerateRequest(BaseModel):
    image: str
    mask_image: str
    task: TaskType
    prompt: str
    negative_prompt: str = ""
    steps: int = Field(default=30, ge=1, le=100)
    guidance_scale: float = Field(default=7.5, ge=0.1, le=30.0)
    fitting_degree: float = Field(default=0.85, ge=0.0, le=1.0)
    seed: int = Field(default=2026, ge=0, le=2147483647)
    local_files_only: bool = False
    horizontal_expansion_ratio: float = Field(default=1.0, ge=1.0, le=4.0)
    vertical_expansion_ratio: float = Field(default=1.0, ge=1.0, le=4.0)


class GenerateResponse(BaseModel):
    run_id: str
    plan: PlanResponse
    result_image: str
    evaluation: EvaluationResult
    artifacts: dict[str, str] = Field(default_factory=dict)
