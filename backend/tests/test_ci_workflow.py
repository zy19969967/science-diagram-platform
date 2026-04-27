from __future__ import annotations

import unittest
from pathlib import Path


class CIWorkflowTest(unittest.TestCase):
    def test_ci_workflow_runs_backend_and_frontend_checks(self) -> None:
        workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
        text = workflow.read_text(encoding="utf-8")

        self.assertIn("Backend validation", text)
        self.assertIn("Frontend validation", text)
        self.assertIn("backend/gateway/requirements.txt", text)
        self.assertIn("python -m unittest discover -s backend/tests -p 'test_*.py' -v", text)
        self.assertIn("python -m py_compile", text)
        self.assertIn("backend/gateway/projects.py", text)
        self.assertIn("Import backend modules", text)
        self.assertIn("import gateway.projects", text)
        self.assertIn("import gateway.main", text)
        self.assertIn("npm install", text)
        self.assertIn("node tests/canvasState.test.mjs", text)
        self.assertIn("node tests/projectState.test.mjs", text)
        self.assertIn("npm run build", text)
        self.assertIn("git diff --check", text)
        self.assertIn("BASE_REF", text)
        self.assertIn("BEFORE_SHA", text)
        self.assertIn('"origin/$BASE_REF...HEAD"', text)
        self.assertIn('"$BEFORE_SHA" HEAD', text)
        self.assertNotIn("docker build", text.lower())
        self.assertNotIn("cuda", text.lower())


if __name__ == "__main__":
    unittest.main()
