"""Build the per-user x64 setup from tracked files at HEAD in a fresh directory."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = "packaging/Setup.cs"
ROLES = {"AbqJobPilot": "launch_gui", "AbqJobPilotOwner": "launch_owner", "AbqJobPilotCLI": "launch_cli"}
EXCLUDED = ("abqjobpilot.gui_legacy", "abqjobpilot.classic_workspace", "abqjobpilot.runner_core",
            "abqjobpilot.web_host", "abqjobpilot.web_bridge", "pythonnet", "webview", "webview2",
            "pytest", "PyInstaller")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args, cwd=REPO, **kwargs):
    subprocess.run(args, cwd=cwd, check=True, **kwargs)


def compile_setup(source, exe, version, payload=None):
    compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    # Reuse the archived installer source; never run the old machine-specific recipe.
    text = source.read_text(encoding="utf-8")
    for old, new in (("AbqJobPilot-050-Candidate024", f"AbqJobPilot-{version}"),
                     ("0.5.0 candidate024", version), ('"0.5.0"', f'"{version}"'),
                     ("new candidate024 subfolder", f"new {version} subfolder"),
                     ("Windows Release Candidate", version), ("AbqJobPilot RC", "AbqJobPilot"),
                     ("This RC", "This version")):
        if old not in text:
            raise ValueError(f"Installer template changed at {old}")
        text = text.replace(old, new)
    text = text.replace("class Setup {", f'[assembly:AssemblyVersion("{version}.0")]\n'
                        f'[assembly:AssemblyFileVersion("{version}.0")]\nclass Setup {{')
    cs = source.parent / "Setup.Release.cs"
    cs.write_text(text, encoding="utf-8-sig")
    libraries = ("System.Windows.Forms", "System.Core", "Microsoft.CSharp", "System.Web.Extensions",
                 "System.IO.Compression", "System.IO.Compression.FileSystem")
    flags = [f"/r:{lib}.dll" for lib in libraries]
    if payload:
        flags.append(f"/resource:{payload},payload.zip")
    run(compiler, "/nologo", "/target:winexe", "/platform:x64", "/optimize+", f"/out:{exe}", *flags, cs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New empty build directory to create")
    work = parser.parse_args().output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    archive = work / "inputs.zip"
    run("git", "archive", "--format=zip", f"--output={archive}", "HEAD", "--", "src", TEMPLATE,
        "LICENSE", "CHANGELOG.md", "docs/RELEASE_1_0_0.md")
    with zipfile.ZipFile(archive) as z:
        z.extractall(work / "input")
    inputs = work / "input"
    src = inputs / "src"
    # Pin the three reviewed public site contracts for this release.
    public_inputs = {
        "abqjobpilot/execution/sanity_hil.py": "38767a8aea94968ad551e490076861ff9ad7d2eed5d6f3bf93ed99945d38f863",
        "abqjobpilot/execution/standard_contract.py": "0983f4093dc24ac48da120aa6cdf1b0f003a32379f016de32a3f58a21abf6d9d",
        "abqjobpilot/execution/rod_output_v2.py": "66b556c5c0f1ea344f2de431be79a4120b38058ee3d9987eceacfe79707fc0d9",
    }
    for relative, expected in public_inputs.items():
        if digest(src / relative) != expected:
            raise ValueError(f"Unreviewed public packaging input: {relative}")
    python = sys.executable
    os.environ.update(PYTHONPATH=str(src), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
                      PYINSTALLER_CONFIG_DIR=str(work / "cache"))
    identity = work / "BUILD_ID.json"
    run(python, "-B", src / "tools/create_build_identity.py", "--output", identity, "--release-icon")
    version = json.loads(identity.read_text())["product_version"]
    pe_version = tuple(map(int, version.split("."))) + (0,)
    version_file = work / "version-info.txt"
    version_file.write_text(
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={pe_version}, prodvers={pe_version}, "
        "mask=63, flags=0, OS=262148, fileType=1, subtype=0, date=(0,0)), "
        "kids=[StringFileInfo([StringTable('040904B0', [StringStruct('ProductName','AbqJobPilot'), "
        f"StringStruct('FileVersion','{version}'), StringStruct('ProductVersion','{version}')])]), "
        "VarFileInfo([VarStruct('Translation',[1033,1200])])])", encoding="utf-8")
    payload = work / "payload"
    for name, entry in ROLES.items():
        args = [python, "-B", "-m", "PyInstaller", "--onedir", "--clean", "--noconfirm",
                "--windowed" if name == "AbqJobPilot" else "--console", "--name", name,
                "--icon", src / "assets/icons/antigravity-approved-B-dark/abqjobpilot_release.ico",
                "--paths", src, "--distpath", payload, "--workpath", work / "work",
                "--specpath", work / "spec", "--version-file", version_file, "--add-data", f"{identity};abqjobpilot"]
        for module in EXCLUDED:
            args.extend(["--exclude-module", module])
        if name == "AbqJobPilotOwner":
            args.extend(["--exclude-module", "mcp"])
        else:
            args.extend(["--recursive-copy-metadata", "mcp", "--collect-submodules", "mcp.server",
                         "--collect-submodules", "mcp.shared"])
            for data, dest in (("assets/icons", "assets/icons"), ("skins", "skins"),
                               ("abqjobpilot/locales", "abqjobpilot/locales"), ("settings.toml", "config")):
                args.extend(["--add-data", f"{src / data};{dest}"])
        run(*args, src / f"{entry}.py", cwd=work)

    for rel in ("LICENSE", "CHANGELOG.md", "docs/RELEASE_1_0_0.md", "src/requirements-build.lock.txt"):
        shutil.copyfile(inputs / rel, payload / Path(rel).name)
    notices = payload / "third-party-notices"
    notices.mkdir()
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", notices / "CPython.txt")
    for path in (Path(sys.base_prefix) / "tcl").glob("*/license.terms"):
        shutil.copyfile(path, notices / f"{path.parent.name}.txt")
    for dist in metadata.distributions():
        for rel in dist.files or ():
            if ".dist-info/" not in rel.as_posix() or not (
                    "/licenses/" in rel.as_posix() or rel.name.lower().startswith(("license", "copying", "notice"))):
                continue
            source = Path(dist.locate_file(rel))
            dest = notices / rel.as_posix()
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)

    template = inputs / TEMPLATE
    compile_setup(template, payload / "Uninstall.exe", version)
    files = sorted(p for p in payload.rglob("*") if p.is_file())
    for path in files:
        suffix = path.suffix.lower()
        if suffix in {".odb", ".inp", ".sta", ".dat", ".sqlite", ".sqlite3", ".db",
                      ".lic", ".key", ".pfx", ".pem", ".env", ".lck"} or path.name.lower() in {
                "connection.json", "agent_project.json", "receipt.json", "direct_url.json"}:
            raise ValueError(f"Unexpected private/runtime payload: {path.relative_to(payload)}")
        if suffix == ".msg" and not {"_tk_data", "_tcl_data"}.intersection(path.parts):
            raise ValueError(f"Unexpected message file: {path.relative_to(payload)}")
        if path.name == "settings.toml" and digest(path) != digest(src / "settings.toml"):
            raise ValueError("Bundled settings differ from the tracked template")
    inventory = [{"path": p.relative_to(payload).as_posix(), "sha256": digest(p)} for p in files]
    (payload / "FILES.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    zipped = work / "payload.zip"
    with zipfile.ZipFile(zipped, "w", zipfile.ZIP_DEFLATED) as z:
        for path in [*files, payload / "FILES.json"]:
            z.write(path, path.relative_to(payload))
    out = work / "distribution"
    out.mkdir()
    exe = out / f"AbqJobPilot-{version}-Windows-x64-Setup.exe"
    compile_setup(template, exe, version, zipped)
    (out / "SHA256SUMS.txt").write_text(f"{digest(exe)}  {exe.name}\n", encoding="ascii")
    print(exe, digest(exe), flush=True)


if __name__ == "__main__":
    main()
