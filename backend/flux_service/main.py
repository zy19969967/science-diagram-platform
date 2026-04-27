from __future__ import annotations

from fastapi import FastAPI, HTTPException

from common.schemas import InitGenerateRequest, InitGenerateResponse

from .runtime import flux_runtime

app = FastAPI(title="Science Diagram Local FLUX Initial Canvas Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    return flux_runtime.health()


@app.post("/generate", response_model=InitGenerateResponse)
def generate(payload: InitGenerateRequest) -> InitGenerateResponse:
    try:
        return flux_runtime.generate(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Local FLUX generation failed: {exc}") from exc
