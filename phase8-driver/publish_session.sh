#!/usr/bin/env bash
# Copy a frozen results root from the ext4 collection clone into the tracked
# Windows clone, add the .gitignore negations, and re-verify the digests from
# the copy.
#
# Why the copy is re-verified rather than trusted: plan section 4 step 3 and
# step 4 are two different checks. This does step 3 on the destination -- the
# on-disk proof in the tree that will actually be committed. Step 4, the
# staged-blob proof, runs after `git add` and is what caught core.autocrlf
# corrupting 6 of 7 CSVs in Phase P while `git diff` showed clean.
#
# Usage: publish_session.sh <slug> [gitignore comment]

set -uo pipefail

SLUG="${1:?usage: publish_session.sh <slug> [comment]}"
COMMENT="${2:-Phase 8.4 session ${SLUG}.}"

SRC="/root/aep-phase8/experiments/results/${SLUG}"
DST="/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/${SLUG}"
GITIGNORE="/mnt/d/personal/AEP/Research-paper-AEP/.gitignore"
REL="experiments/results/${SLUG}"

[ -d "$SRC" ] || { echo "no such source root: $SRC"; exit 1; }
[ -f "$SRC/SHA256SUMS" ] || { echo "source is not frozen: $SRC/SHA256SUMS"; exit 1; }

mkdir -p "$DST/analysis"
cp "$SRC/MANIFEST.csv" "$SRC/MANIFEST.md" "$SRC/SHA256SUMS" "$DST/"
cp "$SRC"/analysis/* "$DST/analysis/"

echo "=== sha256sum -c from the copy in the tracked tree ==="
( cd "$DST" && sha256sum -c SHA256SUMS )
RC=$?
echo "EXIT=$RC"
[ "$RC" -eq 0 ] || { echo "HALT: the copy does not verify"; exit 2; }

# --- .gitignore negations -------------------------------------------------
# experiments/results/* is ignored wholesale, so each root re-opens its own
# levels and then re-closes them. Tracking every file SHA256SUMS lists is what
# lets `sha256sum -c` succeed in a fresh clone rather than report the rest
# missing.
if grep -q "^!${REL}/$" "$GITIGNORE"; then
    echo "gitignore block for ${SLUG} already present, leaving it alone"
else
    {
        echo
        echo "# ${COMMENT}"
        echo "!${REL}/"
        echo "${REL}/*"
        echo "!${REL}/MANIFEST.csv"
        echo "!${REL}/MANIFEST.md"
        echo "!${REL}/SHA256SUMS"
        echo "!${REL}/analysis/"
        echo "${REL}/analysis/*"
        for f in $(cd "$DST/analysis" && ls | sort); do
            echo "!${REL}/analysis/${f}"
        done
    } >> "$GITIGNORE"
    echo "appended gitignore negations for ${SLUG}"
fi

echo
echo "=== files that will be tracked ==="
( cd "$DST" && ls MANIFEST.csv MANIFEST.md SHA256SUMS && ls analysis/ | sed 's|^|analysis/|' )
