#!/usr/bin/env bash
# Put the container runtime in the same namespace as the block devices.
#
# Phase 10 / WS-0. `docs/24-revision-backlog.md` B1 records that backlog item
# B1 was blocked by a *resolution failure in the container runtime*, not by
# WSL2: Docker Desktop's daemon resolves bind-mount sources in the Windows
# filesystem, so `docker inspect aep-phase2-redis72` reports
#
#     "Source": "D:\\personal\\AEP\\Research-paper-AEP\\redis\\phase2.conf"
#
# even though the harness driving it runs inside the distro. A `dm-flakey`
# device assembled inside WSL exists only at a WSL path and therefore cannot be
# named as a bind source. `reports/phase-report-10-env-before.md` §1 holds that
# inspect output verbatim, and §5 holds the sharper form of the same fact:
# **`/var/lib/docker` does not exist inside `Ubuntu-24.04` at all.** The loop
# device, the dm target and the ext4 filesystem live in this distro; Redis's
# `/data` lives in Docker Desktop's VM. Two namespaces.
#
# This script installs Docker Engine natively *in the distro*, so there is one.
#
# **It does not uninstall Docker Desktop, and it does not disable it.** Docker
# Desktop stays installed and startable, because Phase 10 has to measure the
# `docker kill` latency of *both* runtimes and every number in the paper was
# collected on the Docker Desktop one. What changes is which daemon the name
# `docker` reaches, and that change is made in two auditable places:
#
#   1. `/usr/local/bin/docker` -- the hand-written shim from
#      `scripts/wsl_docker_shim.sh` that `cd`s to /mnt/d and `exec`s
#      `docker.exe` -- is **renamed**, not deleted, to
#      `/usr/local/bin/docker-desktop-shim`. `/usr/bin/docker` (the native CLI)
#      then wins on PATH. Rollback is one `mv`.
#   2. A docker context named `aep-native` is created and selected, so the
#      endpoint in use is a stated fact (`docker context show`) rather than an
#      inference from PATH.
#
# Idempotent and non-interactive: safe to re-run. Every version it installs is
# pinned to an exact apt version string and echoed.
#
# Usage:
#     sudo bash scripts/provision_wsl2_native_docker.sh --match-server-version 29.4.3
#     sudo bash scripts/provision_wsl2_native_docker.sh --docker-version '5:29.4.3-1~ubuntu.24.04~noble'
#     sudo bash scripts/provision_wsl2_native_docker.sh --list-available
#
# `--match-server-version` is the Phase 10 path: it pins the native engine to
# the version Docker Desktop was serving, so the runtime-confound replication
# differs in *where the daemon lives* and not in *which daemon it is*. When that
# version is absent from the repo the script does not silently drift -- it
# prints the gap, installs the nearest, and records both, because the delta is a
# limitation of the confound test and not a footnote.

set -euo pipefail

# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------
MATCH_SERVER_VERSION=""
DOCKER_VERSION=""
LIST_ONLY=0
CONTEXT_NAME="${AEP_DOCKER_CONTEXT:-aep-native}"
SHIM="/usr/local/bin/docker"
SHIM_PRESERVED="/usr/local/bin/docker-desktop-shim"
REPO_TREE="${AEP_REPO_TREE:-/mnt/d/personal/AEP/Research-paper-AEP}"
CANARY_WSL_DIR="/root/aep-phase10-canary"
CANARY_DRVFS_DIR="${REPO_TREE}/.scratch/phase10-canary"
RECORD="${AEP_PROVISION_RECORD:-/root/phase10/provision-record.json}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --match-server-version) MATCH_SERVER_VERSION="$2"; shift 2 ;;
    --docker-version)       DOCKER_VERSION="$2";       shift 2 ;;
    --list-available)       LIST_ONLY=1;               shift   ;;
    --context)              CONTEXT_NAME="$2";         shift 2 ;;
    -h|--help)              sed -n '1,60p' "$0";       exit 0  ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" != "0" ]]; then
  echo "REFUSING: this installs packages and manages a daemon; run as root." >&2
  exit 2
fi

step() { printf '\n=== %s ===\n' "$1"; }

step "host"
echo "kernel        $(uname -r)"
echo "distro        $(. /etc/os-release && echo "$PRETTY_NAME  codename=$VERSION_CODENAME")"
echo "pid 1         $(ps -p 1 -o comm=)"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"

