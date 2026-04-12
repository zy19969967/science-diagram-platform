from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from common.schemas import PowerPaintGenerateRequest

from .runtime import PowerPaintRuntime

runtime = PowerPaintRuntime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime.startup()
    yield


app = FastAPI(title="PowerPaint Wrapper", version="0.1.0", lifespan=lifespan)


class GenerateResult(BaseModel):
    result_image: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "powerpaint"}


@app.post("/generate", response_model=GenerateResult)
def generate(payload: PowerPaintGenerateRequest) -> GenerateResult:
    try:
        return GenerateResult(result_image=runtime.generate(payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PowerPaint generation failed: {exc}") from exc
