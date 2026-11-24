#!/usr/bin/env bash
# Test R7 against a case whose answer is known: the race-mechanism /
# host-dependence claim, which B26 enumerates.
#
# R2's discipline. A procedure shipped unverified is a claim about behaviour,
# and B34 says a claim is not an observation. The procedure must find every
# site; if it finds fewer, R7 is wrong and that is the result, NOT a licence to
# adjust the fixture until it passes.
#
# The invocation below is copied from R7 verbatim. If it diverges from the rule,
# the test is testing something else.
set -u
cd /d/personal/AEP/Research-paper-AEP

# --- the fixture: sites that ASSERT or STATE the host-dependence claim -------
# Derived from B26's four, re-located in current text, plus one B26 omitted.
# Each is (file:line, distinctive substring) so the test does not depend on
# line numbers alone.
EXPECT="paper/sections/06-evaluation.tex:393
paper/sections/08-threats.tex:87
paper/sections/08-threats.tex:103
paper/sections/08-threats.tex:390"

# B26's original fourth site. Edit C rewrote it so it no longer shares a noun
# with the claim, and the NOUN search misses it. It is reachable only by the
# macro search, which is why R7 requires both. Kept in the fixture rather than
# dropped -- dropping it would be adjusting the fixture until the rule passes.
EXPECT_MACRO="paper/sections/06-evaluation.tex:462
paper/main.tex:172"

echo "=== R7 invocation, verbatim ==="
echo "grep -rn --include='*.tex' -iE \"\\bhost'?s?\\b\" paper/sections/ paper/main.tex paper/generated/"
echo

OUT=$(grep -rn --include='*.tex' -iE "\bhost'?s?\b" \
        paper/sections/ paper/main.tex paper/generated/ 2>/dev/null)
TOTAL=$(printf '%s\n' "$OUT" | wc -l)
echo "returned: $TOTAL lines"
echo

miss=0
echo "=== fixture coverage ==="
while IFS= read -r want; do
    [ -z "$want" ] && continue
    if printf '%s\n' "$OUT" | grep -qF "$want:"; then
        echo "  FOUND   $want"
    else
        echo "  MISSING $want"
        miss=$((miss + 1))
    fi
done <<< "$EXPECT"

echo
echo "=== second search: macros carrying the claim's evidence ==="
OUT2=$(grep -rn --include='*.tex' "UnwantedPrevented\|KillLatency" \
        paper/sections/ paper/main.tex paper/generated/ 2>/dev/null)
echo "returned: $(printf '%s\n' "$OUT2" | grep -c .) lines"
while IFS= read -r want; do
    [ -z "$want" ] && continue
    if printf '%s\n' "$OUT2" | grep -qF "$want:"; then
        echo "  FOUND   $want   (noun search misses this one)"
    else
        echo "  MISSING $want"
        miss=$((miss + 1))
    fi
done <<< "$EXPECT_MACRO"

echo
if [ "$miss" -ne 0 ]; then
    echo "RESULT: FAIL -- $miss fixture sites not returned. R7 is wrong."
    exit 1
fi
echo "RESULT: PASS -- all 6 fixture sites returned by the union of both searches"

# --- control: the procedure must also beat the instrument it replaces -------
echo
echo "=== control: what claim_sweep.py returns for the same claim ==="
CS=$(python phase8-driver/claim_sweep.py sweep 2>/dev/null | grep -iE "host" || true)
echo "$CS" | grep -c . | sed 's/^/  lines mentioning host: /'
