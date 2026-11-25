"""Console transport for the same native product; no service or Solver auto-start."""
import json, sys
from abqjobpilot.application_runtime import validate_runtime, executable_role, is_frozen_runtime
from abqjobpilot.build_metadata import current_build_metadata
def main():
    validate_runtime()
    if is_frozen_runtime() and executable_role() != 'client':
        raise RuntimeError('CLIENT_EXECUTABLE_IDENTITY_INVALID')
    args=sys.argv[1:]
    if not args:
        build = current_build_metadata()
        print(json.dumps({**{key: build[key] for key in ('product', 'version', 'candidate')},
                          'interfaces': ['agent', 'classic', 'mcp', 'sanity', 'operator'],
                          'real_execution': 'EXACT_TRUSTED_SANITY_GRANT_REQUIRED'}))
        return 0
    mode=args.pop(0);sys.argv=[sys.argv[0],*args]
    if mode=='agent':
        from abqjobpilot.agent_public import main as command
    elif mode=='classic':
        from abqjobpilot.api.cli import main as command
    elif mode=='mcp':
        from abqjobpilot.mcp.server import main as command
    elif mode=='sanity':
        from sanity_cli import main as command
    elif mode=='operator':
        from sanity_operator import main as command
        print(json.dumps(command(),ensure_ascii=True));return 0
    else:
        print(json.dumps({'ok':False,'code':'INVALID_REQUEST'}));return 2
    return command()
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'ok':False,'code':getattr(exc,'code','CLIENT_ERROR'),'detail':str(exc)}));raise SystemExit(2)
