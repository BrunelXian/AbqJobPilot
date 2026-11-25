"""Explicit trusted-local policy. No claim of hostile same-user isolation.

This module does not issue Grants, launch processes or impersonate protected proof.
Only the existing ProductStandardControl performs authority operations.
"""
import json

from .models import canonical_json, digest, fields, now, require
from .rod_output_v2 import PROFILE, OUTPUT

TRUST = "TRUSTED_LOCAL_HIL"
FORMAT = "product-trusted-local-rod-v2"


def check_contract(value, phase, candidate):
    if value is None:
        require(candidate['profile'] != PROFILE, 'LOCAL_CONTRACT_REQUIRED', 'v2 requires new local contract')
        return
    fields(value, ('schema', 'trust', 'workflow_digest', 'output_digest', 'runtime', 'causal'))
    from .rod_trusted import _sha
    require(value['schema'] == 'rod-local-hil-v2' and value['trust'] == TRUST
            and candidate['profile'] == PROFILE and phase in ('A', 'B'),
            'LOCAL_CONTRACT_INVALID', 'Explicit new profile and trust required')
    _sha(value['workflow_digest'])
    require(value['output_digest'] == digest(OUTPUT), 'LOCAL_OUTPUT_MISMATCH', 'Frozen output contract differs')
    fields(value['runtime'], ('gd', 'af', 'plugin', 'python', 'versions'))
    for key in ('gd', 'af', 'plugin', 'python'):
        _sha(value['runtime'][key])
    require(value['runtime']['gd'] == value['workflow_digest'], 'LOCAL_RUNTIME_MISMATCH', 'Workflow identity differs')
    if phase == 'A':
        require(value['causal'] is None, 'CAUSAL_MISMATCH', 'A has no predecessor')
    else:
        causal = value['causal']
        fields(causal, ('a_project_instance_id', 'a_run_id', 'a_decision_digest',
                        'a_artifact_digest', 'a_metric_mm', 'a_observed_revision',
                        'owner_stop_digest', 'goal'))
        require(causal['goal'] == 'NOT_MET' and type(causal['a_observed_revision']) is int
                and causal['a_observed_revision'] > 0, 'CAUSAL_MISMATCH', 'Accepted unmet A required')
        for key in ('a_decision_digest', 'a_artifact_digest', 'owner_stop_digest'):
            _sha(causal[key])


def local(plan):
    return 'local_contract' in plan.get('rod_contract', {})


def qualified(service, plan, binding):
    contract = plan['rod_contract']
    value = contract['local_contract']
    check_contract(value, contract['phase'], contract['candidate'])
    check_runtime(service._standard_backend.config, value['runtime'])
    require(binding.get('local_policy_digest') == digest(value)
            and 'authority_digest' not in binding, 'LOCAL_POLICY_MISMATCH',
            'No protected proof substitution')
    return {'policy_digest': digest(value), 'subject': 'HUMAN_LOCAL_CONSOLE',
            'expires_at': plan['expires_at']}


def decision_namespace(context, plan):
    return canonical_json([context.project_instance_id, 'trusted_local_rod_v2_decision', plan['plan_id']])


def require_decision(service, conn, plan, binding):
    qualification = qualified(service, plan, binding)
    rows = conn.execute('SELECT request_digest,body FROM management_receipts WHERE namespace=? LIMIT 2',
                        (decision_namespace(service.context, plan),)).fetchall()
    require(len(rows) == 1, 'HIL_DECISION_REQUIRED', 'One exact human decision required')
    value = json.loads(rows[0][1])
    from .product_standard import scope
    require(rows[0][0] == digest(value) and value['schema'] == 'trusted-local-rod-decision-v2'
            and value['decision'] == 'APPROVE_EXACT' and value['plan_digest'] == plan['plan_digest']
            and value['scope_digest'] == digest(scope(plan))
            and value['policy_digest'] == qualification['policy_digest']
            and value['subject'] == qualification['subject']
            and value['owner_id'] == service.store._session.owner_id
            and value['not_before'] <= now() < value['expires_at'],
            'HIL_DECISION_DENIED', 'Denied, expired or mismatched local decision')
    return value


