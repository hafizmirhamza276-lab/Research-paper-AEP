#!/usr/bin/env bash
# Bring the WSL side to the same pinned environment CI uses.
#
# The lockfile is the contract: `uv sync --frozen` refuses to resolve anything,
# so a Linux run and a CI run install the same versions of the same packages,
# and a divergence is a hard error rather than a silently different result.
set -euo pipefail

DST="${AEP_LINUX_TREE:-$HOME/aep}"
export PATH="$HOME/.local/bin:$PATH"

cd "$DST"
uv python install 3.13
uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis
echo '--- interpreter ---'
uv run --frozen python -VV
echo '--- signal fidelity ---'
uv run --frozen python -c "import signal; print('HAS_SIGKILL =', hasattr(signal, 'SIGKILL'))"
