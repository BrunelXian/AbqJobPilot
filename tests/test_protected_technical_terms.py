"""Protected display terminology; protocol values and execution records stay verbatim."""
import json
import re
from pathlib import Path

from abqjobpilot.ui_resources import LANGUAGES
from abqjobpilot.command_console import AGENT_UI_STRINGS, AI_INSTRUCTION, COMMAND_REFERENCE


ROOT = Path(__file__).resolve().parents[1] / 'src'
POLICY = json.loads((ROOT / "abqjobpilot/locales/protected_terms.json").read_text(encoding="utf-8"))


def contains_term(text: str, term: str) -> bool:
    plural = "s?" if term in {"Run", "Job", "CPU", "GPU", "Grant", "Receipt"} else ""
    return re.search(rf"(?<![A-Za-z]){re.escape(term)}{plural}(?![A-Za-z])", text) is not None


def test_protected_term_policy_is_unique_and_uses_canonical_spellings():
    terms = POLICY["canonical_terms"]
    assert len(terms) == len(set(terms))
    assert terms == ["Abaqus", "CAE", "Job", "Step", "Increment", "INP", "ODB", "STA",
                     "CPU", "GPU", "MCP", "IPC", "Plan", "Grant", "Run", "Receipt"]
    assert POLICY["format"] == "abqjobpilot-protected-technical-terms-v1"


def test_all_locale_technical_surfaces_keep_protected_terms():
    baseline = None
    for locale in LANGUAGES:
        path = ROOT / "abqjobpilot/locales" / f"{locale}.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        baseline = baseline or set(catalog)
        assert set(catalog) == baseline, locale
        for term, keys in POLICY["locale_surfaces"].items():
            for key in keys:
                assert key in catalog, (locale, key)
                assert contains_term(catalog[key], term), (locale, key, term, catalog[key])
        for extension in (".inp", ".cae"):
            assert extension in catalog["external"], (locale, extension)
        assert "STA" in catalog["progressUnavailable"], locale
        assert catalog["follow"]
        assert "ODB" in catalog["staSummary"] or "ODB" in catalog["odb"], locale


def test_agent_command_prompts_and_summaries_preserve_terms():
    assert all(term in AI_INSTRUCTION for term in ("CPU", "GPU", "--inp", "Job_xxx"))
    assert all(term in COMMAND_REFERENCE for term in ("--inp", "Job_xxx", "--job-id"))
    for locale in ("en", "zh"):
        words = AGENT_UI_STRINGS[locale]
        for key in ("enqueued", "jobs_found", "job_status"):
            assert contains_term(words[key], "Job"), (locale, key, words[key])
        assert "INP" in words["folder_confirm"]


def test_evidence_labels_and_wire_field_names_are_explicit_verbatim_contracts():
    source = (ROOT / "abqjobpilot/desktop_workspace.py").read_text(encoding="utf-8")
    for label in POLICY["verbatim_gui_evidence_labels"]:
        assert repr(label) in source, label
    fields = POLICY["verbatim_status_and_identifier_fields"]
    assert len(fields) == len(set(fields))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", field) for field in fields)

