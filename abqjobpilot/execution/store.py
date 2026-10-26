"""Isolated experiment storage. Creation, mutation and read-only open are distinct."""

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
import threading
import time

from .models import (FORMAT, ProjectContext, ExecutionError, canonical_json, digest,
                     identifier, now, require)
from .paths import confined, local_path, no_reparse
from .ownership import LocalOwnerLock

_SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE configuration(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
CREATE TABLE jobs(job_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                  PRIMARY KEY(job_id,revision));
CREATE TABLE plans(plan_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                   FOREIGN KEY(job_id,revision) REFERENCES jobs(job_id,revision));
CREATE TABLE grants(grant_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plans, body TEXT NOT NULL);
CREATE TABLE runs(run_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, revision INTEGER NOT NULL,
                  plan_id TEXT NOT NULL REFERENCES plans, grant_id TEXT NOT NULL REFERENCES grants,
                  attempt_no INTEGER NOT NULL, retry_of TEXT REFERENCES runs, body TEXT NOT NULL,
                  UNIQUE(job_id,attempt_no), FOREIGN KEY(job_id,revision) REFERENCES jobs(job_id,revision));
CREATE TABLE receipts(namespace TEXT NOT NULL, key TEXT NOT NULL, request_digest TEXT NOT NULL,
                      run_id TEXT NOT NULL UNIQUE REFERENCES runs, body TEXT NOT NULL, PRIMARY KEY(namespace,key));
CREATE TABLE consumption(grant_id TEXT PRIMARY KEY REFERENCES grants, run_id TEXT NOT NULL UNIQUE REFERENCES runs);
CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL REFERENCES runs, run_sequence INTEGER NOT NULL, body TEXT NOT NULL,
                    UNIQUE(run_id,run_sequence));
CREATE TABLE slot(id INTEGER PRIMARY KEY CHECK(id=1), run_id TEXT UNIQUE REFERENCES runs);
INSERT INTO slot VALUES(1,NULL);
CREATE TABLE observations(observation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs, body TEXT NOT NULL);
CREATE TABLE validations(validation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs, body TEXT NOT NULL);
CREATE TABLE dispatch_gate(id INTEGER PRIMARY KEY CHECK(id=1), owner_id TEXT NOT NULL,
                           version INTEGER NOT NULL, state TEXT NOT NULL CHECK(state IN ('OPEN','PAUSED')));
