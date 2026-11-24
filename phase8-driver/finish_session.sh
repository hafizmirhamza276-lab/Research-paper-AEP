#!/usr/bin/env bash
# Refill any run the harness refused to record, then complete the session
# pipeline: analyse, freeze, verify, gate.
#
# Refilling is governed by amendment 4 (reports/phase-report-8-prediction-
# amendment-4-2026-08-28.md), committed while session 2 was still collecting.
# Only runs that raised FaultInjectionError -- the harness's own statement that
# no fault was injected, so the run is not a member of the regime -- are
# refilled. The ceiling is 3 refills per 120-run session; above that the
# instrument is sick, the session is reported as such, and it is NOT refilled.
#
# Usage: finish_session.sh <slug>

set -uo pipefail

SLUG="${1:?usage: finish_session.sh <slug>}"
REPO=/root/aep-phase8
DRIVER=/root/phase8-driver
ROOT_REL="experiments/results/${SLUG}"
ROOT_ABS="${REPO}/${ROOT_REL}"
LOG="${DRIVER}/${SLUG}.log"

exec > >(tee -a "$LOG") 2>&1

say() { echo; echo "=== $* ==="; }

cd "$REPO" || exit 1

RUNS=$(find "$ROOT_ABS" -maxdepth 2 -name summary.json | wc -l)
MISSING=$((120 - RUNS))
say "finish ${SLUG}: ${RUNS}/120 collected, ${MISSING} missing"

# Which runs failed, and why. Only FaultInjectionError is refillable.
say "failures recorded during collection"
grep -nE "^\[[0-9]+/120\]|FAILED" "$LOG" | grep -B1 "FAILED" | grep -E "FAILED|\[" || echo "none"

NON_FAULT=$(grep -c "FAILED" "$LOG")
FAULT=$(grep -c "FAILED: FaultInjectionError" "$LOG")
echo "total failures: ${NON_FAULT}, of which FaultInjectionError: ${FAULT}"

# Reported for every session, including when it is 0 or 1. A kill that does not
# land never occurred across Phase 9's 240 runs or session 1's 120, so any
# recurrence through sessions 2-4 is a candidate symptom of the same host timing
# degradation the drift shows, and belongs in 8.6 whether or not every refill
# runs clean. A count is only interpretable as a series if it is recorded even
# when it is uninteresting.
say "FaultInjectionError census for ${SLUG}"
echo "kills that did not land: ${FAULT} of 120"
grep -E "FAILED: FaultInjectionError" "$LOG" | sed 's/^/  /' || true
grep -B1 "FAILED: FaultInjectionError" "$LOG" | grep -oE "^\[[0-9]+/120\]" \
    | sed 's/^/  original position: /' || true
{
    echo "{"
    echo "  \"session\": \"${SLUG}\","
    echo "  \"fault_injection_errors\": ${FAULT},"
    echo "  \"other_failures\": $((NON_FAULT - FAULT)),"
    echo "  \"runs_collected_before_refill\": ${RUNS},"
    echo "  \"original_positions\": [$(grep -B1 'FAILED: FaultInjectionError' "$LOG" \
        | grep -oE '^\[[0-9]+/120\]' | grep -oE '[0-9]+' | head -20 \
        | paste -sd, -)]"
    echo "}"
} > "${ROOT_ABS}/fault-injection-census.json"
cat "${ROOT_ABS}/fault-injection-census.json"

if [ "$MISSING" -eq 0 ]; then
    echo "nothing to refill"
elif [ "$NON_FAULT" -ne "$FAULT" ]; then
    echo "HALT: a failure that is NOT FaultInjectionError is present."
    echo "Amendment 4 covers only runs the harness refused for a stated"
    echo "instrument reason. Stopping for inspection."
    exit 20
elif [ "$MISSING" -gt 3 ]; then
    echo "HALT: ${MISSING} runs missing, above amendment 4's ceiling of 3."
    echo "That is a sick instrument, not a stray fault. The session is reported"
    echo "as such and is NOT refilled."
    exit 21
else
    # Plan section 3.4's HALT set includes "executions != runs x 1 in any cell",
    # written to catch exactly what --resume can do: collect a run twice and
    # double-count its executions. Amendment 4 now uses --resume deliberately,
    # so the two point at the same signature. The census is taken BEFORE and
    # AFTER while they are still separable; recovering the distinction after the
    # fact would be far harder.
    say "cell census BEFORE refill"
    uv run python "${DRIVER}/cell_census.py" "$ROOT_ABS" before-refill || {
        echo "HALT: pre-refill census failed"; exit 23; }

    say "refill: ${MISSING} run(s), out of position, per amendment 4"
    uv run python -m experiments.run_matrix \
        --regime redis-kill-preack \
        --results-root "$ROOT_REL" \
        --max-tier 2 \
        --resume
    echo "resume exit=$?"

    RUNS=$(find "$ROOT_ABS" -maxdepth 2 -name summary.json | wc -l)
    echo "after refill: ${RUNS}/120"
    if [ "$RUNS" -ne 120 ]; then
        echo "HALT: still ${RUNS}/120 after refill"
        exit 22
    fi

    say "cell census AFTER refill"
    uv run python "${DRIVER}/cell_census.py" "$ROOT_ABS" after-refill || {
        echo "HALT: post-refill census failed"; exit 23; }

    say "resume double-count check"
    uv run python "${DRIVER}/cell_census.py" --compare \
        "${ROOT_ABS}/cell-census-before-refill.json" \
        "${ROOT_ABS}/cell-census-after-refill.json" || {
        echo "HALT: the resume double-count check fired."
        echo "Amendment 4's refill and a genuine double-count share this"
        echo "signature. Stopping while they are still separable."
        exit 24; }
fi

say "analyze"
uv run python -m experiments.analyze --results-root "$ROOT_REL" || {
    echo "HALT: analyze failed"; exit 9; }

cp "${ROOT_ABS}/container-precondition.json" \
   "${ROOT_ABS}/analysis/container-precondition.json"

say "fault census"
uv run python "${DRIVER}/fault_census.py" "$ROOT_ABS" --write || {
    echo "HALT: fault census failed"; exit 25; }

# Slice the continuous foreign-load sample into this session's own window, so
# each root carries the observation that belongs to it. Additive observation
# only -- no gate reads it. Added mid-collection after session 2 showed that a
# t=0 snapshot cannot see load arriving at t+30min; 8.6 must disclose that
# session 2 has no such series and that session 3's begins partway in.
say "foreign-load sample for this session"
uv run python "${DRIVER}/slice_load.py" "$ROOT_ABS" "$LOG" \
    "${DRIVER}/foreign-load-samples.jsonl" || {
    echo "NOTE: foreign-load slice unavailable; continuing (observation only)"; }

say "freeze"
uv run python scripts/freeze_results.py --results-root "$ROOT_REL" || {
    echo "HALT: freeze_results failed"; exit 10; }

say "sha256sum -c on disk"
( cd "$ROOT_ABS" && sha256sum -c SHA256SUMS )
SHARC=$?
echo "sha256sum -c exit=${SHARC}"
[ "$SHARC" -eq 0 ] || { echo "HALT: on-disk digest verification failed"; exit 11; }

say "registered gates"
uv run python "${DRIVER}/gates.py" "$ROOT_ABS"
GATES=$?
echo "gates exit=${GATES}"
[ "$GATES" -eq 0 ] || { echo "HALT: a registered gate failed"; exit 12; }

say "${SLUG} complete at $(date -Iseconds)"
exit 0
