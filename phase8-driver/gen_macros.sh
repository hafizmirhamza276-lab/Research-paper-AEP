#!/usr/bin/env bash
# Regenerate the paper's macro file into a scratch directory and report the
# capability-class macros.
#
# Writes to /mnt/d rather than /tmp: WSL clears /tmp when the distro idles out,
# which silently removed an earlier run's output between two commands.
#
# A script file rather than an inline `bash -c`, per B18.
set -u
REPO=/mnt/d/personal/AEP/Research-paper-AEP
OUT=/mnt/d/personal/AEP/macro-scratch

cd "$REPO" || exit 1
rm -rf "$OUT"
mkdir -p "$OUT"

python3 scripts/paper_tables.py \
    --analysis experiments/results/matrix/analysis \
    --fsync-analysis experiments/results/fsync-always/analysis \
    --flakey experiments/results \
    --out "$OUT" 2>&1 | tail -3

echo "--- total macros ---"
grep -c newcommand "$OUT/numbers.tex"
echo "--- capability-class macros ---"
grep 'newcommand{\\Class' "$OUT/numbers.tex"
echo "--- exit ---"
