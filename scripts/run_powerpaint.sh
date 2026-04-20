#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda
patch_powerpaint_repo

export PYTHONPATH="${PROJECT_ROOT}/backend:${POWERPAINT_REPO_PATH}"
export CUDA_VISIBLE_DEVICES="${POWERPAINT_CUDA_VISIBLE_DEVICES}"
export POWERPAINT_CHECKPOINT_DIR="${MODELS_DIR}/powerpaint/${POWERPAINT_MODEL_DIR_NAME}"

run_in_conda_env "${CONDA_ENV_POWERPAINT}" uvicorn powerpaint_service.main:app --host "${POWERPAINT_HOST}" --port "${POWERPAINT_PORT}"
