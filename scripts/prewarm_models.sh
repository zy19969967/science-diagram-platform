#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_conda_common.sh"

load_platform_env
ensure_runtime_dirs
ensure_conda
require_conda_env "${CONDA_ENV_GATEWAY}"

TIMEOUT_SECONDS="${PREWARM_CURL_MAX_TIME:-1800}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

write_payloads() {
  PREWARM_TMP_DIR="${TMP_DIR}" \
  POWERPAINT_LOCAL_FILES_ONLY="${POWERPAINT_LOCAL_FILES_ONLY}" \
  "${CONDA_BIN}" run --no-capture-output -n "${CONDA_ENV_GATEWAY}" python - <<'PY'
import base64
import io
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw


def bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


tmp_dir = Path(os.environ["PREWARM_TMP_DIR"])
source = Image.new("RGB", (512, 512), "white")
draw = ImageDraw.Draw(source)
draw.rectangle((180, 150, 330, 340), outline="black", width=5)
draw.line((205, 150, 205, 90), fill="black", width=4)
draw.line((305, 150, 305, 90), fill="black", width=4)
draw.line((205, 90, 305, 90), fill="black", width=4)
draw.line((190, 235, 320, 235), fill="#2563eb", width=3)

mask = Image.new("L", (512, 512), 0)
ImageDraw.Draw(mask).rectangle((160, 120, 350, 360), fill=255)

image = data_url(source)
mask_image = data_url(mask)
scene_plan = {
    "diagram_type": "laboratory_process_diagram",
    "width": 512,
    "height": 512,
    "instruction": "画一个烧杯",
    "objects": [
        {
            "id": "obj_1",
            "name": "烧杯",
            "role": "container",
            "position": "center",
            "visual": "laboratory beaker",
        }
    ],
    "relations": [],
    "labels": ["烧杯"],
    "style": "clean scientific illustration, flat vector-like",
    "positive_prompt": "clean scientific diagram, laboratory beaker, white background",
    "negative_prompt": "photorealistic, watermark, blurry text",
    "render_text_as_vector": False,
    "candidate_count": 1,
    "seed": 123,
    "provider": "deterministic-fallback",
    "warnings": [],
}
payloads = {
    "planner.json": {
        "source_image": image,
        "instruction": "把烧杯画得更清晰",
        "preferred_task": "text-guided",
        "selected_asset_id": None,
        "canvas_hints": {},
    },
    "segmenter.json": {
        "source_image": image,
        "width": 512,
        "height": 512,
        "box": [160, 120, 350, 360],
    },
    "powerpaint.json": {
        "image": image,
        "mask_image": mask_image,
        "task": "text-guided",
        "prompt": "clean scientific beaker diagram",
        "negative_prompt": "photorealistic, watermark, blurry text",
        "steps": 1,
        "guidance_scale": 7.5,
        "fitting_degree": 0.85,
        "seed": 123,
        "local_files_only": bool_from_env("POWERPAINT_LOCAL_FILES_ONLY"),
    },
    "flux.json": {
        "scene_plan": scene_plan,
        "seed": 123,
        "provider": "flux-local",
    },
    "qwen-image.json": {
        "image": image,
        "prompt": "clean scientific beaker diagram with crisp edges",
        "negative_prompt": "photorealistic, watermark, blurry text",
        "num_inference_steps": 1,
        "true_cfg_scale": 4.0,
        "strength": 1.0,
        "seed": 123,
        "local_files_only": bool_from_env("QWEN_IMAGE_LOCAL_FILES_ONLY"),
    },
}

for filename, payload in payloads.items():
    (tmp_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
PY
}

post_json() {
  local name="$1"
  local url="$2"
  local payload_file="$3"
  local output_file="${TMP_DIR}/${name}.out"
  local http_code

  echo "== ${name} warmup =="
  http_code="$(curl -sS --max-time "${TIMEOUT_SECONDS}" -o "${output_file}" -w "%{http_code}" -X POST "${url}" \
    -H "Content-Type: application/json" \
    --data-binary "@${payload_file}" || true)"
  if [[ "${http_code}" == "000" || "${http_code}" -lt 200 || "${http_code}" -ge 300 ]]; then
    echo "${name} warmup failed with HTTP ${http_code}." >&2
    echo "Response body:" >&2
    cat "${output_file}" >&2 || true
    echo >&2
    exit 1
  fi
  echo "${name} warmup completed."
}

show_health() {
  local name="$1"
  local url="$2"
  echo "-- ${name} health --"
  curl -fsS --max-time 30 "${url}"
  echo
}

echo "Generating warmup payloads in ${TMP_DIR}"
write_payloads

post_json "planner" "http://${PLANNER_HOST}:${PLANNER_PORT}/plan" "${TMP_DIR}/planner.json"
show_health "planner" "http://${PLANNER_HOST}:${PLANNER_PORT}/health"

post_json "segmenter" "http://${SEGMENTER_HOST}:${SEGMENTER_PORT}/segment" "${TMP_DIR}/segmenter.json"
show_health "segmenter" "http://${SEGMENTER_HOST}:${SEGMENTER_PORT}/health"

post_json "powerpaint" "http://${POWERPAINT_HOST}:${POWERPAINT_PORT}/generate" "${TMP_DIR}/powerpaint.json"
show_health "powerpaint" "http://${POWERPAINT_HOST}:${POWERPAINT_PORT}/health"

post_json "flux" "http://${FLUX_HOST}:${FLUX_PORT}/generate" "${TMP_DIR}/flux.json"
show_health "flux" "http://${FLUX_HOST}:${FLUX_PORT}/health"

post_json "qwen-image" "http://${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/generate" "${TMP_DIR}/qwen-image.json"
show_health "qwen-image" "http://${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/health"

echo "== All service health =="
bash "${SCRIPT_DIR}/check_services.sh"
