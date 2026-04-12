from __future__ import annotations

from fastapi import FastAPI, HTTPException

from common.schemas import SegmentRequest, SegmentResponse
from common.segment_logic import build_segment

app = FastAPI(title="Science Diagram Segmenter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "segmenter"}


@app.post("/segment", response_model=SegmentResponse)
def segment(payload: SegmentRequest) -> SegmentResponse:
    try:
        return build_segment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
