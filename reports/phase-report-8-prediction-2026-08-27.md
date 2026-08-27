# Phase 8 · pre-registration — the AUTH cell, before it exists

**Committed and pushed before any 8.4 run. Same discipline as P9-A and 9C.**

This document fixes the prediction, the sample size, the stopping rule and the
adjudication rules for Phase 8.4's collection, at a commit where no
`AUTHORITATIVE_READBACK` × `redis-kill-preack` data exists anywhere. §2 proves
that. Everything after this document is measurement.

Two properties make the artifact worth anything, and both are checkable by a
reader rather than taken on trust:

1. Its commit hash precedes the first data commit (§1, §9).
2. It is on the remote before collection starts (§9). A pre-registration whose
   only timestamp is on the machine that later produced the data proves nothing.

---

## 1. Provenance

```
$ git rev-parse HEAD
e67efd1f74d14ed7c33fc09b661a24f1c2657d4c

$ git status --porcelain
?? CLAUDE.md

$ git rev-parse --abbrev-ref HEAD
main

$ git rev-list --left-right --count origin/main...HEAD
0	0
```

`CLAUDE.md` is untracked, unrelated and pre-existing; P9-A §1 recorded it in the
same state. It is not part of this phase and is never staged. **It also has a
consequence for one of the gates below, which §6.3 registers rather than
discovers later.**

---

## 2. Proof that no AUTH `redis-kill-preack` data exists at this commit

P9-A §2's four commands, re-run verbatim at `e67efd1`.

```
$ awk -F, 'NR>1{print $1" "$3}' experiments/results/matrix/analysis/redis-kill-ablation.csv | sort -u
redis-kill-preack NO_READBACK

$ grep -c AUTHORITATIVE_READBACK experiments/results/matrix/analysis/redis-kill-ablation.csv
0

$ ls -d experiments/results/b2-* 2>/dev/null
experiments/results/b2-2026-08-21
experiments/results/b2-s1-2026-08-21
experiments/results/b2-s2-2026-08-21
experiments/results/b2-s3-2026-08-21

$ find experiments/results -type d -name '*payments*' | grep -i 'redis\|kill'
  (no output, exit 1)
```

**Commands 1, 2 and 4 reproduce exactly. Command 3 does not, and the reason is
Phase 8.0.** P9-A recorded "(no such directory)" because the four Phase 9
replication roots were untracked and unfrozen at that time; 8.0 froze and
tracked them (`b2ab570`). The command's original purpose — showing that the
results root this phase will create does not exist — is now served by the fact
that **none of those four roots is `b2-paired-*`** and none contains an AUTH row.

A **fifth command is added** which is a stronger statement than the one it
displaces, because it covers every tracked ablation table rather than one:

```
$ for f in $(git ls-files '*redis-kill-ablation.csv'); do \
    awk -F, -v F="$f" 'NR>1{print F": "$1" "$2" "$3" runs="$4}' "$f"; done
experiments/results/b2-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack AEP_FULL NO_READBACK runs=30
experiments/results/b2-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack B3_INTENT_NO_BARRIER NO_READBACK runs=30
experiments/results/b2-s1-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack AEP_FULL NO_READBACK runs=30
experiments/results/b2-s1-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack B3_INTENT_NO_BARRIER NO_READBACK runs=30
experiments/results/b2-s2-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack AEP_FULL NO_READBACK runs=30
experiments/results/b2-s2-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack B3_INTENT_NO_BARRIER NO_READBACK runs=30
experiments/results/b2-s3-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack AEP_FULL NO_READBACK runs=30
experiments/results/b2-s3-2026-08-21/analysis/redis-kill-ablation.csv: redis-kill-preack B3_INTENT_NO_BARRIER NO_READBACK runs=30
experiments/results/matrix/analysis/redis-kill-ablation.csv: redis-kill-preack AEP_FULL NO_READBACK runs=30
experiments/results/matrix/analysis/redis-kill-ablation.csv: redis-kill-preack B3_INTENT_NO_BARRIER NO_READBACK runs=30
reports/raw/e1-redis-kill-ablation.csv: redis-kill-preack AEP_FULL NO_READBACK runs=30
reports/raw/e1-redis-kill-ablation.csv: redis-kill-preack B3_INTENT_NO_BARRIER NO_READBACK runs=30
```

