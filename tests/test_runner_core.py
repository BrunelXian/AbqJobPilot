import unittest

from abqjobpilot.runner_core import (
    _hidden_creationflags,
    _hidden_startupinfo,
    build_abaqus_datacheck_command,
    build_abaqus_full_run_command,
)


class TestRunnerCore(unittest.TestCase):
    def test_full_run_command_includes_resources(self):
        command = build_abaqus_full_run_command(
            {
                "job_name": "Job_test",
                "inp_path": r"D:\Projects\abqjobpilot\tests\fixtures\Job_test.inp",
                "cpus": 12,
                "gpus": 1,
            }
        )
        self.assertIn("cpus=12", command)
        self.assertIn("gpus=1", command)
        self.assertIn("interactive", command)
        self.assertNotIn("shell=True", command)

    def test_datacheck_command_never_includes_gpus(self):
        command = build_abaqus_datacheck_command(
            {
                "job_name": "Job_test",
                "inp_path": r"D:\Projects\abqjobpilot\tests\fixtures\Job_test.inp",
                "cpus": 12,
                "gpus": 1,
            }
        )
        self.assertIn("cpus=12", command)
        self.assertIn("datacheck", command)
        self.assertNotIn("gpus=1", command)

    def test_abaqus_process_uses_hidden_window_options(self):
        startupinfo = _hidden_startupinfo()
        if startupinfo is not None:
            self.assertEqual(startupinfo.wShowWindow, 0)
        self.assertIsInstance(_hidden_creationflags(), int)


if __name__ == "__main__":
    unittest.main()
