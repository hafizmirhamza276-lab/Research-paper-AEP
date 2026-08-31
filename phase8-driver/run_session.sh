#!/usr/bin/env bash
# Phase 8.4 single-session collection, freeze and verify.
#
# One session only. The per-session commit is deliberate and is not automated
# here: if a third collection fails it must cost one session, not three, and
# the staged-blob verification (plan section 4 step 4) happens in the Windows
# clone where the commit is made.
#
# Halting is the default. Any failed gate exits non-zero and leaves the root in
# place for inspection; nothing is regenerated to make a check agree.
#
# Usage: run_session.sh <session slug>     e.g. b2-paired-v2-s2-2026-08-28

set -uo pipefail

SLUG="${1:?usage: run_session.sh <session slug>}"
REPO=/root/aep-phase8
DRIVER=/root/phase8-driver
ROOT_REL="experiments/results/${SLUG}"
ROOT_ABS="${REPO}/${ROOT_REL}"
LOG="${DRIVER}/${SLUG}.log"

exec > >(tee -a "$LOG") 2>&1

say() { echo; echo "=== $* ==="; }

say "session ${SLUG} starting at $(date -Iseconds)"

cd "$REPO" || exit 1

# --- Gate: tree state (plan section 6 stop condition) ----------------------
say "git state"
git rev-parse HEAD
STATUS="$(git status --porcelain)"
if [ -n "$STATUS" ]; then
    echo "HALT: git status is not clean at session start"
    echo "$STATUS"
    exit 3
fi
echo "tree clean"

if [ -e "$ROOT_ABS" ]; then
    echo "HALT: results root already exists: $ROOT_ABS"
    echo "Refusing to collect into an existing root."
    exit 4
fi

# --- Precondition: container state ----------------------------------------
say "container precondition"
bash "${DRIVER}/precondition.sh" "$ROOT_ABS" || {
    echo "HALT: container precondition failed"
    exit 5
}

# --- Collect ---------------------------------------------------------------
say "collection starting at $(date -Iseconds)"
START=$(date +%s)
uv run python -m experiments.run_matrix \
    --regime redis-kill-preack \
    --results-root "$ROOT_REL" \
    --max-tier 2
RC=$?
END=$(date +%s)
ELAPSED=$((END - START))
echo "run_matrix exit=${RC} elapsed=${ELAPSED}s ($(python3 -c "print(f'{${ELAPSED}/3600:.2f}')") h)"

# run_matrix returns 1 if ANY run failed (run_matrix.py:1083). Amendment 4
# registers one such case as expected and non-terminal: runs that raised
# FaultInjectionError -- the harness's own statement that no fault was injected,
# so the run is not a member of the regime -- are refilled via --resume when
# they are under the ceiling of 3.
#
# The first version of this script treated exit 1 as terminal and stopped the
# chain on exactly the case the amendment exists to handle. So the exit code is
# not read alone: it is read together with WHY runs failed.
if [ "$RC" -ne 0 ]; then
    TOTAL_FAILED=$(grep -c "FAILED" "$LOG")
    FAULT_FAILED=$(grep -c "FAILED: FaultInjectionError" "$LOG")
    if [ "$RC" -eq 1 ] \
       && [ "$TOTAL_FAILED" -eq "$FAULT_FAILED" ] \
       && [ "$FAULT_FAILED" -gt 0 ] \
       && [ "$FAULT_FAILED" -le 3 ]; then
        echo "run_matrix exited 1 with ${FAULT_FAILED} FaultInjectionError run(s)"
        echo "and no other failures, which is under amendment 4's ceiling of 3."
        echo "This is the registered refill case, not a halt. Continuing."
    else
        echo "HALT: run_matrix exited ${RC}"
        echo "  total failures        : ${TOTAL_FAILED}"
        echo "  FaultInjectionError   : ${FAULT_FAILED}"
        if [ "$TOTAL_FAILED" -ne "$FAULT_FAILED" ]; then
            echo "  a failure that is NOT FaultInjectionError is present;"
            echo "  amendment 4 does not cover it."
        elif [ "$FAULT_FAILED" -gt 3 ]; then
            echo "  above amendment 4's ceiling of 3: a sick instrument, not a"
            echo "  stray fault. Reported as such and NOT refilled."
        fi
        exit 6
    fi
fi

# Registered wall-time stop condition: 1.5x the 120-run model of 4284 s.
if [ "$ELAPSED" -gt 6426 ]; then
    echo "HALT: wall time ${ELAPSED}s exceeds the registered threshold of 6426s"
    exit 7
fi

say "post-run load"
cat /proc/loadavg

RUNS=$(find "$ROOT_ABS" -maxdepth 2 -name summary.json | wc -l)
echo "runs with summary.json: ${RUNS}"

# Hand off to finish_session.sh rather than repeating its work here. It owns the
# amendment-4 refill, the before/after cell census that separates a registered
# refill from a resume double-count, the fault census, the freeze, the digest
# verification and the registered gates. Duplicating any of that in two scripts
# is how the two come to disagree.
say "handing off to finish_session.sh"
bash "${DRIVER}/finish_session.sh" "$SLUG"
FIN=$?
if [ "$FIN" -ne 0 ]; then
    echo "HALT: finish_session.sh exited ${FIN}"
    exit "$FIN"
fi

# A sentinel, written only on success. Watchers wait on this file rather than on
# a pgrep pattern: the previous watcher matched "run_session.sh <slug>", which is
# a substring of its OWN command line, so it matched itself, could never see the
# process end, and the chain could never advance. The pgrep always read true in
# exactly the way ${#ARRAY[@]:-0} always read false -- see B11.
date -Iseconds > "${DRIVER}/${SLUG}.done"

say "session ${SLUG} complete at $(date -Iseconds), elapsed ${ELAPSED}s"
exit 0
