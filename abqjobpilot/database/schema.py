"""Version 1 history schema. No solver bytes are stored."""

SCHEMA_V1 = (
    "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        logical_key TEXT NOT NULL,
        job_name TEXT,
        inp_path TEXT,
        batch TEXT,
        strategy TEXT,
        created_at TEXT,
        updated_at TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(project_id, logical_key)
    )""",
    """CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES jobs(job_id),
        attempt_no INTEGER NOT NULL CHECK(attempt_no > 0),
        queue_id TEXT UNIQUE,
        status TEXT NOT NULL,
        raw_status TEXT,
        cpus INTEGER,
        gpus INTEGER,
        working_dir TEXT,
        expected_odb_path TEXT,
        created_at TEXT,
        started_at TEXT,
        completed_at TEXT,
        exit_reason TEXT,
        error_code TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(job_id, attempt_no)
    )""",
    """CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        kind TEXT NOT NULL,
        path TEXT NOT NULL,
        exists_flag INTEGER NOT NULL CHECK(exists_flag IN (0, 1)),
        size_bytes INTEGER,
        mtime_ns INTEGER,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(run_id, kind, path)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_runs_job_attempt ON runs(job_id, attempt_no DESC)",
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id)",
)
