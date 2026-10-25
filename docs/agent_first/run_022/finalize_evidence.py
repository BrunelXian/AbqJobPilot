"""Archive selected public test evidence, inventory remaining private test copies."""
import hashlib,json,os
from pathlib import Path
OUT=Path(__file__).resolve().parent
root=Path(json.loads((OUT/'product_ROOT.json').read_text())['root'])
target=OUT/'windows';target.mkdir(exist_ok=True)
index=[]
for name in ('020/fixed_worker_product.json','020/empty_gui_product.json','021B/test_product_standard_gui_full0.json'):
    p=root/'evidence'/name;raw=p.read_bytes();value=json.loads(raw)
    def check(v):
        if isinstance(v,dict):
            assert not {'credential','operator_token','ciphertext'}.intersection(v),'Do not archive secret-bearing objects'
            for x in v.values():check(x)
        elif isinstance(v,list):
            for x in v:check(x)
    check(value)
    destination=target/p.name
    with destination.open('xb') as f:f.write(raw)
    index.append({'source':str(p),'copy':str(destination.relative_to(OUT)),'sha256':hashlib.sha256(raw).hexdigest(),
                  'abaqus_calls':value['abaqus_calls']})
(OUT/'WINDOWS_EVIDENCE_INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
cleanup=json.loads((OUT/'CLEANUP.json').read_text(encoding='utf-8'))
assert not cleanup['matched_alive'] and not cleanup['report_secret_leaks']
residual=[]
for text in cleanup['roots']:
    r=Path(text);assert r.name.startswith('AbqJobPilot_Run022_')
    for directory,dirs,names in os.walk(r,followlinks=False):
        dirs[:]=[n for n in dirs if not ((Path(directory)/n).is_junction() or (Path(directory)/n).is_symlink())]
        for name in names:
            p=Path(directory)/name
            if p.suffix!='.json' or p.is_symlink():continue
            try:v=json.loads(p.read_text(encoding='utf-8'))
            except (OSError,ValueError,UnicodeError):continue
            if isinstance(v,dict) and ('ciphertext' in v or 'credential' in v or 'operator_token' in v):
                residual.append({'path':str(p),'fields':[k for k in ('format','credential','operator_token','ciphertext') if k in v],
                                 'format':v.get('format')})
(OUT/'PRIVATE_RESIDUAL_REVIEW.json').write_text(json.dumps(residual,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'public_copies':len(index),'residual_private_candidates':len(residual)},indent=2))
