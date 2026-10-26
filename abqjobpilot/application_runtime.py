"""Application interpreter policy, not an execution authorization or search path.

Use the explicitly launched CPython installation. A pythonw GUI starts its
console sibling for the independent owner. Fixed plans keep their own pins.
"""
from pathlib import Path
import platform
import struct
import sys


def console_interpreter():
    path = Path(sys.executable).resolve()
    return path.with_name('python.exe') if path.name.lower() == 'pythonw.exe' else path


def validate_runtime():
    from .execution.models import require
    require(sys.platform == 'win32' and platform.python_implementation() == 'CPython',
            'HOST_UNSUPPORTED', 'Windows CPython is required')
    require(sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8,
            'HOST_UNSUPPORTED', 'Use 64-bit CPython 3.12 with Tk')
    path = console_interpreter()
    require(path.name.lower() == 'python.exe' and path.is_file(),
            'HOST_UNSUPPORTED', 'Application console Python is unavailable')
    return path
