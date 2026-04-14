from __future__ import annotations

from fastapi import FastAPI, HTTPException

from common.schemas import SegmentRequest, SegmentResponse
from common.segment_logic import build_segment

from .runtime import segmenter_runtime

app = FastAPI(title="Science Diagram Segmenter", version="0.2.0")


@app.get("/health")
def health() -> dict[str, object]:
    return segmenter_runtime.health()


@app.post("/segment", response_model=SegmentResponse)
def segment(payload: SegmentRequest) -> SegmentResponse:
    refined = segmenter_runtime.segment(payload)
    if refined is not None:
        return refined
    try:
        return build_segment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
