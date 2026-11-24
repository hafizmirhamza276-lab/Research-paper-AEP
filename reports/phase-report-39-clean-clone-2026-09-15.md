# Phase 39 — reproduce the artifact from a clean clone, as an evaluator would

## Asked / Done

Asked: clone from `origin`, follow `ARTIFACT.md` literally, run every gate and
build every document in the clone, classify every failure into one of three, and
write the prerequisites section.

Done: all of it. **Five defects, and the most important one is that
`make reproduce-figures` — the README's headline command, the one this artifact
asks reviewers to run first — exited non-zero in a clean clone, for two
independent reasons, neither of which could be seen from here.** Both are fixed
and the target now regenerates all six generated files *and both analysis
figures* byte-identically in the clone. One defect becomes `docs/25` R14
instance 11.

---

## 1. The clone

```
commit  0baec98589e74d7ade7beecbb328c8c6a49e2c61
date    2026-09-15T16:07:39+05:00
branch  main
```

|  | clone | working tree |
|---|---|---|
| tracked files | 3 229 | 3 229 |
| files on disk (no `.git`) | **3 229** | 29 606 |
| size (no `.git`) | **42 MB** | 815 MB |

`.venv`, `.scratch`, `paper/.ai` and `.ai` are all absent, as they must be. The
26 377-file difference is the whole of what this repository deliberately does
not ship: the virtualenv, the reproduction scratch, and the raw run
directories.

**The environment had everything.** `uv`, `python3`, `docker` (daemon
reachable), `pdflatex`, `bibtex`, `pdftotext`, `pdfinfo`, `java` — all present.
That matters for reading what follows: **nothing below failed for want of a
tool.** Every failure was in the repository.

---

## 2. Every command `ARTIFACT.md` prints, with its outcome

Outcomes are from the clone, running the command exactly as printed, before any
fix in this pass.

| § | command | outcome |
|---|---|---|
| 2 | `uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis` | ran, exit 0 — but **incomplete**, see D5 |
| 3.1 | the `awk` over `per-cell-metrics.csv` | ran; six crash points, pooled `95/180`, `0.527778` — exactly as printed |
| 3.2 | `cat …/redis-kill-ablation.csv` | ran; `28` applied for `B3_INTENT_NO_BARRIER`, `10` for `AEP_FULL`, 30 executions each |
| 3.3 | `grep "unacknowledged write lost" …` | ran; `0/10 usable trials (0 void)` |
| 4 | `make reproduce-figures` | **FAILED, exit 2** — D1 and D2 |
| 4 | `make reproduce-figures ARCHIVE=/path/to/unpacked/matrix` | **FAILED, exit 2** — D3 |
| 4 | `make reproduce-smoke` | ran, exit 0; seven systems, 2 executions each, `reproduce-smoke: OK` |
| 4 | `uv run --frozen pytest -q -ra --strict-markers --cov=aep_core --cov-fail-under=90` | **3 failed** — D5 |
| 4 | `scripts/check_paper_numbers.py` | **FAILED, exit 1** — 39 passed, 2 failed (`main.bbl exists`, `main.log exists`) — ordering, class 1 |
| 4 | `scripts/validate_citations.py` | ran, exit 0 — 371 citations, 0 invalid |
| 4 | `scripts/verify_refs.py --offline` | ran, exit 0 |
| 4 | `scripts/check_prereg_order.py` | ran, exit 0 — 31 cells, 27 ok, 4 exempt, 0 failing |
| 5 | `scripts/verify_raw_archive.py` | ran against a path outside the repo; **exit 1** — class 2, recorded not fixed |
| 6 | `run_matrix --plan-only` / `--resume`, `analyze` | **FAILED, exit 2** — `REFUSED: --results-root is required` — D4 |
| 2 | `bash scripts/build_paper.sh` ×4, supplementaries first | all four exit 0 |

---

## 3. Every gate, in the clone

