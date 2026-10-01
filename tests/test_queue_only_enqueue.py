import inspect
import json
import tempfile
import unittest
from pathlib import Path

from abqjobpilot.api import AbqJobPilotClient, JobRequest
import abqjobpilot.api.client as client_module


class QueueOnlyRuntimeMixin:
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.runtime_dir = self.root / "runtime"
        self.inp_path = self.root / "batch01" / "strategy01" / "Job_queue_only.inp"
        self.inp_path.parent.mkdir(parents=True)
        self.inp_path.write_text("*Heading\n", encoding="utf-8")
        self.client = AbqJobPilotClient(runtime_dir=str(self.runtime_dir))

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(self, **kwargs):
        data = {
            "inp_path": str(self.inp_path),
            "cpus": 14,
            "batch": "batch01",
            "strategy": "strategy01",
            "submission_mode": "enqueue_only",
            "allow_solver_submit": False,
        }
        data.update(kwargs)
        return JobRequest(**data)


class TestQueueOnlyEnqueue(QueueOnlyRuntimeMixin, unittest.TestCase):
    def test_dry_run_reports_queue_only_without_mutation(self):
        result = self.client.enqueue(self.request(submission_mode="preview_only"), dry_run=True)

        self.assertEqual(result.status, "DRY_RUN_READY")
        self.assertTrue(result.queue_only)
        self.assertFalse(result.queue_file_mutated)
        self.assertFalse(result.solver_started)
        self.assertFalse(result.runner_started)
        self.assertFalse(result.gui_required)
        self.assertFalse((self.runtime_dir / "queue.json").exists())

    def test_enqueue_only_writes_only_queue_json(self):
        result = self.client.enqueue(self.request(), dry_run=False)

        self.assertEqual(result.status, "ENQUEUED")
        self.assertTrue(result.queue_only)
        self.assertTrue(result.queue_file_mutated)
        self.assertFalse(result.solver_started)
        self.assertFalse(result.runner_started)
        self.assertFalse(result.gui_required)
        self.assertFalse(result.forbidden_mutations_detected)
        self.assertEqual(result.allowed_mutations, ["runtime/queue.json"])
        self.assertTrue((self.runtime_dir / "queue.json").exists())
        self.assertFalse((self.runtime_dir / "live_status.json").exists())
        self.assertFalse((self.runtime_dir / "reports").exists())

        queue = json.loads((self.runtime_dir / "queue.json").read_text(encoding="utf-8"))
        self.assertEqual(queue["schema_version"], "1.0")
        self.assertEqual(len(queue["jobs"]), 1)
        self.assertEqual(queue["jobs"][0]["status"], "QUEUED")
        self.assertEqual(queue["jobs"][0]["phase"], "QUEUED")

    def test_unsafe_allow_solver_submit_rejected_before_queue_write(self):
        result = self.client.enqueue(self.request(allow_solver_submit=True), dry_run=False)

        self.assertEqual(result.status, "REJECTED_UNSAFE_DIRECT_SUBMIT")
        self.assertFalse((self.runtime_dir / "queue.json").exists())

    def test_unsafe_submit_mode_rejected_before_queue_write(self):
        result = self.client.enqueue(self.request(submission_mode="submit"), dry_run=False)

        self.assertEqual(result.status, "REJECTED_UNSAFE_DIRECT_SUBMIT")
        self.assertFalse((self.runtime_dir / "queue.json").exists())

    def test_live_status_mutation_is_forbidden(self):
        before = client_module.snapshot_runtime(str(self.runtime_dir))
        self.runtime_dir.mkdir(parents=True)
        (self.runtime_dir / "live_status.json").write_text("{}", encoding="utf-8")
        after = client_module.snapshot_runtime(str(self.runtime_dir))

        comparison = client_module.compare_runtime_snapshots(before, after)

        self.assertTrue(comparison["forbidden_mutations_detected"])
        self.assertIn("live_status.json", comparison["forbidden_mutations"])

    def test_reports_mutation_is_forbidden(self):
        before = client_module.snapshot_runtime(str(self.runtime_dir))
        reports = self.runtime_dir / "reports"
        reports.mkdir(parents=True)
        (reports / "report.json").write_text("{}", encoding="utf-8")
        after = client_module.snapshot_runtime(str(self.runtime_dir))

        comparison = client_module.compare_runtime_snapshots(before, after)

        self.assertTrue(comparison["forbidden_mutations_detected"])
        self.assertIn("reports", comparison["forbidden_mutations"])

    def test_api_client_source_has_no_execution_launchers(self):
        source = inspect.getsource(client_module)

        forbidden = [
            "subprocess",
            "Popen",
            "os.system",
            "shell=True",
            "QueueRunner",
            "run_next_job",
            "run_gui",
            "tkinter",
            "PyQt",
            "PySide",
            "customtkinter",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
