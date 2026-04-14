#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not installed."
  exit 1
fi

tmux list-sessions 2>/dev/null | grep -E '^sci-(frontend|gateway|powerpaint|segmenter|planner)' || echo "No science-diagram tmux sessions found."