# --------------------------------------------------------------------------
# 1. Docker's apt repository
# --------------------------------------------------------------------------
step "apt repository"
install -m 0755 -d /etc/apt/keyrings
if [[ ! -s /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "installed /etc/apt/keyrings/docker.asc"
else
  echo "/etc/apt/keyrings/docker.asc already present"
fi
echo "keyring sha256 $(sha256sum /etc/apt/keyrings/docker.asc | cut -d' ' -f1)"

ARCH="$(dpkg --print-architecture)"
SOURCE_LINE="deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable"
if [[ ! -f /etc/apt/sources.list.d/docker.list ]] \
   || ! grep -qxF "$SOURCE_LINE" /etc/apt/sources.list.d/docker.list; then
  echo "$SOURCE_LINE" > /etc/apt/sources.list.d/docker.list
  echo "wrote /etc/apt/sources.list.d/docker.list"
else
  echo "/etc/apt/sources.list.d/docker.list already correct"
fi
cat /etc/apt/sources.list.d/docker.list

apt-get update -qq

# --------------------------------------------------------------------------
# 2. Choose the pin
# --------------------------------------------------------------------------
step "available docker-ce versions"
MADISON="$(apt-cache madison docker-ce || true)"
echo "$MADISON"

if [[ "$LIST_ONLY" == "1" ]]; then
  exit 0
fi

available_versions() {
  awk -F'|' '{gsub(/ /,"",$2); if ($2 != "") print $2}' <<<"$MADISON"
}

MATCH_STATUS="not-requested"
if [[ -z "$DOCKER_VERSION" && -n "$MATCH_SERVER_VERSION" ]]; then
  # Repo versions look like `5:29.4.3-1~ubuntu.24.04~noble`. Match the upstream
  # part exactly -- anchored, so 29.4.3 cannot select 29.4.30.
  DOCKER_VERSION="$(available_versions \
    | grep -E "^[0-9]+:${MATCH_SERVER_VERSION//./\\.}-" | head -1 || true)"
  if [[ -n "$DOCKER_VERSION" ]]; then
    MATCH_STATUS="exact"
    echo "MATCHED Docker Desktop server ${MATCH_SERVER_VERSION} -> ${DOCKER_VERSION}"
  else
    DOCKER_VERSION="$(available_versions | head -1 || true)"
    MATCH_STATUS="nearest"
    echo
    echo "############################################################"
    echo "# Docker Desktop serves ${MATCH_SERVER_VERSION}, which this repo does NOT offer."
    echo "# Installing the nearest available: ${DOCKER_VERSION}"
    echo "# This version delta is a LIMITATION OF THE RUNTIME-CONFOUND TEST."
    echo "# It must be stated in the phase report, not footnoted."
    echo "############################################################"
    echo
  fi
fi
if [[ -z "$DOCKER_VERSION" ]]; then
  DOCKER_VERSION="$(available_versions | head -1 || true)"
  MATCH_STATUS="newest"
fi
[[ -n "$DOCKER_VERSION" ]] || { echo "REFUSING: no docker-ce candidate found." >&2; exit 1; }

# containerd.io is versioned independently of docker-ce; pin it to the newest
# the repo offers rather than inventing a correspondence that does not exist.
CONTAINERD_VERSION="$(apt-cache madison containerd.io \
  | awk -F'|' '{gsub(/ /,"",$2); if ($2 != "") print $2}' | head -1)"
CLI_VERSION="$DOCKER_VERSION"
BUILDX_VERSION="$(apt-cache madison docker-buildx-plugin \
  | awk -F'|' '{gsub(/ /,"",$2); if ($2 != "") print $2}' | head -1)"
COMPOSE_VERSION="$(apt-cache madison docker-compose-plugin \
  | awk -F'|' '{gsub(/ /,"",$2); if ($2 != "") print $2}' | head -1)"

step "the pins this run will install"
echo "docker-ce             ${DOCKER_VERSION}   (match: ${MATCH_STATUS}${MATCH_SERVER_VERSION:+, target ${MATCH_SERVER_VERSION}})"
echo "docker-ce-cli         ${CLI_VERSION}"
echo "containerd.io         ${CONTAINERD_VERSION}"
echo "docker-buildx-plugin  ${BUILDX_VERSION}"
echo "docker-compose-plugin ${COMPOSE_VERSION}"

# --------------------------------------------------------------------------
# 3. Install
# --------------------------------------------------------------------------
step "install"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq \
  "docker-ce=${DOCKER_VERSION}" \
  "docker-ce-cli=${CLI_VERSION}" \
  "containerd.io=${CONTAINERD_VERSION}" \
  "docker-buildx-plugin=${BUILDX_VERSION}" \
  "docker-compose-plugin=${COMPOSE_VERSION}"
# Hold them: an unattended upgrade that moved the engine mid-collection would
# change the runtime between two runs of the same cell and nothing downstream
# would see it.
apt-mark hold docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin >/dev/null
echo "held: $(apt-mark showhold | tr '\n' ' ')"
echo "installed docker-ce   $(dpkg-query -W -f='${Version}' docker-ce)"
echo "installed containerd  $(dpkg-query -W -f='${Version}' containerd.io)"
echo "native CLI at         $(ls -la /usr/bin/docker)"

# --------------------------------------------------------------------------
# 4. Start the daemon. systemd if it is PID 1, a supervised dockerd if not.
# --------------------------------------------------------------------------
step "daemon"
START_PATH="unknown"
if [[ "$(ps -p 1 -o comm=)" == "systemd" ]]; then
  START_PATH="systemd"
  systemctl enable --now docker.service containerd.service
  systemctl is-active docker.service && echo "docker.service active"
else
  # The prompt asks for this branch explicitly. It is not exercised on this
  # host -- systemd IS PID 1 here (reports/phase-report-10-env-before.md §3) --
  # and it is kept so the script provisions a distro where systemd is off.
  START_PATH="dockerd-nohup"
  if ! pgrep -x dockerd >/dev/null; then
    mkdir -p /var/log/aep
    nohup dockerd >>/var/log/aep/dockerd.log 2>&1 &
    echo "started dockerd without systemd, log /var/log/aep/dockerd.log"
  else
    echo "dockerd already running"
  fi
fi
echo "START PATH TAKEN: ${START_PATH}"

for _ in $(seq 1 60); do
  [[ -S /var/run/docker.sock ]] && break
  sleep 1
done
[[ -S /var/run/docker.sock ]] || {
  echo "REFUSING: /var/run/docker.sock never appeared." >&2; exit 1; }
ls -la /var/run/docker.sock

# --------------------------------------------------------------------------
# 5. Move the Docker Desktop shim aside -- reversibly
# --------------------------------------------------------------------------
step "Docker Desktop shim"
if [[ -f "$SHIM" ]] && ! [[ -L "$SHIM" ]] && grep -q 'docker.exe' "$SHIM" 2>/dev/null; then
  mv "$SHIM" "$SHIM_PRESERVED"
  echo "moved ${SHIM} -> ${SHIM_PRESERVED} (preserved, not deleted)"
elif [[ -f "$SHIM_PRESERVED" ]]; then
  echo "${SHIM_PRESERVED} already in place; ${SHIM} $( [[ -e $SHIM ]] && echo exists || echo absent )"
else
  echo "no Docker Desktop shim at ${SHIM}; nothing to move"
fi
echo "ROLLBACK: mv ${SHIM_PRESERVED} ${SHIM}"
echo "docker now resolves to: $(command -v docker)"
hash -r 2>/dev/null || true

# --------------------------------------------------------------------------
# 6. The context. Explicit, so the endpoint is stated rather than inferred.
# --------------------------------------------------------------------------
step "context ${CONTEXT_NAME}"
unset DOCKER_HOST || true
if /usr/bin/docker context inspect "$CONTEXT_NAME" >/dev/null 2>&1; then
  echo "context ${CONTEXT_NAME} already exists"
else
  /usr/bin/docker context create "$CONTEXT_NAME" \
    --description "Phase 10: native Docker Engine inside Ubuntu-24.04 (WS-0)" \
    --docker host=unix:///var/run/docker.sock
fi
/usr/bin/docker context use "$CONTEXT_NAME"
/usr/bin/docker context ls
ENDPOINT="$(/usr/bin/docker context inspect "$CONTEXT_NAME" \
  --format '{{.Endpoints.docker.Host}}')"
echo "endpoint: ${ENDPOINT}"
[[ "$ENDPOINT" == "unix:///var/run/docker.sock" ]] || {
  echo "REFUSING: context ${CONTEXT_NAME} does not name the unix socket." >&2
  exit 1; }

step "docker version / info on the native engine"
docker version
docker info 2>/dev/null | grep -iE 'server version|storage driver|docker root dir|operating system|name:'

# --------------------------------------------------------------------------
# 7. The pinned image, by digest. Also the canary's image, deliberately.
# --------------------------------------------------------------------------
step "pinned redis image"
PINNED="$(grep -oE 'redis:[^[:space:]]+@sha256:[0-9a-f]{64}' "${REPO_TREE}/compose.phase2.yml" | head -1)"
echo "compose pin: ${PINNED}"
docker pull "$PINNED"
RESOLVED="$(docker image inspect "$PINNED" --format '{{json .RepoDigests}}')"
echo "resolved   : ${RESOLVED}"
WANT_DIGEST="${PINNED##*@}"
grep -q "$WANT_DIGEST" <<<"$RESOLVED" || {
  echo "REFUSING: the native engine did not resolve ${WANT_DIGEST}." >&2
  echo "Do NOT substitute a tag. Stop and report." >&2
  exit 1; }
echo "DIGEST OK  : ${WANT_DIGEST}"

# --------------------------------------------------------------------------
# 8. The canaries. This is the assertion the whole phase turns on.
# --------------------------------------------------------------------------
canary() {
  local label="$1" dir="$2"
  local token="aep-phase10-${label}-$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}"
  mkdir -p "$dir"
  printf '%s\n' "$token" > "${dir}/canary.txt"
  local fstype
  fstype="$(stat -f -c %T "$dir")"
  # `cat` inside the container, not `docker cp` and not a bind of the parent
  # directory: the failure this detects is a daemon that resolves the SOURCE
  # elsewhere, and its symptom under Docker Desktop was an empty destination.
  local seen
  seen="$(docker run --rm \
      -v "${dir}/canary.txt:/canary.txt:ro" \
      "$PINNED" cat /canary.txt 2>&1 || true)"
  seen="$(tr -d '\r\n' <<<"$seen")"
  if [[ "$seen" == "$token" ]]; then
    echo "  PASS  ${label}  (${dir}, fs=${fstype})  token round-tripped"
    CANARY_JSON+="{\"name\":\"${label}\",\"path\":\"${dir}/canary.txt\",\"filesystem\":\"${fstype}\",\"token\":\"${token}\",\"seen\":\"${seen}\",\"pass\":true},"
    return 0
  fi
  echo "  FAIL  ${label}  (${dir}, fs=${fstype})"
  echo "        wrote: ${token}"
  echo "        saw  : ${seen:-<empty>}"
  CANARY_JSON+="{\"name\":\"${label}\",\"path\":\"${dir}/canary.txt\",\"filesystem\":\"${fstype}\",\"token\":\"${token}\",\"seen\":\"${seen}\",\"pass\":false},"
  return 1
}

step "bind-mount canaries"
CANARY_JSON=""
CANARY_FAILED=0
# The one B1 needs: a path that exists only inside the distro.
canary "wsl_local" "$CANARY_WSL_DIR" || CANARY_FAILED=1
# The one the drvfs collection arm needs: the repo tree, on 9p.
canary "drvfs" "$CANARY_DRVFS_DIR" || CANARY_FAILED=1

if [[ "$CANARY_FAILED" != "0" ]]; then
  echo
  echo "REFUSING: a bind-mount canary failed. The native engine does not" >&2
  echo "resolve the source it was given, which is the exact condition this" >&2
  echo "phase exists to remove. Stop and report." >&2
  exit 1
fi

# --------------------------------------------------------------------------
# 9. Record what was done, machine-readably
# --------------------------------------------------------------------------
step "record"
mkdir -p "$(dirname "$RECORD")"
cat > "$RECORD" <<JSON
{
  "provisioned_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "kernel": "$(uname -r)",
  "distro": "$(. /etc/os-release && echo "$PRETTY_NAME")",
  "pid1": "$(ps -p 1 -o comm=)",
  "daemon_start_path": "${START_PATH}",
  "docker_context": "${CONTEXT_NAME}",
  "docker_endpoint": "${ENDPOINT}",
  "version_pins": {
    "docker-ce": "$(dpkg-query -W -f='${Version}' docker-ce)",
    "docker-ce-cli": "$(dpkg-query -W -f='${Version}' docker-ce-cli)",
    "containerd.io": "$(dpkg-query -W -f='${Version}' containerd.io)",
    "docker-buildx-plugin": "$(dpkg-query -W -f='${Version}' docker-buildx-plugin)",
    "docker-compose-plugin": "$(dpkg-query -W -f='${Version}' docker-compose-plugin)"
  },
  "version_match": {
    "target_docker_desktop_server_version": "${MATCH_SERVER_VERSION}",
    "status": "${MATCH_STATUS}",
    "installed_server_version": "$(docker version --format '{{.Server.Version}}')"
  },
  "docker_desktop_shim": {
    "preserved_at": "${SHIM_PRESERVED}",
    "rollback": "mv ${SHIM_PRESERVED} ${SHIM}",
    "still_present": $( [[ -e "$SHIM_PRESERVED" ]] && echo true || echo false )
  },
  "pinned_image": "${PINNED}",
  "resolved_repo_digests": ${RESOLVED},
  "canaries": [ ${CANARY_JSON%,} ]
}
JSON
python3 -c "import json,sys; json.load(open('${RECORD}')); print('record is valid JSON')" \
  2>/dev/null || echo "(python3 unavailable; record written unvalidated)"
cat "$RECORD"

step "done"
echo "docker context : $(docker context show)"
echo "docker server  : $(docker version --format '{{.Server.Version}}')"
echo "client os/arch : $(docker version --format '{{.Client.Os}}/{{.Client.Arch}}')"
echo "record         : ${RECORD}"
