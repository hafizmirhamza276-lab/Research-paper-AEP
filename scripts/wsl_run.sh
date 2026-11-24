#!/usr/bin/env bash
# Run a project command inside the WSL tree with the locked environment.
#
#   wsl_run.sh python -m experiments.bench_mock_api --seconds 20
#
# Exists because the Windows shell's PATH leaks into `wsl -- bash -lc '...'`
# and mangles inline commands; a script file takes its arguments cleanly.
set -uo pipefail

DST="${AEP_LINUX_TREE:-$HOME/aep}"
export PATH="$HOME/.local/bin:$PATH"
cd "$DST"
exec uv run --frozen "$@"
