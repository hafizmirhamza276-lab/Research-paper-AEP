#!/usr/bin/env bash
# Does B6's symptom still reproduce on this host?
#
# B6: "local TeX Live typesets 24 of the 29 \bibitem entries bibtex correctly
# produces. The last entries never receive a \bibcite, so nine citations render
# as undefined." That claim decides part of B21 item 4: if a local build cannot
# produce a correct document, "untrack it and build your own" does not work.
#
# Establishing only. B6 is NOT being fixed or closed here.
set -u
W=/tmp/b6symptom
ROOT=/mnt/d/personal/AEP/Research-paper-AEP

rm -rf "$W"; mkdir -p "$W"
cp -r "$ROOT/paper" "$W/paper" || { echo "copy failed"; exit 1; }

cd "$ROOT" || exit 1
AEP_PAPER_DIR="$W/paper" bash scripts/build_paper.sh >"$W/build.out" 2>&1
echo "build verdict: $(grep -E 'passed, [0-9]+ failed' "$W/build.out" | tail -1)"

if [ ! -f "$W/paper/main.log" ]; then
    echo "no promoted log -- build did not complete"
    tail -5 "$W/build.out"
    rm -rf "$W"; exit 1
fi

printf 'refs.bib entries : %s\n' "$(grep -c '^@' "$W/paper/refs.bib")"
printf 'bibitem in .bbl  : %s\n' "$(grep -c '\\bibitem' "$W/paper/main.bbl")"
printf 'bibcite in .log  : %s\n' "$(grep -c 'bibcite' "$W/paper/main.log")"
printf 'undefined cites  : %s\n' "$(grep -c 'Citation.*undefined' "$W/paper/main.log")"
printf 'pages            : %s\n' "$(grep -oE 'Output written on main.pdf \([0-9]+ pages' "$W/paper/main.log" | grep -oE '[0-9]+ pages')"

rm -rf "$W"
