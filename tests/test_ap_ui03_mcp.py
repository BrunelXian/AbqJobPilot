"""MCP boundary smoke test against an isolated TEST_ONLY Project; no Solver calls."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from abqjobpilot.project.manager import ProjectManager
from abqjobpilot.mcp.server import build_server


class MCPReadOnlySurfaceTests(unittest.TestCase):
    def test_five_read_only_tools_remain_available(self):
        with tempfile.TemporaryDirectory(prefix="ap-ui03-mcp-test-only-") as temp:
            root = Path(temp)
            project = root / "TEST_ONLY_Project"
            ProjectManager(recent_file=root / "recent.json").create_project(project, "TEST_ONLY Project")
            server = build_server(str(project))
            tools = asyncio.run(server.list_tools())
            self.assertEqual({tool.name for tool in tools}, {
                "abq_preflight", "abq_list_jobs", "abq_job_status",
                "abq_locate_outputs", "abq_prepare_enqueue",
            })
            self.assertTrue(all(tool.annotations and tool.annotations.read_only_hint for tool in tools))


if __name__ == "__main__":
    unittest.main()
