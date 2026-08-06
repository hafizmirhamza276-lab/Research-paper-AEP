#!/usr/bin/env bash
# Run the full suite in the WSL tree exactly as CI runs it.
#
# Same environment variables, same gates, same coverage floor, so a green run
# here means the same thing a green run in CI means. Redis integration is
# switched on: the environment-gated tests that skip on a developer's laptop
# are the ones covering WAITAOF, the composition and the infrastructure
# faults, and a suite that skipped them would be describing something else.
set -uo pipefail

DST="${AEP_LINUX_TREE:-$HOME/aep}"
export PATH="$HOME/.local/bin:$PATH"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6381/15}"
export AEP_PHASE2_REDIS_INTEGRATION=1
export AEP_PHASE2_REDIS_CONTAINER="${AEP_PHASE2_REDIS_CONTAINER:-aep-phase2-redis72}"
cd "$DST"

uv run --frozen pytest \
  -q -ra --strict-markers \
  --junitxml=junit-linux.xml \
  --cov=aep_core \
  --cov-report=term-missing \
  --cov-fail-under=90
