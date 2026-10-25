"""Read-only Dev Git candidate audit. No staging, cleanup or external tree scan."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8', errors='strict')


paths = sorted(set(filter(None, git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split('\0'))))
ignored = sorted(filter(None, git('ls-files', '--others', '--ignored', '--exclude-standard', '-z').split('\0')))
rows = []
for name in paths:
    p = ROOT/name
    if not p.is_file() or name.startswith(('runtime/', '.git/')):
        continue
    size = p.stat().st_size
    row = {'path': name, 'bytes': size, 'group':
           'application' if name.startswith('abqjobpilot/') else
           'tests' if name.startswith('tests/') else
           'operator_and_examples' if name.startswith('examples/') else
           'historical_reports' if name.startswith('docs/agent_first/') else 'other',
           'flags': []}
    if size > 1024*1024: row['flags'].append('LARGE_REVIEW')
    if p.suffix.lower() in {'.sqlite3', '.sqlite', '.db', '.odb'}: row['flags'].append('RUNTIME_DATABASE_OR_OUTPUT_EXCLUDE')
    if p.suffix.lower() in {'.bin', '.png', '.jpg', '.zip'}: row['flags'].append('BINARY_EXPLICIT_REVIEW')
    if any(part.lower() in {'private', 'runtime', 'backups'} for part in p.relative_to(ROOT).parts):
        row['flags'].append('PRIVATE_OR_RUNTIME_EXCLUDE')
    if size <= 5*1024*1024 and p.suffix.lower() in {'.json', '.py', '.md', '.txt', '.vbs', '.xml'}:
        # Findings list names/counts, never candidate secrets or arbitrary values.
        content = p.read_text(encoding='utf-8-sig', errors='replace')
        matches = re.findall(r'"(?:credential|operator_token|password|api_key)"\s*:\s*"([^"\r\n]{16,})"', content)
        if matches:
            row['flags'].append('POSSIBLE_LITERAL_SECRET_REVIEW')
            row['sensitive_field_matches'] = len(matches)
        if re.search(r'[CD]:\\\\?(?:Users|XianLab|ABAQUS2024|Program Files)', content):
            row['flags'].append('LOCAL_PATH_REVIEW')
    rows.append(row)

base = json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8-sig'))
changed = []; missing = []
for name, expected in base['files'].items():
    path = ROOT/name
    if not path.is_file(): missing.append(name)
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected: changed.append(name)
result = {'head': git('rev-parse', 'HEAD').strip(), 'branch': git('branch', '--show-current').strip(),
          'conflicts': git('ls-files', '-u'), 'status': git('status', '--porcelain'),
          'candidate_count': len(rows), 'candidate_bytes': sum(r['bytes'] for r in rows),
          'ignored_paths': ignored, 'assets': rows, 'baseline_count': len(base['files']),
          'changed_prior_files': changed, 'missing_prior_files': missing,
          'note': 'Flags are review candidates, not proof of credential leakage; no credential values exported'}
with (OUT/'GIT_ASSET_AUDIT.json').open('x', encoding='utf-8') as f:
    f.write(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'candidate_count': len(rows), 'ignored_count': len(ignored),
                  'large': [r['path'] for r in rows if 'LARGE_REVIEW' in r['flags']],
                  'possible_secrets': [r['path'] for r in rows if 'POSSIBLE_LITERAL_SECRET_REVIEW' in r['flags']],
                  'db_or_outputs': [r['path'] for r in rows if 'RUNTIME_DATABASE_OR_OUTPUT_EXCLUDE' in r['flags']],
                  'changed_prior_files': changed, 'missing_prior_files': missing}))
