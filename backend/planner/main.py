from __future__ import annotations

from fastapi import FastAPI

from common.planner_logic import build_plan
from common.schemas import PlanRequest, PlanResponse

from .runtime import planner_runtime

app = FastAPI(title="Science Diagram Planner", version="0.2.0")


@app.get("/health")
def health() -> dict[str, object]:
    return planner_runtime.health()


@app.post("/plan", response_model=PlanResponse)
def plan(payload: PlanRequest) -> PlanResponse:
    planned = planner_runtime.plan(payload)
    return planned or build_plan(payload)
