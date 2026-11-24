#!/usr/bin/env bash
# Does TEXINPUTS ordering decide which main.bbl wins?
#
# probe_bbl_identity.sh established that all three pdflatex passes open
# paper/main.bbl and never the scratch one bibtex just wrote. This asks WHY:
# build_paper.sh:79 sets TEXINPUTS="${PAPER}//:", putting paper/ ahead of the
# trailing empty entry that expands to the compiled-in defaults (which include
# the current directory). If so, the cause belongs to item 1, not item 2, and
# that changes whether item 2 is worth doing alone.
#
# READ-ONLY. kpsewhich only, in /tmp, on a copy.
#
# A script file rather than an inline `wsl bash -lc`, per B18 -- the inline form
# had $W expanded by the OUTER shell to empty, so TEXINPUTS pointed at /paper//
# and both variants trivially resolved to the scratch copy. A meaningless
# result that looked like a real one.
set -u

W=/tmp/bblorder
rm -rf "$W"; mkdir -p "$W/paper" "$W/s"
printf 'PAPER-DIR COPY\n' > "$W/paper/main.bbl"
printf 'SCRATCH COPY\n'    > "$W/s/main.bbl"

cd "$W/s" || exit 1

echo "cwd = $W/s   (both a scratch and a paper main.bbl exist)"
echo

for spec in "${W}/paper//:" ".:${W}/paper//:" "${W}/paper//" ; do
    export TEXINPUTS="$spec"
    resolved=$(kpsewhich -format=tex main.bbl 2>&1)
    case "$resolved" in
        "$W/s"/*|./*) winner="SCRATCH" ;;
        "$W/paper"/*) winner="PAPER  " ;;
        *)            winner="???    " ;;
    esac
    printf '  %-8s  TEXINPUTS=%-28s -> %s\n' "$winner" "$spec" "$resolved"
done

echo
echo "note: a TRAILING colon means 'append the compiled-in defaults', and the"
echo "defaults include the current directory. So paper// sits AHEAD of '.'."

cd /; rm -rf "$W"
