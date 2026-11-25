"""Create deterministic Frozen source/build identity metadata."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from abqjobpilot import __version__ as PRODUCT_VERSION

APP_ID = 'abqjobpilot.windows'
SKIN_API_VERSION = '1.0.0'
PINNED = {
    'python': '3.12.10',
    'pyinstaller': '6.22.3',
    'pyinstaller-hooks-contrib': '2026.9',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--test-only', action='store_true',
                        help='mark an isolated, non-release qualification image')
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", PRODUCT_VERSION) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", SKIN_API_VERSION):
        raise SystemExit('INVALID_BUILD_VERSION')
    root = ROOT
    installed = {
        'python': '.'.join(map(str, sys.version_info[:3])),
        'pyinstaller': importlib.metadata.version('pyinstaller'),
        'pyinstaller-hooks-contrib': importlib.metadata.version('pyinstaller-hooks-contrib'),
    }
    if installed != PINNED:
        raise SystemExit('BUILD_DEPENDENCY_IDENTITY_MISMATCH')
    paths = {root / 'launch_gui.py', root / 'launch_owner.py', root / 'launch_cli.py', root / 'sanity_cli.py', root / 'sanity_operator.py', root / 'LICENSE', root / 'settings.toml',
             root / 'requirements-build.txt', root / 'requirements-build.lock.txt'}
    if (root / 'abqjobpilot.ico').is_file():
        paths.add(root / 'abqjobpilot.ico')
    paths.update(path for path in (root / 'abqjobpilot').rglob('*.py')
                 if 'abqjobpilot' not in path.relative_to(root / 'abqjobpilot').parts)
    paths.update((root / 'abqjobpilot' / 'locales').glob('*.json'))
    paths.update((root / 'skins').rglob('manifest.json'))
    paths.update(path for path in (root / 'assets' / 'icons').rglob('*') if path.is_file())
    files = {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
    }
    tree_material = ''.join(f'{name}\t{digest}\n' for name, digest in sorted(files.items())).encode('utf-8')
    payload = {
        'format': 'abqjobpilot-build-identity-v1',
        'app_id': APP_ID,
        'product_version': PRODUCT_VERSION,
        'skin_api_version': SKIN_API_VERSION,
        'icon_variant': 'development',
        'icon_set': 'antigravity-approved-B-dark',
        'roles': ['gui', 'owner', 'client'],
        'identity_schema': 1,
        'source_tree_sha256': hashlib.sha256(tree_material).hexdigest(),
        'source_files': files,
        'build_environment': installed,
    }
    if args.test_only:
        payload['qualification_mode'] = 'TEST_ONLY_NOT_FOR_RELEASE'
    identity = {**payload, 'build_id': 'sha256:' + hashlib.sha256(canonical(payload)).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(identity, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'build_id': identity['build_id'], 'source_tree_sha256': payload['source_tree_sha256'],
                      'source_count': len(files), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
