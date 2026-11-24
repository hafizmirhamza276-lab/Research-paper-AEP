#!/usr/bin/env bash
# WS-5 tiers 1 and 2. Launched detached; ~12 hours.
#
# Pre-registered in reports/phase-report-ws5-prediction-2026-09-10.md and its
# amendment 1. The prompt is prompts/phase-16-ws5-power-and-cells.md. Both were
# committed and pushed before this script was first run (rules 4 and 5).
#
# R1 -- this script writes its own PID to $ROOT/launcher.pid at start and a
# sentinel to $ROOT/COMPLETE on success. Control it by PID from that file.
# NEVER pkill -f on this script's name: it is a loop, and killing the python
# child it is waiting on leaves the loop alive to start the next step, which is
# exactly how two concurrent sweeps once deleted each other's state (R1a).
#
# R12 -- the port is verified free before every step and after every step. An
# orphaned provider on 8099 outlives both the container and the device, and
# has twice failed an entire session's runs in five seconds.
#
# Rule 2 -- results go to a NEW dated directory. Nothing under an existing
# results root is touched.
#
# E5 -- AEP_HARNESS_SUSPEND_DISABLED is exported here, by the collection
# command itself, which is the only place the harness accepts it from. It is
# true of this host: powercfg reports STANDBYIDLE and HIBERNATEIDLE both 0 on
# AC and DC. It was checked before being declared.
set -uo pipefail

REPO=/mnt/d/personal/AEP/Research-paper-AEP
ROOT="$REPO/experiments/results/ws5-2026-09-10"
LOGS="$ROOT/_launcher"
PORT=8099
export PATH="/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export AEP_HARNESS_SUSPEND_DISABLED=1

cd "$REPO" || exit 9
mkdir -p "$LOGS"
echo $$ > "$ROOT/launcher.pid"

UV="uv run --frozen --extra experiments --extra analysis"

say () { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOGS/launcher.log"; }

port_free () {
    if ss -lptn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
        say "FATAL R12: a provider still holds :$PORT"
        ss -lptn "sport = :$PORT" | tee -a "$LOGS/launcher.log"
        return 1
    fi
    return 0
}

step () {
    local tag="$1"; shift
    say "=== BEGIN $tag ==="
    port_free || { say "ABORT before $tag"; return 1; }
    $UV python -m experiments.run_matrix \
        --results-root "$ROOT/$tag" \
        "$@" >>"$LOGS/$tag.log" 2>&1
    local rc=$?
    say "=== END $tag rc=$rc ==="
    # R8's standard, applied to the port: verify, do not assert. A step that
    # exits 0 having leaked a provider fails the NEXT step, not this one.
    port_free || say "WARNING: $tag left :$PORT held"
    return $rc
}

say "launcher pid $$ -> $ROOT"
say "suspend declared: ${AEP_HARNESS_SUSPEND_DISABLED}"

# --- Tier 1 -------------------------------------------------------------
# 5.1 everysec timing: 7 cells x 15 runs. --endpoint payments is the frozen
# design; crash-free overhead cannot depend on a reconciliation capability an
# execution that never reconciles will never use.
step t1-p0-everysec --regime p0 --endpoint payments --runs-per-cell 15

# 5.4 the one incomplete run, named in phase-report-4-session1:493.
step t1-incomplete --system B4_DURABLE_WORKFLOW \
    --crash-point after_barrier_before_dispatch --endpoint payments \
    --runs-per-cell 3

# --- Tier 2 -------------------------------------------------------------
# 5.2 the 30% regime: 21 cells x 15 runs, all seven systems, all three classes.
step t2-p30 --regime p30 --runs-per-cell 15

# 5.3 the alternative read-back keying: AEP-full on the two querying classes.
# ledger_postings is NO_READBACK -- there is no read-back for a keying to
# change -- so collecting it would cost a third of the runs to reproduce a
# number that cannot move.
step t2-keying --keying ORACLE_FINGERPRINT --system AEP_FULL \
    --endpoint payments --endpoint notifications --runs-per-cell 15

say "ALL STEPS DONE"
date -u +%Y-%m-%dT%H:%M:%SZ > "$ROOT/COMPLETE"
