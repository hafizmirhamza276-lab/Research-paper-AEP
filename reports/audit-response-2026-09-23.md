# Response to the external audit of 2026-09-23

**Verification only. Nothing in the manuscript, the code or the data was changed
by this session.** No live calls.

**Repository state:** `3b55fc5`, the commit the audit examined.

**What this document is.** Finding by finding, whether the audit is right, the
evidence at `file:line` or from a recomputation, and what class of work a fix
would be. It does not choose between fixes and none was started.

**Where I had already recorded something and got it wrong, that is marked.**
Two of the audit's §7 findings are against text I wrote, and one of my own
`claims-to-review` entries checked the wrong half of a question.

| class | meaning |
|---|---|
| **(a)** | wording or scope only |
| **(b)** | re-analysis of data already collected |
| **(c)** | new data collection |

---

## 1. B2 — the crash-point mapping · **VERIFIED**

### 1.1 The mechanism, in code

**Both roadmap points resolve to one enum value for the baselines.**
`experiments/baselines/crash_points.py:96-103` (and `:117-124`, `:142-149`):

```python
"after_barrier_before_dispatch": BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION,
"mid_dispatch":                  BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION,
```

in `_WITHOUT_PRE_DISPATCH_RECORD` (B0, B1, B2), `_WITH_PRE_DISPATCH_RECORD`
(B4, B4b) and `_TEMPORAL_SERVER_SIDE_BARRIER` (B5, B5b).

**That single value is the whole deferred set.**
`crash_points.py:78-80`:

```python
DEFERRED_BASELINE_POINTS = frozenset({BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION})
```

**The deferral decision is keyed on the resolved enum, not on the roadmap
name.** `experiments/harness/injector.py:209-214`:

```python
declared_style = source.get(CRASH_STYLE_VARIABLE)
if declared_style:      style = CrashStyle(declared_style)
elif point in deferred_points:  style = CrashStyle.SIGKILL_DEFERRED
else:                   style = CrashStyle.SIGKILL_IMMEDIATE
```

`point` is the resolved enum. The roadmap name *is* carried forward
(`injector.py:229-235`, into `CrashPlan.roadmap_name`) but only for logging; it
does not reach the style decision. So for every baseline, both roadmap points
become `SIGKILL_DEFERRED` — a watchdog kill 0.4 s after arming, inside the
socket wait.

### 1.2 Does the matrix ever set a crash style? · **No — but the audit's reason is wrong**

The audit says *"`run_matrix.py` and the matrix config never set a crash style
(grep finds no setter)"*. **A setter does exist**, at
`experiments/harness/runner.py:206-207`:

```python
if config.crash_style:
    environment[CRASH_STYLE_VARIABLE] = config.crash_style
```

`crash_style` is a `RunConfig` field defaulting to `None`
(`experiments/harness/config.py:81`), validated when set (`:207-208`), and
never populated by the matrix.

**The empirical check, which is stronger than grep:** all **84** tracked
`run-config.json` files under `experiments/results/matrix/` carry
`crash_style: None`. So the override was available and was never used, and the
deferred path is what ran.

**Conclusion unchanged; the audit's supporting claim is imprecise.**

### 1.3 Is AEP-full affected? · **No. Baselines only**

`experiments/harness/crash_points.py:116-122` maps the two points to
**different** enum values for systems that run `aep_core`'s workflow:

```python
"after_barrier_before_dispatch": CrashPoint.AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT,
"mid_dispatch":                  CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION,
```

and `:135`:

```python
DEFERRED_CRASH_POINTS = frozenset({CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION})
```

So for **AEP-full and B3** `after_barrier_before_dispatch` is
`SIGKILL_IMMEDIATE` and only `mid_dispatch` is deferred. The two points are
genuinely distinct for them.

**The data confirms it.** Crashed regime, `after_barrier_before_dispatch`:

