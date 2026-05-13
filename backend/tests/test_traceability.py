from __future__ import annotations

import unittest
from pathlib import Path


class TraceabilityDocumentTest(unittest.TestCase):
    def test_report_traceability_matrix_covers_all_alignment_phases(self) -> None:
        document = Path(__file__).resolve().parents[2] / "docs" / "report-traceability.md"
        text = document.read_text(encoding="utf-8")

        for phase in range(1, 14):
            self.assertIn(f"Phase {phase}", text)

        self.assertIn("/api/init-plan", text)
        self.assertIn("/api/jobs", text)
        self.assertIn("/api/benchmarks/summary", text)
        self.assertIn("/api/deployment/readiness", text)
        self.assertIn("GATEWAY_API_TOKEN", text)
        self.assertIn("已知限制", text)
        self.assertNotIn("TODO", text)
        self.assertNotIn("TBD", text)


if __name__ == "__main__":
    unittest.main()
