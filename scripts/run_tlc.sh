#!/usr/bin/env bash
# Model-check formal/AEP.tla in every configuration under formal/configs/, and
# hold each one to the outcome it declares.
#
# The point of the expectation is docs/26 section 3 rule 13: a gate that cannot
# fail is decoration.  Nine of the sixteen configurations exist to demonstrate
# that a stated assumption is load-bearing, or that a liveness antecedent is
# reachable, and each of those is only evidence if it really does produce a
# counterexample.  A configuration marked
# "EXPECT: fail" that passes is reported as an ERROR here, not as good news --
# it means either the assumption was never load-bearing or the model stopped
# modelling the thing that depends on it.
#
# Each .cfg declares its own expectation on its first line:
#     \* EXPECT: pass
#     \* EXPECT: fail <PropertyOrInvariantName>
#
# This script is NOT wired into CI in this pass (WS-7 task 7.2 is deferred).
# It lives in scripts/ because its output is load-bearing -- the numbers it
# prints are the ones quoted in formal/README.md and, later, in the paper --
# and docs/26 section 3 rule 14 says such a thing is committed and pinned
# rather than re-typed by hand.
#
# Usage:
#   scripts/run_tlc.sh                 # every configuration
#   scripts/run_tlc.sh base aof-rewind # named configurations only
#
# Requires: a JRE and tla2tools.jar.  Override the jar with TLA_TOOLS=/path.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAL="$ROOT/formal"
TLA_TOOLS="${TLA_TOOLS:-/opt/tla/tla2tools.jar}"
WORKERS="${TLC_WORKERS:-4}"
TIMEOUT="${TLC_TIMEOUT:-1800}"

if ! command -v java >/dev/null 2>&1; then
    echo "FATAL: no java on PATH; TLC cannot run" >&2
    exit 2
fi
if [ ! -f "$TLA_TOOLS" ]; then
    echo "FATAL: tla2tools.jar not found at $TLA_TOOLS (set TLA_TOOLS=)" >&2
    exit 2
fi

# TLC names a violated INVARIANT inline ("Error: Invariant X is violated") but
# reports only "Temporal properties were violated" without saying which.  To
# name it, re-check each temporal property on its own against a derived config
# with the invariants stripped, and return the first that breaks.  Failing
# configurations reach their counterexample in seconds, so the extra runs are
# cheap; this never runs for a configuration that passes.
_tlc_which_temporal() {
    local name="$1" formal="$2" logdir="$3"
    local cfg="$formal/configs/$name.cfg"
    local props
    props="$(sed -n '/^PROPERTIES/,$p' "$cfg" | tail -n +2 | tr -d ' \r' | grep -v '^$')"
    local hit=""
    local p
    for p in $props; do
        local derived="$logdir/${name}__${p}.cfg"
        awk '/^SPECIFICATION/{f=1} /^INVARIANTS/||/^PROPERTIES/{f=0} f' "$cfg" >"$derived"
        printf 'PROPERTIES\n    %s\n' "$p" >>"$derived"
        ( cd "$formal" && timeout "$TIMEOUT" java -XX:+UseParallelGC \
            -cp "$TLA_TOOLS" tlc2.TLC -config "$derived" \
            -metadir "$logdir/meta/${name}__${p}" \
            -workers "$WORKERS" -cleanup AEP.tla \
            >"$logdir/${name}__${p}.log" 2>&1 )
        if ! grep -q "No error has been found" "$logdir/${name}__${p}.log"; then
            hit="${hit:+$hit,}$p"
        fi
    done
    printf '%s' "${hit:-UNIDENTIFIED}"
}

if [ "$#" -gt 0 ]; then
    NAMES=("$@")