| system | n | undet dup | lost effect | mean applied | dispatch_attempts = 0 |
|---|---|---|---|---|---|
| **AEP_FULL** | 90 | 0.000 | 0.000 | **0.000** | 90/90 |
| **B3_INTENT_NO_BARRIER** | 90 | 0.000 | 0.000 | **0.000** | 90/90 |
| B0_NAIVE_RETRY | 90 | 0.933 | 0.000 | **2.144** | 0/90 |
| B1_LEASE_ONLY | 90 | 0.967 | 0.000 | **2.322** | 0/90 |
| B2_CAS_ONLY | 90 | 0.922 | 0.000 | **2.089** | 0/90 |
| B4_DURABLE_WORKFLOW | 90 | 0.967 | 0.000 | **2.222** | 0/90 |
| B4B_…_AT_MOST_ONCE | 90 | 0.000 | 0.911 | **0.911** | 90/90 |

AEP-full and B3 apply **no** effect at that point, exactly as Table 3 says.
Every other system applies effects.

**The B4b row is the clearest single proof.** **82 of 90** B4b executions
record `dispatch_attempts = 0` *and* `applied_effects > 0` — the worker died
before it could record the attempt, but the bytes had already reached the
provider. The audit's figure of 82/90 is exact.

### 1.4 The docstring contradicts the code · **VERIFIED**

`experiments/baselines/crash_points.py:32-36`:

> `BEFORE_REQUEST_TRANSMISSION` — *"Serves both `after_barrier_before_dispatch`
> (**delivered immediately**: the mutation provably was not sent) and
> `mid_dispatch` (delivered by the deferred watchdog…)"*

The code delivers **both** by the deferred watchdog. The docstring describes a
behaviour the module does not implement.

### 1.5 Is Table 3's "no effect" wrong as printed? · **Yes, for six of seven systems**

`paper/sections/03-model.tex:133`:

> `after_barrier_before_dispatch` & record durable; **no effect**

Table 3 presents this as a property of the **crash point**, unqualified by
system. It is true for AEP-full and B3 (0.000 applied) and false for B0, B1,
B2, B4, B4b and B5b, which apply 0.911–2.322 effects on average. Nothing in
the manuscript states the mapping.

### 1.6 Recomputation, both ways

Crashed regime; dropping `after_barrier_before_dispatch` leaves five crash
points for B0–B2 and five for B4/B4b.

**The "0.77–0.83" statement** (`sections/02-motivating.tex:29`,
`sections/06-evaluation.tex:112`, macros `\BaselineDupLow` = 0.77,
`\BaselineDupHigh` = 0.83), min and max of the per-capability duplicate rates
for B0, B1, B2:

| | min | max | as printed |
|---|---|---|---|
| **with the cell** | 0.7733 | 0.8267 | **0.77–0.83** |
| **without the cell** | 0.7417 | 0.7833 | **0.74–0.78** |

**Table 7 cells that move** (rate with → without):

| system | class | metric | with | without | Δ |
|---|---|---|---|---|---|
| B0 | AUTH | dup | 0.8200 | 0.7833 | −0.0367 |
| B0 | NO-READBACK | dup | 0.7733 | 0.7417 | −0.0317 |
| B0 | POS-ONLY | dup | 0.8000 | 0.7667 | −0.0333 |
| B1 | AUTH | dup | 0.8133 | 0.7750 | −0.0383 |
| B1 | NO-READBACK | dup | 0.8267 | 0.7833 | −0.0433 |
| B1 | POS-ONLY | dup | 0.8067 | 0.7750 | −0.0317 |
| B2 | AUTH | dup | 0.8067 | 0.7833 | −0.0233 |
| B2 | NO-READBACK | dup | 0.7800 | 0.7417 | −0.0383 |
| B2 | POS-ONLY | dup | 0.7933 | 0.7583 | −0.0350 |
| B4 | AUTH | dup | 0.5278 | **0.4467** | −0.0811 |
| B4 | NO-READBACK | dup | 0.5611 | 0.4800 | −0.0811 |
| B4 | POS-ONLY | dup | 0.5889 | 0.5067 | −0.0822 |
| B4b | AUTH | lost | 0.5444 | 0.4600 | −0.0844 |
| B4b | NO-READBACK | lost | 0.5167 | 0.4467 | −0.0700 |
| B4b | POS-ONLY | lost | 0.5056 | **0.4267** | −0.0789 |

