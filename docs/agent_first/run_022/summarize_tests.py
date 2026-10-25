"""Preserve iterations, deduplicate parametrized case IDs, never turn skips into passes."""
import json
from pathlib import Path
import xml.etree.ElementTree as E
OUT=Path(__file__).resolve().parent
files=['core_guard_failed.xml','core.xml','product.xml','isolation.xml','legacy.xml','api.xml']
cases={};batches=[]
for name in files:
    path=OUT/name
    if not path.exists():continue
    tree=E.parse(path);counts={k:0 for k in ('PASS','FAIL','ERROR','SKIP')};ids=set()
    for t in tree.iter('testcase'):
        key=t.attrib.get('classname','')+'::'+t.attrib['name'];ids.add(key)
        status='ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
        counts[status]+=1
        cases[key]={'result':status,'source':name}
    batches.append({'file':name,'unique':len(ids),'xml_records':sum(counts.values()),**counts})
result={'deduplication':'classname::parameterized name; final executed result, all initial iteration files retained',
        'batches':batches,'unique':len(cases),'final':{s:sum(x['result']==s for x in cases.values()) for s in ('PASS','FAIL','ERROR','SKIP')},'cases':cases}
(OUT/'TEST_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