| gate | result |
|---|---|
| the suite, as printed | 2 081 passed, 34 skipped, coverage **90.78%** (after D5) |
| the suite with Redis up | **2 115 passed, 0 skipped, 0 failed** |
| `check_paper_numbers.py` **after** the four builds | **43 passed, 0 failed** |
| `validate_citations.py` | 371 / 0 |
| `verify_refs.py --offline` | exit 0 |
| `check_prereg_order.py` | 31 cells, 27 ok, 4 exempt, 0 failing |
| the provenance stamps | `anonymous build`, `supplementary.pdf`, `supplementary-anon.pdf` — all three **PASS before any build in the clone**, against the tracked PDFs and the clone's sources. This is phase 38's fix confirmed where it had never been checked. The fourth stamp is read through `paper/main.log`, which does not exist until a build, so it is covered by the post-build run |
| cross-document references | inside `check_paper_numbers`, passing |
| anonymity | inside `check_paper_numbers`, passing |
| `make reproduce-figures` (after fixes) | 6 IDENTICAL, 2 SKIPPED with the reason, exit 0 |
| `make reproduce-figures RUNS=<unpacked archive>` | **6 tables + both figures IDENTICAL, exit 0** |
| `make reproduce-smoke` | exit 0 |
| all four documents | built; `main.pdf` 23 pages, `supplementary.pdf` 6 |

---

## 4. The three classes

### Class 3 — defects. Five, all fixed.

**D1. `make reproduce-figures` regenerated a `numbers.tex` that was missing
seventeen macros.** The Makefile passes the generator's inputs explicitly.
Phase 25 added four WS-5 inputs to `paper_tables.py` and updated
`check_paper_numbers.py`, which builds its own invocation — and did not update
the Makefile. **Two callers of one generator, drifting apart, and only one of
them was ever run here.** The target reported `DIFFERS numbers.tex` for four
passes without being noticed, because nothing in this working tree runs it.
*Fixed:* a `WS5 :=` variable and the four flags, with the drift recorded in a
comment at the point of the defect.

**D2. The skip branch could not be reached. → `docs/25` R14 instance 11.**
`.SHELLFLAGS` is `-eu -o pipefail`. The guard read the archive manifest as
`want=$(sed … 2>/dev/null | head -1)`; with no manifest `sed` exits 2,
`pipefail` promotes it, `-e` aborts, and `make` prints `Error 2` — three lines
above the `SKIPPED:` message that explains exactly what to do. **A clone never
has that manifest, so the clean-clone case is the only case an evaluator has,
and the target failed in it.** It was green here for its whole life because this
working tree has an untracked `MANIFEST.md` in the archive root. *The tree where
the code is written is not the tree it will be run in, and the difference was an
untracked file.*
*Fixed:* the read is guarded by `[[ -f ]]`.
`tests/test_reproduce_figures_guard.py` (5 tests) extracts the guard from the
Makefile verbatim, runs it against a clone-shaped tree, **and runs the pre-fix
line beside it asserting exit 2** — rule 13 discharged against the real defect,
not a paraphrase.

**D3. `ARCHIVE` named two different things.** It was both "where the analysis
CSVs are" and "where the raw run directories are". They are the same tree here,
so the conflation was invisible; point it at a real unpacked archive — which is
what `ARTIFACT.md` told a reader to do — and the tables get redirected too, onto
the archived `comparisons-vs-aep-full.csv`, which is the pre-rebuild copy with
no `regime` column. The generator refuses it, correctly, and the whole target
dies. *Fixed:* `RUNS ?= $(ARCHIVE)`; the figures use `RUNS`, the tables stay
pinned to the tracked CSVs the paper cites. Verified with the real 432-run
archive unpacked: **six tables and both analysis figures byte-identical, exit 0**.

**D4. The `run_matrix` commands in §6 exited 2 as printed.** Phase 20 removed
`DEFAULT_RESULTS_ROOT` (the frozen root that even `--plan-only` used to write
into) and made `--results-root` required. `ARTIFACT.md` was not updated. *Fixed:*
the printed commands name a new dated root, and a comment says why the default
is gone.

**D5. Every documented `uv sync` line omitted `--extra b5`.** Three tests in
`tests/test_b5_collect_contract.py` import `temporalio` and fail with
`ModuleNotFoundError` rather than skipping. CI syncs `--extra b5` and is green;
no printed command did. *Fixed:* every sync line in `ARTIFACT.md` and
`README.md` now matches CI's extras exactly, and the prerequisites table says
what the extra is for. **Not fixed by making the tests skip** — that would have
changed what the command checks.

