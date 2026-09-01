# What the paper claims now — a per-claim assessment before Phase 10

**Unit 1 of the pre-Phase-10 assessment. This unit is sealed on commit**: the
recommendation (unit 4) is written afterwards and refers only to what is
committed here, so it cannot reach back and shape the findings it rests on.

**Nothing is fixed here.** Custody is a separate verdict in
`reports/phase-report-9-custody-inventory-2026-09-01.md` and does not enter this
assessment.

Quotations are read from the built PDF, not from source. Tooling:
`phase8-driver/claim_sweep.py`.

---

## 1. Method, and what it can and cannot reach

**A withdrawn *number* cannot survive anywhere in this manuscript.** The orphan
gate catches defined-and-unused, LaTeX catches used-and-undefined, and B9
confirmed the ratchet twice. That risk is structurally closed.

**A withdrawn *claim* is caught by nothing.** F.0b named the mechanism — a
careful statement is made once with its bound, then restated somewhere that
needed it as a premise, and the restatement keeps the conclusion and drops the
qualification — and recorded the enforcing lexicon check as unimplemented.

This is that check, widened from equivalence vocabulary to strength vocabulary
(*large, buys, because, is a function of, we show, prevents, guarantees, is
real, now measured, structural*, …), run over all nine sections, `main.tex`
**and the six generated captions**. B20 found two of its four defects inside
generated captions and no grep over `sections/*.tex` reaches them.

| | |
|---|---|
| macro sites (auditable against a source) | **251** |
| sentences in the manuscript | **756** |
| **sentences with evidential force citing no macro** | **137 (18%)** |

Distribution of the 137: `06-evaluation` 42, `08-threats` 39, `07-related` 11,
`01-introduction` 10, `03-model` 8, `04-protocol` 7, `02-motivating` 6,
generated captions 6, `05-implementation` 3, `09-artifact` 2, `main.tex` 2.

**The limit of this method, stated plainly:** it matches sentences to their own
evidence. It does not match sentences to each other. That is unit 1b.

---

## 2. The central claim, verbatim

**Abstract**, as rendered:

> Our central result separates two claims that the write-ahead pattern is
> usually sold as one. *Detection* — no undetected duplicate and no lost effect,
> with a residual of declared ambiguity whose rate is set by what the endpoint
> can be asked — is produced by the pre-dispatch record and a transition table
> that prohibits re-entry into dispatch.

**`06-evaluation.tex`, `sec:eval-detection`**, as rendered:

> **We report this as a finding rather than as a limitation, because it
> reassigns our own headline claim.** The property that distinguishes AEP from
> B0, B1 and B2 — and the property the paper is named for — is produced by the
> pre-dispatch record and by the transition table that refuses to re-enter
> ABOUT-TO-FIRE. It is not produced by waiting for `fsync`.

**The two agree, and this claim is untouched by everything this phase
withdrew.** Nothing in the detection result depended on the kill-latency
mechanism, on the flakey p-values, or on B3-as-a-control.

---

## 3. Per-claim verdicts

### Bucket A — supported at their stated strength (7)

| claim | evidence | precision |
|---|---|---|
| **Detection is produced by the pre-dispatch record, not the barrier** | 540 crashed executions per arm, 0 duplicates and 0 lost effects in both | one-sided 95% Wilson upper bound **4.77%** over 54 run clusters per arm; joint coverage ≥ 90% for the pair |
| **Declared ambiguity is materially unchanged by the ablation** | 195/540 vs 193/540 | stratified run-cluster **90%** interval [−1.11, +2.04] pp, within a ±5 pp margin **stated as a post hoc stipulation** |
| **The baselines without a pre-dispatch record duplicate in most crashed executions** | B4/B4b family | 77–83%, more than an order of magnitude from either bound |
| **AEP records no undetected duplicate and no lost effect in any cell measured** | descriptive | count, no inference |
| **The barrier's durability benefit is real under block-level write loss** | 3 independent replications, perfect separation in each | **30/30 in each**, no p quoted, design floor 0.1 stated |
| **No process-level fault can exercise the barrier's durability** | same probe, process kill | 0/10 lost |
| **Ablating the barrier produces no observed difference in the crashed-regime detection metrics** (intro C4) | as row 1 | **descriptive form, which F.0b explicitly permits.** Correct as written |

**Row 7 is worth stating as a pass.** The introduction says *"no observed
difference"*, not *"indistinguishable"*. That is the one admissible wording when
the licensing quantity is elsewhere, and it was written that way.

### Bucket B — supported more weakly than stated (4)

**B1. `08-threats.tex:385` — the mechanism asserted as fact, contradicted 285
lines earlier in the same file.**

> "…and, as we say there, its effect size **is a function of** that host's
> `docker kill` latency. It is the whole of the barrier's measured case."

`08-threats.tex:96` now reads: *"The protocol's own logic offers a reason … but
our measurement of that reason does not establish it."*

**The same document asserts the mechanism as established in one place and denies
that the measurement establishes it in another.** I introduced this
contradiction: I corrected the first site in B9 unit 3 and did not look for its
restatements. **This is F.0b's restatement problem committed inside the fix for
the previous instance of F.0b's restatement problem.**

**B2. `08-threats.tex:85` — "can now show".**

