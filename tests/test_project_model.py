import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import config
from abqjobpilot.api import AbqJobPilotClient, JobRequest
from abqjobpilot.project import ProjectManager, export_project_archive, import_legacy_runtime, import_project_archive
from abqjobpilot.queue_store import read_queue


class ProjectModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manager = ProjectManager(recent_file=self.root / "app" / "recent.json")

    def project(self, name="StudyA"):
        return self.manager.create_project(self.root / name, name)

    def test_create_open_and_no_unsafe_overwrite(self):
        first = self.project()
        second = self.project("StudyB")
        self.assertNotEqual(first.project_id, second.project_id)
        manifest = json.loads(first.project_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["application"], "abqjobpilot")
        for directory in (first.runtime_dir, first.runtime_dir / "reports"):
            self.assertTrue(directory.is_dir())
        for directory in (first.models_dir, first.results_dir, first.logs_dir):
            self.assertFalse(directory.exists())
        self.assertTrue((first.runtime_dir / "queue.json").is_file())
        self.assertEqual(self.manager.validate_project(first.root).project_id, first.project_id)
        self.assertEqual(self.manager.open_project(first.root).project_id, first.project_id)
        self.manager.close_project()
        self.assertIsNone(self.manager.current)
        with self.assertRaises(FileExistsError):
            self.manager.create_project(first.root, "overwrite")
        self.assertEqual(json.loads(first.project_file.read_text(encoding="utf-8")), manifest)

    def test_invalid_project_rejected_without_mutation(self):
        root = self.root / "invalid"
        root.mkdir()
        (root / "project.json").write_text('{"application":"other"}', encoding="utf-8")
        before = (root / "project.json").read_bytes()
        with self.assertRaises(ValueError):
            self.manager.open_project(root)
        self.assertEqual((root / "project.json").read_bytes(), before)

    def test_project_runtime_isolation_and_switching(self):
        a = self.project()
        b = self.project("StudyB")
        a.models_dir.mkdir()
        inp = a.models_dir / "Job_demo.inp"
        inp.write_text("*Heading\n", encoding="utf-8")
        client_a = AbqJobPilotClient(runtime_dir=str(a.runtime_dir))
        client_b = AbqJobPilotClient(runtime_dir=str(b.runtime_dir))
        request = JobRequest(inp_path=str(inp), submission_mode="enqueue_only")
        with patch.object(config, "RUNTIME_DIR", str(self.root / "unrelated")):
            result = client_a.enqueue(request, dry_run=False)
            self.assertEqual(result.status, "ENQUEUED")
            self.assertEqual(client_a.status(job_id=result.job_id).status, "QUEUED")
            self.assertEqual(client_b.status(job_id=result.job_id).status, "UNKNOWN")
        self.assertEqual(len(client_a.list_jobs()["jobs"]), 1)
        self.assertEqual(client_b.list_jobs()["jobs"], [])
        original = (config.RUNTIME_DIR, config.QUEUE_FILE, config.LIVE_STATUS_FILE, config.SETTINGS_FILE)
        try:
            config.use_runtime_dir(a.runtime_dir)
            self.assertEqual(read_queue()[0]["queue_id"], result.job_id)
            config.use_runtime_dir(b.runtime_dir)
            self.assertEqual(read_queue(), [])
            config.use_runtime_dir(a.runtime_dir)
            self.assertEqual(read_queue()[0]["queue_id"], result.job_id)
        finally:
            config.RUNTIME_DIR, config.QUEUE_FILE, config.LIVE_STATUS_FILE, config.SETTINGS_FILE = original

    def test_recent_newest_first_deduplicated_and_missing_safe(self):
        a = self.project()
        b = self.project("StudyB")
        self.manager.open_project(a.root)
        self.manager.open_project(b.root)
        self.manager.open_project(a.root)
        recent = self.manager.recent_projects()
        self.assertEqual([item["project_id"] for item in recent], [a.project_id, b.project_id])
        self.assertEqual(json.loads(self.manager.recent_file.read_text(encoding="utf-8"))["schema_version"], "1.0")
        (b.root / "project.json").rename(b.root / "project.offline")
        self.assertEqual(len(self.manager.recent_projects()), 1)
        self.assertEqual(len(self.manager.recent_projects(include_missing=True)), 2)

    def test_metadata_archive_round_trip_and_relative_paths(self):
        project = self.project()
        project.models_dir.mkdir()
        project.results_dir.mkdir()
        inp = project.models_dir / "Job_demo.inp"
        inp.write_text("*Heading\n", encoding="utf-8")
        odb = project.results_dir / "Job_demo.odb"
        odb.write_bytes(b"dummy ODB fixture")
        client = AbqJobPilotClient(runtime_dir=str(project.runtime_dir))
        result = client.enqueue(JobRequest(inp_path=str(inp), working_dir=str(project.results_dir),
                                           submission_mode="enqueue_only"), dry_run=False)
        self.assertEqual(result.status, "ENQUEUED")
        archive_path = self.root / "metadata.abqjobpilot-project.zip"
        export_project_archive(project.root, archive_path, mode="metadata")
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["archive_schema_version"], "1.0")
            self.assertEqual(manifest["mode"], "metadata")
            self.assertIn("project/runtime/queue.json", names)
            self.assertNotIn("project/results/Job_demo.odb", names)
            self.assertNotIn("project/models/Job_demo.inp", names)
            portable = json.loads(archive.read("project/runtime/queue.json"))
            self.assertEqual(portable["jobs"][0]["inp_path"], "project://models/Job_demo.inp")
        restored = import_project_archive(archive_path, self.root / "Restored", recent_file=self.manager.recent_file)
        self.assertEqual(restored.project_id, project.project_id)
        restored_record = read_queue(restored.runtime_dir)[0]
        self.assertEqual(restored_record["inp_path"], str(restored.models_dir / "Job_demo.inp"))
        self.assertFalse((restored.models_dir / "Job_demo.inp").exists())
        self.assertEqual(AbqJobPilotClient(runtime_dir=str(restored.runtime_dir)).list_jobs()["jobs"][0]["queue_id"], result.job_id)

    def test_full_archive_round_trip_fixture_artifacts(self):
        project = self.project()
        project.models_dir.mkdir()
        project.results_dir.mkdir()
        inp = project.models_dir / "Job_demo.inp"
        odb = project.results_dir / "Job_demo.odb"
        sta = project.results_dir / "Job_demo.sta"
        for path, content in ((inp, b"*Heading\n"), (odb, b"fake odb"), (sta, b"completed")):
            path.write_bytes(content)
        archive_path = self.root / "full.abqjobpilot-project.zip"
        export_project_archive(project.root, archive_path, mode="full")
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIn("project/models/Job_demo.inp", archive.namelist())
            self.assertIn("project/results/Job_demo.odb", archive.namelist())
        restored = import_project_archive(archive_path, self.root / "Restored", preserve_project_id=False, recent_file=self.manager.recent_file)
        self.assertNotEqual(restored.project_id, project.project_id)
        self.assertEqual((restored.models_dir / inp.name).read_bytes(), inp.read_bytes())
        self.assertEqual((restored.results_dir / odb.name).read_bytes(), odb.read_bytes())
        self.assertEqual((restored.results_dir / sta.name).read_bytes(), sta.read_bytes())
        with self.assertRaises(FileExistsError):
            import_project_archive(archive_path, restored.root, recent_file=self.manager.recent_file)

    def test_archive_rejects_traversal_and_source_overwrite(self):
        project = self.project()
        archive_path = self.root / "bad.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.json", "{}")
            archive.writestr("project/../../evil.txt", "bad")
        with self.assertRaises(ValueError):
            import_project_archive(archive_path, self.root / "Out", recent_file=self.manager.recent_file)
        self.assertFalse((self.root / "evil.txt").exists())
        self.assertFalse((self.root / "Out").exists())
        with self.assertRaises(ValueError):
            export_project_archive(project.root, project.root / "inside.zip")
        self.assertFalse((project.root / "inside.zip").exists())

    def test_archive_rejects_noncanonical_alias(self):
        archive_path = self.root / "alias.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.json", "{}")
            archive.writestr("project/./project.json", "{}")
        with self.assertRaises(ValueError):
            import_project_archive(archive_path, self.root / "Alias", recent_file=self.manager.recent_file)
        self.assertFalse((self.root / "Alias").exists())

    def test_legacy_import_is_metadata_only_and_source_bytes_unchanged(self):
        source = self.root / "legacy" / "runtime"
        reports = source / "reports"
        reports.mkdir(parents=True)
        job = {
            "queue_id": "q_old", "status": "FAILED_FATAL", "job_name": "OldJob",
            "batch_name": "batch", "strategy_name": "strategy", "cpus": 18, "gpus": 1,
            "created_at": "2025-01-01T00:00:00", "ended_at": "2025-01-02T00:00:00",
            "inp_path": str(self.root / "external" / "OldJob.inp"),
            "odb_path": str(self.root / "external" / "OldJob.odb"),
        }
        (source / "queue.json").write_text(json.dumps([job]), encoding="utf-8")
        (source / "live_status.json").write_text(json.dumps({"phase": "IDLE"}), encoding="utf-8")
        (reports / "q_old.json").write_text(json.dumps(job), encoding="utf-8")
        (source / "huge.odb").write_bytes(b"not copied")
        before = {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source.rglob("*") if path.is_file()}
        imported = import_legacy_runtime(source, self.root / "Imported", "Imported",
                                         recent_file=self.manager.recent_file)
        after = {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in source.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(read_queue(imported.runtime_dir)[0], job)
        self.assertEqual(json.loads((imported.runtime_dir / "reports" / "q_old.json").read_text(encoding="utf-8")), job)
        self.assertFalse((imported.runtime_dir / "huge.odb").exists())
        provenance = json.loads(imported.project_file.read_text(encoding="utf-8"))["import_provenance"]
        self.assertEqual(provenance["source_type"], "legacy_abqjobpilot_runtime")
        self.assertIsNone(provenance["source_schema_version"])
        self.assertEqual(provenance["source_path"], str(source))
        exported = self.root / "legacy_metadata.zip"
        export_project_archive(imported.root, exported)
        with zipfile.ZipFile(exported) as archive:
            portable = json.loads(archive.read("project/project.json"))
            self.assertIsNone(portable["import_provenance"]["source_path"])

    def test_project_layer_cannot_start_solver(self):
        from abqjobpilot import project as project_package
        for module in (project_package.archive, project_package.legacy_import, project_package.manager):
            source = Path(module.__file__).read_text(encoding="utf-8")
            for forbidden in ("subprocess.Popen(", "QueueRunner(", "run_next_job(", "os.system("):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
