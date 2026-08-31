# Phase 8.6 §F — findings, contradicted predictions, and disclosures

Everything Phase 8.4's collection and 8.5's analysis established that a reader
of the manuscript needs and would not otherwise get. Registered predictions that
failed are reported as findings and **not re-run**, per 9C's precedent and the
plan's standing rule.

**Nothing here is a re-analysis request.** The k = 4 set is closed, the
registered rules were applied as written, and no verdict below is reopened.

---

## F.0 The verdict, and what travels with it — binding

The primary estimand returned **CONFIRMS**.

**This binds the claim, not a word.** Wherever the primary estimand's result is
stated **in any form** — `CONFIRMS`, "a null", "no effect", "no class effect",
"no difference", "statistically indistinguishable", "the interval contains zero",
or any paraphrase — in prose, a table caption, a figure caption, an abstract, or
the sentence around a macro, the realised precision is stated with it.

**A paraphrase does not exempt.** The test is not whether a particular word
appears; it is whether a reader is being told what the class comparison found. If
they are, the qualification travels with it. **There is no form of words that
reports this result and escapes the binding.**

> **The registered rule returned CONFIRMS at a realised precision inadequate to
> the question.** The interval contains zero at a width that would also have
> contained most effects worth detecting.

| | |
|---|---|
| registered minimum detectable effect | 17.3 pp |
| projected §3.2 half-width at k = 4 | 19.6 pp |
| **realised §3.2 half-width** | **33.9 pp** |
| **observed mean effect** | **+12.5 pp** |

**The first two rows are themselves defective — see F.5 and B19.** Both were
computed without a between-session variance component, so they understate the
precision the question actually required. They are shown here because this is the
record of what was registered; **they are deliberately not quoted in the
manuscript**, where the self-contained comparison is the half-width against the
observed mean.

**The mean effect is smaller than the half-width. The design could not have
detected the effect it found.** This is not failure to reject in the ordinary
sense; it is failure to reject by a design underpowered for its own result.

The correct sentence is *"an effect of +12.5 pp was observed by an instrument too
blunt to resolve it, and by the registered rule that counts as failure to
reject"* — not *"no class effect was detected"*. A reviewer reaches this in one
step, and its absence would be the paper's weakest point.

**F.5 records the same fact as a finding. F.5 is not a substitute for F.0.**

## F.0a The first version of this binding was evaded on its first use

**Recorded because it is a finding about the disclosure mechanism, not an
anecdote about drafting.**

F.0 was first written to bind a **word**: *"The primary estimand returned
CONFIRMS. That word may not appear anywhere … without the following beside it."*

**The very first sentence written under it evaded it.** The draft of the
`08-threats.tex` replacement said *"the registered test nonetheless returns a
null"* — reporting the result, never using the bound word, and therefore never
triggering the binding. It also used the exact idiom F.1 forbids and that this
report had already flagged, three sections earlier, as the phrasing that would
absorb this result if reused.

**Nothing was hidden and nothing was caught.** The evasion was not deliberate;
the requirement simply did not reach the sentence, because the requirement was
about a string and the sentence was about a meaning.

**This is the class that has recurred throughout the phase** — B11's "a gate that
looks live and cannot act", the four instances in handover finding 5, B19's
sensitivity sweep that varied the wrong parameter, B18's guard that fired on the
intercept. **A check that structurally cannot detect what it names.** It has now
occurred in the disclosure rule written to prevent exactly this result being
misread.

**Two consequences.**

1. F.0 now binds the claim rather than the string, and says explicitly that a
   paraphrase does not exempt.
2. **A word-level rule is not sufficient for a semantic requirement**, and the
   general lesson is worth more than this instance: any future requirement of the
   form "X must always accompany Y" needs Y defined by what it *means*, because
   the failure mode is not violation — it is a sentence that never matches the
   trigger. Nothing flags a rule that has stopped applying.

## F.0b The principle, stated without reference to any quantity

**F.0 binds one estimand. That is why it caught one instance and not the other.**
This section states the rule the two instances share, deliberately naming no
metric, no comparison and no phase, so that the next instance is caught by the
rule rather than by someone happening to sweep for it.

### The rule