**Figure 2 / pooled per system**, duplicate rate:

| system | with | without |
|---|---|---|
| AEP_FULL | 0.0000 | 0.0000 |
| B3 | 0.0000 | 0.0000 |
| B0 | 0.7978 | 0.7639 |
| B1 | 0.8156 | 0.7778 |
| B2 | 0.7933 | 0.7611 |
| B4 | 0.5593 | **0.4778** |

**Every one of the audit's quoted recomputations matches mine exactly** (B0
AUTH 0.8200 → 0.7833; B4 → ~0.45 with AUTH 0.4467; B4b → ~0.43 with POS-ONLY
0.4267).

**The direction of every comparison survives**: AEP-full and B3 stay at zero on
both metrics either way, so the headline separation is unaffected. What changes
is the magnitude of every baseline rate and the "0.77–0.83" range.

### 1.7 What fixing it requires

* **Disclose the mapping** in §6.1 and correct the docstring — **(a)**.
* **Correct Table 3** so "no effect" is scoped to the systems for which it
  holds — **(a)**.
* **Drop the cell from the pooled baseline rates** and regenerate every
  affected macro, table and figure — **(b)**. `\BaselineDupLow` /
  `\BaselineDupHigh` become 0.74 / 0.78, and §2's, §6.2's and §6.3.1's prose
  moves with them.
* **Re-collect the baseline cells with `SIGKILL_IMMEDIATE`** — **(c)**. The
  override already exists (`AEP_HARNESS_CRASH_STYLE`), so no code change is
  needed. Six baseline systems × 3 capability classes × 30 runs at the
  matrix's observed rate is **roughly 5–7 hours** on the one host, plus
  re-analysis. This is the only option that makes the cell mean what Table 3
  says.

---

## 2. B1 — detection vs the barrier · **VERIFIED**

### 2.1 What the config asserts

`formal/configs/b3-no-barrier-restart.cfg:1-5`:

```
\* EXPECT: fail NoLostEffect
\* B3 with the AOF rewind enabled: the same ablation, now in a run where
\* Redis dies without flushing. This is the pairing that gives the barrier
\* its purpose, and the difference from b3-no-barrier is the whole point of
\* the ablation.
```

with `BarrierEnabled = FALSE` and `NoLostEffect` among the `INVARIANTS`.

The paired config `b3-no-barrier.cfg` is `EXPECT: pass`, and says why:
*"the barrier does not defend the state machine — it defends the record's
existence, and **nothing here destroys records**."*

**So the project's own model says: ablate the barrier, destroy the record, and
`NoLostEffect` fails.** *No lost effect* is half the abstract's definition of
detection.

### 2.2 Table 6 prints it · **VERIFIED**

`paper/sections/04-protocol.tex:276`:

```
The barrier, plus a restart & no lost effect     & 8 \\  % b3-no-barrier-restart.cfg
```

The row is printed and is **not discussed in the surrounding text**, which
takes up two other rows of the same table.

### 2.3 Was Redis ever restarted after a record loss? · **No, in any collected cell**

`reports/raw/ws4-writeloss-s1-2026-09-07/README.md:35-36`:

> **No void condition fired.** In particular `coordinator_restarted_unexpectedly`
> is `False` in all 60 runs

and `:56-58`, that the marker sampler and the flag *"independently show no
restart during the 60 runs"*. A restart **after** collection ended is recorded
at `:46-52` and is shown not to touch the data.

So in the one regime that destroys unfsynced writes, the in-memory record
survived and served recovery. The zeros there cannot test record loss.
`formal/configs/write-loss-no-restart.cfg` says the same thing in the model.