**Six tracked ablation tables, twelve rows, every one `NO_READBACK`.** Zero rows
of `AUTHORITATIVE_READBACK` × `redis-kill-preack` exist anywhere in the tree.

---

## 3. The prediction

Mechanism statement inherited verbatim from P9-A §4 (`85e6c54`, committed before
any data existed): whether an effect reached the provider is a fact about what
was put on the wire; a read-back is exercised afterwards, by recovery, and can
change what the system is able to **say**, not what was **done**.

### 3.1 PRIMARY — the class effect on the applied column, covariate-adjusted

Logistic regression of applied ∈ {0,1} on capability class, with
`log(issue_to_return_ns)` as covariate and session as a fixed effect.

| | Predicted | CONFIRMS | CONTRADICTS |
|---|---|---|---|
| class coefficient | **0** | 95% CI contains 0 | CI excludes 0 |

**A contradiction is the finding.** If class moves the applied column, that
contradicts the mechanism as the paper describes it. The report says so, names
the affected claims in `06-evaluation.tex` and `08-threats.tex`, and does **not**
re-run to see whether it goes away. Phase 9C set that precedent explicitly.

### 3.2 SECONDARY — the unadjusted paired difference

`d_i = applied_AUTH(i) − applied_NO_READBACK(i)` for AEP-full, session as the
unit, mean with a two-sided 95% t-interval on k−1 df. A robustness check on 3.1.
**The naive Wilson interval on pooled runs is forbidden** — 9C §3 shows it four
times too narrow.

### 3.3 TERTIARY — the ext4 replication of the headline cell

Registered in §5, because it is new to this document.

### 3.4 INTEGRITY CHECK (not an estimand) — the fail-closed invariant

For every **AEP-full** execution with an applied effect, the run must show
traversal of `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT` for that execution.
Predicted: **zero exceptions**, near-certainly, by construction.

**Any exception HALTS the phase** — it would mean a dispatch without
authorization, which `DispatchAuthorizationError` is supposed to make impossible.
Reported and minimised, not re-run away. **This is confirmatory of code-enforced
behaviour along a single code path**, not a discovered property, and the 8.6
report must say so rather than leave it to be inferred. One-directional:
`ack ⇒ applied` is **not** claimed.

**§4 is a correction to how this check is scoped, and it is why B3 appears in §6
as a control rather than here as a contrast.**

### 3.5 Checks carried forward

- **Unfalsifiability check (P9-A §4.4), verbatim.** If AUTH's declared ambiguity
  does not drop below 30/30, the read-back is not being exercised and the cell
  measures something other than what it claims; the applied-effect comparison is
  then uninterpretable regardless of what it shows, and the output is a **defect
  report about the cell**, not a finding about the mechanism.
- **Balance check.** Runs are ordered cell-by-cell, not interleaved
  (`run_matrix.py:451-482`), so a session's two arms are ~18 min apart. Compare
  arms' `issue_to_return_ns` distributions per session; pre-declared threshold
  **|median difference| ≤ 100 ms**, half the measured 194 ms run-level effect.
  Failing sessions are reported individually; **no session is dropped**.
- **HALT (P9-A §4.3):** any `undetected_duplicates > 0`; any `lost_effects > 0`;
  `executions ≠ runs × 1` in any cell; a `(system, response_class)` pair twice.

---

## 4. B3 acknowledges. The invariant check is AEP-full-only.

Found while preparing this document, and it changes the shape of §3.4 and §6.

**B3 is not a system without acknowledgements.** `experiments/baselines/b3_no_barrier.py`
is explicit (lines 6–11, 22–26): B3 *is* `WriteAheadRunner` with
`NoBarrierDurabilityBarrier` substituted, and *"the acknowledgement is still
issued"*. `confirm_durable` returns `True` unconditionally
(`b3_no_barrier.py:79-88`), `authorize_dispatch` consumes the resulting
`DurabilityAck`, and control reaches
`await self._checkpoint("AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT")`
(`aep_core/core/intent_workflow.py:492-494`) on the same code path. The Phase 8.2
observer fires. **B3 will show `durability_ack_observed = 1`.**

