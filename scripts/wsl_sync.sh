#!/usr/bin/env bash
# Mirror the Windows working tree into the WSL native filesystem.
#
# Why this exists: the harness's crash fidelity claim rests on a real SIGKILL
# (reports/phase-report-2b-session2-2026-08-05.md F4), so every number the
# paper reports must be collected on Linux. Development happens on Windows;
# this script is the one-way bridge. It deliberately does NOT copy .git,
# .venv, or experiments/results -- the Linux side has its own environment and
# its own results, and copying either back over the other would silently mix
# two runs.
set -euo pipefail

SRC="${AEP_WINDOWS_TREE:-/mnt/d/personal/AEP/Research-paper-AEP}"
DST="${AEP_LINUX_TREE:-$HOME/aep}"

mkdir -p "$DST"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '*.pyc' \
  --exclude '.coverage' \
  --exclude 'experiments/results/' \
  --exclude 'junit*.xml' \
  --exclude 'pytest-*.txt' \
  --exclude '*.egg-info/' \
  --exclude '.ai/' \
  "$SRC/" "$DST/"

echo "synced $SRC -> $DST"
