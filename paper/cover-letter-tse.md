# Cover letter — IEEE Transactions on Software Engineering

**Manuscript:** *Declared Ambiguity: Fail-Closed Execution for Non-Idempotent
Legacy APIs Without Idempotency Keys*

**Type:** Regular paper

**Length:** 24 pages in the IEEE Computer Society two-column format, plus a
7-page supplementary document submitted separately as supplemental material.

---

Dear Editor-in-Chief,

We submit *Declared Ambiguity: Fail-Closed Execution for Non-Idempotent Legacy
APIs Without Idempotency Keys* for consideration as a regular paper
in IEEE Transactions on Software Engineering.

## The problem, and why it is a software-engineering problem

Autonomous agents are increasingly pointed at enterprise APIs that were written
long before agents existed, and they are the setting in which this problem is
now most visible. But the problem belongs to the endpoint, not to the caller:
any caller that can fail mid-call inherits it — a workflow engine, a retrying
batch job, a human operator with a script. We use agents as the motivating
example throughout and evaluate a scripted caller, which the paper says in §II
rather than leaving a reader to infer.

Those APIs are non-idempotent, accept no idempotency
key, and — the property that does the real damage — often cannot be asked
afterwards whether a mutation was applied. Every durable-execution engine,
workflow system and message broker in current use achieves its guarantee by
requiring exactly what these endpoints will not provide: idempotence, a
deduplication key, or enrolment in a shared transaction.

When a caller crashes around such a call, the engineering choice is not between
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
   than a matter of call ordering: under a trusted-code assumption, the fsync
   acknowledgement returns an opaque, non-copyable, single-use, scope-bound
   in-process dispatch guard; the guard is consumed to write a Redis-visible
   authorization, and the pre-dispatch script refuses to proceed without it.
   This is a control-flow invariant of the supported API, not a cryptographic
   capability and not a boundary against arbitrary code in the same Python
   process.
3. **An evaluation under real process kills** across six named crash points,
   three endpoint reconciliation capabilities and five reported fault regimes —
   every execution crashed, none crashed, Redis hard-killed before the
   acknowledgement, Redis killed after dispatch, and storage discarding writes
   while reporting success — against five baseline designs, one of them in two
   configurations. AEP records
   no undetected duplicate and no lost effect in any cell measured; the
   baselines without a pre-dispatch record duplicate in most crashed executions.
   AEP's residual is declared ambiguity whose rate is a function of what the
   endpoint can be asked.
4. **A decomposition, by ablation, that reassigns our own headline result.** The
   write-ahead pattern is normally presented as one mechanism delivering one
   guarantee. It is two. The pre-dispatch record plus no re-entry produces
   *detection*,
   and it does so *without* the durability barrier: ablating the barrier
   produces no observed difference in the crashed-regime detection metrics. The
   barrier buys something
   else — *prevention* — which is invisible to the crash faults that dominate
   this literature and large under the fault that targets Redis. The measured
   prevention evidence is three sessions covering all three capability classes,
   at one pre-acknowledgement Redis-kill point on one host.
   Detection is nearly free in this workload; prevention is where the fsync
   cost lives, and an operator can buy the first without the second.

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
immunity, no durability beyond one local AOF fsync, and no verified
implementation — the properties are model-checked, the Python is not, and
refinement from the specification to the code is neither proven nor claimed.
The system is a single
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
- **That block-level test then refuted its own pre-registered prediction, and
  we report it as a refutation rather than a caveat.** We predicted AEP would
  withhold dispatch when its write-ahead record was destroyed and that the
  ablation would proceed. Neither withheld: `dm-flakey`'s `drop_writes`
  discards each write and reports success, so `WAITAOF` returned a successful
  acknowledgement after the device had stopped accepting writes, and the
  barrier dispatched on an input that was false. The finding is about storage
  rather than about the protocol — it bounds the durability guarantee to
  storage that reports its own failures — and it is in the results section, not
  in Threats to Validity.

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

The repository contains the implementation, evaluation harness, mock provider,
baseline systems, analysis pipeline, manuscript source, and tracked derived
analysis products. It deliberately does not contain the raw run directories,
which are bulk data: those are carried by a separate evidence archive, built
and verified in two parts, each covered by its own SHA-256 manifest and each
extracted and checked file-by-file before deposit.

**One availability caveat we state rather than imply.** The archive is
deposited into a Zenodo record whose DOI is **reserved but not yet resolving**,
because the record is still a draft; the manuscript renders that state from a
single source rather than asserting availability it does not have. Publishing
the record and creating the immutable release tag are the remaining
pre-submission steps, and we will not submit until the DOI resolves.

`ARTIFACT.md` at the repository root is the entry point. It carries a
claims-to-evidence map in which every quantitative claim in the paper resolves,
in one hop, to the exact command and CSV cell that produces it — the map is
enumerable because every number in the manuscript is a generated macro whose
provenance comment names its file, its filter and its arithmetic. It also states
hardware and software requirements, estimated runtimes, the currently verifiable
tracked subset, and the integration steps for a future immutable raw archive.

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

---

<!-- Everything below the rule is NOT part of the letter. Do not paste it. -->

## Provenance of every number above — not part of the letter

Kept here because this file is hand-pasted and therefore cannot be checked by
`scripts/check_paper_numbers.py` the way the manuscript is. Each entry names
what the number is and where it comes from, so the next person to revise the
letter can verify it in one hop instead of trusting it.

| number | where it appears | source |
|---|---|---|
| **24 pages**, **7 pages** | Length line | `pdfinfo paper/main.pdf` and `paper/supplementary.pdf` after `bash scripts/build_paper.sh`. Not a generated macro — a property of the build, so re-measure after any layout change |
| **six** named crash points | C3 | `\cref{tab:crashpoints}`; §VI-A *Faults* states the same six |
| **three** endpoint reconciliation capabilities | C3 | §VI-A; the three classes named in `tab:outcomes` |
| **five** reported fault regimes | C3 | §I C3 enumerates the same five, with a provenance comment naming each collection root. **This said "three" until 2026-09-22**, matching the matrix root's three and excluding the two regimes §VI-C.2.5 and §VI-C.4 report |
| **five** baseline designs, one in two configurations | C3 | `\cref{tab:trilemma}` — seven systems, of which AEP-full and the five baselines, B4 in two configurations |
| **three** sessions, **all three** capability classes | C4 | `\ArmASessions{}` = 3 and `\ArmAClasses{}` = 3 in `paper/generated/numbers.tex`; §VI-C.2 leads with them. **This said "one no-readback capability class" until 2026-09-22** |
| **one** pre-acknowledgement Redis-kill point, **one** host | C4 | §VI-C.2, *"The scope of the cell is one pre-acknowledgement crash point and one host"* |

No other digit in the letter is an evidence number: `fsync(2)` and `write(2)`
are section numbers of the man pages, `SHA-256` is an algorithm name, and the
rest are list markers. The raw-archive figures that used to appear here — a
run-directory count that did not describe the archive it was attached to — were
removed rather than corrected, because the letter does not need them and §IX
states them once, from their own source.