Consequences, registered now:

1. **`applied ⇒ ack` holds in both arms by construction.** Checking it on B3
   confirms nothing. §3.4 is therefore scoped to AEP-full explicitly.
2. **A B3 arm predicted to violate the invariant would have been false by
   construction** — it would have read either as a finding when it was a
   specification error, or as evidence that B3's acknowledgements mean something.
   The committed plan `reports/plan-phase-8-b2.md` §3.3 is already correctly
   AEP-full-only; the erroneous B3 row existed in an **uncommitted** rev. 2
   draft and never reached the record. It is named here anyway, because the
   underlying fact — that B3 acknowledges — was written down nowhere.
3. **The column's meaning is per-arm.** `durability_ack_observed = 1` means "a
   `DurabilityAck` was issued and spent". For AEP-full it is backed by a
   `WAITAOF` that returned at least one local fsync. For B3 it is backed by
   nothing: *"issued on the strength of a barrier that did not wait"*.
4. **B3 becomes the instrumentation positive control** (§6.3) — a better use of
   it than the contrast, and the only run-level control this regime affords.

### 4.1 Manuscript sweep for B3-as-no-acknowledgement prose — result

Swept every occurrence of `B3`, `barrier`, `acknowledg`, and `WAITAOF` across
`paper/main.tex` and `paper/sections/*.tex`.

**Result: no false statement found.** The prose is consistently precise about
*waiting*, which is what B3 ablates, rather than about *acknowledging*, which it
does not:

| locus | text | verdict |
|---|---|---|
| `06-evaluation.tex:331` | "B3 is not, because B3's ablation is precisely that round trip" | **exactly right**, and pre-empts the misreading |
| `06-evaluation.tex:344` | "the only difference is whether the system **waits for** the durability acknowledgement before dispatching" | **exactly right** — "waits for", not "obtains" |
| `06-evaluation.tex:410` | "as a system that **never waits for** the barrier must" | right |
| `06-evaluation.tex:239-241` | barrier defined as "the `WAITAOF` round trip…"; then "AEP-full with the barrier removed and nothing else removed" | **accurate**, under the definition given in the same sentence |
| `02-motivating.tex:88,107` | "AEP with the durability barrier removed and nothing else"; "B3 AEP minus the barrier" | accurate at the same definitional level |
| `06-evaluation.tex:313`, `:356`, `:616` | "no barrier"; "B3 (no barrier)"; "the barrier removed entirely" | terse but not false — "barrier" is bound to the round trip throughout |

**The specific locus queried, `06-evaluation.tex:240`, is accurate.** It defines
the barrier as the round trip *in the same sentence*, so "the barrier removed"
reads as "the round trip removed", and the clause "and nothing else removed"
actively protects the authorisation machinery. The precondition is indeed still
checked in B3 — on an acknowledgement backed by nothing — and `:331` states that
mechanism 91 lines later.

**One available two-step inference, recorded because I made it myself.**
`04-protocol.tex:78-79` says the barrier "issues a `DurabilityAck` only when
`WAITAOF` returned at least one local fsync"; `02-motivating.tex:107` says "B3
AEP minus the barrier". Chaining them yields "B3 has no `DurabilityAck`", which
is false — B3 substitutes a *different* barrier that issues the ack unbacked.
Each sentence is true of its own subject; the conjunction is not. **This is the
inference that produced the erroneous draft row.** No manuscript change is
required, since nothing asserted is false, and `04-protocol.tex:78` is correct
about AEP-full's barrier, which is its subject.

**Registered condition.** If `durability_ack_observed` ever reaches the
manuscript, **the per-arm semantics must travel with it in the same table or
caption**. A reader meeting "B3 (no barrier)" beside "B3: 28/30 acknowledgements"
will read a contradiction unless told that the acknowledgement is backed by a
returned `WAITAOF` in one arm and by nothing in the other. This binds Phase 8.6
and any later phase; it is not optional and not a stylistic note.

