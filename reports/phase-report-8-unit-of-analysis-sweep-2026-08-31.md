# Unit-of-analysis sweep — every inferential number in the manuscript

**Nothing here is fixed. This is a report and a size, not a change.**

## Why

B20's defect was a **unit-of-analysis error**: `\AblationZeroUpper` put 540
executions in a Wilson denominator where the data are 54 run clusters. It carries
no equivalence word. It surfaced only because a *sentence quoting it* said
"indistinguishable", and it was found during a sweep for that word. **The two
coincided once, by luck.**

By F.0d's own principle a check keyed on equivalence language cannot detect a
unit error — a pattern that matches nothing reads as a clean result. The
abstract's headline detection bound was wrong by an order of magnitude and was
found by accident. Nothing had ever asked the paper's other numbers what their
denominator is.

**Method.** Every candidate is derived from `scripts/paper_tables.py`, the
emitted provenance in `paper/generated/numbers.tex`, and the frozen CSVs. **Prose
was never searched for suspicious phrasing** — doing that is what made B20 a
matter of luck. Prose is consulted only to locate quotations of a quantity
already identified.

---

## 1. Population

| | count |
|---|---|
| macros defined in `numbers.tex` | 137 |
| carrying an explicit denominator | 42 |
| **carrying an inferential claim** (interval, bound, CI, bootstrap, Fisher, quantile, margin) | **28** |

**The 28 are the population that matters, and the 42 are not.** A descriptive
rate over executions *is* a rate over executions and assumes nothing; only an
inferential quantity imports an independence assumption. Narrowing to 28 is the
honest scope, not a convenience.

## 2. Result — 24 of 28 declare their unit, and declare it correctly

**This is the headline, and it largely retires the worry.**

| declared unit | macros |
|---|---|
| **session** (`t(3) = 3.182`, session as the unit) | `ReplicationPreventedLow/High`, `ClassPpHalfWidth`, `ClassPpLow`, `ClassPpHigh` |
| **run cluster** | `AblationZeroUpperRun`, `AblationZeroUpperPerClass`, `BthreeVsAepAmbDiffLow/High`, `BthreeVsAepAmbClusters` |
| **run** (cluster bootstrap over runs) | `BarrierCostLow`, `BarrierCostAlwaysLow`, `ProtocolMinusBarrierLow`, and their `High` siblings by inheritance |
| **execution, declared *and* disclaimed** | `BthreeVsAepDupP`, `BthreeVsAepLostP`, `BthreeVsAepAmbP` — each says *"execution-level Fisher value is descriptive only"* |
| **execution, declared as the rejected alternative** | `AblationZeroUpperExec` |
| **no unit applicable** | `BthreeVsAepAmbDiffConfidence` (a coverage level), `BthreeVsAepAmbMargin` (a margin), `BootstrapResamples`, `AepAlwaysMedian` |

**The vocabulary exists and is used well.** What is missing is that it is
*optional* — which makes this a fail-closed-check problem, not a vocabulary
problem.

**One false positive to design around.** `BarrierCostHigh` reads *"the 97.5th
percentile of **the same** bootstrap"*, inheriting its unit from its sibling. Any
mechanical check must handle sibling inheritance or it will bury real findings in
noise.

## 3. The four that do not declare a unit

| macro | quoted | actual unit | corrected value | quoted at |
|---|---|---|---|---|
| `\UnwantedP` | `1.9e-6` | **run** — 30 runs/arm, one execution per run | **no change** | `main.tex:171` (**abstract**), `06-evaluation.tex:379`, `08-threats.tex:73` |
| `\BaselineDupMaxP` | `5.4e-182` | execution, cluster-unadjusted | **8.7e-25** at the run level | `06-evaluation.tex:93` |
| `\FlakeyBarrierP` | `2.2e-53` | contested — see §4 | 1.6e-27 / 0.1 / 0.25 | `main.tex:178` (**abstract**), `06-evaluation.tex:501` |
| `\FlakeyVsProcessKillP` | `5.8e-14` | contested — see §4 | 0.25 at the collection level | `06-evaluation.tex:503` |

**`\UnwantedP` is correct and undeclared.** Fisher on `[[10,20],[28,2]]`;
`\AepKillRuns` = 30 and `06-evaluation.tex:348` says *"One execution per run"*.
The run **is** the unit. **The declaration lives in prose thirty lines away and
not with the number** — F.0b's structure, applied to units instead of
qualifications. Nothing prevents the next quotation from dropping it. This is
`\ClassPpLow`'s situation exactly: correct today for a reason nothing enforces.

**`\BaselineDupMaxP` changes by 157 orders of magnitude and the claim does not.**
Execution level: 357/450 vs 0/540, p = 5.4e-182. Run level: **42/45 runs with at
least one duplicate against 0/54, p = 8.7e-25.** The sentence says the comparison
"is significant". It is, under either unit. **Value wrong, conclusion safe.**

---

## 4. The flakey probe — the floor claim, established from source

### What the test actually is

**It is Fisher's exact test, not a permutation test over replications**
(`paper_tables.py:691-703`), on the 2×2 `[[0, 90], [90, 0]]`.

**The floor argument survives that substitution, and here is why it does:** for a
2×2 table, Fisher's exact test *is* the permutation test conditional on the
margins. The hypergeometric minimum and the permutation minimum are the same
number. At 3 versus 3 with all margins equal, the minimum two-sided p is
`2/C(6,3) = 0.1`. **Confirmed: perfect separation at the replication level
returns exactly 0.1, which is the floor.** No outcome that design can produce
reaches conventional significance.

