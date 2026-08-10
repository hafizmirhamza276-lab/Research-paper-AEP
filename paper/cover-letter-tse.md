# Cover letter — IEEE Transactions on Software Engineering

**Manuscript:** *Declared Ambiguity: The Agent Execution Protocol (AEP) for
Autonomous Agents Calling Non-Idempotent Legacy APIs*

**Type:** Regular paper

---

Dear Editor-in-Chief,

We submit *Declared Ambiguity: The Agent Execution Protocol (AEP) for Autonomous
Agents Calling Non-Idempotent Legacy APIs* for consideration as a regular paper
in IEEE Transactions on Software Engineering.

## The problem, and why it is a software-engineering problem

Autonomous agents are increasingly pointed at enterprise APIs that were written
long before agents existed. Those APIs are non-idempotent, accept no idempotency
key, and — the property that does the real damage — often cannot be asked
afterwards whether a mutation was applied. Every durable-execution engine,
workflow system and message broker in current use achieves its guarantee by
requiring exactly what these endpoints will not provide: idempotence, a
deduplication key, or enrolment in a shared transaction.

When an agent crashes around such a call, the engineering choice is not between
a correct and an incorrect design. It is a three-way trade, and every system
must pick a corner: re-send and risk a duplicate real-world effect nobody
observes; decline to re-send and risk an effect that exists while the records
deny it; or decline to decide, record that fact durably, and stop. We argue the
third corner is the one a protocol should be engineered to reach, and that the
quantity a system should be judged on is not whether it avoids ambiguity —
against an endpoint that cannot be queried, that is impossible — but whether its
residual uncertainty is *declared and bounded* rather than *silent and
unbounded*.

## Contributions

1. **The declared-ambiguity formulation.** The problem stated as a three-way
   trade rather than a pursuit of exactly-once, with three properties — fenced
   state, detectable ambiguity, a fail-closed liveness bound — each mapped to
   the code path that enforces it and each with its residual window declared
   rather than assumed away.
2. **A protocol and an implementation** in which a durably acknowledged
   write-ahead intent is a *checked precondition* of dispatch authority rather
   than a matter of call ordering: the fsync acknowledgement mints an
   unforgeable, single-use, scope-bound token, and the pre-dispatch script
   refuses to proceed without it.
3. **An evaluation under real process kills** across six named crash points,
   three endpoint reconciliation capabilities and three collected fault regimes,
   against five baseline designs, one of them in two configurations. AEP records
   no undetected duplicate and no lost effect in any cell measured; the
   baselines without a pre-dispatch record duplicate in most crashed executions.
4. **A decomposition, by ablation, that reassigns our own headline result.** The
   write-ahead pattern is normally presented as one mechanism delivering one
   guarantee. It is two. The durable pre-dispatch record produces *detection*,
   and it does so *without* the durability barrier. The barrier buys something
   else — *prevention* — which is invisible to the crash faults that dominate
   this literature. Detection is nearly free; prevention is where the fsync cost
   lives; an operator can buy the first without the second.

## Fit with TSE

The paper is a reliability-engineering contribution: a protocol, an
implementation, and a fault-injection evaluation whose primary instrument is an
ablation. Its centre of gravity is empirical software engineering rather than
distributed-systems theory — we take the underlying impossibility as given and
ask what a system should do about it, which is an engineering question about
observable behaviour under injected faults. TSE's artifact culture is also
material to us: the paper's claims are machine-checked against their evidence on
every push, and we would rather be reviewed somewhere that treats that as
load-bearing than somewhere it is decoration.

We considered TPDS, and judge the fit weaker: the coordination mechanisms are
deliberately not novel — every primitive AEP uses is decades old — and the
contribution is the semantics they are composed to deliver, together with the
ablation that says which half of the composition delivers which half of the
semantics.

## What we are explicit about not claiming

We claim no exactly-once external execution, no prevention of a duplicate the
provider has already accepted, no high availability, consensus or split-brain
immunity, and no durability beyond one local AOF fsync. The system is a single
Redis trust domain and the measurements are single-node. These appear as a table
of non-claims in the manuscript, not as buried caveats.

Two further disclosures we would rather make here than have a reviewer find:

- The ablation that establishes our detection result is *internal by
  construction*. It attributes an effect to a mechanism, which is what we wanted
  it for, but nothing outside this artifact corroborates the resulting claim. We
  say so in Threats to Validity.
- The barrier's durability benefit **cannot be exercised by any process-level
  fault**, because `appendfsync everysec` defers the `fsync(2)` and not the
  `write(2)`. We discovered this by testing a premise we had expected to
  confirm, it refuted half of it, and the paper now names the fault class the
  claim actually holds against and tests it directly with a block-level
  write-loss probe.

## Prior publication

This manuscript has not been published previously and is not under consideration
at any other journal or conference. No part of it has appeared in a workshop,
conference, or symposium proceedings.

We intend to post the manuscript as a preprint to arXiv (primary cs.SE,
secondary cs.DC) at or around the time of submission, under IEEE's policy
permitting author-posted preprints. Should the paper be accepted we will update
the preprint with the DOI and the required IEEE copyright notice. No other
version exists or is planned.

## Artifact availability

The implementation, the evaluation harness, the mock provider, all baseline
systems, the analysis pipeline, the frozen results and the manuscript source are
in one repository, released at tag **`v1.0.0-rc1`**.

`ARTIFACT.md` at the repository root is the entry point. It carries a
claims-to-evidence map in which every quantitative claim in the paper resolves,
in one hop, to the exact command and CSV cell that produces it — the map is
enumerable because every number in the manuscript is a generated macro whose
provenance comment names its file, its filter and its arithmetic. It also states
hardware and software requirements, estimated runtimes, and how to verify the
frozen archive against its manifest of SHA-256 hashes.

Two unattended entry points are provided:

- `make reproduce-smoke` — provisions Redis from the compose file the
  experiments use, runs one representative cell per system end to end with real
  `SIGKILL`, and prints the resulting metric rows. This is a liveness check on
  the harness, and we label it as one: two executions per cell cannot estimate a
  rate.
- `make reproduce-figures` — regenerates every table and macro file in the paper
  from the frozen results and byte-compares them against what is committed.

Continuous integration runs the full test suite against a real Redis provisioned
from the same compose file, fails if any test is skipped, and — on every push —
rebuilds the manuscript and re-derives every number in it from the frozen CSVs.
A number that drifts from its source turns the build red.

We would be glad to answer any questions during review.

Sincerely,

The authors
