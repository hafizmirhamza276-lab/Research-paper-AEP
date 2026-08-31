#!/usr/bin/env bash
# Regenerate paper/generated/ IN PLACE, from WSL.
#
# gen_macros.sh writes to a scratch directory, which is right for inspecting
# the macro set and wrong for committing it. Running the same generator from
# Windows Python instead rewrites every generated file with CRLF endings and
# produces a 700-line diff in which the six real changed values are invisible.
# So the in-place regeneration has to happen on the same side as the files.
#
# A script file rather than an inline `wsl bash -lc`, per B18.
set -u
R=/mnt/d/personal/AEP/Research-paper-AEP
cd "$R" || exit 1

python3 scripts/paper_tables.py \
    --analysis experiments/results/matrix/analysis \
    --fsync-analysis experiments/results/fsync-always/analysis \
    --flakey experiments/results \
    --out paper/generated 2>&1 | tail -3

echo "--- total macros ---"
grep -c newcommand paper/generated/numbers.tex
