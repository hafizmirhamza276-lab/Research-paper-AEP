#!/usr/bin/env bash
# Print the .sqlite3 / -wal / -shm sizes of the first N ledgers under a tree, as
# a concrete illustration of the bare-page-plus-WAL shape that survey (a) found
# holds universally.
#
# A script file rather than an inline `bash -c`, per B18: variable references in
# an inline guest command are expanded by the outer shell before they arrive.
#
# Read-only: stat only, no ledger opened.
#
# Usage: ledger_sample.sh <tree> [count]
set -u
TREE="${1:?usage: ledger_sample.sh <tree> [count]}"
N="${2:-1}"

find "$TREE" -name 'ground_truth.sqlite3' 2>/dev/null | sort | head -"$N" | while read -r f; do
    run=$(basename "$(dirname "$f")")
    printf 'run: %s\n' "$run"
    printf '  %-22s %10s B\n' 'ground_truth.sqlite3' "$(stat -c %s "$f")"
    [ -f "$f-wal" ] && printf '  %-22s %10s B\n' 'ground_truth.sqlite3-wal' "$(stat -c %s "$f-wal")"
    [ -f "$f-shm" ] && printf '  %-22s %10s B\n' 'ground_truth.sqlite3-shm' "$(stat -c %s "$f-shm")"
done
