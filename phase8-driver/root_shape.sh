#!/usr/bin/env bash
# What shape is each results root: does it hold raw run directories and ledgers,
# or only derived analysis products?
#
# Written because survey (a) found five roots -- including `matrix` and
# `b2-2026-08-21`, whose numbers are in the manuscript -- with zero ledgers, and
# "zero ledgers" has two very different meanings: the runs are here and their
# databases are missing, or the runs were never here at all.
#
# Read-only: find and stat only, no file opened.
#
# Usage: root_shape.sh <results dir>
set -u
RESULTS="${1:?usage: root_shape.sh <results dir>}"

printf '%-46s %8s %8s %8s %8s\n' root files rundirs sqlite summaries
printf '%.0s-' {1..82}; echo
for R in "$RESULTS"/*/; do
    R="${R%/}"
    name=$(basename "$R")
    files=$(find "$R" -type f 2>/dev/null | wc -l)
    rundirs=$(find "$R" -mindepth 1 -maxdepth 1 -type d ! -name analysis 2>/dev/null | wc -l)
    sqlite=$(find "$R" -name 'ground_truth.sqlite3' 2>/dev/null | wc -l)
    summaries=$(find "$R" -name 'summary.json' 2>/dev/null | wc -l)
    printf '%-46s %8s %8s %8s %8s\n' "$name" "$files" "$rundirs" "$sqlite" "$summaries"
done
