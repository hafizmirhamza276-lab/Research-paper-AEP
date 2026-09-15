# Phase 25 — WS-5 macros: §VI-RQ3 unblocked

## Asked / Done

Asked: wire four WS-5 inputs through the generator and the gate, emit the macros
§VI-RQ3 needs, test both scripts per rule 14 and R17, prove the existing 197 are
untouched, rebuild.

Done: all of it. **17 macros added, 197 unchanged, gate green at its new count
of 39.** No `.tex` was hand-edited; `numbers.tex` changed only by regeneration.

One thing had to be built that the prompt did not anticipate, and it is
described in §4 rather than buried: the gate has a check that *every* generated
macro is used in the manuscript, so emitting macros a pass ahead of the prose
fails it by construction.

---

## 1. The four inputs

`--ws5-everysec`, `--ws5-p30`, `--ws5-keying`, `--fsync-always-45`, on
`paper_tables.py`, **each `default=None`**. R16's lesson is applied literally:
no input that names a results root gets a default, because a default pointing at
one is what wrote into the frozen matrix root twice.

`check_paper_numbers.py` now carries the same four as defaults and passes them
to the generator, so the gate regenerates with exactly the inputs the documented
invocation uses. That identity is the whole reason the gate is worth anything —
a gate regenerating from different inputs certifies a `numbers.tex` nobody can
reproduce. Absence of any of the four is a **failure**, not a silent skip, in
the same list as the WS-4 and WS-6 inputs.

## 2. Macros added — 17, each with its CSV cell

Every value below was produced by the generator from a committed CSV and matches
the phase 17/18 verdicts exactly.

**Barrier cost under `everysec`, 15 runs per arm** — `ws5-2026-09-10/t1-p0-everysec/analysis/per-execution.csv`, cluster bootstrap over runs, 10 000 resamples, seed 20260806:

| macro | value |
|---|---|
| `\BarrierCostFifteen` | 1 939.7 |
| `\BarrierCostFifteenLow` | 1 855.8 |
| `\BarrierCostFifteenHigh` | 1 962.4 |

**Protocol − barrier, both readings** — same CSV, same estimator. Amendment 2
rules that both are reported and neither chosen silently:

| macro | value | reading |
|---|---|---|
| `\ProtocolMinusBarrierFifteen` | 33.9 | pooled (the pre-registered default) |
| `\ProtocolMinusBarrierFifteenLow` | −122.6 | |
| `\ProtocolMinusBarrierFifteenHigh` | 120.1 | |
| `\ProtocolMinusBarrierLowerMode` | 16.3 | lower-mode, boundary pinned by amendment 3 |
| `\ProtocolMinusBarrierLowerModeLow` | −54.1 | |
| `\ProtocolMinusBarrierLowerModeHigh` | 47.5 | |

**Both span zero.** The lower-mode boundary comes from
`power_analysis.lower_mode_difference`, imported rather than reimplemented, so
the manuscript and the pre-registered analysis stay on one definition of where
the lower mode ends.

**The 45-run `always` arm** — `fsync-always-2026-09-14/analysis/`:

| macro | value |
|---|---|
| `\BarrierCostAlwaysFortyFive` | **−9.2** |
| `\BarrierCostAlwaysFortyFiveLow` | −27.2 |
| `\BarrierCostAlwaysFortyFiveHigh` | 44.6 |
| `\AepAlwaysFortyFiveMedian` | 2 079.8 |
| `\BthreeAlwaysFortyFiveMedian` | 2 089.0 |

Negative, with an interval spanning zero. Pre-registration §4 is explicit that
"the interval must exclude zero" is *not* a sensible criterion for this arm, and
the macro's own provenance comment says so, so the number cannot be quoted
without meeting that framing.

**H4 — the sensitivity check that was predicted null and is not** —
`ws5-2026-09-10/t2-keying/analysis/per-cell-metrics.csv` against the frozen
matrix, pooled over the six crash points within the class:

| macro | value | cell |
|---|---|---|
| `\KeyingAmbiguityOracle` | 44.33 | `ORACLE_FINGERPRINT`, 399/900 |
| `\KeyingAmbiguityCaller` | 35.00 | `CALLER_REFERENCE`, 63/180 |
| `\KeyingAmbiguityDelta` | **9.33** | nearly twice the 5 pp margin |

### Naming

Every WS-5 macro carries its run count: `Fifteen`, `FortyFive`. The three-run
macros are **kept**, because §VIII argues from them about what three runs can
support — so `\BarrierCost` (3 runs) and `\BarrierCostFifteen` both exist, and
the names say which is which at the point of use. A test asserts they differ.

