"""Source/Frozen application identity; never an execution authorization.

Source mode keeps the configured CPython contract. Frozen mode identifies the
actual onedir executable, its fixed role and its bundled build identity.
"""
import hashlib
import json
from pathlib import Path
import platform
import struct
import sys

from . import __version__

APP_ID = 'abqjobpilot.windows'
PRODUCT_VERSION = __version__
SKIN_API_VERSION = '1.0.0'
BUILD_ID_RELATIVE = Path('abqjobpilot') / 'BUILD_ID.json'
GUI_EXECUTABLE = 'AbqJobPilot.exe'
OWNER_EXECUTABLE = 'AbqJobPilotOwner.exe'
OWNER_DIRECTORY = 'AbqJobPilotOwner'


def is_frozen_runtime():
    return bool(getattr(sys, 'frozen', False))


def resource_root():
    """Return the bundled resource root or source checkout root."""
    if is_frozen_runtime():
        root = Path(getattr(sys, '_MEIPASS', '')).resolve()
        require = _require
        require(root.is_dir(), 'HOST_UNSUPPORTED', 'Frozen resource directory is unavailable')
        return root
    return Path(__file__).resolve().parents[1]


def resource_path(relative):
    from .execution.paths import confined
    path = Path(relative)
    if path.is_absolute() or any(part in ('..', '') for part in path.parts):
        from .execution.models import ExecutionError
        raise ExecutionError('INVALID_REQUEST', 'Invalid bundled resource name')
    return confined(resource_root(), resource_root() / path, exists=True)


def _require(ok, code, message):
    from .execution.models import require
    require(ok, code, message)


def _read_build_identity():
    path = resource_path(BUILD_ID_RELATIVE)
    raw = path.read_bytes()
    _require(len(raw) <= 262144, 'HOST_UNSUPPORTED', 'Frozen build identity exceeds bound')
    value = json.loads(raw.decode('utf-8'))
    _require(isinstance(value, dict) and value.get('format') == 'abqjobpilot-build-identity-v1'
             and value.get('app_id') == APP_ID and value.get('roles') == ['gui', 'owner', 'client']
             and value.get('product_version') == PRODUCT_VERSION
             and value.get('skin_api_version') == SKIN_API_VERSION
             and value.get('qualification_mode') in (None, 'TEST_ONLY_NOT_FOR_RELEASE'),
             'HOST_UNSUPPORTED', 'Frozen build identity is invalid')
    claimed = value.get('build_id')
    body = dict(value)
    body.pop('build_id', None)
    encoded = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    actual = 'sha256:' + hashlib.sha256(encoded).hexdigest()
    _require(claimed == actual, 'HOST_UNSUPPORTED', 'Frozen build identity digest differs')
    sources = value.get('source_files')
    _require(isinstance(sources, dict) and all(isinstance(k, str) and isinstance(v, str)
             and len(v) == 64 for k, v in sources.items()),
             'HOST_UNSUPPORTED', 'Frozen source identity list is invalid')
    return value


def executable_role():
    if not is_frozen_runtime():
        return 'source'
    name = Path(sys.executable).name.casefold()
    if name == GUI_EXECUTABLE.casefold():
        return 'gui'
    if name == OWNER_EXECUTABLE.casefold():
        return 'owner'
    if name == 'abqjobpilotcli.exe':
        return 'client'
    _require(False, 'HOST_UNSUPPORTED', 'Unexpected AbqJobPilot executable name')


def owner_executable():
    if not is_frozen_runtime():
        return console_interpreter()
    path = Path(sys.executable).resolve().parent.parent / OWNER_DIRECTORY / OWNER_EXECUTABLE
    path = path.resolve()
    _require(path.is_file(), 'HOST_UNSUPPORTED', 'Frozen Owner executable is unavailable')
    return path


def application_install_root():
    if not is_frozen_runtime():
        return None
    return Path(sys.executable).resolve().parent.parent.resolve()


def _read_portable_test_manifest():
    """Verify the portable TEST_ONLY package metadata and both frozen roles.

    The manifest is shipped beside the onedir role folders. Its build ID must
    match the identity embedded in this executable, and both executable
    digests must match the manifest before the internal Factory is available.
    """
    import re
    from .execution.models import require
    require(is_test_only_build() and executable_role() == 'gui',
            'CAPABILITY_UNAVAILABLE', 'Portable Factory is TEST_ONLY GUI only')
    root = application_install_root()
    manifest_path = root / 'BUILD_MANIFEST.json'
    checksum_path = root / 'BUILD_MANIFEST.sha256'
    require(manifest_path.is_file() and not manifest_path.is_symlink()
            and checksum_path.is_file() and not checksum_path.is_symlink(),
            'HOST_UNSUPPORTED', 'Portable TEST_ONLY build manifest is unavailable')
    raw = manifest_path.read_bytes()
    require(len(raw) <= 4 * 1024 * 1024, 'HOST_UNSUPPORTED', 'Build manifest exceeds bound')
    manifest_digest = hashlib.sha256(raw).hexdigest()
    checksum = checksum_path.read_text(encoding='ascii').strip().split()
    require(len(checksum) == 2 and checksum[0].lower() == manifest_digest
            and checksum[1] == 'BUILD_MANIFEST.json',
            'HOST_UNSUPPORTED', 'Portable build manifest checksum differs')
    manifest = json.loads(raw.decode('utf-8-sig'))
    identity = _read_build_identity()
    require(manifest.get('format') == 'ap-ui03-native-tk-build-manifest-v1'
            and manifest.get('status') == 'TEST_ONLY_NOT_FOR_RELEASE'
            and manifest.get('app_id') == APP_ID
            and manifest.get('product_version') == PRODUCT_VERSION
            and manifest.get('build_id') == identity['build_id']
            and manifest.get('source_files') == identity['source_files']
            and manifest.get('input_verified_before_and_after') is True,
            'HOST_UNSUPPORTED', 'Portable manifest does not match this TEST_ONLY build identity')
    files = manifest.get('distribution_files')
    require(isinstance(files, list), 'HOST_UNSUPPORTED', 'Portable file inventory is invalid')
    indexed = {item.get('path'): item for item in files if isinstance(item, dict)}
    expected = {'gui': f'AbqJobPilot/{GUI_EXECUTABLE}',
                'owner': f'{OWNER_DIRECTORY}/{OWNER_EXECUTABLE}'}
    digests = {}
    for role, relative in expected.items():
        item = indexed.get(relative)
        require(isinstance(item, dict) and re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256', ''))),
                'HOST_UNSUPPORTED', f'Portable {role} digest is absent from the manifest')
        path = (root / relative).resolve(strict=True)
        require(path.is_file() and not path.is_symlink() and path.is_relative_to(root),
                'HOST_UNSUPPORTED', f'Portable {role} image path is invalid')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == item['sha256'], 'HOST_UNSUPPORTED', f'Portable {role} image digest differs')
        digests[role] = actual
    require(manifest.get('roles') == {'gui': f'AbqJobPilot/{GUI_EXECUTABLE}',
                                      'owner': f'{OWNER_DIRECTORY}/{OWNER_EXECUTABLE}'},
            'HOST_UNSUPPORTED', 'Portable executable role paths differ')
    return {'manifest': manifest, 'manifest_sha256': manifest_digest,
            'identity': identity, 'role_sha256': digests}


