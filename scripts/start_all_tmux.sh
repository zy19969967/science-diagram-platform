#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_venv_common.sh"

load_platform_env
ensure_runtime_dirs

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required for start_all_tmux.sh. Please install tmux or start services manually." >&2
  exit 1
fi

start_session() {
  local session_name="$1"
  local command="$2"
  if tmux has-session -t "${session_name}" 2>/dev/null; then
    echo "tmux session already exists: ${session_name}"
    return
  fi
  tmux new-session -d -s "${session_name}" "cd '${PROJECT_ROOT}' && ${command}"
}

mkdir -p "${PROJECT_ROOT}/logs"

start_session sci-planner "bash scripts/run_planner.sh >> logs/planner.log 2>&1"
start_session sci-segmenter "bash scripts/run_segmenter.sh >> logs/segmenter.log 2>&1"
start_session sci-powerpaint "bash scripts/run_powerpaint.sh >> logs/powerpaint.log 2>&1"
sleep 3
start_session sci-gateway "bash scripts/run_gateway.sh >> logs/gateway.log 2>&1"

if [[ "${1:-}" == "--with-frontend" ]]; then
  start_session sci-frontend "bash scripts/serve_frontend.sh >> logs/frontend.log 2>&1"
fi

echo "tmux sessions launched. Current status:"
bash "${SCRIPT_DIR}/status_tmux.sh"
