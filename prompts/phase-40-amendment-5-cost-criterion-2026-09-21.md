# Amendment 5 — C4 failed twice, the stop rule was armed, and the author overrode it

**Amends `prompts/phase-40-agent-reachability.md`** §6 (the stage-10 cost
criterion) and records an explicit override of §9 (the stop rule). The
pre-registration is not edited. Committed **before any further live call** and
before the code that implements the replacement criterion.

This amendment is an **override**, not a clarification. It is written that way
deliberately: a stop rule that is quietly reread is not a stop rule, and a
reader who finds C4 replaced should be able to see that the condition fired,
who overrode it, and on what reasoning.

---

## 1. What happened, on §9's plain words

§6's stage-10 row ends: *"measured cost within 20% of §3's model."*

`reports/phase-report-40-stage-10-2026-09-21.md` assessed both live
collections against it. **C4 failed in both.**

| collection | calls | USD | per call | vs §3's model | verdict |
|---|---|---|---|---|---|
| null stage (amendment 2) | 2 | 0.000275 | 0.00013750 | 8.44 % | **failed as written** |
| retry stage (amendment 3) | 5 | 0.001104 | 0.00022080 | 13.56 % | **failed as written** |

§9 reads:

> **Stages.** Any stage fails its criterion **twice**. One failure is a bug;
> two is the design.

**Two failures of one criterion is exactly the condition §9 describes, and the
condition was armed.** Nothing about that is in dispute and nothing below
retracts it.

## 2. The ruling

**The author ruled that C4's two failures are a defect in the criterion, not a
failure of the design, and overrode the stop rule on that basis.** The
reasoning, recorded as given:

**§3's model is a ceiling, written with `≤`.** Its only arithmetic is
*"1 000 attempts × (≤2 000 input + ≤1 024 output tokens)"*, under the heading
*"Ceiling if something goes wrong"*. Per call that is

```
2 000 × 0.20/10⁶  +  1 024 × 1.20/10⁶  =  0.0004 + 0.0012288  =  0.0016288
```

which reproduces both of §3's published figures exactly (USD 1.64 at the
current price, USD 8.14 at the stale one), so the model is not in doubt.

**C4 asked for a measurement within ±20 % of that ceiling.** A stage can only
land inside that band by nearly exhausting the token caps on every call. The
observed collections used **16–18 % of the prompt cap and 6–12 % of the output
cap**; a ~350-token prompt cannot cost within 20 % of a 2 000-token cap's
price. **No healthy stage could ever have satisfied C4.** It would have failed
identically on a stage that did everything right, which is what distinguishes a
criterion defect from a design failure.

**And the second reading of C4 is unavailable.** If C4 exists to confirm the
project is billed what it thinks, it cannot do that either: the "measured" cost
is not a measurement. It is Azure's token counts multiplied by a price constant
this repository hardcodes, and `tokens × price = recorded USD` holds exactly in
all four runs. The only unverified term is the constant, and checking it needs
the invoice.

**What this override does not do.** It does not touch §9's other two limbs —
the USD 10 spend threshold and the 2026-10-15 date — and it does not excuse any
other criterion. It is specific to C4.

## 3. Nothing is retroactively passed

**Both earlier verdicts stand as `failed as written`.** The null stage and the
retry stage each failed C4 and the record says so, in the stage-10 report and
here. They are not re-scored under the replacement criterion, and any later
summary that describes stage 10 must carry those two failures.

The replacement criterion in §4 applies **from the next stage forward only**.
A criterion rewritten after seeing the data it failed on is only honest if the
failures it replaces stay visible, and §9's counter for C4-as-written is closed
at two rather than reset to zero.

## 4. The replacement: C4′, and it can fail

C4 is replaced, for all stages from here, by three limbs. The first two are the
author's; the third is argued for in §4.4 rather than substituted silently.

### 4.1 C4′(a) — every call's recorded cost is at or under §3's per-call ceiling

> For every entry in every `planner-transcript.jsonl` in the collection,
> `prompt_tokens × 0.20/10⁶ + (completion_tokens + reasoning_tokens) × 1.20/10⁶`
> must be **≤ 0.0016288**, §3's per-call ceiling.

This is a bound, not a band, so a healthy stage satisfies it and a stage that
blows the model fails it.

**It can fail, and the path is live.** `max_prompt_tokens = 2000` is
**not enforced anywhere.** `CallWrapper.attempt` uses it only to price the
reservation (`experiments/harness/planner.py:728-735`); the outbound request is
bounded on output (`max_output_tokens` is passed to the API) and **not on
input**. A prompt above 2 000 tokens is dispatched, billed, and recorded, and
nothing today notices.

That is not hypothetical under the interactive loop. Amendment 4 added
`last_outcome` to every prompt and the loop re-asks on every turn; live prompts
on record are 330–356 tokens, but they were produced by the plan-then-execute
shape that no longer runs. C4′(a) is the check that catches prompt growth
before it silently invalidates §3's ceiling.

### 4.2 C4′(b) — the recorded USD is reproducible from the transcript and a cited price

> The collection's recorded USD must equal an **independent recomputation**
> from the transcript's own token counts and a published price whose source —
> URL and retrieval date — is cited in the repository.

Two halves, and both can fail:

* **The citation.** `Price`'s docstring says "read 2026-09-17" and names no
  source. This amendment requires a `PRICE_SOURCE` constant carrying the URL
  and the retrieval date, and the check fails if it is absent or undated.
