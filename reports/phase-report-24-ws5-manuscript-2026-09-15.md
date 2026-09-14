# Phase 24 — WS-5 → manuscript — **steps 4, 5 and 6 blocked; 1, 2, 3, 7 done**

## Asked / Done

Asked: regenerate and get the gate green, add the rule phase 23 earned, retire
28.0 ms in §VI-RQ3, report the `always` arm, give H1–H5 their sentences with
H4's +9.33 pp in §VI, add §VIII's three items, rule 3 on every number, rebuild.

Done: steps 1, 2, 3 and 7 in full.

**Steps 4, 5 and 6 are blocked, and the bounds are what block them.** Every
number those steps require has no macro, and creating one means editing
`scripts/paper_tables.py`, which is not in this pass's scope. The prompt says
"if a number you need does not exist in a tracked CSV, stop and say so" — the
numbers *do* exist in tracked CSVs; what does not exist is the generator path
from those CSVs to `numbers.tex`, and rule 1 forbids typing them by hand.

---

## 1. Step 2 — the gate, green before prose was touched

```
page count BEFORE                24
paper_tables.py regenerated      \HarnessLoc}{27\,127}
check_paper_numbers.py           33 passed, 0 failed
```

**One thing the prompt did not anticipate.** Regenerating `numbers.tex` makes
*four* documents stale, and `build_paper.sh` runs `check_paper_numbers.py` and
refuses to overwrite `main.pdf` while any of them is — so the first main build
failed with `DO NOT SUBMIT … Existing main.pdf preserved`. The documents have to
be built in dependency order, supplementaries first:

```
build_paper.sh --supplementary              exit=0
build_paper.sh --supplementary --anonymous  exit=0
build_paper.sh --anonymous                  exit=0
build_paper.sh                              exit=0
```

That is the gate working correctly — it refuses to produce a submission PDF
whose sibling artifacts disagree with the sources — and it is worth writing down
because the obvious build order does not work.

## 2. Step 3 — `docs/25` R17

> **R17. Reaching a script's `main()` to prove it misbehaves *is* running it.**

All three occurrences named, in a table: phase 19 (the unrepaired
`fsync_always_benchmark.sh` via its parametrised run-count test, 60 executions
deleted), phase 20 (the pre-guard `wsl_launch_matrix.sh` *inside the harness
written to enforce R16*, a detached `run_matrix` launched), phase 23 (the
pre-fix `run_matrix.main()` under pytest, 19 run directories written into the
frozen matrix root).

The rule states the shape they share: **a refusal test is safe against fixed
code by construction and unsafe against old code by construction**, so the test
that proves the fix works is exactly the test that must never meet the defect.
It also records that `--plan-only`, documented as read-only, writes into the
results root before returning — a flag's documentation is a claim about the
code, not a property of it.

*Placement note.* The prompt said "beside R13 and R16a". R16a already carries
this material from R16's side; R3 and R4 carry the failing-branch side. I made
it a top-level **R17** with cross-references to all three rather than a
sub-rule, because occurrence 2 was not about a results root at all, so the
principle generalises past R16. Recorded here in case that was not the intent.

## 3. Step 7 — §VIII, all three items

**(a) The theorem form was already there** and needed no change: the paragraph
at `08-threats.tex:322` already states $2/2^{n}$, four sessions,
$\SignFloorFour{}$, "no effect size, however large, could have produced a
rejection", and the six-session minimum via $\SignFloorSix{}$. Both macros
exist. An earlier pass had done this.

**(b) Four sessions by ruling, and the cell-major confound** — new, appended to
that paragraph (`08-threats.tex:342`):

> We stopped at four sessions deliberately rather than for want of machine time,
> and the class sweep is reported as a bound rather than as a test. Two further
> sessions were collected far enough to establish that they could not be pooled
> with the first four: the original sessions run one arm to completion and then
> the other, while the harness now alternates the arms run by run, a change made
> because the block order makes arm and drift collinear and therefore not
> separable by any number of sessions. Adding interleaved sessions to blocked
> ones would put two designs inside one paired test. Each session directory
> carries a note recording its order and what that confounds.

**(c) The destroyed-and-recovered cell — one sentence**, as its own paragraph at
`08-threats.tex:353`, placed with the other measurement-defect disclosures:

> The raw runs behind the `appendfsync always` cell were deleted from a working
> checkout by a collection script whose clean path defaulted to on, and were
> restored from the verified evidence archive, whose manifest covers them by
> name and digest; the derived results are unchanged and remain recomputable
> from raw.

One sentence, stated neutrally, with a LaTeX comment naming the archive digest's
location and the 112-of-112 verification. No new macro: it quotes no number in
the prose.

## 4. Steps 4, 5, 6 — blocked, and exactly why

`paper/generated/numbers.tex` holds **197 macros. Not one is derived from a
WS-5 cell.** Every RQ3 macro comes from the three-run frozen matrix cell:

```
ProtocolMinusBarrier   = 28.0      % = 2038.2 - 2010.2   (3 runs)
ProtocolMinusBarrierLow/High       % bootstrap over 3 and 3 runs
BarrierCost            = 1\,966.7  % = 4004.9 - 2038.2   (3 runs)
BarrierCostAlways      = 15.0      % fsync-always/ (the 3-run August cell)
```

