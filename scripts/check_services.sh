#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env

curl -fsS "http://${PLANNER_HOST}:${PLANNER_PORT}/health"
echo
curl -fsS "http://${SEGMENTER_HOST}:${SEGMENTER_PORT}/health"
echo
curl -fsS "http://${POWERPAINT_HOST}:${POWERPAINT_PORT}/health"
echo
curl -fsS "http://${GATEWAY_HOST}:${GATEWAY_PORT}/api/health"
echo
