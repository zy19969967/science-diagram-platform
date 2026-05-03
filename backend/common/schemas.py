from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TaskType = Literal["text-guided", "object-removal", "shape-guided", "image-outpainting"]
SmartTaskType = Literal[
    "text_to_image",
    "image_variation",
    "local_inpaint",
    "outpainting",
    "svg_or_structure_generation",
]
SmartPipeline = Literal[
    "flux_text_to_image",
    "powerpaint_inpaint",
    "powerpaint_variation",
    "powerpaint_outpaint",
    "svg_structure",
    "needs_user_input",
]
SmartJobStatus = Literal["queued", "planning", "generating", "completed", "failed", "cancelled"]
InitMode = Literal["create_from_text"]
InitGenerationProvider = Literal["auto", "deterministic-fallback", "flux-local", "flux-remote"]
JobStatus = Literal["CREATED", "PLANNING", "SEGMENTING", "EXECUTING", "EVALUATING", "DONE", "FAILED", "CANCELLED"]
CanvasLayerType = Literal["base-image", "mask", "asset", "text", "result", "region-prompt"]
PointPromptLabel = Literal["positive", "negative"]
CanvasSource = Literal["upload", "init-candidate", "history", "generated"]
ProjectVersionKind = Literal["init-candidate", "generate-result", "manual-snapshot"]
TextValidationStatus = Literal["pass", "warn", "fail"]
ReadinessStatus = Literal["pass", "warn", "fail"]
MAX_CANVAS_LAYERS = 64
MAX_CANVAS_STATE_BYTES = 65536
MAX_PROJECT_METADATA_BYTES = 65536
MAX_BENCHMARK_METADATA_BYTES = 65536
CANVAS_METADATA_KEYS = {
    "instruction",
    "task",
    "seed",
    "selected_asset_id",
    "selected_init_candidate_id",
    "init_provider",
    "init_diagram_type",
    "latest_run_id",
    "latest_result_url",
    "latest_mask_url",
    "plan_task",
    "point_prompt_count",
}


def _contains_data_url(value: Any) -> bool:
    if isinstance(value, str):
        return value.lstrip().lower().startswith("data:")
    if isinstance(value, dict):
        return any(_contains_data_url(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_data_url(item) for item in value)
    return False


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


class SegmentPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    label: PointPromptLabel = "positive"


class PlanRequest(BaseModel):
    source_image: str | None = None
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


class SmartGenerationOptions(BaseModel):
    num_outputs: int = Field(default=2, ge=1, le=4)
    task_override: SmartTaskType | None = None
    quality: Literal["draft", "standard", "high"] = "standard"
    seed: int = Field(default=2026, ge=0, le=2147483647)
    steps: int = Field(default=30, ge=1, le=100)
    guidance_scale: float = Field(default=7.5, ge=0.1, le=30.0)


class SmartGenerationRequest(BaseModel):
    prompt: str = ""
    image_id: str | None = None
    mask_id: str | None = None
    source_image: str | None = None
    mask_image: str | None = None
    options: SmartGenerationOptions = Field(default_factory=SmartGenerationOptions)


class SmartPlannerDecision(BaseModel):
    task_type: SmartTaskType
    subtask_type: str = "general"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    need_user_clarification: bool = False
    clarification_question: str = ""
    normalized_prompt: str
    negative_prompt: str = ""
    pipeline: SmartPipeline
    requires_mask: bool = False
    can_auto_segment: bool = False
    preserve_background: bool = True
    preserve_identity: bool = False
    preserve_style: bool = True
    warnings: list[str] = Field(default_factory=list)


class SmartGenerationResultItem(BaseModel):
    image_url: str
    thumbnail_url: str | None = None
    metadata_id: str | None = None
    is_diagnostic_result: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SmartGenerationJobResponse(BaseModel):
    job_id: str
    status: SmartJobStatus
    task_type: SmartTaskType
    message: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    results: list[SmartGenerationResultItem] = Field(default_factory=list)
    planner: SmartPlannerDecision | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    generate_response: Any | None = None


class ScenePlanRequest(BaseModel):
    instruction: str = ""
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=768, ge=256, le=2048)
    style: str = "clean scientific illustration, flat vector-like"
    candidate_count: int = Field(default=3, ge=1, le=4)
    seed: int = Field(default=2026, ge=0, le=2147483647)


