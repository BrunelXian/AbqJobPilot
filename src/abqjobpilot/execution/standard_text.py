"""Structure-first decoding of bounded Abaqus/Standard text. Headers are diagnostic only."""
import re
from decimal import Decimal
from pathlib import Path
from .models import bytes_digest, require
from .paths import confined
from .sanity_model import file_bytes, sha

PARSER = "standard-node-print-v1"
NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DdEe][+-]?\d{1,3})?"
HEADER = re.compile(r"^Abaqus(?:/[A-Za-z]+)?\s+(.+?)\s+Date\b.*", re.I)


def lines(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 1048576 and b"\x00" not in raw,
            "INVALID_DAT", "Expected bounded text")
    for codec in ("utf-8-sig", "cp936", "cp1252"):
        try:
            text = raw.decode(codec)
            break
        except UnicodeDecodeError:
            continue
    else:
        require(False,"UNSUPPORTED_TEXT_ENCODING","Unsupported text encoding")
    rows = [" ".join(row.split()) for row in text.splitlines()]
    require(len(rows) <= 16000 and all(len(row) <= 4096 for row in rows), "TEXT_LIMIT", "Text exceeds parser bounds")
    return rows


def metadata(rows):
    versions = sorted({m[1] for row in rows if (m := HEADER.fullmatch(row))})
    return {"reported_release": versions, "parser": PARSER}


def displacement(raw, selector, *, terminal=False, model_title=None):
    rows = lines(raw)
    step, inc = selector["step"], selector["increment"]
    frames = [(i, int(m[1]), int(m[2])) for i, row in enumerate(rows)
              if (m := re.search(r"\bSTEP\s+(\d+)\s+INCREMENT\s+(\d+)$", row, re.I))]
    selected_step=[k for _,s,k in frames if s==step]
    require(selected_step and selected_step==sorted(set(selected_step)), "FRAME_AMBIGUOUS","Missing, out-of-order or repeated frame")
    if inc=="LAST_COMPLETED":
        inc=selected_step[-1]
    selected = [i for i,s,k in frames if (s,k) == (step,inc)]
    require(len(selected) == 1, "FRAME_AMBIGUOUS", "One exact step and increment required")
    start = selected[0]
    if model_title is not None:
        title=rows[start].rsplit(" STEP ",1)[0]
        require(title==model_title, "MODEL_TITLE_MISMATCH", "DAT heading differs from the admitted deck")
    end = next((i for i,s,k in frames if i > start), len(rows))
    frame = rows[start:end]
    if terminal:
        require(end==len(rows) and all(s==step for _,s,_ in frames) and
                sum(re.fullmatch(r"S T E P "+str(step)+r" S T A T I C A N A L Y S I S",r) is not None for r in rows)==1,
                "FRAME_AMBIGUOUS","Expected the only static analysis step of the admitted model")
    summary = [i for i,row in enumerate(frame) if row == f"INCREMENT {inc} SUMMARY"]
    times = [i for i,row in enumerate(frame) if (m := re.fullmatch(r"TIME INCREMENT COMPLETED ("+NUM+r") , FRACTION OF STEP COMPLETED ("+NUM+r")",row)) and 0 < decimal(m[2]) <= 1 and (not terminal or decimal(m[2]) == 1)]
    require(len(summary) == len(times) == 1 and summary[0] < times[0], "FINAL_INCREMENT_UNCONFIRMED", "Missing final increment summary")
    if terminal:
        stamps=[i for i,r in enumerate(frame) if (m:=re.fullmatch(r'STEP TIME COMPLETED ('+NUM+r') , TOTAL TIME COMPLETED ('+NUM+r')',r))
                and all(decimal(v)==1 for v in m.groups())]
        require(len(stamps)==1 and times[0]<stamps[0],"FINAL_TIME_UNCONFIRMED","Model end time differs")
        times=stamps
    completed = [i for i,row in enumerate(frame) if row=="THE ANALYSIS HAS BEEN COMPLETED"]
    if terminal:
        require(len(completed)==1 and times[0]<completed[0],"FINAL_TIME_UNCONFIRMED","Expected analysis completion after the selected frame")
    if completed:
        frame = frame[:completed[0]]
    region = selector["region"]
    tables = []
    for i, row in enumerate(frame):
        if i <= times[0] or not re.fullmatch(r"NODE FOOT- U[123](?: U[123]){0,2}", row):
            continue
        prior = [s for s in frame[times[0]+1:i] if s]
        expected = ["THE FOLLOWING TABLE IS PRINTED FOR ALL NODES"] if region == "ALL" else [
            "THE FOLLOWING TABLE IS PRINTED FOR NODES BELONGING TO NODE SET", region]
        if prior[-len(expected):] == expected or prior[-1:] == [' '.join(expected)]:
            tables.append(i)
    require(len(tables) == 1, "TABLE_AMBIGUOUS", "Expected one matching global node table")
    pos = tables[0]
    cols = frame[pos].split()[2:]
    component = selector["component"]
    require(len(cols) == len(set(cols)) and component in cols and frame[pos+1:pos+2] == ["NOTE"],
            "COMPONENT_UNAVAILABLE", "Requested component absent or ambiguous")
    cursor = pos + 2
    while cursor < len(frame) and not frame[cursor]:
        cursor += 1
    values = {}
    while cursor < len(frame) and frame[cursor]:
        parts = frame[cursor].split()
        require(len(parts) == len(cols)+1 and re.fullmatch(r"[1-9]\d{0,8}",parts[0]) and
                parts[0] not in values, "INVALID_NODE_ROW", "Duplicate or invalid node")
        data = [decimal(v) for v in parts[1:]]
        values[parts[0]] = (data[cols.index(component)], start+cursor+1)
        cursor += 1
    node = str(selector["node"])
    require(node in values, "NODE_UNAVAILABLE", "Target node absent")
    value, lineno = values[node]
    return {**metadata(rows), "raw_value":str(value), "value":str(value * selector["sign"]),
            "selector":dict(selector), "step":step, "increment":inc, "line":lineno, "dat_sha256":sha(raw), "extraction":"EXTRACTED"}


