# Fixed read-only action. No command passthrough and no execute fallback.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
try {
    $python='D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
    $entry=Join-Path $PSScriptRoot 'candidate.py'
    $raw=@(& $python -B $entry check 2>&1)
    $code=$LASTEXITCODE
    $text=$raw -join [Environment]::NewLine
    $value=$text | ConvertFrom-Json
    $root=Join-Path 'C:\Users\wuxia\AppData\Local\Temp' ('AbqJobPilot_Run011_PolicyCheck_'+[Guid]::NewGuid().ToString('N'))
    $null=[IO.Directory]::CreateDirectory($root)
    $path=Join-Path $root 'SELF_CHECK.json'
    $bytes=[Text.Encoding]::UTF8.GetBytes($text)
    $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
    try {$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)} finally {$stream.Dispose()}
    Write-Host ('STATUS: '+$value.status)
    Write-Host ('MACHINE EXIT CODE: '+$code)
    Write-Host ('REPORT: '+$path)
    Write-Host 'NO SOLVER WAS CALLED. This check is not execution approval.'
    Write-Host 'Keep this report. No execute action is chained to this script.'
    Write-Output $text
} catch {
    Write-Host 'SELF_CHECK_ERROR: no execute fallback. Preserve the error and stop.'
    Write-Error $_
}