> **A failure to reject may not be reported as indistinguishability, equivalence,
> sameness, or absence of an effect — in any wording — unless the precision that
> licenses that reading is stated in the same place.**
>
> "The same place" means the sentence, the caption, or the list item a reader
> encounters the claim in. Not the section. Not an earlier paragraph. Not a
> different document.
>
> The licensing precision is one of: an interval and its coverage; an upper
> bound and its coverage; or an equivalence margin, together with whether that
> margin was pre-registered or stipulated after the fact.
>
> Where no such quantity exists, the only admissible report is the descriptive
> one — *no observed difference*, *the test did not reject* — and it must not be
> restated later in stronger words.

### Why the rule has to be quantity-free

Both known instances arose the same way. A careful statement is made once, with
its bound, in the section that computed it. It is then **restated** somewhere
that needed it as a premise — a deployment recommendation, a limitations list, an
abstract — and the restatement keeps the conclusion and drops the qualification,
because the qualification is not what the later passage is about.

Neither instance is a violation of anything checkable:

- The restatement contains **no number**, so `check_paper_numbers.py` has nothing
  to verify. It compares numbers to sources; a sentence with no number is
  invisible to it, and a sentence that overstates a numbered sentence is
  invisible to every tool in the repository.
- The restatement is **not adjacent** to the careful version, so nothing brings
  the two into contact. In one instance they are 300 lines apart in one file.
- The restatement is often **strictly more readable** than the careful version,
  which is why it survives editing.

A rule scoped to a named estimand cannot catch this, because the mechanism is
generic and the estimand is not. F.0a already recorded that a rule about a
*string* cannot catch a claim about a *meaning*; this is the next step of the
same lesson — a rule about *one quantity* cannot catch a *pattern*.

### What would actually enforce it

Nothing in the repository does today, and this should be recorded as unmet rather
than described as handled:

1. **A lexicon check.** The vocabulary of unwarranted equivalence is small and
   enumerable: *indistinguishable*, *equivalent*, *the same as*, *no
   difference*, *no effect*, *unaffected*, *identical to*, *shows no*. A grep-
   level check that flags each occurrence for manual sign-off would have found
   both instances in seconds. It cannot decide whether a claim is warranted; it
   can refuse to let one pass unreviewed.
2. **Precision-carrying macros.** Where a result is emitted as a macro, the
   bound or interval should be emitted such that quoting the estimate without it
   is awkward rather than natural. Nothing enforces co-quotation today.
3. **A restatement audit.** For each careful statement, find every later passage
   that depends on it and check the qualifications survived the trip. This is
   the step neither instance received.

### Standing

**Two instances, both in this manuscript, found five days apart by different
means** — one by drafting under F.0, one by sweeping under it. Neither was found
by a tool. The rule above is recorded as a requirement on future work; the
enforcement in the list above does not exist, and no claim is made here that it
does.

## F.0c Three instances in one session: correct for a reason nothing enforces

**This is recorded as a pattern, not as three slips.** Three constructions
written in this one session were each correct at the moment of writing and each
would have become wrong under a change nobody would think to guard against.
None of the three was a mistake in the value. All three were the same defect in
the *structure* of the claim.

| # | Construction | Correct because | Would break when | Caught by |
|---|---|---|---|---|
| 1 | F.0 bound the **word** "CONFIRMS" | the draft happened to use that word | a paraphrase states the result without it — which is what the first sentence written under the rule did | drafting under the rule (F.0a) |
| 2 | `\ClassPpTwo{}` to `\ClassPpFour{}` quoted as the spread | s2 happens to be lowest and s4 highest **today** | the data are regenerated, a session is reordered, or `k` is extended | review, not by any check |
| 3 | `\ClassPpLow{}` / `\ClassPpHigh{}` emitted with no precision note | the only sentence quoting them today also quotes `\ClassPpHalfWidth{}` | the macros are quoted anywhere else — which is the entire purpose of a macro | review, not by any check |

**What the three share.** Each rests on a fact that is true, unstated, and
unowned: *the author will use this word*; *this session ordering will persist*;
*this macro will only ever be quoted beside its neighbour*. In each case the
guarantee lives in the author's head at the moment of writing and nowhere in the
repository. Nothing degrades when the assumption stops holding — every macro
still resolves, the LaTeX still compiles, `check_paper_numbers.py` still passes,
and the sentence still reads fluently while stating something false.

**This is B11's class, one level up.** B11 and F.0a are about *checks* that
structurally cannot detect what they name. These three are about *claims* that
structurally cannot notice when they stop being true. The common failure is the
same: the thing that would signal the problem is not connected to the thing that
would cause it.

