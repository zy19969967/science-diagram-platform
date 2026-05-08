from __future__ import annotations

from fastapi import FastAPI, HTTPException

from common.schemas import QwenImageEditRequest

from .runtime import qwen_image_runtime

app = FastAPI(title="Science Diagram Local Qwen-Image Edit Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    return qwen_image_runtime.health()


@app.post("/generate")
def generate(payload: QwenImageEditRequest) -> dict[str, str]:
    try:
        return qwen_image_runtime.generate(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Local Qwen-Image generation failed: {exc}") from exc
