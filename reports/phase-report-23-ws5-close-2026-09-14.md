# Phase 23 — WS-5 closed, and R16 instance 3

## Asked / Done

Asked: commit the prompt, record the four-session ruling as an amendment,
record the design discontinuity beside the data, fix `run_matrix.py:89` with
rule-13 evidence, add R16 instance 3, close WS-5 in `docs/26` §7, R15.

Done: all seven. **WS-5 is closed.** The class sweep stands at four sessions by
ruling, `run_matrix.py` no longer defaults to a frozen root, and the
discontinuity is recorded in the four session directories themselves.

**And I damaged the frozen matrix root while proving the defect, for the third
time in this project.** It was fully repaired and verified. §3 is the account.

---

## 1. Amendment 4 — the ruling

`reports/phase-report-ws5-prediction-amendment-4-2026-09-14.md`. Amendments 1–3
unedited (rule 5); amendment 1 §2's "two sessions are added to the existing
four" is **superseded, not rewritten**.

The argument in one line: amendment 1 §2 had already fixed this result as **a
bound rather than a test**, so the 2/2ⁿ floor the extra sessions would have
moved is not load-bearing — it matters only if a p-value is quoted, and
amendment 1 ruled that one will not be. §VIII's claim is *stronger* at four: at
n = 4 "this design could not have found an effect" is a theorem (no effect size
whatever yields p ≤ 0.05), and a six-session tree of mixed design would replace
a clean impossibility result with a messier one.

## 2. The discontinuity, recorded beside the data

`COLLECTION-NOTE.md`, tracked and un-ignored, in all four session roots:

```
experiments/results/b2-2026-08-21/COLLECTION-NOTE.md
experiments/results/b2-s1-2026-08-21/COLLECTION-NOTE.md
experiments/results/b2-s2-2026-08-21/COLLECTION-NOTE.md
experiments/results/b2-s3-2026-08-21/COLLECTION-NOTE.md
```

Each states: the session is cell-major; `5b601d0` (2026-08-28) introduced
run-level interleaving because arm and drift were *perfectly collinear* and the
confound is **non-identifiable**; these sessions pre-date it by a week; the
`b2-paired-v2-*` re-collection precedent exists and was **deliberately not
followed**, with the reason. It also carries the second asymmetry a reader needs:
all 60 runs have `suspend_disabled_declared = false`, so all 60 are already
excluded from every absolute-timing aggregate — **anything computed from these
sessions is a rate claim.**

## 3. R16 instance 3 — and the third time the demonstration caused the defect

### The defect

`experiments/run_matrix.py:89` — `DEFAULT_RESULTS_ROOT = "experiments/results/matrix"`,
the frozen 432-run root. Worse than a bad default: **`--plan-only` writes into
it too**, because the plan files are written before that flag returns. The
module's own docstring offers `--plan-only` as the safe "prints exactly which
cells are in which tier before anything is launched" path. Demonstrated safely,
in a sandbox with CWD elsewhere, before the fix:

```
$ cd /root/p23-sandbox && python -m experiments.run_matrix --plan-only
exit=0
created  experiments/results/matrix/matrix-plan.txt
         experiments/results/matrix/matrix-plan.json
```

**Why phase 20 missed it.** That sweep enumerated *shell* scripts, fixed two,
and wrote a bash guard. The Python driver both of those shell scripts call was
never in its search. A sweep is bounded by the file type it greps for, and
nothing in it said so.

**Fixed:** no default; `--results-root` required for every invocation including
`--plan-only`; refusal before `build_plan`; and `DEFAULT_RESULTS_ROOT` **deleted**
rather than set to `None`, because a constant naming the frozen root is one
`default=` away from returning. Six tests, all on refusals, including one that
records every file's mtime under the frozen root, runs all four refused forms,
and asserts nothing moved.

### What I did to the frozen root

The first rule-13 harness ran the new tests against the **pre-fix module under
pytest**. With no refusal to return at, `main(["--regime", "redis-kill-preack"])`
went past `--plan-only` and **started collecting into the frozen root**. Killed
by PID once noticed. Damage:

```
run directories        103 where 84 belong   (19 added)
files                  240 added
matrix-plan.json/.txt  overwritten
```

**Phase 20's digest is what made this recoverable.** `--check` against the
committed `RAW-SHA256SUMS`:

```
matrix: 1101 files, 0 missing, 240 added, 0 changed   tree digest DIFFERS
```

**0 missing, 0 changed** — nothing original was destroyed or altered. The 19
directories were listed by the digest, each confirmed absent from it, and
removed **one named directory at a time** — not a prune, not an `rm -rf` of the
root. After repair:

