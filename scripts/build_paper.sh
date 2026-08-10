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
#   bash scripts/build_paper.sh               # public    -> paper/main.pdf
#   bash scripts/build_paper.sh --anonymous   # anonymous -> paper/main-anon.pdf
#
# The anonymous build (Monday audit, fix F2) is the same source read with
# \ANONYMOUS defined, which swaps the artifact URL for a neutral pointer and
# blanks the PDF document properties. It uses its own job name so the two
# builds cannot overwrite each other's .aux/.bbl/.log/.pdf, and so the public
# build's artifacts stay on disk for the numbers gate to read.
#
# Requires a TeX distribution with IEEEtran. On the measurement host that is
# the Linux tree; the Windows development tree has no pdflatex, which is why
# the paper is built where the results are.
set -euo pipefail

ANON=0
JOB="main"
TEXINPUT="main.tex"
if [ "${1:-}" = "--anonymous" ]; then
  ANON=1
  JOB="main-anon"
  TEXINPUT='\def\ANONYMOUS{}\input{main.tex}'
fi

PAPER="${AEP_PAPER_DIR:-paper}"
cd "$PAPER"

echo "=== pdflatex / bibtex / pdflatex x2 (${JOB}) ==="
rm -f "${JOB}.aux" "${JOB}.bbl" "${JOB}.blg" "${JOB}.log" "${JOB}.out" "${JOB}.pdf"
pdflatex -interaction=nonstopmode -halt-on-error -jobname="${JOB}" "$TEXINPUT" > /dev/null
bibtex "${JOB}" > /dev/null || true
pdflatex -interaction=nonstopmode -jobname="${JOB}" "$TEXINPUT" > /dev/null || true
pdflatex -interaction=nonstopmode -jobname="${JOB}" "$TEXINPUT" > /dev/null || true

failures=0

echo
echo "=== bibtex parse errors (a blank bibliography compiles clean) ==="
if grep -iE "I was expecting|missing a field name|skipping whatever remains" "${JOB}.blg"; then
  echo "  FAIL"
  failures=$((failures + 1))
else
  echo "  none"
fi

echo
echo "=== undefined references and citations (warnings, not errors) ==="
if grep -iE "Warning.*(undefined|Citation)" "${JOB}.log" | grep -v Font; then
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
grep -oE "Output written on ${JOB}.pdf \([0-9]+ pages" "${JOB}.log" || true
echo "overfull boxes: $(grep -c Overfull "${JOB}.log" || true)"

cd ..
echo
if [ "${ANON}" -ne 0 ]; then
  # check_paper_numbers.py opens paper/main.bbl and paper/main.log by name. In
  # an anonymous build those belong to the public build, so running it here
  # would report a verdict about a different PDF. Nothing is lost by skipping:
  # the numbers, tables and macros are the same source in both builds and the
  # public build gates them, while this build's own bibliography and undefined
  # references were just checked above against main-anon.blg / main-anon.log.
  echo "=== the numbers against the results ==="
  echo "  SKIPPED for the anonymous build -- the gate reads main.log/main.bbl."
  echo "  Run the public build (no flag) for the numbers verdict."
  echo
  if [ "${failures}" -ne 0 ]; then
    echo "DO NOT SUBMIT: ${failures} check(s) failed."
    exit 1
  fi
  echo "build clean (${JOB})."
  exit 0
fi
echo "=== the numbers against the results ==="
if command -v uv > /dev/null; then
  uv run --frozen python scripts/check_paper_numbers.py || failures=$((failures + 1))
elif [ -x "${HOME}/.local/bin/uv" ]; then
  "${HOME}/.local/bin/uv" run --frozen python scripts/check_paper_numbers.py \
    || failures=$((failures + 1))
elif command -v python3 > /dev/null; then
  python3 scripts/check_paper_numbers.py || failures=$((failures + 1))
else
  echo "no uv and no python3: the numbers were NOT checked" >&2
  failures=$((failures + 1))
fi

echo
if [ "${failures}" -ne 0 ]; then
  echo "DO NOT SUBMIT: ${failures} check(s) failed."
  exit 1
fi
echo "build clean."
