"""Usage: AbqJobPilot-Sanity.cmd <operation> [absolute_project]. One JSON object on stdin."""
import json
import sys
from abqjobpilot.execution.models import ExecutionError, require
from abqjobpilot.sanity_api import VERSION, call

def unique(pairs):
    result={}
    for k,v in pairs:
        require(k not in result,'INVALID_REQUEST','Duplicate JSON field')
        result[k]=v
    return result

def main():
    try:
        require(len(sys.argv) in (2,3),'INVALID_REQUEST','Specify operation and project')
        raw=sys.stdin.buffer.read(65537)
        require(len(raw)<=65536,'LIMIT_EXCEEDED','Bounded input required')
        args=json.loads(raw or b'{}',object_pairs_hook=unique)
        result=call(sys.argv[2] if len(sys.argv)==3 else None,sys.argv[1],args)
        print(json.dumps({'contract':VERSION,'ok':True,'result':result},ensure_ascii=True))
        return 0
    except (ExecutionError,OSError,ValueError,TypeError,KeyError) as exc:
        print(json.dumps({'contract':VERSION,'ok':False,'code':getattr(exc,'code','INVALID_INPUT_OR_IO'),'detail':str(exc)},ensure_ascii=True))
        return 1

if __name__=='__main__':
    sys.exit(main())

