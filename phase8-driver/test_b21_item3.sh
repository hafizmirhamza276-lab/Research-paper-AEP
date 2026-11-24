#!/usr/bin/env bash
# B21 item 3: does the provenance refusal actually discriminate?
#
# B34 -- verify the mechanism rather than trusting what the design implies --
# and B5's lesson that a check passing before and after proves nothing. Six
# states through the new code with an expected verdict each, then the same six
# through the PRE-CHANGE code from git, which must pass ALL of them. If the old
# code also failed some, the new check would not be what is doing the work.
#
# Throwaway copy via AEP_PAPER_DIR. paper/ is not touched and nothing in it is
# deleted -- deletion is what item 3 replaces.
#
# TWO DEFECTS IN THIS HARNESS'S FIRST VERSION, fixed here and recorded because
# both would have produced a confident wrong answer:
#   1. It copied the checker to /tmp. ROOT is Path(__file__).parents[1], and
#      lines 88 and 208 build paths to paper_tables.py and gen_state_machine.py
#      from it, so every run failed for reasons having nothing to do with
#      provenance -- 7 passed, 5 failed in all twelve cases. The checker must
#      run from scripts/.
#   2. It tested the verdict with `grep -q "0 failed"`, which matches
#      "10 failed". A pass detector that accepts failures.
set -u

ROOT=/mnt/d/personal/AEP/Research-paper-AEP
WORK=/tmp/b21-item3
STAMP=.build-provenance.json
OLD="$ROOT/scripts/.b21-oldcheck.py"

cleanup() { rm -f "$OLD"; rm -rf "$WORK"; }
trap cleanup EXIT

rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$ROOT/paper" "$WORK/paper"
rm -f "$WORK/paper"/main.aux "$WORK/paper"/main.bbl \
      "$WORK/paper"/main.blg "$WORK/paper"/main.log "$WORK/paper/$STAMP"

cd "$ROOT" || exit 1

echo "=== baseline build into the copy (creates artifacts + stamp) ==="
AEP_PAPER_DIR="$WORK/paper" bash scripts/build_paper.sh 2>&1 | tail -2
[ -f "$WORK/paper/$STAMP" ] || { echo "  NO STAMP -- abort"; exit 1; }
echo "  stamp written"

rm -rf "$WORK/fresh"; cp -r "$WORK/paper" "$WORK/fresh"
rc=0

# verdict: PASS only when the tail line reports exactly zero failures.
verdict() {
    n=$(printf '%s\n' "$1" | grep -oE '[0-9]+ passed, [0-9]+ failed' \
        | tail -1 | grep -oE '[0-9]+ failed' | grep -oE '^[0-9]+')
    [ -n "$n" ] || { echo UNKNOWN; return; }
    [ "$n" -eq 0 ] && echo PASS || echo FAIL
}

gate() {
    label="$1"; expect="$2"; checker="$3"; mutate="$4"
    rm -rf "$WORK/paper"; cp -r "$WORK/fresh" "$WORK/paper"
    "$mutate"
    out=$(python3 "$checker" --paper "$WORK/paper" 2>&1)
    got=$(verdict "$out")
    if [ "$got" = "$expect" ]; then
        printf '  %-36s %-7s (expected %s)  OK\n' "$label" "$got" "$expect"
    else
        printf '  %-36s %-7s (expected %s)  *** WRONG ***\n' "$label" "$got" "$expect"
        printf '%s\n' "$out" | grep -E "passed,|build artifacts match" | sed 's/^/        /'
        rc=1
    fi
}

# Mutations chosen so that ONLY provenance distinguishes them. Removing
# figures/state-machine.tex was rejected: it breaks check_state_machine in both
# versions, so it could not show the new check doing the work.
m_none()    { :; }
m_touch()   { printf '\n%% provenance test\n' >> "$WORK/paper/sections/01-introduction.tex"; }
m_nostamp() { rm -f "$WORK/paper/$STAMP"; }
m_corrupt() { printf 'not json' > "$WORK/paper/$STAMP"; }
m_added()   { printf '%% new\n' > "$WORK/paper/sections/99-provenance-probe.tex"; }
m_removed() { rm -f "$WORK/paper/cover-letter-tse.md"; }

echo
echo "=== NEW code ==="
gate "fresh build"                    PASS "$ROOT/scripts/check_paper_numbers.py" m_none
gate "source modified after build"    FAIL "$ROOT/scripts/check_paper_numbers.py" m_touch
gate "stamp missing"                  FAIL "$ROOT/scripts/check_paper_numbers.py" m_nostamp
gate "stamp corrupt"                  FAIL "$ROOT/scripts/check_paper_numbers.py" m_corrupt
gate "source added after build"       FAIL "$ROOT/scripts/check_paper_numbers.py" m_added
gate "source removed after build"     FAIL "$ROOT/scripts/check_paper_numbers.py" m_removed

echo
echo "=== PRE-CHANGE code (must pass ALL six) ==="
git show HEAD:scripts/check_paper_numbers.py > "$OLD"
gate "fresh build"                    PASS "$OLD" m_none
gate "source modified after build"    PASS "$OLD" m_touch
gate "stamp missing"                  PASS "$OLD" m_nostamp
gate "stamp corrupt"                  PASS "$OLD" m_corrupt
gate "source added after build"       PASS "$OLD" m_added
gate "source removed after build"     PASS "$OLD" m_removed

echo
if [ "$rc" -eq 0 ]; then
    echo "RESULT: PASS -- the refusal discriminates, and nothing else does"
else
    echo "RESULT: FAIL"
fi
exit "$rc"
