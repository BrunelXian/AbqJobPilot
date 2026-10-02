"""Bulk queue operations and default Project location without solver execution."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import config
from abqjobpilot.gui_table_state import restore_iids, row_iid
from abqjobpilot.project.manager import (ProjectManager, default_projects_root,
                                          ensure_default_projects_root)
from abqjobpilot.queue_store import (build_queue_record, read_queue, remove_queued_jobs,
                                      remove_result_jobs, save_queue)


class MultiSelectStoreTests(unittest.TestCase):
    def test_restore_all_visible_stable_ids(self):
        visible = [{"queue_id": "a"}, {"queue_id": "c"}]
        self.assertEqual(restore_iids(("a", "b", "c"), visible), ("a", "c"))
        self.assertEqual(restore_iids(("result_a", "result_b", "result_c"), visible, results=True),
                         ("result_a", "result_c"))

    def test_bulk_store_operations_are_all_or_nothing_and_preserve_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime = root / "runtime"
            inp = root / "model.inp"
            odb = root / "model.odb"
            inp.write_text("*Heading\n", encoding="utf-8")
            odb.write_text("fixture", encoding="utf-8")
            queued = [build_queue_record(inp, 2, 0, "b", "s", f"Q{n}", True, True, "") for n in range(3)]
            results = [build_queue_record(inp, 2, 0, "b", "s", f"R{n}", True, True, "") for n in range(3)]
            for result in results:
                result["status"] = "COMPLETED_OK"
            save_queue(queued + results, runtime_dir=runtime)
            with patch.object(config, "RUNTIME_DIR", str(runtime)), \
                 patch.object(config, "QUEUE_FILE", str(runtime / "queue.json")), \
                 patch.object(config, "LIVE_STATUS_FILE", str(runtime / "live_status.json")):
                before = read_queue(runtime)
                self.assertFalse(remove_queued_jobs([queued[0]["queue_id"], "absent"])["ok"])
                self.assertEqual(read_queue(runtime), before)
                self.assertFalse(remove_queued_jobs([queued[0]["queue_id"], results[0]["queue_id"]])["ok"])
                self.assertEqual(read_queue(runtime), before)
                self.assertTrue(remove_queued_jobs([queued[0]["queue_id"], queued[2]["queue_id"]])["ok"])
                self.assertEqual([j["queue_id"] for j in read_queue(runtime) if j["status"] == "QUEUED"],
                                 [queued[1]["queue_id"]])
                remaining = read_queue(runtime)
                self.assertFalse(remove_result_jobs([results[0]["queue_id"], "absent"])["ok"])
                self.assertEqual(read_queue(runtime), remaining)
                self.assertTrue(remove_result_jobs([results[0]["queue_id"], results[2]["queue_id"]])["ok"])
                self.assertEqual([j["queue_id"] for j in read_queue(runtime) if j["status"] == "COMPLETED_OK"],
                                 [results[1]["queue_id"]])
                remaining = read_queue(runtime)
                running = dict(queued[0], status="FULL_RUNNING")
                save_queue([running] + remaining, runtime_dir=runtime)
                self.assertFalse(remove_queued_jobs([queued[1]["queue_id"]])["ok"])
                self.assertEqual(read_queue(runtime), [running] + remaining)
            self.assertEqual(inp.read_text(encoding="utf-8"), "*Heading\n")
            self.assertEqual(odb.read_text(encoding="utf-8"), "fixture")


class DefaultProjectRootTests(unittest.TestCase):
    def test_default_root_is_app_relative_lazy_and_git_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            app_root = Path(folder) / "app"
            other_cwd = Path(folder) / "elsewhere"
            other_cwd.mkdir()
            old_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                with patch.object(config, "APP_ROOT_PATH", app_root):
                    self.assertEqual(default_projects_root(), app_root / "projects")
                    self.assertFalse((app_root / "projects").exists())
                    self.assertEqual(ensure_default_projects_root(), app_root / "projects")
                    self.assertTrue((app_root / "projects").is_dir())
                    manager = ProjectManager(recent_file=Path(folder) / "recent.json")
                    project = manager.create_project(app_root / "projects" / "Demo", "Demo")
                    self.assertEqual(project.root, app_root / "projects" / "Demo")
                    external = manager.create_project(Path(folder) / "external_project", "External")
                    self.assertEqual(manager.open_project(external.root).project_id, external.project_id)
            finally:
                os.chdir(old_cwd)
        ignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/projects/", ignore)


if __name__ == "__main__":
    unittest.main()
