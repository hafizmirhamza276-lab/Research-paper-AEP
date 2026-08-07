#!/usr/bin/env bash
# Build the manuscript, and fail if the build was only cosmetically clean.
#
# LaTeX's definition of success is weak in the two ways that have already bitten
# this paper once each:
#
#   * a bibliography can compile completely blank while LaTeX reports no
#     undefined citation, because BibTeX emits an empty \bibitem for an entry
#     it failed to parse and says so only in the .blg;
#   * an undefined reference is a *warning*, so `pdflatex` exits 0 with `??`
#     rendered in the text.
#
# So this script treats both as build failures, and runs
# scripts/check_paper_numbers.py afterwards, which is the gate that re-derives
# every generated table and scalar from the frozen CSVs.
#
# Usage, from the repository root:
#   bash scripts/build_paper.sh
#
# Requires a TeX distribution with IEEEtran. On the measurement host that is
# the Linux tree; the Windows development tree has no pdflatex, which is why
# the paper is built where the results are.
set -euo pipefail

PAPER="${AEP_PAPER_DIR:-paper}"
cd "$PAPER"

echo "=== pdflatex / bibtex / pdflatex x2 ==="
rm -f main.aux main.bbl main.blg main.log main.out main.pdf
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
bibtex main > /dev/null || true
pdflatex -interaction=nonstopmode main.tex > /dev/null || true
pdflatex -interaction=nonstopmode main.tex > /dev/null || true

failures=0

echo
echo "=== bibtex parse errors (a blank bibliography compiles clean) ==="
if grep -iE "I was expecting|missing a field name|skipping whatever remains" main.blg; then
  echo "  FAIL"
  failures=$((failures + 1))
else
  echo "  none"
fi

echo
echo "=== undefined references and citations (warnings, not errors) ==="
if grep -iE "Warning.*(undefined|Citation)" main.log | grep -v Font; then
  echo "  FAIL"
  failures=$((failures + 1))
else
  echo "  none"
fi

echo
echo "=== \\todoitem markers left in the sections ==="
if grep -rn '\\todoitem' sections/; then
  echo "  (permitted only where a still-running cell could move a value)"
else
  echo "  none"
fi

echo
echo "=== output ==="
grep -oE "Output written on main.pdf \([0-9]+ pages" main.log || true
echo "overfull boxes: $(grep -c Overfull main.log || true)"

cd ..
echo
echo "=== the numbers against the results ==="
if command -v uv > /dev/null; then
  uv run --frozen python scripts/check_paper_numbers.py || failures=$((failures + 1))
else
  python scripts/check_paper_numbers.py || failures=$((failures + 1))
fi

echo
if [ "${failures}" -ne 0 ]; then
  echo "DO NOT SUBMIT: ${failures} check(s) failed."
  exit 1
fi
echo "build clean."
