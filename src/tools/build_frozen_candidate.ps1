param([string]$CandidateName = 'frozen-candidate', [switch]$TestOnly,
      [Parameter(Mandatory=$true)][string]$InputRoot,
      [Parameter(Mandatory=$true)][string]$BuildPython)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$projectRoot = (Resolve-Path -LiteralPath $InputRoot).Path
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $projectRoot
function Get-InputHashes {
  @(Get-ChildItem -LiteralPath $projectRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
    [ordered]@{path=$_.FullName.Substring($projectRoot.Length+1);sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
  })
}
$beforeInputs = Get-InputHashes
if (-not $beforeInputs.Count -or @(Get-ChildItem -LiteralPath $projectRoot -File -Recurse | Where-Object { -not $_.IsReadOnly }).Count) {
  throw 'IMMUTABLE_INPUT_SNAPSHOT_REQUIRED'
}
$python = (Resolve-Path -LiteralPath $BuildPython).Path
$leaf = [System.IO.Path]::GetFileName($CandidateName)
if ($leaf -ne $CandidateName -or $CandidateName.Contains('..')) { throw 'INVALID_CANDIDATE_NAME' }
$output = Join-Path (Split-Path -Parent $projectRoot) ('artifacts\' + $CandidateName)
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'BUILD_PYTHON_MISSING' }
if ((& $python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))") -ne '3.12.10') { throw 'PYTHON_312_X64_REQUIRED' }
& $python -c "import struct, tkinter; assert struct.calcsize('P') == 8 and tkinter.TkVersion >= 8.6; import PyInstaller, mcp, psutil, yaml"
if ($LASTEXITCODE -ne 0) { throw 'BUILD_DEPENDENCIES_MISSING' }
if (Test-Path -LiteralPath $output) { throw "Refusing to overwrite build output: $output" }
New-Item -ItemType Directory -Path $output | Out-Null
$identity = Join-Path $output 'metadata\BUILD_ID.json'
$identityArgs = @((Join-Path $projectRoot 'tools\create_build_identity.py'), '--output', $identity)
if ($TestOnly) { $identityArgs += '--test-only' }
& $python @identityArgs
if ($LASTEXITCODE -ne 0) { throw "BUILD_ID_GENERATION_FAILED:$LASTEXITCODE" }
& $python -m pip freeze | Set-Content -LiteralPath (Join-Path $output 'BUILDENV_FREEZE.txt') -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'BUILDENV_FREEZE_FAILED' }
@{ python='3.12.10'; architecture='x64'; packages=@(Get-Content -LiteralPath (Join-Path $output 'BUILDENV_FREEZE.txt')) } |
  ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'BUILDENV_LOCK.json') -Encoding utf8
$env:PYINSTALLER_CONFIG_DIR = Join-Path $output 'pyinstaller-config'
$dist = Join-Path $output 'dist'
$workGui = Join-Path $output 'work\gui'
$workOwner = Join-Path $output 'work\owner'
$specGui = Join-Path $output 'spec\gui'
$specOwner = Join-Path $output 'spec\owner'
$localeData = Join-Path $projectRoot 'abqjobpilot\locales'
$skinsData = Join-Path $projectRoot 'skins'
$settingsTemplate = Join-Path $projectRoot 'settings.toml'
$licenseData = Join-Path $projectRoot 'LICENSE'
$iconData = Join-Path $projectRoot 'assets\icons'
$devIcon = Join-Path $iconData 'antigravity-approved-B-dark\abqjobpilot_dev.ico'
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name AbqJobPilot `
  --icon $devIcon --add-data "$iconData;assets/icons" `
  --paths $projectRoot `
  --exclude-module abqjobpilot.gui_legacy --exclude-module abqjobpilot.classic_workspace --exclude-module abqjobpilot.runner_core `
  --exclude-module abqjobpilot.web_host --exclude-module abqjobpilot.web_bridge --exclude-module pythonnet --exclude-module webview --exclude-module webview2 `
  --distpath $dist --workpath $workGui --specpath $specGui `
  --add-data "$identity;abqjobpilot" --add-data "$localeData;abqjobpilot/locales" --add-data "$skinsData;skins" `
  --add-data "$settingsTemplate;config" --add-data "$licenseData;licenses" `
  --collect-submodules mcp.server --collect-submodules mcp.shared --collect-submodules mcp.types --copy-metadata mcp (Join-Path $projectRoot 'launch_gui.py')
