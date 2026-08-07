#!/usr/bin/env bash
set -e
SRC=/mnt/d/personal/AEP/Research-paper-AEP
cd "$HOME/aep"
mkdir -p paper/sections paper/generated paper/figures
cp "$SRC"/paper/main.tex paper/
cp "$SRC"/paper/refs.bib paper/
cp "$SRC"/paper/sections/*.tex paper/sections/
rm -f paper/generated/*.tex
cp "$SRC"/paper/generated/*.tex paper/generated/
cp "$SRC"/paper/figures/*.tex paper/figures/ 2>/dev/null || true
cp "$SRC"/paper/figures/*.pdf paper/figures/ 2>/dev/null || true
cd paper
rm -f main.aux main.bbl main.blg main.log main.out main.pdf
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /tmp/tex1.log 2>&1 || { echo "PASS 1 FAILED"; tail -40 /tmp/tex1.log; exit 1; }
bibtex main > /tmp/bib.log 2>&1 || true
pdflatex -interaction=nonstopmode main.tex > /tmp/tex2.log 2>&1 || true
pdflatex -interaction=nonstopmode main.tex > /tmp/tex3.log 2>&1 || true
echo "=== bibtex problems ==="
grep -iE "error|I was expecting" /tmp/bib.log | head -5 || true
echo "=== undefined refs/citations ==="
grep -iE "Warning.*(undefined|Citation)" main.log | grep -v Font | head -20 || true
echo "=== overfull count ==="
grep -c "Overfull" main.log || true
echo "=== pages ==="
grep -oE "Output written on main.pdf \([0-9]+ pages" main.log || true
cp main.pdf main.bbl main.blg main.log main.aux main.out "$SRC"/paper/
