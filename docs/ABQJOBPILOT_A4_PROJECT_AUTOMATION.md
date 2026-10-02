# Project Automation Surface (application 0.2.1)

AbqJobPilot remains a local Abaqus job lifecycle runner with a thin, GUI-free automation surface. Application version is `0.2.1`; automation/JSON schema remains `1.0`, and SQLite schema remains `1`.

## Selection and ownership

Use `--project "D:\path\Project"`, `--project-id <uuid>`, or `--project-name "Exact name"`. Resolution priority is explicit path, then registered ID, then a unique exact registered name. Name collisions return `AMBIGUOUS_PROJECT` with matching IDs and paths. ID/name lookup uses the application's recent-project registry, not a drive scan. A path may target an unregistered formal Project. No selector on legacy queue commands preserves the default runtime; it does not select the most recent Project. Do not combine a Project selector with `--runtime-dir`.

Project registration lives in the canonical per-user recent-project file. A Project's `project.json`, `project.db`, and `runtime/` remain under its own root. External CAE/INP/ODB/STA/MSG/DAT/LOG files remain in the engineering workspace. CLI/API users must not edit Project/runtime persistence files directly; use AbqJobPilot operations. No public command starts the solver.

## CLI

Add `--json` for JSON-only stdout and a nonzero exit on error. In JSON mode even argument errors are structured. Without `--json`, output is concise human-readable text.

```powershell
python -m abqjobpilot.api.cli project list --json
python -m abqjobpilot.api.cli project create --name "Example Study" --json
python -m abqjobpilot.api.cli project create --name "Example Study" --path "D:\Custom\Example" --json
python -m abqjobpilot.api.cli project show --project-id "<uuid>" --json
python -m abqjobpilot.api.cli project update --project-id "<uuid>" --description "Boundary study" --json
python -m abqjobpilot.api.cli project register --project "D:\Custom\Example" --json
python -m abqjobpilot.api.cli project unregister --project-id "<uuid>" --json
python -m abqjobpilot.api.cli project export --project-id "<uuid>" --mode metadata --output "D:\Backup\Example.zip" --json
python -m abqjobpilot.api.cli project import --archive "D:\Backup\Example.zip" --destination "D:\Restored\Example" --json
python -m abqjobpilot.api.cli job list --project-id "<uuid>" --status FAILED --batch batch01 --limit 50 --json
python -m abqjobpilot.api.cli job show --project-id "<uuid>" --job-id "j_..." --json
python -m abqjobpilot.api.cli enqueue --project-id "<uuid>" --inp "D:\CAE\Example\model.inp" --json
```

`project create` without `--path` uses `<application-root>/projects/<safe display name>` and registers the new Project. Windows-invalid folder components are rejected. `project update` can change only name and description; a name change does not move/rename the directory. `project unregister` removes only the registry entry and returns `PROJECT_NOT_REGISTERED` when already absent. It never deletes the Project or engineering files. `project export` defaults to metadata; `--mode project-owned` maps to the existing full Project-owned archive and does not gather external references. Import uses the existing validated ZIP importer and registers the restored Project. Without a destination, it uses the archive Project name under the default projects root.

`job list` and `job show` read logical Jobs, Runs, and artifact references from an existing `project.db`; they never initialize a missing database or reconcile runtime data. A Project without a database returns an empty Job list. `project show` returns null history counts when no database exists. The active queue remains `runtime/queue.json`; `job list` is not a replacement for the queue `list` command. Filters are exact `--status`, `--batch`, `--strategy`, and positive `--limit`. Job status is canonical; raw Run status remains available in `job show`.

## Python API

```python
from abqjobpilot.api import AbqJobPilotClient, JobRequest

client = AbqJobPilotClient()
projects = client.list_projects().to_dict()
project = client.show_project(project_id="<uuid>").to_dict()
jobs = client.list_project_jobs(project_id="<uuid>").to_dict()
scoped = client.for_project(project_id="<uuid>")
preview = scoped.enqueue(JobRequest(inp_path=r"D:\CAE\Example\model.inp"))
```

`for_project` returns a client bound to that Project's runtime without changing GUI/global runtime. `enqueue` still defaults to dry-run; `dry_run=False` only writes queue metadata. The desktop **Start Queue** action remains the execution trigger. A running GUI is not remotely switched by `project register`.

## Results and errors

New Project/Job result objects support `to_dict()` and `to_json()`. They include `schema_version`, `status`, `errors`, `warnings`, and `error_details` with stable `code`/`message`. Relevant codes include `PROJECT_NOT_FOUND`, `PROJECT_ALREADY_EXISTS`, `AMBIGUOUS_PROJECT`, `PROJECT_INVALID`, `PROJECT_NOT_REGISTERED`, `INVALID_PROJECT_SELECTOR`, `JOB_NOT_FOUND`, and existing database error codes. `capabilities --json` advertises only implemented operations, with `solver_start=false` and `project_delete=false`.

## Safety limits

No direct Project deletion, Job creation, solver start, MCP, HTTP service, or LLM runtime is exposed. Query commands do not create/migrate `project.db`, alter queue order, read whole solver logs, or open ODB files. Archives retain P1/P2 path-traversal and overwrite protections. AbqJobPilot remains the authority for Project metadata; external tools should not write its JSON/SQLite files themselves.
