#!/usr/bin/env bash
# Phase 8.4 per-session container precondition.
#
# Why this exists. The first attempt at session 2 died at run 25 when the WSL
# distro stopped underneath it, and a foreign container (komserv-pg-race) was
# found running in the Docker Desktop VM alongside the AEP fixtures. That VM's
# load is the blind spot 9C section 6 named: the harness cannot see it, and it
# sits on the critical path of the `docker kill` latency the whole phase turns
# on.
#
# What is a fixture and what is residue. aep-phase2-redis72 and
# aep-phase2-toxiproxy are declared by compose.phase2.yml and are part of the
# run -- the harness kills and starts the Redis container as the fault
# injection itself. They are NOT cleaned. Recreating them per session would
# make session 1 differ from sessions 2-4 by construction, which is the exact
# defect the interleaving redesign existed to remove.
#
# Anything else running is foreign load. It is RECORDED BY NAME and then
# stopped (not removed -- stopping is reversible and it is not this project's
# container to delete). The names matter more than the removal: container_state
# in run-config.json covers the AEP container only, so foreign load reaches no
# other artefact, and if a session shows a drift anomaly this snapshot is the
# first place to look.
#
# Usage: precondition.sh <absolute run root>

set -uo pipefail

ROOT="${1:?usage: precondition.sh <absolute run root>}"
EXPECTED=("aep-phase2-redis72" "aep-phase2-toxiproxy")

is_expected() {
    local name="$1"
    for e in "${EXPECTED[@]}"; do
        [ "$name" = "$e" ] && return 0
    done
    return 1
}

snapshot() {
    # name<TAB>state<TAB>status<TAB>image, all containers including stopped
    docker ps -a --format '{{.Names}}\t{{.State}}\t{{.Status}}\t{{.Image}}' 2>/dev/null
}

mkdir -p "$ROOT"

BEFORE="$(snapshot)"
VOLUMES_BEFORE="$(docker volume ls -q 2>/dev/null | wc -l)"
LOAD_BEFORE="$(cat /proc/loadavg)"

# Foreign == running, and not one of the two declared fixtures.
FOREIGN=()
while IFS=$'\t' read -r name state status image; do
    [ -z "${name:-}" ] && continue
    [ "$state" != "running" ] && continue
    if ! is_expected "$name"; then
        FOREIGN+=("$name|$image|$status")
    fi
done <<< "$BEFORE"

STOPPED=()
for entry in "${FOREIGN[@]:-}"; do
    [ -z "$entry" ] && continue
    name="${entry%%|*}"
    if docker stop "$name" >/dev/null 2>&1; then
        STOPPED+=("$name")
    fi
done

# Let the VM settle after stopping anything, so the "after" load is meaningful.
# NB: ${#ARR[@]:-0} is not valid bash -- it is a "bad substitution", the test
# never runs, and under `if` that reads as false rather than as an error. That
# silently disabled the fixtures-missing gate below on the first use of this
# script. Empty arrays are safe under `set -u` on bash 4.4+, so the length is
# taken directly.
if [ "${#STOPPED[@]}" -gt 0 ]; then
    sleep 10
fi

AFTER="$(snapshot)"
VOLUMES_AFTER="$(docker volume ls -q 2>/dev/null | wc -l)"
LOAD_AFTER="$(cat /proc/loadavg)"

# Both fixtures must be present (running or stopped -- the harness starts Redis
# itself). Absence means the compose stack is not up and the session must not
# proceed.
MISSING=()
for e in "${EXPECTED[@]}"; do
    if ! grep -qP "^${e}\t" <<< "$AFTER"; then
        MISSING+=("$e")
    fi
done

export SNAP_BEFORE="$BEFORE"
export SNAP_AFTER="$AFTER"
export SNAP_FOREIGN="$(printf '%s\n' "${FOREIGN[@]:-}")"
export SNAP_STOPPED="$(printf '%s\n' "${STOPPED[@]:-}")"
export SNAP_MISSING="$(printf '%s\n' "${MISSING[@]:-}")"

python3 - "$ROOT" "$VOLUMES_BEFORE" "$VOLUMES_AFTER" "$LOAD_BEFORE" "$LOAD_AFTER" <<'PY'
import json, os, subprocess, sys

root, vol_before, vol_after, load_before, load_after = sys.argv[1:6]

def table(raw):
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        while len(parts) < 4:
            parts.append("")
        out.append({"name": parts[0], "state": parts[1],
                    "status": parts[2], "image": parts[3]})
    return out

before = table(os.environ.get("SNAP_BEFORE", ""))
after = table(os.environ.get("SNAP_AFTER", ""))
foreign = [e for e in os.environ.get("SNAP_FOREIGN", "").split("\n") if e]
stopped = [e for e in os.environ.get("SNAP_STOPPED", "").split("\n") if e]
missing = [e for e in os.environ.get("SNAP_MISSING", "").split("\n") if e]

record = {
    "schema": "aep.phase8.container-precondition/1",
    "captured_at": subprocess.run(
        ["date", "-Iseconds"], capture_output=True, text=True).stdout.strip(),
    "expected_fixtures": ["aep-phase2-redis72", "aep-phase2-toxiproxy"],
    "fixtures_missing": missing,
    "foreign_running_before": [
        dict(zip(("name", "image", "status"), e.split("|"))) for e in foreign
    ],
    "foreign_stopped": stopped,
    "containers_before": before,
    "containers_after": after,
    "volume_count_before": int(vol_before),
    "volume_count_after": int(vol_after),
    "loadavg_before": load_before.strip(),
    "loadavg_after": load_after.strip(),
    "note": (
        "Fixtures are declared by compose.phase2.yml and are part of the run; "
        "they are never cleaned, because recreating them per session would make "
        "session 1 differ from sessions 2-4 by construction. Foreign containers "
        "are recorded by name and stopped, not removed. container_state in "
        "run-config.json covers the AEP Redis container only, so foreign load "
        "reaches no other artefact in the run root."
    ),
}

path = os.path.join(root, "container-precondition.json")
with open(path, "w", newline="\n") as fh:
    json.dump(record, fh, indent=2, sort_keys=False)
    fh.write("\n")
print(path)
PY

echo "--- precondition summary ---"
echo "foreign running before : ${#FOREIGN[@]}"
for entry in "${FOREIGN[@]:-}"; do [ -n "$entry" ] && echo "    $entry"; done
echo "foreign stopped        : ${STOPPED[*]:-none}"
echo "fixtures missing       : ${MISSING[*]:-none}"
echo "volumes                : $VOLUMES_BEFORE -> $VOLUMES_AFTER"
echo "loadavg before/after   : $LOAD_BEFORE  /  $LOAD_AFTER"

if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "PRECONDITION FAILED: compose fixtures absent: ${MISSING[*]}"
    exit 2
fi

exit 0
