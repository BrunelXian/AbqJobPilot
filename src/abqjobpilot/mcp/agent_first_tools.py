"""Project-bound, connect-only adapter for the Agent-first MCP surface."""

from .. import __version__
from ..execution.models import CONTRACT, integer, require, text
from ..execution.protocol import DELEGATED_ENVIRONMENT, DELEGATED_GRANT_STATUS, EXTRACT_ODB, SUBMIT_DELEGATED
from ..service_discovery import discover, project_identity

CONTRACT_VERSION = "abq-agent-first-mcp-v1"
SUBMIT_FIELDS = ("project_id", "project_instance_id", "job_id", "job_revision", "plan_id", "plan_digest",
                 "grant_id", "idempotency_key")
RUN_FIELDS = ("run_id", "project_id", "project_instance_id", "job_id", "job_revision", "plan_id", "plan_digest",
              "grant_id", "attempt_no", "phase_attempt_id", "queue_state", "execution", "phase", "execution_phase",
              "backend_id", "backend_outcome", "simulation", "admission_only", "solver_conclusion",
              "artifact_validation", "reconciliation_requirement", "revision", "input_binding")


class AgentFirstTools:
    def __init__(self, project_path, connection_file=None):
        self.context = project_identity(project_path)
        self._connection_file = connection_file

    @property
    def project(self):
        return {"project_id": self.context.project_id, "project_instance_id": self.context.project_instance_id}

    def _connect(self):
        client, context, health = discover(self.context.root, self._connection_file)
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "The bound Project instance changed")
        return client, health

    def check_environment(self):
        client, health = self._connect()
        operations = health["operations"]
        delegated = (client.delegated_environment() if DELEGATED_ENVIRONMENT in operations else
                     {"delegation_enabled": False, "gate_state": None, "accepting_new": False})
        return {"product_version": __version__, "supervisor": {
                    "status": "CONNECTED", "owner_id": client.endpoint["owner_id"],
                    "gate_state": delegated["gate_state"], "execution_scope": health["execution_scope"],
                }, "capabilities": {
                    "abq_check_environment": "AVAILABLE",
                    "abq_get_grant_status": "AVAILABLE" if delegated["delegation_enabled"]
                    and DELEGATED_GRANT_STATUS in operations else "UNAVAILABLE",
                    "abq_submit_job": "TEST_ONLY_DELEGATED_ADMISSION" if delegated["delegation_enabled"]
                    and SUBMIT_DELEGATED in operations else "UNAVAILABLE",
                    "abq_get_run_status": "AVAILABLE" if "run" in operations else "UNAVAILABLE",
                    "abq_get_receipt": "AVAILABLE" if "receipt" in operations else "UNAVAILABLE",
                    "abq_extract_odb": "UNAVAILABLE",
                    "odb_fixture_extraction": "TEST_ONLY" if delegated.get("odb_fixture_enabled")
                    and EXTRACT_ODB in operations else "UNAVAILABLE",
                }, "accepting_new_delegated_requests": delegated["accepting_new"] and SUBMIT_DELEGATED in operations}

    def grant_status(self, grant_id):
        text(grant_id)
        client, health = self._connect()
        require(DELEGATED_GRANT_STATUS in health["operations"], "CAPABILITY_UNAVAILABLE", "Owner lacks delegated status")
        return {"grant": client.delegated_grant_status(grant_id)}

    def submit_job(self, **arguments):
        require(type(arguments["grant_id"]) is str and bool(arguments["grant_id"]),
                "GRANT_REQUIRED", "A registered delegated Grant ID is required")
        for key in SUBMIT_FIELDS:
            if key != "job_revision":
                text(arguments[key])
        integer(arguments["job_revision"], 1)
        require(all(arguments[key] == value for key, value in self.project.items()),
                "PROJECT_IDENTITY_MISMATCH", "Submission differs from the bound Project instance")
        client, health = self._connect()
        require(SUBMIT_DELEGATED in health["operations"], "CAPABILITY_UNAVAILABLE", "Owner lacks delegated submission")
        request = {**arguments, "contract_version": CONTRACT, "operation": "submit", "retry_of": None}
        return client.submit_delegated(request)

    def run_status(self, run_id):
        text(run_id)
        client, health = self._connect()
        run = client.run(run_id)
        backend = run["backend_id"]
        if backend in {"python-process-fixture-v1", "abaqus-standard-axial-2024-v1"} and "progress" in health["operations"]:
            progress = client.progress(run_id)
        else:
            progress = {"status": "NOT_APPLICABLE" if backend == "fake-v1" else "UNAVAILABLE", "records": []}
        return {"run": {key: run[key] for key in RUN_FIELDS if key in run}, "progress": progress}

    def receipt(self, idempotency_key):
        text(idempotency_key)
        client, _ = self._connect()
        return {"receipt": client.receipt(idempotency_key)}

    def extract_odb(self, run_id, extraction=None):
        text(run_id)
        require(extraction is not None, "CAPABILITY_UNAVAILABLE", "Native ODB extraction remains unavailable")
        client, health = self._connect()
        require(EXTRACT_ODB in health["operations"], "CAPABILITY_UNAVAILABLE", "Owner lacks the extraction contract")
        return client.extract_odb(run_id, extraction)
