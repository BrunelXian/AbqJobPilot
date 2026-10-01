import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

from abqjobpilot.database import (DatabaseFailure, ProjectHistoryRepository,
                                  backup_database, inspect_schema_version, sync_history_from_runtime)
from abqjobpilot.database.connection import open_connection
from abqjobpilot.database.migrations import get_schema_version
from abqjobpilot.project import ProjectManager, export_project_archive, import_legacy_runtime, import_project_archive
from abqjobpilot.queue_store import build_queue_record, read_queue, save_queue


class ProjectDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manager = ProjectManager(recent_file=self.root / "recent.json")
        self.project = self.manager.create_project(self.root / "A", "A")
        self.project.models_dir.mkdir()
        self.inp = self.project.models_dir / "Job_A.inp"
        self.inp.write_text("*Heading\n", encoding="utf-8")

    def record(self, queue_id: str, status: str = "QUEUED") -> dict:
        record = build_queue_record(self.inp, 12, 1, "batch", "strategy", "Job_A",
                                    True, True, "", queue_id=queue_id)
        record["status"] = status
        record["phase"] = status
        if status.startswith(("FAILED", "COMPLETED")):
            record["ended_at"] = "2026-01-02T00:00:00"
        return record

    def test_lazy_schema_idempotent_and_foreign_keys(self):
        self.assertFalse((self.project.root / "project.db").exists())
        self.assertEqual(self.manager.open_project(self.project.root).project_id, self.project.project_id)
        self.assertFalse((self.project.root / "project.db").exists())
        repo = ProjectHistoryRepository(self.project)
        self.assertEqual(repo.initialize(), 1)
        self.assertEqual(repo.initialize(), 1)
        self.assertEqual(inspect_schema_version(repo.db_path), 1)
        connection = open_connection(repo.db_path)
        try:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual({row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'") if row[0] != 'sqlite_sequence'},
                {"schema_meta", "jobs", "runs", "artifacts"})
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO runs(run_id,job_id,attempt_no,status) VALUES(?,?,?,?)",
                                   ("r_bad", "missing", 1, "QUEUED"))
            connection.rollback()
        finally:
            connection.close()

    def test_logical_job_multiple_runs_and_artifact_metadata(self):
        repo = ProjectHistoryRepository(self.project)
        job = repo.get_or_create_job(job_name="Job_A", inp_path=str(self.inp), batch="batch")
        self.assertEqual(repo.get_or_create_job(job_name="Job_A", inp_path=str(self.inp))["job_id"], job["job_id"])
        failed = repo.create_run(job["job_id"], queue_id="q_1", cpus=12, gpus=1)
        self.assertEqual(repo.create_run(job["job_id"], queue_id="q_1")["run_id"], failed["run_id"])
        repo.update_run_status(failed["run_id"], "FULL_RUNNING", started_at="2026-01-01T00:00:00")
        repo.complete_run(failed["run_id"], "FAILED_FATAL", completed_at="2026-01-01T01:00:00")
        success = repo.create_run(job["job_id"], queue_id="q_2", status="COMPLETED_OK")
        self.assertEqual((failed["attempt_no"], success["attempt_no"]), (1, 2))
        self.assertEqual([run["status"] for run in repo.list_runs(job["job_id"])], ["COMPLETED", "FAILED"])
        self.assertEqual(repo.latest_completed_run(job["job_id"])["run_id"], success["run_id"])
        self.assertEqual(repo.list_jobs()[0]["latest_status"], "COMPLETED")
        odb = self.project.results_dir / "large.odb"
        self.project.results_dir.mkdir()
        payload = b"SOLVER_BYTES_NOT_IN_DATABASE" * 100
        odb.write_bytes(payload)
        artifact = repo.add_or_update_artifact(success["run_id"], "ODB", str(odb), exists_flag=True,
                                               size_bytes=odb.stat().st_size, mtime_ns=odb.stat().st_mtime_ns)
        missing = repo.add_or_update_artifact(success["run_id"], "STA", str(odb.with_suffix(".sta")), exists_flag=False)
        self.assertEqual(artifact["size_bytes"], len(payload))
        self.assertEqual(missing["exists_flag"], 0)
        self.assertEqual(len(repo.list_artifacts(success["run_id"])), 2)
        self.assertNotIn(payload, repo.db_path.read_bytes())

    def test_reconciliation_requeue_idempotent_and_terminal_not_downgraded(self):
        first = self.record("q_first", "FAILED_FATAL")
        save_queue([first], runtime_dir=self.project.runtime_dir)
        initial = sync_history_from_runtime(self.project.root)
        self.assertEqual(initial["created_runs"], 1)
        self.assertEqual(sync_history_from_runtime(self.project.root)["created_runs"], 0)
        repo = ProjectHistoryRepository(self.project)
        job = repo.find_job_by_queue_id("q_first")
        self.assertEqual(repo.list_runs(job["job_id"])[0]["status"], "FAILED")
        second = self.record("q_second", "QUEUED")
        save_queue([first, second], runtime_dir=self.project.runtime_dir)
        self.assertEqual(sync_history_from_runtime(self.project.root)["created_runs"], 1)
        runs = repo.list_runs(job["job_id"])
        self.assertEqual([(run["attempt_no"], run["queue_id"]) for run in runs],
                         [(2, "q_second"), (1, "q_first")])
        second["status"] = "COMPLETED_OK"
        second["started_at"] = "2026-01-02T01:00:00"
        second["ended_at"] = "2026-01-02T02:00:00"
        save_queue([first, second], runtime_dir=self.project.runtime_dir)
        sync_history_from_runtime(self.project.root)
        self.assertEqual([run["status"] for run in repo.list_runs(job["job_id"])], ["COMPLETED", "FAILED"])
        stale = dict(second, status="QUEUED")
        save_queue([first, stale], runtime_dir=self.project.runtime_dir)
        sync_history_from_runtime(self.project.root)
        self.assertEqual(repo.list_runs(job["job_id"])[0]["status"], "COMPLETED")
        self.assertEqual(len(repo.list_jobs()), 1)

    def test_future_schema_and_zero_to_one_migration(self):
        repo = ProjectHistoryRepository(self.project)
        with closing(sqlite3.connect(repo.db_path)) as connection:
            connection.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO schema_meta VALUES(?, ?)", ("schema_version", "0"))
            connection.commit()
        self.assertEqual(repo.initialize(), 1)
        self.assertEqual(inspect_schema_version(repo.db_path), 1)
        with closing(sqlite3.connect(repo.db_path)) as connection:
            connection.execute("UPDATE schema_meta SET value = ? WHERE key = ?", ("999", "schema_version"))
            connection.commit()
        before = hashlib.sha256(repo.db_path.read_bytes()).hexdigest()
        with self.assertRaises(DatabaseFailure) as caught:
            repo.list_jobs()
        self.assertEqual(caught.exception.code, "UNSUPPORTED_DATABASE_SCHEMA")
        with closing(open_connection(repo.db_path)) as connection:
            self.assertEqual(get_schema_version(connection), 999)
        self.assertEqual(hashlib.sha256(repo.db_path.read_bytes()).hexdigest(), before)

    def test_backup_is_readable_and_isolated(self):
        repo = ProjectHistoryRepository(self.project)
        repo.get_or_create_job(job_name="Job_A", inp_path=str(self.inp))
        backup = self.root / "backup.db"
        backup_database(repo.db_path, backup)
        self.assertEqual(inspect_schema_version(backup), 1)
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
        with self.assertRaises(FileExistsError):
            backup_database(repo.db_path, backup)

    def test_p1_and_p2_archive_compatibility_and_path_rebase(self):
        p1_archive = self.root / "p1.zip"
        export_project_archive(self.project.root, p1_archive)
        with zipfile.ZipFile(p1_archive) as archive:
            self.assertNotIn("project/project.db", archive.namelist())
        p1_imported = import_project_archive(p1_archive, self.root / "P1Imported")
        self.assertFalse((p1_imported.root / "project.db").exists())
        first = self.record("q_one", "FAILED_FATAL")
        second = self.record("q_two", "COMPLETED_OK")
        save_queue([first, second], runtime_dir=self.project.runtime_dir)
        sync_history_from_runtime(self.project.root)
        metadata_archive = self.root / "p2_metadata.zip"
        full_archive = self.root / "p2_full.zip"
        export_project_archive(self.project.root, metadata_archive, mode="metadata")
        export_project_archive(self.project.root, full_archive, mode="full")
        for path in (metadata_archive, full_archive):
            with zipfile.ZipFile(path) as archive:
                self.assertIn("project/project.db", archive.namelist())
            imported = import_project_archive(path, self.root / (path.stem + "_import"),
                                              preserve_project_id=False)
            repo = ProjectHistoryRepository(imported)
            job = repo.find_job_by_queue_id("q_one")
            self.assertEqual(job["project_id"], imported.project_id)
            self.assertEqual(job["inp_path"], str(imported.models_dir / "Job_A.inp"))
            self.assertEqual([run["queue_id"] for run in repo.list_runs(job["job_id"])], ["q_two", "q_one"])
            self.assertEqual(sync_history_from_runtime(imported.root)["created_runs"], 0)
            artifacts = repo.list_artifacts(repo.list_runs(job["job_id"])[0]["run_id"])
            self.assertEqual(next(item["path"] for item in artifacts if item["kind"] == "INP"),
                             str(imported.models_dir / "Job_A.inp"))

    def test_legacy_import_populates_history_without_source_write(self):
        source = self.root / "legacy" / "runtime"
        source.mkdir(parents=True)
        record = self.record("q_old", "FAILED_FATAL")
        queue = source / "queue.json"
        queue.write_text(json.dumps([record]), encoding="utf-8")
        before = queue.read_bytes()
        imported = import_legacy_runtime(source, self.root / "LegacyImported", "Legacy",
                                         recent_file=self.root / "recent.json")
        self.assertEqual(queue.read_bytes(), before)
        self.assertEqual(read_queue(imported.runtime_dir)[0], record)
        repo = ProjectHistoryRepository(imported)
        job = repo.find_job_by_queue_id("q_old")
        self.assertEqual(repo.list_runs(job["job_id"])[0]["status"], "FAILED")

    def test_project_database_isolation(self):
        other = self.manager.create_project(self.root / "B", "B")
        repo_a = ProjectHistoryRepository(self.project)
        repo_b = ProjectHistoryRepository(other)
        repo_a.get_or_create_job(job_name="Job_A", inp_path=str(self.inp))
        self.assertEqual(len(repo_a.list_jobs()), 1)
        self.assertEqual(repo_b.list_jobs(), [])
        self.assertNotEqual(repo_a.db_path, repo_b.db_path)

    def test_unsupported_database_does_not_block_runtime_queue_json(self):
        repo = ProjectHistoryRepository(self.project)
        repo.initialize()
        with closing(sqlite3.connect(repo.db_path)) as connection:
            connection.execute("UPDATE schema_meta SET value = ? WHERE key = ?", ("999", "schema_version"))
            connection.commit()
        record = self.record("q_queue_still_works")
        save_queue([record], runtime_dir=self.project.runtime_dir)
        self.assertEqual(read_queue(self.project.runtime_dir)[0]["queue_id"], record["queue_id"])
        with self.assertRaises(DatabaseFailure) as caught:
            sync_history_from_runtime(self.project.root)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_DATABASE_SCHEMA")
        self.assertEqual(read_queue(self.project.runtime_dir)[0], record)


if __name__ == "__main__":
    unittest.main()
