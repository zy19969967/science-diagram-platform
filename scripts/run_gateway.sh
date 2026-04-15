#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda

export PYTHONPATH="${PROJECT_ROOT}/backend"
export PLANNER_URL="http://${PLANNER_HOST}:${PLANNER_PORT}"
export SEGMENTER_URL="http://${SEGMENTER_HOST}:${SEGMENTER_PORT}"
export POWERPAINT_URL="http://${POWERPAINT_HOST}:${POWERPAINT_PORT}"

run_in_conda_env "${CONDA_ENV_GATEWAY}" uvicorn gateway.main:app --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}"
