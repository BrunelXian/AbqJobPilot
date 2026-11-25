"""Narrow standalone Owner entry point for Source and Frozen onedir builds."""
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        from abqjobpilot.application_runtime import executable_role, is_frozen_runtime, validate_runtime
        validate_runtime()
        frozen = is_frozen_runtime()
        if frozen and executable_role() != 'owner':
            raise RuntimeError('OWNER_EXECUTABLE_IDENTITY_INVALID')
        if argv and argv[0] == '--fixture-role':
            if not frozen:
                raise RuntimeError('OWNER_FIXTURE_FROZEN_ONLY')
            import argparse
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument('--role', choices=('launcher', 'worker', 'branch', 'leaf', 'burst'), required=True)
            parser.add_argument('--directory', required=True)
            parser.add_argument('--index', type=int, choices=range(6), default=0)
            try:
                args = parser.parse_args(argv[1:])
            except SystemExit:
                return 2
            # Restore the historical fixed-role route and its static bundle dependency.
            # Fixture code has no service credentials, Store access or Solver command.
            from abqjobpilot.execution.process_fixture import main as fixture_main
            return fixture_main(['--role', args.role, '--directory', args.directory,
                                 '--index', str(args.index)])
        if not argv or argv[0] != '--service-owner':
            raise RuntimeError('OWNER_FIXED_COMMAND_REQUIRED')
        from abqjobpilot.service_owner import main as owner_main
        owner_main(argv[1:])
        return 0
    except Exception as exc:
        from abqjobpilot.execution.models import ExecutionError
        code = exc.code if isinstance(exc, ExecutionError) else str(exc) if str(exc).isupper() else 'SERVICE_HOST_FAILED'
        print(code, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
