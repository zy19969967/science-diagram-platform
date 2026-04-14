#!/usr/bin/env bash
set -euo pipefail

sessions=(sci-frontend sci-gateway sci-powerpaint sci-segmenter sci-planner)

for session in "${sessions[@]}"; do
  if tmux has-session -t "${session}" 2>/dev/null; then
    tmux kill-session -t "${session}"
    echo "Stopped ${session}"
  fi
done
