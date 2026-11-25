"""One Owner-local uncertain Fixture attempt; observation never changes Store facts.

No discovery, adoption, termination, dispatch or recovery authority. Handles
remain held after the query/time budget expires until Owner teardown.
"""
import threading
import time
from .models import require


class AttemptResources:
    MAX_QUERIES = 64
    OBSERVATION_SECONDS = 1800

    def __init__(self):
        self._lock = threading.RLock()
        self.active = None

    def begin(self, run):
        with self._lock:
            require(self.active is None, 'MANAGED_SCOPE_UNKNOWN',
                    'Owner retains an unresolved Fixture attempt; no new creation')
            self.active = {'binding': {k: run[k] for k in
                           ('project_instance_id', 'run_id', 'phase_attempt_id', 'owner_id', 'owner_epoch')},
                           'scope': None, 'process': None, 'refs': {}, 'uncertain': False,
                           'queries': 0, 'created_monotonic': time.monotonic()}
            return self.active

    def finish(self, *, failed):
        with self._lock:
            item = self.active
            if item is None:
                return []
            has_handles = item['scope'] is not None or item['process'] is not None or bool(item['refs'])
            if failed and has_handles:
                item['uncertain'] = True
                return []
            errors = self._close(item)
            if not errors:
                self.active = None
            else:
                item['uncertain'] = True
            return errors

    @staticmethod
    def _close(item):
        errors, seen = [], set()
        for resource in list(item['refs'].values()) + [item['process'], item['scope']]:
            if resource is None or id(resource) in seen:
                continue
            seen.add(id(resource))
            try:
                close = getattr(resource, 'close', None)
                if close:
                    close()  # Never terminate; no KILL_ON_JOB_CLOSE.
            except Exception as exc:
                errors.append(exc)
        return errors

    def observe(self, run_id):
        with self._lock:
            item = self.active
            require(item is not None and item['binding']['run_id'] == run_id,
                    'MANAGED_SCOPE_UNKNOWN', 'Original retained attempt unavailable')
            require(item['queries'] < self.MAX_QUERIES and
                    time.monotonic() - item['created_monotonic'] <= self.OBSERVATION_SECONDS,
                    'LIMIT_EXCEEDED', 'Owner observation budget exhausted; handles remain retained')
            item['queries'] += 1
            scope = item['scope']
            return {**item['binding'], 'observation_only': True,
                    'execution_uncertain': item['uncertain'], 'query_number': item['queries'],
                    'scope': scope.query() if scope is not None else None,
                    'process_exits': {role: ref.exit_evidence() for role, ref in item['refs'].items()},
                    'does_not_commit_completion': True}

    def close_owner(self):
        """Owner teardown, not a maintenance permission or proof of completion."""
        with self._lock:
            if self.active is None:
                return []
            errors = self._close(self.active)
            if not errors:
                self.active = None
            return errors
