"""Fixed application artwork; independent of skins and execution authority."""
import ctypes
import sys
from .application_runtime import resource_root, is_frozen_runtime, _read_build_identity


def icon_variant():
    # Source and all current qualification builds retain the DEV identity.
    if is_frozen_runtime():
        return _read_build_identity().get('icon_variant', 'development')
    return 'development'


def initialize_taskbar():
    if sys.platform == 'win32':
        variant = icon_variant()
        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        result = setter(
            'AbqJobPilot.' + ('Release' if variant == 'release' else 'Development'))
        if result != 0:
            raise RuntimeError('TASKBAR_ID_INITIALIZATION_FAILED')


def apply_window_icon(window):
    variant = icon_variant()
    if variant not in ('release', 'development'):
        raise RuntimeError('INVALID_BUILD_ICON_VARIANT')
    filename = 'abqjobpilot_release.ico' if variant == 'release' else 'abqjobpilot_dev.ico'
    path = resource_root() / 'assets' / 'icons' / 'antigravity-approved-B-dark' / filename
    if not path.is_file():
        raise RuntimeError('APPLICATION_ICON_MISSING')
    window.iconbitmap(str(path))
    window.application_icon_path = path
