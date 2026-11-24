#!/usr/bin/env bash
# Which directories in a results root have no ground_truth.sqlite3?
#
# root_shape.sh found matrix holding 433 directories but 432 ledgers and 432
# summaries, while ARTIFACT.md describes 432 raw run directories. One directory
# is therefore not a run, or is a run missing its ledger, and those are very
# different facts about the tree the manuscript rests on.
#
# Read-only: listing and existence tests only, no file opened.
#
# Usage: dirs_without_ledgers.sh <results root>
set -u
R="${1:?usage: dirs_without_ledgers.sh <results root>}"

cd "$R" || exit 1
for d in */; do
    d="${d%/}"
    if [ ! -f "$d/ground_truth.sqlite3" ]; then
        printf 'NO LEDGER: %s\n' "$d"
        printf '  contents: '
        ls -1 "$d" 2>/dev/null | head -6 | tr '\n' ' '
        printf '\n  file count: %s\n' "$(find "$d" -type f 2>/dev/null | wc -l)"
    fi
done
