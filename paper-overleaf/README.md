# AEP — Overleaf project

Two independent documents. They are **not** an appendix bound into one file:
IEEE Computer Society guidance treats supplemental material as a separate
submission and excludes it from the page count.

| document | main file | pages |
|---|---|---|
| manuscript | `main.tex` | 25 |
| supplementary | `supplementary.tex` | 7 |

## In Overleaf

Upload this folder as a project, then **Menu → Settings**:

- **Compiler:** pdfLaTeX
- **Main document:** `main.tex`

To build the supplementary instead, set **Main document** to
`supplementary.tex` and recompile. Overleaf builds one main document at a
time, so switch the setting rather than expecting both PDFs at once.

## Compile order

Both documents need BibTeX, so the sequence is the usual four passes — the
second pdfLaTeX resolves citations, the third resolves `cleveref` and the
cross-references that depend on final page and float placement:

```
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

and the same with `supplementary` in place of `main`. Overleaf runs this for
you; the sequence is written out here for anyone compiling locally.

`main.bbl` and `supplementary.bbl` are included, so the documents will compile
to correct references even if BibTeX is not run at all.

## What is here

```
main.tex                 manuscript
supplementary.tex        supplementary material
sections/                the nine manuscript sections, \input by main.tex
generated/               tables and the \newcommand numbers, \input by both
figures/                 two data figures (PDF) and the state machine (TikZ)
refs.bib                 bibliography source
main.bbl                 pre-built bibliography for main.tex
supplementary.bbl        pre-built bibliography for supplementary.tex
IEEEtran.cls             IEEE journal class, v1.8b
IEEEtran.bst             IEEE BibTeX style
```

Everything resolves with paths relative to this folder. Nothing refers to
anything outside it, and no script has to be run before compiling: the
contents of `generated/` are already generated.

`IEEEtran.cls` and `IEEEtran.bst` are bundled so the project compiles the same
way anywhere. Overleaf also provides both, and removing them here would make
no difference to the output.