**Instance 3 is the sharpest, and it is instance 2 in a second place.** A macro
exists precisely so a number can be quoted away from where it was defined. So a
macro whose correctness depends on its quotation context is a contradiction in
terms — and `\ClassPpLow`/`\ClassPpHigh` straddling zero *is* a statement of the
primary estimand's result, the exact claim F.0 binds. F.0 was satisfied at the
prose site and unenforced at the macro site, for the same reason F.0's first
version was evaded: the rule reached the sentence someone wrote, not the claim
someone could write next. Fixed this session by attaching the binding to both
macro descriptions in `scripts/paper_tables.py`, so the requirement travels with
the value rather than with the current prose.

**Two of the three were found by review, not by me and not by a tool.** That is
the part with the most predictive value. The rate at which this class is *found*
in this project is set by how carefully someone reads, and nothing in the
harness contributes. **The correct inference is not that three were fixed; it is
that the population is unknown and the sampling method is manual.** Three found
in one session, in a session that was not looking for them, argues the remaining
count is not zero.

**No enforcement is claimed.** The three enforcement mechanisms listed in F.0b
remain unimplemented, and none of them would have caught instances 2 or 3 in any
case: both are about a *derivation* being pinned to an incidental fact, which no
lexical or numeric check can see. What would catch them is a rule that every
emitted number states what it is derived *from* — index versus extremum,
value versus value-plus-binding — and that rule does not exist.

## F.1 CONFIRMS is failure to reject, not evidence of absence

| session | β class | se | β/se | pp difference |
|---|---|---|---|---|
| s1 | −0.0477 | 0.538 | −0.09 | 0.0 |
| s2 | −0.0268 | 0.610 | −0.04 | −10.0 |
| s3 | **+0.8698** | 0.594 | **+1.46** | +23.3 |
| s4 | **+1.5382** | 0.585 | **+2.63** | +36.7 |

**Two of the four sessions show a substantial positive class effect.** The
interval contains zero because the sessions disagree with one another, not
because the effect is absent.

**This may not be absorbed as a null result, an absence of effect, or a
demonstration of equivalence anywhere in the manuscript.**

## F.2 Heterogeneity is the result

- mean β class **+0.5834**, t(3) interval **[−0.6368, +1.8035]**
- between-session sd **0.7669** against a typical within-session se of **0.5815**

**More of the interval's width comes from sessions disagreeing with each other
than from sampling error inside them.** The class effect is not stable across
four sessions collected on the same host, under the same harness, on the same
filesystem, on the same day and the days around it.

That instability is visible independently in the balance figures — **+13.0,
−97.7, +73.6, +41.3 ms** — and in the covariate imbalance signs **+, −, +, +**.
It is the phase's most durable observation and it is not noise.

**Robustness:** §3.2's unadjusted paired difference reaches the same verdict on a
different quantity — mean **+12.5 pp**, interval **[−21.4, +46.4] pp**. Adding
run position to the primary moves the mean by **+0.003** log-odds and changes
nothing.

## F.3 Two registered predictions were contradicted

Both were registered in advance, both failed, **neither was re-run**.

**F.3a — fault delivery did not keep degrading.** Session 2's jump from 0 to 2
non-landing kills was read as the leading edge of host degradation, and B1 was
annotated on that basis. Sessions 3 and 4 returned **0 and 0**. Across 480 runs
there are **2** non-landing kills, both in one session, both in the first seven
repetitions. Clustered, not a rate, and not a trend.

**B1's entry currently argues from the 0→2 reading and should be annotated with
this.** That is a Phase 12 edit; it is named here, not made here.

**F.3b — drift did not reverse sign.** Session 1's Spearman of −0.478 against
the earlier +0.703 was read as a sign reversal that would recur. **All four v2
sessions are negative.** No reversal in the pre-registered set.

## F.4 A registered halt fired and was overridden by changing the guard

**Stated because the sequence was *halt → change the instrument → proceed*, and a
reader is entitled to see that without reading a diff.**

The first fit of the primary estimand halted on session 2 with "separation or
implausible standard error". The halt was wrong: the guard tested coefficient
magnitude on the **intercept**, which is not a quantity of interest.
`log(latency)` sits near 7.0 with slopes of 2.4–6.7, so the intercept must land
near −7×slope simply to place the curve — it is the log-odds extrapolated to 1 ms
against an observed range of ~740–8200 ms.

None of the three registered halt conditions was met: all four sessions converged
in 6–7 iterations, no predictor perfectly orders the outcome, and every
class-coefficient standard error is near 0.6. The guard was narrowed to exclude
the intercept; **the model was untouched, no penalty or prior was applied, and
the fitted coefficients are identical either way.**

