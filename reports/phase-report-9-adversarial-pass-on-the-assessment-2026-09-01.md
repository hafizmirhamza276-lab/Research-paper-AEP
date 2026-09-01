# Adversarial pass on units 1 and 1b

**Unit 2.** Units 1 and 1b are sealed; this amends them rather than editing
them. Read as an opponent of their author, per the standing step added after B9
unit 3 found three defects of four in prose I had written one commit after
committing to remove exactly that pattern.

**Five amendments. Three weaken my own findings, one strengthens one, and one
guards against a misreading my own report invites.**

---

## A1 — B1 undercounted, and the fourth site is defensible

Unit 1 said `08-threats.tex:385` contradicts `08-threats.tex:96`. **It does, but
:385 is an accurate cross-reference.** It says *"as we say there"* and points at
`sec:eval-prevention`, which still contains:

> "Second, and for the same reason, *the effect size is a property of this
> host's `docker` latency.*"

So **four sites assert the mechanism as fact, not three.** The fourth is
`06-evaluation.tex:393`.

**And the fourth is defensible on its own terms.** It is the second of *"two
honest qualifications"* — a reason offered for *distrusting* the number, not for
believing it. **Asserting a limitation on thin evidence is conservative, not
overclaiming**, and the direction matters. It is the antecedent of the two
threats-section restatements, which convert a self-imposed caution into an
asserted finding.

**Net effect: B1 gets larger and its centre of gravity moves.** The problem is
not one contradicted sentence; it is a caution stated once and restated twice as
a result.

## A2 — B4 was dressed in more authority than it earns, and I tested the stronger reading and rejected it

Unit 1 filed the abstract's `p = 1.9 × 10⁻⁶` under *"F.0's binding in its
general form"*. **That is wrong and I should not have reached for it.**

F.0b binds *a failure to reject reported as indistinguishability*. **The
prevention result is a rejection.** F.0b does not apply.

I then tested the stronger reading — that this is a unit-of-analysis error, the
B20/B9 class. **It is not.** `\UnwantedP` is a Fisher on 10/30 against 28/30,
one execution per run, within one session. That is a legitimate run-level unit
for the question *"in this session, did the two arms differ?"*. It is not
execution-level pooling and the paper does not decline it anywhere.

**What survives is smaller and still real:** the abstract and `08-threats.tex:73`
answer a narrower question than the body answers about the same quantity, and
neither says so. A quantity measured five times is represented by one of its
five measurements in the two places a reader forms an impression. **That is a
representativeness gap, not a precision violation and not a unit error.** It
should be filed as what it is.

## A3 — "the only one of four" oversells its reference class

Unit 1b said prevention's is the only one of **four** session-clustered
intervals excluding zero. True, and the four are not four independent
quantities: the kill-latency pair is **one contrast measured on two arms**. The
honest count is **three distinct quantities**, of which prevention's is the one
that excludes zero.

The finding holds. Its rhetorical weight was inflated by a reference class I
did not examine before quoting its size.

## A4 — the misreading my own report invites, and the guard against it

**Unit 1 says B3 "was never a negative control". A careless reader of my own
report will conclude B3 is discredited. It is not, and the distinction is
load-bearing.**

| B3's role | status |
|---|---|
| **negative control for the kill-latency contrast** | **invalid** — same pooled construction, and at the session level its interval is 2.61× its own mean |
| **ablation arm for detection** | **valid and untouched** — 540 executions, both zero-event columns identical |
| **comparison arm for prevention** | **valid and untouched** — 28/30 against 10/30, and B3's count did not move by a single execution across all five sessions |

**The causal attribution of prevention to the barrier is by design, not by the
race mechanism**: B3 differs from AEP-full in the barrier and nothing else. That
argument never used the kill-latency data and does not weaken with it.

**This amendment exists because my own unit 1 made the misreading available.**

## A5 — "twelve claims" implies a completeness the method does not have

Unit 1 reports *"twelve claims adjudicated: 7 / 4 / 1"*. The sweep found **137**
sentences with evidential force and no macro. **The twelve are a selection — the
claims that carry the paper's argument — not a partition of the 137.**

"7 of 12 supported at stated strength" reads as a coverage statistic. It is
not. **The correct statement is that twelve load-bearing claims were adjudicated
and seven hold at their stated strength; the remaining 125 swept sentences were
read and none produced a further finding, which is a weaker guarantee than an
exhaustive audit and should not be quoted as one.**

---

## What did not change

- **The central result stands.** Nothing in this pass touched chain 1, the
  4.77% bound, the baseline contrast, or the detection claim in the abstract.
- **Chain 2 is still broken and still does not propagate.** A4 strengthens that
  conclusion rather than weakening it: the attribution of prevention to the
  barrier is a design argument.
- **B2 and B3 stand as filed.** *"Can now show"* and the *"therefore"* chain are
  unamended.
- **1b §3b stands**, with A2's recharacterisation applied to it as well: three
  sites, one adjacent to the replication, and the mechanism is F.0b's
  restatement pattern operating on a number that was never withdrawn.

## What this pass says about the standing step

**Three of five amendments weakened findings I had written.** The one-commit
gap between B9 unit 2 and unit 3's defect showed the author is the weakest
enforcer of their own rule; this pass shows the same for the author's own
findings, at a similar rate.

**It is mitigation and not a solution.** A2 in particular — reaching for F.0's
authority for a defect F.0 does not cover — is a failure I would not expect to
catch reliably in my own work, and I caught it here only because the pass was
scheduled rather than optional.
