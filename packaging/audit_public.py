"""Inspect a locally built candidate and its source without running the application.

Use the locked build Python. Pass the build directory and an external JSON array
of site-specific strings to reject. Keep the latter outside the distribution.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import marshal
from pathlib import Path, PureWindowsPath
import re
import subprocess
import tempfile
from types import CodeType
import zipfile

from PyInstaller.archive.readers import CArchiveReader


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("private_markers", type=Path)
    args = parser.parse_args()
    root = args.build.resolve()
    markers = json.loads(args.private_markers.read_text(encoding="utf-8-sig"))
    if not markers or not all(isinstance(x, str) and x for x in markers):
        raise ValueError("Provide a nonempty private marker list")
    words = {s for x in markers for s in (x, x.replace("\\", "/"), x.replace("\\", "\\\\"))}
    deny = [x.lower().encode(enc) for x in words for enc in ("utf-8", "utf-16le")]
    stats = Counter()
    abs_filenames = set()
    checked = set()
    token = re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{36,}|"
                       rb"sk-proj-[A-Za-z0-9_-]{40,}|AKIA[A-Z0-9]{16}|"
                       rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\s+[A-Za-z0-9+/]{32}")

    def scan(name, raw):
        content = sha(raw)
        if content in checked:
            return
        checked.add(content)
        lower = raw.lower()
        if any(fragment in lower for fragment in deny) or token.search(raw):
            raise ValueError(f"Private marker in {name}")
        if raw.startswith(b"SQLite format 3\x00"):
            raise ValueError(f"Database in {name}")

    def code_paths(code):
        stats["code_objects"] += 1
        if PureWindowsPath(code.co_filename).is_absolute() or code.co_filename.startswith("/"):
            abs_filenames.add(code.co_filename)
        for value in code.co_consts:
            if isinstance(value, CodeType):
                code_paths(value)

    repo = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo)

    # Scan only reachable publication history, including deleted blobs.
    rows = git("rev-list", "--objects", "HEAD").splitlines()
    with subprocess.Popen(["git","cat-file","--batch"], cwd=repo, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as objects:
        for row in rows:
            oid, _, path = row.partition(b" ")
            objects.stdin.write(oid+b"\n")
            objects.stdin.flush()
            _, typ, size = objects.stdout.readline().split()
            raw = objects.stdout.read(int(size))
            if objects.stdout.read(1) != b"\n" or len(raw) != int(size):
                raise ValueError("Incomplete Git object")
            scan("Git " + path.decode(errors="replace"), raw)
            stats["git_" + typ.decode()] += 1
        objects.stdin.close()
        if objects.wait():
            raise ValueError("Git object scan failed")

    (setup,) = (root / "distribution").glob("*Setup.exe")
    outer = setup.read_bytes()
    scan("setup image", outer)
    payload = (root / "payload.zip").read_bytes()
    if outer.count(payload) != 1:
        raise ValueError("Expected the exact embedded ZIP once")
    role_names = {"AbqJobPilot", "AbqJobPilotCLI", "AbqJobPilotOwner"}
    identity = json.loads((root / "BUILD_ID.json").read_bytes())
    src = root / "input" / "src"
    source_index = {row.split(b"\t",1)[1].decode(): row.split()[2].decode()
                    for row in git("ls-tree","-r","-z","HEAD","--","src").split(b"\0") if row}
    for rel, expected in identity["source_files"].items():
        raw = (src / rel).read_bytes()
        blob_id = hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
        if blob_id != source_index.get("src/"+rel):
            raise ValueError(f"Snapshot differs from tracked source: {rel}")
        if sha((src / rel).read_bytes()) != expected:
            raise ValueError(f"Source identity mismatch in {rel}")
    with zipfile.ZipFile(io.BytesIO(payload)) as z, tempfile.TemporaryDirectory(dir=root) as scratch:
        files = json.loads(z.read("FILES.json"))
        index = {x["path"]: x["sha256"] for x in files}
        if len(index) != len(files) or len(z.namelist()) != len(index)+1 or set(z.namelist()) != set(index)|{"FILES.json"}:
            raise ValueError("Invalid payload inventory")
        for name in z.namelist():
            raw = z.read(name)
            stats["payload_files"] += 1
            if name in index and sha(raw) != index[name]:
                raise ValueError(f"File digest mismatch: {name}")
            scan(name, raw)
            path = Path(name)
            if path.suffix.lower() in {".odb", ".inp", ".dat", ".sta", ".db", ".sqlite", ".sqlite3", ".lic",
                                       ".lck", ".pfx", ".key", ".pem", ".env"} or path.name.lower() in {
                                           "agent_project.json", "receipt.json", "connection.json"}:
                raise ValueError(f"Unexpected data file: {name}")
            if path.name == "settings.toml" and raw != (src / "settings.toml").read_bytes():
                raise ValueError("Unexpected settings content")
            if path.name == "BUILD_ID.json" and json.loads(raw) != identity:
                raise ValueError("Embedded identity mismatch")
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(io.BytesIO(raw)) as nested:
                    for member in nested.namelist():
                        inner = nested.read(member)
                        scan(name+"/"+member, inner)
                        if member.endswith(".pyc"):
                            code_paths(marshal.loads(inner[16:]))
            if name not in {f"{r}/{r}.exe" for r in role_names}:
                continue
            local = Path(scratch) / path.name
            local.write_bytes(raw)
            archive = CArchiveReader(str(local))
            for entry, record in archive.toc.items():
                if record[-1] == "z":
                    pyz = archive.open_embedded_archive(entry)
                    for module in pyz.toc:
                        value = pyz.extract(module)
                        if not isinstance(value, CodeType):
                            continue
                        scan(module, marshal.dumps(value))
                        code_paths(value)
                        stats["pyz_modules"] += 1
                    for module in ("sanity_hil", "standard_contract", "rod_output_v2"):
                        rel = "abqjobpilot/execution/"+module+".py"
                        value = pyz.extract("abqjobpilot.execution."+module)
                        expected = compile((src / rel).read_bytes(),value.co_filename,"exec",dont_inherit=True)
                        if expected != value:
                            raise ValueError(f"{name} compiled contract differs: {module}")
                        stats["public_contract_matches"] += 1
                else:
                    inner = archive.extract(entry)
                    scan(name+"/"+entry, inner)
                    if record[-1] in {"s","m","M"}:
                        code_paths(marshal.loads(inner))
    if stats["public_contract_matches"] != 9:
        raise ValueError("All three roles must contain the reviewed public contracts")
    print(json.dumps({"installer_sha256":sha(outer),"installer_bytes":len(outer),"counts":stats,
                      "absolute_co_filenames":sorted(abs_filenames)},indent=2))


if __name__ == "__main__":
    main()
