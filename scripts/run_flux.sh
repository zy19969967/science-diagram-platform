#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda

export PYTHONPATH="${PROJECT_ROOT}/backend"
export CUDA_VISIBLE_DEVICES="${FLUX_CUDA_VISIBLE_DEVICES}"
export HF_HOME
export FLUX_BACKEND
export FLUX_MODEL_REPO
export FLUX_MODEL_DTYPE
export FLUX_NUM_INFERENCE_STEPS
export FLUX_GUIDANCE_SCALE
export FLUX_MAX_SEQUENCE_LENGTH
export FLUX_LOCAL_FILES_ONLY

run_in_conda_env "${CONDA_ENV_FLUX}" uvicorn flux_service.main:app --host "${FLUX_HOST}" --port "${FLUX_PORT}"
