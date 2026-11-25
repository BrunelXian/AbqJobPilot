"""Read-only build identity shown by the application; never sourced from user settings."""
import platform
import sys

from . import __version__
from .application_runtime import SKIN_API_VERSION, is_frozen_runtime, _read_build_identity


def current_build_metadata() -> dict[str, str]:
    if is_frozen_runtime():
        identity = _read_build_identity()
        build_id = identity['build_id']
    else:
        build_id = 'SOURCE / UNBUILT'
    return {
        'product': 'AbqJobPilot',
        'version': __version__,
        'candidate': 'development',
        'qualification': 'TEST_ONLY_NOT_FOR_RELEASE',
        'build_id': build_id,
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'skin_api_version': SKIN_API_VERSION,
        'runtime_mode': 'Frozen' if is_frozen_runtime() else 'Source',
    }