---

## 5. Sample size, and the filesystem asymmetry

### 5.1 k = 4, derived from the primary estimand

The design blocks on session and adjusts for kill latency, which brings the
residual variance back to roughly binomial — 9C measured over-dispersion **5.37**
for unblocked pooling, **so the binomial calculation below is valid only because
of the blocking.** Baseline p₀ = 53/150 = **0.3533** (AEP-full, `NO_READBACK`,
five sessions). Per-arm n = 30k; 80% power, α = 0.05 two-sided:

| k | n/arm | **MDE (pp)** | secondary half-width (pp) | run time |
|---|---|---|---|---|
| 2 | 60 | 24.4 | 110.8 | 2.4 h |
| 3 | 90 | 20.0 | 30.6 | 3.6 h |
| **4** | **120** | **17.3** | **19.6** | **4.8 h** |
| 5 | 150 | 15.5 | 15.3 | 6.0 h |
| 6 | 180 | 14.1 | 12.9 | 7.1 h |

**Stated minimum detectable class effect: 17.3 percentage points**, which is
**30% of the barrier's own measured effect** (B3 140/150 vs AEP-full 53/150 =
58.0 pp). The paper claims capability class moves the *ambiguity* column by
~100 pp and the *applied* column not at all; a movement of the applied column by
a third of the barrier's own effect would materially qualify that, a smaller one
would not. k = 4 is also where the primary's MDE and the secondary's half-width
become commensurable, so the robustness check can corroborate rather than
decorate; at k = 3 they diverge (20.0 vs 30.6).

**Sensitivity to AUTH's applied fraction** (sweeps the *treatment arm*, baseline
pinned at 0.3533):

| AUTH applied fraction | 0.05 | 0.10 | 0.20 | 0.358 | 0.50 | 0.65 |
|---|---|---|---|---|---|---|
| **MDE (pp)** | 13.4 | 14.4 | 15.9 | **17.3** | 17.7 | 17.3 |

### 5.2 The filesystem asymmetry — declared, and half of it discharged

**The asymmetry.** k, the 17.3 pp MDE, p₀ = 0.3533 and sd(d) ≈ 3.70 were all
derived from data dominated by drvfs sessions. **8.4 collects on ext4** — the
stratum that showed +88 ms rather than +201 ms in the kill-latency test, and
whose recovery broke the session-level monotonicity (Spearman 1.000 → 0.700).
The estimand is safe, because the primary contrast is within-session and
within-filesystem. **The power calculation is not, because it was borrowed
across strata.** This section discharges what can be discharged and declares the
rest.

**5.2a The primary transfers, and this is shown rather than assumed.** Ext4's
only observed baseline is the 2026-08-07 cell at **10/30 = 0.3333**; its 95%
Wilson interval is **[0.192, 0.512]**, the honest plausible range at one session.
Re-running the *same* formula that produced 17.3 pp
(δ = (z₍.975₎ + z₍.80₎)·√(2p₀(1−p₀)/120); it reproduces 17.29 pp at p₀ = 0.3533)
as the **baseline** moves across that range — which is what changing filesystem
does, and is a different question from the §5.1 table:

| p₀ | 0.192 (Wilson lo) | 0.250 | **0.333 (ext4 observed)** | 0.353 (committed) | 0.450 | 0.512 (Wilson hi) |
|---|---|---|---|---|---|---|
| **MDE (pp)** | 14.25 | 15.66 | **17.05** | 17.29 | 17.99 | 18.08 |

**Bounded in [14.3, 18.1] pp across ext4's entire plausible baseline.** Worst
case 18.1 pp is a 0.8 pp degradation on the committed 17.3, still **31% of the
barrier's own 58.0 pp effect** — the criterion the 17.3 figure was justified
against. At ext4's actual observed rate the design is marginally *more*
sensitive. **k stays 4.**