> "…an effect size we **can now show** is host-dependent rather than merely
> suspect it is…"

What remains: one unreplicated session at p = 0.03, and a four-session interval
of [−91, +302] ms containing zero. **"Can now show" asserts a demonstration the
evidence no longer supports.** The sentence was written when the pooled
p = 4.0×10⁻⁹ existed.

**B3. `06-evaluation.tex:463` — "therefore" chaining to withdrawn support.**

> "18 is **therefore** not a constant of the protocol and this paper does not
> offer it as one: **it is where one host's kill-latency distribution happened
> to place a race.**"

The first clause is a *disclaimer* and is safe. The second states the mechanism
as fact and the "therefore" chains it to the paragraph immediately above, which
now concludes the opposite. The following sentence — *"What is structural is
that the race exists for AEP-full at all and cannot exist for B3"* — **is sound
and is a design claim, not a measurement.** Only the middle clause is exposed.

**B4. The abstract states the prevention result with no precision qualifier.**

> "…in one NO-READBACK capability class, at one pre-acknowledgement Redis-kill
> point, on one host, its unwanted-applied-effect rate is 0.3333 versus 0.9333
> over 30 runs per system (10/30 versus 28/30, Fisher **p = 1.9 × 10⁻⁶**) — 18
> real non-idempotent effects not committed."

The body measures the same quantity **five times**: it ranged 4–20 out of 30,
session-clustered mean 17.2 prevented, interval **[6.1, 28.4]** — a half-width
0.65× its mean.

The abstract carries three *scope* qualifiers and **no precision qualifier**,
and `1.9 × 10⁻⁶` is the most precise-looking number in it. **Under F.0's general
form the precision travels with the result.** The single-session p is not wrong;
it is the least informative available summary of a quantity that has since been
replicated four more times, placed where a reader forms their impression of how
firm the result is.

*(This is the precision question. B24 filed the separate question of whether
that Fisher's unit is right.)*

### Bucket C — no support beyond a single unreplicated session (1)

**C1. The race mechanism — the explanation for why prevention varies.**

| what was support | status |
|---|---|
| pooled `\KillLatencyDiff` +201 ms | **withdrawn** — pooling artefact |
| pooled `\KillLatencyP` 4.0×10⁻⁹ | **withdrawn** |
| B3 as negative control, −14 ms at p = 0.63 | **withdrawn** — never a control |
| 8.5's covariate non-degeneracy | **withdrawn** — not prediction |
| **ext4, one session, +88 ms, p = 0.03** | **retained; k = 1** |
| four-session replication | **[−91, +302] ms, half-width 1.86× the mean** |

**One unreplicated session, plus a replication too imprecise to confirm or
refute it.** The paragraph in `06-evaluation.tex` states this correctly. Three
sentences elsewhere (B1–B3) do not.

---

## 4. Abstract–body agreement

The abstract predates the withdrawals. Compared sentence by sentence on
*strength*:

| abstract sentence | body | agree? |
|---|---|---|
| detection separated from prevention | `sec:eval-detection` | **yes** |
| 4.77% over 54 run clusters | same, and the caption adds that per class it would be 20.1 pp | **yes** — the abstract makes no per-class claim, so omitting 20.1 is not an overclaim. **Recorded as a pass; it was checked** |
| ambiguity difference with 90% interval | same, with the margin stipulation | **yes** |
| **prevention, p = 1.9 × 10⁻⁶, 18 prevented** | measured 5×, 4–20, [6.1, 28.4] | **no — B4** |
| flakey: 3 replications, perfect in every one, 90/90 | per-replication 30/30 in each | **yes** — the replication structure is carried in the abstract's own words |
| "Because detection does not depend on the barrier, its cost is a deployment choice" | `sec:eval-deployment` | **yes** |
| **the kill-latency mechanism** | — | **the abstract never mentions it.** Everything in bucket C is absent from the abstract |

**The abstract does not overstate the detection result, and it does not mention
the mechanism at all.** Its single disagreement with the body is B4.

**`\ClassPp*` — the registered primary estimand, CONFIRMS at a 33.9 pp
half-width against a 12.5 pp mean — appears only in `08-threats.tex`.** Not in
the abstract, not in the evaluation section. That is not an overclaim: the
paper makes no class-effect claim anywhere, so there is nothing to qualify. It
is a placement question, and `sec:eval-prevention` does cross-reference it
(*"that comparison did not reach a precision adequate to the question"*).

---

## 5. Summary

**Twelve claims adjudicated: 7 supported at stated strength, 4 supported more
weakly than stated, 1 with no support beyond a single unreplicated session.**

**The central result stands, unweakened and unqualified by anything this phase
withdrew.** Detection is produced by the pre-dispatch record and not the
barrier; the ablation, the bound and the baseline contrast that support it were
never touched. The corrections this phase made all landed on the *prevention*
half and on the *explanation* of the prevention result — the newest and most
novel material, which is where the paper's own threats section already said the
weakest evidence was.

**Three of the four bucket-B items are the same defect in three places:** a
sentence that asserts the race mechanism as established, written when the
pooled p existed, and left behind when that p was withdrawn. **Two of the three
are in the same file as the corrected version.**

**The fourth is the abstract's missing precision qualifier on prevention.**

None of the four requires new evidence to resolve. Each is a wording change of
one clause.