class ScenePlanObject(BaseModel):
    id: str
    name: str
    role: str
    position: str
    visual: str


class ScenePlanRelation(BaseModel):
    source: str
    target: str
    type: str = "arrow"


class ScenePlanResponse(BaseModel):
    mode: InitMode = "create_from_text"
    diagram_type: str
    width: int
    height: int
    instruction: str
    objects: list[ScenePlanObject]
    relations: list[ScenePlanRelation] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    style: str
    positive_prompt: str
    negative_prompt: str
    render_text_as_vector: bool = True
    candidate_count: int = Field(default=3, ge=1, le=4)
    seed: int = Field(default=2026, ge=0, le=2147483647)
    provider: str = "deterministic-fallback"
    warnings: list[str] = Field(default_factory=list)


class InitCandidate(BaseModel):
    id: str
    image: str
    seed: int
    provider: str
    score: float
    width: int
    height: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class InitGenerateRequest(BaseModel):
    scene_plan: ScenePlanResponse
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    provider: InitGenerationProvider = "auto"


class InitGenerateResponse(BaseModel):
    provider: str
    scene_plan: ScenePlanResponse
    candidates: list[InitCandidate]
    requested_provider: InitGenerationProvider = "auto"
    used_provider: str | None = None
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)


class CanvasLayer(BaseModel):
    id: str
    type: CanvasLayerType
    name: str
    visible: bool = True
    locked: bool = False
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data")
    @classmethod
    def reject_embedded_data_urls(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_data_url(value):
            raise ValueError("canvas layer data must reference artifacts, not embedded data URLs")
        return value


class CanvasState(BaseModel):
    canvas_id: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source: CanvasSource = "upload"
    layers: list[CanvasLayer] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("layers")
    @classmethod
    def limit_layers(cls, value: list[CanvasLayer]) -> list[CanvasLayer]:
        if len(value) > MAX_CANVAS_LAYERS:
            raise ValueError(f"canvas_state layers cannot exceed {MAX_CANVAS_LAYERS}")
        return value

    @field_validator("metadata", mode="before")
    @classmethod
    def allow_known_metadata_keys(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): item
            for key, item in value.items()
            if str(key) in CANVAS_METADATA_KEYS
        }

    @field_validator("metadata")
    @classmethod
    def reject_metadata_data_urls(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_data_url(value):
            raise ValueError("canvas_state metadata must reference artifacts, not embedded data URLs")
        return value

    @model_validator(mode="after")
    def limit_serialized_size(self) -> "CanvasState":
        serialized = json.dumps(self.model_dump(), ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > MAX_CANVAS_STATE_BYTES:
            raise ValueError(f"canvas_state cannot exceed {MAX_CANVAS_STATE_BYTES} bytes")
        return self


class TextObservation(BaseModel):
    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "provided-ocr"
    bbox: list[float] | None = None


class TextValidationRequest(BaseModel):
    canvas_state: CanvasState
    expected_labels: list[str] = Field(default_factory=list, max_length=128)
    ocr_observations: list[TextObservation] = Field(default_factory=list, max_length=128)
    include_hidden_layers: bool = False


class TextValidationReport(BaseModel):
    status: TextValidationStatus
    source: str
    expected_labels: list[str] = Field(default_factory=list)
    vector_labels: list[str] = Field(default_factory=list)
    ocr_labels: list[str] = Field(default_factory=list)
    matched_labels: list[str] = Field(default_factory=list)
    missing_labels: list[str] = Field(default_factory=list)
    extra_vector_labels: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SvgExportRequest(BaseModel):
    canvas_state: CanvasState
    expected_labels: list[str] = Field(default_factory=list, max_length=128)
    ocr_observations: list[TextObservation] = Field(default_factory=list, max_length=128)
    include_hidden_layers: bool = False
    filename: str = "science-diagram.svg"


class SvgExportResponse(BaseModel):
    svg: str
    mime_type: str = "image/svg+xml"
    filename: str = "science-diagram.svg"
    text_report: TextValidationReport
    warnings: list[str] = Field(default_factory=list)


class SegmentRequest(BaseModel):
    source_image: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    mask_image: str | None = None
    asset_placement: AssetPlacement | None = None
    box: list[int] | None = None
    point_prompts: list[SegmentPoint] = Field(default_factory=list, max_length=32)


class SegmentResponse(BaseModel):
    mask_image: str
    coverage_ratio: float
    bounding_box: list[int] | None = None


class EvaluationResult(BaseModel):
    changed_ratio: float
    outside_mask_change_ratio: float
    note: str
    inside_mask_change_ratio: float = 0.0
    mask_coverage_ratio: float = 0.0
    edit_localization_score: float = 0.0
    preservation_score: float = 0.0


class MaskQualityReport(BaseModel):
    coverage_ratio: float
    area_pixels: int
    bounding_box: list[int] | None = None
    artifact_url: str | None = None


class PromptTrace(BaseModel):
    instruction: str
    task: TaskType
    task_prompt: str
    negative_prompt: str = ""
    selected_asset_id: str | None = None
    seed: int
    planner_source: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class RunQualityReport(BaseModel):
    run_id: str
    quality_version: str = "phase4-v1"
    mask: MaskQualityReport
    prompt: PromptTrace
    evaluation: EvaluationResult
    artifacts: dict[str, str] = Field(default_factory=dict)


class BenchmarkMetricAverages(BaseModel):
    changed_ratio: float = 0.0
    outside_mask_change_ratio: float = 0.0
    inside_mask_change_ratio: float = 0.0
    mask_coverage_ratio: float = 0.0
    edit_localization_score: float = 0.0
    preservation_score: float = 0.0


class BenchmarkRunCreateRequest(BaseModel):
    run_id: str
    project_id: str | None = None
    version_id: str | None = None
    label: str = ""
    scenario: str = ""
    provider: str = "unknown"
    model: str = ""
    task: TaskType | None = None
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    quality_report: RunQualityReport
    text_report: TextValidationReport | None = None
    tags: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("run_id", "project_id", "version_id", "label", "scenario", "provider", "model")
    @classmethod
    def trim_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()[:160]

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        tags = []
        for item in value:
            tag = str(item).strip()[:48]
            if tag and tag not in tags:
                tags.append(tag)
        return tags

    @field_validator("metadata")
    @classmethod
    def reject_benchmark_metadata_data_urls(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_data_url(value):
            raise ValueError("benchmark metadata must reference artifacts, not embedded data URLs")
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > MAX_BENCHMARK_METADATA_BYTES:
            raise ValueError(f"benchmark metadata cannot exceed {MAX_BENCHMARK_METADATA_BYTES} bytes")
        return value

    @field_validator("quality_report", "text_report")
    @classmethod
    def reject_benchmark_report_data_urls(cls, value: Any) -> Any:
        if value is not None and _contains_data_url(value.model_dump()):
            raise ValueError("benchmark reports must reference artifacts, not embedded data URLs")
        return value


class BenchmarkRunSnapshot(BenchmarkRunCreateRequest):
    benchmark_id: str
    created_at: str
    updated_at: str


class BenchmarkProviderSummary(BaseModel):
    provider: str
    run_count: int = 0
    average_metrics: BenchmarkMetricAverages = Field(default_factory=BenchmarkMetricAverages)
    text_pass_rate: float | None = None


class BenchmarkSummaryResponse(BaseModel):
    total_runs: int = 0
    average_metrics: BenchmarkMetricAverages = Field(default_factory=BenchmarkMetricAverages)
    text_pass_rate: float | None = None
    by_provider: list[BenchmarkProviderSummary] = Field(default_factory=list)
    recent_runs: list[BenchmarkRunSnapshot] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GatewayAuthStatus(BaseModel):
    enabled: bool = False
    scheme: str = "Bearer token or X-API-Token"
    protected_paths: list[str] = Field(default_factory=lambda: ["/api/*"])
    exempt_paths: list[str] = Field(default_factory=list)


class DeploymentReadinessCheck(BaseModel):
    name: str
    status: ReadinessStatus
    detail: str


class DeploymentReadinessResponse(BaseModel):
    status: ReadinessStatus
    checked_at: str
    auth: GatewayAuthStatus
    checks: list[DeploymentReadinessCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    source_image: str
    instruction: str = ""
    task: TaskType | None = None
    mask_image: str | None = None
    point_prompts: list[SegmentPoint] = Field(default_factory=list, max_length=32)
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
    canvas_state: CanvasState | None = None
    smart_metadata: dict[str, Any] = Field(default_factory=dict)


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
    canvas_state: CanvasState | None = None
    quality_report: RunQualityReport | None = None


class ProjectCreateRequest(BaseModel):
    name: str = "Untitled science diagram"
    source_image_metadata: dict[str, Any] = Field(default_factory=dict)
    init_plan: dict[str, Any] | None = None
    selected_candidate_id: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        trimmed = value.strip()
        return trimmed[:120] if trimmed else "Untitled science diagram"

    @field_validator("source_image_metadata", "init_plan")
    @classmethod
    def reject_project_data_urls(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if _contains_data_url(value):
            raise ValueError("project metadata must reference artifacts, not embedded data URLs")
        return value


class ProjectVersionCreateRequest(BaseModel):
    kind: ProjectVersionKind = "manual-snapshot"
    parent_version_id: str | None = None
    run_id: str | None = None
    label: str = ""
    canvas_state: CanvasState
    quality_report: RunQualityReport | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    result_image: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("artifacts", "metadata")
    @classmethod
    def reject_version_metadata_data_urls(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_data_url(value):
            raise ValueError("project version metadata must reference artifacts, not embedded data URLs")
        return value

    @field_validator("result_image")
    @classmethod
    def reject_result_image_data_url(cls, value: str | None) -> str | None:
        if value and _contains_data_url(value):
            raise ValueError("project version result_image must reference an artifact URL")
        return value

    @model_validator(mode="after")
    def limit_serialized_metadata_size(self) -> "ProjectVersionCreateRequest":
        if self.kind == "generate-result":
            if not self.run_id:
                raise ValueError("generate-result project versions require run_id")
            if not (self.result_image or self.artifacts.get("result")):
                raise ValueError("generate-result project versions require a result artifact")

        serialized = json.dumps(
            {
                "artifacts": self.artifacts,
                "metadata": self.metadata,
                "quality_report": self.quality_report.model_dump() if self.quality_report else None,
            },
            ensure_ascii=False,
            default=str,
        )
        if len(serialized.encode("utf-8")) > MAX_PROJECT_METADATA_BYTES:
            raise ValueError(f"project version metadata cannot exceed {MAX_PROJECT_METADATA_BYTES} bytes")
        return self


class ProjectVersionSnapshot(ProjectVersionCreateRequest):
    version_id: str
    project_id: str
    created_at: str


class ProjectSnapshot(BaseModel):
    project_id: str
    name: str
    source_image_metadata: dict[str, Any] = Field(default_factory=dict)
    init_plan: dict[str, Any] | None = None
    selected_candidate_id: str | None = None
    latest_version_id: str | None = None
    versions: list[ProjectVersionSnapshot] = Field(default_factory=list)
    created_at: str
    updated_at: str


class JobCreateRequest(BaseModel):
    kind: Literal["generate"] = "generate"
    generate_request: GenerateRequest
    max_attempts: int = Field(default=1, ge=1, le=3)


class JobSnapshot(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(ge=0.0, le=1.0)
    message: str
    result: GenerateResponse | None = None
    error: str | None = None
    created_at: str
    updated_at: str
    attempt: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=1, ge=1, le=3)
    cancel_requested: bool = False
    failure_stage: JobStatus | None = None
