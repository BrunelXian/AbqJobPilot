# Research preview evidence · 0.5.3 DEV

## The reproducible result

INT-002A.1 passed the engineering checkout's **250 targeted offline tests**, with zero failures, errors or skips in the final run. The public checkout carries the delegated execution change and a selected test set. A publication check ran 42 tests from the bridge, delegated Grant, budget and historical MCP modules against this public tree. The [Windows stdio demo](../README.md#try-one-test_only-job-over-real-mcp-stdio) runs one of those tests with a new Project each time.

| Observation in the demo | Evidence |
| --- | --- |
| The request reached the original Owner | A real stdio client read the Owner's TEST_ONLY capability and the exact Grant before submission. The client observed dispatch and read the original Receipt again after reconnecting. |
| One accepted request produced one result | The persisted event order was `REQUEST_ACCEPTED`, `START_INTENT`, `FAKE_COMPLETED`, `VALIDATION_RECORDED`. The terminal Run and JSON shared the Run ID, Attempt ID and Plan digest. The validator checked the file size and SHA-256 against the emitted artifact. |
| Budget and replay agreed | The Grant ended at one consumed, zero remaining. Identical replay returned the original Receipt. Changing the revision under the same key returned `IDEMPOTENCY_CONFLICT`. A fresh key returned `GRANT_BUDGET_EXHAUSTED`. |
| Execution stayed in scope | Both the Plan and the operator's TEST_ONLY Grant explicitly selected `execute_fake_result_v1`. The registered `fake-v1` backend wrote bounded JSON. Earlier admission-only Plans retain their original permissions. The result has `simulation=true` and `solver_conclusion=NOT_RUN`. |

A separate clean Windows CPython 3.12 virtual environment installed MCP SDK 2.3.0 and pytest 9.2.0. The README's named stdio test returned one pass there.

The suite also checks the failure path. Killing the isolated Owner after claim leaves the original Run requiring reconciliation, its one accepted budget unit consumed, and no successful result. Substituting another Run's artifact fails validation. The [bridge test source](../tests/test_delegated_fake_execution.py) contains the checks. All IDs and output digests in a local proof come from that invocation.

## Historical real-solver evidence

[INT-001](https://github.com/BrunelXian/Goal-Driven-CAE-Orchestrator/blob/codex/vericae-0.5.5-public/docs/vericae/demo/README.md) read existing Abaqus records through the historical MCP interface. The scientific cross-check succeeded and the overall decision was **PARTIAL**. The solver completed, while unexplained auxiliary process exits kept Execution Qualification at **REVIEW_REQUIRED**. The recorded ODB source was trusted. Abaqus Python produced a diagnostic JSON value, but the original extraction Receipt remains **FAILED**, Extraction Qualification **REVIEW_REQUIRED** and Result Data Integrity **INSUFFICIENT**. The historical output lacks the Owner-bound output digest needed for full integrity verification.

INT-002B is a separate new-task integration. Research planning passed. Execution is **BLOCKED / STOPPED** with zero new submissions reported. After loss of the original Owner, a current Grant balance could not be confirmed. The public demo uses its own disposable Owner, Project, Grant and test request.

## Acceptance still required

- **INSTALL-02** must bind the chosen Abaqus environment and required launcher materials into a general new Plan and recheck those frozen identities before dispatch.
- A future VeriCAE new-task test requires a valid independent operator handoff. Results and independent validation must use the same Run, Attempt and Receipt.
- Scientific interpretation requires suitable model assumptions and solver evidence. The TEST_ONLY JSON exercises identity, state and accounting.

The [GUI image](images/native-tk-preview.png) is a capture of the DEV Native Tk window's client area. The capture used an empty local profile, English labels and Light mode, before system-resource sampling. No Project, service session or research data was attached.
