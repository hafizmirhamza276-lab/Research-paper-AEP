#!/usr/bin/env bash
# D0(ii): every one of the six roadmap crash points, one run each, on Linux.
#
# A thin wrapper over `python -m experiments.smoke_matrix`, which owns the
# gate. The provider is started and stopped per run by the orchestrator, so
# this script starts nothing and only has to assert that Redis is reachable
# and disposable before anything is killed on it.
set -uo pipefail

DST="${AEP_LINUX_TREE:-$HOME/aep}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6381/15}"
export PATH="$HOME/.local/bin:$PATH"
cd "$DST"

# Nothing else is started here: a provider left listening from an earlier run
# would be detected by the supervisor's digest check, but killing it first
# makes the failure impossible rather than merely reported.
pkill -f 'experiments.mock_api' >/dev/null 2>&1
sleep 0.5

exec uv run --frozen python -m experiments.smoke_matrix \
  --redis-url "${REDIS_URL}" \
  "$@"
