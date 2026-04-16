#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs

POWERPAINT_CHECKPOINT_DIR="${MODELS_DIR}/powerpaint/${POWERPAINT_MODEL_DIR_NAME}"
POWERPAINT_MODEL_GIT_URL="${POWERPAINT_MODEL_GIT_URL:-https://huggingface.co/${POWERPAINT_MODEL_REPO}}"

cat <<EOF
PowerPaint code repo:
  ${POWERPAINT_REPO_GIT_URL}
PowerPaint weight repo (Git LFS on Hugging Face):
  ${POWERPAINT_MODEL_GIT_URL}

This script only prepares the model weights. Cloning the GitHub code repo alone does not include the v2 checkpoints.
EOF

if ! command -v git >/dev/null 2>&1; then
  echo "git is required for fetch_powerpaint_model.sh." >&2
  exit 1
fi

if ! git lfs version >/dev/null 2>&1; then
  echo "git-lfs is required for fetch_powerpaint_model.sh. Please install git-lfs first." >&2
  exit 1
fi

mkdir -p "$(dirname "${POWERPAINT_CHECKPOINT_DIR}")"

if [[ -d "${POWERPAINT_CHECKPOINT_DIR}/.git" ]]; then
  git -C "${POWERPAINT_CHECKPOINT_DIR}" pull --ff-only
  git -C "${POWERPAINT_CHECKPOINT_DIR}" lfs pull
else
  if [[ -d "${POWERPAINT_CHECKPOINT_DIR}" && -n "$(ls -A "${POWERPAINT_CHECKPOINT_DIR}" 2>/dev/null)" ]]; then
    echo "${POWERPAINT_CHECKPOINT_DIR} already exists but is not a git repository." >&2
    echo "Move it aside or clear it before downloading the PowerPaint model with git." >&2
    exit 1
  fi

  if [[ -d "${POWERPAINT_CHECKPOINT_DIR}" ]]; then
    rmdir "${POWERPAINT_CHECKPOINT_DIR}"
  fi

  git lfs install
  git clone "${POWERPAINT_MODEL_GIT_URL}" "${POWERPAINT_CHECKPOINT_DIR}"
  git -C "${POWERPAINT_CHECKPOINT_DIR}" lfs pull
fi

cat <<EOF
PowerPaint model is ready at:
  ${POWERPAINT_CHECKPOINT_DIR}

Recommended follow-up:
  1. Set POWERPAINT_LOCAL_FILES_ONLY=true in .env.nodocker after the weights are present.
  2. Start the service with bash scripts/run_powerpaint.sh
EOF
