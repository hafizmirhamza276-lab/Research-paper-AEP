#!/usr/bin/env bash
# Find every copy of the matrix run tree on this machine and report how complete
# each one is.
#
# Survey (a) established that SHA256SUMS names zero run directories, so nothing
# detects a partial copy. A copy holding a subset of matrix's 432 runs would
# verify exactly as well as a complete one -- there is no entry for the missing
# runs to fail against. This locates the copies so the claim can be checked
# rather than assumed.
#
# Read-only: find and stat only, no file opened, no ledger touched.
#
# Usage: find_matrix_copies.sh <search root> [<search root> ...]
set -u
for base in "$@"; do
    [ -d "$base" ] || continue
    find "$base" -type d -name matrix 2>/dev/null | while read -r d; do
        runs=$(find "$d" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | grep -vc '/analysis' || true)
        dbs=$(find "$d" -name 'ground_truth.sqlite3' 2>/dev/null | wc -l)
        [ "$dbs" -eq 0 ] && [ "$runs" -eq 0 ] && continue
        printf '%s\n  run dirs: %s   ledgers: %s\n' "$d" "$runs" "$dbs"
    done
done
