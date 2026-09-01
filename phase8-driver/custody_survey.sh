#!/usr/bin/env bash
# READ-ONLY custody survey: where does each raw run tree actually live, and
# what has an archive?
#
# stat and count only. No ledger is opened, no WAL is checkpointed, nothing is
# written into any results root. A script file rather than an inline
# `wsl bash -lc`, per B18.
#
# FAIL-CLOSED, and the first version of this script was not. It tested
# `[ ! -d "$base" ]` and printed ABSENT, which is what an unprivileged shell
# gets for /root -- so a tree holding 432 run directories reported as holding
# nothing. That is F.0d's fail-open class inside a tool written for a task
# about whether the evidence still exists: "there is no data here" and "I am
# not allowed to look" must never render the same. They are now three distinct
# outcomes -- ABSENT, UNREADABLE, and a count -- and UNREADABLE sets the exit
# status so a caller cannot mistake a blocked survey for a complete one.
set -u
incomplete=0

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
    for root in "$base"/*/; do
        [ -d "$root" ] || continue
        name=$(basename "$root")
        n=$(find "$root" -mindepth 1 -maxdepth 1 -type d \
              ! -name analysis ! -name voided 2>/dev/null | wc -l)
        printf '  %-42s %4d run dirs\n' "$name" "$n"
    done
}

for base in /root/aep/experiments/results \
            /root/aep-phase8/experiments/results \
            /root/aep-stage3/experiments/results \
            /mnt/d/personal/AEP/Research-paper-AEP/experiments/results; do
    survey "$base"
done

echo
echo "=== archives: /mnt/d/personal/AEP/phase8-raw-archive ==="
if [ -d /mnt/d/personal/AEP/phase8-raw-archive ]; then
    ls -la /mnt/d/personal/AEP/phase8-raw-archive/*.tar.gz 2>/dev/null \
        || echo "  no tarballs"
else
    echo "  ABSENT"
fi

echo
if [ "$incomplete" -ne 0 ]; then
    echo "INCOMPLETE: at least one tree could not be read. This survey does"
    echo "NOT establish that the unreadable trees are empty."
    exit 2
fi
echo "COMPLETE: every listed tree was readable."
