#!/usr/bin/env bash
# Launch the evaluation matrix detached, so it outlives the shell that started
# it and can be polled.
#
#   wsl_launch_matrix.sh [extra run_matrix.py arguments...]
#
# Resumable by construction: run_matrix.py skips any run whose summary.json
# already exists and parses, so re-running this script continues rather than
# restarting. That is also why it does not clear the results root.
set -uo pipefail

DST="${AEP_LINUX_TREE:-$HOME/aep}"
# This defaulted to experiments/results/matrix -- the frozen 432-run root
# every outcome rate in the paper is computed from. A bare invocation aimed
# a resumable collection at it. Second instance of the shape that caused the
# phase 19 accident (docs/25 R16), found while wiring the guard in phase 20.
# shellcheck source=scripts/results_root_guard.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/results_root_guard.sh"
aep_require_explicit_results_root RESULTS_ROOT || exit $?
LOG="${MATRIX_LOG:-$DST/experiments/results/matrix-run.log}"
export PATH="$HOME/.local/bin:$PATH"
cd "$DST"

if pgrep -f 'experiments.run_matrix' >/dev/null; then
  echo "a matrix run is already in flight:"
  pgrep -af 'experiments.run_matrix'
  exit 1
fi

mkdir -p "$(dirname "$LOG")"
# PYTHONUNBUFFERED so the log is readable while the run is in flight; the
# default block buffering makes a six-hour job look like a hung one.
PYTHONUNBUFFERED=1 nohup uv run --frozen python -m experiments.run_matrix \
  --results-root "$RESULTS_ROOT" \
  --resume \
  "$@" >>"$LOG" 2>&1 &

echo "matrix launched, pid $!"
echo "log: $LOG"