if ($LASTEXITCODE -ne 0) { throw "GUI_BUILD_FAILED:$LASTEXITCODE" }
& $python -m PyInstaller --noconfirm --clean --onedir --console --name AbqJobPilotOwner `
  --icon $devIcon `
  --paths $projectRoot `
  --exclude-module abqjobpilot.gui_legacy --exclude-module abqjobpilot.classic_workspace --exclude-module abqjobpilot.runner_core `
  --exclude-module abqjobpilot.web_host --exclude-module abqjobpilot.web_bridge --exclude-module mcp --exclude-module pythonnet --exclude-module webview --exclude-module webview2 `
  --distpath $dist --workpath $workOwner --specpath $specOwner `
  --add-data "$identity;abqjobpilot" --add-data "$licenseData;licenses" (Join-Path $projectRoot 'launch_owner.py')
if ($LASTEXITCODE -ne 0) { throw "OWNER_BUILD_FAILED:$LASTEXITCODE" }
$guiExe = Join-Path $dist 'AbqJobPilot\AbqJobPilot.exe'
$ownerExe = Join-Path $dist 'AbqJobPilotOwner\AbqJobPilotOwner.exe'
if (-not (Test-Path -LiteralPath $guiExe -PathType Leaf) -or -not (Test-Path -LiteralPath $ownerExe -PathType Leaf)) {
  throw 'EXPECTED_EXE_MISSING'
}
# Inspect the actual archive, not merely the source list in BUILD_ID.json.
@'
import json, marshal, sys, types
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
owner, output = map(Path, sys.argv[1:])
archive = CArchiveReader(str(owner))
entry = marshal.loads(archive.extract('launch_owner'))
def strings(code):
    for value in code.co_consts:
        if isinstance(value, str): yield value
        elif isinstance(value, types.CodeType): yield from strings(value)
constants = set(strings(entry))
modules = set(archive.open_embedded_archive('PYZ.pyz').toc)
required = 'abqjobpilot.execution.process_fixture'
assert '--fixture-role' in constants and '--service-owner' in constants, 'OWNER_ROLE_ENTRY_MISSING'
assert required in modules, 'OWNER_FIXTURE_MODULE_MISSING'
for prefix in ('abqjobpilot.runner_core', 'abqjobpilot.gui_legacy', 'abqjobpilot.classic_workspace', 'webview', 'webview2', 'pythonnet'):
    assert not any(n == prefix or n.startswith(prefix + '.') for n in modules), prefix
output.write_text(json.dumps({'entry': 'launch_owner', 'fixed_fixture_entry': True,
    'fixture_module': required, 'fixture_module_present': True,
    'forbidden_modules_absent': True}, indent=2), encoding='utf-8')
