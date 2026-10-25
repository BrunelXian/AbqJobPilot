"""Independent fixed-process artifact validation; process exit is not inferred here."""

import json

from .models import ExecutionError, bytes_digest, canonical_json, identifier, now
from .process_contract import BACKEND, directory, expected_result


def validate_process_artifact(context, plan, run):
    observation = {"observation_id": identifier("obs"), "run_id": run["run_id"], "phase_attempt_id": run["phase_attempt_id"],
                   "kind": "PROCESS_FIXTURE_JSON", "provenance": BACKEND, "observed_at": now(),
                   "exists": False, "binding_status": "UNKNOWN"}
    verdict, reasons = "UNKNOWN", ["ARTIFACT_UNAVAILABLE"]
    try:
        path = directory(context, run) / "result.json"
        from .paths import confined
        path = confined(context.test_root, path, exists=True)
        info = path.stat()
        with path.open("rb") as stream:
            content = stream.read(65537)
        observation.update(exists=True, size=len(content), digest=bytes_digest(content), mtime=info.st_mtime_ns,
                           file_identity={"device": info.st_dev, "inode": info.st_ino})
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate fixture key")
                result[key] = value
            return result
        valid = (len(content) <= 65536 and info.st_nlink == 1
                 and canonical_json(json.loads(content, object_pairs_hook=unique_object)) == canonical_json(expected_result(context, plan, run)))
        verdict, reasons = ("PASS", []) if valid else ("FAIL", ["FIXED_CONTENT_MISMATCH"])
        observation["binding_status"] = "MATCHED" if valid else "MISMATCH"
    except (ValueError, UnicodeError):
        verdict, reasons = "FAIL", ["INVALID_JSON"]
    except (OSError, ExecutionError):
        pass
    return observation, {"validation_id": identifier("val"), "run_id": run["run_id"], "phase_attempt_id": run["phase_attempt_id"],
                         "scope": "simulation", "policy_id": "process-fixture-result-v1", "policy_version": 1,
                         "validator_id": "process-fixture-validator", "validator_version": 1,
                         "verdict": verdict, "reasons": reasons, "evidence_refs": [observation["observation_id"]], "recorded_at": now()}
