#!/usr/bin/env bash
# B5 verification: freeze the SAME root on WSL and on Windows and require the
# two SHA256SUMS to be byte-identical to each other AND to the committed one.
#
# WHY THIS AND NOT A FIXTURE TEST. The committed manifest is real data produced
# by the pre-fix code on Linux. If the fix is correct, the Windows output
# becomes byte-identical to it -- so the expected value is not invented, and one
# comparison proves portability AND non-regression together.
#
# NO SESSION ROOT IS TOUCHED. The freeze runs on COPIES in a scratch directory
# outside every results root and outside the repository, with the same guard
# stage0_build.sh uses. No existing SHA256SUMS is rewritten -- the standing rule
# is not approached, it is structurally out of reach.
set -u

REPO=/d/personal/AEP/Research-paper-AEP
RES="$REPO/experiments/results"
SCRATCH=/d/personal/AEP/b5-verify
ROOT=b2-2026-08-21

case "$SCRATCH" in
    "$RES"*|"$REPO"*) echo "FATAL: scratch inside repo or results"; exit 1 ;;
esac

rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"

# Two independent copies so neither platform sees the other's output.
cp -r "$RES/$ROOT" "$SCRATCH/win"
cp -r "$RES/$ROOT" "$SCRATCH/wsl"

# The copies carry the committed SHA256SUMS/MANIFEST.*; remove them from the
# COPIES only, so each freeze writes its own rather than reading a stale one.
COMMITTED="$SCRATCH/committed-SHA256SUMS"
cp "$RES/$ROOT/SHA256SUMS" "$COMMITTED"
rm -f "$SCRATCH/win/SHA256SUMS" "$SCRATCH/win/MANIFEST.md" "$SCRATCH/win/MANIFEST.csv"
rm -f "$SCRATCH/wsl/SHA256SUMS" "$SCRATCH/wsl/MANIFEST.md" "$SCRATCH/wsl/MANIFEST.csv"

# The committed MANIFEST.md's title carries the --label the original freeze was
# run with. Without it the regenerated manifest differs on its first line and
# the comparison fails for a reason that has nothing to do with portability --
# which is exactly what happened on the first run of this script.
LABEL=$(head -1 "$RES/$ROOT/MANIFEST.md" | sed 's/^# Results manifest -- //')
echo "label recovered from committed manifest: [$LABEL]"

echo "=== freeze on WINDOWS (python $(python -c 'import sys;print(sys.version.split()[0])')) ==="
( cd "$REPO" && python scripts/freeze_results.py --results-root "$SCRATCH/win" \
    --label "$LABEL" ) 2>&1 | tail -3

echo "=== freeze on WSL ==="
MSYS_NO_PATHCONV=1 wsl -- bash -lc \
    "cd /mnt/d/personal/AEP/Research-paper-AEP && python3 scripts/freeze_results.py --results-root /mnt/d/personal/AEP/b5-verify/wsl --label '$LABEL'" \
    2>&1 | tail -3

echo
echo "=== BYTE COMPARISON ==="
rc=0
for pair in "win:wsl" "win:committed" "wsl:committed"; do
    a="${pair%%:*}"; b="${pair##*:}"
    fa="$SCRATCH/$a/SHA256SUMS"
    [ "$a" = committed ] && fa="$COMMITTED"
    fb="$SCRATCH/$b/SHA256SUMS"
    [ "$b" = committed ] && fb="$COMMITTED"
    if cmp -s "$fa" "$fb"; then
        echo "  $a == $b   BYTE-IDENTICAL"
    else
        echo "  $a != $b   *** DIFFERS ***"
        diff "$fa" "$fb" | head -5
        rc=1
    fi
done

echo
echo "=== FORMAT ASSERTIONS on the Windows output ==="
python - "$SCRATCH/win/SHA256SUMS" "$SCRATCH/win/MANIFEST.md" <<'PY'
import sys
bad = 0
for p in sys.argv[1:]:
    b = open(p, 'rb').read()
    cr = b.count(b'\r'); bs = b.count(bytes([92]))
    print("  %-16s CR=%d backslash=%d" % (p.split('/')[-1], cr, bs))
    if cr or bs:
        bad = 1
sys.exit(bad)
PY
[ $? -eq 0 ] || rc=1

echo
if [ "$rc" -ne 0 ]; then echo "RESULT: FAILED"; exit 1; fi
echo "RESULT: PASS -- Windows output is byte-identical to the committed manifest"
