"""New-install paths and existing-runtime compatibility."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import config
from abqjobpilot.project.manager import (
    ProjectManager, default_projects_root, ensure_default_projects_root,
    set_default_projects_root,
)


class ProjectDataDefaultsTests(unittest.TestCase):
    def test_project_root_is_user_level_configurable_and_lazy(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            state = base / "state"
            chosen = base / "engineering_projects"
            with patch.object(config, "APP_ROOT_PATH", source), \
                 patch("abqjobpilot.project.manager.get_app_state_dir", return_value=state):
                self.assertEqual(default_projects_root(), state / "projects")
                self.assertFalse((state / "projects").exists())
                self.assertEqual(set_default_projects_root(chosen), chosen)
                self.assertFalse(chosen.exists())
                self.assertEqual(ensure_default_projects_root(), chosen)
                project = ProjectManager(base / "recent.json").create_project(chosen / "Example", "Example")
                self.assertEqual(ProjectManager(base / "recent.json").open_project(project.root).project_id,
                                 project.project_id)
                self.assertTrue((project.runtime_dir / "queue.json").is_file())
                self.assertFalse((source / "projects").exists())

    def test_source_tree_cannot_be_configured_as_default(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            state = Path(folder) / "state"
            with patch.object(config, "APP_ROOT_PATH", source), \
                 patch("abqjobpilot.project.manager.get_app_state_dir", return_value=state):
                with self.assertRaises(ValueError):
                    set_default_projects_root(source / "projects")
                with self.assertRaises(ValueError):
                    set_default_projects_root("relative_projects")
                self.assertFalse((state / "app_settings.json").exists())

    def test_new_no_project_runtime_is_installation_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            with patch("abqjobpilot.config.Path.home", return_value=base):
                with patch.object(config, "APP_ROOT_PATH", base / "install_a"):
                    first = config.default_runtime_path()
                with patch.object(config, "APP_ROOT_PATH", base / "install_b"):
                    second = config.default_runtime_path()
            self.assertNotEqual(first, second)
            self.assertNotIn("install_a/runtime", first.as_posix())
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

    def test_existing_legacy_runtime_stays_at_old_path_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            legacy = source / "runtime"
            legacy.mkdir(parents=True)
            queue = legacy / "queue.json"
            queue.write_text('{"jobs":[{"queue_id":"old"}]}', encoding="utf-8")
            before = queue.read_bytes()
            with patch.object(config, "APP_ROOT_PATH", source):
                self.assertEqual(config.default_runtime_path(), legacy)
            self.assertEqual(queue.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