**5.2b The secondary transfers only partly, and the residue is declared.**
sd(d) ≈ 3.70 = √2 × 2.618, where 2.618 = √(30·0.3533·0.6467) is the *within*-session
binomial sd. At ext4's p₀ = 0.3333 that becomes √2 × 2.582 = **3.65**, and the
secondary half-width 3.1824 × 3.65/2 = 5.81 counts = **19.4 pp** against the
committed 19.6. The p₀ transfer is immaterial.

What does **not** transfer: sd(d) = √2 · sd₍within₎ assumes pairing removes the
*whole* between-session component. On drvfs that component is measured (session
sd 6.07 across five, 6.99 across the homogeneous four; over-dispersion 5.37 and
7.14). **On ext4 it is unestimable — there is one session.** If the session
effect acts unequally on the two arms, sd(d) is larger and the secondary's
interval is wider.

> **DECLARED ASSUMPTION.** Pairing is assumed to remove the between-session
> component on ext4 as it is measured to on drvfs. This cannot be checked before
> collection and is not claimed to be. **If the realised sd(d) exceeds 3.70, the
> interval is reported wider. No fifth session is added.** §8 names this case
> explicitly.

---

## 6. Registered rules that must exist before the data does

### 6.1 The ext4 replication — TERTIARY, registered because it will exist anyway

8.4's `ledger_postings` arm is 4 sessions × 30 AEP-full runs on ext4: a
**homogeneous ext4 replication of the paper's headline cell**, where the paper
has n = 1 session and the existing replication set is drvfs. It is real evidence
and it will exist whether or not it is planned. Claimed after the fact it would
be post-hoc; registered now it is credible.

Reference values, all from `paper/generated/numbers.tex`: paper's ext4 point
`\UnwantedPrevented` = **18**; drvfs replication `\ReplicationPreventedMean` =
**17.2**, `\ReplicationPreventedLow`/`High` = **[6.1, 28.4]**; per-session
prevented 8, 16, 21, 24 (sd 6.99).

**Registered prediction.** The four ext4 sessions' **mean prevented count lands
inside [6.1, 28.4]**, near 17–18.

**Direction — registered as an expectation, with no threshold, and the reason is
stated.** The mechanism predicts ext4 should prevent *more*: ext4's kill latency
is systematically lower (pooled median **858.9 ms** vs drvfs **1000.8 ms**,
−141.9 ms, comparable to the +194 ms within-stratum discriminating difference),
and a faster kill leaves the acknowledgement less time to win. **The one existing
ext4 session already sits against that**: 18 prevented against the drvfs mean of
17.2 — a 142 ms shift that produced no visible move. The tension is recorded, not
resolved in advance, and no directional threshold is registered.

### 6.2 What the spread will mean — including the boundary region

The sharper prediction is dispersion. Registered:

| ext4 session-level range | verdict | consequence |
|---|---|---|
| **≥ 10** | **DISPERSED** | replicates drvfs's instability; over-dispersion is not filesystem-specific; 8.1's framing stands |
| **6 – 9** | **BOUNDARY — "cannot distinguish"** | not evidence for either reading. Report ext4's over-dispersion φ beside drvfs's 7.14 and state the question is open at k = 4 |
| **≤ 5** | **TIGHT** | the over-dispersion is drvfs-specific — a finding about the environment, not the protocol |

**Why the boundary region is named in advance.** 9C's verdict (i) VARIABLE fired
on `range(S) ≥ 8` with an observed range of exactly 8, and 9C's own report
records that this "is not a comfortable margin". Reusing ≥ 8 unchanged would
inherit that discomfort. Worse, **9C's scheme classified nothing in 6–7**:
(i) needed ≥ 8 and both (ii) and (iii) needed ≤ 5. The scheme above leaves no
range unclassified.

**BOUNDARY is a verdict, not a deferral.** It is reported as "cannot
distinguish" — the vocabulary AMENDMENT 4 already established for the
filesystem-interaction test at p = 0.25 — and **is not a reason to collect a
fifth session.** The marginal case is exactly where optional stopping is most
tempting, which is why it is decided here.

