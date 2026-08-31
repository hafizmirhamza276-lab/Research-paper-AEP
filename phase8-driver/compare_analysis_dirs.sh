#!/usr/bin/env bash
# Do `analysis/` and `analysis-interim/` in the matrix root hold the same bytes?
#
# freeze_results.py digests `analysis/*` by name, so analysis-interim/ is outside
# SHA256SUMS entirely. If the two directories disagree, the manuscript's own root
# contains two different answers to the same question with only one of them
# attested -- B15a's shape, in the tree the paper rests on.
#
# Read-only: hashes files, writes nothing, touches no ledger.
#
# Usage: compare_analysis_dirs.sh <matrix root>
set -u
R="${1:?usage: compare_analysis_dirs.sh <matrix root>}"
A="$R/analysis"
B="$R/analysis-interim"

echo "=== file names ==="
diff <(cd "$A" && ls -1 | sort) <(cd "$B" && ls -1 | sort) \
    && echo "identical file lists"

echo
echo "=== content comparison ==="
same=0; differ=0; only=0
for f in $(cd "$A" && ls -1 | sort); do
    if [ ! -f "$B/$f" ]; then
        printf '  ONLY IN analysis/      %s\n' "$f"
        only=$((only + 1))
        continue
    fi
    ha=$(sha256sum "$A/$f" | cut -d' ' -f1)
    hb=$(sha256sum "$B/$f" | cut -d' ' -f1)
    if [ "$ha" = "$hb" ]; then
        same=$((same + 1))
    else
        printf '  DIFFERS                %-45s\n' "$f"
        printf '      analysis/         %s  (%s bytes)\n' "${ha:0:16}" "$(stat -c %s "$A/$f")"
        printf '      analysis-interim/ %s  (%s bytes)\n' "${hb:0:16}" "$(stat -c %s "$B/$f")"
        differ=$((differ + 1))
    fi
done
echo
echo "identical: $same   differing: $differ   only in analysis/: $only"

echo
echo "=== mtimes ==="
echo "analysis/         newest: $(cd "$A" && ls -1t | head -1) $(stat -c %y "$A/$(cd "$A" && ls -1t | head -1)")"
echo "analysis-interim/ newest: $(cd "$B" && ls -1t | head -1) $(stat -c %y "$B/$(cd "$B" && ls -1t | head -1)")"

echo
echo "=== is analysis-interim named by SHA256SUMS? ==="
if [ -f "$R/SHA256SUMS" ]; then
    n=$(grep -c 'analysis-interim' "$R/SHA256SUMS" || true)
    echo "entries mentioning analysis-interim: $n"
    echo "total entries in SHA256SUMS        : $(wc -l < "$R/SHA256SUMS")"
else
    echo "no SHA256SUMS in this root"
fi