### Class 1 — prerequisites, now documented.

* **Build before you gate.** `check_paper_numbers.py` reads `paper/main.log` and
  `paper/main.bbl`, which are build products and are not committed, so in a
  fresh clone it fails 2 of 41 until `build_paper.sh` has run. `ARTIFACT.md`
  §2a now prints the build-first order, and why supplementaries come first.
* **The 34 skips are an opt-in, not a missing Docker.** They are behind
  `AEP_PHASE2_REDIS_INTEGRATION=1` and a `REDIS_URL` pointing at a dedicated AOF
  database, and each says so in its skip reason. With Redis up, 2 115 pass and
  nothing skips. The prerequisites table said "Docker"; it was wrong and now
  says this.
* **One test wants an idle machine.** The injector's cost-ratio test failed once
  here while a `make` target ran beside it, and passed three times alone.
  Recorded, not adjusted.

### Class 2 — outside the repository. One, already named.

`verify_raw_archive.py` defaults `--archive` to `/root/aep-raw-archive`, a path
on the measurement host. `docs/36` §4 line 149 already names it, with its size
and contents, and `docs/36` §5 names where the raw runs will live once the
Zenodo record is published. **No addition to `docs/36` was needed** — the one
thing this pass reached outside the repository was the one thing phase 38's
inventory had already recorded. `ARTIFACT.md` §5 now says a reader must point
`--archive` at their unpacked copy.

### Recorded, not fixed

`verify_raw_archive.py` **exits 1 on a clean verification.** Its summary line is
`IDENTICAL 114  IDENTICAL-after-normalisation 8  DIFFERS 0  NOT REGENERATED 8`,
and the exit code does not distinguish the last column from the third. The eight
are `container-precondition.json` (3), `fault-injection-census.json` (3) and
`foreign-load-sample.json` (2) — environment censuses the *collection* writes,
so `analyze.py` has nothing to compare them with. Changing the exit code would
change what the command checks, which this pass's bounds forbid; it is written
down in `ARTIFACT.md` §5 instead, where a reader meets the command.

---

## 5. The phase 17 / phase 18 dispute, settled