### 2.4 Precisely which faults the claim holds for

**True for:** worker `SIGKILL` at any of the six crash points with Redis alive
(the crashed regime); a Redis process kill where the AOF and page cache survive
(`redis-kill-preack`); host-level write loss **without** a restart
(`write-loss-preack`). In all of these the record exists when recovery reads
it, so the barrier cannot matter — and the ablation's null is a consequence of
that, not an independent finding.

**Not established for, and contradicted in the model:** any fault that destroys
the record before recovery reads it — host-level page-cache loss followed by a
Redis restart. `b3-no-barrier-restart.cfg` says `NoLostEffect` fails there.

### 2.5 Where it is stated without that scope

| location | text | scoped? |
|---|---|---|
| `paper/main.tex:292` (abstract) | *"Because detection does not depend on the barrier, its cost is a deployment choice"* | **no** |
| `sections/06-evaluation.tex:393` | *"Durability is neither necessary nor sufficient for detection."* | **no** — the strongest form |
| `sections/08-threats.tex:151` | *"the ablation says which half delivers which, including that the expensive half is optional"* | **no** |
| `generated/table-deployment-choice.tex:13` | *"All three rows run the same pre-dispatch intent ledger and therefore make the same detection claim"* | **no**, and it is a **generated** caption |
| `sections/01-introduction.tex:121` (C4) | *"…in the crashed-regime detection metrics"* | **yes** |

**The audit is right that C4 is correctly scoped and the other four are not.**

### 2.6 What fixing it requires

* **Scope the four unscoped statements** to faults that do not destroy the
  record, and **discuss the Table 6 restart row** — **(a)**. The caption is
  generated, so that one is a `scripts/paper_tables.py` edit plus a
  regeneration, still **(a)** in substance.
* **State that detection under record-destroying faults is untested
  empirically and fails in the model** — **(a)**.
* **Run B3 and AEP-full under `drop_writes` with a Redis restart after
  dispatch** — **(c)**. This needs root, a loop device and a `dm-flakey`
  target, i.e. the existing write-loss provisioning plus a restart step.
  Scale: one cell, two arms, 30 runs each at 10 executions. The existing
  write-loss session was 60 runs in about an hour, so **roughly 1–2 hours**
  plus provisioning — but it is the cell that would decide the paper's central
  claim, and the model predicts B3 fails it.

---

## 3. Consistency items 4, 5, 6, 7, 8, 10

### Item 4 — latency cells mixing 3-run and 15-run sources · **VERIFIED**

Provenance, `paper/generated/numbers.tex`:

* `\AepStepMedian` = 4 004.9 — *"step_latency_ms_median over crash-free runs
  only (**overhead_runs_crash_free=3**)"*
* `\BthreeStepMedian` = 2 038.2 — same comment, **3 runs**
* `\BarrierCostFifteen` = 1 939.7, interval [1 855.8, 1 962.4] — *"cluster
  bootstrap over runs, 10000 resamples, seed 20260806 … **15 and 15 runs**"*

4 004.9 − 2 038.2 = **1 966.7**, and **1 966.7 > 1 962.4**, so the difference
Table 9 implies lies **outside** the 15-run interval §6.4 quotes.
`generated/table-deployment-choice.tex` prints **1 966.7** directly in the
"AEP-full, `everysec`" row.

**Class (a)** to label Table 9's provenance; **(b)** to re-derive Table 9 from
the 15-run collection so the two agree.

### Item 5 — the −9.2 vs 15.0 sign · **VERIFIED**

`paper/sections/06-evaluation.tex:756-763` says the supplementary gives the
three points *"with the table they are read from"*, then quotes
`\BarrierCostAlwaysFortyFive` = **−9.2** ms.

`paper/generated/table-deployment-choice.tex` row *"AEP-full, `always`"* prints
barrier = **15.0** ms.

