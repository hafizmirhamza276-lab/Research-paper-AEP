#!/usr/bin/env bash
# READ-ONLY. The custody survey reported matrix at runs=433 but db=wal=shm=432.
# The triple check passed because the three ledger files agree with each other;
# what it cannot see is a run DIRECTORY with no ledger at all. Identify it.
#
# find and ls only. No ledger opened, nothing written.
# A script file rather than an inline `wsl bash -lc`, per B18 -- the inline form
# lost its quoting and reported a spurious "No such file or directory".
set -u
base=/root/aep/experiments/results/matrix
for d in "$base"/*/; do
    name=$(basename "$d")
    [ "$name" = analysis ] && continue
    [ "$name" = voided ] && continue
    n=$(find "$d" -maxdepth 1 -name '*.sqlite3' -type f 2>/dev/null | wc -l)
    if [ "$n" -eq 0 ]; then
        echo "NO LEDGER: $name"
        ls -la "$d" | head -20
    fi
done
echo "--- done ---"
