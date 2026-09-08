<#
.SYNOPSIS
    Hold the WSL distro open for the duration of a long collection.

.DESCRIPTION
    WSL2 shuts an idle distro down and takes every process in it with it. That
    is what killed the 2026-09-08 B5 primary at run 39 of 120, and -- per its
    own comment -- the Phase 8.4 session 2 attempt at run 25 before that.

    **`.wslconfig`'s `vmIdleTimeout=-1` does not prevent it.** The key is not
    honoured by WSL 2.7.3.0; it is accepted silently and has no effect. Measured
    on 2026-09-08: after a clean `wsl --shutdown` to apply it, the distro still
    stopped within 100 s of the last client detaching. A setting that looks like
    a fix and is not one is worse than no setting, which is why this script
    exists and why that comment in `.wslconfig` should not be trusted.

    What does work is an attached client. While any `wsl.exe` session is live
    the VM stays up, so this holds one open and does nothing else.

    **It must be started from outside the agent session that launches the
    collection.** A keepalive that dies with its parent is not a keepalive; that
    is the same failure it is meant to prevent, one level up.

.PARAMETER Action
    start | stop | status

.EXAMPLE
    powershell -File scripts/wsl_keepalive.ps1 -Action start
    # ... launch the collection, detached ...
    powershell -File scripts/wsl_keepalive.ps1 -Action stop
#>
param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "status",
    [string]$Distro = "Ubuntu-24.04",
    [string]$PidFile = "$env:TEMP\aep-wsl-keepalive.pid"
)

function Get-KeepalivePid {
    if (-not (Test-Path $PidFile)) { return $null }
    $recorded = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $recorded) { return $null }
    $process = Get-Process -Id $recorded -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    return [int]$recorded
}

function Get-DistroState {
    # -l -v pads with NULs; strip them or every comparison fails.
    $lines = (wsl.exe -l -v) -replace "`0", ""
    foreach ($line in $lines) {
        if ($line -match "^\s*\*?\s*$([regex]::Escape($Distro))\s+(\S+)") {
            return $Matches[1]
        }
    }
    return "ABSENT"
}

switch ($Action) {
    "start" {
        $existing = Get-KeepalivePid
        if ($existing) {
            Write-Output "already running, pid $existing"
            break
        }
        # R1: the PID is recorded at start and is the only handle used to stop
        # it. Nothing here is ever killed by pattern.
        $process = Start-Process -FilePath "wsl.exe" `
            -ArgumentList "-d", $Distro, "-u", "root", "--", "sleep", "infinity" `
            -WindowStyle Hidden -PassThru
        $process.Id | Out-File -FilePath $PidFile -Encoding ascii
        Start-Sleep -Seconds 3
        Write-Output "started, pid $($process.Id)  (recorded in $PidFile)"
        Write-Output "distro $Distro is $(Get-DistroState)"
    }
    "stop" {
        $recorded = Get-KeepalivePid
        if (-not $recorded) {
            Write-Output "not running (no live process for $PidFile)"
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            break
        }
        Stop-Process -Id $recorded -Force
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Output "stopped pid $recorded"
    }
    "status" {
        $recorded = Get-KeepalivePid
        if ($recorded) {
            Write-Output "keepalive RUNNING, pid $recorded"
        } else {
            Write-Output "keepalive NOT running"
        }
        Write-Output "distro $Distro is $(Get-DistroState)"
    }
}
