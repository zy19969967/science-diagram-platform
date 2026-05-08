from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Callable

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageFilter

from common.assets import asset_catalog_with_urls
from common.canvas_state import build_canvas_state_after_generate
from common.export_logic import build_svg_export, build_text_validation_report
from common.generation_logic import build_smart_generation_plan, smart_metadata
from common.init_logic import build_scene_plan
from common.planner_logic import build_plan
from common.quality import build_quality_report
from common.schemas import (
    BenchmarkRunCreateRequest,
    BenchmarkRunSnapshot,
    BenchmarkSummaryResponse,
    DeploymentReadinessResponse,
    GenerateRequest,
    GenerateResponse,
    InitGenerateRequest,
    InitGenerateResponse,
    JobCreateRequest,
    JobSnapshot,
    JobStatus,
    PlanRequest,
    PlanResponse,
    PowerPaintGenerateRequest,
    ProjectCreateRequest,
    ProjectSnapshot,
    ProjectVersionCreateRequest,
    QwenImageEditRequest,
    ScenePlanRequest,
    ScenePlanResponse,
    SegmentRequest,
    SegmentResponse,
    SmartGenerationJobResponse,
    SmartGenerationRequest,
    SmartGenerationResultItem,
    SmartPlannerDecision,
    SvgExportRequest,
    SvgExportResponse,
    TextValidationReport,
    TextValidationRequest,
)
from common.segment_logic import build_segment
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url
from common.utils.masks import blend_with_mask, blur_mask, dilate_mask, evaluate_edit

from .benchmarks import BenchmarkStore
from .deployment import build_deployment_readiness
from .jobs import JobCancelled, JobStore
from .init_provider import InitProviderError, generate_initial_candidates
from .projects import ProjectStore
from .security import GatewayAuthConfig, request_is_authorized

PLANNER_URL = os.getenv("PLANNER_URL", "http://127.0.0.1:19081")
SEGMENTER_URL = os.getenv("SEGMENTER_URL", "http://127.0.0.1:19083")
POWERPAINT_URL = os.getenv("POWERPAINT_URL", "http://127.0.0.1:19082")
QWEN_IMAGE_URL = os.getenv("QWEN_IMAGE_URL", "http://127.0.0.1:19086")
RUNS_DIR = Path(os.getenv("RUNS_DIR", "/app/data/runs"))
PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", str(RUNS_DIR.parent / "projects")))
JOBS_DIR = Path(os.getenv("JOBS_DIR", str(RUNS_DIR.parent / "jobs")))
BENCHMARKS_DIR = Path(os.getenv("BENCHMARKS_DIR", str(RUNS_DIR.parent / "benchmarks")))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "/app/assets"))
FLUX_INIT_URL = os.getenv("FLUX_INIT_URL", "http://127.0.0.1:19085")
GATEWAY_API_TOKEN = os.getenv("GATEWAY_API_TOKEN", "")

RUNS_DIR.mkdir(parents=True, exist_ok=True)
job_store = JobStore(JOBS_DIR)
project_store = ProjectStore(PROJECTS_DIR)
benchmark_store = BenchmarkStore(BENCHMARKS_DIR)
gateway_auth = GatewayAuthConfig(GATEWAY_API_TOKEN)
smart_job_metadata: dict[str, dict] = {}
smart_job_plans: dict[str, SmartPlannerDecision] = {}

app = FastAPI(title="Science Diagram Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/artifacts", StaticFiles(directory=RUNS_DIR), name="artifacts")


@app.middleware("http")
async def gateway_auth_middleware(request: Request, call_next):
    if not request_is_authorized(request, gateway_auth):
        return JSONResponse(status_code=401, content={"detail": "Gateway API token is required."})
    return await call_next(request)


