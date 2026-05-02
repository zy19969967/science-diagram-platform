#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda

POWERPAINT_CHECKPOINT_DIR="${MODELS_DIR}/powerpaint/${POWERPAINT_MODEL_DIR_NAME}"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

cat <<EOF
PowerPaint code repo:
  ${POWERPAINT_REPO_GIT_URL}
PowerPaint weight repo:
  ${POWERPAINT_MODEL_REPO}
PowerPaint weight download target:
  ${POWERPAINT_CHECKPOINT_DIR}

This script only prepares the model weights. Cloning the GitHub code repo alone does not include the PowerPaint 2.1 checkpoints.
EOF

require_conda_env "${CONDA_ENV_POWERPAINT}"

mkdir -p "$(dirname "${POWERPAINT_CHECKPOINT_DIR}")"

if [[ -d "${POWERPAINT_CHECKPOINT_DIR}/.git" ]]; then
  BACKUP_DIR="${POWERPAINT_CHECKPOINT_DIR}.git-lfs-backup-$(date +%Y%m%d-%H%M%S)"
  echo "Existing Git LFS checkout found at ${POWERPAINT_CHECKPOINT_DIR}."
  echo "Moving it aside to ${BACKUP_DIR} before using huggingface-cli download."
  mv "${POWERPAINT_CHECKPOINT_DIR}" "${BACKUP_DIR}"
fi

mkdir -p "${POWERPAINT_CHECKPOINT_DIR}"

run_conda run --no-capture-output -n "${CONDA_ENV_POWERPAINT}" \
  huggingface-cli download "${POWERPAINT_MODEL_REPO}" \
  --repo-type model \
  --local-dir "${POWERPAINT_CHECKPOINT_DIR}" \
  --local-dir-use-symlinks False \
  --resume-download

cat <<EOF
PowerPaint model is ready at:
  ${POWERPAINT_CHECKPOINT_DIR}

Recommended follow-up:
  1. Set POWERPAINT_LOCAL_FILES_ONLY=true in .env.nodocker after the weights are present.
  2. Start the service with bash scripts/run_powerpaint.sh
EOF
