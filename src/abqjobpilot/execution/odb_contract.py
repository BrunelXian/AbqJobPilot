"""Wire and allowlist contract for the controlled ODB operation."""

from .models import fields, integer, require, text

VERSION = "abq-odb-extraction-v1"
FIXTURE = "fixed-u2-fixture-v1"
FIXTURE_OPT_IN = "odb_fixture_test_only"
SELECTOR = {"step": "Step-1", "field": "U", "region": "TIP", "component": "U2", "output_format": "JSON"}
FRAME_LIMIT = 4
REQUEST = ("contract_version", "mode", "receipt_id", "idempotency_key", "script_id", *SELECTOR,
           "first_frame", "frame_count")


def check_request(run_id, request):
    text(run_id)
    fields(request, REQUEST)
    for key in ("receipt_id", "idempotency_key"):
        text(request[key])
    require(request["contract_version"] == VERSION and request["mode"] in ("TEST_ONLY", "REAL"),
            "INVALID_REQUEST", "Explicit extraction contract and mode required")
    require(request["script_id"] == FIXTURE, "ODB_SCRIPT_NOT_ALLOWED", "Only the fixed fixture script is registered")
    require(all(request[key] == value for key, value in SELECTOR.items()),
            "ODB_FIELD_NOT_ALLOWED", "Requested step, field, region, component or format is outside the profile")
    integer(request["first_frame"])
    integer(request["frame_count"], 1)
    require(request["first_frame"] + request["frame_count"] <= FRAME_LIMIT,
            "ODB_RANGE_INVALID", "Frame range exceeds the fixed fixture")
