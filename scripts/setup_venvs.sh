#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_venv_common.sh"

load_platform_env
ensure_runtime_dirs

create_env() {
  local env_name="$1"
  if [[ ! -d "${PROJECT_ROOT}/${env_name}" ]]; then
    "${PYTHON_BIN}" -m venv "${PROJECT_ROOT}/${env_name}"
  fi
}

install_gateway() {
  create_env ".venv-gateway"
  activate_venv ".venv-gateway"
  pip install --upgrade pip
  pip install -r "${PROJECT_ROOT}/backend/gateway/requirements.txt"
  deactivate
}

install_planner() {
  create_env ".venv-planner"
  activate_venv ".venv-planner"
  pip install --upgrade pip
  pip install --index-url "${TORCH_INDEX_URL}" torch==2.5.1 torchvision==0.20.1
  pip install -r "${PROJECT_ROOT}/backend/planner/requirements.txt"
  deactivate
}

install_segmenter() {
  create_env ".venv-segmenter"
  activate_venv ".venv-segmenter"
  pip install --upgrade pip
  pip install --index-url "${TORCH_INDEX_URL}" torch==2.5.1 torchvision==0.20.1
  pip install -r "${PROJECT_ROOT}/backend/segmenter/requirements.txt"
  deactivate
}

ensure_powerpaint_repo() {
  if [[ -d "${POWERPAINT_REPO_PATH}/.git" ]]; then
    return
  fi
  git clone --depth 1 https://github.com/open-mmlab/PowerPaint.git "${POWERPAINT_REPO_PATH}"
}

install_powerpaint() {
  ensure_powerpaint_repo
  create_env ".venv-powerpaint"
  activate_venv ".venv-powerpaint"
  pip install --upgrade pip
  pip install -r "${PROJECT_ROOT}/backend/powerpaint_service/requirements.txt"
  pip install -r "${POWERPAINT_REPO_PATH}/requirements/requirements.txt"
  deactivate
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
2. Start services with:
   bash scripts/run_planner.sh
   bash scripts/run_segmenter.sh
   bash scripts/run_powerpaint.sh
   bash scripts/run_gateway.sh
3. Build the frontend with:
   bash scripts/build_frontend.sh
4. Optionally serve the built frontend with:
   bash scripts/serve_frontend.sh
EOF
