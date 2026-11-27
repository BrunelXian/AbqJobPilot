import io
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

from abqjobpilot import __version__, application_runtime, gui_app
from abqjobpilot.api import AbqJobPilotClient
from abqjobpilot.build_metadata import current_build_metadata
from abqjobpilot.execution.models import CONTRACT, DELEGATED_GRANT_CONTRACT
from abqjobpilot.execution.protocol import PROTOCOL
from abqjobpilot.mcp.agent_first_tools import CONTRACT_VERSION as AGENT_FIRST_CONTRACT
from abqjobpilot.sanity_api import VERSION as SANITY_CONTRACT
import launch_cli

SOURCE = Path(__file__).resolve().parents[1] / "src"
EXPECTED_VERSION = "1.0.0"


def test_product_version_is_consistent_across_runtime_surfaces(tmp_path, monkeypatch, capsys):
    version = EXPECTED_VERSION
    build = current_build_metadata()
    assert __version__ == application_runtime.PRODUCT_VERSION == gui_app.__version__ == build["version"] == version
    assert build["runtime_mode"] == "Source" and build["qualification"] == "SOURCE_UNQUALIFIED"
    assert gui_app.AbqJobPilotApp._texts(SimpleNamespace(lang="en"))["about"]["build"] == "Build"
    assert gui_app.AbqJobPilotApp._texts(SimpleNamespace(lang="zh"))["about"]["build"] == "构建版本"

    client = AbqJobPilotClient(runtime_dir=str(tmp_path / "runtime"), recent_file=str(tmp_path / "recent.json"))
    assert client.capabilities()["application_version"] == version
    monkeypatch.setattr(sys, "argv", ["launch_cli"])
    assert launch_cli.main() == 0
    cli = json.loads(capsys.readouterr().out)
    assert (cli["version"], cli["candidate"]) == (version, build["candidate"])

    with io.TextIOWrapper(io.BytesIO(b"{}"), encoding="utf-8") as stdin:
        monkeypatch.setattr(sys, "stdin", stdin)
        monkeypatch.setattr(sys, "argv", ["launch_cli", "sanity", "capabilities", str(tmp_path / "project")])
        assert launch_cli.main() == 0
    sanity = json.loads(capsys.readouterr().out)["result"]
    assert (sanity["product_version"], sanity["candidate"]) == (version, build["candidate"])
    assert sanity["contract"] == SANITY_CONTRACT == "sanity-execution/1.0"
    assert CONTRACT == "af-experiment-v1" and PROTOCOL == "af-local-json-v1"
    assert DELEGATED_GRANT_CONTRACT == "af-test-only-delegated-grant-v2"
    assert AGENT_FIRST_CONTRACT == "abq-agent-first-mcp-v1"
    assert not list(tmp_path.iterdir())


def test_future_frozen_manifest_reads_the_same_product_version_without_building():
    generator = runpy.run_path(str(SOURCE / "tools" / "create_build_identity.py"))
    assert generator["PRODUCT_VERSION"] == __version__ == EXPECTED_VERSION
    recipe = (SOURCE / "tools" / "build_frozen_candidate.ps1").read_text(encoding="utf-8")
    assert "product_version=$identityValue.product_version" in recipe
