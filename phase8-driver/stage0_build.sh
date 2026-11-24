#!/usr/bin/env bash
# Stage 0, BUILD HALF ONLY. Medium-independent.
#
# Builds one tar.gz per 21 August root plus a full SHA-256 manifest, into a
# SCRATCH directory OUTSIDE every results root and outside the repository.
# It copies to no destination: the approved medium (personal cloud account) is
# not present on this machine and no substitute is used.
#
# WHY THE ARCHIVING STEP IS THE DANGEROUS ONE (copy plan section 5): a verified
# copy of a corrupted archive verifies perfectly. So the guard cannot be
# verification -- it has to be that archiving NEVER WRITES INTO A RESULTS ROOT.
# Every output of this script lands in $SCRATCH. Nothing is created, moved or
# deleted inside experiments/results.
#
# LEDGER SAFETY. tar reads bytes; no ledger is opened, no WAL is checkpointed,
# and *.sqlite3 is never named in a glob -- the whole run directory is archived
# so the triple (db, -wal, -shm) travels together. 1093 of 1093 ledgers are bare
# 4096-byte pages with the ground truth in uncheckpointed WALs, so an archive
# that took only *.sqlite3 would produce files that open cleanly and contain
# nothing.
#
# MTIMES ARE CAPTURED BEFORE AND AFTER. Unchanged mtimes are the evidence that
# nothing opened a ledger. They are recorded here, before any sync client can
# touch them: sync clients normalise mtimes and would destroy this evidence.
#
# VERIFICATION IS BY NAME-SET, NEVER BY COUNT (B32). Two totals that agree tell
# you nothing about which items they contain -- that is how runs=433 passed
# against db=432.
set -u

REPO=/d/personal/AEP/Research-paper-AEP
RES="$REPO/experiments/results"
SCRATCH=/d/personal/AEP/stage0-staging
ROOTS="b2-2026-08-21 b2-s1-2026-08-21 b2-s2-2026-08-21 b2-s3-2026-08-21"

case "$SCRATCH" in
    "$RES"*) echo "FATAL: scratch is inside a results root"; exit 1 ;;
    "$REPO"*) echo "FATAL: scratch is inside the repository"; exit 1 ;;
esac

mkdir -p "$SCRATCH"
rc=0

ledger_mtimes() {
    find "$1" -mindepth 2 \( -name '*.sqlite3' -o -name '*.sqlite3-wal' \
        -o -name '*.sqlite3-shm' \) -printf '%P %T@\n' 2>/dev/null | sort
}

for R in $ROOTS; do
    SRC="$RES/$R"
    echo "=== $R ==="

    ledger_mtimes "$SRC" > "$SCRATCH/$R.mtimes-before"

    # Manifest of EVERY file, not just derived products. The root's own
    # SHA256SUMS names zero run directories, which is why a fresh one is built
    # rather than reused -- and the existing one is never rewritten.
    ( cd "$SRC" && find . -type f -print0 | sort -z \
        | xargs -0 sha256sum ) > "$SCRATCH/$R.manifest.sha256" 2>/dev/null
    echo "  manifest: $(wc -l < "$SCRATCH/$R.manifest.sha256") files"

    tar -czf "$SCRATCH/$R.tar.gz" -C "$RES" "$R" 2>/dev/null
    echo "  tarball:  $(stat -c %s "$SCRATCH/$R.tar.gz") bytes"

    ledger_mtimes "$SRC" > "$SCRATCH/$R.mtimes-after"
    if diff -q "$SCRATCH/$R.mtimes-before" "$SCRATCH/$R.mtimes-after" >/dev/null; then
        echo "  mtimes:   UNCHANGED ($(wc -l < "$SCRATCH/$R.mtimes-before") ledger files)"
    else
        echo "  mtimes:   *** CHANGED -- a ledger was touched ***"
        rc=1
    fi

    # --- verify the tarball by name-set symmetric difference, then by hash ---
    TMP="$SCRATCH/.verify-$R"
    rm -rf "$TMP"; mkdir -p "$TMP"
    tar -xzf "$SCRATCH/$R.tar.gz" -C "$TMP" 2>/dev/null

    ( cd "$SRC" && find . -type f | sort ) > "$TMP/.names-src"
    ( cd "$TMP/$R" && find . -type f | sort ) > "$TMP/.names-tar"
    SYMDIFF=$(comm -3 "$TMP/.names-src" "$TMP/.names-tar" | wc -l)
    echo "  name-set symmetric difference: $SYMDIFF"
    [ "$SYMDIFF" -eq 0 ] || rc=1

    ( cd "$TMP/$R" && sha256sum -c "$SCRATCH/$R.manifest.sha256" ) \
        > "$TMP/.hashcheck" 2>&1
    BAD=$(grep -c -v ': OK$' "$TMP/.hashcheck" 2>/dev/null || true)
    OK=$(grep -c ': OK$' "$TMP/.hashcheck" 2>/dev/null || true)
    echo "  per-path sha256: $OK OK, $BAD mismatched"
    [ "$BAD" -eq 0 ] || rc=1

    rm -rf "$TMP"
done

echo
echo "SCRATCH: $SCRATCH"
echo "NOT COPIED ANYWHERE. No destination medium is present."
if [ "$rc" -ne 0 ]; then
    echo "RESULT: FAILED -- do not use these archives"
    exit 1
fi
echo "RESULT: all archives verified against source"
