from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

H20_GPU_DEFAULTS = {
    "PROJECT_GPU_POOL": "0,1",
    "QWEN_IMAGE_CUDA_VISIBLE_DEVICES": "0",
    "POWERPAINT_CUDA_VISIBLE_DEVICES": "1",
    "PLANNER_CUDA_VISIBLE_DEVICES": "1",
    "SEGMENTER_CUDA_VISIBLE_DEVICES": "1",
    "FLUX_CUDA_VISIBLE_DEVICES": "1",
}


class H20DeploymentDefaultsTest(unittest.TestCase):
    def test_env_examples_default_to_two_h20_nvlink_gpus(self) -> None:
        for filename in (".env.example", ".env.server.example", ".env.nodocker.example"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            for key, value in H20_GPU_DEFAULTS.items():
                self.assertIn(f"{key}={value}", text, filename)

    def test_compose_defaults_match_two_h20_nvlink_gpu_layout(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("CUDA_VISIBLE_DEVICES: ${QWEN_IMAGE_CUDA_VISIBLE_DEVICES:-0}", compose)
        self.assertIn("CUDA_VISIBLE_DEVICES: ${POWERPAINT_CUDA_VISIBLE_DEVICES:-1}", compose)
        self.assertIn("CUDA_VISIBLE_DEVICES: ${PLANNER_CUDA_VISIBLE_DEVICES:-1}", compose)
        self.assertIn("CUDA_VISIBLE_DEVICES: ${SEGMENTER_CUDA_VISIBLE_DEVICES:-1}", compose)
        self.assertIn("CUDA_VISIBLE_DEVICES: ${FLUX_CUDA_VISIBLE_DEVICES:-1}", compose)

    def test_conda_defaults_match_two_h20_nvlink_gpu_layout(self) -> None:
        common = (ROOT / "scripts" / "_conda_common.sh").read_text(encoding="utf-8")

        self.assertIn('PROJECT_GPU_POOL="${PROJECT_GPU_POOL:-0,1}"', common)
        self.assertIn('QWEN_IMAGE_CUDA_VISIBLE_DEVICES="${QWEN_IMAGE_CUDA_VISIBLE_DEVICES:-0}"', common)
        self.assertIn('POWERPAINT_CUDA_VISIBLE_DEVICES="${POWERPAINT_CUDA_VISIBLE_DEVICES:-1}"', common)
        self.assertIn('PLANNER_CUDA_VISIBLE_DEVICES="${PLANNER_CUDA_VISIBLE_DEVICES:-1}"', common)
        self.assertIn('SEGMENTER_CUDA_VISIBLE_DEVICES="${SEGMENTER_CUDA_VISIBLE_DEVICES:-1}"', common)
        self.assertIn('FLUX_CUDA_VISIBLE_DEVICES="${FLUX_CUDA_VISIBLE_DEVICES:-1}"', common)

    def test_docs_describe_two_h20_nvlink_layout(self) -> None:
        docs = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "docs/server-deploy.md",
                "docs/server-conda-deploy.md",
                "docs/server-deployment-checklist.md",
                "docs/architecture.md",
                "docs/known-issues.md",
            )
        )

        self.assertIn("H20-NVLink 96GB", docs)
        self.assertIn("GPU 0", docs)
        self.assertIn("GPU 1", docs)
        self.assertIn("Qwen-Image", docs)
        self.assertIn("PowerPaint、planner、segmenter 和 FLUX", docs)


if __name__ == "__main__":
    unittest.main()
