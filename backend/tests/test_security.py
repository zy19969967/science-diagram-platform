from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ASSETS_DIR", str(Path(__file__).resolve().parents[1] / "assets"))
os.environ.setdefault("RUNS_DIR", "/tmp/science-diagram-test-runs")
os.environ.setdefault("PROJECTS_DIR", "/tmp/science-diagram-test-projects")
os.environ.setdefault("JOBS_DIR", "/tmp/science-diagram-test-jobs")
os.environ.setdefault("BENCHMARKS_DIR", "/tmp/science-diagram-test-benchmarks")

from fastapi.testclient import TestClient

from gateway import main as gateway_main
from gateway.projects import ProjectStore
from gateway.security import GatewayAuthConfig


class GatewaySecurityTest(unittest.TestCase):
    def tearDown(self) -> None:
        gateway_main.gateway_auth = GatewayAuthConfig("")

    def test_gateway_remains_open_when_api_token_is_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway_main.project_store = ProjectStore(Path(temp_dir))
            gateway_main.gateway_auth = GatewayAuthConfig("")
            client = TestClient(gateway_main.app)

            response = client.get("/api/projects")

            self.assertEqual(response.status_code, 200)

    def test_gateway_protects_api_routes_when_api_token_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway_main.project_store = ProjectStore(Path(temp_dir))
            gateway_main.gateway_auth = GatewayAuthConfig("secret-token")
            client = TestClient(gateway_main.app)

            health_response = client.get("/api/health")
            unauthorized_response = client.get("/api/projects")
            bearer_response = client.get("/api/projects", headers={"Authorization": "Bearer secret-token"})
            token_header_response = client.get("/api/projects", headers={"X-API-Token": "secret-token"})

            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(unauthorized_response.status_code, 401)
            self.assertEqual(unauthorized_response.json()["detail"], "Gateway API token is required.")
            self.assertEqual(bearer_response.status_code, 200)
            self.assertEqual(token_header_response.status_code, 200)

    def test_readiness_reports_auth_storage_services_and_traceability(self) -> None:
        gateway_main.gateway_auth = GatewayAuthConfig("secret-token")
        client = TestClient(gateway_main.app)

        response = client.get("/api/deployment/readiness", headers={"Authorization": "Bearer secret-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["auth"]["enabled"], True)
        self.assertIn(body["status"], {"pass", "warn"})
        check_names = {item["name"] for item in body["checks"]}
        self.assertIn("runs_dir", check_names)
        self.assertIn("projects_dir", check_names)
        self.assertIn("jobs_dir", check_names)
        self.assertIn("benchmarks_dir", check_names)
        self.assertIn("assets_dir", check_names)
        self.assertIn("planner_url", check_names)
        self.assertIn("flux_init_url", check_names)
        self.assertIn("traceability_matrix", check_names)

    def test_readiness_warns_when_auth_is_disabled(self) -> None:
        gateway_main.gateway_auth = GatewayAuthConfig("")
        client = TestClient(gateway_main.app)

        response = client.get("/api/deployment/readiness")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["auth"]["enabled"], False)
        self.assertIn("GATEWAY_API_TOKEN is not configured.", body["warnings"])


if __name__ == "__main__":
    unittest.main()
