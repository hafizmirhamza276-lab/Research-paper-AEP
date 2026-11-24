#!/usr/bin/env bash
# Task 1(b): copy a complete frozen root -- all 120 run directories, every
# ledger, every log -- off the WSL ext4 VHDX.
#
# Why this exists: the commit tracks analysis products only, and SHA256SUMS
# attests only those (B15). Nothing in the repository attests the evidence the
# analysis was derived from. This produces the manifest B15 says is missing, over
# EVERY file in the root, and puts a copy on a different filesystem.
#
# Ledger handling, non-negotiable:
#   * No sqlite file is opened, by any tool, for reading or writing.
#   * No WAL is checkpointed. ground_truth.sqlite3 is a bare page in these roots
#     and the data lives in an uncheckpointed -wal; a checkpoint-on-open would
#     rewrite the ledger, and copying only *.sqlite3 would publish empty pages.
#   * The triple (.sqlite3, -wal, -shm) travels together inside the tar.
# -wal/-shm mtimes are recorded before and after as the proof of the first two.
#
# Nothing is written into the source root. The manifest lands beside the tarball.
#
# Usage: raw_archive.sh <slug>
set -uo pipefail

SLUG="${1:?usage: raw_archive.sh <slug>}"
SRC="/root/aep-phase8/experiments/results/${SLUG}"
OUT="/mnt/d/personal/AEP/phase8-raw-archive"
TAR="${OUT}/${SLUG}.tar.gz"
MAN="${OUT}/${SLUG}.FULL-SHA256SUMS"
STAMP="${OUT}/${SLUG}.ledger-mtimes"

[ -d "$SRC" ] || { echo "no such root: $SRC"; exit 1; }
mkdir -p "$OUT"

cd "$SRC" || exit 1

echo "=== ledger mtimes BEFORE (stat only; no ledger opened) ==="
find . -name 'ground_truth.sqlite3*' -printf '%T@ %s %p\n' | sort > "${STAMP}.before"
wc -l < "${STAMP}.before"

echo "=== full manifest over every file in the root ==="
find . -type f | sed 's|^\./||' | sort > /tmp/${SLUG}.filelist
echo "files in root: $(wc -l < /tmp/${SLUG}.filelist)"
xargs -a /tmp/${SLUG}.filelist -d '\n' sha256sum > "$MAN"
echo "manifest entries: $(wc -l < "$MAN")"

echo "=== ledger inventory ==="
echo "  .sqlite3 : $(grep -c 'ground_truth\.sqlite3$' "$MAN")"
echo "  -wal     : $(grep -c 'ground_truth\.sqlite3-wal$' "$MAN")"
echo "  -shm     : $(grep -c 'ground_truth\.sqlite3-shm$' "$MAN")"
echo "  run dirs : $(find . -maxdepth 1 -type d ! -name . ! -name analysis | wc -l)"

echo "=== tar (no checkpoint, triple travels together) ==="
tar -czf "$TAR" -C /root/aep-phase8/experiments/results "$SLUG" || exit 1
echo "tarball bytes: $(stat -c %s "$TAR")"
echo "tar entries  : $(tar -tzf "$TAR" | wc -l)"
echo "tar sqlite triples: $(tar -tzf "$TAR" | grep -c 'ground_truth\.sqlite3')"

echo "=== ledger mtimes AFTER ==="
find . -name 'ground_truth.sqlite3*' -printf '%T@ %s %p\n' | sort > "${STAMP}.after"
if diff -q "${STAMP}.before" "${STAMP}.after" > /dev/null; then
    echo "UNCHANGED: no ledger mtime or size moved; nothing was opened or checkpointed"
else
    echo "HALT: a ledger changed during archiving"
    diff "${STAMP}.before" "${STAMP}.after" | head -20
    exit 2
fi

echo "=== verify by extracting to scratch and re-checking the full manifest ==="
rm -rf "/tmp/verify-${SLUG}"
mkdir -p "/tmp/verify-${SLUG}"
tar -xzf "$TAR" -C "/tmp/verify-${SLUG}" || exit 1
( cd "/tmp/verify-${SLUG}/${SLUG}" && sha256sum -c "$MAN" 2>&1 | grep -cv ': OK$' | xargs -I{} echo "non-OK lines: {}" )
( cd "/tmp/verify-${SLUG}/${SLUG}" && sha256sum -c --quiet "$MAN" )
RC=$?
echo "EXTRACT VERIFY EXIT=$RC"
rm -rf "/tmp/verify-${SLUG}"

echo "=== digest of the archive itself ==="
sha256sum "$TAR" | tee "${TAR}.sha256"
sha256sum "$MAN"

exit $RC
