#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_venv_common.sh"

load_platform_env

cd "${PROJECT_ROOT}/frontend/dist"
exec "${PYTHON_BIN}" -m http.server "${FRONTEND_STATIC_PORT}" --bind "${FRONTEND_STATIC_HOST}"