Phase 17 called `make reproduce-figures` broken. Phase 18 said it always
worked. The clone says **both were describing their own machine**: the target's
behaviour depends on what untracked state the tree happens to hold — a partial
run tree (phase 17's 84-of-432) or an untracked `MANIFEST.md` (D2). In a clean
clone, before this pass, it failed. After this pass it passes, and passes
*more* than it ever did here: with `RUNS=` pointed at the unpacked archive it
compares the two analysis figures as well, which no run in this working tree has
ever done.

---

## 6. What `ARTIFACT.md` now tells a reader, before they run anything

A new §2a, placed before the claims table, stating:

* which tools are needed and **what happens without each** — including that the
  poppler-dependent checks *fail closed* rather than skipping;
* that `make reproduce-figures` needs nothing but `uv`, takes a minute, and is
  the check that matters most;
* **what a clean clone cannot reproduce and why** — the two analysis figures
  (raw runs are archived, not committed), anything needing the raw runs until
  the Zenodo record is published, and the **two collection trees declared
  outside the archive**: `/root/aep-5b` (transient smoke output) and
  `/root/aep-stage3` (zero run directories, a source checkout), neither backing
  any number in the paper;
* the build-first ordering, and the reason it is not arbitrary.

Everything in it was established by running the command in the clone, not by
recalling what the command needs.

---

## 7. Not done, and why

* **No `.tex` prose changed. No numeric claim changed. Zero deletions.**
* The Zenodo deposit is untouched — out of scope, and still the step that makes
  the DOI resolve.
* `verify_raw_archive.py`'s exit code: see above.
* `make reproduce-figures RUNS=…` was verified against the 2026-09-03 archive's
  `matrix` root only. The extension archive's roots have no committed figures to
  compare against, so there is nothing for the target to check there.

---

## 8. Raw outputs

```
clone                     0baec98, 2026-09-15T16:07:39+05:00
                          3229 tracked / 3229 on disk / 42 MB
                          (working tree: 3229 / 29606 / 815 MB)

BEFORE THE FIXES, IN THE CLONE
make reproduce-figures                       exit 2   DIFFERS numbers.tex
make reproduce-figures ARCHIVE=<unpacked>    exit 2   "no regime column"
pytest (as printed)                          3 failed  ModuleNotFoundError: temporalio
check_paper_numbers.py                       exit 1   39 passed, 2 failed
run_matrix --plan-only (as printed)          exit 2   REFUSED: --results-root is required

AFTER THE FIXES, IN THE CLONE
make reproduce-figures                       exit 0   6 IDENTICAL, 2 SKIPPED (reason given)
make reproduce-figures RUNS=<unpacked>       exit 0   6 tables + 2 figures IDENTICAL
make reproduce-smoke                         exit 0   7 systems, frozen tree untouched
pytest (as printed)                          2081 passed, 34 skipped, coverage 90.78%
pytest with Redis up                         2115 passed, 0 skipped, 0 failed
check_paper_numbers.py (after builds)        exit 0   43 passed, 0 failed
validate_citations.py                        exit 0   371 citations, 0 invalid
verify_refs.py --offline                     exit 0
check_prereg_order.py                        exit 0   31 cells, 27 ok, 4 exempt, 0 failing
verify_raw_archive.py                        exit 1   26300 verified, 0 problems;
                                                      DIFFERS 0, NOT REGENERATED 8
build_paper.sh x4                            exit 0   main 23 pp, supplementary 6 pp

tests/test_reproduce_figures_guard.py        5 passed

R15 -- the gates that cover what this pass changed, in the WORKING TREE
  the suite (the new test; the Makefile and
  doc edits are reachable from three test files)  2081 passed, 34 skipped,
                                                  coverage 90.78%
  check_paper_numbers.py (cross-document
  references read README.md and ARTIFACT.md)      43 passed, 0 failed
  make reproduce-figures (the repaired target)    exit 0, 6 IDENTICAL,
                                                  SKIPPED 84-of-432 with both counts
  validate_citations.py                           371 citations, 0 invalid

.tex changed                                 0
deletions                                    0
```

---

## 9. The check that closes the pass: a second clone, of the pushed fix

The first clone was repaired by copying files into it, which proves the fix
works but not that the fix *shipped*. So the commit was pushed and a **second
clean clone** taken of it — `28a1936`, 3 232 tracked files, 3 232 on disk,
nothing copied in — and `ARTIFACT.md` followed as it now reads:

```
uv sync --frozen ... --extra b5                 exit 0
build_paper.sh x4, supplementaries first        exit 0, exit 0, exit 0, exit 0
make reproduce-figures                          exit 0   6 IDENTICAL, 2 SKIPPED with the reason
make reproduce-figures RUNS=<unpacked archive>  exit 0   8 IDENTICAL (6 tables + both figures)
check_paper_numbers.py                          exit 0   43 passed, 0 failed
validate_citations.py                           exit 0   371 citations, 0 invalid
verify_refs.py --offline                        exit 0
check_prereg_order.py                           exit 0   31 cells, 27 ok, 4 exempt, 0 failing
the suite, as ARTIFACT.md prints it             exit 0   2 081 passed, 34 skipped
run_matrix --results-root R --plan-only         exit 0   (it exited 2 as printed before)
```

Every command `ARTIFACT.md` prints now runs, from a clone, on a machine that
was given nothing but the repository.

---

**Pointer.** A clean clone of `0baec98` could not run the artifact's headline
command: `make reproduce-figures` exited 2 for two independent reasons — four
generator inputs the Makefile lost at phase 25, and a manifest read that aborted
the recipe instead of reaching its own skip message. Three more printed commands
failed as printed (`run_matrix` without `--results-root`, `uv sync` without
`--extra b5`, `ARCHIVE=` pointed at a real archive). All five are fixed, the
guard has a test that is watched failing against the pre-fix line, the abort is
`docs/25` R14 instance 11, and `ARTIFACT.md` §2a now states prerequisites and
reproducibility boundaries. In the clone: 2 115 tests pass with Redis up, 43 of
43 numbers, six tables and **both analysis figures** byte-identical, all four
documents built.
