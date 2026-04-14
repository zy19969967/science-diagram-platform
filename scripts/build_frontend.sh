#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_venv_common.sh"

load_platform_env

if [[ "${VITE_API_BASE_URL}" == *"YOUR_SERVER_IP"* ]]; then
  echo "Please set PUBLIC_GATEWAY_BASE_URL or VITE_API_BASE_URL in .env.nodocker before building the frontend." >&2
  exit 1
fi

cd "${PROJECT_ROOT}/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
export VITE_API_BASE_URL
exec npm run build
