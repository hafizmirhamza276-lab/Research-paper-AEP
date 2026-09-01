#!/usr/bin/env bash
# READ-ONLY. Did the sudo password reach any shell history file?
#
# The survey was run as `echo <pw> | sudo -S bash <script>` from Git Bash via
# `wsl --`. Three places could plausibly retain that string: the Git Bash
# history on the Windows side, the WSL user's history, and root's history.
#
# Bash only appends to HISTFILE when the shell is INTERACTIVE. Every shell in
# that pipeline was non-interactive. This script tests that claim rather than
# relying on it -- the whole point of a fail-closed survey is not to assert an
# absence it has not checked.
#
# A script file rather than an inline `wsl bash -lc`, per B18: the inline form
# lost `~` and `$f` through two levels of quoting and printed "ABSENT " with an
# empty path, which is a fail-open answer -- it looked like a clean result.
#
# grep -c only. Nothing written, no ledger touched.
set -u

# FAIL-CLOSED, and the first version of this function was not -- written
# directly below a header block asserting that a survey must not claim an
# absence it has not checked. Run unprivileged it printed
# "ABSENT: /root/.bash_history", because `[ ! -e ]` is true for a path whose
# PARENT is 0700. Same defect, same session, same author, one function below
# the comment forbidding it. Three outcomes now, and UNREADABLE is not ABSENT.
incomplete=0

check() {
    f="$1"
    d=$(dirname "$f")
    if [ -e "$d" ] && [ ! -r "$d" ]; then
        echo "  UNREADABLE: $f (parent $d denied) -- re-run with sudo"
        incomplete=1
        return
    fi
    if [ ! -e "$f" ]; then
        echo "  ABSENT (verified: parent $d readable): $f"
        return
    fi
    n=$(wc -l < "$f" 2>/dev/null)
    # Match the invocation shape, not the secret: searching for the password
    # itself would mean writing it into another file.
    hits=$(grep -c -- 'sudo -S' "$f" 2>/dev/null || true)
    mtime=$(stat -c '%y' "$f" 2>/dev/null)
    echo "  EXISTS: $f"
    echo "    lines=$n  'sudo -S' hits=$hits"
    echo "    mtime=$mtime"
}

echo "=== WSL user history ==="
check "/home/hamzakhan/.bash_history"

echo "=== root history ==="
check "/root/.bash_history"

echo "=== any root shell rc history settings ==="
if [ -r /root/.bashrc ]; then
    grep -n 'HISTFILE\|HISTSIZE' /root/.bashrc 2>/dev/null || echo "  (no HISTFILE/HISTSIZE lines)"
else
    echo "  UNREADABLE: /root/.bashrc -- re-run with sudo"
    incomplete=1
fi

echo
echo "running as: $(id -un)"
if [ "$incomplete" -ne 0 ]; then
    echo "INCOMPLETE: this run did NOT establish that the unreadable paths are absent."
    exit 2
fi
echo "COMPLETE: every path above was readable or verified absent."