else
    NAMES=()
    for f in "$FORMAL"/configs/*.cfg; do
        NAMES+=("$(basename "$f" .cfg)")
    done
fi

LOGDIR="${TLC_LOGDIR:-$(mktemp -d)}"
mkdir -p "$LOGDIR"
echo "TLC $(java -cp "$TLA_TOOLS" tlc2.TLC 2>&1 | head -1)"
echo "logs: $LOGDIR"
echo

failures=0
printf '%-30s %-28s %-28s %8s %10s  %s\n' \
    CONFIG EXPECTED ACTUAL STATES DEPTH VERDICT

for name in "${NAMES[@]}"; do
    cfg="$FORMAL/configs/$name.cfg"
    if [ ! -f "$cfg" ]; then
        echo "FATAL: no such configuration: $cfg" >&2
        exit 2
    fi

    # The expectation is the first line of the config, so it cannot drift away
    # from the constants it is an expectation about.
    # tr -d '\r': these files are edited on Windows as well as Linux, and a
    # trailing CR turns an exact expectation match into a silent mismatch --
    # which showed up here as a WRONG-REASON verdict on a config that had
    # failed for precisely the declared reason.
    expect_line="$(head -1 "$cfg" | tr -d '\r')"
    case "$expect_line" in
        *"EXPECT: pass"*) expect="pass"; expect_what="" ;;
        *"EXPECT: fail "*) expect="fail"; expect_what="${expect_line##*EXPECT: fail }" ;;
        *) echo "FATAL: $name.cfg has no EXPECT line" >&2; exit 2 ;;
    esac

    log="$LOGDIR/$name.log"
    # -metadir gives each configuration its own working directory.  Without it
    # TLC writes states/ relative to the module, so two runs in this directory
    # delete each other's fingerprint files and one dies with an IOException
    # that looks nothing like a model-checking result.  That happened here once
    # already, and a future parallel CI job would hit it every time.
    ( cd "$FORMAL" && timeout "$TIMEOUT" java -XX:+UseParallelGC \
        -cp "$TLA_TOOLS" tlc2.TLC \
        -config "configs/$name.cfg" -metadir "$LOGDIR/meta/$name" \
        -workers "$WORKERS" -cleanup AEP.tla \
        >"$log" 2>&1 )
    rc=$?

    if [ "$rc" -eq 124 ]; then
        actual="timeout after ${TIMEOUT}s"; what=""
    elif grep -q "No error has been found" "$log"; then
        actual="pass"; what=""
    elif grep -q "^Error: Invariant" "$log"; then
        what="$(grep -m1 "^Error: Invariant" "$log" | sed 's/^Error: Invariant //; s/ is violated.*//')"
        actual="fail"
    elif grep -q "^Error: Temporal properties were violated" "$log"; then
        # TLC names the invariant inline but not the temporal property, so
        # re-run each temporal property alone to find out which one broke.
        what="$(_tlc_which_temporal "$name" "$FORMAL" "$LOGDIR")"
        actual="fail"
    elif grep -q "^Error: Action property" "$log"; then
        what="$(grep -m1 "^Error: Action property" "$log" | sed 's/^Error: Action property //; s/ is violated.*//')"
        actual="fail"
    else
        actual="ERROR (see log)"; what=""
    fi

    # Distinct states, not states generated: the generated count includes every
    # re-derivation of an already-seen state and so says more about the search
    # order than about the model.
    states="$(grep -oE '[0-9]+ distinct states found' "$log" | tail -1 | grep -oE '^[0-9]+')"
    depth="$(grep -oE 'depth of the complete state graph search is [0-9]+' "$log" \
             | tail -1 | grep -oE '[0-9]+$')"

    verdict="OK"
    if [ "$actual" != "$expect" ]; then
        verdict="UNEXPECTED"
        failures=$((failures + 1))
    elif [ "$expect" = "fail" ] && [ -n "$expect_what" ] && [ "$what" != "$expect_what" ]; then
        # Failing is not enough: it has to fail for the declared reason.  A
        # config that fails on a different property is not the evidence the
        # README says it is.
        verdict="WRONG-REASON"
        failures=$((failures + 1))
    fi

    printf '%-30s %-28s %-28s %8s %10s  %s\n' \
        "$name" "$expect${expect_what:+ $expect_what}" \
        "$actual${what:+ $what}" "${states:--}" "${depth:--}" "$verdict"
done

echo
if [ "$failures" -ne 0 ]; then
    echo "$failures configuration(s) did not match their declared expectation."
    echo "Logs are in $LOGDIR"
    exit 1
fi
echo "all ${#NAMES[@]} configuration(s) matched their declared expectation"