`paper_tables.py` takes five input paths (`--analysis`, `--fsync-analysis`,
`--flakey`, `--b5-session`, `--writeloss-cell`). **None of them can be pointed
at a WS-5 root**, and `check_paper_numbers.py` hardcodes all five as defaults,
so changing the invocation alone would turn the gate red.

What each blocked step needs, and where the number already sits:

| step | claim | number | tracked CSV that has it |
|---|---|---|---|
| 4 | barrier cost, 15 runs | 1 939.7 [1 855.8, 1 962.4] ms | `ws5-2026-09-10/t1-p0-everysec/analysis/` |
| 4 | protocol − barrier, pooled | 33.9 [−122.6, +120.1] ms | same |
| 4 | protocol − barrier, lower-mode | 16.3 [−54.1, +47.5] ms | same |
| 5 | `always` barrier cost, 45 runs | **−9.2 ms** (2 079.80 − 2 089.03) | `fsync-always-2026-09-14/analysis/latency-and-throughput.csv` |
| 6 | H2 upper-mode fraction | 0.20 | `ws5-2026-09-10/t1-p0-everysec/analysis/` |
| 6 | H3 two violating cells | 0.0333 vs 0.0044 | `ws5-2026-09-10/t2-p30/analysis/` |
| 6 | **H4 declared ambiguity, POS-ONLY** | **+9.33 pp** | `ws5-2026-09-10/t2-keying/analysis/` |
| 6 | H5 difference and interval | +1.33 [−2.67, +5.11] pp | `ws5-2026-09-10/t2-p30/analysis/` |

**The `always` result is worth stating here even though it cannot yet go in the
paper.** At 45 runs the barrier's cost under `appendfsync always` is
**−9.2 ms** — AEP-full's median 2 079.80 against B3's 2 089.03. Negative, and
therefore near-zero. That is exactly the shape the pre-registration said to
expect and refused to treat as a failure, and it is a *stronger* result than the
three-run cell's 15.0 ms: it says the barrier's ≈ 1 940 ms under `everysec` is
the fsync boundary and not the barrier. Read from the committed CSV; nothing was
recomputed.

**The minimal unblocking change**, for whoever authorises it:

1. `scripts/paper_tables.py`: accept `--ws5-everysec`, `--ws5-p30`,
   `--ws5-keying` and `--fsync-always-45` and emit macros from them.
2. `scripts/check_paper_numbers.py`: add the same four defaults, so the gate
   regenerates with them and rule 3 keeps holding.
3. Then steps 4–6 are prose over existing macros.

Both files are load-bearing scripts, so rule 14 applies: each change needs a
test, and R17 now governs how that test is written.

## 5. What the paper still claims that the data no longer supports

Unchanged by this pass, and this is the cost of stopping:

* **§VI-RQ3 still quotes `\ProtocolMinusBarrier{}` = 28.0 ms** at
  `06-evaluation.tex:672`, from three runs. At fifteen it is 33.9 ms with an
  interval of [−122.6, +120.1] that spans zero under both readings.
  §VI already quotes the three-run interval beside it and already says the
  decomposition supports "an ordering and an order of magnitude — the barrier
  dominates — and not the ratio of the two numbers", so the paper is not
  asserting more than it can support. It is asserting it from the smaller
  sample.
* **§VIII:303 still says "Closing this needs more crash-free runs."** Those runs
  now exist — 15 per arm under `everysec`, 15 per arm under `always`. The
  sentence is true as written and stale in its implication.

Neither was edited, because editing either means quoting a number that has no
macro.

## 6. Rule 3, and what was not touched

Nothing under `paper/generated/` was hand-edited; `numbers.tex` changed only by
regeneration, and only `\HarnessLoc`. The two new §VIII passages quote **no**
numeric claim, so rule 3 has nothing to attach to beyond the source comment on
the archive digest. `analysis/table-1.csv` is not cited anywhere new.

## 7. Raw outputs

```
BEFORE                     24 pages
AFTER                      25 pages        (+1, both §VIII additions)
check_paper_numbers.py     33 passed, 0 failed      (before prose, and after)
validate_citations.py      OK: 371 citations, 0 invalid
builds                     main, main-anon, supplementary, supplementary-anon  all exit 0
full suite                 2039 passed, 34 skipped  (the 34 are the Redis-integration tests, expected without compose up)
.tex files changed         1  (paper/sections/08-threats.tex)
generated files changed    1  (paper/generated/numbers.tex, by regeneration)
```

## 8. Findings outside scope

1. **The macro pipeline has no WS-5 path at all.** This is the finding, not an
   inconvenience: five pre-registered hypotheses were collected, analysed and
   ruled, and none of their numbers can reach the manuscript under rule 3
   without a generator change nobody has scheduled. The gate that keeps the
   paper honest is also what keeps the new results out of it.
2. **`build_paper.sh` cannot build `main.pdf` first after a macro change.** Not
   a defect — it is the staleness gate — but the four documents have a build
   order and nothing documents it.
3. **§VI-RQ3's `\BarrierCostAlways{}` is the three-run figure (15.0 ms) while a
   45-run replacement (−9.2 ms) sits committed and unused.** Of everything
   blocked here, this is the one where the paper's current number is most likely
   to be read as more precise than it is.

## 9. Page count

| | pages |
|---|---|
| before | 24 |
| after | **25** |

+1, entirely from §VIII's two additions. M5's ≤ 16-page target is WS-9's work
and this pass moved the number the wrong way by one page, as any addition to
§VIII would.
