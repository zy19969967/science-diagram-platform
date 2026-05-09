from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
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
    QwenEditPromptRequest,
    QwenEditPromptResponse,
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

QWEN_IMAGE_SCIENCE_STYLE_PROMPT = "保持科学线稿风格，白底、轮廓清晰。"

QWEN_IMAGE_PHOTO_STYLE_PROMPT = "保持照片风格，光照、透视和材质与原图一致。"

QWEN_IMAGE_DIAGRAM_PRESERVATION_PROMPT = "未选区保持原图不变。"

QWEN_IMAGE_PHOTO_PRESERVATION_PROMPT = "未选区保持原图不变。"

QWEN_IMAGE_TERM_HINTS = (
    ("锥形瓶", "锥形瓶（窄颈、宽底）"),
    ("conical flask", "锥形瓶（窄颈、宽底）"),
    ("erlenmeyer", "锥形瓶（窄颈、宽底）"),
    ("glass cup", "玻璃杯"),
    ("cup", "杯子"),
    ("beaker", "烧杯"),
)

QWEN_IMAGE_INTERNAL_NEGATIVE_MARKERS = (
    "background changed",
    "color bleeding",
    "broken edges",
    "text corruption",
    "object remnants",
    "ghost artifacts",
    "mismatched texture",
)

QWEN_IMAGE_PLANNER_LOCATION_PATTERNS = (
    r"\s*,?\s*(?:positioned|placed|located|sitting|standing)\b[^.]*",
    r"\s*,?\s*in the (?:lower|upper|left|right|center|centre)\b[^.]*",
    r"\s*,?\s*where the\b[^.]*",
)


