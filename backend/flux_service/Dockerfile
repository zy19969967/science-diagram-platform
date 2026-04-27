FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121
ARG TORCH_VERSION=2.5.1
ARG TORCHVISION_VERSION=0.20.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-pip \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/common /app/common
COPY backend/flux_service /app/service

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir --index-url "${TORCH_INDEX_URL}" torch=="${TORCH_VERSION}" torchvision=="${TORCHVISION_VERSION}" && \
    python3 -m pip install --no-cache-dir -r /app/service/requirements.txt

ENV PYTHONPATH=/app
ENV HF_HOME=/models/huggingface

CMD ["python3", "-m", "uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8004"]
