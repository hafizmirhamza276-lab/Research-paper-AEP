# WS-6 — the reading, corrected cell (attempt 3)

**8 September 2026.** `analyse_b5_agreement.py` run **unmodified** (script at
`4f31c42`, working tree clean) against attempt 3's session root (`7fddd91`).
Exit 0. Output kept beside the data as `agreement.txt` / `agreement.json`.

**No change was made to the script, and the paper was not touched.**

---

## 1. The reading

**All four testable cells `DISAGREES`. All four reached the overlap test —
stage 4 of 4. None resolved early.**

| Hypothesis | Response class | runs | void | pend | B5 | frozen B4/B4b | stage |
|---|---|---|---|---|---|---|---|
| H1 duplicates | AUTHORITATIVE | 30 | 0 | 0 | **0.1567** [0.1233, 0.1900] | 0.9333 [0.9000, 1.0000] | **4 — overlap** |
| H1 duplicates | NO_READBACK | 30 | 1 | 0 | **0.1586** [0.1241, 0.1931] | 0.9667 [0.9000, 1.0000] | **4 — overlap** |
| H2 lost effects | AUTHORITATIVE | 30 | 0 | 0 | **0.1433** [0.1067, 0.1833] | 0.9667 [0.9000, 1.0000] | **4 — overlap** |
| H2 lost effects | NO_READBACK | 30 | 1 | 0 | **0.1414** [0.1034, 0.1828] | 0.8667 [0.8000, 0.9000] | **4 — overlap** |

Stage by stage, for all four: **stage 1** absent-point — passed (not
`after_intent_before_barrier`). **Stage 2** voids — passed; one void excluded in
each `NO_READBACK` cell, none in the others. **Stage 3** pending bound — passed,
silently, with **0 `PENDING_AT_DEADLINE` in every cell** (0% against the
pre-registered 20%); the script emits no stage-3 line when pending is zero.
**Stage 4** overlap — reached, and none overlapped.

### H3 — non-escalation: **HELD**

**No declared ambiguity appeared.** 0 across 118 non-void runs. H3 is absolute —
one would refute it — and none occurred.

## 2. The intervals now have width, and the counts behind them vary

This is the check attempt 2 failed, and the corrected re-registration §5 requires
it: *a cell whose non-void runs are all identical is reported as
instrument-constrained, not as a result.* **That condition is not met here.**

Per-run counts of the field each hypothesis is computed from:

| Cell | n | min | med | max | **distinct values** | distribution | sd |
|---|---|---|---|---|---|---|---|
| H1 AUTHORITATIVE | 30 | 0 | 1.5 | 3 | **4** — [0,1,2,3] | 0×4, 1×11, 2×9, 3×6 | 0.971 |
| H1 NO_READBACK | 29 | 0 | 2.0 | 3 | **4** — [0,1,2,3] | 0×4, 1×10, 2×9, 3×6 | 0.983 |
| H2 AUTHORITATIVE | 30 | 0 | 1.0 | 4 | **5** — [0,1,2,3,4] | 0×5, 1×14, 2×5, 3×5, 4×1 | 1.073 |
| H2 NO_READBACK | 29 | 0 | 1.0 | 4 | **5** — [0,1,2,3,4] | 0×5, 1×14, 2×4, 3×5, 4×1 | 1.086 |

Every cell spans the full range from 0 to 3 or 4, with a mode at 1 and standard
deviations near 1.0. Interval widths follow:

| Cell | attempt 2 width | **attempt 3 width** |
|---|---|---|
| H1 AUTHORITATIVE | 0.0000 | **0.0667** |
| H1 NO_READBACK | 0.0214 | **0.0690** |
| H2 AUTHORITATIVE | 0.0000 | **0.0767** |
| H2 NO_READBACK | 0.0000 | **0.0793** |

For comparison, the same read of attempt 2's H2 cells gives **one distinct value
(`[3]`) in 30 of 30 runs, sd = 0.000**. The clusters are now genuinely distinct
draws, so the run is the right unit again and the bootstrap is describing
something.

**This is not a comparison between attempts.** Attempt 2 did not measure this
cell; its fault stream was fixed. The two are set side by side only to show that
the instrument-constrained condition applied there and does not apply here.

## 3. Four cells are NOT_TESTABLE_ABSENT_IN_B5

`after_intent_before_barrier`, at **both** response classes, for **both** H1 and
H2 — resolved at **stage 1**, before any arithmetic, `runs_total = 0`.

**The comparison is not complete.** B5 has no such position, while **B4 and B4b
have frozen data there at all three response classes**. It is a hole in B5 where
B4 has numbers, not a shared absence, and no agreement claim covers it. The
script says so in its own summary.

## 4. The voids, from the script's own output

Confirmed from the script rather than assumed. Its header:

```
runs: 120 total, 2 voided as instrument failures and excluded from every rate
       2  VOID_WORKER_NEVER_READY
```

and per affected cell:

```
1/30 runs voided as instrument failures and excluded from the rate:
{'VOID_WORKER_NEVER_READY': 1}
```

`voided_runs = 2`, `voids_by_verdict = {'VOID_WORKER_NEVER_READY': 2}`. One fell
in each `NO_READBACK` cell, which is why those two compute over 29 runs.
Excluded from every rate and reported with counts — not averaged in as zeros.

## 5. H1's units, and when they were changed

H1 now compares `undetected_duplicate_executions` on both sides, against a frozen
numerator that is `int(execution.is_undetected_duplicate)`. **H2 was already
units-consistent and was not changed.**

Under attempt 2's units — B5's *applications* count against B4's *executions*
indicator — H1 read `DISAGREES` at **0.4000** and **0.4107**. That is recorded
here **not as a comparison between attempts**, since attempt 2 did not measure
this cell, but so the record shows plainly that **the units correction was
committed at `4f31c42`, before this data existed at `7fddd91`, and before it was
read.** The ordering is the whole point of it being recorded at all.

## 6. A finding, recorded and not fixed

**Attempt 2's records do not contain `undetected_duplicate_executions` at all** —
the field is absent in all 30 and all 28 runs of its two `B5_TEMPORAL` cells,
because `collect.py` only began writing it at `4f31c42`.

`cell_interval` reads `int(run.get(metric_field, 0))`, so running the **corrected**
script against attempt 2's session would silently compute **H1 = 0.0000** from a
missing field rather than failing. The corrected re-registration already forbids
re-reading that session, and this is the concrete failure mode if anyone does.

**Not fixed in this pass.** Changing the script is what the ordering exists to
prevent, and this pass reads a result. Recorded so the next reader meets it as a
known hazard.

## 7. What this does and does not say

The reading is `DISAGREES` on all four testable cells, on a harness whose
per-run fault streams are now proven to vary and whose per-run counts do vary.
The two defects that stood between the previous reading and any claim about B4
are closed.

**What this pass does not do:** it draws no conclusion about §VI or §VIII, makes
no claim about what the disagreement means for B4, regenerates no macro, and
touches no manuscript prose. That is a separate pass.
