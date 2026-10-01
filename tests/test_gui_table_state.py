import unittest

from abqjobpilot.gui_table_state import (
    queue_display_jobs,
    restore_iid,
    result_display_jobs,
    row_iid,
    selected_job_id,
)


class TestGuiTableState(unittest.TestCase):
    def test_queue_preserves_runner_order_and_identity(self):
        jobs = [
            {"queue_id": "old", "status": "QUEUED", "created_at": "2026-01-01T00:00:00"},
            {"queue_id": "done", "status": "COMPLETED_OK"},
            {"queue_id": "new", "status": "QUEUED", "created_at": "2026-05-01T00:00:00"},
        ]
        visible = queue_display_jobs(jobs)
        self.assertEqual([job["queue_id"] for job in visible], ["old", "new"])
        self.assertEqual(row_iid(visible[0]), "old")

    def test_results_newest_first_with_timestamp_fallbacks(self):
        jobs = [
            {"queue_id": "old", "status": "FAILED_FATAL", "ended_at": "2026-05-01T09:00:00"},
            {"queue_id": "no_end", "status": "FAILED_FATAL", "updated_at": "2026-05-03T09:00:00"},
            {"queue_id": "latest", "status": "COMPLETED_OK", "ended_at": "2026-05-04T09:00:00"},
            {"queue_id": "bad_date", "status": "FAILED_FATAL", "ended_at": "invalid"},
            {"queue_id": "queued", "status": "QUEUED", "created_at": "2026-05-05T09:00:00"},
        ]
        self.assertEqual([job["queue_id"] for job in result_display_jobs(jobs)],
                         ["latest", "no_end", "old", "bad_date"])
        self.assertEqual([job["queue_id"] for job in jobs],
                         ["old", "no_end", "latest", "bad_date", "queued"])

    def test_result_selection_restores_by_id_after_reorder(self):
        jobs = [
            {"queue_id": "b", "status": "FAILED_FATAL"},
            {"queue_id": "a", "status": "COMPLETED_OK"},
        ]
        selected = selected_job_id(row_iid(jobs[1], results=True), results=True)
        self.assertEqual(selected, "a")
        self.assertEqual(restore_iid(selected, list(reversed(jobs)), results=True), "result_a")
        self.assertIsNone(restore_iid(selected, [jobs[0]], results=True))


if __name__ == "__main__":
    unittest.main()
