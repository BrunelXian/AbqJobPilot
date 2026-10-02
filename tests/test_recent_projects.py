import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import config
from abqjobpilot.project import ProjectManager, export_project_archive, import_project_archive, import_legacy_runtime
from abqjobpilot.project.manager import default_recent_file, RECENT_LIMIT


class RecentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / 'app' / 'recent.json'
        self.manager = ProjectManager(recent_file=self.store)

    def create(self, name='A'):
        return self.manager.create_project(self.root / name, name)

    def test_path_independent_of_cwd_runtime_and_instance_override(self):
        expected = default_recent_file()
        cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with patch.object(config, 'RUNTIME_DIR', str(self.root / 'runtime')):
                self.assertEqual(ProjectManager().recent_file, expected)
                self.create()
                self.assertEqual(ProjectManager().recent_file, expected)
            with patch.dict(os.environ, {'LOCALAPPDATA': 'relative-state'}):
                self.assertEqual(default_recent_file(), Path.home() / '.abqjobpilot/recent_projects.json')
        finally:
            os.chdir(cwd)

    def test_create_open_register_and_fresh_manager_persist(self):
        a = self.create()
        self.assertIsNone(self.manager.current)
        self.assertEqual(ProjectManager(self.store).recent_projects()[0]['project_id'], a.project_id)
        self.manager.open_project(a.root)
        item = ProjectManager(self.store).recent_projects()[0]
        self.assertEqual(item['path'], str(a.root.resolve()))
        self.assertEqual(item['name'], 'A')
        self.assertTrue(item['last_opened_at'])

    def test_real_process_restart_and_different_cwd(self):
        a = self.create()
        code = ('import json,sys; from abqjobpilot.project import ProjectManager; '
                'm=ProjectManager(sys.argv[1]); m.open_project(sys.argv[2]); print(json.dumps(m.recent_projects()))')
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        for _ in range(2):
            output = subprocess.check_output([sys.executable, '-c', code, str(self.store), str(a.root)],
                                             cwd=self.root, env=env, text=True)
            self.assertEqual(json.loads(output)[0]['project_id'], a.project_id)
            self.assertEqual(len(json.loads(output)), 1)

    def test_order_limit_and_dedup(self):
        projects = [self.create(f'P{i}') for i in range(RECENT_LIMIT + 2)]
        self.manager.open_project(projects[-2].root)
        self.manager.open_project(str(projects[-2].root) + os.sep)
        items = self.manager.recent_projects()
        self.assertEqual(len(items), RECENT_LIMIT)
        self.assertEqual(items[0]['project_id'], projects[-2].project_id)
        self.assertEqual(len({r['project_id'] for r in items}), RECENT_LIMIT)

    @unittest.skipUnless(os.name == 'nt', 'Windows filesystem case semantics')
    def test_windows_case_and_separator_aliases(self):
        a = self.create()
        # Different ID ensures path comparison, rather than ID alone, removes the alias.
        data = json.loads(self.store.read_text())
        data['recent_projects'][0].update(path=str(a.root).swapcase() + '\\', project_id='old-id')
        self.store.write_text(json.dumps(data))
        self.manager.open_project(str(a.root).lower() + '\\')
        items = self.manager.recent_projects()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['project_id'], a.project_id)

    def test_existing_migrated_project_registration_never_rewrites_data(self):
        a = self.create('RL-LAM-ScanOPT-Stage1-3')
        (a.root / 'project.db').write_bytes(b'opaque existing database: registration must not open it')
        before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in a.root.rglob('*') if f.is_file()}
        self.assertEqual(self.manager.register_project(a.root).project_id, a.project_id)
        self.assertEqual(before, {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in a.root.rglob('*') if f.is_file()})

    def test_invalid_missing_malformed_and_missing_paths(self):
        self.assertEqual(self.manager.recent_projects(), [])
        with self.assertRaises(ValueError):
            self.manager.open_project(self.root / 'invalid')
        self.assertFalse(self.store.exists())
        a = self.create()
        (a.root / 'project.json').rename(a.root / 'offline.json')
        self.assertEqual(self.manager.recent_projects(), [])
        self.assertEqual(len(self.manager.recent_projects(include_missing=True)), 1)
        for text in ('{bad', '[]', '{"recent_projects": null}', '{"recent_projects": [null, 1, {}]}'):
            self.store.write_text(text)
            self.assertEqual(self.manager.recent_projects(), [])

    def test_archive_and_legacy_register_after_success(self):
        a = self.create()
        archive = export_project_archive(a.root, self.root / 'a.zip')
        imported = import_project_archive(archive, self.root / 'restored', recent_file=self.store)
        self.assertEqual(ProjectManager(self.store).recent_projects()[0]['path'], imported.root_dir)
        self.assertEqual(imported.project_id, a.project_id)
        legacy = self.root / 'legacy'
        legacy.mkdir()
        (legacy / 'queue.json').write_text('[]')
        imported = import_legacy_runtime(legacy, self.root / 'imported', 'Imported', recent_file=self.store)
        self.assertEqual(ProjectManager(self.store).recent_projects()[0]['project_id'], imported.project_id)
        before = self.store.read_bytes()
        with patch('abqjobpilot.database.reconciliation.sync_history_from_runtime', side_effect=ValueError('projection failed')):
            with self.assertRaises(ValueError):
                import_legacy_runtime(legacy, self.root / 'failed', 'Failed', recent_file=self.store)
        self.assertEqual(self.store.read_bytes(), before)
        with self.assertRaises(FileNotFoundError):
            import_project_archive(self.root / 'bad.zip', self.root / 'bad', recent_file=self.store)

    def test_explicit_stores_do_not_write_production(self):
        production = default_recent_file()
        before = production.read_bytes() if production.exists() else None
        self._exercise_isolated_imports()
        self.assertEqual(production.read_bytes() if production.exists() else None, before)

    def _exercise_isolated_imports(self):
        a = self.create('Isolated')
        archive = export_project_archive(a.root, self.root / 'isolated.zip')
        import_project_archive(archive, self.root / 'isolated-copy', recent_file=self.store)
        legacy = self.root / 'isolated-legacy'
        legacy.mkdir()
        (legacy / 'queue.json').write_text('[]')
        import_legacy_runtime(legacy, self.root / 'isolated-import', 'Isolated import', recent_file=self.store)

    def test_gui_seeds_both_recent_menus_at_startup_and_reloads(self):
        from abqjobpilot.gui_app import AbqJobPilotApp
        a = self.create()
        runtime = self.root / 'runtime'
        with patch.object(config, 'RUNTIME_DIR', str(runtime)), \
             patch.object(config, 'QUEUE_FILE', str(runtime / 'queue.json')), \
             patch.object(config, 'LIVE_STATUS_FILE', str(runtime / 'live_status.json')), \
             patch.object(config, 'SETTINGS_FILE', str(runtime / 'settings.json')), \
             patch('abqjobpilot.gui_app.ProjectManager', side_effect=lambda: ProjectManager(self.store)), \
             patch.object(AbqJobPilotApp, '_read_gpu_text', return_value='--'):
            for _ in range(2):
                try:
                    app = AbqJobPilotApp()
                except tk.TclError as exc:
                    self.skipTest(str(exc))
                try:
                    self.assertIsNone(app.project_manager.current)
                    for parent in (app.nametowidget(app.menu_bar.entrycget(0, 'menu')), app.project_dropdown_menu):
                        recent = app.nametowidget(parent.entrycget(5, 'menu'))
                        self.assertIsNotNone(recent.index('end'))
                        self.assertIn(a.name, recent.entrycget(0, 'label'))
                        app.tk.call(recent.cget('postcommand'))
                    recent.invoke(0)
                    self.assertEqual(app.project_manager.current.project_id, a.project_id)
                    self.assertIn(a.name, app.project_name_var.get())
                    self.assertFalse(app.runner.is_running())
                finally:
                    app.destroy()
