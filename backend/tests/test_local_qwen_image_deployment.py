from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LocalQwenImageDeploymentTest(unittest.TestCase):
    def test_docker_compose_declares_qwen_image_service_and_gateway_url(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("  qwen-image:", compose)
        self.assertIn("profiles: [\"qwen-image\"]", compose)
        self.assertIn("backend/qwen_image_service/Dockerfile", compose)
        self.assertIn("QWEN_IMAGE_URL: ${QWEN_IMAGE_URL:-http://qwen-image:8005}", compose)
        self.assertIn("QWEN_IMAGE_MODEL_REPO: ${QWEN_IMAGE_MODEL_REPO:-Qwen/Qwen-Image-Edit}", compose)
        self.assertIn("QWEN_IMAGE_MODEL_DTYPE: ${QWEN_IMAGE_MODEL_DTYPE:-bfloat16}", compose)
        self.assertIn(
            "QWEN_IMAGE_NUM_INFERENCE_STEPS: ${QWEN_IMAGE_NUM_INFERENCE_STEPS:-50}",
            compose,
        )
        self.assertIn("QWEN_IMAGE_TRUE_CFG_SCALE: ${QWEN_IMAGE_TRUE_CFG_SCALE:-4.0}", compose)
        self.assertIn("QWEN_IMAGE_STRENGTH: ${QWEN_IMAGE_STRENGTH:-1.0}", compose)
        self.assertIn("QWEN_IMAGE_LOCAL_FILES_ONLY: ${QWEN_IMAGE_LOCAL_FILES_ONLY:-false}", compose)
        self.assertIn("CUDA_VISIBLE_DEVICES: ${QWEN_IMAGE_CUDA_VISIBLE_DEVICES:-", compose)
        self.assertIn("NVIDIA_VISIBLE_DEVICES: ${QWEN_IMAGE_CUDA_VISIBLE_DEVICES:-", compose)
        gateway_section = compose.split("  planner:", 1)[0]
        self.assertNotIn("      qwen-image:\n        condition: service_healthy", gateway_section)

    def test_conda_scripts_include_qwen_image_service(self) -> None:
        common = (ROOT / "scripts" / "_conda_common.sh").read_text(encoding="utf-8")
        setup = (ROOT / "scripts" / "setup_conda_envs.sh").read_text(encoding="utf-8")
        run_qwen_image = (ROOT / "scripts" / "run_qwen_image.sh").read_text(encoding="utf-8")
        start = (ROOT / "scripts" / "start_all_tmux.sh").read_text(encoding="utf-8")
        services = (ROOT / "scripts" / "check_services.sh").read_text(encoding="utf-8")
        gpu_check = (ROOT / "scripts" / "check_gpu_envs.sh").read_text(encoding="utf-8")
        prewarm = (ROOT / "scripts" / "prewarm_models.sh").read_text(encoding="utf-8")

        self.assertIn('QWEN_IMAGE_PORT="${QWEN_IMAGE_PORT:-19086}"', common)
        self.assertIn('CONDA_ENV_QWEN_IMAGE="${CONDA_ENV_QWEN_IMAGE:-sci-qwen-image}"', common)
        self.assertIn('QWEN_IMAGE_MODEL_REPO="${QWEN_IMAGE_MODEL_REPO:-Qwen/Qwen-Image-Edit}"', common)
        self.assertIn('QWEN_IMAGE_MODEL_DTYPE="${QWEN_IMAGE_MODEL_DTYPE:-bfloat16}"', common)
        self.assertIn('QWEN_IMAGE_NUM_INFERENCE_STEPS="${QWEN_IMAGE_NUM_INFERENCE_STEPS:-50}"', common)
        self.assertIn('QWEN_IMAGE_TRUE_CFG_SCALE="${QWEN_IMAGE_TRUE_CFG_SCALE:-4.0}"', common)
        self.assertIn('QWEN_IMAGE_STRENGTH="${QWEN_IMAGE_STRENGTH:-1.0}"', common)
        self.assertIn('QWEN_IMAGE_LOCAL_FILES_ONLY="${QWEN_IMAGE_LOCAL_FILES_ONLY:-false}"', common)

        self.assertIn("install_qwen_image", setup)
        self.assertIn("qwen_image_service/requirements.txt", setup)
        self.assertIn("uvicorn qwen_image_service.main:app", run_qwen_image)
        self.assertIn("QWEN_IMAGE_CUDA_VISIBLE_DEVICES", run_qwen_image)
        self.assertIn("run_qwen_image.sh", start)
        self.assertIn("${QWEN_IMAGE_HOST}:${QWEN_IMAGE_PORT}/health", services)
        self.assertIn('check_env "qwen-image"', gpu_check)
        self.assertIn("qwen-image", prewarm)

    def test_environment_examples_document_qwen_image_defaults(self) -> None:
        docker_env_files = (".env.example", ".env.server.example")
        nodocker_env_files = (".env.nodocker.example",)

        for filename in docker_env_files + nodocker_env_files:
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("QWEN_IMAGE_MODEL_REPO=Qwen/Qwen-Image-Edit", text)
            self.assertIn("QWEN_IMAGE_MODEL_DTYPE=bfloat16", text)
            self.assertIn("QWEN_IMAGE_NUM_INFERENCE_STEPS=50", text)
            self.assertIn("QWEN_IMAGE_TRUE_CFG_SCALE=4.0", text)
            self.assertIn("QWEN_IMAGE_STRENGTH=1.0", text)
            self.assertIn("QWEN_IMAGE_LOCAL_FILES_ONLY=false", text)
            self.assertIn("QWEN_IMAGE_CUDA_VISIBLE_DEVICES", text)

        for filename in nodocker_env_files:
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("QWEN_IMAGE_PORT=19086", text)
            self.assertIn("CONDA_ENV_QWEN_IMAGE=sci-qwen-image", text)

    def test_docs_describe_gpu_requirement_and_model_scope(self) -> None:
        docs = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "docs/deployment.md",
                "docs/architecture.md",
                "docs/known-issues.md",
            )
        )

        self.assertIn("Qwen-Image", docs)
        self.assertIn("Qwen/Qwen-Image-Edit", docs)
        self.assertIn("Qwen-Image-Edit-2511", docs)
        self.assertIn("第一版不默认使用 Qwen-Image-Edit-2511", docs)
        self.assertIn("80GB", docs)
        self.assertIn("H20-NVLink 96GB", docs)
        self.assertIn("GPU 0", docs)
        self.assertIn("GPU 1", docs)
        self.assertIn("QWEN_IMAGE_PORT=19086", docs)
        self.assertIn("bash scripts/run_qwen_image.sh", docs)


if __name__ == "__main__":
    unittest.main()
