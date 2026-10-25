"""Read this Run's frozen inventory; produce metadata only, never inspect other projects."""
import ast
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
baseline = json.loads((OUT / 'BASELINE.json').read_text(encoding='utf-8'))
entries = baseline['entries']
if isinstance(entries, dict):
    entries = [{'path': k, **v} for k, v in entries.items()]
paths = [Path(e['path']) for e in entries]
paths = [p if p.is_absolute() else ROOT / p for p in paths]
sources = [p for p in paths if p.suffix == '.py' and
           p.relative_to(ROOT).parts[0] in ('abqjobpilot', 'examples')]
trees = {p: ast.parse(p.read_text(encoding='utf-8-sig')) for p in sources}
stage = {
    'client': 'Run003', 'protocol': 'Run003', 'ownership': 'Run003', 'supervisor': 'Run003',
    'reconciliation': 'Run004', 'diagnostics': 'Run005', 'audit_export': 'Run005',
    'process_backend': 'Run006', 'process_contract': 'Run006', 'process_fixture': 'Run006',
    'process_handles': 'Run006', 'process_validation': 'Run006',
    'process_reconciliation': 'Run007', 'public_workflow': 'Run008', 'test_authority': 'Run008',
    'progress_log': 'Run012', 'closeout': 'Run014', 'managed_process': 'Run015',
    'standard_sequence': 'Run016', 'standard_backend': 'Run013', 'standard_contract': 'Run013',
    'standard_dat': 'Run013', 'standard_process': 'Run013',
}
tests = {p: p.read_text(encoding='utf-8-sig') for p in (ROOT / 'tests').glob('test_*.py')}
rows, symbols = [], {}
for p, tree in trees.items():
    rel = p.relative_to(ROOT).as_posix()
    af = '/execution/' in rel
    intro = stage.get(p.stem, 'Run002; later changes see Run reports') if af else (
        'Run009' if '/abaqus_preview/' in rel else
        'Run012' if p.stem in ('execution_gui', 'gui_legacy', 'dev_gui_demo') else
        'legacy / stage not inferred')
    funcs = [f'{n.name}:{n.lineno}' for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    symbols[rel] = funcs
    imports = set()
    for other, ot in trees.items():
        if other == p:
            continue
        for n in ast.walk(ot):
            if isinstance(n, ast.ImportFrom) and ((n.module or '').split('.')[-1] == p.stem or
                 any(a.name == p.stem for a in n.names)):
                imports.add(other.relative_to(ROOT).as_posix())
            if isinstance(n, ast.Import) and any(a.name.endswith('.' + p.stem) for a in n.names):
                imports.add(other.relative_to(ROOT).as_posix())
    calls = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = ast.unparse(n.func)
            if any(w in name.lower() for w in ('popen','createprocess','write','sqlite','transaction',
                   'terminate','unlink','mkdir','save','execute','create_job','mint','issue')):
                calls.add(name)
    coverage = [t.name for t, text in tests.items() if p.stem in text and p.stem != '__init__']
    authority = ('explicit experiment.json / execution.sqlite3; role depends on API' if af else
                 'offline engineering inputs, no execution Store' if '/abaqus_preview/' in rel else
                 'public IPC only' if p.stem == 'execution_gui' else
                 'trusted explicit isolated setup' if rel.startswith('examples/') else
                 'legacy Project/Runtime or utility; see architecture review')
    recommendation = ('retain; separate privileged setup from client' if rel.startswith('examples/') else
                      'retain; do not merge historical schemas by name')
    rows.append([rel, intro, (ast.get_docstring(tree) or '; '.join(funcs[:6])).split('\n')[0],
                 '; '.join(sorted(imports)) or 'dynamic/entrypoint/none statically found',
                 '; '.join(sorted(calls)) or 'no keyword-matched side effect; manual review still required',
                 authority, '; '.join(coverage) or 'no lexical match; not a coverage claim', recommendation])
with (OUT / 'SOURCE_ASSETS.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['file','stage_evidence_hint','responsibility','static_callers','side_effect_call_candidates',
                'data_authority','test_candidates_not_coverage','recommendation'])
    w.writerows(rows)
(OUT / 'SOURCE_SYMBOLS.json').write_text(json.dumps(symbols, ensure_ascii=False, indent=2), encoding='utf-8')

# Report names/keys only; never print credential values or unfiltered payloads.
findings, data_files = [], []
secret_keys = {'credential', 'token', 'secret', 'password', 'ipc_token', 'authkey', 'signature', 'proof'}
def walk(value, pointer, relative):
    if isinstance(value, dict):
        for k, v in value.items():
            loc = pointer + '/' + str(k)
            if k.lower() in secret_keys and isinstance(v, str) and v:
                findings.append({'file': relative, 'key': loc, 'length': len(v),
                                 'classification': 'REVIEW_REQUIRED_NOT_PROOF_OF_LIVE_SECRET'})
            walk(v, loc, relative)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk(v, pointer + '/' + str(i), relative)
for p in paths:
    rel = p.relative_to(ROOT).as_posix()
    if p.suffix.lower() in {'.db','.sqlite','.sqlite3','.odb','.inp','.cae','.bin'} or p.stat().st_size > 1_000_000:
        data_files.append({'file': rel, 'bytes': p.stat().st_size})
    if p.suffix == '.json' and p.stat().st_size < 2_000_000:
        try:
            walk(json.loads(p.read_text(encoding='utf-8-sig')), '', rel)
        except (ValueError, UnicodeError):
            pass
(OUT / 'GIT_DATA_REVIEW.json').write_text(json.dumps({'scope':'nonignored baseline files only; not general secret scanning',
    'structured_sensitive_key_candidates': findings, 'data_or_large_files': data_files}, indent=2), encoding='utf-8')
print(json.dumps({'source_modules':len(rows),'structured_key_candidates':len(findings),'data_or_large':len(data_files)}))
