#!/usr/bin/env bash
# Sample the Docker VM's container set every 60 s for the duration of the
# Phase 8.4 collection.
#
# Why this exists, and why it was added mid-collection. The per-session
# container precondition is a snapshot at t=0. Session 2's precondition
# correctly recorded `foreign_running_before: []` -- the VM really was clean at
# 14:45:52 -- and two foreign postgres containers then appeared DURING the
# session and were only discovered 43 minutes after it ended, by session 3's
# precondition catching them still up. Both were removed within four minutes of
# being stopped, so the evidence about session 2 is unrecoverable.
#
# A start-of-session snapshot can establish "the VM was clean when this session
# began". It cannot establish "the VM was clean while this session ran", and for
# a phase whose estimand turns on `docker kill` latency that is the wrong
# boundary.
#
# This is ADDITIVE OBSERVATION ONLY. It touches no registered gate, changes no
# collection condition, and nothing downstream reads it. It runs `docker ps`,
# which does not interact with the fixtures. Sessions 3 and 4 therefore get the
# evidence session 2 could not have; session 2 does not retroactively gain it,
# and 8.6 must say so rather than presenting the three sessions as uniformly
# instrumented.
#
# Writes one JSON object per sample to a continuous log. finish_session.sh
# slices it per session by that session's own collection window.
#
# Usage: load_sampler.sh <output jsonl> [interval seconds]

set -uo pipefail

OUT="${1:?usage: load_sampler.sh <output jsonl> [interval]}"
INTERVAL="${2:-60}"
FIXTURES="aep-phase2-redis72 aep-phase2-toxiproxy"

mkdir -p "$(dirname "$OUT")"

while true; do
    TS=$(date -Iseconds)
    # -a so a container that has already exited is still seen; foreign load here
    # is ephemeral and a running-only view misses most of it.
    PS=$(docker ps -a --format '{{.Names}}|{{.State}}|{{.Status}}|{{.Image}}' 2>/dev/null)
    LOAD=$(cat /proc/loadavg 2>/dev/null | cut -d' ' -f1-3)

    # The container table goes through the environment, not stdin: the heredoc
    # already owns stdin, and two redirections silently leave one unread.
    export SAMPLE_PS="$PS"
    python3 - "$TS" "$OUT" "$LOAD" "$FIXTURES" <<'PY' 2>/dev/null || true
import json, os, sys
ts, out, load, fixtures = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split()
rows = []
for line in os.environ.get("SAMPLE_PS", "").splitlines():
    if not line.strip():
        continue
    parts = (line.split("|") + ["", "", "", ""])[:4]
    rows.append({"name": parts[0], "state": parts[1],
                 "status": parts[2], "image": parts[3]})
foreign = [r for r in rows if r["name"] not in fixtures]
rec = {
    "t": ts,
    "loadavg": load,
    "containers": len(rows),
    "running": sum(1 for r in rows if r["state"] == "running"),
    "foreign": foreign,
    "foreign_running": [r["name"] for r in foreign if r["state"] == "running"],
}
with open(out, "a", newline="\n") as fh:
    fh.write(json.dumps(rec) + "\n")
PY
    sleep "$INTERVAL"
done
