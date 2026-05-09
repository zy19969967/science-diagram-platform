from __future__ import annotations

from fastapi import FastAPI

from common.init_logic import build_scene_plan
from common.planner_logic import build_plan
from common.schemas import (
    PlanRequest,
    PlanResponse,
    QwenEditPromptRequest,
    QwenEditPromptResponse,
    ScenePlanRequest,
    ScenePlanResponse,
)

from .runtime import planner_runtime

app = FastAPI(title="Science Diagram Planner", version="0.2.0")


@app.get("/health")
def health() -> dict[str, object]:
    return planner_runtime.health()


@app.post("/plan", response_model=PlanResponse)
def plan(payload: PlanRequest) -> PlanResponse:
    planned = planner_runtime.plan(payload)
    return planned or build_plan(payload)


@app.post("/init-plan", response_model=ScenePlanResponse)
def init_plan(payload: ScenePlanRequest) -> ScenePlanResponse:
    planned = planner_runtime.plan_scene(payload)
    return planned or build_scene_plan(payload)


@app.post("/qwen-edit-prompt", response_model=QwenEditPromptResponse)
def qwen_edit_prompt(payload: QwenEditPromptRequest) -> QwenEditPromptResponse:
    enhanced = planner_runtime.enhance_qwen_edit_prompt(payload)
    return enhanced or QwenEditPromptResponse(
        prompt=payload.fallback_prompt,
        negative_prompt=" ",
        source="gateway-fallback",
        warnings=["Qwen3.5 prompt enhancer unavailable; using gateway fallback prompt."],
    )
