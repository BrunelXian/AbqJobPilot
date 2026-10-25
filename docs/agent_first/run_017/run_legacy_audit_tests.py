"""Explicit isolated audit selection; no default Runtime/Recent writes and no Solver."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
root = Path(tempfile.mkdtemp(prefix='AbqJobPilot_Run017_legacy_')).resolve()
os.environ.update(TEMP=str(root), TMP=str(root), PYTHONDONTWRITEBYTECODE='1',
                  PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONIOENCODING='utf-8')
tempfile.tempdir = str(root)
(root / 'home').mkdir()
print('ISOLATED_ROOT=' + str(root), flush=True)

# Only imports/queries and explicitly selected legacy queue/file tests. The
# process tests here spawn the registered interpreter for CLI/MCP checks only.
with patch.object(Path, 'home', return_value=root / 'home'):
    from abqjobpilot import config
    config.use_runtime_dir(root / 'runtime')
    import pytest
    sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', str(root / 'cases'),
        '--junitxml', str(root / 'result.xml'), '-o', 'tmp_path_retention_policy=all',
        'tests/test_mcp_readonly.py', 'tests/test_project_model.py',
        'tests/test_project_database.py', 'tests/test_project_file_ownership.py',
        'tests/test_queue_only_enqueue.py',
        'tests/test_public_api.py::TestPublicApi',
        'docs/agent_first/run_017/test_format_boundaries.py']))
