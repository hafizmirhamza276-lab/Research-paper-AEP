#!/usr/bin/env bash
# Bring the Linux measurement tree's *source* into line with the committed one.
#
# The measurement tree is not a git checkout: it holds the results, which are
# gitignored and are published as an archive. That is fine until a number in
# the paper is computed from the source rather than from a CSV -- the two LOC
# figures in Section 5 are -- at which point a build on the measurement tree
# describes a tree nobody can check out, and scripts/check_paper_numbers.py
# correctly refuses it. This script is the fix.
#
# Two rules it enforces rather than trusting:
#
#   1. **It never deletes under experiments/results/.** That directory is the
#      evaluation, it is not in git, and `rsync --delete` over its parent
#      would take it. The filter is belt and braces: an exclude, and a
#      protect rule so a later --delete pass cannot reach it either.
#
#   2. **It refuses to run while the matrix is collecting.** Rewriting the
#      harness under a live run is how a resumed run ends up mixing code
#      versions, and the digest check that would catch it only fires between
#      runs.
#
# Usage, from the repository root on the Windows side:
#   AEP_MEASUREMENT_TREE=$HOME/aep bash scripts/sync_measurement_tree.sh
set -euo pipefail

SRC="${AEP_SOURCE_TREE:-$(pwd)}"
DEST="${AEP_MEASUREMENT_TREE:-$HOME/aep}"

if [ ! -d "${DEST}" ]; then
  echo "no measurement tree at ${DEST}" >&2
  exit 1
fi

if pgrep -f "experiments.run_matrix" > /dev/null; then
  echo "REFUSING: the matrix is collecting. Rewriting the harness under a" >&2
  echo "live run mixes code versions across a resumption boundary, and the" >&2
  echo "configuration digest only catches that between runs." >&2
  pgrep -af "experiments.run_matrix" >&2
  exit 1
fi

echo "source      ${SRC}"
echo "measurement ${DEST}"
echo

cd "${DEST}"
for tree in aep_core scripts tests; do
  rsync -a --delete "${SRC}/${tree}/" "${tree}/" --exclude '__pycache__'
  echo "  synced ${tree}/"
done

# experiments/ carries results/ inside it. Exclude it from the transfer and
# protect it from the delete pass.
rsync -a --delete "${SRC}/experiments/" experiments/ \
  --exclude '__pycache__' --exclude 'results' --filter='P results'
echo "  synced experiments/ (results/ excluded and protected)"

rsync -a "${SRC}/pyproject.toml" "${SRC}/uv.lock" ./
mkdir -p paper/sections paper/generated paper/figures
rsync -a "${SRC}/paper/main.tex" "${SRC}/paper/refs.bib" paper/
rsync -a --delete "${SRC}/paper/sections/" paper/sections/
rsync -a --delete "${SRC}/paper/generated/" paper/generated/
rsync -a "${SRC}/paper/figures/" paper/figures/
echo "  synced paper/"

echo
echo "=== what the LOC macros will count here ==="
printf '  aep_core    %s lines\n' \
  "$(find aep_core -name '*.py' -not -path '*__pycache__*' -exec cat {} + | wc -l)"
printf '  experiments %s lines\n' \
  "$(find experiments -name '*.py' -not -path '*__pycache__*' -not -path './experiments/results/*' -exec cat {} + | wc -l)"
echo
echo "=== results left untouched ==="
printf '  matrix run directories: %s\n' \
  "$(ls -d experiments/results/matrix/*/ 2>/dev/null | wc -l)"
