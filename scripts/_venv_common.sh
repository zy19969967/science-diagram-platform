#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCI_PLATFORM_ENV_FILE:-${ROOT_DIR}/.env.nodocker}"

load_platform_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
  fi

  export PROJECT_ROOT="${PROJECT_ROOT:-${ROOT_DIR}}"
  export POWERPAINT_REPO_PATH="${POWERPAINT_REPO_PATH:-$(cd "${PROJECT_ROOT}/.." && pwd)/PowerPaint}"

  export GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"
  export GATEWAY_PORT="${GATEWAY_PORT:-8000}"
  export PLANNER_HOST="${PLANNER_HOST:-127.0.0.1}"
  export PLANNER_PORT="${PLANNER_PORT:-8001}"
  export POWERPAINT_HOST="${POWERPAINT_HOST:-127.0.0.1}"
  export POWERPAINT_PORT="${POWERPAINT_PORT:-8002}"
  export SEGMENTER_HOST="${SEGMENTER_HOST:-127.0.0.1}"
  export SEGMENTER_PORT="${SEGMENTER_PORT:-8003}"

  export FRONTEND_STATIC_HOST="${FRONTEND_STATIC_HOST:-0.0.0.0}"
  export FRONTEND_STATIC_PORT="${FRONTEND_STATIC_PORT:-8080}"
  export PUBLIC_GATEWAY_BASE_URL="${PUBLIC_GATEWAY_BASE_URL:-http://127.0.0.1:${GATEWAY_PORT}}"
  export VITE_API_BASE_URL="${VITE_API_BASE_URL:-${PUBLIC_GATEWAY_BASE_URL}}"

  export MODELS_DIR="${MODELS_DIR:-${PROJECT_ROOT}/models}"
  export HF_HOME="${HF_HOME:-${MODELS_DIR}/huggingface}"
  export RUNS_DIR="${RUNS_DIR:-${PROJECT_ROOT}/data/runs}"
  export ASSETS_DIR="${ASSETS_DIR:-${PROJECT_ROOT}/backend/assets}"

  export PYTHON_BIN="${PYTHON_BIN:-python3}"
  export TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"

  export POWERPAINT_CUDA_VISIBLE_DEVICES="${POWERPAINT_CUDA_VISIBLE_DEVICES:-4}"
  export PLANNER_CUDA_VISIBLE_DEVICES="${PLANNER_CUDA_VISIBLE_DEVICES:-5}"
  export SEGMENTER_CUDA_VISIBLE_DEVICES="${SEGMENTER_CUDA_VISIBLE_DEVICES:-6}"

  export PLANNER_BACKEND="${PLANNER_BACKEND:-qwen3.5}"
  export PLANNER_MODEL_REPO="${PLANNER_MODEL_REPO:-Qwen/Qwen3.5-4B}"
  export PLANNER_MODEL_DTYPE="${PLANNER_MODEL_DTYPE:-float16}"
  export PLANNER_MAX_NEW_TOKENS="${PLANNER_MAX_NEW_TOKENS:-320}"
  export PLANNER_ATTN_IMPL="${PLANNER_ATTN_IMPL:-sdpa}"
  export PLANNER_LOCAL_FILES_ONLY="${PLANNER_LOCAL_FILES_ONLY:-false}"

  export SEGMENTER_BACKEND="${SEGMENTER_BACKEND:-sam2}"
  export SEGMENTER_MODEL_REPO="${SEGMENTER_MODEL_REPO:-facebook/sam2.1-hiera-base-plus}"
  export SEGMENTER_MODEL_DTYPE="${SEGMENTER_MODEL_DTYPE:-float16}"
  export SEGMENTER_LOCAL_FILES_ONLY="${SEGMENTER_LOCAL_FILES_ONLY:-false}"
  export SEGMENTER_BOX_PADDING_RATIO="${SEGMENTER_BOX_PADDING_RATIO:-0.18}"
  export SEGMENTER_MASK_THRESHOLD="${SEGMENTER_MASK_THRESHOLD:-0.0}"
  export SEGMENTER_USE_PLACEMENT_BOX="${SEGMENTER_USE_PLACEMENT_BOX:-false}"

  export POWERPAINT_MODEL_REPO="${POWERPAINT_MODEL_REPO:-JunhaoZhuang/PowerPaint-v1}"
  export POWERPAINT_VERSION="${POWERPAINT_VERSION:-ppt-v1}"
  export POWERPAINT_MODEL_DIR_NAME="${POWERPAINT_MODEL_DIR_NAME:-ppt-v1}"
  export POWERPAINT_WEIGHT_DTYPE="${POWERPAINT_WEIGHT_DTYPE:-float16}"
  export POWERPAINT_LOCAL_FILES_ONLY="${POWERPAINT_LOCAL_FILES_ONLY:-false}"
}

ensure_runtime_dirs() {
  mkdir -p "${MODELS_DIR}/huggingface" "${MODELS_DIR}/powerpaint" "${RUNS_DIR}" "${PROJECT_ROOT}/logs"
}

activate_venv() {
  local env_name="$1"
  local activate_script="${PROJECT_ROOT}/${env_name}/bin/activate"
  if [[ ! -f "${activate_script}" ]]; then
    echo "Virtual environment not found: ${PROJECT_ROOT}/${env_name}" >&2
    echo "Run bash scripts/setup_venvs.sh first." >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "${activate_script}"
}
