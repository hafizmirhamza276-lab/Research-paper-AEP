# Verify the B31a guard actually holds ON THIS TREE, not only in the scratch
# repos where it was established.
#
# WHY A PROBE AND NOT A DIRECT TEST. `git clean -nxd` still lists all 402
# entries after the guard is applied, because the ACL changes git's ABILITY,
# not its INTENT. A dry run therefore cannot distinguish "guarded" from
# "unguarded" -- it is a fail-open check for this purpose.
#
# The obvious real test -- attempt to delete a run directory and see it fail --
# is unacceptable: if the guard does not hold, the test destroys 60 runs that
# exist nowhere else. So the probe is a directory this script creates itself.
# BLAST RADIUS IF THE GUARD FAILS: one empty probe directory. Zero evidence.
#
# The probe inherits the root's deny, so removing it requires disabling
# inheritance on the probe and dropping the ACE -- done here, and verified.

$ErrorActionPreference = 'Continue'

$root  = 'D:\personal\AEP\Research-paper-AEP\experiments\results\b2-2026-08-21'
$probe = Join-Path $root '_guard_probe'
$sid   = ([Security.Principal.WindowsIdentity]::GetCurrent()).User.Value

# --- create -------------------------------------------------------------
New-Item -ItemType Directory -Path $probe -Force | Out-Null
Set-Content -LiteralPath (Join-Path $probe 'canary.txt') -Value 'probe'
Write-Output "created: $probe"

# --- attempt deletion: this MUST fail ------------------------------------
$blocked = $false
try {
    Remove-Item -LiteralPath $probe -Recurse -Force -ErrorAction Stop
} catch {
    $blocked = $true
}

if (Test-Path -LiteralPath $probe) {
    Write-Output 'RESULT: GUARD HOLDS -- deletion was refused, probe survived'
} else {
    Write-Output 'RESULT: *** GUARD DOES NOT HOLD *** -- probe was deleted'
    exit 1
}

# --- clean up the probe --------------------------------------------------
# The deny is inherited from the root. Convert to explicit, drop it, remove.
icacls $probe /inheritance:d | Out-Null
icacls $probe /remove:d "*$sid" /T | Out-Null
Remove-Item -LiteralPath $probe -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $probe) {
    Write-Output 'CLEANUP: FAILED -- probe still present, remove by hand'
    exit 2
}
Write-Output 'CLEANUP: probe removed, root left as found'
