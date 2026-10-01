import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import config, utils
from abqjobpilot.api import AbqJobPilotClient, JobRequest
from abqjobpilot.queue_store import add_inp_job_to_queue, build_queue_record, read_queue
from abqjobpilot.runner_core import _write_live_status, _write_report
from abqjobpilot.status_codes import normalize_status


class TestAutomationSurface(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime_a = self.root / "runtime_A"
        self.runtime_b = self.root / "runtime_B"
        self.inp = self.root / "batch" / "strategy" / "Job_demo.inp"
        self.inp.parent.mkdir(parents=True)
        self.inp.write_text("*Heading\n", encoding="utf-8")
        self.client_a = AbqJobPilotClient(runtime_dir=str(self.runtime_a))
        self.client_b = AbqJobPilotClient(runtime_dir=str(self.runtime_b))

    def request(self):
        return JobRequest(inp_path=str(self.inp), cpus=12, gpus=1, batch="batch", strategy="strategy",
                          submission_mode="enqueue_only")

    def test_two_runtimes_are_isolated_for_enqueue_status_and_outputs(self):
        preview = self.client_a.preflight(self.request())
        self.assertEqual(preview.status, "PREVIEW_READY")
        self.assertFalse(self.runtime_a.exists())
        result = self.client_a.enqueue(self.request(), dry_run=False)
        self.assertEqual(result.status, "ENQUEUED")
        self.assertEqual(self.client_a.status(job_id=result.job_id).status, "QUEUED")
        self.assertEqual(self.client_b.status(job_id=result.job_id).status, "UNKNOWN")
        self.assertEqual(self.client_a.locate_outputs(job_id=result.job_id).job_id, result.job_id)
        self.assertIsNone(self.client_b.locate_outputs(job_id=result.job_id).working_dir)
        self.assertEqual(len(self.client_a.list_jobs()["jobs"]), 1)
        self.assertEqual(self.client_b.list_jobs()["jobs"], [])
        self.assertFalse(self.runtime_b.exists())
        self.assertEqual(read_queue(self.runtime_a)[0]["queue_id"], result.job_id)

    def test_report_and_live_status_reads_use_selected_runtime(self):
        self.runtime_a.mkdir()
        reports = self.runtime_a / "reports"
        reports.mkdir()
        (reports / "q_report.json").write_text(json.dumps({
            "queue_id": "q_report", "status": "FAILED_FATAL", "job_name": "Report",
            "work_dir": str(self.inp.parent),
        }), encoding="utf-8")
        (self.runtime_a / "live_status.json").write_text(json.dumps({
            "queue_id": "q_live", "phase": "FULL_RUNNING", "current_job": "Live",
            "log_path": str(self.inp.with_suffix(".log")),
        }), encoding="utf-8")
        self.assertEqual(self.client_a.status(job_id="q_report").status, "FAILED")
        self.assertEqual(self.client_a.status(job_id="q_live").status, "RUNNING")
        self.assertEqual(self.client_b.status(job_id="q_report").status, "UNKNOWN")
        self.assertEqual(self.client_b.status(job_id="q_live").status, "UNKNOWN")

    def test_shared_record_shape_and_legacy_queue_read(self):
        canonical = build_queue_record(self.inp.resolve(), 12, 1, "batch", "strategy", "Job_demo", True, True, "",
                                       queue_id="q_fixed", created_at="2026-01-01T00:00:00")
        self.assertEqual(canonical["queue_id"], "q_fixed")
        self.assertEqual(canonical["created_at"], "2026-01-01T00:00:00")
        api_result = self.client_a.enqueue(self.request(), dry_run=False)
        self.assertEqual(api_result.status, "ENQUEUED")
        api_record = read_queue(self.runtime_a)[0]
        with patch.object(config, "RUNTIME_DIR", str(self.runtime_b)), \
             patch.object(config, "QUEUE_FILE", str(self.runtime_b / "queue.json")), \
             patch.object(config, "LIVE_STATUS_FILE", str(self.runtime_b / "live_status.json")):
            gui_record = add_inp_job_to_queue(str(self.inp), cpus=12, gpus=1,
                                               batch_name="batch", strategy_name="strategy")["job"]
        for key in ("job_name", "inp_path", "work_dir", "cpus", "gpus", "batch_name", "strategy_name",
                    "run_datacheck", "run_full", "odb_path", "status", "phase", "schema_version"):
            self.assertEqual(api_record[key], canonical[key])
            self.assertEqual(gui_record[key], canonical[key])
        legacy = dict(api_record)
        legacy.pop("schema_version")
        (self.runtime_b / "queue.json").write_text(json.dumps([legacy]), encoding="utf-8")
        self.assertEqual(self.client_b.status(job_id=legacy["queue_id"]).status, "QUEUED")
        self.assertEqual(read_queue(self.runtime_b)[0]["queue_id"], legacy["queue_id"])
        self.assertEqual(json.loads((self.runtime_b / "queue.json").read_text(encoding="utf-8")), [legacy])

    def test_atomic_replace_failure_preserves_canonical_json(self):
        self.runtime_a.mkdir()
        queue_file = self.runtime_a / "queue.json"
        queue_file.write_text('{"schema_version":"1.0","jobs":[]}', encoding="utf-8")
        with patch.object(utils.os, "replace", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                utils.write_json(queue_file, {"schema_version": "1.0", "jobs": [{"queue_id": "new"}]})
        self.assertEqual(json.loads(queue_file.read_text(encoding="utf-8"))["jobs"], [])
        self.assertEqual(list(self.runtime_a.glob("*.tmp")), [])

    def test_status_normalization_and_error_details(self):
        self.assertEqual(normalize_status("DATACHECK_RUNNING"), "RUNNING")
        self.assertEqual(normalize_status("SKIPPED"), "SKIPPED")
        self.assertEqual(normalize_status("COMPLETED_WITH_WARNINGS", odb_exists=False), "ODB_MISSING")
        self.assertEqual(normalize_status("FAILED_LICENSE"), "FAILED")
        self.assertEqual(normalize_status("unrecognized-state"), "UNKNOWN")
        missing = self.client_a.preflight(JobRequest(inp_path=str(self.root / "missing.inp")))
        data = missing.to_dict()
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIn({"code": "INP_NOT_FOUND", "message": data["errors"][0]}, data["error_details"])
        bad_cpu = self.client_a.preflight(JobRequest(inp_path=str(self.inp), cpus=0))
        self.assertEqual(bad_cpu.error_details[0]["code"], "INVALID_CPU_COUNT")
        bad_gpu = self.client_a.preflight(JobRequest(inp_path=str(self.inp), gpus=-1))
        self.assertEqual(bad_gpu.error_details[0]["code"], "INVALID_GPU_COUNT")
        unsafe = self.client_a.enqueue(JobRequest(inp_path=str(self.inp), submission_mode="submit",
                                                   allow_solver_submit=True), dry_run=False)
        self.assertEqual(unsafe.error_details[0]["code"], "UNSAFE_OPERATION")
        not_found = self.client_a.status(job_id="q_missing")
        self.assertEqual(not_found.error_details[0]["code"], "RUNTIME_NOT_FOUND")

    def test_malformed_queue_returns_error_without_overwrite(self):
        self.runtime_a.mkdir()
        queue_file = self.runtime_a / "queue.json"
        queue_file.write_text("{not valid json", encoding="utf-8")
        status = self.client_a.status(job_id="q_missing")
        self.assertEqual(status.error_details[0]["code"], "INVALID_STATUS_DATA")
        rejected = self.client_a.enqueue(self.request(), dry_run=False)
        self.assertEqual(rejected.status, "FAILED")
        self.assertEqual(rejected.error_details[0]["code"], "INVALID_STATUS_DATA")
        self.assertEqual(queue_file.read_text(encoding="utf-8"), "{not valid json")

    def test_threaded_writers_in_one_process_keep_all_records(self):
        inps = [self.inp.parent / f"Job_{index}.inp" for index in range(12)]
        for inp in inps:
            inp.write_text("*Heading\n", encoding="utf-8")
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda inp: self.client_a.enqueue(
                JobRequest(inp_path=str(inp), submission_mode="enqueue_only"), dry_run=False), inps))
        self.assertTrue(all(result.status == "ENQUEUED" for result in results))
        self.assertEqual(len({job["queue_id"] for job in read_queue(self.runtime_a)}), len(inps))
        self.assertEqual(json.loads((self.runtime_a / "queue.json").read_text(encoding="utf-8"))["schema_version"], "1.0")

    def test_new_live_status_and_report_are_versioned(self):
        with patch.object(config, "RUNTIME_DIR", str(self.runtime_a)), \
             patch.object(config, "LIVE_STATUS_FILE", str(self.runtime_a / "live_status.json")):
            _write_live_status(phase="IDLE")
            _write_report({"queue_id": "q_fixture", "job_name": "Fixture", "status": "COMPLETED_OK"})
        live = json.loads((self.runtime_a / "live_status.json").read_text(encoding="utf-8"))
        report = json.loads(next((self.runtime_a / "reports").glob("q_fixture*.json")).read_text(encoding="utf-8"))
        self.assertEqual(live["schema_version"], "1.0")
        self.assertEqual(report["schema_version"], "1.0")

    def test_capabilities_and_folder_preview_are_read_only(self):
        capabilities = self.client_a.capabilities()
        self.assertFalse(capabilities["capabilities"]["solver_start"])
        self.assertEqual(capabilities["schema_version"], "1.0")
        result = self.client_a.enqueue_folder(str(self.inp.parent))
        self.assertEqual(result["status"], "DRY_RUN_READY")
        self.assertEqual(len(result["results"]), 1)
        self.assertFalse(self.runtime_a.exists())

    def test_cli_capabilities_and_list_json(self):
        for command in ("capabilities", "list"):
            completed = subprocess.run(
                [sys.executable, "-m", "abqjobpilot.api.cli", command, "--runtime-dir", str(self.runtime_a), "--json"],
                check=True, capture_output=True, text=True,
            )
            data = json.loads(completed.stdout)
            self.assertEqual(data["schema_version"], "1.0")
        self.assertFalse(self.runtime_a.exists())


if __name__ == "__main__":
    unittest.main()