**Opposite sign, and the quoted figure is not in the table the sentence points
at.** The two come from different collections: the table's row from
`experiments/results/fsync-always` (6 runs), the prose from
`fsync-always-2026-09-14` (45 runs).

**Class (b)** — re-derive the table row from the same collection as the prose,
or relabel both.

### Item 6 — mixed sources inside one parenthesis · **VERIFIED**

`paper/supplementary.tex:574-576`: *"(B3 is `\BthreeStepMedian` ms under
`everysec` and `\BthreeAlwaysFortyFiveMedian` ms under `always`)"* — that is
**2 038.2** and **2 089.0**.

* 2 038.2 is the **3-run** `latency-and-throughput.csv` figure.
* 2 089.0 is from **`fsync-always-2026-09-14`**.
* The **15-run `everysec`** B3 median, computed here from
  `ws5-2026-09-10/t1-p0-everysec/analysis/per-execution.csv` (150 executions,
  15 runs), is **2 075.2 ms** — the audit's figure exactly.

So a sentence whose whole point is that the two policies are comparable
compares a 3-run number with a 45-run number, when a 15-run number for the same
policy exists.

**Class (b)**.

### Item 7 — Bonferroni coverage · **VERIFIED, with a correction to how it is described**

`paper/sections/06-evaluation.tex:362-369` derives it carefully **for two
bounds**:

> *"Each system's rate is individually bounded this way. When **the two system
> bounds** are stated simultaneously, Bonferroni gives joint coverage of at
> least 90%, not 95%."*

That arithmetic is right: 1 − 2(0.05) = 0.90.

**The error is in what the same passage then claims the bound supports**, two
sentences later:

> *"This finite-sample bound is the support for 'no observed difference' in
> **the two zero-event metrics**"*

and in the restatements, `sections/07-related.tex:220` and the supplementary:

> *"**both zero-event rates** fall within [0, 4.77%] at joint coverage of at
> least 90%"*

Two metrics (undetected duplicate, lost effect) × two systems (AEP-full, B3) =
**four** simultaneous bounds → Bonferroni gives **≥ 80%**, not ≥ 90%.

**So the audit's conclusion is right and its framing is slightly off:** §6.3.1
does not derive ≥90% for four bounds; it derives it for two and then applies it
to a four-bound claim.

**Class (a)** if the claim is narrowed to one metric at a time; **(a)** also if
the coverage figure is corrected to 80% — the arithmetic needs no new data.

### Item 8 — the sign-test "theorem" · **PARTLY VERIFIED**

`paper/sections/08-threats.tex:347-350`:

> *"with $n$ paired sessions the smallest attainable two-sided sign-test
> $p$-value is $2/2^{n}$, which at $n=4$ is 0.125. **No effect size, however
> large, could have produced a rejection at $\alpha=0.05$ from these
> designs.**"*

**True of the sign test.** 2/2⁴ = 0.125 > 0.05.

**False as a statement about the design**, because the paper's own t-analysis on
a four-session design *did* reject. Recomputed here:

| four-session comparison | mean | t(3) | two-sided p | 95% CI | rejects at α = 0.05? |
|---|---|---|---|---|---|
| prevention (8, 16, 24, 21) | 17.25 | 4.933 | **0.0160** | [6.12, 28.38] | **yes** |
| kill-latency (70, −4, 282, 74) | 105.50 | 1.715 | 0.1848 | [−90.24, 301.24] | no |

The prevention interval is what `\ReplicationPreventedMean` 17.2
[`\ReplicationPreventedLow` 6.1, `\ReplicationPreventedHigh` 28.4] prints, and
`sections/08-threats.tex:148` calls it *"the only session-clustered interval in
this paper that excludes zero."*

So the same n = 4 design produced a rejection under the test the paper reports,
and the sentence *"these designs could not have found one, whatever was
there"* is true only if the sign test is the test. The paper reports
**t-intervals** for both of the comparisons the paragraph is about.

