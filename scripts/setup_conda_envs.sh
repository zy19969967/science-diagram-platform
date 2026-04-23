#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda

create_env() {
  local env_name="$1"
  if ! conda_env_exists "${env_name}"; then
    run_conda create -y -n "${env_name}" python="${CONDA_PYTHON_VERSION}"
  fi
}

install_cuda_torch() {
  local env_name="$1"
  run_conda run -n "${env_name}" python -m pip install \
    --index-url "${TORCH_INDEX_URL}" \
    torch=="${TORCH_VERSION}" \
    torchvision=="${TORCHVISION_VERSION}"
}

install_gateway() {
  create_env "${CONDA_ENV_GATEWAY}"
  run_conda run -n "${CONDA_ENV_GATEWAY}" python -m pip install --upgrade pip
  run_conda run -n "${CONDA_ENV_GATEWAY}" python -m pip install -r "${PROJECT_ROOT}/backend/gateway/requirements.txt"
}

install_planner() {
  create_env "${CONDA_ENV_PLANNER}"
  run_conda run -n "${CONDA_ENV_PLANNER}" python -m pip install --upgrade pip
  install_cuda_torch "${CONDA_ENV_PLANNER}"
  run_conda run -n "${CONDA_ENV_PLANNER}" python -m pip install -r "${PROJECT_ROOT}/backend/planner/requirements.txt"
}

install_segmenter() {
  create_env "${CONDA_ENV_SEGMENTER}"
  run_conda run -n "${CONDA_ENV_SEGMENTER}" python -m pip install --upgrade pip
  install_cuda_torch "${CONDA_ENV_SEGMENTER}"
  run_conda run -n "${CONDA_ENV_SEGMENTER}" python -m pip install -r "${PROJECT_ROOT}/backend/segmenter/requirements.txt"
}

ensure_powerpaint_repo() {
  if [[ -d "${POWERPAINT_REPO_PATH}/.git" ]]; then
    return
  fi
  git clone --depth 1 "${POWERPAINT_REPO_GIT_URL}" "${POWERPAINT_REPO_PATH}"
}

install_powerpaint() {
  ensure_powerpaint_repo
  create_env "${CONDA_ENV_POWERPAINT}"
  run_conda run -n "${CONDA_ENV_POWERPAINT}" python -m pip install --upgrade pip
  install_cuda_torch "${CONDA_ENV_POWERPAINT}"
  run_conda run -n "${CONDA_ENV_POWERPAINT}" python -m pip install -r "${PROJECT_ROOT}/backend/powerpaint_service/requirements.txt"
  run_conda run -n "${CONDA_ENV_POWERPAINT}" python -m pip install -r "${POWERPAINT_REPO_PATH}/requirements/requirements.txt"
  install_cuda_torch "${CONDA_ENV_POWERPAINT}"
}

install_frontend() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found; skipping frontend dependency installation." >&2
    return
  fi
  cd "${PROJECT_ROOT}/frontend"
  npm install
}

install_gateway
install_planner
install_segmenter
install_powerpaint
install_frontend

cat <<EOF
Setup finished.

Next steps:
1. Copy .env.nodocker.example to .env.nodocker and edit PUBLIC_GATEWAY_BASE_URL / GPU ids if needed.
2. If conda is not on PATH, set CONDA_BIN in .env.nodocker to the full conda executable path.
3. Confirm the Conda env names if you customized them:
   ${CONDA_ENV_GATEWAY}
   ${CONDA_ENV_PLANNER}
   ${CONDA_ENV_SEGMENTER}
   ${CONDA_ENV_POWERPAINT}
4. If you are using PowerPaint 2.1 with git download, prefetch the weights with:
   bash scripts/fetch_powerpaint_model.sh
5. Start services with:
   bash scripts/run_planner.sh
   bash scripts/run_segmenter.sh
   bash scripts/run_powerpaint.sh
   bash scripts/run_gateway.sh
6. Build the frontend with:
   bash scripts/build_frontend.sh
7. Optionally serve the built frontend with:
   bash scripts/serve_frontend.sh
EOF
