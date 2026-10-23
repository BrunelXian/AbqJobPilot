# Run inside the existing operator PowerShell. No new shell, service, job or breakaway.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$here = $PSScriptRoot
$venv = 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
$base = 'D:\Program Files\Python312\python.exe'
$temp = 'C:\Users\wuxia\AppData\Local\Temp'

function Identity($process) {
    $null = $process.Handle # Retain an OS reference before any exit.
    return @{pid=$process.Id; creation_time_100ns=$process.StartTime.ToUniversalTime().ToFileTimeUtc();
             image_path=$process.MainModule.FileName}
}
function Assert-Identity($actual, $expected) {
    if ($actual.pid -ne $expected.pid -or
        $actual.creation_time_100ns -ne $expected.creation_time_100ns -or
        $actual.image_path -ine $expected.image_path) { throw 'PROCESS_IDENTITY_MISMATCH' }
}
function Hold-Verified($expected, $image) {
    $process = [Diagnostics.Process]::GetProcessById($expected.pid)
    try {
        $actual = Identity $process
        Assert-Identity $actual $expected
        if ($actual.image_path -ine $image) { throw 'PROCESS_IMAGE_MISMATCH' }
        return @{process=$process; identity=$actual}
    } catch { $process.Dispose(); throw }
}
function Observe($process, $identity) {
    # WaitForExit(0) + ExitCode on retained .NET Process handle, never PID absence.
    $exited = $process.WaitForExit(0)
    $code = $null
    if ($exited) { $code = $process.ExitCode }
    return @{identity=$identity; observed_at=[DateTime]::UtcNow.ToString('o');
             source='PowerShell_retained_OS_process_reference'; exited=$exited; exit_code=$code}
}
function Publish($root, $name, $value) {
    $path = Join-Path $root $name
    $bytes = [Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 30 -Compress))
    $stream = [IO.File]::Open($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    $mark = [IO.File]::Open($path+'.ready',[IO.FileMode]::CreateNew)
    $mark.Dispose()
}
function Await($predicate, [double]$seconds, $reason) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $seconds) {
        if (& $predicate) { return }
        Start-Sleep -Milliseconds 10
    }
    throw $reason
}
function Read-Published($root, $name) {
    Await { Test-Path -LiteralPath (Join-Path $root ($name+'.ready')) } 8 ('MISSING_'+$name)
    return (Get-Content -LiteralPath (Join-Path $root $name) -Raw | ConvertFrom-Json)
}

# Pin local test support; it is separate from the unchanged real candidate.
$bundle = Get-Content -LiteralPath (Join-Path $here 'BUNDLE.json') -Raw | ConvertFrom-Json
foreach ($item in $bundle.materials) {
    $file = Get-Item -LiteralPath $item.path
    if ($file.Length -ne $item.bytes -or
        (Get-FileHash -LiteralPath $item.path -Algorithm SHA256).Hash.ToLower() -ne $item.sha256) {
        throw 'HOST_FIXTURE_MATERIAL_CHANGED'
    }
}
$root = Join-Path $temp ('AbqJobPilot_Run011_Host_'+[Guid]::NewGuid().ToString('N')+'\case_host')
if (Test-Path -LiteralPath $root) { throw 'NEW_FIXTURE_ROOT_REQUIRED' }
foreach ($part in @('','observations','engineering\scratch','extracted')) {
    $null = [IO.Directory]::CreateDirectory((Join-Path $root $part))
}
Write-Output ('HOST_FIXTURE_EVIDENCE='+$root)
$report = [ordered]@{schema='r011-host-compatibility-v1'; status='INCOMPLETE'; evidence_root=$root;
    context='ACTUAL_POWERSHELL_INVOCATION_NOT_ASSUMED_OPERATOR_DESKTOP';
    abaqus_calls=0; real_execute_calls=0; admission_changed=$false;
    started_at=[DateTime]::UtcNow.ToString('o'); powershell_version=$PSVersionTable.PSVersion.ToString();
    child_creation='ordinary Process.Start to registered venv, UseShellExecute=false, no breakaway';
    worker_creation='frozen run_once + fixed Python worker; CREATE_NO_WINDOW/close_fds/DEVNULL/regular files'}
