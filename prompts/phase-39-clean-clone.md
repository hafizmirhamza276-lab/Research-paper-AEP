# Phase 39 — reproduce the artifact from a clean clone, as an evaluator would

## Read first
- `ARTIFACT.md` — the whole file, as a reader following it for the first time
- `README.md` — the two commands in the first code block
- `reports/phase-report-38-…` — the provenance stamp that could not verify in a
  clone, and why
- `docs/25` R14 and its instances — a gate green over what it can see
- `docs/36` — what lives outside the repository

## Context
Phase 38 found a gate that passed here and would have failed in any clone,
because one of its inputs was gitignored. Artifact evaluation runs in a clean
clone on a different machine. This pass finds out what else is in that class,
before a reviewer does.

## Bounds
- In scope: `reports/`, `prompts/`, and fixes to `scripts/`, `Makefile`,
  `README.md`, `ARTIFACT.md`, `docs/` where the clone reveals a defect.
- Out of scope: any `.tex` prose, any numeric claim, the deposit, any
  collection. Do not change what a command *checks* in order to make it pass —
  record it instead.
- The working repository is not modified to suit the clone. If they disagree,
  the clone is the truth about what ships.

## Steps

1. Commit this prompt as `prompts/phase-39-clean-clone.md`.

2. **Clone into a fresh directory from `origin`,** not a copy of the working
   tree. Nothing from the working tree is allowed in, including `.scratch/`,
   caches, and anything under `/root/aep*`. Record what the clone's size and
   file count are against the working tree's.

3. **Follow `ARTIFACT.md` literally**, as someone who has never seen this
   project. Every command it names, in the order it names them. Record for each:
   ran / failed / could not be run, and why.

4. **Then `README.md`'s two headline commands:** `make reproduce-figures` and
   `make reproduce-smoke`. Phase 17 called the first broken, phase 18 said it
   always worked, and the truth turned out to depend on whether the machine had
   a partial tree. A clean clone settles it.

5. **Run the full gate set in the clone:** the suite, the 43 numbers, the
   citations, the prereg audit, the anonymity check, the provenance stamps, the
   cross-document reference gate. Every one of these was built here and has only
   ever run here.

6. **Build all four documents in the clone**, supplementaries first.

7. **Classify every failure into one of three:** needs a dependency the clone
   legitimately lacks (Docker, Redis, TeX) — document it in `ARTIFACT.md` as a
   prerequisite; needs something outside the repository — check `docs/36` names
   it, and add it if not; or is a defect — fix it.

8. **The prerequisites section is the deliverable**, as much as the fixes.
   `ARTIFACT.md` should let a reader know, before running anything, what they
   need and what they will and will not be able to reproduce. Include the two
   trees declared outside the archive.

9. R15 scoped to whatever was fixed. Zero `.tex` prose.

## Acceptance criteria
- A clean clone exists and its provenance is stated (commit, date, size)
- Every `ARTIFACT.md` command has a recorded outcome
- Both README commands have a definitive verdict from the clone
- Every gate run in the clone, with its result
- All four documents build in the clone, or exactly what stopped them
- Every failure classified into one of the three, none left unclassified
- `ARTIFACT.md` states prerequisites and reproducibility boundaries
- No gate weakened to make it pass

## Report
`reports/phase-report-39-clean-clone-<date>.md`: Asked / Clone provenance /
Per-command table / Per-gate table / The three classes with every failure in one
/ What `ARTIFACT.md` now tells a reader / Not done and why / Raw outputs.
Five-line pointer.

## Next
The deposit when Zenodo is stable, then `v1.0.0`, then the submission package.