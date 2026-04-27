from __future__ import annotations

import unittest

from gateway.jobs import JobStore


class JobStoreTest(unittest.TestCase):
    def test_create_and_update_job_snapshot(self) -> None:
        store = JobStore()

        created = store.create("Queued for generation")
        self.assertEqual(created.status, "CREATED")
        self.assertEqual(created.progress, 0.0)
        self.assertEqual(created.message, "Queued for generation")

        updated = store.update(
            created.job_id,
            status="EXECUTING",
            progress=0.65,
            message="PowerPaint is running",
        )
        self.assertEqual(updated.status, "EXECUTING")
        self.assertEqual(updated.progress, 0.65)
        self.assertEqual(updated.message, "PowerPaint is running")
        self.assertIsNotNone(store.get(created.job_id))

    def test_update_missing_job_raises_key_error(self) -> None:
        store = JobStore()

        with self.assertRaises(KeyError):
            store.update("missing", status="DONE")


if __name__ == "__main__":
    unittest.main()
