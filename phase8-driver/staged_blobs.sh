#!/usr/bin/env bash
# Plan section 4 step 4: the staged-blob proof.
#
# Re-hash what git actually staged -- not what is on disk -- and compare it
# against that file's line in SHA256SUMS. This is the check that caught
# core.autocrlf corrupting 6 of 7 committed CSVs in Phase P while `git diff`
# showed clean. .gitattributes:19 should make it impossible, which is why it is
# verified rather than assumed.
#
# Also confirms the staged SHA256SUMS blob is byte-identical to disk and carries
# no CR bytes.
#
# Usage: staged_blobs.sh <slug>

set -uo pipefail

SLUG="${1:?usage: staged_blobs.sh <slug>}"
# Run this from Windows Git Bash, not from WSL. Git in WSL refuses the Windows
# clone with "detected dubious ownership", and its stderr is easy to swallow --
# which makes every staged read come back empty and every file look like a
# mismatch against the empty-string digest. Overridable, but the default is the
# path that works without changing anyone's global git config.
REPO="${REPO:-/d/personal/AEP/Research-paper-AEP}"
REL="experiments/results/${SLUG}"

cd "$REPO" || exit 1

FAIL=0
CHECKED=0

while read -r want name; do
    [ -z "${name:-}" ] && continue
    path="${REL}/${name}"
    got=$(git cat-file blob ":${path}" 2>/dev/null | sha256sum | cut -d' ' -f1)
    if [ -z "$got" ]; then
        echo "MISSING FROM INDEX: $path"
        FAIL=$((FAIL + 1))
        continue
    fi
    CHECKED=$((CHECKED + 1))
    if [ "$got" != "$want" ]; then
        echo "MISMATCH: $path"
        echo "   SHA256SUMS : $want"
        echo "   staged blob: $got"
        FAIL=$((FAIL + 1))
    fi
done < <(sed 's/^\\//' "${REL}/SHA256SUMS" | awk '{print $1, $2}' | sed 's/\*//')

# The manifest of digests is itself staged, and nothing above checks it.
DISK=$(sha256sum "${REL}/SHA256SUMS" | cut -d' ' -f1)
STAGED=$(git cat-file blob ":${REL}/SHA256SUMS" | sha256sum | cut -d' ' -f1)
CR=$(git cat-file blob ":${REL}/SHA256SUMS" | tr -cd '\r' | wc -c)

echo
echo "staged blobs re-hashed against SHA256SUMS : ${CHECKED} checked, ${FAIL} mismatches"
echo "SHA256SUMS disk   : $DISK"
echo "SHA256SUMS staged : $STAGED"
echo "CR bytes in staged SHA256SUMS: $CR"

if [ "$DISK" != "$STAGED" ]; then
    echo "MISMATCH: the staged SHA256SUMS is not byte-identical to disk"
    FAIL=$((FAIL + 1))
fi
if [ "$CR" -ne 0 ]; then
    echo "MISMATCH: the staged SHA256SUMS carries CR bytes"
    FAIL=$((FAIL + 1))
fi

if [ "$FAIL" -ne 0 ]; then
    echo "HALT: staged-blob verification failed with ${FAIL} problem(s)"
    exit 1
fi

echo "OK: ${CHECKED}/${CHECKED} staged blobs match, SHA256SUMS byte-identical, 0 CR bytes"
exit 0
