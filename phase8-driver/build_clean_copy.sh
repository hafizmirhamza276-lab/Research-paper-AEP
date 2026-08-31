#!/usr/bin/env bash
# Build the CURRENT (edited) paper/ from a copy that excludes the untracked,
# stale build artifacts, so the comparison against the HEAD control is
# symmetric.
#
# Why this exists. scripts/build_paper.sh compiles in a scratch directory
# specifically to avoid disturbing the last-known-good output, but it then sets
#
#     TEXINPUTS="${PAPER}//"
#
# which makes kpathsea search paper/ recursively for EVERY file the run needs,
# including main.aux and main.bbl. Those two are untracked and, on this host,
# three weeks old. pdflatex finds the stale main.bbl before the one bibtex just
# wrote in the scratch directory, and the stale one predates three \cite keys
# that 07-related.tex now uses -- so the build reports undefined citations that
# have nothing to do with the sources being compiled.
#
# `git archive HEAD paper` silently drops untracked files, which is why the
# HEAD control passed and the edited tree did not. That difference was the
# artifacts, not the edits. This script removes the asymmetry.
#
# A script file rather than an inline `wsl bash -lc`, per B18.
set -u
R=/mnt/d/personal/AEP/Research-paper-AEP
DEST=/tmp/editpaper

rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$R/paper" "$DEST/paper" || exit 1

echo "=== removing untracked build artifacts from the copy ==="
for f in main.aux main.bbl main.blg main.log main.out; do
    if [ -e "$DEST/paper/$f" ]; then
        echo "  removed $f"
        rm -f "$DEST/paper/$f"
    fi
done

cd "$R" || exit 1
AEP_PAPER_DIR="$DEST/paper" bash scripts/build_paper.sh 2>&1 | tail -18
