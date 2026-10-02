import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import __version__
from abqjobpilot.api import AbqJobPilotClient, JobRequest
from abqjobpilot.api.cli import main
from abqjobpilot.api.project_surface import safe_project_folder
from abqjobpilot.database import ProjectHistoryRepository
from abqjobpilot.project.manager import ProjectManager
from abqjobpilot.queue_store import read_queue


class ProjectAutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recent = self.root / "app-state" / "recent.json"
        self.client = AbqJobPilotClient(runtime_dir=str(self.root / "default-runtime"),
                                        recent_file=str(self.recent))
        self.manager = ProjectManager(recent_file=self.recent)
        self.inp = self.root / "engineering" / "Model.inp"
        self.inp.parent.mkdir()
        self.inp.write_text("*Heading\n", encoding="utf-8")

    def cli(self, *args):
        output = io.StringIO()
        with patch("abqjobpilot.project.manager.default_recent_file", return_value=self.recent), \
             patch("abqjobpilot.api.project_surface.ensure_default_projects_root", return_value=self.root / "projects"), \
             redirect_stdout(output):
            exit_code = main([*args, "--json"])
        return exit_code, json.loads(output.getvalue())

    def test_version_capabilities_and_json_errors(self):
        self.assertEqual(__version__, "0.2.1")
        caps = self.client.capabilities()
        self.assertEqual(caps["application_version"], __version__)
        self.assertEqual(caps["automation_surface"], "1.0")
        self.assertTrue(caps["capabilities"]["project_create"])
        self.assertFalse(caps["capabilities"]["solver_start"])
        self.assertFalse(caps["capabilities"]["project_delete"])
        code, data = self.cli("project", "show")
        self.assertEqual(code, 1)
        self.assertEqual(data["error_details"][0]["code"], "INVALID_PROJECT_SELECTOR")
        code, data = self.cli("project", "create")
        self.assertEqual(code, 1)
        self.assertEqual(data["status"], "INVALID_REQUEST")

    def test_create_list_show_update_register_unregister(self):
        project = self.client.create_project("Study", path=str(self.root / "Study"))
        self.assertEqual(project.status, "PROJECT_CREATED")
        info = project.to_dict()["project"]
        project_id = info["project_id"]
        self.assertEqual(self.client.list_projects().to_dict()["projects"][0]["project_id"], project_id)
        shown = self.client.show_project(project_id=project_id).to_dict()["project"]
        self.assertEqual(shown["job_count"], None)
        self.assertFalse((self.root / "Study" / "project.db").exists())
        changed = self.client.update_project(project_id=project_id, name="Renamed", description="Notes",
                                             update_description=True)
        self.assertEqual(changed.to_dict()["project"]["name"], "Renamed")
        self.assertTrue((self.root / "Study" / "project.json").exists())
        removed = self.client.unregister_project(project_id=project_id)
        self.assertEqual(removed.status, "PROJECT_UNREGISTERED")
        self.assertTrue((self.root / "Study" / "runtime" / "queue.json").exists())
        self.assertEqual(self.client.unregister_project(project=str(self.root / "Study")).status,
                         "PROJECT_NOT_REGISTERED")
        self.assertEqual(self.client.register_project(str(self.root / "Study")).status, "PROJECT_REGISTERED")

    def test_default_folder_safety_and_ambiguous_name(self):
        with patch("abqjobpilot.api.project_surface.ensure_default_projects_root", return_value=self.root / "projects"):
            result = self.client.create_project("Normal Name")
        self.assertEqual(result.status, "PROJECT_CREATED")
        self.assertEqual(Path(result.to_dict()["project"]["path"]).name, "Normal Name")
        self.assertEqual(safe_project_folder("中文 Study"), "中文 Study")
        for name in ("..", "C:evil", "CON", "../escape", "bad?name"):
            self.assertEqual(self.client.create_project(name).status, "INVALID_PROJECT_SELECTOR")
        self.manager.create_project(self.root / "Other", "Normal Name")
        ambiguous = self.client.show_project(project_name="Normal Name").to_dict()
        self.assertEqual(ambiguous["status"], "AMBIGUOUS_PROJECT")
        self.assertEqual(len(ambiguous["matches"]), 2)

    def test_default_create_uses_application_root_and_duplicate_is_safe(self):
        with patch("abqjobpilot.project.manager.config.APP_ROOT_PATH", self.root):
            result = self.client.create_project("Default Study")
        self.assertEqual(result.status, "PROJECT_CREATED")
        destination = self.root / "projects" / "Default Study"
        self.assertEqual(result.to_dict()["project"]["path"], str(destination))
        before = (destination / "project.json").read_bytes()
        with patch("abqjobpilot.project.manager.config.APP_ROOT_PATH", self.root):
            duplicate = self.client.create_project("Default Study")
        self.assertEqual(duplicate.status, "PROJECT_ALREADY_EXISTS")
        self.assertEqual(before, (destination / "project.json").read_bytes())

    def test_explicit_project_enqueue_isolated_and_never_starts_solver(self):
        a = self.manager.create_project(self.root / "A", "A")
        b = self.manager.create_project(self.root / "B", "B")
        scoped = self.client.for_project(project_id=a.project_id)
        self.assertEqual(scoped.enqueue(JobRequest(str(self.inp))).status, "DRY_RUN_READY")
        self.assertEqual(read_queue(a.runtime_dir), [])
        result = scoped.enqueue(JobRequest(str(self.inp)), dry_run=False)
        self.assertEqual(result.status, "ENQUEUED")
        self.assertFalse(result.solver_started)
        self.assertEqual(len(read_queue(a.runtime_dir)), 1)
        self.assertEqual(read_queue(b.runtime_dir), [])
        self.assertFalse((self.inp.parent / "Model.odb").exists())
        self.assertFalse((self.root / "default-runtime").exists())

    def test_history_queries_read_only_and_archive_roundtrip(self):
        project = self.manager.create_project(self.root / "P", "P")
        self.assertEqual(self.client.list_project_jobs(project_id=project.project_id).to_dict()["jobs"], [])
        self.assertFalse((project.root / "project.db").exists())
        repo = ProjectHistoryRepository(project)
        job = repo.get_or_create_job(job_name="Model", inp_path=str(self.inp), batch="B", strategy="S")
        first = repo.create_run(job["job_id"], status="FAILED_FATAL", queue_id="q1")
        second = repo.create_run(job["job_id"], status="COMPLETED_OK", queue_id="q2")
        repo.add_or_update_artifact(second["run_id"], "ODB", str(self.inp.with_suffix(".odb")), exists_flag=False)
        db_before = (project.root / "project.db").read_bytes()
        listing = self.client.list_project_jobs(project_id=project.project_id, status="COMPLETED", batch="B")
        self.assertEqual(listing.to_dict()["jobs"][0]["run_count"], 2)
        shown = self.client.show_job(job["job_id"], project_id=project.project_id).to_dict()
        self.assertEqual([run["run_id"] for run in shown["runs"]], [second["run_id"], first["run_id"]])
        self.assertEqual(shown["artifacts"][0]["items"][0]["kind"], "ODB")
        self.assertEqual(db_before, (project.root / "project.db").read_bytes())
        archive = self.root / "copy.zip"
        self.assertEqual(self.client.export_project(str(archive), project_id=project.project_id).status,
                         "PROJECT_EXPORTED")
        self.assertEqual(self.client.import_project_archive(str(archive), destination=str(self.root / "Restored")).status,
                         "PROJECT_IMPORTED")
        self.assertFalse((self.root / "Restored" / "runtime" / "Model.inp").exists())

    def test_cli_project_scoping_and_job_queries(self):
        project = self.manager.create_project(self.root / "P", "P")
        code, data = self.cli("project", "show", "--project-id", project.project_id)
        self.assertEqual(code, 0)
        self.assertEqual(data["project"]["project_id"], project.project_id)
        code, data = self.cli("enqueue", "--project-id", project.project_id,
                              "--inp", str(self.inp), "--enqueue-only")
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "ENQUEUED")
        self.assertEqual(len(read_queue(project.runtime_dir)), 1)
        code, data = self.cli("job", "list", "--project-id", project.project_id)
        self.assertEqual(code, 0)
        self.assertEqual(data["jobs"], [])  # No implicit history projection.
        code, data = self.cli("project", "unregister", "--project-id", project.project_id)
        self.assertEqual((code, data["status"]), (0, "PROJECT_UNREGISTERED"))
        self.assertTrue((project.root / "project.json").exists())
        code, data = self.cli("project", "unregister", "--project-id", project.project_id)
        self.assertEqual((code, data["status"]), (1, "PROJECT_NOT_REGISTERED"))

    def test_cli_archive_update_and_explicit_runtime_conflict(self):
        project = self.manager.create_project(self.root / "Exported", "Exported")
        code, data = self.cli("project", "update", "--project-id", project.project_id,
                              "--description", "new notes")
        self.assertEqual((code, data["project"]["description"]), (0, "new notes"))
        code, data = self.cli("project", "update", "--project-id", project.project_id,
                              "--name", "Renamed")
        self.assertEqual((code, data["project"]["description"]), (0, "new notes"))
        self.assertEqual(data["project"]["name"], "Renamed")
        archive = self.root / "export.zip"
        code, data = self.cli("project", "export", "--project-id", project.project_id,
                              "--output", str(archive))
        self.assertEqual((code, data["mode"]), (0, "metadata"))
        code, data = self.cli("project", "import", "--archive", str(archive),
                              "--destination", str(self.root / "Imported"))
        self.assertEqual(code, 0)
        self.assertEqual(data["project"]["path"], str(self.root / "Imported"))
        code, data = self.cli("preflight", "--inp", str(self.inp), "--project-id", project.project_id,
                              "--runtime-dir", str(project.runtime_dir))
        self.assertEqual((code, data["status"]), (1, "INVALID_PROJECT_SELECTOR"))


if __name__ == "__main__":
    unittest.main()
