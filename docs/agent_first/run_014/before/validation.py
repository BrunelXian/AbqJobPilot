"""Independent simulation validator; never reports a Solver verdict."""

import json

from .models import ExecutionError, bytes_digest, identifier, now
from .paths import result_path


def validate_artifact(context, plan, run, emission, *, captured=None):
    observation = {"observation_id": identifier("obs"), "run_id": run["run_id"],
                   "phase_attempt_id": run["phase_attempt_id"], "kind": "FAKE_JSON",
                   "exists": False, "path": None, "file_identity": None, "size": None, "mtime": None,
                   "digest": None, "provenance": "fake-v1", "binding_status": "UNKNOWN", "observed_at": now()}
    reasons = []
    verdict = "UNKNOWN"
    try:
        path = result_path(context, run["run_id"])
        observation["path"] = str(path)
        info = path.stat() if captured is None else captured[1]
        observation.update(exists=True, size=info.st_size, mtime=info.st_mtime_ns,
                           file_identity={"device": info.st_dev, "inode": info.st_ino})
        if captured is None:
            with path.open("rb") as stream:
                content = stream.read(plan["resources"]["max_output_bytes"] + 1)
        else:
            content = captured[0]  # Internal bounded bytes also used for the immutable snapshot.
        observation["digest"] = bytes_digest(content)
        data = json.loads(content)
        required = {"format", "simulation", "run_id", "phase_attempt_id", "plan_digest", "config_digest", "input_digests"}
        checks = {
            "schema": type(data) is dict and set(data) == required,
            "size": len(content) <= plan["resources"]["max_output_bytes"] and len(content) == emission["size"],
            "digest": observation["digest"] == emission["digest"],
            "path": str(path) == emission["path"],
        }
        if checks["schema"]:
            checks.update(format=data["format"] == "fake-result-v1", simulation=data["simulation"] is True,
                          run=data["run_id"] == run["run_id"], phase=data["phase_attempt_id"] == run["phase_attempt_id"],
                          plan=data["plan_digest"] == plan["plan_digest"],
                          config=data["config_digest"] == plan["config_snapshot"]["digest"],
                          inputs=data["input_digests"] == [item["digest"] for item in plan["input_manifest"]])
        reasons = [name for name, passed in checks.items() if not passed]
        verdict = "PASS" if not reasons else "FAIL"
        observation["binding_status"] = "MATCHED" if verdict == "PASS" else "MISMATCH"
    except (ValueError, UnicodeError) as exc:
        verdict, reasons = "FAIL", ["Invalid fixture JSON: " + str(exc)]
    except (OSError, ExecutionError) as exc:
        reasons = ["Artifact cannot be observed: " + str(exc)]
    validation = {"validation_id": identifier("val"), "run_id": run["run_id"],
                  "phase_attempt_id": run["phase_attempt_id"], "scope": "simulation",
                  "policy_id": "fake-result-v1", "policy_version": 1, "validator_id": "fake-json-validator",
                  "validator_version": 1, "verdict": verdict, "reasons": reasons,
                  "evidence_refs": [observation["observation_id"]], "recorded_at": now()}
    return observation, validation
