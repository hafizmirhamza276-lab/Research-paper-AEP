#!/usr/bin/env bash
# The barrier's cost is a property of a durability configuration, not of AEP.
#
# Amendment F0(iii): run one crash-free AEP-full configuration against a Redis
# with `appendfsync always`, so the paper can state the barrier cost as a
# function of the durability setting rather than as one large number. The
# `everysec` figure it is compared against is the same cell -- same system,
# same endpoint, same seeds, same executions -- already collected in the main
# matrix, so the only variable is the fsync policy.
#
# Three things this script refuses to do:
#
#   1. Touch the matrix's Redis. It starts a SECOND container on a different
#      port with its own volume. The main instance is left alone, because a
#      `CONFIG SET appendfsync always` on it would silently change the
#      durability policy under every other result in the paper.
#
#   2. Write into the frozen results tree. Its results root is separate.
#
#   3. Measure a configuration it did not actually get. It reads
#      `CONFIG GET appendfsync` back from the running server and exits
#      non-zero unless the answer is literally `always`. A benchmark that
#      reports a number for a setting it failed to apply is worse than no
#      benchmark.
#
# Usage (from the repository root, on the Linux measurement host):
#   AEP_HARNESS_SUSPEND_DISABLED=1 bash scripts/fsync_always_benchmark.sh
set -euo pipefail

# Same image digest as compose.phase2.yml -- a different Redis build would
# make the comparison meaningless.
IMAGE="redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44"
NAME="aep-fsync-always"
PORT="6383"
RESULTS_ROOT="experiments/results/fsync-always"

# The config the container must actually load.
#
# Two attempts failed here and both failed *silently at the Docker layer*: the
# container started, found nothing at the mount point, and came up on the
# compiled-in defaults (`appendfsync everysec`, `appendonly no`). Only the
# gate below noticed.
#
# The cause is that this Docker Desktop resolves bind-mount sources in the
# Windows filesystem, not in the WSL distro's. The matrix's own Redis proves
# it -- `docker inspect aep-phase2-redis72` reports its source as
# `D:\...\Research-paper-AEP\redis\phase2.conf`, a Windows path, even though
# the harness driving it runs inside WSL. A source under the distro's `/root`
# or `/tmp` does not exist as far as the daemon is concerned.
#
# And `/mnt/d/...` is not it either: mounting that produced an empty directory
# at the destination, the daemon's way of saying it could not resolve the
# source. This `docker` is a wrapper forwarding to `docker.exe`, so the source
# must be a *Windows* path.
#
# Two variables, because the shell and the daemon do not agree on what a path
# is. CONF_LOCAL is what this script reads (POSIX, for the diff and the
# existence check); AEP_DOCKER_CONF is what the daemon mounts. They must name
# the same file, and the config gate below is what proves they did.
CONF_LOCAL="${AEP_CONF_LOCAL:-$(pwd)/redis/phase2-always.conf}"
CONF="${AEP_DOCKER_CONF:-${CONF_LOCAL}}"

# Amendment G1 needs a second row in this cell: the same crash-free
# configuration with the barrier ablated, under the same fsync policy. Without
# it, "the barrier costs X under always" has to be computed by subtracting a
# B3 median measured under *everysec*, which silently assumes the ablated
# protocol's own writes cost the same under both policies -- an assumption,
# not a measurement, sitting underneath a headline number.
#
# So the system list is a variable, and a second invocation can append to the
# same results root instead of replacing it.
SYSTEMS="${AEP_FSYNC_SYSTEMS:-AEP_FULL}"
MOCK_PORT="${AEP_FSYNC_MOCK_PORT:-8098}"
CLEAN="${AEP_FSYNC_CLEAN:-1}"

echo "=============================================================="
echo "F0(iii)  barrier latency under appendfsync=always"
echo "=============================================================="
echo

# ---------------------------------------------------------------- teardown
cleanup() {
  echo
  echo "--- teardown ---"
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
  echo "removed ${NAME}"
}
trap cleanup EXIT

docker rm -f "${NAME}" >/dev/null 2>&1 || true

