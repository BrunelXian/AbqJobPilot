"""Regression checks for reference-only Project ownership (P2B)."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from abqjobpilot.api import AbqJobPilotClient, JobRequest
from abqjobpilot.database import ProjectHistoryRepository, sync_history_from_runtime
from abqjobpilot.project import ProjectManager, export_project_archive, import_legacy_runtime, import_project_archive
from abqjobpilot.queue_store import read_queue, save_queue


class ProjectFileOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "engineering"
        self.workspace.mkdir()
        self.inp = self.workspace / "Case01.inp"
        self.cae = self.workspace / "Case01.cae"
        self.odb = self.workspace / "Case01.odb"
        self.sta = self.workspace / "Case01.sta"
        for path, content in ((self.inp, b"*Heading\n"), (self.cae, b"CAE_FIXTURE"),
                              (self.odb, b"EXTERNAL_ODB_BYTES_UNIQUE_TO_P2B"), (self.sta, b"COMPLETED")):
            path.write_bytes(content)
        self.manager = ProjectManager(recent_file=self.root / "recent.json")
        self.project = self.manager.create_project(self.root / "manager", "manager")

    def _hashes(self):
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (self.inp, self.cae, self.odb, self.sta)}

    def _enqueue(self, *, working_dir=None):
        client = AbqJobPilotClient(runtime_dir=str(self.project.runtime_dir))
        result = client.enqueue(JobRequest(inp_path=str(self.inp), working_dir=working_dir,
                                           submission_mode="enqueue_only"), dry_run=False)
        self.assertEqual(result.status, "ENQUEUED")
        return result, read_queue(self.project.runtime_dir)[0]

    def test_create_open_and_switch_do_not_own_or_mutate_external_files(self):
        before = self._hashes()
        self.assertEqual(set(self.project.root.iterdir()),
                         {self.project.project_file, self.project.runtime_dir})
        self.manager.open_project(self.project.root)
        other = self.manager.create_project(self.root / "other", "other")
        self.manager.open_project(other.root)
        self.manager.open_project(self.project.root)
        self.assertEqual(self._hashes(), before)
        self.assertFalse((self.project.root / "models").exists())
        self.assertFalse((other.root / "results").exists())

    def test_queue_preserves_external_inp_workdir_and_expected_odb(self):
        before = self._hashes()
        result, record = self._enqueue()
        self.assertEqual(record["inp_path"], str(self.inp))
        self.assertEqual(record["work_dir"], str(self.workspace))
        self.assertEqual(record["odb_path"], str(self.odb))
        self.assertEqual(result.expected_odb_path, str(self.odb))
        self.assertEqual(self._hashes(), before)
        self.assertFalse((self.project.root / "models").exists())
        self.assertEqual({path.name for path in self.project.root.rglob("*.inp")}, set())

    def test_explicit_workdir_is_not_replaced_by_project_directory(self):
        alternate = self.root / "alternate_workdir"
        alternate.mkdir()
        _, record = self._enqueue(working_dir=str(alternate))
        self.assertEqual(record["inp_path"], str(self.inp))
        self.assertEqual(record["work_dir"], str(alternate))
        self.assertEqual(record["odb_path"], str(alternate / "Case01.odb"))
        self.assertFalse((self.project.root / "results").exists())

    def test_history_indexes_external_files_without_copy_or_blob(self):
        before = self._hashes()
        _, record = self._enqueue()
        record.update(status="COMPLETED_OK", phase="COMPLETED_OK", ended_at="2026-01-01T00:00:00")
        save_queue([record], runtime_dir=self.project.runtime_dir)
        sync_history_from_runtime(self.project.root)
        repo = ProjectHistoryRepository(self.project)
        job = repo.find_job_by_queue_id(record["queue_id"])
        run = repo.list_runs(job["job_id"])[0]
        artifacts = {item["kind"]: item for item in repo.list_artifacts(run["run_id"])}
        self.assertEqual(artifacts["ODB"]["path"], str(self.odb))
        self.assertEqual(artifacts["ODB"]["size_bytes"], self.odb.stat().st_size)
        self.assertEqual(artifacts["INP"]["path"], str(self.inp))
        self.assertNotIn(self.odb.read_bytes(), repo.db_path.read_bytes())
        self.assertEqual(self._hashes(), before)
        self.assertEqual(list(self.project.root.rglob("*.odb")), [])

    def test_metadata_and_full_archive_never_collect_external_references(self):
        before = self._hashes()
        _, record = self._enqueue()
        sync_history_from_runtime(self.project.root)
        for mode in ("metadata", "full"):
            archive_path = self.root / f"{mode}.zip"
            export_project_archive(self.project.root, archive_path, mode=mode)
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                manifest = json.loads(archive.read("manifest.json"))
                archived_record = json.loads(archive.read("project/runtime/queue.json"))["jobs"][0]
                self.assertEqual(archived_record["inp_path"], str(self.inp))
                self.assertEqual(archived_record["odb_path"], str(self.odb))
                self.assertNotIn("project/models/Case01.inp", names)
                self.assertNotIn("project/results/Case01.odb", names)
                self.assertNotIn("project/results/Case01.cae", names)
                self.assertIn("project/project.db", names)
                self.assertTrue(any(ref["kind"] == "external_reference" and ref["value"] == str(self.inp)
                                    for ref in manifest["path_references"]))
            restored = import_project_archive(archive_path, self.root / f"restored_{mode}")
            self.assertEqual(read_queue(restored.runtime_dir)[0]["inp_path"], str(self.inp))
            self.assertEqual(ProjectHistoryRepository(restored).find_job_by_queue_id(record["queue_id"])["inp_path"],
                             str(self.inp))
        self.assertEqual(self._hashes(), before)

    def test_metadata_archive_import_tolerates_missing_external_files(self):
        _, record = self._enqueue()
        missing = self.root / "unavailable" / "Case01.inp"
        record["inp_path"] = str(missing)
        record["odb_path"] = str(missing.with_suffix(".odb"))
        save_queue([record], runtime_dir=self.project.runtime_dir)
        sync_history_from_runtime(self.project.root)
        archive_path = self.root / "missing_metadata.zip"
        export_project_archive(self.project.root, archive_path)
        restored = import_project_archive(archive_path, self.root / "missing_restored")
        self.assertEqual(read_queue(restored.runtime_dir)[0]["inp_path"], str(missing))
        self.assertFalse(missing.exists())
        self.assertFalse((restored.root / "models").exists())

    def test_legacy_import_retains_references_and_source_bytes(self):
        legacy = self.root / "legacy" / "runtime"
        legacy.mkdir(parents=True)
        record = {"queue_id": "legacy_one", "status": "FAILED_FATAL", "job_name": "Case01",
                  "inp_path": str(self.inp), "work_dir": str(self.workspace), "odb_path": str(self.odb),
                  "sta_path": str(self.sta)}
        queue_file = legacy / "queue.json"
        queue_file.write_text(json.dumps([record]), encoding="utf-8")
        before = self._hashes()
        queue_bytes = queue_file.read_bytes()
        imported = import_legacy_runtime(legacy, self.root / "legacy_imported", "legacy",
                                         recent_file=self.root / "legacy_recent.json")
        self.assertEqual(queue_file.read_bytes(), queue_bytes)
        self.assertEqual(self._hashes(), before)
        self.assertEqual(read_queue(imported.runtime_dir)[0]["odb_path"], str(self.odb))
        self.assertEqual(ProjectHistoryRepository(imported).find_job_by_queue_id("legacy_one")["inp_path"],
                         str(self.inp))
        self.assertEqual(list(imported.root.rglob("*.odb")), [])

    def test_older_project_owned_archive_remains_importable(self):
        self.project.models_dir.mkdir()
        self.project.results_dir.mkdir()
        owned = self.project.models_dir / "owned.inp"
        owned.write_text("*Heading\n", encoding="utf-8")
        (self.project.results_dir / "owned.odb").write_bytes(b"project-owned fixture")
        archive_path = self.root / "older_full.zip"
        export_project_archive(self.project.root, archive_path, mode="full")
        restored = import_project_archive(archive_path, self.root / "older_restored")
        self.assertEqual((restored.models_dir / "owned.inp").read_bytes(), owned.read_bytes())
        self.assertTrue((restored.results_dir / "owned.odb").is_file())


if __name__ == "__main__":
    unittest.main()
