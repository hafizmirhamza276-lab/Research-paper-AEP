#!/usr/bin/env bash
# Is B21's mechanism live? build_paper.sh:79 sets
#   export TEXINPUTS="${PAPER}//:${TEXINPUTS:-}"
# and B21 says that lets pdflatex, running in the scratch directory, resolve
# paper/main.bbl (untracked, 10 August) instead of the one bibtex just wrote.
#
# But ARTIFACT.md's 31 August note reports a build that was clean on citations,
# which the stale .bbl should have broken. Those two cannot both be right about
# the same conditions, so this resolves which.
#
# READ-ONLY. Resolves paths with kpsewhich; compiles nothing, promotes nothing,
# writes only under /tmp.
#
# A script file rather than an inline `wsl bash -lc`, per B18 -- the inline form
# lost "$f" through two levels of quoting and printed four empty filenames,
# which looked like four failed lookups rather than a broken probe.
set -u

PAPERDIR=/mnt/d/personal/AEP/Research-paper-AEP/paper
WORK=/tmp/texinputs-probe
rm -rf "$WORK"; mkdir -p "$WORK"
cd "$WORK" || exit 1

export TEXINPUTS="${PAPERDIR}//:"

echo "TEXINPUTS=$TEXINPUTS"
echo
echo "=== does recursive TEXINPUTS reach paper/ at all? ==="
for f in main.tex refs.bib sections/07-related.tex; do
    printf '  %-26s -> %s\n' "$f" "$(kpsewhich -format=tex "$f" 2>&1)"
done

echo
echo "=== the file under test: main.bbl ==="
printf '  %-26s -> %s\n' "main.bbl (no local copy)" "$(kpsewhich -format=tex main.bbl 2>&1)"

printf 'SCRATCH-COPY\n' > main.bbl
printf '  %-26s -> %s\n' "main.bbl (local copy present)" "$(kpsewhich -format=tex main.bbl 2>&1)"

echo
echo "=== which one would TeX actually open? ==="
# TeX resolves an \input relative to the CWD before consulting TEXINPUTS, so
# the question is whether a scratch-local main.bbl shadows paper/main.bbl.
first=$(kpsewhich -format=tex main.bbl 2>&1)
case "$first" in
    "$WORK"/*) echo "  SCRATCH WINS -- B21's mechanism does NOT fire when bibtex has written a .bbl" ;;
    "$PAPERDIR"/*) echo "  PAPER WINS -- B21's mechanism IS live; the stale .bbl shadows the fresh one" ;;
    *) echo "  UNRESOLVED: [$first]" ;;
esac

cd /; rm -rf "$WORK"