**Class (a)** — scope the sentence to the sign test, or justify why the sign
test governs those two comparisons and the t-interval governs the third.

### Item 10 — prevention under `always` · **VERIFIED**

`generated/table-deployment-choice.tex` row *"AEP-full, `always`"* prints
**prevents: yes**.

Both `always` collections contain **no crashed executions at all**:

| collection | regimes | crashed | runs |
|---|---|---|---|
| `experiments/results/fsync-always` | `p0` × 60 | `0` × 60 | 6 |
| `experiments/results/fsync-always-2026-09-14` | `p0` × 450 | `0` × 450 | 45 |

Prevention is a claim about withholding dispatch when the store dies. **No
`always` execution was ever crashed or had Redis killed.** The cell is
crash-free throughout.

**Class (a)** if the column is changed to "not measured" or the row is
annotated; **(c)** if the claim is to be kept — a `redis-kill-preack` cell
under `appendfsync always`, two arms, ~30 runs each, **roughly 1–2 hours**.

---

## 4. The audit's §7 table of audit-pack claims

**Two of these are against text I wrote. Both are correct.**

| # | pack claim | audit says | my finding |
|---|---|---|---|
| 1 | header *"builds green, gates green"* | untrue | **VERIFIED** |
| 2 | §2.2 macro-source counts | inaccurate | **VERIFIED** |
| 3 | §2.1 `\WriteLossAepApplied` provenance path | path only under `reports/raw/` | **VERIFIED** |
| 4 | §7.4 `\archiveavail` renders *"not yet deposited"* | inaccurate | **VERIFIED** |
| 5 | target venue *"TSE, double-anonymous"* | likely wrong | **CANNOT VERIFY** |
| 6 | the pooling violation caught *"by an external reviewer"* | unconfirmed | **VERIFIED as unsupported** |
| 7 | Roman-numeral section references | mismatch | **VERIFIED** |
| 8 | C3 *"in any cell measured"* | true | agreed |
| 9 | no manuscript text mentions phase 40 | true | agreed |

**1.** `python scripts/check_prereg_order.py` → **exit code 1**, *"cells: 35
ok: 27 exempt: 4 failing: 4"*. The four are `reports/raw/phase40-deployment-2026-09-18`,
`phase40-stage-10-interactive-2026-09-21`, `phase40-stage-30-2026-09-21`,
`phase40-stage-100-2026-09-22`, each *"tracked collection with no entry in
EXPECTED"*. The audit's reading is right: the collections **were**
pre-registered in `prompts/`, so this is a gate-table omission, not a missing
pre-registration. **The pack's claim is still untrue, and I wrote it without
running that gate.** Class **(a)** — add four rows to `EXPECTED`.

**2.** Provenance-comment lines in `paper/generated/numbers.tex` naming each
source: `per-cell-metrics.csv` **56**, `redis-kill-ablation.csv` **41**,
`comparisons-vs-aep-full.csv` **20**, `e1-kill-latency-by-run.csv` **19**,
`per-execution.csv` **11**, `latency-and-throughput.csv` **9**,
`coverage.json` **7**. The pack's table said `per-cell-metrics.csv` supplied
**3** and `redis-kill-ablation.csv` **25**. My counts differ slightly from the
audit's (52 / 19 / 19) because of how a line with two paths is attributed, but
the finding is identical: **the pack's table was built from a crude path regex
and undercounts badly.** Class **(a)**.

**3.** The provenance comment reads
`ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv`. That directory
exists **only** at `reports/raw/ws4-writeloss-s1-2026-09-07`;
`experiments/results/ws4-writeloss-s1-2026-09-07` does not exist. An auditor
following the path as written lands nowhere. **This is a defect in the
generated provenance itself, not only in my pack, which copied it.** Class
**(a)** — prefix the path in `scripts/paper_tables.py` and regenerate.

**4.** `pdftotext paper/main.pdf` contains *"begins resolving when the record is
published."* and **no** "not yet deposited" sentence. Class **(a)**.