async def post_json(url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def current_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


ProgressCallback = Callable[[JobStatus, float, str], None]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway"}


@app.get("/api/deployment/readiness", response_model=DeploymentReadinessResponse)
def deployment_readiness() -> DeploymentReadinessResponse:
    repo_root = Path(__file__).resolve().parents[2]
    return build_deployment_readiness(
        auth=gateway_auth.status(),
        storage_dirs={
            "runs_dir": RUNS_DIR,
            "projects_dir": PROJECTS_DIR,
            "jobs_dir": JOBS_DIR,
            "benchmarks_dir": BENCHMARKS_DIR,
        },
        service_urls={
            "planner_url": PLANNER_URL,
            "segmenter_url": SEGMENTER_URL,
            "powerpaint_url": POWERPAINT_URL,
            "qwen_image_url": QWEN_IMAGE_URL,
            "flux_init_url": FLUX_INIT_URL,
        },
        assets_dir=ASSETS_DIR,
        traceability_path=repo_root / "docs" / "report-traceability.md",
    )


@app.get("/api/assets")
def assets(request: Request) -> list[dict]:
    return [asset.model_dump() for asset in asset_catalog_with_urls(current_base_url(request))]


@app.post("/api/plan", response_model=PlanResponse)
async def plan(payload: PlanRequest) -> PlanResponse:
    try:
        data = await post_json(f"{PLANNER_URL}/plan", payload.model_dump())
        return PlanResponse.model_validate(data)
    except Exception:
        return build_plan(payload)


@app.post("/api/init-plan", response_model=ScenePlanResponse)
async def init_plan(payload: ScenePlanRequest) -> ScenePlanResponse:
    try:
        data = await post_json(f"{PLANNER_URL}/init-plan", payload.model_dump())
        return ScenePlanResponse.model_validate(data)
    except Exception:
        return build_scene_plan(payload)


@app.post("/api/init-generate", response_model=InitGenerateResponse)
async def init_generate(payload: InitGenerateRequest) -> InitGenerateResponse:
    try:
        return await generate_initial_candidates(payload, flux_init_url=FLUX_INIT_URL)
    except InitProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _smart_failure_response(
    *,
    decision: SmartPlannerDecision,
    message: str,
    error: str,
    metadata: dict,
) -> SmartGenerationJobResponse:
    return SmartGenerationJobResponse(
        job_id=uuid.uuid4().hex[:12],
        status="failed",
        task_type=decision.task_type,
        message=message,
        progress=1.0,
        planner=decision,
        metadata=metadata,
        error=error,
    )


def _smart_result_from_generate_response(result: GenerateResponse, metadata: dict) -> SmartGenerationResultItem:
    return SmartGenerationResultItem(
        image_url=result.result_image,
        thumbnail_url=result.artifacts.get("result"),
        metadata_id=result.run_id,
        is_diagnostic_result=bool(metadata.get("is_diagnostic_result")),
        metadata=metadata,
    )


def _smart_response_from_job(snapshot: JobSnapshot) -> SmartGenerationJobResponse:
    metadata = smart_job_metadata.get(snapshot.job_id, {})
    decision = smart_job_plans.get(snapshot.job_id)
    task_type = decision.task_type if decision else metadata.get("task_type", "local_inpaint")
    status_map = {
        "CREATED": "queued",
        "PLANNING": "planning",
        "SEGMENTING": "generating",
        "EXECUTING": "generating",
        "EVALUATING": "generating",
        "DONE": "completed",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
    }
    results = []
    if snapshot.result:
        results.append(_smart_result_from_generate_response(snapshot.result, metadata))
    return SmartGenerationJobResponse(
        job_id=snapshot.job_id,
        status=status_map.get(snapshot.status, "failed"),
        task_type=task_type,
        message=snapshot.error or snapshot.message,
        progress=snapshot.progress,
        results=results,
        planner=decision,
        metadata=metadata,
        error=snapshot.error,
        generate_response=snapshot.result.model_dump() if snapshot.result else None,
    )


def _legacy_task_for_decision(decision: SmartPlannerDecision) -> str:
    if decision.task_type == "outpainting":
        return "image-outpainting"
    if decision.subtask_type == "object_removal":
        return "object-removal"
    if decision.subtask_type == "object_replacement":
        return "text-guided"
    if decision.subtask_type in {"background_edit", "color_change", "attribute_edit", "repair"}:
        return "text-guided"
    if decision.task_type == "text_to_image":
        return "text-guided"
    if decision.task_type == "image_variation":
        return "text-guided"
    return "text-guided"


def _provider_for_smart_decision(payload: SmartGenerationRequest, decision: SmartPlannerDecision) -> str:
    if decision.task_type == "text_to_image":
        return "flux-local"
    if decision.task_type == "local_inpaint" and decision.pipeline == "qwen_image_inpaint":
        return payload.options.generation_provider
    return "powerpaint"


def _fitting_for_task(task: str | None) -> float:
    if task == "object-removal":
        return 0.75
    if task == "shape-guided":
        return 0.95
    if task == "image-outpainting":
        return 0.8
    return 0.85


def _scale_for_task(task: str | None) -> float:
    if task in {"object-removal", "image-outpainting"}:
        return 12.0
    if task == "shape-guided":
        return 7.5
    return 7.5


QWEN_IMAGE_DEFAULT_NEGATIVE_PROMPT = " "

QWEN_IMAGE_SCIENCE_STYLE_PROMPT = (
    "Preserve the clean scientific diagram style: white background, flat vector-like drawing, "
    "crisp thin gray or black outlines, simple translucent cyan liquid when present, no shadows, "
    "no photographic texture."
)

QWEN_IMAGE_TERM_HINTS = (
    ("锥形瓶", "Erlenmeyer flask / conical flask"),
    ("烧杯", "beaker"),
    ("玻璃棒", "glass rod"),
    ("漏斗", "funnel"),
    ("试管", "test tube"),
    ("支架", "lab stand"),
    ("铁架台", "lab stand"),
    ("倾斜", "tilted"),
    ("平行", "parallel"),
    ("垂直", "perpendicular"),
)


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _qwen_term_hints(text: str) -> str:
    hints = [f"{source}: {target}" for source, target in QWEN_IMAGE_TERM_HINTS if source in text]
    return ", ".join(hints)


def _qwen_image_edit_prompt(*, instruction: str, plan_prompt: str, task: str | None) -> str:
    user_instruction = instruction.strip()
    planner_prompt = plan_prompt.strip()
    edit_target = _first_nonempty(user_instruction, planner_prompt, "edit the masked object")

    if task == "object-removal":
        action = "Remove the masked object and fill the masked region with clean white diagram background."
    else:
        action = f"User edit instruction: {edit_target}."
        if planner_prompt and planner_prompt != user_instruction and user_instruction:
            action = f"{action} Visual target from planner: {planner_prompt}."

    parts = [
        "Edit only the masked region.",
        action,
        "Keep every unmasked part of the source image unchanged, including the support stand, glass rod, funnel, beaker, liquid level, line thickness, and white background.",
        QWEN_IMAGE_SCIENCE_STYLE_PROMPT,
        "Make the replacement match the existing diagram perspective, scale, geometry, and line weight.",
    ]
    hints = _qwen_term_hints(user_instruction)
    if hints:
        parts.insert(2, f"Recognize these requested lab objects and relations: {hints}.")
    if "平行" in user_instruction:
        parts.append("If parallel alignment is requested, align the replacement object's main axis parallel to the referenced object.")
    return " ".join(parts)


def _provider_edit_prompts(
    *,
    provider: str,
    instruction: str,
    plan_prompt: str,
    request_negative_prompt: str,
    plan_negative_prompt: str,
    task: str | None,
) -> tuple[str, str]:
    if provider == "qwen-image":
        negative_prompt = request_negative_prompt.strip()
        if not negative_prompt or negative_prompt == plan_negative_prompt.strip():
            negative_prompt = QWEN_IMAGE_DEFAULT_NEGATIVE_PROMPT
        return _qwen_image_edit_prompt(instruction=instruction, plan_prompt=plan_prompt, task=task), negative_prompt
    return _first_nonempty(plan_prompt, instruction), _first_nonempty(request_negative_prompt, plan_negative_prompt)


def _full_image_mask(source_image: str) -> str:
    image = decode_data_url_to_image(source_image, mode="RGB")
    mask = Image.new("L", image.size, 255)
    return encode_image_to_data_url(mask)


def _generate_request_from_smart(payload: SmartGenerationRequest, decision: SmartPlannerDecision) -> GenerateRequest:
    if not payload.source_image:
        raise HTTPException(status_code=400, detail="source_image is required for image editing tasks.")
    if decision.requires_mask and not payload.mask_image:
        raise HTTPException(status_code=400, detail="mask_image is required for local inpaint tasks.")
    mask_image = payload.mask_image
    if not mask_image and decision.task_type in {"image_variation", "outpainting"}:
        mask_image = _full_image_mask(payload.source_image)
    return GenerateRequest(
        source_image=payload.source_image,
        instruction=payload.prompt,
        task=_legacy_task_for_decision(decision),
        generation_provider=payload.options.generation_provider if decision.pipeline == "qwen_image_inpaint" else "powerpaint",
        mask_image=mask_image,
        plan=PlanResponse(
            task=_legacy_task_for_decision(decision),
            task_prompt=decision.normalized_prompt,
            negative_prompt=decision.negative_prompt,
            mask_strategy="user-mask" if payload.mask_image else "smart-generation",
            reasoning="统一生成入口完成任务判断。",
            warnings=decision.warnings,
        ),
        steps=payload.options.steps,
        guidance_scale=payload.options.guidance_scale,
        true_cfg_scale=payload.options.true_cfg_scale,
        strength=payload.options.strength,
        seed=payload.options.seed,
        negative_prompt=decision.negative_prompt,
        smart_metadata=smart_metadata(
            request=payload,
            decision=decision,
            provider=_provider_for_smart_decision(payload, decision),
            fallback_used=False,
            is_diagnostic_result=False,
        ),
    )


@app.post("/api/generation/jobs", response_model=SmartGenerationJobResponse)
async def create_generation_job(
    payload: SmartGenerationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> SmartGenerationJobResponse:
    decision = build_smart_generation_plan(payload)
    base_metadata = smart_metadata(
        request=payload,
        decision=decision,
        provider=_provider_for_smart_decision(payload, decision),
        fallback_used=False,
        is_diagnostic_result=False,
    )

    if decision.need_user_clarification:
        return _smart_failure_response(
            decision=decision,
            message=decision.clarification_question or "需要补充修改区域。",
            error="USER_CLARIFICATION_REQUIRED",
            metadata=base_metadata,
        )

    if decision.task_type == "text_to_image":
        scene_plan = build_scene_plan(
            ScenePlanRequest(
                instruction=payload.prompt,
                candidate_count=payload.options.num_outputs,
                seed=payload.options.seed,
            )
        )
        try:
            candidates = await generate_initial_candidates(
                InitGenerateRequest(scene_plan=scene_plan, seed=payload.options.seed, provider="flux-local"),
                flux_init_url=FLUX_INIT_URL,
            )
        except InitProviderError:
            return _smart_failure_response(
                decision=decision,
                message="文生图模型当前不可用，请检查 FLUX 配置。",
                error="TEXT_TO_IMAGE_MODEL_UNAVAILABLE",
                metadata={**base_metadata, "provider_unavailable": True},
            )
        except Exception as exc:
            return _smart_failure_response(
                decision=decision,
                message="文生图模型当前不可用，请检查 FLUX 配置。",
                error="TEXT_TO_IMAGE_MODEL_UNAVAILABLE",
                metadata={**base_metadata, "provider_unavailable": True, "provider_error": str(exc)},
            )

        is_diagnostic = bool(candidates.fallback_used)
        metadata = smart_metadata(
            request=payload,
            decision=decision,
            provider=candidates.used_provider or candidates.provider,
            fallback_used=candidates.fallback_used,
            is_diagnostic_result=is_diagnostic,
        )
        return SmartGenerationJobResponse(
            job_id=uuid.uuid4().hex[:12],
            status="completed",
            task_type=decision.task_type,
            message=(
                "当前文生图模型不可用，以下结果只是诊断占位。"
                if is_diagnostic
                else "文生图生成完成。"
            ),
            progress=1.0,
            results=[
                SmartGenerationResultItem(
                    image_url=candidate.image,
                    thumbnail_url=None,
                    metadata_id=candidate.id,
                    is_diagnostic_result=is_diagnostic,
                    metadata={**metadata, "candidate_metadata": candidate.metadata},
                )
                for candidate in candidates.candidates
            ],
            planner=decision,
            metadata=metadata,
        )

    generate_request = _generate_request_from_smart(payload, decision)
    snapshot = job_store.create("Queued for generation")
    smart_job_metadata[snapshot.job_id] = base_metadata
    smart_job_plans[snapshot.job_id] = decision
    background_tasks.add_task(
        run_generate_job,
        snapshot.job_id,
        generate_request,
        current_base_url(request),
        1,
    )
    return _smart_response_from_job(snapshot)


@app.get("/api/generation/jobs/{job_id}", response_model=SmartGenerationJobResponse)
async def get_generation_job(job_id: str) -> SmartGenerationJobResponse:
    snapshot = job_store.get(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _smart_response_from_job(snapshot)


@app.post("/api/generation/jobs/{job_id}/cancel", response_model=SmartGenerationJobResponse)
async def cancel_generation_job(job_id: str) -> SmartGenerationJobResponse:
    try:
        snapshot = job_store.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    return _smart_response_from_job(snapshot)


@app.post("/api/canvas/validate-text", response_model=TextValidationReport)
def validate_canvas_text(payload: TextValidationRequest) -> TextValidationReport:
    return build_text_validation_report(payload)


@app.post("/api/canvas/export-svg", response_model=SvgExportResponse)
def export_canvas_svg(payload: SvgExportRequest) -> SvgExportResponse:
    return build_svg_export(payload)


@app.get("/api/projects", response_model=list[ProjectSnapshot])
def list_projects() -> list[ProjectSnapshot]:
    return project_store.list_projects()


@app.post("/api/projects", response_model=ProjectSnapshot)
def create_project(payload: ProjectCreateRequest) -> ProjectSnapshot:
    return project_store.create_project(payload)


@app.get("/api/projects/{project_id}", response_model=ProjectSnapshot)
def get_project(project_id: str) -> ProjectSnapshot:
    try:
        project = project_store.get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@app.post("/api/projects/{project_id}/versions", response_model=ProjectSnapshot)
def append_project_version(project_id: str, payload: ProjectVersionCreateRequest) -> ProjectSnapshot:
    try:
        project_store.append_version(project_id, payload)
        project = project_store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@app.get("/api/benchmarks/runs", response_model=list[BenchmarkRunSnapshot])
def list_benchmark_runs(limit: int = 50) -> list[BenchmarkRunSnapshot]:
    return benchmark_store.list_runs(limit=limit)


@app.post("/api/benchmarks/runs", response_model=BenchmarkRunSnapshot)
def record_benchmark_run(payload: BenchmarkRunCreateRequest) -> BenchmarkRunSnapshot:
    return benchmark_store.record_run(payload)


@app.get("/api/benchmarks/summary", response_model=BenchmarkSummaryResponse)
def get_benchmark_summary() -> BenchmarkSummaryResponse:
    return benchmark_store.summary()


@app.post("/api/segment", response_model=SegmentResponse)
async def segment(payload: SegmentRequest) -> SegmentResponse:
    try:
        data = await post_json(f"{SEGMENTER_URL}/segment", payload.model_dump())
        return SegmentResponse.model_validate(data)
    except Exception:
        return build_segment(payload)


def _is_diagram(image: Image.Image) -> bool:
    """Detect white-background scientific diagrams: border near-white + low variance."""
    import numpy as np
    arr = np.asarray(image.convert("RGB"))
    h, w = arr.shape[:2]
    border_pixels = np.concatenate([arr[0, :, :], arr[-1, :, :], arr[:, 0, :], arr[:, -1, :]])
    near_white_ratio = (border_pixels > 240).all(axis=1).mean()
    gray = arr.mean(axis=2)
    low_variance = gray.std() < 60
    return near_white_ratio > 0.7 and low_variance


def _diagram_removal_fill(source: Image.Image, mask: Image.Image) -> Image.Image:
    """Fill masked area with median border color for white-background diagram removal."""
    import numpy as np
    arr = np.asarray(source.convert("RGB"))
    mask_bin = np.asarray(mask.convert("L")) > 32
    if not mask_bin.any():
        return source
    from PIL import ImageFilter
    dilated = np.asarray(mask.filter(ImageFilter.MaxFilter(5))) > 32
    border_ring = dilated & ~mask_bin
    if border_ring.any():
        fill_color = np.median(arr[border_ring], axis=0).astype(np.uint8)
    else:
        fill_color = np.array([255, 255, 255], dtype=np.uint8)
    result = arr.copy()
    result[mask_bin] = fill_color
    return Image.fromarray(result, mode="RGB")


async def generate_pipeline(
    payload: GenerateRequest,
    base_url: str,
    progress: ProgressCallback | None = None,
) -> GenerateResponse:
    if progress:
        progress("PLANNING", 0.12, "Planning edit instructions")
    has_smart_plan = bool(payload.plan and payload.smart_metadata)
    if payload.plan and not has_smart_plan:
        plan_payload = payload.plan
        planner_source = "provided-plan"
    else:
        plan_payload = await plan(
            PlanRequest(
                source_image=payload.source_image,
                instruction=payload.instruction,
                selected_asset_id=payload.selected_asset_id,
                preferred_task=payload.task or (payload.plan.task if payload.plan else None),
                canvas_hints={
                    "has_asset": bool(payload.asset_placement),
                    "has_mask": bool(payload.mask_image),
                    "has_point_prompts": bool(payload.point_prompts),
                },
            )
        )
        planner_source = "planner-service-or-fallback"

    source_image = decode_data_url_to_image(payload.source_image, mode="RGB")

    has_point_prompts = bool(payload.point_prompts)
    use_sam2 = plan_payload.mask_strategy == "sam2-refine" and has_point_prompts
    if use_sam2:
        if progress:
            progress("SEGMENTING", 0.35, "SAM-2 refining mask")
        try:
            normalized_mask = await segment(
                SegmentRequest(
                    source_image=payload.source_image,
                    width=source_image.width,
                    height=source_image.height,
                    mask_image=payload.mask_image,
                    asset_placement=payload.asset_placement,
                    point_prompts=payload.point_prompts,
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"SAM-2 mask refinement failed: {exc}") from exc
    else:
        if progress:
            progress("SEGMENTING", 0.30, "Normalizing user mask")
        try:
            normalized_mask = build_segment(
                SegmentRequest(
                    source_image=payload.source_image,
                    width=source_image.width,
                    height=source_image.height,
                    mask_image=payload.mask_image,
                    asset_placement=payload.asset_placement,
                    point_prompts=payload.point_prompts,
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to prepare a valid mask: {exc}") from exc

    raw_mask = decode_data_url_to_image(normalized_mask.mask_image, mode="L")
    import numpy as np
    mask_arr = np.asarray(raw_mask) > 32

    task_name = plan_payload.task or payload.task
    task_fitting = _fitting_for_task(task_name)
    task_scale = _scale_for_task(task_name)
    effective_fitting = payload.fitting_degree if payload.fitting_degree != 0.9 else task_fitting
    effective_scale = payload.guidance_scale if payload.guidance_scale != 5.0 else task_scale
    provider_name = payload.generation_provider
    provider_pipeline = "qwen_image_inpaint" if provider_name == "qwen-image" else "powerpaint_inpaint"
    provider_model = "Qwen/Qwen-Image-Edit" if provider_name == "qwen-image" else "PowerPaint"
    provider_model_dtype = (
        os.getenv("QWEN_IMAGE_MODEL_DTYPE", "bfloat16")
        if provider_name == "qwen-image"
        else os.getenv("POWERPAINT_WEIGHT_DTYPE", "float16")
    )
    provider_prompt, provider_negative_prompt = _provider_edit_prompts(
        provider=provider_name,
        instruction=payload.instruction,
        plan_prompt=plan_payload.task_prompt,
        request_negative_prompt=payload.negative_prompt,
        plan_negative_prompt=plan_payload.negative_prompt,
        task=task_name,
    )

    # For white-background scientific diagrams, skip generative AI for removal
    if provider_name == "powerpaint" and task_name == "object-removal" and _is_diagram(source_image):
        if progress:
            progress("EXECUTING", 0.65, "Filling diagram background")
        result_image = _diagram_removal_fill(source_image, raw_mask)
        result_image_data = encode_image_to_data_url(result_image)
        # Skip PowerPaint, go straight to evaluation
        if progress:
            progress("EVALUATING", 0.9, "Evaluating result and saving artifacts")
        mask_image = raw_mask
        evaluation = evaluate_edit(source_image, result_image, mask_image)
        run_id = uuid.uuid4().hex[:12]
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        source_image.save(run_dir / "source.png")
        mask_image.save(run_dir / "mask.png")
        result_image.save(run_dir / "result.png")
        artifacts = {
            "source": f"{base_url}/artifacts/{run_id}/source.png",
            "mask": f"{base_url}/artifacts/{run_id}/mask.png",
            "result": f"{base_url}/artifacts/{run_id}/result.png",
            "metadata": f"{base_url}/artifacts/{run_id}/metadata.json",
        }
        canvas_state_after = build_canvas_state_after_generate(payload.canvas_state, run_id=run_id, artifacts=artifacts)
        quality_report = build_quality_report(
            run_id=run_id, payload=payload, plan=plan_payload,
            mask=mask_image, evaluation=evaluation, artifacts=artifacts,
            planner_source=planner_source,
        )
        metadata = {
            "run_id": run_id, "instruction": payload.instruction,
            "plan": plan_payload.model_dump(),
            "evaluation": evaluation.model_dump(),
            "quality_report": quality_report.model_dump(),
            "smart_generation": payload.smart_metadata,
            "selected_asset_id": payload.selected_asset_id,
            "task": task_name,
            "canvas_state_before": payload.canvas_state.model_dump() if payload.canvas_state else None,
            "canvas_state_after": canvas_state_after.model_dump() if canvas_state_after else None,
        }
        quality_report.prompt.parameters["mask_strategy"] = plan_payload.mask_strategy
        quality_report.prompt.parameters["sam2_refinement_requested"] = use_sam2
        quality_report.prompt.parameters["effective_fitting_degree"] = effective_fitting
        quality_report.prompt.parameters["planner_source"] = planner_source
        quality_report.prompt.parameters["provider"] = provider_name
        quality_report.prompt.parameters["pipeline"] = provider_pipeline
        quality_report.prompt.parameters["model"] = provider_model
        quality_report.prompt.parameters["model_dtype"] = provider_model_dtype
        quality_report.prompt.parameters["provider_prompt"] = provider_prompt
        quality_report.prompt.parameters["provider_negative_prompt"] = provider_negative_prompt
        for key in (
            "task_type",
            "subtask_type",
            "planner_confidence",
            "provider",
            "pipeline",
            "model",
            "model_dtype",
            "fallback_used",
            "is_diagnostic_result",
            "resize_strategy",
            "postprocess_blending",
        ):
            if key in payload.smart_metadata:
                quality_report.prompt.parameters[f"smart_{key}"] = payload.smart_metadata[key]
        metadata["quality_report"] = quality_report.model_dump()
        (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return GenerateResponse(
            run_id=run_id, plan=plan_payload,
            result_image=result_image_data, evaluation=evaluation,
            artifacts=artifacts, canvas_state=canvas_state_after,
            quality_report=quality_report,
        )

    if provider_name == "qwen-image":
        if progress:
            progress("EXECUTING", 0.65, "Qwen-Image generation is running")
        qwen_request = QwenImageEditRequest(
            image=payload.source_image,
            mask_image=normalized_mask.mask_image,
            prompt=provider_prompt,
            negative_prompt=provider_negative_prompt,
            num_inference_steps=payload.steps,
            true_cfg_scale=payload.true_cfg_scale if payload.true_cfg_scale is not None else payload.guidance_scale,
            strength=payload.strength,
            seed=payload.seed,
            local_files_only=payload.local_files_only,
        )
        try:
            provider_data = await post_json(f"{QWEN_IMAGE_URL}/generate", qwen_request.model_dump())
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Qwen-Image service is unavailable: {exc}") from exc
    else:
        # Pre-fill mask area with border average color to avoid BrushNet black-hole issue.
        if mask_arr.any():
            dilated = np.asarray(raw_mask.filter(ImageFilter.MaxFilter(9))) > 32
            border_ring = dilated & ~mask_arr
            if border_ring.any():
                src_arr = np.asarray(source_image)
                avg_color = src_arr[border_ring].mean(axis=0).astype(np.uint8)
                filled = src_arr.copy()
                filled[mask_arr] = avg_color
                inner_ring = mask_arr & ~(np.asarray(raw_mask.filter(ImageFilter.MinFilter(3))) > 32)
                if inner_ring.any():
                    filled_blurred = np.asarray(Image.fromarray(filled, mode="RGB").filter(ImageFilter.GaussianBlur(radius=2)))
                    filled[inner_ring] = filled_blurred[inner_ring]
                inpaint_image = encode_image_to_data_url(Image.fromarray(filled, mode="RGB"))
            else:
                inpaint_image = payload.source_image
        else:
            inpaint_image = payload.source_image

        if progress:
            progress("EXECUTING", 0.65, "PowerPaint generation is running")
        powerpaint_request = PowerPaintGenerateRequest(
            image=inpaint_image,
            mask_image=normalized_mask.mask_image,
            task=task_name,
            prompt=provider_prompt,
            negative_prompt=provider_negative_prompt,
            steps=payload.steps,
            guidance_scale=effective_scale,
            fitting_degree=effective_fitting,
            seed=payload.seed,
            local_files_only=payload.local_files_only,
            horizontal_expansion_ratio=payload.horizontal_expansion_ratio,
            vertical_expansion_ratio=payload.vertical_expansion_ratio,
        )

        try:
            provider_data = await post_json(f"{POWERPAINT_URL}/generate", powerpaint_request.model_dump())
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"PowerPaint service is unavailable: {exc}") from exc

    if progress:
        progress("EVALUATING", 0.9, "Evaluating result and saving artifacts")
    result_image = decode_data_url_to_image(provider_data["result_image"], mode="RGB")

    # Post-process with provider-specific masks: PowerPaint gets a wider edge blend;
    # Qwen-Image gets full outside-mask protection.
    if mask_arr.any():
        if provider_name == "qwen-image":
            blended_mask = blur_mask(dilate_mask(raw_mask, radius=2), radius=2)
        else:
            boundary_ring = dilate_mask(raw_mask, radius=5)
            boundary_ring = Image.fromarray(
                (np.asarray(boundary_ring, dtype=np.int16) - np.asarray(raw_mask, dtype=np.int16)).clip(0, 255).astype(np.uint8),
                mode="L",
            )
            boundary_blurred = blur_mask(boundary_ring, radius=3)
            blended_mask = Image.fromarray(
                (np.asarray(raw_mask, dtype=np.int16) + np.asarray(boundary_blurred, dtype=np.int16)).clip(0, 255).astype(np.uint8),
                mode="L",
            )
        result_image = blend_with_mask(source_image, result_image, blended_mask)
        result_image_data = encode_image_to_data_url(result_image)
    else:
        result_image_data = provider_data["result_image"]

    mask_image = raw_mask
    evaluation = evaluate_edit(source_image, result_image, mask_image)

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    source_image.save(run_dir / "source.png")
    mask_image.save(run_dir / "mask.png")
    result_image.save(run_dir / "result.png")
    artifacts = {
        "source": f"{base_url}/artifacts/{run_id}/source.png",
        "mask": f"{base_url}/artifacts/{run_id}/mask.png",
        "result": f"{base_url}/artifacts/{run_id}/result.png",
        "metadata": f"{base_url}/artifacts/{run_id}/metadata.json",
    }
    canvas_state_after = build_canvas_state_after_generate(payload.canvas_state, run_id=run_id, artifacts=artifacts)
    quality_report = build_quality_report(
        run_id=run_id,
        payload=payload,
        plan=plan_payload,
        mask=mask_image,
        evaluation=evaluation,
        artifacts=artifacts,
        planner_source=planner_source,
    )
    metadata = {
        "run_id": run_id,
        "instruction": payload.instruction,
        "plan": plan_payload.model_dump(),
        "evaluation": evaluation.model_dump(),
        "quality_report": quality_report.model_dump(),
        "smart_generation": payload.smart_metadata,
        "selected_asset_id": payload.selected_asset_id,
        "task": payload.task or plan_payload.task,
        "canvas_state_before": payload.canvas_state.model_dump() if payload.canvas_state else None,
        "canvas_state_after": canvas_state_after.model_dump() if canvas_state_after else None,
    }
    quality_report.prompt.parameters["mask_strategy"] = plan_payload.mask_strategy
    quality_report.prompt.parameters["sam2_refinement_requested"] = use_sam2
    quality_report.prompt.parameters["effective_fitting_degree"] = effective_fitting
    quality_report.prompt.parameters["planner_source"] = planner_source
    quality_report.prompt.parameters["provider"] = provider_name
    quality_report.prompt.parameters["pipeline"] = provider_pipeline
    quality_report.prompt.parameters["model"] = provider_model
    quality_report.prompt.parameters["model_dtype"] = provider_model_dtype
    quality_report.prompt.parameters["provider_prompt"] = provider_prompt
    quality_report.prompt.parameters["provider_negative_prompt"] = provider_negative_prompt
    for key in (
        "task_type",
        "subtask_type",
        "planner_confidence",
        "provider",
        "pipeline",
        "model",
        "model_dtype",
        "fallback_used",
        "is_diagnostic_result",
        "resize_strategy",
        "postprocess_blending",
    ):
        if key in payload.smart_metadata:
            quality_report.prompt.parameters[f"smart_{key}"] = payload.smart_metadata[key]
    metadata["quality_report"] = quality_report.model_dump()
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return GenerateResponse(
        run_id=run_id,
        plan=plan_payload,
        result_image=result_image_data,
        evaluation=evaluation,
        artifacts=artifacts,
        canvas_state=canvas_state_after,
        quality_report=quality_report,
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest, request: Request) -> GenerateResponse:
    return await generate_pipeline(payload, current_base_url(request))


async def run_generate_job(job_id: str, payload: GenerateRequest, base_url: str, max_attempts: int = 1) -> None:
    def update(status: JobStatus, progress: float, message: str) -> None:
        if job_store.is_cancel_requested(job_id):
            raise JobCancelled()
        job_store.update(job_id, status=status, progress=progress, message=message)

    for attempt in range(1, max_attempts + 1):
        try:
            if job_store.is_cancel_requested(job_id):
                raise JobCancelled()
            job_store.update(job_id, attempt=attempt)
            result = await generate_pipeline(payload, base_url, progress=update)
            if job_store.is_cancel_requested(job_id):
                raise JobCancelled()
            planner_src = result.quality_report.prompt.parameters.get("planner_source", "unknown") if result.quality_report else "unknown"
            psrc_label = "Qwen" if planner_src == "planner-service-or-fallback" else "fallback"
            if job_id in smart_job_metadata:
                smart_job_metadata[job_id]["planner_source"] = planner_src
                smart_job_metadata[job_id]["planner_label"] = psrc_label
            job_store.update(
                job_id,
                status="DONE",
                progress=1.0,
                message=f"[{psrc_label}] Generation complete",
                result=result,
            )
            return
        except JobCancelled:
            job_store.cancel(job_id)
            return
        except HTTPException as exc:
            if attempt < max_attempts:
                job_store.update(
                    job_id,
                    status="CREATED",
                    progress=0.0,
                    message=f"Retrying generation ({attempt + 1}/{max_attempts})",
                    error=str(exc.detail),
                    attempt=attempt + 1,
                )
                continue
            job_store.update(
                job_id,
                status="FAILED",
                progress=1.0,
                message="Generation failed",
                error=str(exc.detail),
            )
            return
        except Exception as exc:
            if attempt < max_attempts:
                job_store.update(
                    job_id,
                    status="CREATED",
                    progress=0.0,
                    message=f"Retrying generation ({attempt + 1}/{max_attempts})",
                    error=str(exc),
                    attempt=attempt + 1,
                )
                continue
            job_store.update(
                job_id,
                status="FAILED",
                progress=1.0,
                message="Generation failed",
                error=str(exc),
            )
            return


@app.post("/api/jobs", response_model=JobSnapshot)
async def create_job(payload: JobCreateRequest, request: Request, background_tasks: BackgroundTasks) -> JobSnapshot:
    snapshot = job_store.create("Queued for generation", max_attempts=payload.max_attempts)
    background_tasks.add_task(
        run_generate_job,
        snapshot.job_id,
        payload.generate_request,
        current_base_url(request),
        payload.max_attempts,
    )
    return snapshot


@app.post("/api/jobs/{job_id}/cancel", response_model=JobSnapshot)
async def cancel_job(job_id: str) -> JobSnapshot:
    try:
        return job_store.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.get("/api/jobs/{job_id}", response_model=JobSnapshot)
async def get_job(job_id: str) -> JobSnapshot:
    snapshot = job_store.get(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return snapshot


@app.post("/api/evaluate")
async def evaluate(payload: dict) -> dict:
    source_image_data = payload.get("source_image")
    result_image_data = payload.get("result_image")
    mask_image_data = payload.get("mask_image")
    if not source_image_data or not result_image_data or not mask_image_data:
        raise HTTPException(status_code=400, detail="source_image, result_image and mask_image are required.")

    source_image = decode_data_url_to_image(source_image_data, mode="RGB")
    result_image = decode_data_url_to_image(result_image_data, mode="RGB")
    mask_image = decode_data_url_to_image(mask_image_data, mode="L")
    return evaluate_edit(source_image, result_image, mask_image).model_dump()
