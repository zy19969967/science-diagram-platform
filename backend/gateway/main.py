from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Callable

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from common.assets import asset_catalog_with_urls
from common.planner_logic import build_plan
from common.init_logic import build_init_candidates, build_scene_plan
from common.schemas import (
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
    ScenePlanRequest,
    ScenePlanResponse,
    SegmentRequest,
    SegmentResponse,
)
from common.segment_logic import build_segment
from common.utils.images import decode_data_url_to_image
from common.utils.masks import evaluate_edit

from .jobs import job_store

PLANNER_URL = os.getenv("PLANNER_URL", "http://127.0.0.1:19081")
SEGMENTER_URL = os.getenv("SEGMENTER_URL", "http://127.0.0.1:19083")
POWERPAINT_URL = os.getenv("POWERPAINT_URL", "http://127.0.0.1:19082")
RUNS_DIR = Path(os.getenv("RUNS_DIR", "/app/data/runs"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "/app/assets"))

RUNS_DIR.mkdir(parents=True, exist_ok=True)

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
    return build_scene_plan(payload)


@app.post("/api/init-generate", response_model=InitGenerateResponse)
async def init_generate(payload: InitGenerateRequest) -> InitGenerateResponse:
    return build_init_candidates(payload)


@app.post("/api/segment", response_model=SegmentResponse)
async def segment(payload: SegmentRequest) -> SegmentResponse:
    try:
        data = await post_json(f"{SEGMENTER_URL}/segment", payload.model_dump())
        return SegmentResponse.model_validate(data)
    except Exception:
        return build_segment(payload)


async def generate_pipeline(
    payload: GenerateRequest,
    base_url: str,
    progress: ProgressCallback | None = None,
) -> GenerateResponse:
    if progress:
        progress("PLANNING", 0.12, "Planning edit instructions")
    plan_payload = payload.plan or await plan(
        PlanRequest(
            source_image=payload.source_image,
            instruction=payload.instruction,
            selected_asset_id=payload.selected_asset_id,
            preferred_task=payload.task,
            canvas_hints={
                "has_asset": bool(payload.asset_placement),
                "has_mask": bool(payload.mask_image),
            },
        )
    )

    source_image = decode_data_url_to_image(payload.source_image, mode="RGB")

    if progress:
        progress("SEGMENTING", 0.35, "Preparing edit mask")
    try:
        normalized_mask = await segment(
            SegmentRequest(
                source_image=payload.source_image,
                width=source_image.width,
                height=source_image.height,
                mask_image=payload.mask_image,
                asset_placement=payload.asset_placement,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to prepare a valid mask: {exc}") from exc

    if progress:
        progress("EXECUTING", 0.65, "PowerPaint generation is running")
    powerpaint_request = PowerPaintGenerateRequest(
        image=payload.source_image,
        mask_image=normalized_mask.mask_image,
        task=payload.task or plan_payload.task,
        prompt=plan_payload.task_prompt,
        negative_prompt=payload.negative_prompt or plan_payload.negative_prompt,
        steps=payload.steps,
        guidance_scale=payload.guidance_scale,
        fitting_degree=payload.fitting_degree,
        seed=payload.seed,
        local_files_only=payload.local_files_only,
        horizontal_expansion_ratio=payload.horizontal_expansion_ratio,
        vertical_expansion_ratio=payload.vertical_expansion_ratio,
    )

    try:
        powerpaint_data = await post_json(f"{POWERPAINT_URL}/generate", powerpaint_request.model_dump())
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"PowerPaint service is unavailable: {exc}") from exc

    if progress:
        progress("EVALUATING", 0.9, "Evaluating result and saving artifacts")
    result_image_data = powerpaint_data["result_image"]
    result_image = decode_data_url_to_image(result_image_data, mode="RGB")
    mask_image = decode_data_url_to_image(normalized_mask.mask_image, mode="L")
    evaluation = evaluate_edit(source_image, result_image, mask_image)

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    source_image.save(run_dir / "source.png")
    mask_image.save(run_dir / "mask.png")
    result_image.save(run_dir / "result.png")
    metadata = {
        "run_id": run_id,
        "instruction": payload.instruction,
        "plan": plan_payload.model_dump(),
        "evaluation": evaluation.model_dump(),
        "selected_asset_id": payload.selected_asset_id,
        "task": payload.task or plan_payload.task,
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    artifacts = {
        "source": f"{base_url}/artifacts/{run_id}/source.png",
        "mask": f"{base_url}/artifacts/{run_id}/mask.png",
        "result": f"{base_url}/artifacts/{run_id}/result.png",
        "metadata": f"{base_url}/artifacts/{run_id}/metadata.json",
    }

    return GenerateResponse(
        run_id=run_id,
        plan=plan_payload,
        result_image=result_image_data,
        evaluation=evaluation,
        artifacts=artifacts,
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest, request: Request) -> GenerateResponse:
    return await generate_pipeline(payload, current_base_url(request))


async def run_generate_job(job_id: str, payload: GenerateRequest, base_url: str) -> None:
    def update(status: JobStatus, progress: float, message: str) -> None:
        job_store.update(job_id, status=status, progress=progress, message=message)

    try:
        result = await generate_pipeline(payload, base_url, progress=update)
        job_store.update(
            job_id,
            status="DONE",
            progress=1.0,
            message="Generation complete",
            result=result,
        )
    except HTTPException as exc:
        job_store.update(
            job_id,
            status="FAILED",
            progress=1.0,
            message="Generation failed",
            error=str(exc.detail),
        )
    except Exception as exc:
        job_store.update(
            job_id,
            status="FAILED",
            progress=1.0,
            message="Generation failed",
            error=str(exc),
        )


@app.post("/api/jobs", response_model=JobSnapshot)
async def create_job(payload: JobCreateRequest, request: Request, background_tasks: BackgroundTasks) -> JobSnapshot:
    snapshot = job_store.create("Queued for generation")
    background_tasks.add_task(
        run_generate_job,
        snapshot.job_id,
        payload.generate_request,
        current_base_url(request),
    )
    return snapshot


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
