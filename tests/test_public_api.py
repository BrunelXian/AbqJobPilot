import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from abqjobpilot import config
from abqjobpilot.api import AbqJobPilotClient, JobRequest


class ConfigRuntimeMixin:
    def setUp(self):
        self._old_runtime = config.RUNTIME_DIR
        self._old_queue = config.QUEUE_FILE
        self._old_live = config.LIVE_STATUS_FILE
        self._old_settings = config.SETTINGS_FILE
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        runtime = self.root / "runtime"
        config.RUNTIME_DIR = str(runtime)
        config.QUEUE_FILE = str(runtime / "queue.json")
        config.LIVE_STATUS_FILE = str(runtime / "live_status.json")
        config.SETTINGS_FILE = str(runtime / "settings.json")
        self.inp_path = self.root / "batch01" / "strategy01" / "Job_test.inp"
        self.inp_path.parent.mkdir(parents=True)
        self.inp_path.write_text("*Heading\n", encoding="utf-8")
        self.client = AbqJobPilotClient()

    def tearDown(self):
        config.RUNTIME_DIR = self._old_runtime
        config.QUEUE_FILE = self._old_queue
        config.LIVE_STATUS_FILE = self._old_live
        config.SETTINGS_FILE = self._old_settings
        self.temp_dir.cleanup()


class TestPublicApi(ConfigRuntimeMixin, unittest.TestCase):
    def test_job_request_defaults_are_safe(self):
        request = JobRequest(inp_path=str(self.inp_path))
        self.assertEqual(request.submission_mode, "preview_only")
        self.assertFalse(request.allow_solver_submit)

    def test_preflight_ready_for_existing_fixture(self):
        result = self.client.preflight(JobRequest(inp_path=str(self.inp_path), cpus=14, batch="batch01", strategy="strategy01"))
        self.assertEqual(result.status, "PREVIEW_READY")
        self.assertTrue(result.inp_exists)
        self.assertEqual(result.job_name, "Job_test")
        self.assertIn("DATACHECK:", result.command_preview)
        self.assertIn("FULL_RUN:", result.command_preview)

    def test_preflight_invalid_for_missing_inp(self):
        missing = self.root / "batch01" / "strategy01" / "missing.inp"
        result = self.client.preflight(JobRequest(inp_path=str(missing), cpus=14))
        self.assertEqual(result.status, "INVALID_REQUEST")
        self.assertFalse(result.inp_exists)
        self.assertTrue(result.errors)

    def test_preflight_does_not_mutate_queue_files(self):
        queue_path = Path(config.QUEUE_FILE)
        self.assertFalse(queue_path.exists())
        self.client.preflight(JobRequest(inp_path=str(self.inp_path), cpus=14))
        self.assertFalse(queue_path.exists())

    def test_enqueue_dry_run_ready(self):
        result = self.client.enqueue(JobRequest(inp_path=str(self.inp_path), cpus=14), dry_run=True)
        self.assertEqual(result.status, "DRY_RUN_READY")
        self.assertTrue(result.queue_only)
        self.assertFalse(result.queue_file_mutated)
        self.assertFalse(result.solver_started)
        self.assertFalse(result.runner_started)
        self.assertFalse(result.gui_required)
        self.assertIn("FULL_RUN:", result.command_preview)

    def test_enqueue_dry_run_does_not_mutate_queue_files(self):
        queue_path = Path(config.QUEUE_FILE)
        self.client.enqueue(JobRequest(inp_path=str(self.inp_path), cpus=14), dry_run=True)
        self.assertFalse(queue_path.exists())

    def test_enqueue_rejects_unsafe_direct_submit(self):
        request = JobRequest(
            inp_path=str(self.inp_path),
            cpus=14,
            submission_mode="submit",
            allow_solver_submit=True,
        )
        result = self.client.enqueue(request, dry_run=False)
        self.assertEqual(result.status, "REJECTED_UNSAFE_DIRECT_SUBMIT")
        self.assertIn("REJECTED_UNSAFE_DIRECT_SUBMIT", "\n".join(result.errors))

    def test_api_import_does_not_launch_gui(self):
        import abqjobpilot.api as public_api

        self.assertTrue(hasattr(public_api, "AbqJobPilotClient"))

    def test_status_reads_queue_json(self):
        Path(config.RUNTIME_DIR).mkdir(parents=True)
        job = {
            "queue_id": "q_test",
            "status": "QUEUED",
            "job_name": "Job_test",
            "inp_path": str(self.inp_path),
            "work_dir": str(self.inp_path.parent),
            "odb_path": str(self.inp_path.with_suffix(".odb")),
            "log_path": str(self.inp_path.with_suffix(".log")),
        }
        Path(config.QUEUE_FILE).write_text(json.dumps([job]), encoding="utf-8")

        result = self.client.status(job_id="q_test")
        self.assertEqual(result.status, "QUEUED")
        self.assertEqual(result.job_id, "q_test")
        self.assertIn(config.QUEUE_FILE, result.status_sources)

    def test_locate_outputs_detects_odb_and_lock(self):
        self.inp_path.with_suffix(".odb").write_text("fake odb marker", encoding="utf-8")
        self.inp_path.with_suffix(".lck").write_text("locked", encoding="utf-8")

        result = self.client.locate_outputs(inp_path=str(self.inp_path))
        self.assertTrue(result.odb_exists)
        self.assertTrue(result.lock_exists)
        self.assertTrue(result.warnings)


class TestPublicCli(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.inp_path = self.root / "batch01" / "strategy01" / "Job_cli.inp"
        self.inp_path.parent.mkdir(parents=True)
        self.inp_path.write_text("*Heading\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_preflight_json_returns_valid_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "abqjobpilot.api.cli",
                "preflight",
                "--inp",
                str(self.inp_path),
                "--cpus",
                "14",
                "--batch",
                "smoke_batch",
                "--strategy",
                "smoke_strategy",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(completed.stdout)
        self.assertEqual(data["status"], "PREVIEW_READY")

    def test_cli_enqueue_dry_run_json_returns_valid_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "abqjobpilot.api.cli",
                "enqueue",
                "--inp",
                str(self.inp_path),
                "--cpus",
                "14",
                "--batch",
                "smoke_batch",
                "--strategy",
                "smoke_strategy",
                "--dry-run",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(completed.stdout)
        self.assertEqual(data["status"], "DRY_RUN_READY")
        self.assertTrue(data["queue_only"])
        self.assertFalse(data["queue_file_mutated"])
        self.assertFalse(data["solver_started"])
        self.assertFalse(data["runner_started"])

    def test_cli_enqueue_only_json_returns_valid_json_against_temp_runtime(self):
        runtime_dir = self.root / "runtime"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "abqjobpilot.api.cli",
                "enqueue",
                "--inp",
                str(self.inp_path),
                "--cpus",
                "14",
                "--batch",
                "smoke_batch",
                "--strategy",
                "smoke_strategy",
                "--enqueue-only",
                "--runtime-dir",
                str(runtime_dir),
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(completed.stdout)
        self.assertEqual(data["status"], "ENQUEUED")
        self.assertTrue(data["queue_only"])
        self.assertTrue(data["queue_file_mutated"])
        self.assertFalse(data["solver_started"])
        self.assertFalse(data["runner_started"])
        self.assertFalse(data["gui_required"])
        self.assertTrue((runtime_dir / "queue.json").exists())
        self.assertFalse((runtime_dir / "live_status.json").exists())


if __name__ == "__main__":
    unittest.main()
