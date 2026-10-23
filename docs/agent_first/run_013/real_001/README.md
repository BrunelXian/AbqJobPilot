# Run013 real_001 — explicitly authorized service acceptance

Source of authorization: current human message titled `批准 Run 013 唯一实机验收`, binding experiment `run013_e52135d71d2c43d2a45301c586cbfb7e` and canonical body SHA-256 `3c59461d53e658eb9894d6936bd405f85a7f27b6ebc3deb5343c81d8411ceebe`.

The existing `standard_service.py authorize --approval-source` mechanism registers this source; this document introduces no permission protocol. Maximum one Standard analysis, CPU1/GPU0/2048MB, no additional Abaqus calls. Service observation 300 seconds ends waiting only. No stop-owner, termination, retry, reset or cleanup of execution evidence is authorized here.

Preflight: Develop@fb7912ec9e0107b18f65948b147c87579c87cded; no unresolved conflicts; version0.3.0.dev0. Registered LangChainEnv Python3.12.10, sqlite3.49.1, Tk8.6. Existing modifications retained (BASELINE_STATUS.txt). No separate applicable Run protocol file found beyond AGENTS and the per-Run delivery convention; this new directory preserves the candidate and earlier reports.

The candidate and actual 42 code/input materials plus 20 explicit Runtime references matched. Stored Plan equals the frozen Plan; counts before registration: plans1, grants/runs/receipts/consumption/events/observations/validations0, supervisor_started0. Only bootstrap exists in private; control/session/logs empty; engineering has only axial_bar.inp and empty scratch. No endpoint or output intent.

GUI measurement reuses `tests/run012_gui.py`: it constructs the existing `AbqJobPilotApp` with the same explicit connection and request key as `standard_service.py gui`; its existing observer records rendered widgets. It does not submit, authorize, open storage, start/stop owners or execute Backend code. The measurement driver only queries public APIs, reads retained OS identities, and normally closes its own GUI using identity-checked WM_CLOSE. No Solver command or alternate execution controller is introduced. The actual Run is submitted separately through the frozen public entry.

Only the candidate's existing `start` entry owns Supervisor creation, using regular stdout/stderr files and the explicit service/session host contract. No breakaway, service, scheduler or changed Job policy. Actual Backend admission still executes inside the owner before external creation. No claim is made for owner/Job/session closure survival.
