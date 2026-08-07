## F. The draft read as a hostile TSE reviewer

What follows is the review I would write if this manuscript were assigned to me
and I wanted to reject it. Ordered by how much damage each objection does.

### F1. "Your headline result does not need your headline mechanism."

This is the strongest attack and the paper only partly answers it.

AEP-full and B3 are **identical** on RQ1: both record zero undetected
duplicates and both declare ambiguity. B3 is AEP-full with the durability
barrier removed. So the paper's central claim — silent failure becomes declared
ambiguity — is delivered entirely by the write-ahead intent, the fenced CAS and
the recovery classifier, and **not at all** by the mechanism the paper spends
its most novel design effort on (the ack → authorization → preflight chain).

The paper's answer is §6.2: the barrier's contribution is visible only under
infrastructure faults, where it is large ($p=1.9\times10^{-6}$). That is a
real answer. But a reviewer is entitled to say: *then the contribution is a
write-ahead intent ledger with fail-closed classification, which is
architecturally unsurprising, plus one dispatch gate whose benefit shows up in
one 60-run experiment on one fault.* The paper does not currently pre-empt
that framing, and it should — either by arguing that the fail-closed
composition is itself the contribution, or by strengthening the barrier
evidence.

**Severity: high. Not fixable by writing; needs either a reframing or more
faults.**

### F2. "Your comparison is against baselines you wrote, on a mock you wrote."

Every system in Table 1 is the authors' code. The oracle is the authors'
service. `B4_SEMANTICS.md` defends B4's re-execution policy against Temporal's
documentation, which is the right move and is more than most papers do — but it
defends *one* modelling decision. Nothing defends B0's retry predicate, B1's
lease parameters, or the provider's 15% timeout rate, each of which moves the
duplicate rates.

The paper now names this in threats. Naming is not answering. The answer a
reviewer wants is at least one measurement against a real system — an actual
Temporal worker against the same mock provider would be a few days of work and
would convert the strongest fairness objection into a data point.

**Severity: high. Addressable.**

### F3. "The evaluation is one machine, one endpoint shape, and n=3 for every
timing number."

Three crash-free runs per system. One endpoint for all of RQ3. WSL2 with
Docker Desktop port forwarding in the latency path. No multi-node anything. The
paper is candid about all of it, and candour does not widen a confidence
interval. For TSE the timing story is thin enough that a reviewer could
reasonably ask for it to be either strengthened or demoted to a
micro-benchmark appendix.

**Severity: medium. Cheap to fix for the timing numbers (more p0 runs are
minutes each); expensive for the platform.**

### F4. "You measure that AEP declares ambiguity. You do not show that
declaring helps."

The paper's normative core — a declared incident beats an undiscovered one — is
asserted, not evidenced. There is no operator study, no incident-resolution
data, no evidence that a queue of declared ambiguities stays bounded or gets
worked. On a `NO_READBACK` endpoint the declared-ambiguity rate is high enough
that a reviewer can fairly ask whether the system is usable at that rate. The
draft now owns this in §6.1 and threats, which is the right move, but the
objection stands and cannot be closed with the current apparatus.

**Severity: medium-high for a *software engineering* venue specifically, which
cares about whether practitioners can use the thing.**

### F5. "Your motivating study is not a study."

§2 replays four traces from the authors' own harness. `PAPER_ROADMAP.md` §5
asked for "3 concrete failure traces from B0 reproduced by your harness", so the
section does what was specified — but the section title promises more than
harness output delivers, and there is no evidence about how often real agent
deployments meet non-idempotent endpoints without idempotency keys. The premise
of the entire paper is currently supported by argument alone.

**Severity: medium. A survey of a dozen real enterprise APIs' idempotency
support would close it cheaply and would strengthen the introduction more than
anything else available.**

### F6. "The barrier's durability benefit is unmeasured, and you say so, and
then you keep the barrier."

A reviewer who reads §6.2.1 carefully will notice the paper proves that
`appendonly yes` alone survives every fault it injected, and that the barrier
costs ~1 967 ms per step — three orders of magnitude more than the rest of the
protocol. The paper's justification for keeping it is (a) the dispatch-gate
benefit and (b) an argument about host-level faults it did not inject. A
reviewer may reasonably say: *you have shown the barrier costs 98% of your
latency and defends against a fault you did not test.* The `appendfsync always`
comparison helps by showing the cost is configurable, but it does not supply
the missing fault.

**Severity: medium. §G1 of the predecessor report is the same question and it
is still open.**

### F7. Smaller things a reviewer would list without much comment

1. **Eleven-to-twelve pages is short for TSE.** Not a defect, but it signals a
   thin evaluation to a reviewer skimming.
2. **`\todo` markers remain** where completion cells could move a value. Honest
   in a draft; must be zero at submission.
3. **RQ4 reports almost nothing.** Recovery latency is withheld because the E5
   gate leaves too few gated crashed runs. That is the right call and it leaves
   an RQ with no numbers, which reads badly. Either collect gated crashed runs
   or fold RQ4 into RQ1.
4. **The known-ambiguity rate at `after_barrier_before_dispatch` is 30/30 under
   both non-authoritative capabilities** — the crash point where *no effect can
   exist*. The paper presents this as conservatism, correctly. A reviewer will
   still note that a protocol which could observe "the dispatch authorization
   was never consumed" could in principle resolve some of these to a confirmed
   non-event, and will ask why it does not. **That is a good question and the
   paper does not currently answer it.**
5. **`AEP` is not defined as an acronym anywhere in the draft.**
6. **No related-work comparison table.** Reviewers in this area expect one.
7. **The Wilson interval in the figures differs from the bootstrap interval in
   the CSVs.** Documented in code, not in the paper; a reader comparing the two
   would be briefly confused.

### F8. What the draft does well enough that I would not attack it

For balance, and because these were the expensive parts:

- Every number traces to a CSV cell, and a script fails the build on drift.
- The negative result in §6.2.1 is stated by the authors before a reviewer
  could find it, with the mechanism explained and the claim narrowed.
- The non-claims table and the declared residual windows are unusually
  complete, and the residuals are probe-confirmed rather than asserted.
- Regimes are never pooled, and the paper explains why the pooled table its own
  tool emits is not quotable.
- The bibliography is verified by resolution, and the one fabricated DOI that
  entered the file was caught by that check rather than by a reader.
