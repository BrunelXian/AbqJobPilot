"""Owner-only exit semantics for the fixed Standard HIL backend."""

from collections import Counter
from dataclasses import dataclass
from pathlib import PureWindowsPath

POLICY = "standard-hil-exit-semantics-v1"
MAX_EVIDENCE_BYTES = 24 * 1024
CRITICAL_SUCCESS = "CRITICAL_SUCCESS"
CRITICAL_FAILURE = "CRITICAL_FAILURE"
AUXILIARY_EXPECTED_NONZERO = "AUXILIARY_EXPECTED_NONZERO"
AUXILIARY_UNEXPECTED_NONZERO = "AUXILIARY_UNEXPECTED_NONZERO"
UNKNOWN = "EXIT_SEMANTICS_UNKNOWN"
MEMBERSHIP_UNCERTAIN = "PROCESS_MEMBERSHIP_UNCERTAIN"


@dataclass(frozen=True)
class AuxiliaryExitWitness:
    """Reviewed operation and its handle-bound observation from a trusted producer.

    The producer verifies command/caller provenance and that the actual dependency
    was satisfied independently. A reported exit code or shared console text is
    insufficient. Current vendor HIL has no such producer and supplies no witnesses.
    """

    operation: str
    reviewed_argv: tuple[str, ...]
    observed_argv: tuple[str, ...]
    expected_exit: int
    expected_output_digest: str
    observed_output_digest: str
    caller: tuple[int, int, str]
    expected_independent_digest: str
    observed_independent_digest: str
    observed_command_line: str | None = None


def member_key(record):
    return (record["pid"], record["creation_time_100ns"], record["image_path"])


def _critical_role(record, images):
    image = PureWindowsPath(record["image_path"])
    if record["role"] == "wrapper":
        return "wrapper" if image == PureWindowsPath(images["wrapper"]) else None
    return next((role for role, path in images.items()
                 if role != "wrapper" and image == PureWindowsPath(path)), None)


def _auxiliary_semantics(record, witness, identities, provenance):
    parent = provenance.get("parent", {})
    if (not witness or not witness.operation or not witness.observed_argv
            or witness.observed_argv != witness.reviewed_argv
            or PureWindowsPath(witness.observed_argv[0]) != PureWindowsPath(record["image_path"])
            or witness.caller not in identities or witness.caller[1] > record["creation_time_100ns"]
            or witness.caller == member_key(record)
            or provenance.get("command_status") != "HANDLE_OBSERVED"
            or not witness.observed_command_line or provenance.get("command_line") != witness.observed_command_line
            or provenance.get("parent_status") != "VERIFIED_JOB_LIFETIME"
            or (parent.get("pid"), parent.get("creation_time_100ns")) != witness.caller[:2]
            or parent.get("role") != identities[witness.caller]["role"]
            or not witness.expected_output_digest or not witness.observed_output_digest
            or not witness.expected_independent_digest or not witness.observed_independent_digest):
        return UNKNOWN
    if (record["exit_code"] == witness.expected_exit
            and witness.expected_exit != 0
            and witness.observed_output_digest == witness.expected_output_digest
            and witness.observed_independent_digest == witness.expected_independent_digest):
        return AUXILIARY_EXPECTED_NONZERO
    return AUXILIARY_UNEXPECTED_NONZERO


def assess(view, critical_images, *, auxiliary_witnesses=None):
    """Classify the full verified Job set. Private witnesses are keyed by member identity."""
    witnesses = {} if auxiliary_witnesses is None else auxiliary_witnesses
    records = view["process_records"]
    exits = view["process_exits"]
    identities = {member_key(record): record for record in records}
    captured = {(item["pid"], item["creation_time_100ns"]): item
                for item in view.get("process_provenance", {}).get("members", ())}
    accounted = Counter()
    blockers = set()
    members = []
    for item in exits:
        key = member_key(item)
        original = identities.get(key)
        expected_source = "direct_native_handle" if item["role"] == "wrapper" else "retained_windows_handle"
        valid = (original is not None and original["role"] == item["role"]
                 and original["identity_status"] == item["identity_status"] == "VERIFIED"
                 and item["exit_source"] == expected_source and type(item["exit_code"]) is int)
        critical = _critical_role(item, critical_images) if valid else None
        witness = witnesses.get(key) if valid and not critical and item["exit_code"] else None
        semantic = UNKNOWN
        if critical:
            accounted[critical] += 1
            semantic = CRITICAL_FAILURE if item["exit_code"] else CRITICAL_SUCCESS
        elif witness:
            semantic = _auxiliary_semantics(item, witness, identities, captured.get(key[:2], {}))
        if not valid:
            blockers.add(MEMBERSHIP_UNCERTAIN)
        elif semantic in (CRITICAL_FAILURE, AUXILIARY_UNEXPECTED_NONZERO) or (semantic == UNKNOWN and item["exit_code"]):
            blockers.add(semantic)
        entry = {"role": item["role"], "classification": semantic}
        if critical:
            entry["critical_role"] = critical
        if semantic in (AUXILIARY_EXPECTED_NONZERO, AUXILIARY_UNEXPECTED_NONZERO):
            entry["operation"] = witness.operation
            entry["output_digest"] = witness.observed_output_digest
            entry["caller_role"] = identities[witness.caller]["role"]
            entry["independent_digest"] = witness.observed_independent_digest
        members.append(entry)

    evidence = view.get("membership_evidence", {})
    exit_keys = {member_key(item) for item in exits}
    if (evidence.get("complete") is not True or view["observation_unknowns"]
            or view["all_observed_exited"] is not True
            or len(records) != len(identities) or len(exits) != len(exit_keys)
            or len({item["role"] for item in records}) != len(records)
            or identities.keys() != exit_keys
            or len(records) != evidence.get("job_total_processes")
            or len(records) != evidence.get("verified_members")
            or len(exits) != evidence.get("verified_exits")):
        blockers.add(MEMBERSHIP_UNCERTAIN)
    unverified_critical = sorted(role for role in critical_images if accounted[role] != 1)
    if unverified_critical:
        blockers.add(UNKNOWN)
    precedence = (MEMBERSHIP_UNCERTAIN, CRITICAL_FAILURE, AUXILIARY_UNEXPECTED_NONZERO, UNKNOWN)
    return {
        "policy": POLICY,
        "accepted": not blockers,
        "reason": next((reason for reason in precedence if reason in blockers), None),
        "unverified_critical_roles": unverified_critical,
        "counts": dict(Counter(item["classification"] for item in members)),
        "members": members,
    }


def summary(assessment):
    return {key: value for key, value in assessment.items() if key != "members"}