```
run dirs 84    matrix: 861 files, 0 missing, 0 added, 0 changed
tree digest matches abd4cebb5dac73f5c9fb66923e1d8bbacd7975dd564316b3fc19af0989687dc5
SHA256SUMS 17 OK    git status on the root: clean
```

**What is not recoverable:** `matrix-plan.json` and `matrix-plan.txt` were
overwritten. They are root-level files, so `RAW-SHA256SUMS` (run directories
only) and `SHA256SUMS` both miss them, and this checkout's matrix root was
excluded from the Phase-11 archive as an older incomplete copy. They are derived
artefacts, not run evidence — but **the digest's coverage boundary is a real gap
and this is the first time it has cost anything.**

### R16a, added to `docs/25`

Third occurrence in a week: phase 19 deleted the `fsync-always` raw tree this
way, phase 20 reproduced R16 inside the harness written to enforce R16, phase 23
contaminated the matrix root. The rule now says what the three have in common:
**for a driver whose non-refusing path collects, R13 is discharged by source
evidence plus a sandbox with CWD elsewhere, never by calling it** — and the new
tests point at the fixed module only, which is safe by construction precisely
because every path in it refuses.

## 4. `docs/26` §7 — WS-5 closed

Two boxes ticked (≥ 15 runs per timing interval; 30%-regime, in-flight kill and
keying variant collected), and a third line added that states the exception
rather than hiding it inside a tick:

> **WS-5 is closed to further collection** (amendment 4). The `always` arm is
> collected (45 runs, phase 21). The capability-class sweep **stays at four
> sessions by ruling**, reported as a bound with its 0.125 sign-test floor
> stated, not as a test … Nothing in WS-5 is now "implemented but not
> collected"; the class sweep is "collected and deliberately not extended",
> which is a different statement and is the one the paper must make.

## 5. R15, scoped — and one gate is red, deliberately

```
tests covering the changed file (found, not assumed): tests/test_run_matrix_results_root.py
that + guard + digest suites                          39 passed
every caller of run_matrix still passes --results-root  3/3
validate_citations.py                                 OK: 371 citations, 0 invalid
every raw digest --check (incl. the repaired root)    0 failing
zero .tex changed                                     0
check_paper_numbers.py                                32 passed, 1 FAILED
```

**The failure is real, is mine, and is not repaired in this pass.** The only
differing macro is `\HarnessLoc`: regenerated **27,127** against committed
**27,098**. `git diff --numstat experiments/run_matrix.py` is `34 5` — **+29 net
lines**, exactly the difference. Every other generated file is byte-identical
(`table-ablation`, `table-ambiguity-by-crashpoint`, `table-deployment-choice`,
`table-latency`, `table-outcomes`).

So the gate is working exactly as designed: harness code changed, therefore the
harness-size macro must be regenerated. `\HarnessLoc` is used once, at
`paper/sections/05-implementation.tex:6`.

**Why I did not fix it.** Regenerating `paper/generated/numbers.tex` changes a
`.tex` file, and this pass's bounds say **zero `.tex`**. It also makes the built
PDFs stale, which `check_paper_numbers.py` separately checks, so the real repair
is regenerate **and rebuild** — manuscript work, which is the next pass by
explicit instruction. Regenerating without rebuilding would trade one red check
for another while breaking a stated bound.

**This is the manuscript pass's first required action**, before anything else it
does:

```
python scripts/paper_tables.py --analysis experiments/results/matrix/analysis \
  --fsync-analysis experiments/results/fsync-always/analysis \
  --flakey experiments/results \
  --b5-session reports/raw/ws6-b5-s1-2026-09-08-attempt3 \
  --writeloss-cell reports/raw/ws4-writeloss-s1-2026-09-07 \
  --out paper/generated
bash scripts/build_paper.sh
```

## 6. Findings outside scope

1. **`RAW-SHA256SUMS` covers run directories only.** Root-level files
   (`matrix-plan.json`, `matrix-plan.txt`, `matrix-progress.jsonl`) are bound by
   nothing, which is why this pass's only permanent loss is two of them.
   Widening the tool's coverage is a change to a load-bearing script and belongs
   in its own pass with its own rule-13 evidence.
2. **The harness LOC macro couples the manuscript to every tooling change.**
   Any safety fix to `experiments/**.py` turns `check_paper_numbers.py` red
   until the paper is rebuilt. That is the gate doing its job, and it also means
   tooling passes and manuscript passes cannot be fully separated. Recorded, not
   acted on.

## 7. Environment

`uv run --frozen --extra dev --extra cov --extra experiments --extra analysis
--extra b5`, CPython 3.13.0, WSL2 6.6.114.1. No collection, no Docker
container started or stopped by this pass. The frozen matrix root was
contaminated and repaired within it; its tree digest is back to its committed
value.
