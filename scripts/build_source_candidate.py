"""Build only the reviewed release_inputs.json files; no Git or external tools.

Usage: python -B scripts/build_source_candidate.py --output <new-directory>
Run from a reviewed checkout/source snapshot containing this script and manifest.
Existing output directories are never overwritten. No Project data is discovered.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_inputs(root: Path, manifest: dict) -> dict[str, bytes]:
    if manifest.get('format') != 1 or manifest.get('version') != '0.3.0.dev0':
        raise ValueError('Unsupported build manifest')
    payload = {}
    for row in manifest['files']:
        name = row['path']; p = PurePosixPath(name)
        if not name or '\\' in name or ':' in name or p.is_absolute() or any(x in {'', '.', '..'} for x in name.split('/')):
            raise ValueError('Invalid manifest path')
        if name in payload:
            raise ValueError('Duplicate manifest path')
        source = root.joinpath(*p.parts)
        if not source.resolve().is_relative_to(root.resolve()):
            raise ValueError('Source escapes build root')
        data = source.read_bytes()
        if digest(data) != row['sha256'] and row.get('allow_crlf_checkout'):
            # Canonical LF Git blobs may be CRLF in a Windows checkout. Do not
            # write source files; accept only the exact reviewed resulting hash.
            data = data.replace(b'\r\n', b'\n')
        if digest(data) != row['sha256']:
            raise ValueError('Input hash mismatch: ' + name)
        payload[name] = data
    if not payload:
        raise ValueError('Empty input set')
    return payload

def archive(payload: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path, data in sorted(payload.items()):
            item = zipfile.ZipInfo('AbqJobPilot/' + path, (1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            output.writestr(item, data, compresslevel=9)
    return stream.getvalue()

def build(root: Path, destination: Path) -> dict:
    manifest_bytes = (root/'scripts/release_inputs.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    payload = load_inputs(root, manifest)
    data = archive(payload)
    if data != archive(payload):
        raise ValueError('Reproducibility check failed')
    destination.mkdir(parents=True, exist_ok=False)
    name = 'AbqJobPilot-0.3.0.dev0-source-rc-f02.zip'
    (destination/name).write_bytes(data)
    report = {'version': manifest['version'], 'base_commit': manifest['base_commit'],
              'manifest_sha256': digest(manifest_bytes), 'package': name, 'package_sha256': digest(data),
              'file_count': len(payload), 'reproducible': True,
              'files': [{'path': p, 'bytes': len(b), 'sha256': digest(b)} for p,b in sorted(payload.items())]}
    (destination/'BUILD.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(Path(__file__).resolve().parents[1], args.output.resolve())
    print(json.dumps({k: result[k] for k in ('package','package_sha256','file_count','reproducible')}))

if __name__ == '__main__':
    main()
