#!/usr/bin/env bash
# Run the REAL scripts/build_paper.sh, but with AEP_PAPER_DIR pointed at a copy
# of paper/ so nothing is promoted into the tracked tree. The operator has not
# yet authorised promotion, and a clean build promotes automatically.
#
# This closes the residual left by phase8-driver/probe_texinputs.sh, which used
# kpsewhich rather than pdflatex actually opening the file.
#
# Sources are COPIED, never modified. paper/ itself is read-only here.
set -u

ROOT=/mnt/d/personal/AEP/Research-paper-AEP
WORK=/tmp/build-probe
MODE="${1:-clean}"      # clean | staleblb

rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$ROOT/paper" "$WORK/paper"

# The copy inherits whatever untracked artifacts paper/ currently has.
rm -f "$WORK/paper/main.aux" "$WORK/paper/main.bbl" "$WORK/paper/main.log"

if [ "$MODE" = "staleblb" ]; then
    # Reinstate a stale .bbl to test B21's mechanism against a real pdflatex
    # run rather than against kpsewhich. Deliberately missing the three keys
    # 07-related.tex cites.
    printf '\\begin{thebibliography}{1}\n\\bibitem{placeholder} Stale.\n\\end{thebibliography}\n' \
        > "$WORK/paper/main.bbl"
    echo "MODE: stale main.bbl planted in the copy's paper/ dir"
else
    echo "MODE: clean (no stale artifacts)"
fi

cd "$ROOT" || exit 1
echo "=== build_paper.sh with AEP_PAPER_DIR=$WORK/paper ==="
AEP_PAPER_DIR="$WORK/paper" bash scripts/build_paper.sh 2>&1 | tail -32
echo "exit=$?"

echo
echo "=== which main.bbl did pdflatex actually open? ==="
# The promoted log lands in AEP_PAPER_DIR on success; on failure look in scratch.
LOG=$(ls -t "$WORK/paper/main.log" "$ROOT"/.scratch/paper-build/*/main.log 2>/dev/null | head -1)
echo "log: $LOG"
grep -oE '\([^()]*main\.bbl' "$LOG" 2>/dev/null | head -3 || echo "  no main.bbl open recorded"
