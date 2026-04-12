from __future__ import annotations

from fastapi import FastAPI

from common.planner_logic import build_plan
from common.schemas import PlanRequest, PlanResponse

app = FastAPI(title="Science Diagram Planner", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "planner"}


@app.post("/plan", response_model=PlanResponse)
def plan(payload: PlanRequest) -> PlanResponse:
    return build_plan(payload)