## 3. Proof the existing 197 are unchanged

```
macros before   197
macros after    214        (+17)
existing macros with a changed value   0
```

Measured by diffing `numbers.tex` before and after and counting `^<` lines that
define a macro: **zero**. The only pre-existing macro that has moved in this
whole sequence is `\HarnessLoc`, and that was phase 24.

## 4. What had to be built, and why it is not a hole

`check_macros_are_used` fails on any macro defined and not used. Seventeen
macros emitted a pass ahead of the prose that will quote them fail it by
construction, and the two ways out — write the prose (a `.tex` edit, out of
scope) or not emit them (defeats the pass) — were both closed.

So the gate gained `PENDING_MACROS`: a name-to-reason map, every entry reading
*"phase 26, section VI-RQ3"*. **It is not an allowlist that subtracts.** It adds
two checks that can fail:

* **"every pending macro still exists"** — a name that has vanished from
  `numbers.tex` is a stale entry.
* **"no pending macro is already in use"** — a name that *is* used is an entry
  someone forgot to delete.

and it prints `NOTE 17 macro(s) staged for prose that does not exist yet`, so
the staging is visible on every run rather than silent. `Result.note` was added
for that: neither a pass nor a failure.

**The intended failure mode is that phase 26 cannot finish without emptying this
list**, because using a macro trips the second check.

## 5. R17 compliance

R17 was written in phase 24 and this is its first application. **No test here
executes an older version of either script.**

* The R16-shaped assertions — "no input defaults to a results root", "the gate
  passes every input to the generator", "a missing input is a failure" — read
  **source text**.
* The behavioural tests run the **current** generator into a `tmp_path`, which
  is where its only writes go.
* The absent-input test asserts that no macro is emitted rather than that a zero
  is, because a zero is indistinguishable from a measurement.

Ten tests, all passing.

## 6. Not done, and why

**H2, H3 and H5 have no macros.** Phase 24 §4 listed them as blocked and they
remain so, for three different reasons worth separating:

* **H5's interval** is a *stratified* run-cluster bootstrap preserving
  crash-point, endpoint-capability and keying strata. `paper_tables.py` has an
  unstratified estimator; adding the stratified one is a new estimator in the
  generator, which is the kind of change that needs its own pre-registration
  check rather than being slipped into a plumbing pass.
* **H3's verdict is two cells at 1 event in 30**, and the finding is that the
  criterion fails for a denominator reason. A macro for "0.0333" would put a
  number in the paper whose interest is entirely in its denominator.
* **H2's upper-mode fraction** is available, but amendment 2 already supersedes
  phase 17's verdict on it, and the manuscript claim §VI needs is the *pooled
  median stands* — which `\ProtocolMinusBarrierFifteen` already carries.

Each is a judgement about what belongs in the paper, not a technical block. If
phase 26 wants any of them, say so and they are a small addition — except H5,
which is an estimator change.

## 7. Raw outputs

```
generator flags added      --ws5-everysec --ws5-p30 --ws5-keying --fsync-always-45
                           all default=None
gate defaults added        the same four; absence is a failure
macros                     197 -> 214, 0 existing values changed
check_paper_numbers.py     39 passed, 0 failed   (was 33; +4 presence, +2 pending)
                           NOTE 17 macro(s) staged for prose that does not exist yet
validate_citations.py      OK: 371 citations, 0 invalid
tests/test_ws5_macros.py   10 passed
full suite                 2049 passed, 34 skipped  (2039 before: +10 new; the 34 are Redis-integration, expected)
builds                     supplementary, supplementary-anon, anon, main -- all exit 0
.tex hand-edited           0
pages                      25 -> 25
```

## 8. Findings outside scope

1. **`paper_tables.py` now imports `power_analysis`.** The generator depends on
   the pre-registered analysis module for the lower-mode boundary. That is the
   right direction — one definition, pinned by amendment 3 — but it couples the
   manuscript build to a script in `scripts/` that was written as a standalone
   instrument. Recorded, not acted on.
2. **The gate's count is now 39 and will keep moving.** Four of the six new
   checks are presence checks for inputs. A reader comparing "33/33" in an older
   report to "39/39" here should know the denominator changed and why.
3. **`\BarrierCostAlways` (3 runs, 15.0 ms) and `\BarrierCostAlwaysFortyFive`
   (15 runs, −9.2 ms) disagree in sign.** Both are correct for their samples.
   Phase 26 must not quote them as if one refines the other: the three-run
   figure's interval spans zero too, and §VIII already says so.

## 9. Page delta

| | pages |
|---|---|
| before | 25 |
| after | **25** |

No change, as expected: this pass added macros and no prose.
