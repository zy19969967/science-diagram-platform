#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda

export PYTHONPATH="${PROJECT_ROOT}/backend"
export CUDA_VISIBLE_DEVICES="${PLANNER_CUDA_VISIBLE_DEVICES}"

run_in_conda_env "${CONDA_ENV_PLANNER}" uvicorn planner.main:app --host "${PLANNER_HOST}" --port "${PLANNER_PORT}"
