#!/usr/bin/env bash
# Give the WSL distro a `docker` that reaches Docker Desktop.
#
# Docker Desktop's WSL integration was not enabled for this distro, so
# `docker` is absent and the three Redis-restart tests fail with "The command
# 'docker' could not be found" -- an environment gap, not a code defect (they
# pass in CI, which has a real docker). The shim forwards to docker.exe and
# runs it from the Windows-side working tree, because docker.exe resolves a
# relative --file argument such as `-f compose.phase2.yml` against a Windows
# working directory and cannot resolve one against a WSL path.
#
# Install with: sudo bash wsl_docker_shim.sh
set -euo pipefail

WINDOWS_TREE_UNC="${AEP_WINDOWS_TREE_UNC:-D:\\personal\\AEP\\Research-paper-AEP}"
TARGET=/usr/local/bin/docker

cat >"$TARGET" <<EOF
#!/usr/bin/env bash
# Forward to Docker Desktop, from the Windows-side tree.
cd /mnt/d/personal/AEP/Research-paper-AEP 2>/dev/null || true
exec docker.exe "\$@"
EOF
chmod +x "$TARGET"

echo "installed $TARGET -> docker.exe (cwd ${WINDOWS_TREE_UNC})"
docker version --format '{{.Server.Version}}' 2>&1 | head -1
