# Phase 23 — WS-5 closed, and R16 instance 3

**Rule 4.** Committed with the pass that executed it.

**Issued:** 2026-09-14.

## The prompt, as issued

> **Ruling: the class sweep stays at four sessions.** Amendment 1 §2 already
> fixed the result as a bound rather than a test, which is the only thing six
> sessions would have bought. §VIII's claim — that this design could not have
> found an effect — is stronger at four than a mixed six-session tree would
> allow. No further WS-5 collection will happen. This pass closes the
> workstream and fixes one defect that phase 22 surfaced.
>
> 1. Commit this prompt.
> 2. Record the ruling as an amendment, not as a report line (amendment 4).
> 3. Record the design discontinuity where a reader will hit it.
> 4. R16 instance 3 — `run_matrix.py:89`. Rule 13 before the fix.
> 5. Close WS-5 in `docs/26` §7.
> 6. R15 scoped to step 4. Zero `.tex`.
>
> Out of scope: zero `.tex`, any collection, re-collection of anything.

## Corrections and deviations, recorded rather than applied silently

**1. The rule-13 harness contaminated the frozen matrix root.** Running the new
tests against the pre-fix module under pytest meant calling `main()` with no
refusal to return at, so it began collecting: 19 run directories, 240 files,
into `experiments/results/matrix`, plus `matrix-plan.json`/`.txt` overwritten.
Phase 20's `RAW-SHA256SUMS` reported **0 missing, 0 changed, 240 added**; the 19
were removed by name and the tree digest returned to `abd4cebb5dac73f5…`. The
two plan files are not recoverable — root-level files are outside that digest's
coverage. Third occurrence of this shape in a week; generalised as `docs/25`
**R16a**.

**2. `check_paper_numbers.py` is left red, deliberately.** The R16 fix added 29
net lines to `experiments/run_matrix.py`, so `\HarnessLoc` moves 27,098 →
27,127. Repairing it means regenerating `paper/generated/numbers.tex` **and**
rebuilding the paper — a `.tex` change and manuscript work, both outside this
pass's bounds. It is recorded as the manuscript pass's first required action,
with the exact commands, in the phase 23 report §5.
