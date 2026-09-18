#!/usr/bin/env bash
# The phase 40 live collection. Committed before any call exists (docs/26 §3
# rule 4), so the conditions are in the record ahead of the data.
#
# THE CODE IS THE ONLY CEILING. There is no spending cap configured on the
# Azure side, so every guard that matters is here or in
# experiments/harness/planner.py. This script therefore refuses more than it
# does:
#
#   * the stage caps must be set explicitly; there is no default
#   * they may only be lowered from the pre-registered ceiling, never raised
#     (agent_loop.stage_caps refuses upward)
#   * the results root must be new and empty, so a rerun cannot resume onto a
#     journal that already holds someone else's reservations
#   * the key is never echoed, never written to the log, and never exported
#     into anything but this process
#
# Usage:
#   bash scripts/run_phase40_live.sh <results-root>
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${1:-}"
ENV_FILE="$REPO/.env"

die () { echo "REFUSING: $*" >&2; exit 2; }

[ -n "$ROOT" ] || die "give me a results root: run_phase40_live.sh <dir>"
[ -e "$ROOT" ] && [ -n "$(ls -A "$ROOT" 2>/dev/null)" ] && \
    die "$ROOT is not empty. A live collection starts on a fresh journal."
[ -f "$ENV_FILE" ] || die "no $ENV_FILE"

# Permissions first: a key readable by the world is a key to rotate, not to use.
PERMS="$(stat -c '%a' "$ENV_FILE")"
case "$PERMS" in
    *[0-9][1-7][0-9]|*[0-9][0-9][1-7]) echo "  note: $ENV_FILE is mode $PERMS" ;;
esac

# Load without echoing. `set -a` exports everything the file defines; nothing
# here prints a value, and the file itself is gitignored.
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

for name in AZURE_OPENAI_ENDPOINT AZURE_OPENAI_API_KEY \
            AZURE_OPENAI_DEPLOYMENT AZURE_OPENAI_API_VERSION \
            AEP_PLANNER_SNAPSHOT; do
    [ -n "${!name:-}" ] || die "$name is not set in $ENV_FILE"
done

# The stage's caps. Lower than section 3's collection-wide numbers on purpose:
# section 6 stages at 10, 30, 100 then 300 calls, and 1 000 is the ceiling for
# the whole experiment, not the setting for the first ten calls.
export AEP_PLANNER_MODE=live
export AEP_PLANNER_PER_COLLECTION_CALLS="${AEP_PLANNER_PER_COLLECTION_CALLS:?set the stage cap explicitly}"
export AEP_PLANNER_PER_RUN_CALLS="${AEP_PLANNER_PER_RUN_CALLS:?set the stage cap explicitly}"
export AEP_PLANNER_PER_COLLECTION_USD="${AEP_PLANNER_PER_COLLECTION_USD:?set the stage cap explicitly}"
export AEP_HARNESS_SUSPEND_DISABLED=1

echo "=== configuration (no secrets) ==="
echo "  endpoint     ${AZURE_OPENAI_ENDPOINT}"
echo "  deployment   ${AZURE_OPENAI_DEPLOYMENT}"
echo "  api-version  ${AZURE_OPENAI_API_VERSION}"
echo "  snapshot     ${AEP_PLANNER_SNAPSHOT}"
echo "  key          ${#AZURE_OPENAI_API_KEY} characters, not shown"
echo "  caps         calls/collection=${AEP_PLANNER_PER_COLLECTION_CALLS}" \
     "calls/run=${AEP_PLANNER_PER_RUN_CALLS}" \
     "usd=${AEP_PLANNER_PER_COLLECTION_USD}"
echo "  results      $ROOT"

cd "$REPO" || die "cannot enter $REPO"

command -v docker >/dev/null || die "docker is not on PATH"
docker compose -f compose.phase2.yml up -d --wait >/dev/null 2>&1 \
    || die "Redis did not come up"
docker exec aep-phase2-redis72 redis-cli -n 15 \
    SET aep:test-instance-marker 1 >/dev/null || die "cannot mark Redis disposable"

# R12. An orphaned provider on 8099 outlives its container and has failed a
# whole session's runs in five seconds.
if ss -lptn 'sport = :8099' 2>/dev/null | grep -q LISTEN; then
    ss -lptn 'sport = :8099' >&2
    die "something already holds :8099"
fi

mkdir -p "$ROOT"
uv run --frozen --extra dev --extra experiments --extra analysis \
    python -m experiments.run_matrix \
        --results-root "$ROOT" \
        --system AEP_FULL --system B0_NAIVE_RETRY \
        --crash-point mid_dispatch --endpoint notifications \
        --keying CALLER_REFERENCE --max-tier 1 \
        --runs-per-cell 1 --executions-per-run 3 --workers 1 \
        >"$ROOT/collection.log" 2>&1
rc=$?
echo "=== collection rc=$rc ==="
tail -12 "$ROOT/collection.log"

echo "=== counter ==="
[ -f "$ROOT/planner-cumulative.json" ] && cat "$ROOT/planner-cumulative.json"
exit $rc