**5. I cannot verify this and will not concede it.** Establishing TSE's current
review model requires reading IEEE's author pages, and this session makes no
network calls. What I can say: the repository contains **no** evidence for
"double-anonymous" beyond the project's own assertion, and the entire
`\ifanonymous` apparatus, `prove_anonymous_gate.sh`, and the stripped
disclosure rest on it. **If the audit is right, a large amount of machinery is
built for a review model that does not apply.** This needs an authoritative
check against the TSE submission site before submission. Class **(a)** if the
model is confirmed and only labels change; the anonymous build itself can
simply go unused.

**6.** `reports/paper-review-2026-08-11.md:7` describes *"the reviewer's
container has Python 3.12 + `uv 0.11.7`, no Docker, and outbound network
limited to package registries and web search"*, and `:1-9` name no person and
no affiliation. That is consistent with an agent sandbox and inconsistent with
nothing. **I cannot establish who or what wrote it, which is exactly the
problem: the pack called it "an external reviewer" and thereby claimed an
independence it never established.** Class **(a)** — describe it as what it
verifiably is, a review conducted in a separate session against the tracked
CSVs.

**7.** The compsoc build renders Arabic numerals: `pdftotext` gives
*"9 T HREATS TO VALIDITY"* and *"(Section 6.4)"*. The pack used §VI-B, §VIII
throughout. Class **(a)**.

---

## 5. The AI disclosure findings

### 5.1 The anonymous build does not name the AI systems · **VERIFIED**

`paper/main.tex:167-173`, the `\ifanonymous` branch:

> *"The author used generative AI coding and drafting assistants throughout
> this work (implementation, harness, analysis pipeline, documentation and
> manuscript prose) under the author's direction and review."*

`paper/main.tex:203-220`, the `\else` branch:

> *"The author used **Anthropic's Claude (Claude Code, Opus and Sonnet models)
> and OpenAI's Codex** …"*

The anonymous build is the one reviewers see, and it names no system. Naming a
vendor does not identify an author. **Class (a)** — one sentence.

### 5.2 The commit-trailer claim · **PARTLY VERIFIED — the audit missed half the claim**

The disclosure (`main.tex:211-215`) says identifiers are recorded

> *"in the artifact repository's commit trailers **and in the per-assistant
> configuration files committed beside them**, which are the authoritative
> record."*

**On trailers, the audit is exactly right.** `git log` over 488 commits:
**396** carry `Co-Authored-By: Claude Opus 5 (1M context)` and **no other
identifier appears in any trailer** — no Sonnet, no Codex.

**On the second half, the audit is wrong.** `.claude/` **is tracked** (12
files), and four of them name model identifiers: `sonnet-4-6` and `opus-4-7`
appear in `.claude/agents/aep-orchestrator.md`, `implementer.md`,
`opus-fixer.md` and `tech-designer.md`. So **Sonnet is recorded**, in exactly
the place the disclosure points to.

**What remains true:** there is **no model identifier for Codex anywhere in the
tracked tree**. `CODEX_PROMPTS.md` and `WEEKEND_CODEX_PROMPTS.md` are prompt
files and name no model. (`gpt-5.6-luna` appears in tracked files, but that is
the phase-40 Azure *planner deployment*, not the drafting assistant.)

**So the record is incomplete for Codex only, not for Sonnet.** Class **(a)** —
either record the Codex model, or narrow the claim to the assistants whose
identifiers are recorded.

---

## 6. S1 — the Temporal comparison · **VERIFIED, and the mechanism is worse than the audit states**

The claim, `paper/sections/06-evaluation.tex:159-162`:

> *"But **at that same crash point** B4 duplicates at `\BfourAtBarrier` … and
> B4b loses at `\BfourbAtBarrier` over `\BfourbAtBarrierExec`, **roughly six
> times the engine's rates**."*

