# The argument, not the sentences — unit 1b

**Unit 1 matched every sentence to its own evidence. It could not match
sentences to each other.** A paper can pass sentence-by-sentence and still have
an argument that no longer connects, because the paper does not only *report*
results — it *explains* them, and an explanation is a chain across sentences.

**Sealed with unit 1**; the recommendation is written after both.

---

## 1. The five places the paper explains rather than reports

| # | explanation | what carries it now | status |
|---|---|---|---|
| 1 | **Detection comes from the pre-dispatch record and the missing re-entry edge, not from the barrier** | The B3 ablation (barrier removed, both zero-event columns unchanged, bound 4.77%) **and** the B4 contrast (durable record, acknowledged by the same barrier, duplicates at the study's highest rate) | **intact** |
| 2 | **The prevention effect size varies because it is a race** | one unreplicated session at +88 ms, p = 0.03; a four-session interval [−91, +302] containing zero | **broken** |
| 3 | **A process kill cannot test durability because `appendfsync everysec` defers the `fsync(2)` and not the `write(2)`** | Redis's documented semantics **plus** two probes that disagree as predicted: 0/10 lost under process kill, 30/30 lost in each write-loss replication | **intact** |
| 4 | **Detection is nearly free and prevention is where the fsync cost lives, so an operator can buy one without the other** | chain 1, plus the latency decomposition — protocol-minus-barrier 28.0 ms against a barrier cost of 1966.7 ms | **intact** |
| 5 | **Declared ambiguity's rate is set by what the endpoint can be asked** | per-class rates 0.00 / 0.35 / 0.72, and the design reason absence is provable only under AUTH | **intact** |

**Four of five chains are intact and none of them touches anything this phase
withdrew.** Chain 3 is worth naming explicitly: it is a *mechanistic* argument
resting on documented `fsync` semantics and two probes that were designed to
disagree, and it never depended on a p-value in the first place.

---

## 2. The load-bearing question: does the broken chain propagate?

**No. This is the assessment's most important negative result and it is stated
first so it cannot be buried under the findings that follow.**

Chain 2 explains **why the prevention number varies between hosts and
sessions**. It does not carry **whether the barrier prevents**. Those are
different claims with different evidence:

| claim | evidence | interval |
|---|---|---|
| *the barrier withholds effects B3 commits* | 4 pre-registered sessions, 30 runs per arm each, session as the unit | **[6.1, 28.4] effects — excludes zero** |
| *the magnitude is set by kill latency* | chain 2 | **[−91, +302] ms — contains zero** |

The deployment recommendation — *"if losing Redis is the fault to worry about,
the barrier is the point of the protocol"* — rests on the first row. **A reader
following the argument from the abstract to the operator recommendation passes
through chain 1 and chain 4 and never needs chain 2.** They are not misled.

**Chain 2's collapse costs the paper an explanation, not a result.**

---

## 3. Two defects that only appear when sentences are matched to each other

### 3a. The paper's self-criticism is now misdirected, and it under-claims

`08-threats.tex:83-88`:

> "…our most novel mechanism serves the claim with the **weakest** evidence —
> one capability class, one crash point, and an effect size we can now show is
> host-dependent…"

**On scope this is still exactly right** and should not be softened: the
prevention cell is one capability class, one crash point, one host, and the four
replications are all the same cell.

**On strength within that scope it is now wrong in the paper's own disfavour.**
The manuscript contains **four session-clustered intervals**:

| quantity | interval | zero? |
|---|---|---|
| **effects prevented** | **[6.1, 28.4]** | **excluded** |
| capability-class effect | [−21.4, +46.4] pp | contains |
| kill-latency contrast | [−91, +302] ms | contains |
| kill-latency, B3 arm | [−166, +74] ms | contains |

**The prevention result is the only one of the four that excludes zero.** It is
the paper's best-replicated inferential claim, and the sentence calling its
evidence the weakest is in the same paragraph as B2's overstatement of the
mechanism. **Under-claim and over-claim, adjacent, in the paragraph the paper
wrote to be hard on itself.**

That is not an argument for softening the self-criticism. It is a finding that
the self-criticism now attaches to the wrong half: the scope is narrow, the
*replication within that scope* is the strongest in the paper, and the *thing
that is actually weakly evidenced* is the explanation — which the same paragraph
asserts rather than doubts.

### 3b. The prevention claim is carried in three places by a single session's p, and only one of them is adjacent to the replication

`\UnwantedP` = 1.9 × 10⁻⁶ is a **within-session Fisher on one cell of 30 runs
per arm**. It appears three times:

| site | what follows it |
|---|---|
| `main.tex` — abstract | nothing. Three scope qualifiers, no precision |
| `08-threats.tex:73` — **bold** | nothing. *"under a process fault the barrier's contribution is prevention (§eval-prevention, p = 1.9 × 10⁻⁶)"* |
| `06-evaluation.tex` | **the replication, immediately** — 5 measurements, range 4–20, mean 17.2, interval [6.1, 28.4] |

**A reader who reads the abstract, or who reads the threats section, receives a
single session's p-value and never learns the quantity was measured four more
times.** Only the one reader who reaches `sec:eval-prevention` gets the
replicated version.

**This is F.0b's restatement mechanism applied to a number that was never
withdrawn**, which is the part worth recording: the careful statement is made
once with its interval, and the two restatements keep the conclusion and drop
the qualification because neither passage is *about* precision. **F.0b does not
require a withdrawal. It only requires a restatement.** Every existing check
passes all three sites, because the number is correct at all three.

---

## 4. What unit 1 could not have found

Unit 1's four bucket-B items are each a sentence that overstates its own
support. **Both defects in §3 are different in kind:**

- **3a** is a sentence that *understates* its own support, which no
  overstatement audit looks for.
- **3b** is three sentences that are each individually correct — the p is real,
  the test is right, the number is right — and that mislead collectively because
  of what follows two of them and not the third.

**Neither is reachable by matching sentences to their own evidence, which is
what unit 1, `check_paper_numbers.py`, the orphan gate and the F.0b lexicon
check all do.** The addition that produced this unit was correct, and it found
what the sentence-level pass structurally could not.

---

## 5. Summary

**Four of five explanatory chains are intact. The broken one explains the
variance of a result, not the result, and it does not propagate to any
recommendation the paper makes.**

Two argument-level defects, neither visible sentence by sentence:

1. The self-criticism attaches to the scope of the prevention claim while
   under-stating that within that scope it is the paper's only session-clustered
   interval excluding zero — in the same paragraph that overstates the
   mechanism.
2. The prevention claim is carried by a single session's p in the abstract and
   in the threats section, with the four-session replication adjacent to it in
   only one of its three sites.

**Both are wording changes. Neither requires new evidence, and neither touches
the central result.**