**The narrowed guard was then positive-controlled**, because a guard that stops
firing is never caught. Run against B3's genuinely separated 30/30 arms it
**halts in all four sessions**, by non-convergence before any threshold is
consulted.

## F.5 The phase did not achieve its registered precision, and the reason is on the record

Realised §3.2 half-width **33.9 pp** against **19.6 pp** projected; implied
between-session sd **21.3 pp** against **12.3 pp** assumed, about **73% larger**.

**The 12.3 pp has been traced.** It is the binomial sampling sd of a *single*
session's paired difference — `100·√(2·p₀(1−p₀)/30)` at `p₀ = 53/150` — which
reproduces all five rows of the plan's table to within 0.1 pp. **It contains no
between-session variance component at all**, so the projection assumed the
sessions would differ only by binomial noise.

**The benchmark shares the defect, so this is not "the phase missed its
registered 17.3 pp".** The MDE column is pooled binomial across all k sessions at
per-arm n = 30k, reproducing 5 of 5 rows, with no between-session component
either — and pooling runs across sessions as independent draws is exactly what
`paper_tables.py:1894-1897` refuses in the code that generates the manuscript's
own interval. The commensurability argument that selected k = 4 has the missing
assumption on **both** sides: the two numbers met because they omitted the same
thing.

**The accurate statement is that between-session variance was absent from both
sides of the design's power argument.**

**And the sensitivity analysis could not have caught it.** §6 swept `p₀` across
its entire plausible range, held the variance assumption fixed throughout, and
concluded that `p₀` "is the one input that could have invalidated the
calculation". The input that invalidated it was the one never varied. The design
was robust to the parameter that did not matter — the same class as handover
finding 5's four instances, now in the design rather than in a check.

Observed over-dispersion is **2.99** against 9C's unblocked **5.37**. Blocking
worked; it did not reach the 1.0 both columns assumed. **Filed as B19.**

**Descriptive, post hoc, and not a power claim:** at the realised sd of 21.3 pp,
a 17.3 pp half-width needs **k ≈ 9** (k=4: 33.9, k=6: 22.4, k=8: 17.8, k=9:
16.4). The sd was not knowable in advance and this is not a target the phase
should have hit; it is recorded because a reviewer will ask and Phase 12 planning
needs a figure grounded in observation.

**k = 4 is not extended.** The plan states that if realised precision is worse it
is reported worse, and adding sessions after seeing results is optional stopping.

## F.6 The estimator was chosen after collection, and it determined the verdict

Plan §3.1 registered a 95% CI and **did not name a variance estimator**. That gap
was filled after collection, and the choice decided the outcome: the t(3)
interval contains zero (**CONFIRMS**) while the pooled fixed-effect Wald interval
`[+0.0173, +1.1291]` excludes it.

**Weaker than blind, stronger than post-hoc** — Amendment 3's own label, applied
here so the paper grades its decisions on one scale.

**And weaker than Amendment 3's original position.** When the 0.02 threshold was
set, sessions 3 and 4 did not exist in any form. When this estimator was chosen,
**all four sessions' outcome counts were visible** — 18/18, 15/18, 17/10, 23/12 —
which give the direction and approximate magnitude of the result. The fitted
coefficient added adjustment and precision; it is not the fact that was withheld,
and claiming otherwise would imply protection that does not exist.

**What protects the choice is not blindness but the absence of any free
parameter.** The construction — session as the unit, mean, t(k−1),
half-width `t·sd/√k` — predates collection: it is `paper_tables.py:1899-1901`,
which produced `[6.1, 28.4]`, and plan §3.2 already registers it. There was no
knob to turn, and the alternative was two inferential standards in one paper.

**The dual result is reported, not resolved.** The point estimates barely differ
(+0.583 vs +0.573); the disagreement is entirely about the standard error. The
pooled exclusion is marginal — lower bound **+0.017**, and a **3.11%** change in
one standard error would flip it. That standard error was cross-checked against a
numerically differentiated Hessian and agrees to between 5e-08 and 1.5e-06
relative, so the disagreement is a property of the two constructions rather than
of the arithmetic. **The t(3) verdict is not exposed to this**, being built from
the between-session sd rather than any model standard error.

## F.7 Foreign load: co-occurrence, and s1/s2 are unmeasured rather than clean

