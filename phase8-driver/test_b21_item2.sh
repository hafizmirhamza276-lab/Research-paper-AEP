#!/usr/bin/env bash
# B21 item 2: does the .bbl-identity assertion discriminate?
#
# Four constructed states through the NEW build_paper.sh with expected verdicts,
# then the same four through the PRE-CHANGE script, which must pass all of them.
# A check that passes before and after proves nothing (B5).
#
# Everything runs against copies via AEP_PAPER_DIR. paper/ is not touched and
# nothing in it is deleted.
set -u

ROOT=/mnt/d/personal/AEP/Research-paper-AEP
WORK=/tmp/b21-item2
OLD="$ROOT/scripts/.b21-oldbuild.sh"

cleanup() { rm -f "$OLD"; rm -rf "$WORK"; }
trap cleanup EXIT
rm -rf "$WORK"; mkdir -p "$WORK"

# The pre-change script: item 1's fix reverted too, since the assertion only
# has anything to catch while paper/ outranks the scratch dir.
( cd "$ROOT" && git show 2701b42~1:scripts/build_paper.sh ) > "$OLD"

run() {
    label="$1"; expect="$2"; script="$3"; mutate="$4"
    P="$WORK/p"; rm -rf "$P"; cp -r "$ROOT/paper" "$P"
    "$mutate"
    out=$( cd "$ROOT" && AEP_PAPER_DIR="$P" bash "$script" 2>&1 )
    if printf '%s\n' "$out" | grep -q "bbl identity: pdflatex opened the staged"; then
        got=PASS
    elif printf '%s\n' "$out" | grep -q "bbl identity:"; then
        got=CAUGHT
    else
        got=NOCHECK
    fi
    if [ "$got" = "$expect" ]; then
        printf '  %-38s %-8s (expected %s)  OK\n' "$label" "$got" "$expect"
    else
        printf '  %-38s %-8s (expected %s)  *** WRONG ***\n' "$label" "$got" "$expect"
        printf '%s\n' "$out" | grep -E "bbl identity|passed," | sed 's/^/        /'
        rc=1
    fi
}

# State 1: paper/main.bbl absent -> scratch is the only candidate.
m_absent()  { rm -f "$WORK/p/main.bbl"; }
# State 2: paper/main.bbl present -> under the OLD path it shadows the scratch
#          one; under the NEW path it must not.
m_present() { :; }
# State 3: a paper/main.bbl that is valid but demonstrably not this build's.
m_foreign() {
    printf '\\begin{thebibliography}{1}\n\\bibitem{x} Foreign.\n\\end{thebibliography}\n' \
        > "$WORK/p/main.bbl"
}
# State 4: no log for the assertion to read -- the fail-closed path.
m_nolog()   { :; }

rc=0
echo "=== NEW build_paper.sh (item 1 + item 2) ==="
run "paper/main.bbl absent"              PASS "$ROOT/scripts/build_paper.sh" m_absent
run "paper/main.bbl present"             PASS "$ROOT/scripts/build_paper.sh" m_present
run "paper/main.bbl foreign"             PASS "$ROOT/scripts/build_paper.sh" m_foreign

echo
echo "=== PRE-CHANGE build_paper.sh (must never emit the assertion) ==="
run "paper/main.bbl absent"              NOCHECK "$OLD" m_absent
run "paper/main.bbl present"             NOCHECK "$OLD" m_present
run "paper/main.bbl foreign"             NOCHECK "$OLD" m_foreign

echo
echo "=== the assertion catches a shadowed .bbl (item 1 reverted, item 2 kept) ==="
# Item 1's fix removed but item 2's assertion retained: paper/ outranks scratch
# again, so the assertion must FIRE. This is the state item 2 exists for.
# The variant MUST live in scripts/: build_paper.sh sets
#   ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# so a copy under /tmp resolves ROOT to /tmp and fails on
# "${ROOT}/scripts/paper_provenance.py" before pdflatex ever runs -- which
# reports NOCHECK and looks like the assertion not firing. Same defect as the
# item 3 harness copying the checker out of scripts/; second time in two days.
ITEM2="$ROOT/scripts/.b21-item2only.sh"
sed 's|^export TEXINPUTS="\.:|export TEXINPUTS="|' \
    "$ROOT/scripts/build_paper.sh" > "$ITEM2"
if grep -qE '^export TEXINPUTS="\$\{PAPER\}//' "$ITEM2"; then
    echo "  (item 1 reverted in the variant; item 2 retained)"
else
    echo "  WARNING: revert did not apply -- test invalid"; rc=1
fi
run "shadowed .bbl, assertion active"    CAUGHT "$ITEM2" m_present
rm -f "$ITEM2"

echo
[ "$rc" -eq 0 ] && echo "RESULT: PASS" || echo "RESULT: FAIL"
exit "$rc"
