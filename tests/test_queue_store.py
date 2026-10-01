import tempfile
import unittest
from pathlib import Path

from abqjobpilot import config
from abqjobpilot.queue_store import add_inp_job_to_queue, load_queue, remove_result_job, update_job


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


if __name__ == "__main__":
    unittest.main()
