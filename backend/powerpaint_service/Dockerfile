FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ARG POWERPAINT_GIT_REF=main
ARG POWERPAINT_REPO_GIT_URL=https://github.com/zhuang2002/PowerPaint.git

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-pip \
    git \
    git-lfs \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN git lfs install
RUN git clone --depth 1 --branch ${POWERPAINT_GIT_REF} ${POWERPAINT_REPO_GIT_URL} /opt/PowerPaint

WORKDIR /app

COPY backend/common /app/common
COPY backend/powerpaint_service /app/service

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r /app/service/requirements.txt && \
    python3 -m pip install --no-cache-dir -r /opt/PowerPaint/requirements/requirements.txt

ENV PYTHONPATH=/app:/opt/PowerPaint
ENV POWERPAINT_REPO_PATH=/opt/PowerPaint
ENV POWERPAINT_REPO_GIT_URL=https://github.com/zhuang2002/PowerPaint.git
ENV POWERPAINT_CHECKPOINT_DIR=/models/powerpaint/ppt-v2-1
ENV POWERPAINT_MODEL_REPO=JunhaoZhuang/PowerPaint-v2-1
ENV POWERPAINT_MODEL_GIT_URL=https://huggingface.co/JunhaoZhuang/PowerPaint-v2-1
ENV POWERPAINT_DOWNLOAD_METHOD=git
ENV POWERPAINT_VERSION=ppt-v2
ENV HF_HOME=/models/huggingface

CMD ["python3", "-m", "uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8002"]
