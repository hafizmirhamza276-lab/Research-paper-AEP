#!/usr/bin/env bash
# Build the manuscript without risking the last-known-good PDF.
#
# Compilation happens in a scratch directory. Bibliography, reference, PDF,
# and paper-number checks all run against those staged artifacts; only a clean
# build is promoted into paper/. The PDF is promoted last so every earlier
# failure path leaves the existing PDF byte-for-byte intact.
#
# Usage, from the repository root:
#   bash scripts/build_paper.sh               # public    -> paper/main.pdf
#   bash scripts/build_paper.sh --anonymous   # anonymous -> paper/main-anon.pdf
set -euo pipefail

ANON=0
JOB="main"
TEXINPUT="main.tex"
if [ "${1:-}" = "--anonymous" ]; then
  ANON=1
  JOB="main-anon"
  TEXINPUT='\def\ANONYMOUS{}\input{main.tex}'
elif [ "$#" -ne 0 ]; then
  echo "usage: $0 [--anonymous]" >&2
  exit 2
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PAPER="${AEP_PAPER_DIR:-${ROOT}/paper}"
PDFLATEX="${AEP_PDFLATEX:-pdflatex}"
BIBTEX="${AEP_BIBTEX:-bibtex}"

# Resolve every required command before creating scratch files or touching any
# existing output. The overridable TeX command names make this check directly
# testable and also support installations whose executables are not on PATH.
required_commands=("$PDFLATEX" "$BIBTEX" grep head mktemp mkdir cp mv rm)
for required in "${required_commands[@]}"; do
  if ! command -v "$required" >/dev/null 2>&1; then
    echo "required paper-build command not found: $required" >&2
    exit 127
  fi
done

NUMBER_RUNNER=()
if [ "$ANON" -eq 0 ]; then
  if [ -n "${AEP_NUMBER_PYTHON:-}" ]; then
    if ! command -v "$AEP_NUMBER_PYTHON" >/dev/null 2>&1; then
      echo "configured paper-number Python not found: $AEP_NUMBER_PYTHON" >&2
      exit 127
    fi
    NUMBER_RUNNER=("$AEP_NUMBER_PYTHON")
  elif command -v uv >/dev/null 2>&1; then
    NUMBER_RUNNER=(uv run --frozen python)
  elif [ -x "${HOME}/.local/bin/uv" ]; then
    NUMBER_RUNNER=("${HOME}/.local/bin/uv" run --frozen python)
  elif command -v python3 >/dev/null 2>&1; then
    NUMBER_RUNNER=(python3)
  else
    echo "required paper-number command not found: uv or python3" >&2
    exit 127
  fi
fi

SCRATCH_PARENT="${ROOT}/.scratch/paper-build"
mkdir -p "$SCRATCH_PARENT"
BUILD_DIR="$(mktemp -d "${SCRATCH_PARENT}/${JOB}.XXXXXX")"
BUILD_DIR_REL="${BUILD_DIR#"${ROOT}/"}"
STAGED_PDF="${PAPER}/.${JOB}.pdf.stage.$$"
STAGED_LOG="${PAPER}/.${JOB}.log.stage.$$"
STAGED_BBL="${PAPER}/.${JOB}.bbl.stage.$$"
STAGED_BLG="${PAPER}/.${JOB}.blg.stage.$$"

cleanup() {
  rm -rf -- "$BUILD_DIR" || true
  rm -f -- "$STAGED_PDF" "$STAGED_LOG" "$STAGED_BBL" "$STAGED_BLG" || true
}
trap cleanup EXIT

# TeX runs from scratch. Recursive TEXINPUTS makes sections, generated tables,
# and figures visible without copying them, while BIBINPUTS exposes refs.bib.
export TEXINPUTS="${PAPER}//:${TEXINPUTS:-}"
export BIBINPUTS="${PAPER}:${BIBINPUTS:-}"
cd "$BUILD_DIR"

echo "=== pdflatex / bibtex / pdflatex x2 (${JOB}, staged) ==="
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null
"$BIBTEX" "$JOB" >/dev/null
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null

for artifact in "${JOB}.pdf" "${JOB}.log" "${JOB}.bbl" "${JOB}.blg"; do
  if [ ! -s "$artifact" ]; then
    echo "paper build did not produce a non-empty ${artifact}" >&2
    exit 1
  fi
done
if [ "$(head -c 5 "${JOB}.pdf")" != "%PDF-" ]; then
  echo "paper build produced an invalid PDF header: ${JOB}.pdf" >&2
  exit 1
fi
if command -v pdfinfo >/dev/null 2>&1; then
  pdfinfo "${JOB}.pdf" >/dev/null
fi

failures=0

echo
echo "=== bibtex parse errors (a blank bibliography compiles clean) ==="
if grep -iE "I was expecting|missing a field name|skipping whatever remains" \
  "${JOB}.blg"; then
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
if grep -rn '\\todoitem' "${PAPER}/sections/"; then
  echo "  (permitted only where a still-running cell could move a value)"
else
  echo "  none"
fi

overfull_count="$(grep -c Overfull "${JOB}.log" || true)"
underfull_count="$(grep -c Underfull "${JOB}.log" || true)"
echo
echo "=== staged output ==="
grep -oE "Output written on ${JOB}.pdf \([0-9]+ pages" "${JOB}.log" || true
echo "overfull boxes: ${overfull_count}"
echo "underfull boxes: ${underfull_count}"

if [ "$ANON" -eq 0 ]; then
  echo
  echo "=== the numbers against the results ==="
  cd "$ROOT"
  if ! "${NUMBER_RUNNER[@]}" scripts/check_paper_numbers.py \
    --build-dir "$BUILD_DIR_REL"; then
    failures=$((failures + 1))
  fi
fi

if [ "$failures" -ne 0 ]; then
  echo
  echo "DO NOT SUBMIT: ${failures} check(s) failed. Existing ${JOB}.pdf preserved."
  exit 1
fi

# Stage every promoted artifact first. Move the PDF only after logs and
# bibliography artifacts, so a staging/promotion failure cannot replace the
# old PDF with a build whose supporting artifacts were not preserved.
cp -- "$BUILD_DIR/${JOB}.pdf" "$STAGED_PDF"
cp -- "$BUILD_DIR/${JOB}.log" "$STAGED_LOG"
cp -- "$BUILD_DIR/${JOB}.bbl" "$STAGED_BBL"
cp -- "$BUILD_DIR/${JOB}.blg" "$STAGED_BLG"
mv -f -- "$STAGED_LOG" "$PAPER/${JOB}.log"
mv -f -- "$STAGED_BBL" "$PAPER/${JOB}.bbl"
mv -f -- "$STAGED_BLG" "$PAPER/${JOB}.blg"
mv -f -- "$STAGED_PDF" "$PAPER/${JOB}.pdf"

echo
echo "build clean (${JOB}); verified artifacts promoted atomically."
