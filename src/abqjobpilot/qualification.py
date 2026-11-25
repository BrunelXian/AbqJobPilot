"""Explicit immutable TEST_ONLY scope, never a Grant or a release entry point."""
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path

ACTIVE = ContextVar('ap_d02_qualification', default=None)
FORMAT = 'ap-d02-acceptance-v1'


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, expected_digest):
    from .application_runtime import application_install_root, _read_build_identity, is_test_only_build
    from .execution.models import require
    from .execution.paths import no_reparse
    require(is_test_only_build(), 'CAPABILITY_UNAVAILABLE', 'Only a TEST_ONLY Frozen image can load qualification scope')
    candidate = application_install_root().parent.resolve()
    allowed = candidate.parent / 'test-sandbox' / 'ap-d02'
    config_path = Path(path)
    require(config_path.is_absolute(), 'TEST_AUTHORITY_SCOPE', 'Explicit qualification path required')
    no_reparse(config_path)
    require(config_path.resolve().is_relative_to(allowed) and config_path.stat().st_size <= 16384,
            'TEST_AUTHORITY_SCOPE', 'Qualification must be under the isolated AP-D02 root')
    raw = config_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_digest, 'TEST_AUTHORITY_SCOPE', 'Immutable qualification digest differs')
    value = json.loads(raw)
    require(value['format'] == FORMAT and value['candidate_root'] == str(candidate)
            and value['build_id'] == _read_build_identity()['build_id']
            and value['scenario'] in ('normal', 'result_wait')
            and type(value['max_runs']) is int and value['max_runs'] == 1
            and type(value['max_seconds']) is int and value['max_seconds'] == 40
            and value['managed_scope'] is True and type(value['max_process_members']) is int and value['max_process_members'] == 32,
            'TEST_AUTHORITY_SCOPE', 'Fixed qualification contract differs')
    sandbox = Path(value['sandbox'])
    require(sandbox.parent == allowed and sandbox.is_dir()
            and Path(value['project']) == sandbox / 'fixture' / 'Project'
            and Path(value['evidence']).parent == sandbox,
            'TEST_AUTHORITY_SCOPE', 'Exact isolated Project and evidence scope required')
    for target in (sandbox, Path(value['project']), Path(value['evidence'])):
        no_reparse(target)
    for role, relative in (('gui', 'AbqJobPilot/AbqJobPilot.exe'), ('owner', 'AbqJobPilotOwner/AbqJobPilotOwner.exe')):
        image = candidate / 'dist' / relative
        no_reparse(image)
        require(value[role]['path'] == str(image) and value[role]['sha256'] == digest_file(image),
                'TEST_AUTHORITY_SCOPE', 'Exact candidate image identity differs')
    require(digest_file(candidate / 'BUILD_MANIFEST.json') == value['manifest_sha256'],
            'TEST_AUTHORITY_SCOPE', 'Build manifest differs')
    return value


def require_owner_project(service, scenario):
    """Factory binding restricts the existing Owner issuer; it grants no power."""
    from .application_runtime import _read_build_identity, application_install_root
    from .execution.models import require
    from .execution.paths import no_reparse
    root = Path(service.context.test_root)
    allowed = application_install_root().parent.parent / 'test-sandbox' / 'ap-d02'
    path = root.parent.parent / 'factory-binding.json'
    no_reparse(path)
    require(root.parent.name == 'fixture' and root.name == 'Project'
            and root.parent.parent.parent == allowed, 'TEST_AUTHORITY_SCOPE', 'Fixed qualification root required')
    binding = json.loads(path.read_text(encoding='utf-8'))
    require(binding['build_id'] == _read_build_identity()['build_id']
            and binding['project_instance_id'] == service.context.project_instance_id
            and binding['context_digest'] == service.context.context_digest
            and binding['scenario'] == scenario and binding['max_runs'] == 1,
            'TEST_AUTHORITY_SCOPE', 'Factory/Owner/Scenario binding differs')
