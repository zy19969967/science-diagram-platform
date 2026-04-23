#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_conda

echo "System GPU visibility:"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader
else
  echo "nvidia-smi not found"
fi
echo

check_env() {
  local label="$1"
  local env_name="$2"
  local visible_devices="$3"

  echo "=== ${label} (${env_name}) ==="
  echo "CUDA_VISIBLE_DEVICES=${visible_devices}"

  if ! conda_env_exists "${env_name}"; then
    echo "Conda environment not found: ${env_name}"
    echo
    return
  fi

  CUDA_VISIBLE_DEVICES="${visible_devices}" run_conda run --no-capture-output -n "${env_name}" python -c '
import os
try:
    import torch
except Exception as exc:
    print(f"torch import failed: {exc}")
    raise

print("torch:", torch.__version__)
print("torch.version.cuda:", torch.version.cuda)
print("torch.cuda.is_available:", torch.cuda.is_available())
print("torch.cuda.device_count:", torch.cuda.device_count())
print("CUDA_VISIBLE_DEVICES:", os.environ.get("CUDA_VISIBLE_DEVICES"))
if torch.cuda.is_available():
    for idx in range(torch.cuda.device_count()):
        print(f"device[{idx}]:", torch.cuda.get_device_name(idx))
'
  echo
}

check_env "planner" "${CONDA_ENV_PLANNER}" "${PLANNER_CUDA_VISIBLE_DEVICES}"
check_env "segmenter" "${CONDA_ENV_SEGMENTER}" "${SEGMENTER_CUDA_VISIBLE_DEVICES}"
check_env "powerpaint" "${CONDA_ENV_POWERPAINT}" "${POWERPAINT_CUDA_VISIBLE_DEVICES}"
