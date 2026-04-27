from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LocalFluxDeploymentTest(unittest.TestCase):
    def test_docker_compose_runs_local_flux_service(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("  flux:", compose)
        self.assertIn("backend/flux_service/Dockerfile", compose)
        self.assertIn("FLUX_INIT_URL: ${FLUX_INIT_URL:-http://flux:8004}", compose)
        self.assertIn("FLUX_MODEL_REPO", compose)
        self.assertIn("FLUX_CUDA_VISIBLE_DEVICES", compose)
        self.assertIn("condition: service_healthy", compose)

    def test_conda_scripts_include_local_flux_service(self) -> None:
        setup = (ROOT / "scripts" / "setup_conda_envs.sh").read_text(encoding="utf-8")
        common = (ROOT / "scripts" / "_conda_common.sh").read_text(encoding="utf-8")
        start = (ROOT / "scripts" / "start_all_tmux.sh").read_text(encoding="utf-8")
        services = (ROOT / "scripts" / "check_services.sh").read_text(encoding="utf-8")

        self.assertIn("CONDA_ENV_FLUX", common)
        self.assertIn("FLUX_PORT", common)
        self.assertIn("install_flux", setup)
        self.assertIn("run_flux.sh", start)
        self.assertIn("${FLUX_HOST}:${FLUX_PORT}/health", services)

    def test_environment_examples_document_local_flux_defaults(self) -> None:
        for filename in (".env.example", ".env.server.example", ".env.nodocker.example"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("FLUX_MODEL_REPO", text)
            self.assertIn("FLUX_CUDA_VISIBLE_DEVICES", text)
            self.assertIn("FLUX_LOCAL_FILES_ONLY", text)


if __name__ == "__main__":
    unittest.main()
