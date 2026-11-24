#!/usr/bin/env bash
# Start (or restart) a MockLegacyAPI in the WSL tree and wait until it serves.
#
# Usage: wsl_mock_api.sh <config-path> [port]
#
# The service is started detached with its stdout/stderr on disk, because the
# runner's own lesson (reports/phase-report-2b-session2-2026-08-05.md, the
# recovery-process pipe deadlock) applies here too: a long-lived child whose
# output goes to an unread pipe stops when the pipe buffer fills.
set -uo pipefail

DST="${AEP_LINUX_TREE:-$HOME/aep}"
CONFIG="${1:?usage: wsl_mock_api.sh <config-path> [port]}"
PORT="${2:-8099}"
export PATH="$HOME/.local/bin:$PATH"
cd "$DST"

pkill -f "experiments.mock_api" >/dev/null 2>&1
sleep 0.5

mkdir -p "$(dirname "$DST/experiments/results/mock-api-${PORT}.log")"
nohup uv run --frozen python -m experiments.mock_api \
  --config "${CONFIG}" --host 127.0.0.1 --port "${PORT}" \
  > "experiments/results/mock-api-${PORT}.log" 2>&1 &

for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${PORT}/v1/config" >/dev/null; then
    echo "mock API up on ${PORT}"
    cat "experiments/results/mock-api-${PORT}.log"
    exit 0
  fi
  sleep 0.5
done

echo "FATAL: mock API did not come up on ${PORT}"
cat "experiments/results/mock-api-${PORT}.log"
exit 1