* **The recomputation.** The checker must recompute from the transcript using
  the documented formula, **not** by calling `Price.usd` — otherwise it
  compares the code with itself. Recomputed independently, it fails if the
  pricing code ever drifts from the documented rule. The most likely drift is
  concrete: `Usage.output` adds reasoning tokens to completion tokens, and on
  one recorded call reasoning tokens were **four times** the visible
  completion. A change that dropped them would understate every bill and no
  current check would see it.

**The invoice check is an OPEN ITEM, not done.** C4′(b) verifies the repository
is internally consistent and that its price has a citable source. It does
**not** verify that Azure charged that price. That requires the Azure invoice or
cost-analysis blade, which has not been read. Until it is, the paper may say the
cost was *computed* from vendor-reported token counts at a published rate, and
may not say it was *billed* at that rate.

### 4.3 C4′(c) — no call costs more than its reservation

> For every reservation key in `planner-cumulative.jsonl`, the settle entry
> must be **≤ 0**.

### 4.4 Why (c) is added rather than assumed

§3 makes the cumulative counter the control that enforces the collection-wide
ceiling, and the counter's safety property is stated in the code: reserve at the
maximum §3 allows *before* dispatch, settle the difference after, so that dying
in between **over**-counts and stops the collection early rather than spending
money nobody counted.

That property holds only while the reservation is genuinely an upper bound. It
is an upper bound only because of `max_prompt_tokens`, and §4.1 has just
established that `max_prompt_tokens` is not enforced. **A prompt over 2 000
tokens therefore produces a positive settle, and a positive settle means the
counter under-counts and the USD ceiling can be crossed without the cap
firing.** That is the one failure mode that makes every other spending control
in §3 unsound, and §3 has no check for it.

(a) and (c) catch the same underlying fault from two different records — (a)
from the transcript, (c) from the ledger — which is the point of having both:
they also disagree with each other if the transcript and the journal ever
diverge. In both existing collections every settle is negative, so (c) passes
today and is not being added to manufacture a failure.

If the author judges (c) redundant, striking it leaves (a) and (b) intact; it
is proposed here rather than adopted quietly so that choice is available.

### 4.5 The known-positive

`docs/25` R2 — *a negative result is only trusted after a known-positive* —
applies to a criterion as much as to a probe. **A criterion that has never been
shown to fail is not evidence that anything passed.**

`tests/test_planner_cost_criterion.py` therefore carries, for each of the three
limbs, a case that **must** fail it:

| limb | injected fault | must be caught |
|---|---|---|
| (a) | a transcript entry with 4 000 prompt tokens | cost 0.0020 > 0.0016288 |
| (b) | a collection whose recorded USD omits reasoning tokens | recomputation disagrees |
| (b) | `PRICE_SOURCE` blank or without a date | citation missing |
| (c) | a journal whose settle is positive | reservation was not an upper bound |

and, beside each, the clean case that must pass — including both archived
collections, which the checker is run against so that C4′ is shown to be
satisfiable by real data and not only by fixtures.

The criterion is implemented as `scripts/check_planner_cost.py` so that it is
executable rather than prose. A stage is assessed against C4′ by running it.

## 5. The next stage, and how §9's "twice" counts from here

**The next stage is a re-run of the 10-call stage on the interactive loop.**
Not stage 30. The stage-10 report's §4 gives the reasoning and it is adopted:
the prompt changed in amendment 3 and the loop in amendment 4, so neither
existing collection came from the instrument that stage 30 would run, and
stage 30's criterion is a *result* rather than an instrument check — a new
instrument fault would arrive entangled with the replay evidence and neither
could be read.

**It counts as a NEW stage-10 attempt**, assessed against C1, C2, C3 and
**C4′**. It is not a continuation of either earlier collection.

**How §9's counter stands from here, stated explicitly so it is not argued
later:**

| criterion | failures so far | counts toward §9 |
|---|---|---|
| C4 as written | **2** (null, retry) | **closed at 2, overridden by §2 above** — not reset, not carried forward |
| C4′ | 0 | **counts from the next stage forward.** Two failures of C4′ arms §9 again, and that arming is not overridable by this amendment |
| C1, C2, C3 | 0 | unchanged; counted per stage as §9 always said |

**C4′'s counter starts at zero and the author does not get this override
twice.** If C4′ fails twice, §9 applies on its plain words, because C4′ — unlike
C4 — is a criterion a healthy stage can satisfy, so two failures would mean what
§9 says they mean.

## 6. One thing this amendment deliberately does not fix

§5 of the pre-registration also lists `temperature` and `top_p` among the
recorded transcript fields, and they are absent — `sampling` carries only
`{"reasoning_effort": "low"}`. That is very probably correct, because the
Responses API does not accept them for a reasoning deployment, but §5 says they
are recorded and the record should say *not settable on this deployment* rather
than omit them silently.

It is **not** changed here. The transcript schema is being bumped in the same
session for the timestamp, so folding this in would be cheap — and that is
exactly why it is left alone: it is a second change to what §5 requires, made
on an inference about the vendor's API that has not been tested against the
vendor. It is recorded as open, for the author.

## 7. What is unchanged

§1's design, §1.1's harness-assigned target, §2's metric and its prohibition on
rates, §3's five controls and both of its USD figures, §4's `PLANNER_FILTERED`,
§5 apart from the timestamp that amendment 5's companion commit adds, §6's
C1–C3 and its staging, §8's failure definitions, and §9's spend and date limbs.
Amendments 1, 2, 3 and 4 stand in full.
