#!/usr/bin/env bash
# B21 item 2 -- establishing, not fixing.
#
# build_paper.sh:79 exports TEXINPUTS="${PAPER}//:", so paper/main.bbl and the
# scratch main.bbl are both resolvable. Which does pdflatex open, and on which
# pass? The earlier attempt read the newest surviving log after the build and
# got a 31 August leftover, because build_paper.sh removes its scratch dir on
# exit. This one inspects the log AFTER EACH PASS, inside the scratch dir, while
# it still exists -- surviving cleanup by construction rather than by luck.
#
# It replicates build_paper.sh's four steps rather than calling it, precisely so
# the intermediate state is observable. Read-only with respect to the repo:
# everything happens in /tmp on a COPY of paper/.
set -u

ROOT=/mnt/d/personal/AEP/Research-paper-AEP
WORK=/tmp/bbl-identity
PAPER="$WORK/paper"
BUILD="$WORK/scratch"

rm -rf "$WORK"; mkdir -p "$PAPER" "$BUILD"
cp -r "$ROOT/paper/." "$PAPER/"

# Make paper/main.bbl unmistakable: a valid bibliography that also carries a
# marker key nothing cites. If the marker reaches the output, paper/ won.
if [ -f "$PAPER/main.bbl" ]; then
    sed 's/\\begin{thebibliography}{\(.*\)}/\\begin{thebibliography}{\1}\n\\bibitem{PAPERDIRMARKER} MARKER FROM PAPER DIR./' \
        "$PAPER/main.bbl" > "$PAPER/main.bbl.new" && mv "$PAPER/main.bbl.new" "$PAPER/main.bbl"
    echo "marker planted in $PAPER/main.bbl"
else
    echo "NOTE: no paper/main.bbl to mark"
fi

export TEXINPUTS="${PAPER}//:"
export BIBINPUTS="${PAPER}:"
cd "$BUILD" || exit 1

report() {
    printf '  %-22s ' "$1"
    if [ ! -f main.log ]; then echo "(no log)"; return; fi
    hits=$(grep -oE '\([^() ]*main\.bbl' main.log | sort -u | tr '\n' ' ')
    [ -n "$hits" ] && echo "opened: $hits" || echo "opened: (no main.bbl open)"
}

echo
echo "=== pass 1 (no scratch main.bbl exists yet) ==="
pdflatex -interaction=nonstopmode -halt-on-error -jobname=main main.tex >/dev/null 2>&1
report "after pass 1"
ls -la main.bbl 2>/dev/null | awk '{print "  scratch main.bbl: "$5" bytes"}' || echo "  scratch main.bbl: absent"

echo
echo "=== bibtex (writes scratch main.bbl) ==="
bibtex main >/dev/null 2>&1
ls -la main.bbl 2>/dev/null | awk '{print "  scratch main.bbl: "$5" bytes"}'
grep -c PAPERDIRMARKER main.bbl 2>/dev/null | sed 's/^/  marker in scratch bbl: /'

echo
echo "=== pass 2 ==="
pdflatex -interaction=nonstopmode -halt-on-error -jobname=main main.tex >/dev/null 2>&1
report "after pass 2"

echo
echo "=== pass 3 ==="
pdflatex -interaction=nonstopmode -halt-on-error -jobname=main main.tex >/dev/null 2>&1
report "after pass 3"

echo
echo "=== did the paper-dir marker reach the output? ==="
if command -v pdftotext >/dev/null 2>&1; then
    pdftotext main.pdf - 2>/dev/null | grep -c "MARKER FROM PAPER DIR" \
        | sed 's/^/  occurrences in PDF text: /'
else
    grep -ac "PAPERDIRMARKER" main.aux | sed 's/^/  \\bibcite for marker in main.aux: /'
fi

echo
echo "=== undefined citations in the final log ==="
grep -c "Citation.*undefined" main.log 2>/dev/null | sed 's/^/  count: /'

cd /; rm -rf "$WORK"