### 6.3 Missing vs false, for `durability_ack_observed`

Both HALT. They mean opposite things. The moment one occurs is the worst possible
time to decide which it was.

**First, a structural fact that shapes the rule.** `REGIME_REDIS_KILL_PREACK`
pins `executions_per_run = 1` (`run_matrix.py:240`), and `analyze.py:1141-1145`
emits `0` only when a run's `durability_ack_execution_ids` is non-empty and this
execution is not in it — impossible in a one-execution run. **The column is `1`
or `""`, never `0`.** There is no sibling execution inside a run to discriminate
against, so the rule must be **cell-level**. Let `acks(cell)` = the number of
runs in that cell with a non-empty `durability_ack_execution_ids`.

| Observation | Class | Meaning | Action |
|---|---|---|---|
| `applied=1 ∧ ack=1` | — | invariant holds | normal |
| `applied=0 ∧ ack=""` | — | the kill won the race | normal, and the majority case |
| `applied=0 ∧ ack=1` | — | ack won; dispatch/apply did not follow | **normal** — the invariant is one-directional; `ack ⇒ applied` is not claimed |
| `applied=1 ∧ ack=""`, **`acks(AEP-full cell) > 0`** | **FALSE** | the observer demonstrably worked in this cell and recorded no acknowledgement for a run that applied | **HALT.** Protocol finding: a dispatch without dispatch authorization, which `DispatchAuthorizationError` is supposed to make impossible. Report, minimise, **do not re-run** |
| `applied=1 ∧ ack=""`, **`acks(AEP-full cell) = 0`** | **MISSING** | the observer fired nowhere | **HALT.** Instrumentation defect. **Says nothing whatever about the protocol.** Diagnose the observer; the session is not analysed and not folded into k = 4 |

**Two gates, evaluated FIRST — before the invariant check and before any
estimand**, on the same principle by which P9-A required the positive control to
be read first.

**Gate 1 — B3 positive control.** This is what §4 buys. B3 traverses the same
checkpoint and never blocks, so it should acknowledge in essentially every run.
Registered: **`acks(B3 cell) ≥ 28` per session.** Below that, the observer is
unreliable and **every `""` in that session is MISSING, not FALSE** — which
closes the hole that `acks > 0` alone would leave, where an *intermittent*
observer is misread as a protocol violation.

There is **no negative-control arm in this regime**; §4 removed the one that
looked like it. The only negative evidence is the unit test that the observer
fires at no other boundary
(`experiments/harness/tests/test_provenance_and_ack.py:46`). Said plainly here
rather than implying a run-level control exists.

**Gate 2 — harness version.** Each root records `harness_version` via
`experiments/harness/provenance.py:224`. Registered: **`commit` must be `e67efd1`
or a descendant.** If it is not, the observer's presence is not established and
every `""` is MISSING by construction.

> **Registered expectation about `dirty`, so it cannot fire spuriously.**
> `harness_version()` computes `dirty` as `bool(git status --porcelain)`, and
> `?? CLAUDE.md` is untracked, unrelated and pre-existing (§1). Verified at this
> commit: `{'commit': 'e67efd1…', 'dirty': True}` on a tree that is otherwise
> clean. **`dirty: true` is therefore EXPECTED throughout 8.4 and is not a gate
> condition** — registering "dirty ⇒ HALT" would have failed every session for a
> reason having nothing to do with the observer. What is gated instead:
> `git status --porcelain` is recorded at each session start and must show
> **only** `?? CLAUDE.md`. Anything else halts the session.

---

## 7. Collection and stopping

Per session: confirm the host quiet and `git status` as above; record host load;
run `run_matrix.py --regime redis-kill-preack --max-tier 2 --results-root
experiments/results/b2-paired-s<N>-<date>` (both endpoints, unfiltered); record
load again; freeze and verify; commit before starting the next. **Collection runs
on ext4**, per the 8.1.0 report §E.3 — it drops the event-log append cost ~40×.

