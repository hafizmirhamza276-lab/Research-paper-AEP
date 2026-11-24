#!/usr/bin/env bash
# B41: what did the defect actually change?
#
# The tracked paper/main.pdf was promoted 2026-09-01 from a build that passed
# all 18 checks -- but under the pre-fix TEXINPUTS its bibliography came from
# the PREVIOUS build's paper/main.bbl, so the gate's pass did not cover what
# shipped. This builds once WITH the fix and diffs the two bibliographies.
#
# Promotes nothing: the build runs with AEP_PAPER_DIR pointed at a copy. The
# tracked PDF is read, never written.
set -u

ROOT=/mnt/d/personal/AEP/Research-paper-AEP
WORK=/tmp/bibcompare
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$ROOT/paper" "$WORK/paper"

command -v pdftotext >/dev/null 2>&1 || { echo "pdftotext missing"; exit 1; }

cd "$ROOT" || exit 1
echo "=== build WITH the fix, into a copy ==="
AEP_PAPER_DIR="$WORK/paper" bash scripts/build_paper.sh 2>&1 | tail -3

echo
echo "=== which main.bbl did the fixed build open? ==="
grep -oE '\([^() ]*main\.bbl' "$WORK/paper/main.log" | sort -u | sed 's/^/  /'

# Extract the reference list from each PDF. IEEEtran renders it under
# "REFERENCES"; take everything from that heading to the end.
# Extract the reference list. NOT -layout: the paper is two-column, so -layout
# interleaves body text with references on the same line and the entries cannot
# be isolated. Raw reading order keeps each entry contiguous.
#
# The first version of this function anchored on a "REFERENCES" heading and
# returned ZERO lines from both PDFs -- then reported them IDENTICAL. A
# comparison that compares nothing and calls it agreement is the same shape as
# B33's over-reporting search, in the reporting direction that matters most
# here: it would have cleared the shipped PDF without looking at it.
extract() {
    pdftotext "$1" - 2>/dev/null \
        | tr '\n' ' ' \
        | sed 's/\(\[[0-9]\{1,\}\]\)/\n\1/g' \
        | grep -E '^\[[0-9]+\] [A-Z]' \
        | sed 's/[[:space:]]\+/ /g; s/ $//' \
        | sort -u
}

extract "$ROOT/paper/main.pdf"     > "$WORK/tracked.txt"
extract "$WORK/paper/main.pdf"     > "$WORK/fixed.txt"

echo
echo "=== reference-list size ==="
t=$(wc -l < "$WORK/tracked.txt"); f=$(wc -l < "$WORK/fixed.txt")
printf '  tracked (shipped 2026-09-01): %s entries\n' "$t"
printf '  rebuilt with the fix       : %s entries\n' "$f"

# Fail closed: an empty extraction must never be reported as agreement.
if [ "$t" -eq 0 ] || [ "$f" -eq 0 ]; then
    echo
    echo "  ABORT: extraction produced an empty list -- the comparison would be"
    echo "  vacuous. Not reporting 'identical' on the strength of two empty files."
    exit 1
fi

echo
echo "=== DIFF (tracked vs fixed) ==="
if diff -u "$WORK/tracked.txt" "$WORK/fixed.txt" > "$WORK/diff.txt"; then
    echo "  IDENTICAL -- the defect changed nothing in the shipped bibliography"
else
    echo "  DIFFERS:"
    head -60 "$WORK/diff.txt" | sed 's/^/    /'
    echo "    ... ($(wc -l < "$WORK/diff.txt") diff lines total)"
fi

echo
echo "=== also: does the tracked .bbl differ from what bibtex produces now? ==="
if diff -q "$ROOT/paper/main.bbl" "$WORK/paper/main.bbl" >/dev/null 2>&1; then
    echo "  paper/main.bbl == freshly generated .bbl"
else
    echo "  paper/main.bbl DIFFERS from the freshly generated one:"
    diff "$ROOT/paper/main.bbl" "$WORK/paper/main.bbl" | head -20 | sed 's/^/    /'
fi
