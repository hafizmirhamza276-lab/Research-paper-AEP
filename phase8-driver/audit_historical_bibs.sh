#!/usr/bin/env bash
# Did the three PDFs promoted inside the defect window ship a bibliography
# inconsistent with their OWN sources?
#
# Window opens at c2fffa6 (2026-08-12), which introduced the scratch build and
# the recursive TEXINPUTS. main.pdf was tracked at c2fffa6, 83cccdc and
# 97c44ff, so those PDFs are recoverable from git even though their .bbl inputs
# are not.
#
# METHOD, per commit: export the tracked tree, extract the SHIPPED PDF's
# bibliography, then rebuild from that same commit's sources with the CORRECTED
# search path and extract the bibliography that build produces. Compare.
#
# build_paper.sh is deliberately NOT used: at these commits its gate would fail
# for unrelated reasons (pydantic), and a failed gate promotes no PDF. pdflatex
# and bibtex are driven directly, so the comparison does not depend on any gate.
#
# WHAT A MATCH PROVES, AND WHAT IT DOES NOT. Agreement means that build's stale
# paper/main.bbl happened to hold the right content -- because refs.bib had not
# changed in a way that mattered since whichever earlier build wrote it. IT DOES
# NOT MEAN THE PIPELINE WORKED. The wrong file was still opened; it just held
# the right bytes.
set -u

ROOT=/mnt/d/personal/AEP/Research-paper-AEP
WORK=/tmp/histbib
COMMITS="c2fffa6 83cccdc 97c44ff"

rm -rf "$WORK"; mkdir -p "$WORK"
command -v pdftotext >/dev/null 2>&1 || { echo "pdftotext missing"; exit 1; }

# The rewritten extractor: raw reading order (the paper is two-column, so
# -layout interleaves body text with references), entries split on bracketed
# numbers, aborting on empty is handled by the caller.
extract() {
    pdftotext "$1" - 2>/dev/null \
        | tr '\n' ' ' \
        | sed 's/\(\[[0-9]\{1,\}\]\)/\n\1/g' \
        | grep -E '^\[[0-9]+\] [A-Z]' \
        | sed 's/[[:space:]]\+/ /g; s/ $//' \
        | sort -u
}

rc=0
for C in $COMMITS; do
    echo "================ $C ================"
    T="$WORK/$C"
    mkdir -p "$T"
    ( cd "$ROOT" && git archive "$C" paper ) | tar -x -C "$T" 2>/dev/null

    if [ ! -f "$T/paper/main.pdf" ]; then
        echo "  no tracked main.pdf at this commit -- skipping"
        continue
    fi
    date=$( cd "$ROOT" && git log -1 --format=%ad --date=short "$C" )
    echo "  date: $date   refs.bib: $(grep -c '^@' "$T/paper/refs.bib" 2>/dev/null) entries"

    extract "$T/paper/main.pdf" > "$T/shipped.txt"

    # Rebuild from the same sources with the CORRECTED path (dot first).
    B="$T/build"; mkdir -p "$B"
    ( cd "$B" \
      && TEXINPUTS=".:$T/paper//:" BIBINPUTS="$T/paper:" \
         pdflatex -interaction=nonstopmode -jobname=main main.tex >/dev/null 2>&1
      cd "$B" && BIBINPUTS="$T/paper:" bibtex main >/dev/null 2>&1
      cd "$B" && TEXINPUTS=".:$T/paper//:" BIBINPUTS="$T/paper:" \
         pdflatex -interaction=nonstopmode -jobname=main main.tex >/dev/null 2>&1
      cd "$B" && TEXINPUTS=".:$T/paper//:" BIBINPUTS="$T/paper:" \
         pdflatex -interaction=nonstopmode -jobname=main main.tex >/dev/null 2>&1 )

    if [ ! -f "$B/main.pdf" ]; then
        echo "  REBUILD FAILED -- cannot compare this commit"
        rc=1
        continue
    fi
    echo "  rebuilt opened: $(grep -oE '\([^() ]*main\.bbl' "$B/main.log" | sort -u | tr '\n' ' ')"
    extract "$B/main.pdf" > "$T/rebuilt.txt"

    s=$(wc -l < "$T/shipped.txt"); r=$(wc -l < "$T/rebuilt.txt")
    echo "  shipped entries: $s   rebuilt entries: $r"
    if [ "$s" -eq 0 ] || [ "$r" -eq 0 ]; then
        echo "  ABORT: empty extraction -- refusing to report agreement"
        rc=1
        continue
    fi
    if diff -q "$T/shipped.txt" "$T/rebuilt.txt" >/dev/null; then
        echo "  RESULT: MATCH -- shipped bibliography is consistent with its own sources"
    else
        echo "  RESULT: *** DIFFERS ***"
        diff "$T/shipped.txt" "$T/rebuilt.txt" | head -20 | sed 's/^/      /'
        rc=1
    fi
done

echo
echo "================================================"
[ "$rc" -eq 0 ] && echo "All comparable commits MATCH." || echo "At least one commit differs or could not be compared."
exit "$rc"
