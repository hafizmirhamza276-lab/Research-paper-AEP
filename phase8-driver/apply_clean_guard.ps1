# Interim guard for B31 / B31a.
#
# The four b2-*-2026-08-21 result roots hold 240 run directories that exist
# NOWHERE ELSE (privileged custody survey, 1 Sep: /root/aep-phase8 holds 0 of
# them). They are gitignored, so `git status` reports nothing and
# `git clean -xdf` deletes them silently.
#
# This applies an INHERITABLE DENY of DELETE to each root for the current user.
# It does NOT touch .gitignore: no raw run enters the index, no WAL is
# versioned, the allow-list is unchanged. Loosening .gitignore would have been
# the harmful "fix" (B31).
#
# Established by test, not by documentation (B31a): a deny of DC
# (delete-child) on the root does NOT work, because children still grant DELETE
# by inheritance. The inheritable deny of DELETE itself does.
#
# REVERSAL -- the whole point of recording it here:
#   pwsh/powershell -File apply_clean_guard.ps1 -Remove
# or by hand, per root:
#   icacls "<root>" /remove:d "*<SID>"
#
# Stops accident, not intent. Anyone can remove the ACE; that is the correct
# threat model, since B31 is about a routine command run for an unrelated
# reason.
#
# A script file rather than an inline command, per B18: the inline form lost
# its backslashes through two levels of quoting and silently targeted a
# non-existent path.

param([switch]$Remove, [switch]$Show)

$ErrorActionPreference = 'Stop'

$base = 'D:\personal\AEP\Research-paper-AEP\experiments\results'
$roots = @(
    'b2-2026-08-21',
    'b2-s1-2026-08-21',
    'b2-s2-2026-08-21',
    'b2-s3-2026-08-21'
)

$sid = ([Security.Principal.WindowsIdentity]::GetCurrent()).User.Value
Write-Output "SID: $sid"

foreach ($r in $roots) {
    $p = Join-Path $base $r
    if (-not (Test-Path -LiteralPath $p)) {
        # Fail closed: a missing root is not a no-op, it is a survey failure.
        Write-Output "MISSING: $p  -- NOT a no-op; investigate before proceeding"
        continue
    }
    if ($Show) {
        Write-Output "=== $r ==="
        icacls $p
    } elseif ($Remove) {
        Write-Output "=== REMOVING deny on $r ==="
        icacls $p /remove:d "*$sid" /T | Select-Object -Last 1
    } else {
        Write-Output "=== APPLYING deny on $r ==="
        icacls $p /deny "*${sid}:(OI)(CI)(DE)" | Select-Object -Last 1
    }
}
