#!/usr/bin/env bash
# Copy a frozen root into the tracked Windows clone, copying EXACTLY the files
# SHA256SUMS names plus SHA256SUMS itself -- nothing else.
#
# This differs from publish_session.sh, which copies `analysis/*` and derives its
# .gitignore block from `ls`. Deriving from the freeze rather than from the
# directory means an unhashed file that appeared in analysis/ after the freeze
# cannot ride along into the commit. The two agree on s3/s4 (checked by
# derive_negations.py before this ran), but agreeing today is not the same as
# being derived from the right source.
#
# Copies only. Writes no .gitignore, stages nothing, commits nothing.
#
# Usage: publish_from_sums.sh <slug>
set -uo pipefail

SLUG="${1:?usage: publish_from_sums.sh <slug>}"
SRC="/root/aep-phase8/experiments/results/${SLUG}"
DST="/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/${SLUG}"

[ -f "$SRC/SHA256SUMS" ] || { echo "source is not frozen: $SRC/SHA256SUMS"; exit 1; }

mkdir -p "$DST/analysis"
cp "$SRC/SHA256SUMS" "$DST/SHA256SUMS"

n=0
while read -r _ path; do
    path="${path#\*}"
    [ -n "$path" ] || continue
    mkdir -p "$DST/$(dirname "$path")"
    cp "$SRC/$path" "$DST/$path" || { echo "HALT: could not copy $path"; exit 1; }
    n=$((n + 1))
done < <(tr -d '\r' < "$SRC/SHA256SUMS")

echo "copied ${n} SHA256SUMS-named files + SHA256SUMS = $((n + 1)) files"

echo "=== sha256sum -c from the copy in the tracked tree ==="
( cd "$DST" && sha256sum -c SHA256SUMS )
RC=$?
echo "EXIT=$RC"
[ "$RC" -eq 0 ] || { echo "HALT: the copy does not verify"; exit 2; }

echo "=== files present in the destination root ==="
( cd "$DST" && find . -type f | sed 's|^\./||' | sort )
