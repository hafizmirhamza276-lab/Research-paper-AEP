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
STAGED_PROV="${PAPER}/.provenance.stage.$$"

cleanup() {
  rm -rf -- "$BUILD_DIR" || true
  rm -f -- "$STAGED_PDF" "$STAGED_LOG" "$STAGED_BBL" "$STAGED_BLG" || true
  rm -f -- "$STAGED_PROV" || true
}
trap cleanup EXIT

# TeX runs from scratch. Recursive TEXINPUTS makes sections, generated tables,
# and figures visible without copying them, while BIBINPUTS exposes refs.bib.
#
# B21 item 1 / B41. The leading "." is load-bearing. A trailing colon appends
# the compiled-in defaults, which include the current directory -- so without
# it "${PAPER}//" sat AHEAD of the scratch dir, and every pdflatex pass opened
# paper/main.bbl instead of the one bibtex had just written beside it. The
# manuscript was typeset from the previous build's bibliography, and promotion
# then overwrote that file with the .bbl the document did not use.
export TEXINPUTS=".:${PAPER}//:${TEXINPUTS:-}"
export BIBINPUTS="${PAPER}:${BIBINPUTS:-}"

# B21 item 3. Hash the sources BEFORE compiling, so the stamp records what this
# build actually read rather than whatever the tree holds once it finishes. It
# is staged here and promoted only with the artifacts, so a failed build leaves
# the previous stamp exactly as it was -- the same discipline as the PDF.
if [ "$ANON" -eq 0 ]; then
  "${NUMBER_RUNNER[@]}" "${ROOT}/scripts/paper_provenance.py" \
    write "$PAPER" "$STAGED_PROV" >/dev/null
fi

cd "$BUILD_DIR"

echo "=== pdflatex / bibtex / pdflatex x2 (${JOB}, staged) ==="
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null
"$BIBTEX" "$JOB" >/dev/null
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null

# B21 item 2 / B41. Assert that the .bbl pdflatex actually opened is the one
# bibtex just wrote here, not one resolved through TEXINPUTS from $PAPER. This
# runs INSIDE the scratch directory, immediately after the passes and before
# any cleanup -- it survives cleanup by construction, not because a file
# outlives it. An earlier attempt read the newest surviving log after the build
# and got one three days old.
#
# The dependency on the three pdflatex calls above is real and is at three
# lines' range in the same block (B40's shape, much shorter). The explicit
# -f test is the mitigation: if this is ever reordered above them, it fails
# closed rather than silently finding no log and concluding nothing.
if [ ! -f "${JOB}.log" ]; then
  echo "bbl identity: no ${JOB}.log to check -- refusing to assume" >&2
  exit 1
fi
bbl_opens="$(grep -oE "\([^() ]*${JOB}\.bbl" "${JOB}.log" | sed 's/^(//' | sort -u)"
if [ -z "$bbl_opens" ]; then
  echo "bbl identity: ${JOB}.log records no ${JOB}.bbl being opened" >&2
  exit 1
fi
while IFS= read -r opened; do
  case "$opened" in
    ./*|"${BUILD_DIR}"/*) ;;
    *)
      echo "bbl identity: pdflatex opened ${opened}, not the staged ${JOB}.bbl" >&2
      echo "  the manuscript would be typeset from a bibliography this build" >&2
      echo "  did not produce. See backlog B41." >&2
      exit 1
      ;;
  esac
done <<EOF
$bbl_opens
EOF
echo "bbl identity: pdflatex opened the staged ${JOB}.bbl"

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
# The stamp goes with them. It is promoted BEFORE the PDF for the same reason
# the logs are: the PDF is the last thing to move, so no ordering leaves a new
# PDF beside a stamp that does not describe it.
if [ "$ANON" -eq 0 ]; then
  mv -f -- "$STAGED_PROV" "$PAPER/.build-provenance.json"
fi
mv -f -- "$STAGED_PDF" "$PAPER/${JOB}.pdf"

echo
echo "build clean (${JOB}); verified artifacts promoted atomically."
