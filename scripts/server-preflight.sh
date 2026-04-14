#!/usr/bin/env bash
set -euo pipefail

echo "== Kernel =="
uname -a || true
echo

echo "== OS Release =="
cat /etc/os-release || true
echo

echo "== NVIDIA SMI =="
nvidia-smi || true
echo

echo "== Docker Version =="
docker --version || true
echo

echo "== Docker Compose Version =="
docker compose version || true
echo

echo "== NVIDIA Container Toolkit =="
nvidia-container-toolkit --version || dpkg -l | grep -E 'nvidia-container-toolkit|nvidia-docker' || true
echo

echo "== Memory =="
free -h || true
echo

echo "== Disk =="
df -h || true
echo

echo "== Network =="
ip -brief addr || true
echo

echo "== Docker Root Dir =="
if docker info >/tmp/science-diagram-docker-info.txt 2>/dev/null; then
  grep 'Docker Root Dir' /tmp/science-diagram-docker-info.txt || true
  rm -f /tmp/science-diagram-docker-info.txt
else
  echo "docker info failed. If this is a permission issue, try: sudo docker info | grep 'Docker Root Dir'"
fi
