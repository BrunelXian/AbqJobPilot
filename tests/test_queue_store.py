import tempfile
import unittest
from pathlib import Path

from abqjobpilot import config
from abqjobpilot.queue_store import (
    add_inp_job_to_queue,
    load_queue,
    move_queued_job,
    remove_queued_job,
    remove_result_job,
    requeue_result_job,
    update_job,
)


class TestQueueStore(unittest.TestCase):
    def setUp(self):
        self._old_runtime = config.RUNTIME_DIR
        self._old_queue = config.QUEUE_FILE
        self._old_live = config.LIVE_STATUS_FILE
        self._old_settings = config.SETTINGS_FILE
        self.temp_dir = tempfile.TemporaryDirectory()
        runtime = Path(self.temp_dir.name) / "runtime"
        config.RUNTIME_DIR = str(runtime)
        config.QUEUE_FILE = str(runtime / "queue.json")
        config.LIVE_STATUS_FILE = str(runtime / "live_status.json")
        config.SETTINGS_FILE = str(runtime / "settings.json")
        self.inp_path = Path(self.temp_dir.name) / "batch" / "strategy" / "Job_test.inp"
        self.inp_path.parent.mkdir(parents=True)
        self.inp_path.write_text("*Heading\n", encoding="utf-8")

    def tearDown(self):
        config.RUNTIME_DIR = self._old_runtime
        config.QUEUE_FILE = self._old_queue
        config.LIVE_STATUS_FILE = self._old_live
        config.SETTINGS_FILE = self._old_settings
        self.temp_dir.cleanup()

    def test_failed_result_can_be_cleared_and_requeued(self):
        first = add_inp_job_to_queue(str(self.inp_path), cpus=14)
        self.assertTrue(first["ok"])
        update_job(first["queue_id"], {"status": "FAILED_FATAL", "phase": "FAILED_FATAL"})

        second = add_inp_job_to_queue(str(self.inp_path), cpus=14)
        self.assertTrue(second["ok"], second.get("message"))
        self.assertEqual(len(load_queue()), 2)

        cleared = remove_result_job(first["queue_id"])
        self.assertTrue(cleared["ok"])
        jobs = load_queue()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["queue_id"], second["queue_id"])

    def test_active_duplicate_is_still_rejected(self):
        first = add_inp_job_to_queue(str(self.inp_path), cpus=14)
        self.assertTrue(first["ok"])

        duplicate = add_inp_job_to_queue(str(self.inp_path), cpus=14)
        self.assertFalse(duplicate["ok"])
        self.assertIn("already exists", duplicate["message"])

    def test_requeue_keeps_resources_and_does_not_start_solver(self):
        first = add_inp_job_to_queue(
            str(self.inp_path), cpus=18, gpus=1, batch_name="batch-x", strategy_name="strategy-x",
            job_name="custom_name", run_datacheck=False, run_full=True, notes="retry",
        )
        update_job(first["queue_id"], {"status": "FAILED_FATAL", "phase": "FAILED_FATAL"})
        requeued = requeue_result_job(first["queue_id"])
        self.assertTrue(requeued["ok"], requeued.get("message"))
        self.assertNotEqual(requeued["queue_id"], first["queue_id"])
        self.assertEqual(requeued["job"]["status"], "QUEUED")
        for field in ("cpus", "gpus", "batch_name", "strategy_name", "job_name", "run_datacheck", "run_full", "notes"):
            self.assertEqual(requeued["job"][field], first["job"][field])
        self.assertEqual([job["status"] for job in load_queue()], ["FAILED_FATAL", "QUEUED"])

    def test_delete_result_and_remove_queue_record_leave_solver_files(self):
        odb = self.inp_path.with_suffix(".odb")
        odb.write_bytes(b"preserve")
        first = add_inp_job_to_queue(str(self.inp_path))
        self.assertFalse(remove_result_job(first["queue_id"])["ok"])
        self.assertTrue(remove_queued_job(first["queue_id"])["ok"])
        self.assertTrue(self.inp_path.exists())
        self.assertEqual(odb.read_bytes(), b"preserve")

        second = add_inp_job_to_queue(str(self.inp_path))
        update_job(second["queue_id"], {"status": "FAILED_FATAL"})
        self.assertTrue(remove_result_job(second["queue_id"])["ok"])
        self.assertTrue(self.inp_path.exists())
        self.assertEqual(odb.read_bytes(), b"preserve")

    def test_move_changes_only_pending_execution_order(self):
        first = add_inp_job_to_queue(str(self.inp_path))
        update_job(first["queue_id"], {"status": "FAILED_FATAL"})
        second_path = self.inp_path.with_name("Job_second.inp")
        third_path = self.inp_path.with_name("Job_third.inp")
        second_path.write_text("*Heading\n", encoding="utf-8")
        third_path.write_text("*Heading\n", encoding="utf-8")
        second = add_inp_job_to_queue(str(second_path))
        third = add_inp_job_to_queue(str(third_path))
        self.assertTrue(move_queued_job(third["queue_id"], "top")["ok"])
        self.assertEqual([job["queue_id"] for job in load_queue()],
                         [first["queue_id"], third["queue_id"], second["queue_id"]])
        self.assertTrue(move_queued_job(third["queue_id"], "down")["ok"])
        self.assertEqual([job["queue_id"] for job in load_queue()],
                         [first["queue_id"], second["queue_id"], third["queue_id"]])
        update_job(second["queue_id"], {"status": "FULL_RUNNING"})
        self.assertFalse(move_queued_job(third["queue_id"], "top")["ok"])
        self.assertFalse(remove_queued_job(third["queue_id"])["ok"])


if __name__ == "__main__":
    unittest.main()