def assert_external_user_path(value):
    """Keep Projects and user data outside the immutable onedir version tree."""
    if not is_frozen_runtime():
        return Path(value)
    from .execution.models import require
    path = Path(value).resolve()
    root = application_install_root()
    require(path.is_absolute() and not path.is_relative_to(root), 'APP_DATA_IN_INSTALL_DIR',
            'Projects and user data must be outside the Frozen application directory')
    return path


def frozen_fixture_identity():
    """Resolve a fresh frozen fixture pin from the verified build manifest."""
    _require(is_frozen_runtime(), 'HOST_UNSUPPORTED', 'Frozen fixture identity requires a Frozen runtime')
    value = _read_build_identity()
    owner = owner_executable()
    exe_digest = 'sha256:' + hashlib.sha256(owner.read_bytes()).hexdigest()
    sources = value['source_files']
    fixture = sources.get('abqjobpilot/execution/process_fixture.py')
    managed = sources.get('abqjobpilot/execution/managed_process.py')
    _require(fixture and managed, 'HOST_UNSUPPORTED', 'Frozen Fixture source pins are unavailable')
    return {'interpreter': str(owner), 'image': str(owner), 'interpreter_digest': exe_digest,
            'image_digest': exe_digest,
            'fixture_digest': hashlib.sha256((value['build_id'] + ':' + fixture).encode('ascii')).hexdigest(),
            'managed_process_digest': hashlib.sha256((value['build_id'] + ':' + managed).encode('ascii')).hexdigest(),
            'build_id': value['build_id']}


def is_test_only_build():
    """True only for an explicitly marked qualification image, never inferred from its path."""
    return bool(is_frozen_runtime() and _read_build_identity().get('qualification_mode') == 'TEST_ONLY_NOT_FOR_RELEASE')


def require_fake_only(profile=None):
    """Frozen AP-D01B admits TEST_ONLY/Fake only; no Standard/Rod Owner setup."""
    if is_frozen_runtime():
        extension = (profile or {}).get('standard_extension')
        _require(extension is None or (extension.get('format')=='product-fixed-standard-profile-v1'
                 and extension.get('standard_config',{}).get('backend_id')=='abaqus-standard-t3d2-sanity-v1'),
                 'FROZEN_REAL_BACKEND_DISABLED',
                 'Frozen AP-D01B runtime has no Standard or Rod execution qualification')


def require_classic_source():
    """Legacy QueueRunner is unavailable in every product runtime."""
    _require(False, 'CLASSIC_EXECUTION_UNAVAILABLE',
             'Classic Queue execution is unavailable; use the authorized Owner service')


def console_interpreter():
    path = Path(sys.executable).resolve()
    return path.with_name('python.exe') if path.name.lower() == 'pythonw.exe' else path


def validate_runtime():
    from .execution.models import require
    require(sys.platform == 'win32' and platform.python_implementation() == 'CPython',
            'HOST_UNSUPPORTED', 'Windows CPython is required')
    require(sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8,
            'HOST_UNSUPPORTED', 'Use 64-bit CPython 3.12 with Tk')
    if is_frozen_runtime():
        path = Path(sys.executable).resolve()
        role = executable_role()
        _read_build_identity()
        runtime_root = Path(getattr(sys, '_MEIPASS', '')).resolve()
        require(runtime_root.is_dir() and runtime_root.parent == path.parent,
                'HOST_UNSUPPORTED', 'Frozen onedir resources are outside the application directory')
        require(path.is_file(), 'HOST_UNSUPPORTED', 'Frozen application executable is unavailable')
        if role == 'gui':
            require(path.name.casefold() == GUI_EXECUTABLE.casefold(), 'HOST_UNSUPPORTED', 'GUI role identity differs')
        elif role == 'owner':
            require(path.name.casefold() == OWNER_EXECUTABLE.casefold(), 'HOST_UNSUPPORTED', 'Owner role identity differs')
        return path
    path = console_interpreter()
    require(path.name.lower() == 'python.exe' and path.is_file(),
            'HOST_UNSUPPORTED', 'Application console Python is unavailable')
    return path
