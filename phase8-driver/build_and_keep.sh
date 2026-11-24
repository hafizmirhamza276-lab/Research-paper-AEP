#!/usr/bin/env bash
# Build the current paper/ in a scratch copy and KEEP the PDF, so a changed
# site can be read as rendered rather than as source.
#
# build_clean_copy.sh removes the stale untracked artifacts that make
# TEXINPUTS find a three-week-old main.bbl; scripts/build_paper.sh then
# deletes its build directory on exit and refuses to publish while any check
# fails, which is correct for publishing and useless for reading. This does
# the same copy, compiles in place, and leaves main.pdf where pdftotext can
# reach it. It publishes nothing back into the repository.
#
# A script file rather than an inline `wsl bash -lc`, per B18 -- and because
# variable expansion in an inline invocation was eaten by the outer shell.
set -u
R=/mnt/d/personal/AEP/Research-paper-AEP
D=/tmp/b9paper

rm -rf "$D"
mkdir -p "$D"
cp -r "$R/paper" "$D/paper" || exit 1
cd "$D/paper" || exit 1
rm -f main.aux main.bbl main.blg main.log main.out main.pdf

pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1
bibtex main >/dev/null 2>&1
pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1
pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1

echo "=== undefined references or citations ==="
grep -c "Undefined control sequence\|undefined" main.log || true
echo "=== pdf ==="
ls -la main.pdf