$owned = @()
try {
    $shell = [Diagnostics.Process]::GetCurrentProcess()
    $operatorIdentity = Identity $shell
    $report.powershell = $operatorIdentity
    $launch = New-Object Diagnostics.Process
    $launch.StartInfo.FileName = $venv
    $launch.StartInfo.Arguments = '-B "'+(Join-Path $here 'fixture_controller.py')+'" "'+$root+'"'
    $launch.StartInfo.WorkingDirectory = $root
    $launch.StartInfo.UseShellExecute = $false
    $launch.StartInfo.CreateNoWindow = $true
    $launch.StartInfo.RedirectStandardOutput = $false
    $launch.StartInfo.RedirectStandardError = $false
    if (-not $launch.Start()) { throw 'CONTROLLER_CREATE_UNKNOWN' }
    $owned += @{role='controller_venv_launcher'; process=$launch; identity=$null}
    $launchId = Identity $launch
    $owned[-1].identity = $launchId
    Publish $root 'observer_context.json' @{powershell=$operatorIdentity; launcher=$launchId}
    $ready = Read-Published $root 'controller_ready.json'
    Assert-Identity $launchId $ready.chain.venv_launcher
    Assert-Identity $operatorIdentity $ready.chain.powershell
    $held = Hold-Verified $ready.chain.controller $base
    $controller = $held.process
    $controllerId = $held.identity
    $owned += @{role='actual_controller'; process=$controller; identity=$controllerId}
    $report.controller_host = $ready.host
    $report.controller_chain_OS_evidence = $ready.chain
    Publish $root 'controller_reference_held.json' @{source='PowerShell'; held=$true}
    $workerLaunch = Read-Published $root 'worker_launcher.json'
    $held = Hold-Verified $workerLaunch.identity $venv
    $wl = $held.process
    $wlId = $held.identity
    $owned += @{role='worker_venv_launcher'; process=$wl; identity=$wlId}
    # Original worker file is not an atomic handoff. Wait for a complete small JSON.
    $candidateBox = @{value=$null}
    Await {
        $p = Join-Path $root 'worker_ready.json'
        if (-not (Test-Path -LiteralPath $p)) { return $false }
        try { $candidateBox.value = Get-Content -LiteralPath $p -Raw | ConvertFrom-Json; return $true }
        catch { return $false }
    } 4 'WORKER_READY_UNAVAILABLE'
    $workerCandidate = $candidateBox.value
    $held = Hold-Verified $workerCandidate $base
    $worker = $held.process
    $workerId = $held.identity
    $owned += @{role='actual_worker'; process=$worker; identity=$workerId}
    $report.worker_candidate_self_report = $workerCandidate
    $report.worker_verified_OS_identity = $workerId
    Publish $root 'worker_references_held.json' @{worker=$workerId; venv_launcher=$wlId}
    $returned = Read-Published $root 'function_returned.json'
    $report.function_return = @{source=$returned.source; at_ns=$returned.observed_at_ns;
                               not_OS_exit_evidence=$true}
    if (-not $returned.report.deadline_reached -or $returned.report.PSObject.Properties['failure']) {
        throw 'CONTROLLER_OBSERVATION_DID_NOT_COMPLETE'
    }
    Await { $controller.WaitForExit(0) -and $launch.WaitForExit(0) } 8 'CONTROLLER_CHAIN_EXIT_UNCONFIRMED'
    $report.controller_exit = Observe $controller $controllerId
    $report.controller_venv_exit = Observe $launch $launchId
    if ($report.controller_exit.exit_code -ne 0 -or $report.controller_venv_exit.exit_code -ne 0) {
        throw 'CONTROLLER_CHAIN_NONZERO_EXIT'
    }
    $report.worker_after_entire_controller_chain_exit = Observe $worker $workerId
    if ($report.worker_after_entire_controller_chain_exit.exited) { throw 'WORKER_DID_NOT_SURVIVE_CHAIN_EXIT' }
    $heartbeat = Join-Path $root 'heartbeat.txt'
    $before = (Get-Item -LiteralPath $heartbeat).Length
    Await { (Get-Item -LiteralPath $heartbeat).Length -gt $before } 2 'NO_WRITES_AFTER_CHAIN_EXIT'
    $report.post_exit_growth = @{before_bytes=$before; after_bytes=(Get-Item -LiteralPath $heartbeat).Length;
        observed_at=[DateTime]::UtcNow.ToString('o'); source='file_growth_between_two_OS_liveness_observations'}
    $report.worker_after_growth = Observe $worker $workerId
    if ($report.worker_after_growth.exited) { throw 'WORKER_NOT_LIVE_AFTER_GROWTH' }
    # No release signal: existing worker reaches its own fixed ten-second deadline.
    Await { $worker.WaitForExit(0) -and $wl.WaitForExit(0) } 15 'WORKER_NATURAL_EXIT_UNCONFIRMED'
    $report.worker_exit = Observe $worker $workerId
    $report.worker_venv_exit = Observe $wl $wlId
    if ($report.worker_exit.exit_code -ne 0 -or $report.worker_venv_exit.exit_code -ne 0) {
        throw 'WORKER_NONZERO_EXIT'
    }
    $done = Get-Content -LiteralPath (Join-Path $root 'worker_done.json') -Raw | ConvertFrom-Json
    Assert-Identity $workerId $done.identity
    if (-not $done.natural_exit -or (Test-Path -LiteralPath (Join-Path $root 'release'))) {
        throw 'FIXTURE_SELF_COMPLETION_MISSING'
    }
    $report.worker_self_report = @{source='worker_file_not_OS_exit_proof'; content=$done}
    $report.status = 'PASS_OBSERVED_FIXED_PYTHON_CHAIN_ONLY'
} catch {
    $report.status = 'NOT_PASSED'
    $report.reason = $_.Exception.Message
} finally {
    $cleanup = @()
    # Bounded observation only; never kill on failure, and never release the worker early.
    $cleanupClock = [Diagnostics.Stopwatch]::StartNew()
    foreach ($entry in $owned) {
        try {
            if ($null -eq $entry.identity) { throw 'CREATED_PROCESS_IDENTITY_UNKNOWN' }
            while (-not $entry.process.WaitForExit(0) -and $cleanupClock.Elapsed.TotalSeconds -lt 18) {
                Start-Sleep -Milliseconds 20
            }
            $state = Observe $entry.process $entry.identity
            if (-not $state.exited) { $report.status='NOT_PASSED'; $report.cleanup_unknown=$true }
            $cleanup += @{role=$entry.role; observation=$state; action='observe_only_then_close_own_reference'}
        } catch { $report.status='NOT_PASSED'; $cleanup += @{role=$entry.role; error='EXIT_OBSERVATION_UNKNOWN'} }
        finally { $entry.process.Dispose() }
    }
    if (Get-Variable shell -ErrorAction SilentlyContinue) { $shell.Dispose() }
    $report.cleanup = $cleanup
    $report.finished_at = [DateTime]::UtcNow.ToString('o')
    $report.scope = 'Only this host invocation and fixed Python fixture; terminal/session remained alive; no full Job hierarchy or Abaqus proof'
    Publish $root 'HOST_REPORT.json' $report
}
$report | ConvertTo-Json -Depth 30