def decimal(value):
    require(len(value) <= 36 and re.fullmatch(NUM, value), "INVALID_NUMBER", "Finite fixed or scientific notation required")
    return Decimal(value.upper().replace("D","E"))


def bound_terminal_text(context, plan, observation, intent, *, allow_partial=False):
    """Read only the current Attempt's pinned native text outputs."""
    raw = {}
    root = Path(plan['engineering'])
    for ext in ('dat', 'sta', 'msg'):
        matches = [a for a in observation['artifacts'] if a['logical_ref'] == 'output:' + ext]
        if not matches and allow_partial:
            continue
        require(len(matches) == 1, 'EVIDENCE_IDENTITY_MISMATCH', 'Expected one artifact per logical output')
        artifact = matches[0]
        path = confined(context.test_root, root / (plan['job_name'] + '.' + ext), exists=True)
        data = file_bytes(path, 1048576)
        st = path.stat()
        require((st.st_dev, st.st_ino, st.st_mtime_ns, len(data), bytes_digest(data)) ==
                (artifact['device'], artifact['inode'], artifact['mtime_ns'], artifact['size'], artifact['digest'])
                and min(st.st_ctime_ns, st.st_mtime_ns) >= intent['intent_at_ns'],
                'EVIDENCE_CHANGED', 'Artifact changed or predates attempt')
        raw[ext] = data
    return raw


def terminal_outcome(raw):
    records = [lines(raw[ext]) if ext in raw else [] for ext in ("dat", "sta", "msg")]
    negative=re.compile(r"\*\*\*\s*ERROR|HAS NOT BEEN COMPLETED|ANALYSIS (?:HAS BEEN |WAS )?(?:ABORTED|TERMINATED)|^[1-9]\d* ERROR MESSAGES?",re.I)
    if any(negative.search(row) for rows in records for row in rows):
        return "FAILED"
    d,s,m = records
    complete = (d.count("THE ANALYSIS HAS BEEN COMPLETED") == d.count("ANALYSIS COMPLETE") == 1
            and d.index("THE ANALYSIS HAS BEEN COMPLETED") < d.index("ANALYSIS COMPLETE")
            and s.count("THE ANALYSIS HAS COMPLETED SUCCESSFULLY")==1 and [r for r in s if r][-1]=="THE ANALYSIS HAS COMPLETED SUCCESSFULLY"
            and m.count("THE ANALYSIS HAS BEEN COMPLETED")==1)
    return "COMPLETED" if complete else "UNKNOWN"


def completion(dat, sta, msg):
    return terminal_outcome({"dat": dat, "sta": sta, "msg": msg}) == "COMPLETED"

