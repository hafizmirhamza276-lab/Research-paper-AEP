#!/usr/bin/env bash
# Where on this host do ground_truth.sqlite3 ledgers actually live?
#
# Survey (a) found that six result roots on the collection host -- including
# `matrix` and `b2-2026-08-21`, whose numbers are in the manuscript -- hold only
# derived products and zero run directories. That has two very different
# readings, and this settles which: the raw runs are elsewhere on the host, or
# they are not on the host at all.
#
# Read-only: find only, no file opened.
#
# Usage: locate_ledgers.sh
set -u
find /root -name ground_truth.sqlite3 2>/dev/null \
  | sed 's|/[^/]*/ground_truth\.sqlite3$||' \
  | sed 's|/[^/]*$||' \
  | sort | uniq -c | sort -rn