### But the premise is weaker than the brief assumed — and this must be said

`one_trial` (`flakey_write_loss.py:345-357`): *"A fresh filesystem per trial. A
trial must not be able to read a key a previous trial's AOF happens to still
contain."* Each trial does `unmount / mkfs.ext4 / mount` and starts a **fresh
Redis process**. The §6 prose says the *replications* rebuild the device and
filesystem; in fact **every trial does.**

**So the replication is a weaker cluster than "3 rebuilds of everything"
suggests.** What trials within a replication share is the loop/dm-flakey device
stack, the host, the kernel and the Redis binary — real, but much less than the
10-executions-in-one-run sharing that made B20 clear-cut. **The floor argument is
arithmetically right and its premise is contestable.** That was asked for
explicitly and is reported rather than smoothed over.

### The defect neither of us listed, and it is unambiguous

**The two arms are matched pairs, and Fisher treats them as independent
samples.** `one_trial`'s own docstring: *"One matched pair of writes, one
write-loss event, one read-back."* The acknowledged and unacknowledged records
are written in the same trial and exposed to the **same** write-loss event. The
emitted provenance even says it — *"over the **same** 90 trials"* — and then
tests them as two independent groups of 90.

**This is wrong regardless of which unit wins**, and it is orthogonal to
clustering.

### Four options, with what each assumes

| | option | value | assumes | verdict |
|---|---|---|---|---|
| **A** | keep it | `2.2e-53` | 180 independent observations | **Wrong twice.** Ignores the pairing and the shared device stack. |
| **B** | paired, trial level — exact binomial on 90 concordant pairs | `1.6e-27` | trials independent; respects the pairing | Defensible. Fresh filesystem and Redis per trial support it. |
| **C** | replication level — Fisher 3v3, or sign test n=3 | `0.1` / `0.25` | replication is the cluster | **Both are the design's floor.** Reports the design, not the data. |
| **D** | **quote no p-value** | — | nothing | Descriptive statement only. |

### Which I would take: **D**, with B as the fallback if a p is required

Not by preference — by elimination. **A is eliminated by the pairing**, which is
a defect in the test's construction and not a judgement call. **C is eliminated
because a floor is not a measurement**: 0.1 arises from perfect separation, the
strongest outcome the design can produce, and is still above 0.05. Reporting it
would state a property of the design and invite a reader to treat it as a
property of the data.

**B survives and I still would not lead with it.** `1.6e-27` is a number whose
only effect on a reader is to make an already-decisive mechanism demonstration
look like an overwhelming statistical result, and it still assumes a trial
independence the shared device stack partially violates.

**What D says instead is stronger and unit-independent:** three independent
replications, each rebuilding the device and filesystem, **a fresh filesystem and
a fresh Redis per trial**, and perfect separation in every one — 30/30
acknowledged survived, 30/30 unacknowledged lost, in all three. That tells a
reader more than any of the three p-values and claims no precision that exists.
F.0b licenses the bare descriptive form exactly where no defensible quantity is
available, and that is the case here.

**Stated plainly, because it is the same shape as B20 and the same answer:**
dropping a p-value that currently reads `2.2e-53` makes the paper look weaker to
a casual reader while making it correct. The number was never available.

**`\FlakeyVsProcessKillP` is worse and the same answer applies.** It pools a
figure from a raw report text file (`0/10` under `docker kill`) against the 90
trials, across two fault classes collected separately. At the collection level it
is 1 against 3, whose Fisher floor is **0.25**. There is no unit at which this
comparison is informative.

---

## 5. Can the check be mechanical? Yes for declaration, no for correctness

That split is the useful part.

**Mechanical, and it should fail closed.** Every macro whose provenance matches
an inferential pattern must contain an explicit unit token; `paper_tables.py`
refuses to emit otherwise. **A new quantity with no declared unit fails until
declared** — F.0d's property, and the same shape as `\AblationZeroUpperPerClass`
refusing to emit when the arm-classes are unequal.

**Not mechanical: whether the declared unit is the *right* one.** That is the
judgement B20 needed, and no check can make it. What the declaration buys is that
the judgement becomes **visible and reviewable** — which is all a check can
honestly offer.

**Would it have caught B20? No — and that is the important answer.**
`\AblationZeroUpper`'s provenance read *"one-sided Wilson 95% upper bound on
0/540, percentage"*. It **declared** its unit; the unit was wrong. A
declaration check would have passed it. **It would have caught all four findings
in §3, and it would have missed the one that started this.** Any claim that this
check prevents B20-class defects would be false.

## 6. Size

- **28 inferential quantities. 24 declare their unit and declare it correctly.**
- **4 do not.** Of those: one is correct and undeclared (`\UnwantedP`); one is
  wrong by 157 orders of magnitude with the conclusion unaffected
  (`\BaselineDupMaxP`); **two are the flakey probe, and both should lose their
  p-values entirely.**
- **Two reach the abstract**: `\UnwantedP` (correct, undeclared) and
  `\FlakeyBarrierP` (recommend withdrawal).
- **Nothing else in the manuscript pools where the paper refuses pooling.** The
  session-clustered, run-clustered and run-bootstrap quantities are all declared
  and all consistent with `paper_tables.py:1894-1897`, `table-ablation.tex:6` and
  `06-evaluation.tex:300`.

**No finding was manufactured to justify the sweep.** Had the flakey probe
declared its unit, this report would have said "nothing beyond B20" and that
would have been the result.
