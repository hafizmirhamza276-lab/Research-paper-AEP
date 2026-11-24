#!/usr/bin/env bash
# READ-ONLY custody survey: where does each raw run tree live, what does it
# hold, and how big is it?
#
# stat, find, ls, du only. NO ledger is opened for reading or writing, no WAL
# is checkpointed, nothing is created, moved or deleted inside any root, and
# nothing is written anywhere under /root. Counting a .sqlite3 by name is a
# directory-entry read; it does not open the file.
#
# A script file rather than an inline `wsl bash -lc`, per B18.
#
# FAIL-CLOSED, and the first version of this script was not. It tested
# `[ ! -d "$base" ]` and printed ABSENT, which is what an unprivileged shell
# gets for /root -- so a tree holding 432 run directories reported as holding
# nothing. That is F.0d's fail-open class inside a tool written for a task
# about whether the evidence still exists: "there is no data here" and "I am
# not allowed to look" must never render the same. They are now three distinct
# outcomes -- ABSENT, UNREADABLE, and a count -- and UNREADABLE sets the exit
# status so a caller cannot mistake a blocked survey for a complete one.
#
# Run unprivileged for the Windows side; run under `sudo` for /root.
set -u
incomplete=0

# Per root: run directories, and the three ledger files counted separately so
# a broken triple is visible rather than averaged away.
detail() {
    root="$1"
    name=$(basename "$root")
    runs=$(find "$root" -mindepth 1 -maxdepth 1 -type d \
             ! -name analysis ! -name voided 2>/dev/null | wc -l)
    db=$(find "$root" -mindepth 2 -name '*.sqlite3' -type f 2>/dev/null | wc -l)
    wal=$(find "$root" -mindepth 2 -name '*.sqlite3-wal' -type f 2>/dev/null | wc -l)
    shm=$(find "$root" -mindepth 2 -name '*.sqlite3-shm' -type f 2>/dev/null | wc -l)
    size=$(du -sh "$root" 2>/dev/null | cut -f1)
    triple="OK"
    if [ "$db" -ne "$wal" ] || [ "$db" -ne "$shm" ]; then
        triple="BROKEN"
    fi
    printf '  %-42s runs=%4d  db=%4d wal=%4d shm=%4d [%s]  %s\n' \
        "$name" "$runs" "$db" "$wal" "$shm" "$triple" "$size"
}

survey() {
    base="$1"
    echo "=== $base ==="
    if [ -e "$base" ] && [ ! -r "$base" ]; then
        echo "  UNREADABLE (exists, permission denied) -- re-run with sudo"
        incomplete=1
        return
    fi
    if [ ! -d "$base" ]; then
        # A parent that is itself unreadable makes an existing child look
        # absent, so say which of the two this is rather than guessing.
        parent=$(dirname "$base")
        while [ "$parent" != "/" ]; do
            if [ -e "$parent" ] && [ ! -r "$parent" ]; then
                echo "  UNREADABLE (parent $parent denied) -- re-run with sudo"
                incomplete=1
                return
            fi
            parent=$(dirname "$parent")
        done
        echo "  ABSENT (verified: every parent readable)"
        return
    fi
    found=0
    for root in "$base"/*/; do
        [ -d "$root" ] || continue
        detail "$root"
        found=1
    done
    [ "$found" -eq 0 ] && echo "  (no result roots)"
    echo "  TOTAL: $(du -sh "$base" 2>/dev/null | cut -f1)"
}

for base in /root/aep/experiments/results \
            /root/aep-phase8/experiments/results \
            /root/aep-stage3/experiments/results \
            /mnt/d/personal/AEP/Research-paper-AEP/experiments/results; do
    survey "$base"
done

echo
echo "=== /mnt/d/personal/AEP (non-repo trees) ==="
for d in /mnt/d/personal/AEP/phase8-raw-archive \
         /mnt/d/personal/AEP/phase8-raw-archive-* \
         /mnt/d/personal/AEP/audit-clone \
         /mnt/d/personal/AEP/phase8-driver; do
    if [ -d "$d" ]; then
        printf '  %-46s %s\n' "$(basename "$d")" "$(du -sh "$d" 2>/dev/null | cut -f1)"
    fi
done
echo "  --- tarballs ---"
ls -la /mnt/d/personal/AEP/phase8-raw-archive/*.tar.gz 2>/dev/null \
    | awk '{printf "  %-52s %10d bytes  %s %s\n", $9, $5, $6, $7}' \
    || echo "  none"

echo
if [ "$incomplete" -ne 0 ]; then
    echo "INCOMPLETE: at least one tree could not be read. This survey does"
    echo "NOT establish that the unreadable trees are empty."
    exit 2
fi
echo "COMPLETE: every listed tree was readable."