The numbers: `\BfourbAtBarrier` = **0.9167** (55/60), provenance
*"crash_point=after_barrier_before_dispatch"*; the engine's `\BfivebLost` =
**0.1424** (84/590). 0.9167 / 0.1424 = 6.4.

**"That same crash point" is precisely where the two systems are killed
differently.**

* **B5/B5b** arm `ACTIVITY_ENTERED_BEFORE_CALL`
  (`experiments/baselines/b5_temporal/worker.py:46,62`, mapped from
  `after_barrier_before_dispatch`) and die **immediately** via `_maybe_die`
  (`worker.py:141-159`, `os.kill(os.getpid(), SIGKILL)` at the point). All 120
  collected runs record `armed_point = ACTIVITY_ENTERED_BEFORE_CALL`.
* **B4/B4b** at the same roadmap name get the **deferred watchdog** kill (§1),
  landing inside the socket wait — 82/90 with zero recorded dispatch attempts
  and an applied effect.

So B5 dies **before** transmission and B4b dies **during** it, at the same
named crash point, and the ratio between them is reported as a modelling
difference.

**The exposure difference the audit names is also real.** Every B5 run has
`executions: 10` and the worker `SIGKILL`s itself at the first armed point, so
one death per ten executions; every B4b execution in the crashed regime is
killed.

**One correction to my own §1.3 above:** B5/B5b appear in
`ROADMAP_TO_BASELINE` with the collapsing mapping, but the Temporal worker does
not use it — it reads the roadmap name directly and has its own immediate and
deferred paths. **B5/B5b are therefore not affected by B2**, which is what
makes the comparison asymmetric rather than uniformly wrong.

**Class:** **(a)** to disclose that the two cells differ in kill style and
exposure, and to withdraw or qualify "roughly six times"; **(c)** to make it
like-for-like — re-collect either B5 at a deferred kill or B4/B4b at an
immediate one, one cell per arm, **roughly 2–3 hours** including the Temporal
server.

The audit also notes the Temporal cell took three attempts and that the paper
says nothing about it. Confirmed: the collected directory is
`ws6-b5-s1-2026-09-08-attempt3`, and its `README.md` records the earlier two.
**Class (a)** — one sentence.

---

## 7. One of my own `claims-to-review` entries checked the wrong half

`reports/claims-to-review.md` entry 3 is marked **CHECKED** on the strength of
`voided/` being a real directory in the archive, with 24 manifest entries. That
is true and I verified it.

**It is not what §VIII claims.** `sections/08-threats.tex` says the voided run
*"is in the **published** archive under `voided/`"*. The archive is **not
published** — `\archivedoistate` is `RESERVED` and the DOI does not resolve.
So the sentence is false at submission for the reason the audit gives in B3,
and my entry closed it on the directory's existence without testing the word
*published*.

**Class (a)**, and it belongs with the deposit: the sentence becomes true the
moment the record is published, and false until then.

---

## 8. Summary

**Verified:** B2 in full, including the docstring contradiction and Table 3
being wrong as printed for six of seven systems. B1 in full. Consistency items
4, 5, 6, 7 (with a correction to its framing), 10. Item 8 partly. S1, with a
sharper mechanism than the audit gives. All four checkable audit-pack findings
against my own text. The anonymous-build disclosure gap.

**Refuted or corrected:**

* the audit's *"grep finds no setter"* for the crash style — a setter exists at
  `runner.py:206-207`; the conclusion survives on the data instead;
* the audit's *"no trailer for any Sonnet model or for Codex … the claimed
  authoritative record is incomplete"* — Sonnet **is** recorded, in the tracked
  `.claude/agents/` files the same sentence points to; only Codex is missing;
* item 7's framing — §6.3.1 derives ≥90% correctly for two bounds; the error is
  applying it to a four-bound claim.

**Could not verify:** TSE's review model and page limit, which need the TSE
submission site and are the load-bearing premise of B3.

**Nothing in this session changed the manuscript, the code, the data or the
gates.**
