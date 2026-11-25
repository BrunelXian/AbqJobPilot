param([Parameter(Mandatory=$true)][string]$ProjectRoot,
      [Parameter(Mandatory=$true)][string]$SnapshotRoot)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$target = [System.IO.Path]::GetFullPath($SnapshotRoot)
if (Test-Path -LiteralPath $target) { throw 'SNAPSHOT_TARGET_ALREADY_EXISTS' }
New-Item -ItemType Directory -Path $target -Force | Out-Null
foreach ($relative in @('launch_gui.py','launch_owner.py','LICENSE','settings.toml','requirements.txt','requirements-mcp.txt','requirements-build.txt','requirements-build.lock.txt','abqjobpilot.ico')) {
  $source = Join-Path $root $relative
  if (Test-Path -LiteralPath $source -PathType Leaf) {
    $destination = Join-Path $target $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
  }
}
$sources = @()
$packageRoot = Join-Path $root 'abqjobpilot'
foreach ($file in Get-ChildItem -LiteralPath $packageRoot -File -Recurse) {
  $relative = $file.FullName.Substring($root.Length + 1)
  if ($relative.StartsWith('abqjobpilot\abqjobpilot\',[System.StringComparison]::OrdinalIgnoreCase)) { continue }
  if ($relative -match '\\webui\\') { continue }
  if ($file.Extension -ne '.py' -and -not ($relative -match '^abqjobpilot\\locales\\[^\\]+\.json$')) { continue }
  $sources += $file
}
$sources += Get-ChildItem -LiteralPath (Join-Path $root 'skins') -File -Recurse
$sources += Get-ChildItem -LiteralPath (Join-Path $root 'assets\icons') -File -Recurse
$sources += Get-Item -LiteralPath (Join-Path $root 'tools\create_build_identity.py'),(Join-Path $root 'tools\build_frozen_candidate.ps1'),(Join-Path $root 'tools\prepare_build_snapshot.ps1')
foreach ($file in $sources) {
  $relative = $file.FullName.Substring($root.Length + 1)
  $destination = Join-Path $target $relative
  New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
  Copy-Item -LiteralPath $file.FullName -Destination $destination
}
Get-ChildItem -LiteralPath $target -File -Recurse | ForEach-Object { $_.IsReadOnly = $true }
$files = @(Get-ChildItem -LiteralPath $target -File -Recurse)
if (-not $files.Count -or @($files | Where-Object { -not $_.IsReadOnly }).Count) { throw 'IMMUTABLE_SNAPSHOT_VERIFICATION_FAILED' }
"SNAPSHOT=$target"
"FILES=$($files.Count)"