CREATE TABLE management_grants(grant_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE management_receipts(namespace TEXT NOT NULL, key TEXT NOT NULL, request_digest TEXT NOT NULL,
                                 operation_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL, PRIMARY KEY(namespace,key));
CREATE TABLE management_consumption(grant_id TEXT PRIMARY KEY REFERENCES management_grants,
                                    operation_id TEXT UNIQUE NOT NULL REFERENCES management_receipts(operation_id));
CREATE TABLE reconciliations(reconciliation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs, body TEXT NOT NULL);
CREATE TABLE control_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL);
"""


@dataclass
class _Session:
    owner_id: str = field(default_factory=lambda: identifier("owner"))
    authority_instance: str = field(default_factory=lambda: identifier("fixture_authority"))
    lock: threading.RLock = field(default_factory=threading.RLock)
    closed: bool = False
    lease: object = None
    active_dispatches: int = 0
    dispatch_enabled: bool = True
    stopping: bool = False


_SESSIONS = {}
_REGISTRY_LOCK = threading.Lock()


def _session(context):
    with _REGISTRY_LOCK:
        return _SESSIONS.get(context.execution_store)


def validate_context(context, *, bounded=False):
    require(type(context) is ProjectContext, "INVALID_REQUEST", "Explicit ProjectContext required")
    root = confined(context.test_root, context.root, exists=True)
    require(root != Path(context.test_root), "PROJECT_IDENTITY_MISMATCH", "Project must be below test root")
    require(context.runtime_root == str(root / "runtime")
            and context.execution_store == str(root / "execution.sqlite3"),
            "PROJECT_IDENTITY_MISMATCH", "Context paths do not match Project")
    manifest = confined(context.test_root, root / "experiment.json", exists=True)
    try:
        if bounded:
            from .diagnostics import bounded_tree, MAX_RECORD_BYTES
            with manifest.open("rb") as stream:
                content = stream.read(MAX_RECORD_BYTES + 1)
            require(len(content) <= MAX_RECORD_BYTES, "LIMIT_EXCEEDED", "Diagnostic manifest exceeds bound")
            body = json.loads(content)
            bounded_tree(body)
        else:
            body = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutionError("UNSUPPORTED_FORMAT", "Invalid experiment manifest") from exc
    require(type(body) is dict and body.get("format_id") == FORMAT and type(body.get("schema_version")) is int
            and body["schema_version"] in (1, 2, 3) and context.format_id == FORMAT
            and context.schema_version == body["schema_version"],
            "UNSUPPORTED_FORMAT", "Not the supported experimental format")
    identity = root.stat()
    require(digest(body) == context.manifest_digest
            and body["project_id"] == context.project_id
            and body["project_instance_id"] == context.project_instance_id
            and body["storage_generation"] == context.storage_generation
            and body["root"] == context.root and body["test_root"] == context.test_root
            and (identity.st_dev, identity.st_ino) == (context.root_device, context.root_inode),
            "PROJECT_IDENTITY_MISMATCH", "Project was changed, moved or copied")
    confined(context.test_root, context.runtime_root, exists=True)
    return confined(context.test_root, context.execution_store, exists=True)


def _check_sidecars(path):
    for suffix in ("-wal", "-shm", "-journal"):
        try:
            path.with_name(path.name + suffix).lstat()
        except FileNotFoundError:
            continue
        # Do not follow a sidecar link, even to find out whether its target exists.
        raise ExecutionError("STORE_REQUIRES_MAINTENANCE", "SQLite sidecar present; no implicit recovery")


def _connection(context, *, read_only, timeout=5, deadline=None):
    path = validate_context(context, bounded=deadline is not None)
    _check_sidecars(path)
    connection = sqlite3.connect(path.as_uri() + ("?mode=ro" if read_only else "?mode=rw"), uri=True, timeout=timeout)
    try:
        if deadline is not None:
            connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        if read_only:
            connection.execute("PRAGMA query_only=ON")
        require(connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete",
                "STORE_REQUIRES_MAINTENANCE", "Only DELETE journal mode is supported")
        if deadline is not None:
            metadata_rows = connection.execute("SELECT CASE WHEN length(key)<=256 THEN key END, "
                                               "CASE WHEN length(value)<=1024 THEN value END FROM meta LIMIT 17").fetchall()
            require(len(metadata_rows) <= 16 and all(r[0] is not None and r[1] is not None for r in metadata_rows),
                    "LIMIT_EXCEEDED", "Diagnostic metadata exceeds bound")
            metadata = dict(metadata_rows)
        else:
            metadata = dict(connection.execute("SELECT key,value FROM meta"))
        require(metadata.get("format") == FORMAT and metadata.get("schema") == str(context.schema_version),
                "UNSUPPORTED_FORMAT", "Unsupported experiment schema")
        require(metadata.get("context_digest") == context.context_digest,
                "PROJECT_IDENTITY_MISMATCH", "Store identity differs from context")
        if not read_only:
            connection.execute("PRAGMA synchronous=FULL")
        return connection
    except BaseException:
        connection.close()
        raise


def create_experiment(explicit_test_root, new_project_root):
    """Only this function creates files; no adoption of an existing Project."""
    test_root = local_path(explicit_test_root)
    no_reparse(test_root)
    require(test_root.is_dir(), "NOT_FOUND", "Caller must create an explicit temporary test root")
    test_root = test_root.resolve()
    root = confined(test_root, new_project_root)
    require(root != test_root and not root.exists(), "PROJECT_EXISTS", "Experiment requires a new child directory")
    require(root.parent.is_dir(), "NOT_FOUND", "Project parent must exist")
    root.mkdir(exist_ok=False)
    (root / "runtime").mkdir()
    identity = root.stat()
    manifest = {"format_id": FORMAT, "schema_version": 3, "project_id": identifier("p"),
                "project_instance_id": identifier("pi"), "storage_generation": identifier("generation"),
                "root": str(root), "test_root": str(test_root)}
    (root / "experiment.json").write_text(canonical_json(manifest), encoding="utf-8")
    context = ProjectContext(manifest["project_id"], manifest["project_instance_id"], str(test_root), str(root),
                             str(root / "runtime"), str(root / "execution.sqlite3"), FORMAT, 3,
                             manifest["storage_generation"], digest(manifest), identity.st_dev, identity.st_ino)
    (root / "owner.lock").write_bytes(b"0")
    session = _Session(lease=LocalOwnerLock(context))
    connection = None
    try:
        Path(context.execution_store).touch(exist_ok=False)
        connection = sqlite3.connect(context.execution_store)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(_SCHEMA)
        connection.execute("INSERT INTO dispatch_gate VALUES(1,?,1,'OPEN')", (session.owner_id,))
        connection.executemany("INSERT INTO meta VALUES(?,?)", [("format", FORMAT), ("schema", "3"),
                               ("context_digest", context.context_digest), ("owner_id", session.owner_id),
                               ("authority_instance", session.authority_instance), ("supervisor_started", "0")])
        connection.commit()
    except BaseException:
        session.lease.close()
        raise
    finally:
        if connection is not None:
            connection.close()
    with _REGISTRY_LOCK:
        _SESSIONS[context.execution_store] = session
    return context


def document(connection, table, key, value):
    # Identifiers are internal constants, never request strings.
    require((table, key) in {("plans", "plan_id"), ("grants", "grant_id"), ("runs", "run_id")},
            "INVALID_REQUEST", "Unsupported internal lookup")
    row = connection.execute(f"SELECT body FROM {table} WHERE {key}=?", (value,)).fetchone()
    require(row is not None, "NOT_FOUND", f"{table} record not found")
    return json.loads(row[0])


def append_event(connection, run_id, kind, payload=None, evidence_refs=()):
    sequence = connection.execute("SELECT COALESCE(MAX(run_sequence),0)+1 FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
    body = {"event_id": identifier("ev"), "run_id": run_id, "run_sequence": sequence, "type": kind,
            "observed_at": now(), "recorded_at": now(), "payload": payload or {}, "evidence_refs": list(evidence_refs)}
    cursor = connection.execute("INSERT INTO events(event_id,run_id,run_sequence,body) VALUES(?,?,?,?)",
                                (body["event_id"], run_id, sequence, canonical_json(body)))
    # project_sequence is supplied by the immutable SQL row, not a separate update.
    return {**body, "project_sequence": cursor.lastrowid}


def update_run(connection, run, kind, *, evidence_refs=(), **changes):
    updated = {**run, **changes, "revision": run["revision"] + 1}
    cursor = connection.execute("UPDATE runs SET body=? WHERE run_id=? AND body=?",
                                (canonical_json(updated), run["run_id"], canonical_json(run)))
    require(cursor.rowcount == 1, "STATE_CONFLICT", "Run changed concurrently")
    append_event(connection, run["run_id"], kind, {"revision": updated["revision"], **changes}, evidence_refs)
    return updated


class ReadOnlyStore:
    def __init__(self, context):
        self.context = context
        with self.read():
            pass

    @contextmanager
    def read(self):
        session = _session(self.context)
        lock = session.lock if session else threading.RLock()
        with lock:
            connection = None
            try:
                connection = _connection(self.context, read_only=True)
                yield connection
            except (sqlite3.Error, OSError) as exc:
                raise ExecutionError("STORE_UNAVAILABLE", f"Read failed: {exc}", stage="QUERY") from exc
            finally:
                if connection is not None:
                    connection.close()

    def query_receipt(self, context, client_namespace, key):
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Wrong query context")
        namespace = canonical_json([context.project_instance_id, client_namespace, "submit"])
        with self.read() as connection:
            row = connection.execute("SELECT body FROM receipts WHERE namespace=? AND key=?", (namespace, key)).fetchone()
            require(row is not None, "NOT_FOUND", "No committed receipt")
            return json.loads(row[0])

    def project_view(self, context, client_namespace, before_row=0, limit=32):
        """Bounded keyset page and gate/slot from one short read-only transaction."""
        from .models import integer
        from .diagnostics import bounded_tree, read_error
        require(context == self.context, 'PROJECT_IDENTITY_MISMATCH', 'Wrong query context')
        require(context.schema_version == 3, 'UNSUPPORTED_FORMAT', 'Project view requires format 3')
        integer(before_row); integer(limit, 1)
        require(before_row < 2**63 and limit <= 32, 'LIMIT_EXCEEDED', 'Project page bound exceeded')
        namespace = canonical_json([context.project_instance_id, client_namespace, 'submit'])
        connection = None
        deadline = time.monotonic() + .75
        try:
            connection = _connection(context, read_only=True, timeout=.2, deadline=deadline)
            connection.execute('BEGIN')
            rows = connection.execute(
                'SELECT r.rowid, CASE WHEN length(CAST(r.body AS BLOB))<=65536 THEN r.body END AS run, '
                'CASE WHEN length(CAST(q.body AS BLOB))<=4096 THEN q.body END AS receipt, '
                'CASE WHEN length(CAST(p.body AS BLOB))<=65536 THEN p.body END AS plan '
                'FROM runs r JOIN receipts q ON q.run_id=r.run_id JOIN plans p ON p.plan_id=r.plan_id '
                'WHERE q.namespace=? AND (?=0 OR r.rowid<?) ORDER BY r.rowid DESC LIMIT ?',
                (namespace, before_row, before_row, limit + 1)).fetchall()
            self._diagnostic_checkpoint('project_view:after_runs')
            gate = gate_view(connection)
            slot = connection.execute('SELECT run_id FROM slot WHERE id=1').fetchone()
            require(slot is not None, 'STORE_UNAVAILABLE', 'Execution slot record missing')
            require(all(row[k] is not None for row in rows for k in ('run','receipt','plan')),
                    'LIMIT_EXCEEDED', 'Project record exceeds bound')
            require(sum(len(row[k].encode('utf-8')) for row in rows for k in ('run','receipt','plan')) <= 262144,
                    'LIMIT_EXCEEDED', 'Project page bytes exceed bound')
            require(time.monotonic() < deadline, 'STORE_UNAVAILABLE', 'Project read deadline exceeded')
            slot_run_id = slot[0]
            read_at = now()
        except (ExecutionError, sqlite3.Error, OSError, ValueError, TypeError, RecursionError) as exc:
            raise read_error(exc) from None
        finally:
            if connection is not None: connection.close()
        self._diagnostic_checkpoint('project_view:after_close')
        try:
            items=[]
            for row in rows[:limit]:
                run, receipt, plan = (json.loads(row[k]) for k in ('run','receipt','plan'))
                require(all(type(v) is dict for v in (run,receipt,plan)), 'STORE_UNAVAILABLE', 'Invalid Project record')
                item={k:run.get(k) for k in ('run_id','job_id','plan_id','backend_id','revision',
                      'created_at','queue_state','execution','execution_phase','solver_conclusion',
                      'artifact_validation','reconciliation')}
                item['job_name']=plan.get('job_name')  # Fake has a logical job_id, no invented name.
                item['receipt']={k:receipt.get(k) for k in ('request_id','idempotency_key','accepted_at','run_id')}
                require(all(v is None or type(v) in (str,int) for k,v in item.items() if k!='receipt')
                        and all(type(v) in (str,int) for v in item['receipt'].values()),
                        'STORE_UNAVAILABLE', 'Invalid Project public field')
                items.append(item)
            result={'view_version':'af-project-view-v1','project_id':context.project_id,
                    'project_instance_id':context.project_instance_id,'context_digest':context.context_digest,
                    'gate':gate,'slot_run_id':slot_run_id,'read_at':read_at,'runs':items,
                    'next_before_row':rows[limit-1][0] if len(rows)>limit else None,
                    'consistency':'single_read_transaction; pages are successive snapshots'}
            bounded_tree(result)
            require(len(canonical_json(result).encode('utf-8')) <= 131072, 'LIMIT_EXCEEDED', 'Project response exceeds bound')
            return result
        except (ExecutionError, ValueError, TypeError, RecursionError) as exc:
            raise read_error(exc) from None

    def query_run(self, context, run_id):
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Wrong query context")
        with self.read() as connection:
            run = document(connection, "runs", "run_id", run_id)
        return {**run, "reconciliation_requirement": "RECONCILIATION_REQUIRED"
                if run["execution"] in {"START_INTENT", "VALIDATING"} or run["reconciliation"] != "NONE" else "NONE",
                "reconciliation_basis": "Unfinished dispatch or recorded uncertainty; query performs no repair"}

    def events(self, context, after_sequence=0, limit=100):
        from .models import integer
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Wrong query context")
        integer(after_sequence)
        integer(limit, 1)
        require(limit <= 1000, "INVALID_REQUEST", "Event page limit exceeds 1000")
        with self.read() as connection:
            rows = connection.execute("SELECT sequence,body FROM events WHERE sequence>? ORDER BY sequence LIMIT ?",
                                      (after_sequence, limit)).fetchall()
        return [{**json.loads(row["body"]), "project_sequence": row["sequence"]} for row in rows]

    def _run_records(self, context, run_id, table):
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Wrong query context")
        with self.read() as connection:
            document(connection, "runs", "run_id", run_id)
            return [json.loads(row[0]) for row in connection.execute(f"SELECT body FROM {table} WHERE run_id=? ORDER BY rowid", (run_id,))]

    def validations(self, context, run_id):
        return self._run_records(context, run_id, "validations")

    def observations(self, context, run_id):
        return self._run_records(context, run_id, "observations")

    def gate(self):
        require(self.context.schema_version == 3, "UNSUPPORTED_FORMAT", "Management requires format 3")
        with self.read() as connection:
            return gate_view(connection)

    def management_receipt(self, namespace, action, key):
        require(self.context.schema_version == 3, "UNSUPPORTED_FORMAT", "Management requires format 3")
        with self.read() as connection:
            row = connection.execute("SELECT body FROM management_receipts WHERE namespace=? AND key=?",
                                     (canonical_json([self.context.project_instance_id, namespace, action]), key)).fetchone()
            require(row is not None, "NOT_FOUND", "No committed management receipt")
            return json.loads(row[0])

    def reconciliations(self, context, run_id):
        require(context.schema_version == 3, "UNSUPPORTED_FORMAT", "Management requires format 3")
        return self._run_records(context, run_id, "reconciliations")

    def _diagnostic_checkpoint(self, name):
        """Read-only test barrier; never supplied through a request."""

    def diagnose(self, context, run_id):
        from .diagnostics import build_report
        return build_report(context, self._diagnostic_snapshot(context, run_id))

    def inspect_interrupted_execution(self, context, run_id, *, observe_os=False):
        """Read-only classification; optional bounded current observations, never recovery."""
        from .interruption import inspect_store
        return inspect_store(self, context, run_id, observe_os=observe_os)

    def _diagnostic_snapshot(self, context, run_id, *, interruption=False):
        from .diagnostics import read_error, valid_id, MAX_RECORD_BYTES, MAX_RAW_BYTES
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Wrong diagnostic context")
        require(valid_id(run_id, "r"), "INVALID_REQUEST", "A generated Run ID is required")
        connection = None
        deadline = time.monotonic() + 0.75
        total = 0
        def rows(table, clause, parameters, limit, columns=""):
            # All SQL identifiers/clauses are internal constants. CASE prevents a
            # large persisted body from being materialized in Python at all.
            nonlocal total
            found = connection.execute(
                f"SELECT length(CAST(body AS BLOB)), CASE WHEN length(CAST(body AS BLOB))<=? THEN body ELSE NULL END"
                f"{columns} FROM {table} WHERE {clause} ORDER BY rowid LIMIT ?",
                (MAX_RECORD_BYTES, *parameters, limit + 1)).fetchall()
            require(len(found) <= limit, "LIMIT_EXCEEDED", "Diagnostic record count exceeds limit")
            for row in found:
                total += row[0]
                require(row[1] is not None and total <= MAX_RAW_BYTES, "LIMIT_EXCEEDED", "Diagnostic record bytes exceed limit")
            return [tuple(row[1:]) for row in found]
        try:
            # No execution lease or unbounded session mutex: SQLite supplies the
            # snapshot. Existing context/sidecar/query_only policy is retained.
            connection = _connection(context, read_only=True, timeout=0.2, deadline=deadline)
            connection.execute("BEGIN")
            run_rows = rows("runs", "run_id=?", (run_id,), 1, ",CASE WHEN length(plan_id)<=256 THEN plan_id END")
            require(bool(run_rows), "NOT_FOUND", "Run was not recorded")
            require(run_rows[0][1] is not None, "LIMIT_EXCEEDED", "Diagnostic Plan identity exceeds bound")
            self._diagnostic_checkpoint("diagnostic:after_run")
            gate = None
            if context.schema_version == 3:
                gate_row = connection.execute("SELECT CASE WHEN length(owner_id)<=256 THEN owner_id END AS owner_id, "
                                              "CASE WHEN typeof(version)='integer' THEN version END AS version, "
                                              "CASE WHEN length(state)<=32 THEN state END AS state FROM dispatch_gate WHERE id=1").fetchone()
                require(gate_row is not None, "STORE_UNAVAILABLE", "Diagnostic gate missing")
                require(all(v is not None for v in gate_row), "LIMIT_EXCEEDED", "Diagnostic gate exceeds bound")
                gate = dict(gate_row)
            raw = {"run": run_rows, "plan": rows("plans", "plan_id=?", (run_rows[0][1],), 1),
                   "receipts": rows("receipts", "run_id=?", (run_id,), 1),
                   "events": rows("events", "run_id=?", (run_id,), 64, ",sequence,run_sequence"),
                   "observations": rows("observations", "run_id=?", (run_id,), 16),
                   "validations": rows("validations", "run_id=?", (run_id,), 16),
                   "reconciliations": rows("reconciliations", "run_id=?", (run_id,), 8) if context.schema_version == 3 else [],
                   "gate": gate,
                   "event_upper_bound": connection.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0],
                   "read_at": now(), "requested_run_id": run_id}
            if interruption:
                require(context.schema_version == 3, 'UNSUPPORTED_FORMAT', 'Interruption diagnostics require format 3')
                slot = connection.execute('SELECT CASE WHEN run_id IS NULL OR length(run_id)<=64 THEN 1 ELSE 0 END, '
                    'CASE WHEN length(run_id)<=64 THEN run_id END FROM slot WHERE id=1').fetchone()
                owner = connection.execute("SELECT CASE WHEN length(value)<=64 THEN value END FROM meta WHERE key='owner_id'").fetchone()
                require(slot is not None and owner is not None, 'STORE_UNAVAILABLE', 'Control metadata missing')
                require(slot[0] == 1 and owner[0] is not None, 'LIMIT_EXCEEDED', 'Control metadata exceeds bound')
                require((slot[1] is None or valid_id(slot[1], 'r')) and valid_id(owner[0], 'owner'),
                        'STORE_UNAVAILABLE', 'Control identity invalid')
                raw['interruption'] = {'slot_run_id': slot[1], 'store_owner_id': owner[0],
                    'consumption': [tuple(r) for r in connection.execute(
                        'SELECT CASE WHEN length(grant_id)<=64 THEN grant_id END,run_id FROM consumption WHERE run_id=? LIMIT 2', (run_id,))],
                    'committed_operations': [r[0] for r in connection.execute(
                        'SELECT CASE WHEN length(m.operation_id)<=64 THEN m.operation_id END FROM management_receipts m '
                        'JOIN management_consumption g ON g.operation_id=m.operation_id '
                        'WHERE m.operation_id IN (SELECT json_extract(body,\'$.operation_id\') '
                        'FROM reconciliations WHERE run_id=?) LIMIT 9', (run_id,))]}
            require(time.monotonic() < deadline, "STORE_UNAVAILABLE", "Diagnostic read deadline exceeded")
        except (ExecutionError, sqlite3.Error, OSError, ValueError, TypeError, RecursionError) as exc:
            raise read_error(exc) from None
        finally:
            if connection is not None:
                connection.close()  # Ends the read transaction before projection or serialization.
        self._diagnostic_checkpoint("diagnostic:after_close")
        return raw


def gate_view(connection):
    return dict(connection.execute("SELECT owner_id,version,state FROM dispatch_gate WHERE id=1").fetchone())


def needs_reconciliation(run):
    return run["execution"] in {"START_INTENT", "VALIDATING"} or run["reconciliation"] != "NONE"


def open_existing_read_only(context):
    return ReadOnlyStore(context)


def acquire_supervisor_store(context, authority_instance, *, idle_only=False, lifecycle_admit=None, standard_binding=None, management_admit=None):
    """Explicit trusted owner handoff, never called by a client or a query.

    Only v3, original root identity, and exact pre-registered fixture authority.
    Every subsequent Supervisor start is paused, independently of older resumes.
    """
    validate_context(context)
    require(context.schema_version == 3, "UNSUPPORTED_FORMAT", "Writable ownership requires format 3; no migration")
    with _REGISTRY_LOCK:
        existing = _SESSIONS.get(context.execution_store)
        require(existing is None or existing.closed, "OWNER_BUSY", "Local owner session is still active")
        lease = LocalOwnerLock(context)
        connection = None
        try:
            connection = _connection(context, read_only=False)
            metadata = dict(connection.execute("SELECT key,value FROM meta"))
            require(metadata.get("authority_instance") == authority_instance,
                    "GRANT_SCOPE_MISMATCH", "Trusted bootstrap authority does not match fixture registration")
            if idle_only:
                from .lifecycle import require_idle
                require_idle(connection, standard_binding=standard_binding)
            if lifecycle_admit:lifecycle_admit(context)
            # Trusted management-only preflight, under the SAME owner lock and
            # before any owner/gate write. Do not re-enter the session registry.
            if management_admit:management_admit(context, connection)
            fresh = metadata.get("supervisor_started") == "0" and connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
            if idle_only:
                fresh = fresh and connection.execute("SELECT state FROM dispatch_gate WHERE id=1").fetchone()[0]=='OPEN'
            session = _Session(authority_instance=authority_instance, lease=lease, dispatch_enabled=fresh)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE meta SET value='1' WHERE key='supervisor_started'")
            connection.execute("UPDATE meta SET value=? WHERE key='owner_id'", (session.owner_id,))
            connection.execute("UPDATE dispatch_gate SET owner_id=?,version=version+1,state=? WHERE id=1",
                               (session.owner_id, "OPEN" if fresh else "PAUSED"))
            connection.commit()
            _SESSIONS[context.execution_store] = session
        except BaseException:
            lease.close()
            raise
        finally:
            if connection is not None:
                connection.close()
    return ExperimentStore(context)


def acquire_initial_preparation_store(context, authority_instance):
    """Trusted operator lease for initial provisioning ONLY, before any owner/Run.

    Does not start/reset dispatch or change supervisor_started. It cannot open
    an active or previously started store to circumvent the owner boundary.
    """
    validate_context(context)
    require(context.schema_version == 3, 'UNSUPPORTED_FORMAT', 'Initial provisioning requires format 3')
    with _REGISTRY_LOCK:
        existing = _SESSIONS.get(context.execution_store)
        require(existing is None or existing.closed, 'OWNER_BUSY', 'Local owner is active')
        lease = LocalOwnerLock(context)
        connection = None
        try:
            connection = _connection(context, read_only=True)
            metadata = dict(connection.execute('SELECT key,value FROM meta'))
            require(metadata.get('authority_instance') == authority_instance, 'GRANT_SCOPE_MISMATCH', 'Authority differs')
            require(metadata.get('supervisor_started') == '0' and connection.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 0,
                    'OWNER_UNCONFIRMED', 'Initial provisioning closed after owner start or acceptance')
            _SESSIONS[context.execution_store] = _Session(authority_instance=authority_instance, lease=lease)
        except BaseException:
            lease.close(); raise
        finally:
            if connection is not None: connection.close()
    return ExperimentStore(context)


class ExperimentStore(ReadOnlyStore):
    def __init__(self, context):
        self._session = _session(context)
        require(self._session is not None and not self._session.closed,
                "OWNER_UNCONFIRMED", "Only a live creating-process session may write; reopen is read-only")
        self._session.lease.check()
        super().__init__(context)

    def _checkpoint(self, name):
        """Internal fault-injection seam; no request can supply a callback."""

    @contextmanager
    def transaction(self, stage):
        with self._session.lock:
            require(not self._session.closed, "OWNER_UNCONFIRMED", "Experiment session is closed")
            require(not self._session.stopping or stage in {'lifecycle_stop','pause_on_error'},
                    'SERVICE_STOPPING', 'Owner has committed or uncertain lifecycle stop')
            self._session.lease.check()
            connection = None
            commit_attempted = False
            try:
                connection = _connection(self.context, read_only=False)
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                self._checkpoint(stage + ":before_commit")
                commit_attempted = True
                connection.commit()
            except (sqlite3.Error, OSError) as exc:
                if connection is not None:
                    connection.rollback()
                code = "ACCEPTANCE_UNKNOWN" if stage in {"accept", "management", "lifecycle_stop"} and commit_attempted else "STORE_UNAVAILABLE"
                raise ExecutionError(code, f"Transaction failed; query durable state before retry: {exc}", stage=stage) from exc
            except BaseException:
                if connection is not None:
                    connection.rollback()
                raise
            finally:
                if connection is not None:
                    connection.close()

    def close(self):
        """Close the shared experiment writer session, not just this facade."""
        with self._session.lock:
            require(self._session.active_dispatches == 0, "OWNER_BUSY", "Cannot release ownership during execution")
            self._session.closed = True
            self._session.lease.close()

    @contextmanager
    def dispatch_scope(self, *, product_service=None, run_id=None):
        with self._session.lock:
            self._session.lease.check()
            if product_service is not None:
                require(not self._session.stopping and product_service.store is self and
                        product_service.product_control.pending(product_service) == run_id,
                        'DISPATCH_PAUSED', 'No exact current-owner product dispatch permission')
            else:
                require(self.dispatch_allowed(), "DISPATCH_PAUSED", "Owner dispatch gate is paused")
            self._session.active_dispatches += 1
        try:
            yield
        finally:
            with self._session.lock:
                self._session.active_dispatches -= 1

    def pending_for_owner(self):
        """Owner worker polls durable acceptance, independently of RPC delivery."""
        with self.read() as connection:
            if connection.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is not None:
                return None
            for row in connection.execute("SELECT body FROM runs ORDER BY rowid"):
                run = json.loads(row[0])
                if run["queue_state"] == "PENDING" and run["execution"] == "PLANNED":
                    return run["run_id"]
        return None

    def dispatch_allowed(self):
        if self._session.closed or self._session.stopping:
            return False
        gate = self.gate()
        return gate["state"] == "OPEN" and gate["owner_id"] == self._session.owner_id

    def pause_after_error(self):
        with self.transaction("pause_on_error") as connection:
            connection.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1 WHERE id=1 AND state='OPEN'")
