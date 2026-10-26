"""Copy an explicit reviewed source closure; never includes historical raw fixtures."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
DEST=OUT/'local_verification/source'
DEST.mkdir(parents=True,exist_ok=False)
frozen=json.loads((OUT/'SNAPSHOT_FILES.json').read_text())
paths={r['path'] for r in frozen}
expected={r['path']:r['sha256'] for r in frozen}
assert not any('ORIGINAL_DAT.bin' in p or 'historical_invalid_after.json' in p for p in paths)
records=[]
for rel in sorted(paths):
    src=ROOT/rel;dst=DEST/rel
    assert hashlib.sha256(src.read_bytes()).hexdigest()==expected[rel], 'Candidate changed: '+rel
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    records.append({'path':rel,'bytes':src.stat().st_size,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
print(json.dumps({'copied_files':len(records),'raw_historical_fixtures_present':False}))
