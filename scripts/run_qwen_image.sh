#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda

if [[ ! -d "${PROJECT_ROOT}/backend/qwen_image_service" ]]; then
  echo "backend/qwen_image_service is not present yet. Add the Qwen-Image service before starting this process." >&2
  exit 1
fi

export PYTHONPATH="${PROJECT_ROOT}/backend"
export CUDA_VISIBLE_DEVICES="${QWEN_IMAGE_CUDA_VISIBLE_DEVICES}"
export HF_HOME
export HF_ENDPOINT
export QWEN_IMAGE_MODEL_REPO
export QWEN_IMAGE_MODEL_DTYPE
export QWEN_IMAGE_NUM_INFERENCE_STEPS
export QWEN_IMAGE_TRUE_CFG_SCALE
export QWEN_IMAGE_STRENGTH
export QWEN_IMAGE_LOCAL_FILES_ONLY

run_in_conda_env "${CONDA_ENV_QWEN_IMAGE}" uvicorn qwen_image_service.main:app --host "${QWEN_IMAGE_HOST}" --port "${QWEN_IMAGE_PORT}"