def source_digest():
    from pathlib import Path
    from .models import bytes_digest
    root = Path(__file__).resolve().parents[1]
    rows = [(p.relative_to(root).as_posix(), bytes_digest(p.read_bytes())) for p in sorted(root.rglob('*.py'))]
    return bytes_digest(json.dumps(rows, separators=(',', ':')).encode())


def plugin_digest(root):
    from pathlib import Path
    from .paths import local_path, no_reparse
    from .standard_contract import identity
    from .models import bytes_digest
    root = local_path(root)
    no_reparse(root)
    names = ['plugin.json', 'scripts/gdcae.py', 'scripts/candidate.py',
             'skills/research/SKILL.md', 'skills/setup/SKILL.md',
             'references/handoff.md', 'references/runtime-contract.json']
    names += ['agents/gdcae-' + role + '.toml' for role in ('cae', 'results', 'inverse', 'reviewer')]
    rows = [(name, identity(Path(root)/name, 1048576)['digest']) for name in sorted(names)]
    return bytes_digest(json.dumps(rows, separators=(',', ':')).encode())


def check_runtime(config, runtime):
    """Narrow Route C closure qualification; does not change legacy fixed policy."""
    from .standard_contract import ENTRY, CMD, PYTHON, identity
    config.verify()
    value = config.value()
    materials = value.get('materials', [])
    require(type(materials) is list and 3 <= len(materials) <= 32,
            'LOCAL_RUNTIME_MISMATCH', 'Declared entry/cmd/python materials required')
    paths = [m['path'].casefold() for m in materials]
    require(len(paths) == len(set(paths)) and {p.casefold() for p in (ENTRY, CMD, PYTHON)} <= set(paths),
            'LOCAL_RUNTIME_MISMATCH', 'Missing or duplicate mandatory materials')
    require(all(identity(m['path']) == m for m in materials)
            and identity(PYTHON)['digest'] == runtime['python']
            and value.get('research_runtime') == runtime and source_digest() == runtime['af']
            and plugin_digest(value.get('research_plugin_root', '')) == runtime['plugin'],
            'LOCAL_RUNTIME_MISMATCH', 'Frozen actual source/runtime differs')
    versions = dependency_versions()
    require(runtime['versions'] == versions, 'LOCAL_RUNTIME_MISMATCH', 'Frozen dependencies differ')


def dependency_versions():
    """Original Owner uses -I -S: inspect the frozen venv metadata, no site hooks."""
    import importlib.metadata
    import platform
    from pathlib import Path
    from .standard_contract import PYTHON
    from .paths import no_reparse
    packages = Path(PYTHON).parent.parent / 'Lib' / 'site-packages'
    no_reparse(packages)
    found = {name: [] for name in ('mcp', 'pydantic', 'pywin32')}
    for dist in importlib.metadata.distributions(path=[str(packages)]):
        name = (dist.metadata.get('Name') or '').lower().replace('_', '-')
        if name in found:
            found[name].append(dist.version)
    require(all(len(values) == 1 for values in found.values()),
            'LOCAL_RUNTIME_MISMATCH', 'Missing or ambiguous frozen dependency metadata')
    return {'python': platform.python_version(), **{name: values[0] for name, values in found.items()}}


def owner_runtime_preview(config):
    """Read-only Route C selection of the ORIGINAL fixed interpreter/Owner.

    The caller interpreter may be isolated. No arbitrary executable, new host,
    capability, startup reservation or process is accepted/created here.
    """
    from pathlib import Path
    from .standard_contract import PYTHON, identity
    value = config.value()
    require(value.get('rod_profile') == PROFILE, 'LOCAL_POLICY_MISMATCH',
            'Only explicit Route C output-v2 uses this selection')
    check_runtime(config, value.get('research_runtime'))
    entry = Path(__file__).resolve().parents[1] / 'service_owner.py'
    return {'policy': 'route-c-fixed-owner-interpreter-v1',
            'interpreter': identity(PYTHON), 'owner_entry': identity(entry),
            'af_source_digest': source_digest(), 'arguments': ['-I', '-S', '-B'],
            'launch_authorized': False, 'ipc': 'EXISTING_PROJECT_SCOPED_IPC'}
