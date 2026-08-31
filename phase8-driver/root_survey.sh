#!/usr/bin/env bash
# Read-only. What sits at the top level of a frozen root, and how many run
# directories it holds. Used to show that the .gitignore block leaves the
# unhashed top-level copies untracked deliberately, not by oversight.
set -u
for S in "$@"; do
    R="/root/aep-phase8/experiments/results/${S}"
    echo "== ${S} =="
    echo "-- top-level files --"
    ( cd "$R" && ls -1p | grep -v '/$' | sort )
    echo "-- top-level dirs --"
    ( cd "$R" && ls -1p | grep '/$' | sort )
    echo "-- run directory count (excluding analysis/) --"
    ( cd "$R" && ls -1p | grep '/$' | grep -cv '^analysis/$' )
    echo
done