Foreign `komserv-pg-race` containers were **confirmed running inside both
sampled sessions** — three during s3, two during s4 — despite the per-session
precondition clearing the VM at t = 0. They arrived after the session started,
which is precisely the gap B12 names.

**The two sessions with confirmed foreign load, s3 and s4, are the +23.3 pp and
+36.7 pp sessions** — the two largest class effects.

**No causal claim, no adjustment, no exclusion.** Load is measured for 2 of 4
sessions; adjusting on it would make the four non-comparable and silently drop
half the design. **Sessions 1 and 2 have no series at all**, so their load is
**unmeasured, not absent** — the available comparison is not "load versus no
load" but **"load observed versus load not looked for"**. Two sessions against
two unmeasured ones is consistent with load mattering and equally consistent with
coincidence.

At 60 s sampling resolution the counts are **lower bounds**: both containers
observed in this phase were removed within four minutes, so an empty list is weak
evidence of quiet rather than proof of it.

## F.8 The four sessions are not uniformly instrumented

They must not be presented as though they were.

| | s1 | s2 | s3 | s4 |
|---|---|---|---|---|
| `SHA256SUMS` entries | 15 | 17 | 18 | 18 |
| container precondition | ✗ | ✓ | ✓ | ✓ |
| fault-injection census | ✗ | ✓ | ✓ | ✓ |
| foreign-load series | ✗ | ✗ | ✓ | ✓ |

Instrumentation was added *during* the phase. It touched no registered gate and
changed no collection condition, so it is additive observation — but the coverage
differs across the set and the artefacts record their own limits (**R5**).

**Uniform where it matters for pooling:** all four report `mount_type = volume`,
`is_drvfs = false`, ext4, device `/dev/sdf`, harness clean, and all four ran under
amendment 1's interleaved sort key. **k = 4 stands.**

## F.9 B3 controls for the barrier, not for the host

B3's arms are **30/30 AUTH and 28/30 NO_READBACK in all four sessions — zero
variance across 480 runs.**

**That is a structural consequence, not an observation about stability.**
`experiments/baselines/b3_no_barrier.py:79-88`: `confirm_durable` returns `True`
and issues **no command**. B3 has no barrier wait in its dispatch path, and the
quantity this phase perturbs is `docker kill` latency racing the acknowledgement.
**B3 has no acknowledgement to race.**

**Licensed:** B3 flat while AEP-full moves *locates the movement in the arm the
barrier governs*. That is a real statement and it does not depend on which way
the class difference points.

**Not licensed:** any claim that the host was stable, that timing conditions were
comparable across sessions, or that the instrument was healthy. **B3 would read
30/30 and 28/30 on a host that was on fire.** Wherever B3 is described as a
"control", it must be qualified — it controls for the barrier, not for the host.

**Separately informative:** the NO_READBACK arm is **28/30 in all four
sessions**, identical. Those two failures are not timing-driven.

## F.10 The fail-closed invariant held, confirmatorily

**131 applied AEP-full executions, 131 with `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_
PREFLIGHT` traversed, zero exceptions.**

**Confirmatory of code-enforced behaviour along a single code path, not a
discovered property** (`injector.py:351-356`). `_checkpoint` is awaited on the
protocol path so *dispatched ⇒ traversed* holds by construction, and
`DispatchAuthorizationError` already enforces the invariant in code. Zero
exceptions was near-certain, and what the check mostly exercises is the
observer's own fidelity. Its value is that the claim rests on 131 recorded
executions rather than on reading the source.

**One-directional.** `ack ⇒ applied` is not claimed and is not testable here.

## F.11 Session 2's collection conditions, carried forward

Session 2 was collected with foreign container load in the VM, established from a
status string captured at session 3's precondition and hashed into its artefact.
It is also the session with both non-landing kills, a −97.7 ms balance figure,
and a drift roughly three times session 1's.

**No registered stop condition fired and session 2 is not dropped.** Discovering
an unrecorded difference in a session's conditions after the fact is licence to
report it, not to remove it.

**Its balance failure's shape matters more than its size.** AEP-full and B3
disagree in *sign* within that session — −97.7 against +43.8 — and an ordering or
lag effect moves both arms the same way, because both are drawn from the same
drifting session. Four cells moving independently at seven times session 1's
scale is a timing environment, not a lag effect.

---

## What §F does not do

It does not re-run anything, does not adjust any estimate, does not drop any
session, and does not modify the pre-registration, any amendment, any macro or
any file under `paper/`. Every item above is a statement about what was observed
and under what conditions.