@dataclass(frozen=True)
class QwenEditInput:
    request_image: Image.Image
    request_mask: Image.Image
    image_data_url: str
    mask_data_url: str
    source_size: tuple[int, int]
    request_size: tuple[int, int]
    crop_box: tuple[int, int, int, int] | None = None
    crop_size: tuple[int, int] | None = None
    prefill_enabled: bool = False


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _sanitize_qwen_planner_prompt(value: str) -> str:
    sanitized = value.strip()
    for pattern in QWEN_IMAGE_PLANNER_LOCATION_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    sanitized = re.sub(r"\s+\.", ".", sanitized)
    sanitized = re.sub(r"\.{2,}", ".", sanitized)
    return sanitized.strip(" ,")


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _qwen_prompt_enhancer_enabled() -> bool:
    value = os.getenv("QWEN_IMAGE_PROMPT_ENHANCER_ENABLED", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _qwen_prompt_is_chinese_enough(prompt: str) -> bool:
    return _contains_cjk(prompt)


def _qwen_lookup_known_term(text: str) -> str | None:
    normalized = text.lower()
    for source, target in QWEN_IMAGE_TERM_HINTS:
        if source in normalized or source in text:
            return target
    return None


def _qwen_normalize_known_terms(text: str) -> str:
    normalized = text
    if "锥形瓶" in normalized and "窄颈" not in normalized and "宽底" not in normalized:
        normalized = normalized.replace("锥形瓶", "锥形瓶（窄颈、宽底）", 1)
    return normalized


def _qwen_english_instruction_to_chinese(instruction: str, planner_prompt: str, task: str | None) -> str:
    text = instruction.strip()
    combined = f"{instruction} {planner_prompt}"
    lower = combined.lower()
    if task == "object-removal" or "remove" in lower or "delete" in lower:
        return "删除选区内容"

    replacement_patterns = (
        r"\b(?:replace|change|turn|convert)\b.+?\b(?:with|to|into)\b\s+(.+)$",
        r"\b(?:replace with|change to|turn into|convert to)\b\s+(.+)$",
    )
    for pattern in replacement_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            target = _qwen_lookup_known_term(match.group(1)) or _qwen_lookup_known_term(combined) or "用户要求的内容"
            return f"把选区内容改成：{target}"

    known_target = _qwen_lookup_known_term(combined)
    if known_target:
        return f"把选区内容改成：{known_target}"
    return "按用户要求编辑选区内容"


def _qwen_direct_instruction(instruction: str, planner_prompt: str, task: str | None) -> str:
    user_instruction = instruction.strip()
    if user_instruction and _contains_cjk(user_instruction):
        return _qwen_normalize_known_terms(user_instruction)
    if user_instruction:
        return _qwen_english_instruction_to_chinese(user_instruction, planner_prompt, task)

    planner_instruction = _sanitize_qwen_planner_prompt(planner_prompt)
    if planner_instruction and _contains_cjk(planner_instruction):
        return _qwen_normalize_known_terms(planner_instruction)
    if planner_instruction:
        return _qwen_english_instruction_to_chinese(planner_instruction, planner_prompt, task)
    return "按用户要求编辑选区内容"


def _qwen_prompt_has_bad_lab_geometry(prompt: str, context: str) -> bool:
    combined = f"{prompt} {context}".lower()
    if "锥形瓶" not in combined and "conical flask" not in combined and "erlenmeyer" not in combined:
        return False
    return "wide mouth" in combined or "narrow base" in combined


def _qwen_chinese_transform_parts(instruction: str) -> tuple[str | None, str | None]:
    match = re.search(r"(?:把|将).+?(?:替换为|替换成|换成|改成|变成|变为|转成)(.+)$", instruction)
    source = None
    if match:
        source_match = re.search(r"(?:把|将)(.+?)(?:替换为|替换成|换成|改成|变成|变为|转成)", instruction)
        if source_match:
            source = source_match.group(1).strip(" 。.，,")
    if not match:
        match = re.search(r"(?:替换为|替换成|换成|改成|变成|变为|转成)(.+)$", instruction)
    if not match:
        return None, None
    return source, match.group(1).strip(" 。.，,")


def _qwen_target_after_transform_verb(prompt: str, targets: list[str]) -> bool:
    for target in targets:
        if not target:
            continue
        pattern = r"(?:替换为|替换成|换成|改成|变成|变为|转成)[:：]?[^\n。；;，,]*" + re.escape(target)
        if re.search(pattern, prompt):
            return True
    return False


def _qwen_prompt_preserves_chinese_action(instruction: str, prompt: str) -> bool:
    if not _contains_cjk(instruction):
        return True

    transform_source, transform_target = _qwen_chinese_transform_parts(instruction)
    if transform_target:
        target_core = re.sub(r"^(一个|一只|一件|这个|这些|该|选区里的|选区内的)", "", transform_target).strip()
        known_target = _qwen_lookup_known_term(transform_target)
        target_candidates = [transform_target, target_core]
        if known_target:
            target_candidates.append(known_target.split("（", 1)[0])
        if not _qwen_target_after_transform_verb(prompt, target_candidates):
            return False
        if transform_source:
            source_core = re.sub(r"^(一个|一只|一件|这个|这些|该|选区里的|选区内的)", "", transform_source).strip()
            source_candidates = [transform_source, source_core]
            known_source = _qwen_lookup_known_term(transform_source)
            if known_source:
                source_candidates.append(known_source.split("（", 1)[0])
            if _qwen_target_after_transform_verb(prompt, source_candidates):
                return False
        return True

    if any(verb in instruction for verb in ("删除", "移除", "去掉", "删掉")):
        return any(verb in prompt for verb in ("删除", "移除", "去掉", "删掉"))

    return True


def _qwen_image_edit_prompt(
    *,
    instruction: str,
    plan_prompt: str,
    task: str | None,
    source_is_diagram: bool = True,
) -> str:
    edit_instruction = _qwen_direct_instruction(instruction, plan_prompt, task).rstrip("。.! ")
    preserve_prompt = QWEN_IMAGE_DIAGRAM_PRESERVATION_PROMPT if source_is_diagram else QWEN_IMAGE_PHOTO_PRESERVATION_PROMPT
    style_prompt = QWEN_IMAGE_SCIENCE_STYLE_PROMPT if source_is_diagram else QWEN_IMAGE_PHOTO_STYLE_PROMPT

    parts = [
        "只修改 mask 内区域。",
        f"{edit_instruction}。",
        preserve_prompt,
        style_prompt,
    ]
    return "".join(parts)


def _is_internal_negative_prompt(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in QWEN_IMAGE_INTERNAL_NEGATIVE_MARKERS)


def _provider_edit_prompts(
    *,
    provider: str,
    instruction: str,
    plan_prompt: str,
    request_negative_prompt: str,
    plan_negative_prompt: str,
    task: str | None,
    source_is_diagram: bool = True,
) -> tuple[str, str]:
    if provider == "qwen-image":
        negative_prompt = request_negative_prompt.strip()
        if (
            not negative_prompt
            or negative_prompt == plan_negative_prompt.strip()
            or _is_internal_negative_prompt(negative_prompt)
        ):
            negative_prompt = QWEN_IMAGE_DEFAULT_NEGATIVE_PROMPT
        return (
            _qwen_image_edit_prompt(
                instruction=instruction,
                plan_prompt=plan_prompt,
                task=task,
                source_is_diagram=source_is_diagram,
            ),
            negative_prompt,
        )
    return _first_nonempty(plan_prompt, instruction), _first_nonempty(request_negative_prompt, plan_negative_prompt)


async def _enhance_qwen_provider_prompt(
    *,
    instruction: str,
    task: str | None,
    plan_prompt: str,
    source_is_diagram: bool,
    fallback_prompt: str,
    fallback_negative_prompt: str,
) -> tuple[str, str, str, list[str]]:
    source_style = "scientific_diagram" if source_is_diagram else "photographic"
    request = QwenEditPromptRequest(
        instruction=instruction,
        task=task,
        plan_prompt=plan_prompt,
        source_style=source_style,
        has_mask=True,
        fallback_prompt=fallback_prompt,
    )
    try:
        data = await post_json(f"{PLANNER_URL}/qwen-edit-prompt", request.model_dump())
        response = QwenEditPromptResponse.model_validate(data)
    except Exception:
        return fallback_prompt, fallback_negative_prompt, "gateway-fallback", []

    prompt = response.prompt.strip() or fallback_prompt
    negative_prompt = response.negative_prompt.strip() or fallback_negative_prompt or QWEN_IMAGE_DEFAULT_NEGATIVE_PROMPT
    if negative_prompt != QWEN_IMAGE_DEFAULT_NEGATIVE_PROMPT and _is_internal_negative_prompt(negative_prompt):
        negative_prompt = QWEN_IMAGE_DEFAULT_NEGATIVE_PROMPT
    if not _qwen_prompt_is_chinese_enough(prompt):
        return fallback_prompt, fallback_negative_prompt, "gateway-fallback", [
            "Qwen3.5 prompt was not Chinese; gateway fallback prompt was used."
        ]
    if _qwen_prompt_has_bad_lab_geometry(prompt, f"{instruction} {plan_prompt}"):
        return fallback_prompt, fallback_negative_prompt, "gateway-fallback", [
            "Qwen3.5 prompt contained incorrect lab-object geometry; gateway fallback prompt was used."
        ]
    if not _qwen_prompt_preserves_chinese_action(instruction, prompt):
        return fallback_prompt, fallback_negative_prompt, "gateway-fallback", [
            "Qwen3.5 prompt changed the Chinese edit action; gateway fallback prompt was used."
        ]
    return prompt, negative_prompt, response.source or "qwen3.5-enhancer", response.warnings


def _mask_bbox(mask: Image.Image) -> tuple[int, int, int, int] | None:
    import numpy as np

    arr = np.asarray(mask.convert("L")) > 32
    if not arr.any():
        return None
    ys, xs = np.where(arr)
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def _mask_coverage_ratio(mask: Image.Image) -> float:
    import numpy as np

    return float((np.asarray(mask.convert("L")) > 32).mean())


def _prepare_qwen_edit_input(source_image: Image.Image, edit_mask: Image.Image) -> QwenEditInput:
    source_size = source_image.size
    return QwenEditInput(
        request_image=source_image.convert("RGB"),
        request_mask=edit_mask.convert("L"),
        image_data_url=encode_image_to_data_url(source_image),
        mask_data_url=encode_image_to_data_url(edit_mask),
        source_size=source_size,
        request_size=source_size,
        prefill_enabled=False,
    )


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
    source_is_diagram = _is_diagram(source_image)

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
    provider_route_reason = ""
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
        source_is_diagram=source_is_diagram,
    )
    provider_prompt_source = "user-direct" if provider_name == "qwen-image" else "planner"
    provider_prompt_warnings: list[str] = []
    if provider_name == "qwen-image" and _qwen_prompt_enhancer_enabled():
        (
            provider_prompt,
            provider_negative_prompt,
            provider_prompt_source,
            provider_prompt_warnings,
        ) = await _enhance_qwen_provider_prompt(
            instruction=payload.instruction,
            task=task_name,
            plan_prompt=plan_payload.task_prompt,
            source_is_diagram=source_is_diagram,
            fallback_prompt=provider_prompt,
            fallback_negative_prompt=provider_negative_prompt,
        )
    qwen_edit_input: QwenEditInput | None = None
    qwen_execution_mask: Image.Image | None = None
    qwen_execution_mask_dilation_radius = 0
    qwen_provider_raw: Image.Image | None = None
    qwen_restored_preblend: Image.Image | None = None
    qwen_final_blend_mask: Image.Image | None = None

    # For white-background scientific diagrams, skip generative AI for removal.
    if task_name == "object-removal" and source_is_diagram and provider_name == "powerpaint":
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
        quality_report.prompt.parameters["provider"] = "deterministic-fill"
        quality_report.prompt.parameters["pipeline"] = "diagram_removal_fill"
        quality_report.prompt.parameters["model"] = "median-border-fill"
        quality_report.prompt.parameters["model_dtype"] = "n/a"
        quality_report.prompt.parameters["provider_prompt"] = "Remove the masked diagram object with deterministic white-background fill."
        quality_report.prompt.parameters["provider_negative_prompt"] = ""
        quality_report.prompt.parameters["source_style"] = "scientific_diagram" if source_is_diagram else "photographic"
        quality_report.prompt.parameters["provider_route_reason"] = "scientific_diagram_removal_uses_deterministic_fill"
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
        qwen_edit_input = _prepare_qwen_edit_input(source_image, raw_mask)
        qwen_request = QwenImageEditRequest(
            image=qwen_edit_input.image_data_url,
            mask_image=qwen_edit_input.mask_data_url,
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
        provider_result = decode_data_url_to_image(provider_data["result_image"], mode="RGB")
        qwen_provider_raw = provider_result
        if provider_result.size != source_image.size:
            provider_result = provider_result.resize(source_image.size, resample=Image.Resampling.LANCZOS)
        provider_data = {
            "result_image": encode_image_to_data_url(provider_result)
        }
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
            blended_mask = raw_mask
            qwen_final_blend_mask = blended_mask
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
    if qwen_edit_input:
        qwen_edit_input.request_image.save(run_dir / "qwen_request_image.png")
        qwen_edit_input.request_mask.save(run_dir / "qwen_request_mask.png")
        artifacts["qwen_request_image"] = f"{base_url}/artifacts/{run_id}/qwen_request_image.png"
        artifacts["qwen_request_mask"] = f"{base_url}/artifacts/{run_id}/qwen_request_mask.png"
        if qwen_execution_mask:
            qwen_execution_mask.save(run_dir / "qwen_execution_mask.png")
            artifacts["qwen_execution_mask"] = f"{base_url}/artifacts/{run_id}/qwen_execution_mask.png"
        if qwen_provider_raw:
            qwen_provider_raw.save(run_dir / "qwen_provider_raw.png")
            artifacts["qwen_provider_raw"] = f"{base_url}/artifacts/{run_id}/qwen_provider_raw.png"
        if qwen_restored_preblend:
            qwen_restored_preblend.save(run_dir / "qwen_restored_preblend.png")
            artifacts["qwen_restored_preblend"] = f"{base_url}/artifacts/{run_id}/qwen_restored_preblend.png"
        if qwen_final_blend_mask:
            qwen_final_blend_mask.save(run_dir / "qwen_final_blend_mask.png")
            artifacts["qwen_final_blend_mask"] = f"{base_url}/artifacts/{run_id}/qwen_final_blend_mask.png"
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
    quality_report.prompt.parameters["source_style"] = "scientific_diagram" if source_is_diagram else "photographic"
    quality_report.prompt.parameters["provider_prompt_source"] = provider_prompt_source
    if provider_prompt_warnings:
        quality_report.prompt.parameters["provider_prompt_warnings"] = provider_prompt_warnings
    if provider_route_reason:
        quality_report.prompt.parameters["provider_route_reason"] = provider_route_reason
    if qwen_edit_input:
        quality_report.prompt.parameters["qwen_edit_crop_enabled"] = qwen_edit_input.crop_box is not None
        quality_report.prompt.parameters["qwen_edit_crop_box"] = list(qwen_edit_input.crop_box) if qwen_edit_input.crop_box else None
        quality_report.prompt.parameters["qwen_edit_crop_size"] = list(qwen_edit_input.crop_size) if qwen_edit_input.crop_size else None
        quality_report.prompt.parameters["qwen_edit_request_size"] = list(qwen_edit_input.request_size)
        quality_report.prompt.parameters["qwen_edit_crop_source_size"] = list(qwen_edit_input.source_size)
        quality_report.prompt.parameters["qwen_edit_prefill_enabled"] = qwen_edit_input.prefill_enabled
        quality_report.prompt.parameters["qwen_edit_execution_mask_dilation_radius"] = qwen_execution_mask_dilation_radius
        quality_report.prompt.parameters["qwen_edit_execution_mask_bbox"] = (
            list(_mask_bbox(qwen_execution_mask)) if qwen_execution_mask else None
        )
        quality_report.prompt.parameters["qwen_edit_execution_mask_coverage_ratio"] = (
            _mask_coverage_ratio(qwen_execution_mask) if qwen_execution_mask else None
        )
        quality_report.prompt.parameters["qwen_edit_user_mask_bbox"] = list(_mask_bbox(raw_mask)) if _mask_bbox(raw_mask) else None
        quality_report.prompt.parameters["qwen_edit_user_mask_coverage_ratio"] = _mask_coverage_ratio(raw_mask)
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
