#!/usr/bin/env bash
# Rule 13 evidence for check_paper_numbers.py's four anonymous-build checks.
#
# A gate that has never been shown to fail on the leak it exists to catch is
# decoration. This reintroduces each leak, shows the corresponding check fires,
# and restores. It IS the test for those checks -- a separate unit test asserting
# that a leaky PDF fails would have to fabricate the PDF, and a fabricated leak
# proves less than the real build with the primitives removed.
#
#   bash scripts/prove_anonymous_gate.sh
#
# Exit 0 means every check was observed failing on its own leak AND the tree was
# restored to a fully passing state. Any other exit means do not trust the gate.
set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 9

PAPER="${ROOT}/paper"
RUNNER=(uv run --frozen --extra experiments python)
command -v uv >/dev/null 2>&1 || RUNNER=(python3)

for required in pdflatex pdftotext strings; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "required command not found: $required" >&2; exit 127; }
done

BK="$(mktemp -d /tmp/anon-proof.XXXXXX)"
LEAKY="$(mktemp -d /tmp/anon-leaky.XXXXXX)"
restore () {
  [ -f "$BK/main-anon.pdf" ] && cp "$BK/main-anon.pdf" "$PAPER/main-anon.pdf"
  [ -f "$BK/stamp.json" ] && cp "$BK/stamp.json" "$PAPER/.build-provenance-anon.json"
  git checkout -- paper/sections/08-threats.tex 2>/dev/null
  rm -rf "$BK" "$LEAKY"
}
trap restore EXIT

cp "$PAPER/main-anon.pdf" "$BK/main-anon.pdf"
cp "$PAPER/.build-provenance-anon.json" "$BK/stamp.json"

# Capture ONCE per stage, into OUT, and both print and assert from that. An
# earlier version called the checker a second time to assert on, so it was
# asserting about a run it had not shown -- the R13 shape, in the proof of the
# gate R13 exists to justify.
OUT=""
sample () {
  OUT="$("${RUNNER[@]}" scripts/check_paper_numbers.py 2>&1 \
        | grep -E "(PASS|FAIL)  anonymous build")"
  printf '%s\n' "$OUT"
}
fails () { printf '%s\n' "$OUT" | grep -c "FAIL"; }

echo "############ 0. BASELINE ############"
sample
[ "$(fails)" -eq 0 ] || { echo "baseline is not clean; refusing to prove"; exit 1; }

echo
echo "############ 1. LEAKS REINTRODUCED (no primitives, no \\ANONYMOUS) ############"
export TEXINPUTS=".:${PAPER}//:"
export BIBINPUTS="${PAPER}:"
( cd "$LEAKY" && pdflatex -interaction=nonstopmode -jobname=main-anon \
    '\input{main.tex}' >/dev/null 2>&1 )
[ -s "$LEAKY/main-anon.pdf" ] || { echo "could not build the leaky PDF"; exit 1; }
cp "$LEAKY/main-anon.pdf" "$PAPER/main-anon.pdf"
echo "  /PTEX.FileName: $(strings "$PAPER/main-anon.pdf" | grep -c 'PTEX.FileName')"
echo "  /CreationDate : $(strings "$PAPER/main-anon.pdf" | grep -c '/CreationDate')"
echo "  byline        : $(pdftotext -f 1 -l 1 "$PAPER/main-anon.pdf" - 2>/dev/null | sed -n '8p')"
sample
CONTENT_FAILS="$(fails)"
if [ "$CONTENT_FAILS" -lt 3 ]; then
  echo "EXPECTED the three content checks to fail; only ${CONTENT_FAILS} did." >&2
  exit 1
fi

echo
echo "############ 2. STALENESS (good PDF, changed source) ############"
cp "$BK/main-anon.pdf" "$PAPER/main-anon.pdf"
printf '\n%% gate proof, reverted immediately\n' >> paper/sections/08-threats.tex
sample
printf '%s\n' "$OUT" | grep -q "FAIL  anonymous build is not stale" || {
  echo "EXPECTED the staleness check to fail on a changed source." >&2; exit 1; }
git checkout -- paper/sections/08-threats.tex

echo
echo "############ 3. RESTORED ############"
cp "$BK/main-anon.pdf" "$PAPER/main-anon.pdf"
cp "$BK/stamp.json" "$PAPER/.build-provenance-anon.json"
sample
[ "$(fails)" -eq 0 ] || { echo "tree not restored"; exit 1; }
echo
echo "all four anonymous-build checks were observed failing on their own leak,"
echo "and the tree was restored clean."
