"""Development-only freeze; never launch, overwrite a candidate or mint approval."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'controller'))
sys.path.insert(0,str(HERE.parents[3]))
import frozen
import package
from records import stable_read, digest


if __name__=='__main__':
    _,old=frozen.load_candidate(package.OLD_DIGEST)
    package.review(HERE/'operator_evidence')
    body=package.configuration(old['body'])
    body['materials']=[]
    for path in package.paths():
        _,info=stable_read(path)
        body['materials'].append({'path':str(path),'bytes':info['bytes'],'sha256':info['sha256']})
    candidate={'body':body,'content_digest':digest(body)}
    with (HERE/'CANDIDATE_MANIFEST.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(candidate,f,ensure_ascii=False,sort_keys=True,separators=(',',':'));f.write('\n')
    print(candidate['content_digest'])
