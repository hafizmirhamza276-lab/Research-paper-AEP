#!/usr/bin/env bash
# Run the remaining sessions back to back, sequentially, halting the whole chain
# on the first failure.
#
# There is ONE watcher, and it is this script: it runs each session in the
# foreground and reads its exit code directly. No pgrep, no polling, no second
# observer.
#
# What went wrong before, because it is the reason this file exists. The watcher
# was:
#
#     while pgrep -f "run_session.sh b2-paired-v2-s2-2026-08-28"; do sleep 60; done
#
# That pattern is a substring of the watcher's own command line, so `pgrep -f`
# matched the watcher itself. The condition could never become false, the loop
# could never exit, and the chain could never advance -- and running two of them
# only guaranteed each also matched the other. It is the same class as B11's
# ${#ARRAY[@]:-0}: that always read false, this always read true, and neither
# could ever act. A watcher whose exit path is never exercised is untested in
# precisely the way B11 names.
#
# Usage: run_chain.sh <slug> [<slug> ...]

set -uo pipefail

DRIVER=/root/phase8-driver

for SLUG in "$@"; do
    echo
    echo "##############################################################"
    echo "# chain: starting ${SLUG} at $(date -Iseconds)"
    echo "##############################################################"

    rm -f "${DRIVER}/${SLUG}.done"

    bash "${DRIVER}/run_session.sh" "$SLUG"
    RC=$?

    if [ "$RC" -ne 0 ]; then
        echo
        echo "##############################################################"
        echo "# chain HALTED: ${SLUG} exited ${RC}"
        echo "# Remaining sessions are NOT started. Nothing is retried."
        echo "##############################################################"
        exit "$RC"
    fi

    if [ ! -f "${DRIVER}/${SLUG}.done" ]; then
        echo "chain HALTED: ${SLUG} exited 0 but wrote no sentinel"
        exit 30
    fi

    echo "# chain: ${SLUG} complete at $(cat "${DRIVER}/${SLUG}.done")"
done

echo
echo "##############################################################"
echo "# chain complete: $* "
echo "##############################################################"
date -Iseconds > "${DRIVER}/chain.done"
exit 0