# ---------------------------------------------------------- the config file
if [ ! -f "${CONF_LOCAL}" ]; then
  echo "missing ${CONF_LOCAL}" >&2
  exit 1
fi

echo "--- config under test ---"
echo "read by this script : ${CONF_LOCAL}"
echo "mounted by docker   : ${CONF}"
echo
echo "--- the only line that differs from redis/phase2.conf ---"
diff <(grep -vE '^#|^$' redis/phase2.conf) \
     <(grep -vE '^#|^$' "${CONF_LOCAL}") || true
echo

# ------------------------------------------------------------------ start
echo "--- starting ${NAME} on 127.0.0.1:${PORT} ---"
docker run -d --name "${NAME}" \
  -p "127.0.0.1:${PORT}:6379" \
  -v "${CONF}:/usr/local/etc/redis/redis.conf:ro" \
  "${IMAGE}" \
  redis-server /usr/local/etc/redis/redis.conf >/dev/null

for _ in $(seq 1 30); do
  if docker exec "${NAME}" redis-cli PING 2>/dev/null | grep -q PONG; then break; fi
  sleep 1
done

# ------------------------------------------------- the gate: did it apply?
echo
echo "--- verifying the server is actually running the policy under test ---"
echo '$ redis-cli CONFIG GET appendfsync'
ACTUAL="$(docker exec "${NAME}" redis-cli CONFIG GET appendfsync | tail -1 | tr -d '\r')"
echo "appendfsync = ${ACTUAL}"
echo '$ redis-cli CONFIG GET appendonly'
docker exec "${NAME}" redis-cli CONFIG GET appendonly | tail -1
echo '$ redis-cli INFO server | grep redis_version'
docker exec "${NAME}" redis-cli INFO server | grep -E "redis_version|run_id" | tr -d '\r'

if [ "${ACTUAL}" != "always" ]; then
  echo
  echo "REFUSING TO MEASURE: appendfsync is '${ACTUAL}', not 'always'." >&2
  exit 1
fi
echo "gate passed."
echo

# ------------------------------------------------- the disposability marker
# Phase 2A replaced the test fixture's FLUSHALL with a guard: the harness
# refuses to run against a Redis that has not asserted it is disposable,
# because it kills processes holding leases on that instance and deletes the
# keys it created. A fresh throwaway container has to opt in explicitly, and
# that opt-in is recorded here rather than buried, because the guard existing
# is a property the artifact claims.
echo "--- marking the throwaway instance disposable (Phase 2A guard) ---"
echo '$ redis-cli -n 15 SET aep:test-instance-marker 1'
docker exec "${NAME}" redis-cli -n 15 SET aep:test-instance-marker 1
echo

# --------------------------------------------------------------- the cell
echo "--- the cell: ${SYSTEMS}, crash-free (p0), payments, 3 runs x 10 exec ---"
echo "    identical to the everysec cells of the same systems"
echo "    (same matrix seed, so the per-run seeds are the same)"
echo
if [ "${CLEAN}" = "1" ]; then
  rm -rf "${RESULTS_ROOT}"
else
  echo "    appending to ${RESULTS_ROOT} (AEP_FSYNC_CLEAN=0)"
fi
SYSTEM_FLAGS=()
for system in ${SYSTEMS}; do
  SYSTEM_FLAGS+=(--system "${system}")
done
set -x
uv run --frozen python -m experiments.run_matrix \
  --regime p0 \
  "${SYSTEM_FLAGS[@]}" \
  --endpoint payments \
  --redis-url "redis://127.0.0.1:${PORT}/15" \
  --results-root "${RESULTS_ROOT}" \
  --resume \
  --port "${MOCK_PORT}"
set +x

# ------------------------------------------------------------- the numbers
echo
echo "--- analysis of the appendfsync=always cell ---"
uv run --frozen python -m experiments.analyze \
  --results-root "${RESULTS_ROOT}" \
  --destination "${RESULTS_ROOT}/analysis"

echo
echo "--- side by side ---"
uv run --frozen python scripts/fsync_compare.py \
  --always "${RESULTS_ROOT}/analysis/latency-and-throughput.csv" \
  --everysec experiments/results/matrix/analysis/latency-and-throughput.csv