'@ | & $python - $ownerExe (Join-Path $output 'OWNER_BUNDLE_CHECK.json')
if ($LASTEXITCODE -ne 0) { throw 'OWNER_BUNDLE_CONTRACT_FAILED' }
$files = @(Get-ChildItem -LiteralPath $dist -File -Recurse | Sort-Object FullName | ForEach-Object {
  [ordered]@{path=$_.FullName.Substring($dist.Length + 1).Replace('\','/');bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
$identityValue = Get-Content -LiteralPath $identity -Raw | ConvertFrom-Json
$afterInputs = Get-InputHashes
if (($beforeInputs | ConvertTo-Json -Depth 4 -Compress) -cne ($afterInputs | ConvertTo-Json -Depth 4 -Compress)) {
  throw 'BUILD_INPUT_CHANGED'
}
$beforeInputs | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'INPUT_FILES.json') -Encoding utf8
$status = if ($TestOnly) { 'TEST_ONLY_NOT_FOR_RELEASE' } else { 'ISOLATED_QUALIFICATION_CANDIDATE_NOT_RELEASE' }
$manifest = [ordered]@{
  format='ap-ui03-native-tk-build-manifest-v1'
  status=$status
  app_id='abqjobpilot.windows'
  product_version=$identityValue.product_version
  skin_api_version='1.0.0'
  build_id=$identityValue.build_id
  source_tree_sha256=$identityValue.source_tree_sha256
  source_files=$identityValue.source_files
  input_snapshot=$projectRoot
  input_files_sha256=(Get-FileHash -LiteralPath (Join-Path $output 'INPUT_FILES.json') -Algorithm SHA256).Hash.ToLowerInvariant()
  input_verified_before_and_after=$true
  excluded_modules=@('abqjobpilot.gui_legacy','abqjobpilot.classic_workspace','abqjobpilot.runner_core')
  build_environment=$identityValue.build_environment
  build_scripts=@(
    [ordered]@{path='tools/create_build_identity.py';sha256=(Get-FileHash -LiteralPath (Join-Path $projectRoot 'tools\create_build_identity.py') -Algorithm SHA256).Hash.ToLowerInvariant()},
    [ordered]@{path='tools/build_frozen_candidate.ps1';sha256=(Get-FileHash -LiteralPath (Join-Path $projectRoot 'tools\build_frozen_candidate.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()},
    [ordered]@{path='tools/prepare_build_snapshot.ps1';sha256=(Get-FileHash -LiteralPath (Join-Path $projectRoot 'tools\prepare_build_snapshot.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()}
  )
  environment_lock=@(
    [ordered]@{path='BUILDENV_LOCK.json';sha256=(Get-FileHash -LiteralPath (Join-Path $output 'BUILDENV_LOCK.json') -Algorithm SHA256).Hash.ToLowerInvariant()},
    [ordered]@{path='BUILDENV_FREEZE.txt';sha256=(Get-FileHash -LiteralPath (Join-Path $output 'BUILDENV_FREEZE.txt') -Algorithm SHA256).Hash.ToLowerInvariant()}
  )
  roles=[ordered]@{gui='AbqJobPilot/AbqJobPilot.exe';owner='AbqJobPilotOwner/AbqJobPilotOwner.exe'}
  distribution_files=$files
}
$manifestPath = Join-Path $output 'BUILD_MANIFEST.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() + '  BUILD_MANIFEST.json' |
  Set-Content -LiteralPath (Join-Path $output 'BUILD_MANIFEST.sha256') -Encoding ascii
# Ship the complete candidate manifest at the portable root for the internal TEST_ONLY Factory.
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $dist 'BUILD_MANIFEST.json')
Copy-Item -LiteralPath (Join-Path $output 'BUILD_MANIFEST.sha256') -Destination (Join-Path $dist 'BUILD_MANIFEST.sha256')
$zipPath = Join-Path $output ('AbqJobPilot-' + $identityValue.product_version + '-windows-x64.zip')
Compress-Archive -Path (Join-Path $dist '*') -DestinationPath $zipPath -CompressionLevel Optimal
$distBytes = (Get-ChildItem -LiteralPath $dist -File -Recurse | Measure-Object -Property Length -Sum).Sum
$guiBytes = (Get-ChildItem -LiteralPath (Join-Path $dist 'AbqJobPilot') -File -Recurse | Measure-Object -Property Length -Sum).Sum
$ownerBytes = (Get-ChildItem -LiteralPath (Join-Path $dist 'AbqJobPilotOwner') -File -Recurse | Measure-Object -Property Length -Sum).Sum
$zipBytes = (Get-Item -LiteralPath $zipPath).Length
$guiFiles = @(Get-ChildItem -LiteralPath (Join-Path $dist 'AbqJobPilot') -File -Recurse)
$ownerFiles = @(Get-ChildItem -LiteralPath (Join-Path $dist 'AbqJobPilotOwner') -File -Recurse)
function Get-CategoryBytes($files) {
  $python = 0L; $tcltk = 0L; $other = 0L
  foreach ($file in $files) {
    $name = $file.Name.ToLowerInvariant(); $relative = $file.FullName.ToLowerInvariant()
    if ($name -match '^python3(12)?\.dll$' -or $name -eq 'base_library.zip' -or $name -like 'vcruntime*.dll') { $python += $file.Length }
    elseif ($name -like 'tcl*.dll' -or $name -like 'tk*.dll' -or $name -eq '_tkinter.pyd' -or $relative -match '\\(tcl|tk)8\.') { $tcltk += $file.Length }
    else { $other += $file.Length }
  }
  return [ordered]@{cpython_runtime_bytes=$python;tcl_tk_bytes=$tcltk;application_and_third_party_bytes=$other}
}
$guiHashes = @{}; foreach ($file in $guiFiles) { $rel=$file.FullName.Substring((Join-Path $dist 'AbqJobPilot').Length+1).Replace('\','/'); $guiHashes[$rel]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
$ownerDuplicateBytes = 0L
foreach ($file in $ownerFiles) { $rel=$file.FullName.Substring((Join-Path $dist 'AbqJobPilotOwner').Length+1).Replace('\','/'); if ($guiHashes.ContainsKey($rel) -and $guiHashes[$rel] -eq (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()) { $ownerDuplicateBytes += $file.Length } }
[ordered]@{gui_onedir_bytes=$guiBytes;owner_onedir_bytes=$ownerBytes;distribution_bytes=$distBytes;zip_bytes=$zipBytes;
  gui_categories=(Get-CategoryBytes $guiFiles);owner_categories=(Get-CategoryBytes $ownerFiles);duplicate_identical_gui_owner_bytes=$ownerDuplicateBytes} |
  ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'SIZE_SUMMARY.json') -Encoding utf8
"OUTPUT=$output"
"GUI=$guiExe"
"OWNER=$ownerExe"
"BUILD_ID=$($identityValue.build_id)"
"DIST_FILES=$($files.Count)"
"GUI_BYTES=$guiBytes"
"OWNER_BYTES=$ownerBytes"
"DIST_BYTES=$distBytes"
"ZIP_BYTES=$zipBytes"
"DUPLICATE_IDENTICAL_BYTES=$ownerDuplicateBytes"

