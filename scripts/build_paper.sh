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
#   bash scripts/build_paper.sh --supplementary [--anonymous]
#                                             #           -> paper/supplementary[-anon].pdf
#
# The supplementary is a SEPARATE document, not an appendix bound into
# main.tex, because IEEE CS guidance treats appendices as supplemental material
# to be submitted separately and excludes supplemental material from the page
# count. It is built by this same script so it inherits every protection the
# main build has: scratch compilation, the .bbl identity assertion, staged
# promotion, its own provenance stamp, and -- for its anonymous build -- the
# same pdfTeX primitives.
set -euo pipefail

ANON=0
DOC="main"
JOB="main"
TEXINPUT="main.tex"
# --supplementary may appear before or after --anonymous.
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--supplementary" ]; then
    DOC="supplementary"
  else
    ARGS+=("$arg")
  fi
done
set -- ${ARGS[@]+"${ARGS[@]}"}
JOB="$DOC"
TEXINPUT="${DOC}.tex"
if [ "${1:-}" = "--anonymous" ]; then
  ANON=1
  JOB="${DOC}-anon"
  # Two pdfTeX primitives, and they are here rather than in main.tex so the
  # public build is untouched by construction -- it is not anonymous and does
  # not need to be.
  #
  # \pdfsuppressptexinfo=-1 stops pdfTeX writing /PTEX.FileName, /PTEX.PageNumber
  # and /PTEX.InfoDict into each embedded PDF figure. Those recorded the
  # ABSOLUTE build path, which carries the repository name and so resolves by
  # search to the author's account. It is in neither the text layer nor DocInfo,
  # so pdftotext and pdfinfo both miss it.
  #
  # \pdfinfoomitdate=1 omits /CreationDate and /ModDate, whose +05'00' offset is
  # a weaker locality hint of the same kind. \pdftrailerid{} removes the last
  # per-build varying identifier.
  #
  # Chosen over the alternatives after testing all of them on this toolchain
  # (pdfTeX 1.40.25): relative figure paths do not work because TEXINPUTS
  # resolves figures through an absolute "${PAPER}//" and the resolved path is
  # what gets recorded; a post-process strip would have to rewrite PDF objects
  # and shift the xref table, risking corruption of the artifact it is meant to
  # protect. These primitives remove the strings at the source, need no external
  # tool, and cannot produce an invalid PDF.
  TEXINPUT="\pdfsuppressptexinfo=-1 \pdfinfoomitdate=1 \pdftrailerid{}\def\ANONYMOUS{}\input{${DOC}.tex}"
elif [ "$#" -ne 0 ]; then
  echo "usage: $0 [--supplementary] [--anonymous]" >&2
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

# Resolved for BOTH builds. It used to be public-only, because only the public
# build ran check_paper_numbers.py; the anonymous build now also writes a
# provenance stamp, and needs the same runner to do it.
NUMBER_RUNNER=()
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
"${NUMBER_RUNNER[@]}" "${ROOT}/scripts/paper_provenance.py" \
  write "$PAPER" "$STAGED_PROV" >/dev/null

cd "$BUILD_DIR"

# Does this document have a bibliography at all? The supplementary starts
# as an empty container with no citations, and bibtex fails hard on
# "I found no citation commands". Running it anyway would make an honest
# empty container unbuildable; skipping it silently would hide a missing
# bibliography the day the first citation is moved in. So the decision is
# derived from the source, announced, and PAIRED WITH A GATE:
# check_paper_numbers.py refuses a supplementary that cites without
# declaring a bibliography.
HAS_BIB=0
if grep -qE '^[^%]*\\bibliography\{' "${PAPER}/${DOC}.tex"; then
  HAS_BIB=1
fi

echo "=== pdflatex / bibtex / pdflatex x2 (${JOB}, staged) ==="
"$PDFLATEX" -interaction=nonstopmode -halt-on-error -jobname="$JOB" \
  "$TEXINPUT" >/dev/null
if [ "$HAS_BIB" -eq 1 ]; then
  "$BIBTEX" "$JOB" >/dev/null
else
  echo "no bibliography in ${DOC}.tex -- skipping bibtex (announced, not silent)"
fi
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
if [ "$HAS_BIB" -eq 0 ]; then
  echo "bbl identity: not applicable -- ${DOC}.tex declares no bibliography"
fi
if [ "$HAS_BIB" -eq 1 ]; then
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
fi

REQUIRED_ARTIFACTS=("${JOB}.pdf" "${JOB}.log")
if [ "$HAS_BIB" -eq 1 ]; then
  REQUIRED_ARTIFACTS+=("${JOB}.bbl" "${JOB}.blg")
fi
for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
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

if [ "$ANON" -eq 0 ] && [ "$DOC" != "supplementary" ]; then
  echo
  echo "=== the numbers against the results ==="
  cd "$ROOT"
  if ! "${NUMBER_RUNNER[@]}" scripts/check_paper_numbers.py \
    --build-dir "$BUILD_DIR_REL"; then
    failures=$((failures + 1))
  fi
fi

# Every variant, not only the main non-anonymous one. A repository path is
# wrong in all four, and it is an anonymity risk in exactly the two the
# numbers check above skips. Run on the staged PDF, before promotion, so a
# build that would ship one never replaces a clean artifact.
echo
echo "=== repository paths in the rendered text ==="
cd "$ROOT"
if ! "${NUMBER_RUNNER[@]}" scripts/check_no_repo_paths.py \
  "$BUILD_DIR/${JOB}.pdf"; then
  failures=$((failures + 1))
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
if [ "$HAS_BIB" -eq 1 ]; then
  cp -- "$BUILD_DIR/${JOB}.bbl" "$STAGED_BBL"
  cp -- "$BUILD_DIR/${JOB}.blg" "$STAGED_BLG"
fi
mv -f -- "$STAGED_LOG" "$PAPER/${JOB}.log"
if [ "$HAS_BIB" -eq 1 ]; then
  mv -f -- "$STAGED_BBL" "$PAPER/${JOB}.bbl"
  mv -f -- "$STAGED_BLG" "$PAPER/${JOB}.blg"
fi
# The stamp goes with them. It is promoted BEFORE the PDF for the same reason
# the logs are: the PDF is the last thing to move, so no ordering leaves a new
# PDF beside a stamp that does not describe it.
# One stamp per artifact, never shared: a rebuild of one must not vouch for
# another that was not rebuilt. That is the main-anon.pdf failure, generalised.
if [ "$DOC" = "supplementary" ]; then
  if [ "$ANON" -eq 0 ]; then
    mv -f -- "$STAGED_PROV" "$PAPER/.build-provenance-supp.json"
  else
    mv -f -- "$STAGED_PROV" "$PAPER/.build-provenance-supp-anon.json"
  fi
elif [ "$ANON" -eq 0 ]; then
  mv -f -- "$STAGED_PROV" "$PAPER/.build-provenance.json"
else
  mv -f -- "$STAGED_PROV" "$PAPER/.build-provenance-anon.json"
fi
mv -f -- "$STAGED_PDF" "$PAPER/${JOB}.pdf"

echo
echo "build clean (${JOB}); verified artifacts promoted atomically."