**Stop mid-run and come back if:** any HALT in §3.5 fires; any §3.4 exception;
either gate in §6.3 fails; `canary_survived + canary_lost ≠ 30` in any arm;
`uptime_after_seconds` large in any run; host load outside 9C's observed
0.10–2.49; a session kill-latency median outside the 859–1216 ms envelope
(record, then continue); `git status` showing anything but `?? CLAUDE.md`;
session wall time > 1.5× model (3213 s).

Stopping means: finish the run in flight, freeze what exists, report the partial
session, and **do not** fold it into the k = 4 set.

**Reporting cadence: after session 1, not after session 4.** If the balance check
or an observer gate fails, that is knowable at ~1.4 h rather than ~5.5 h.

---

## 8. The no-extension commitment

**k = 4 is committed and will not be extended after seeing results.** Adding
sessions post hoc is optional stopping and would forfeit the discipline that
makes Phase 9's result believable.

Three specific temptations this forecloses, named now because a rule that names
its hard cases is harder to reinterpret later:

1. **A wide secondary interval** (§5.2b). If realised sd(d) exceeds 3.70, the
   interval is reported wider. No fifth session.
2. **An unexpected AUTH applied fraction.** §5.1's sensitivity table and §5.2a's
   baseline-transfer table between them show the MDE stays within
   [13.4, 18.1] pp across every plausible value. Reported, not acted on.
3. **A BOUNDARY ext4 spread** (§6.2). Reported as "cannot distinguish". No fifth
   session.

---

## 9. What would be uncomfortable, stated before it can happen

An ext4 four-session mean **outside [6.1, 28.4]** means the ext4 and drvfs
populations differ — the filesystem does reach the applied rate. Precisely what
that would and would not contradict, so it cannot be fudged afterwards:

- It would **not** contradict **F.2a's fact**. Redis's `/data` is a named Docker
  volume (`compose.phase2.yml:12`), verified by `docker inspect`:
  `type=volume, src=/var/lib/docker/volumes/aep-phase2_redis-data/_data`. So
  `WAITAOF` latency was constant across both strata. That is verified and stays
  true.
- It **would** contradict the **inference** that the confound is therefore
  immaterial. **F.2a narrows the confound to the harness side; it does not
  eliminate it.** The live route is already measured in the 8.1.0 report §E.3:
  the event-log append costs **229.7 µs on drvfs against 5.4 µs on ext4**, ~40×,
  and the worker's ability to process `WAITAOF`'s reply competes with that write.
  Naming the route in advance means a surprising result is read as evidence on a
  stated hypothesis rather than as a puzzle.
- **Consequence if it fires:** 8.1's paper text is revisited in 8.6 and the
  result reported as the finding. It is **not** grounds to re-run, to drop a
  session, or to add one.

---

## 10. What this pre-registration does not cover

- **POS_ONLY.** `notifications` is not in `REGIME_REDIS_KILL_PREACK.endpoints`
  (`run_matrix.py:249`) and filtering to it yields zero cells silently. Deferred
  to a new regime, not an edit to the existing one, so the frozen cells'
  provenance is unchanged. Not this phase.
- **Other hosts.** One WSL2 machine. §9's mechanism makes this sharper, not
  weaker: the effect size is a function of the host's kill-latency distribution,
  so a second host would sample a different distribution, not add a replicate.
- **Other crash points.** `after_intent_before_barrier` only.
- **`redis-kill-inflight`.** Fully defined (`run_matrix.py:259-279`), zero runs.
- **The barrier's durability claim.** Backlog B1 — protocol outcomes under
  block-level write loss — is untouched; no process-level fault can close it.
- **Detection.** Unchanged and not re-examined.
- **No submission, upload, DOI, or tag.**

---

## 11. Verification of this document

1. `git rev-parse HEAD` above equals the **parent** of this document's commit.
2. All five provenance commands re-run at that commit with raw output pasted.
3. **Pushed before collection**, verified on the remote by inspection — not by
   exit code — as 8.0 required.
4. The commit contains no file under `experiments/results/b2-paired-*`.
5. Full pytest and `check_paper_numbers.py` re-run: expected unchanged, since no
   code, macro or paper file is touched. This commit is inert by construction.
