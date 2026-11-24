# B4 semantics: what it models, what it does not, and why it is not a strawman

**Amendment E4 (the fairness lock).** B4 is the baseline that carries the most
rhetorical weight in this paper: it is the one that has a durable,
`WAITAOF`-acknowledged write-ahead record *and duplicates anyway*. In the
Session 3 tier-1 slice it recorded an undetected-duplicate rate of **0.95**
against AEP-full's 0.0000. A number that shape, against a baseline this author
also wrote, is worth nothing unless the baseline's re-execution policy is the
documented default of a real production system rather than a choice made to
produce the number.

This document is the citation. It states which production system B4 models,
quotes that system's own documentation for the behaviour under test, and
enumerates the knobs B4 does and does not implement. Amendment E4 forbids any
further B4 cell from running until it exists.

---

## 1. The system B4 models

**Temporal** (temporal.io), the durable-execution engine `PAPER_ROADMAP.md`
§3.3 names when it defines B4 as *"a minimal Temporal-like event-sourced
re-execution baseline"*.

> **Quotation provenance.** Every quotation below was retrieved from the live
> Temporal documentation on **2026-08-06** by automated fetch. URLs are given so
> that each can be re-verified; anyone preparing the paper for submission should
> re-read them against the live pages, because vendor documentation is a moving
> target and a quotation that has drifted is worse than no quotation.

---

## 2. The behaviour under test: a scheduled-but-uncompleted activity

The crash B4 is measured under leaves exactly one shape of history:
`activity_scheduled` is durably recorded, `activity_completed` is not, and the
worker that was executing it no longer exists. Everything in this paper's
comparison turns on what the engine does next.

### 2.1 The engine cannot see the crash; it infers it from a timeout

From [Detecting Activity failures](https://docs.temporal.io/encyclopedia/detecting-activity-failures):

> "The main use case for the Start-To-Close timeout is to detect when a Worker
> crashes after it has started executing an Activity Task."

> "The Temporal Server doesn't detect failures when a Worker loses
> communication with the Server or crashes. Therefore, the Temporal Server
> relies on the Start-To-Close Timeout to force Activity retries."

### 2.2 On that timeout, the default is to run the activity again

Same page:

> "An `ActivityTaskTimedOut` Event is written to the Workflow Execution's
> mutable state. If a Retry Policy dictates a retry, the Temporal Service
> schedules another Activity Task."

Whether the Retry Policy "dictates a retry" is settled by its defaults. From
[Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies), the
default Activity Retry Policy is:

| Field | Documented default |
|---|---|
| Initial Interval | 1 second |
| Backoff Coefficient | 2.0 |
| **Maximum Attempts** | **unlimited** ("Setting the value to 0 also means unlimited.") |

**This is the load-bearing citation.** With Maximum Attempts unlimited by
default, a Start-To-Close timeout caused by a worker crash *does* dictate a
retry, and the engine schedules another Activity Task for an activity that may
already have applied its effect. That is B4's behaviour, and it is the vendor's
default, not this author's choice.

### 2.3 The vendor states the consequence explicitly

From [Activity definition](https://docs.temporal.io/activity-definition), the
Idempotency section:

> "You should always make your business logic Activities idempotent in Temporal.
> Because Activities may be retried, these functions may be executed more than
> once."

> "An Activity is idempotent if multiple Activity Task Executions do not change
> the state of the system beyond the first Activity Task Execution."

and from [Activities](https://docs.temporal.io/activities), of the Activity
Definition: *"We recommend that it be idempotent."*

The documentation also describes precisely the window this paper's workload
lives in: a worker may complete an activity successfully but crash before
notifying the service, the Event History then shows no completion, and a retry
is triggered.

**So the vendor's position is not that duplicates do not happen. It is that
duplicates are the caller's problem, to be solved by making the activity
idempotent.** The entire premise of this paper is the case where the caller
*cannot* do that, because the legacy endpoint is non-idempotent and offers no
idempotency key. B4 is that engine meeting that endpoint. It is not a
misconfiguration of Temporal; it is Temporal's documented contract applied
outside the precondition the contract assumes.

---

## 3. What B4 implements, knob by knob

`experiments/baselines/b4_durable_workflow.py` is a *minimal* engine. This table
is the fairness statement: it says what is modelled, what is stubbed, and what
is absent, so that no reader has to infer any of it from the code.

| Mechanism | In B4? | Note |
|---|---|---|
| Durable append-only event history | **Yes** | Redis list, one per execution |
| History append acknowledged durable before proceeding | **Yes** | the *same* `WAITAOF` barrier AEP-full uses — B4 is **not** ablated on durability |
| Replay from history; memoised completion is not re-run | **Yes** | a recorded `activity_completed` returns its recorded result and sends no bytes |
| Re-execution of a scheduled-but-uncompleted activity | **Yes** | the behaviour cited in §2.2 — B4's default |
| Retry Policy: Maximum Attempts unlimited (vendor default) | **Yes** | modelled as "always re-run on replay"; the run's own `max_dispatch_attempts` bounds in-process retries |
| Retry Policy: Maximum Attempts = 1 (at-most-once) | **Yes, as B4b** | see §4 |
| Activity idempotency (the vendor's recommended mitigation) | **No — deliberately** | the workload is a non-idempotent legacy mutation with no idempotency key. Modelling it would delete the experiment. §5. |
| Initial Interval / Backoff Coefficient / jitter | **No** | retry *timing* is not under test; retry *policy* is |
| Heartbeating and heartbeat timeouts | **No** | §5 |
| Timers, signals, queries, child workflows, continue-as-new | **No** | not on the path under test |
| Task queues, worker pools, sticky execution | **No** | one worker slot per execution |
| Workflow versioning / patching, determinism checking | **No** | one activity, one version |
| Server-side visibility, archival, multi-cluster replication | **No** | not on the path under test |

**What this scope buys and what it costs.** B4 reproduces exactly one
mechanism — durable history plus replay plus at-least-once activity
re-execution — and nothing else. It supports a claim about *event-sourced
re-execution as a strategy*. It does **not** support any claim about Temporal's
throughput, latency, operational maturity or correctness as a product, and no
such claim is made anywhere in this paper.

---

## 4. B4b: the standard configuration that avoids the duplicate

Amendment E4: *"If a standard configuration would avoid the duplicate,
implement it as B4b and run both."* One does, and it is documented, so it is
implemented and both are run.

From [Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies):

> "Setting the value to 1 means a single execution attempt and no retries."

**B4b is B4 with Maximum Attempts = 1.** On replay, a history holding
`activity_scheduled` with no `activity_completed` is *not* re-dispatched. The
attempt budget is spent, the activity is recorded as timed out, and the failure
propagates.

**What B4b trades.** It cannot produce a caller-caused duplicate — its
duplicate rate should be 0 by construction, and if it is not, the harness has a
defect. What it produces instead is a **lost effect**: where the provider did
apply the mutation before the worker died, B4b records a failure over an effect
that exists, and — this is the part that matters — it does not escalate. The
`activity_timed_out` record is an ordinary workflow failure, not a declared
ambiguity, so nothing in B4b tells an operator that a real-world effect may be
unaccounted for.

**This is the honest shape of the comparison, and it is why running B4b makes
the paper stronger rather than weaker.** The three-way result the evaluation
should report is:

| | caller-caused duplicate | lost effect | ambiguity declared to an operator |
|---|---|---|---|
| B4 (Max Attempts unlimited — vendor default) | **yes** | no | no |
| B4b (Max Attempts = 1 — documented at-most-once) | no | **yes** | **no** |
| AEP-full | no | no | **yes**, bounded and measured |

A durable-execution engine can pick either end of the duplicate/loss trade by
configuration. What neither configuration can do is *know which one happened*,
because the fact it would need — whether the provider applied the effect — is
not in its history and cannot be put there by any amount of logging. That, and
not the 0.95, is the claim B4 exists to support.

---

## 5. Two things B4 does not model, and the argument that it need not

**Activity idempotency.** The vendor's recommended mitigation (§2.3) is to make
the activity idempotent. B4 does not, because the paper's premise is a
non-idempotent legacy endpoint with no idempotency key — the case
`PAPER_ROADMAP.md` §1 defines. Modelling idempotency here would not make the
comparison fairer; it would replace the problem with a different one in which
no system under test can fail. Where a caller *can* make the effect idempotent,
it should, and AEP is not needed. That precondition is stated in the paper's
threats-to-validity, not hidden here.

**Heartbeating.** Temporal's Heartbeat Timeout detects a dead worker faster
than Start-To-Close. It changes *how quickly* the retry is scheduled; it does
not change *whether* one is. Since B4's measured quantity is the duplicate, not
the detection latency, omitting heartbeats does not bias the duplicate rate.
It does mean **no B4 latency number in this paper should be read as Temporal's
recovery latency** — B4's is dominated by the harness's lease wait, which is a
property of this harness and not of any engine.

---

## 6. What a hostile reviewer should still be told

1. **B4 is 2 runs / 20 executions in the Session 3 table.** The 0.95 is a point
   estimate on a thin row and is reported with its interval.
2. **B4 is not Temporal.** It shares one mechanism. §3 is the full list.
3. **The re-execution decision is B4's own code**, not a Temporal binary. The
   defence is §2: it is the vendor's documented default, quoted, with the URL.
4. **The quotations are dated** (2026-08-06) and must be re-verified before
   submission.
5. **B4 and B4b bracket the configuration space, they do not survey it.** A
   deployment could set Maximum Attempts to 3, or add a heartbeat, or make the
   activity idempotent. The first two land between B4 and B4b on the same
   duplicate/loss trade; the third leaves the problem this paper is about.

---

## References

- Temporal — *Detecting Activity failures*.
  <https://docs.temporal.io/encyclopedia/detecting-activity-failures> (read 2026-08-06)
- Temporal — *Retry Policies*.
  <https://docs.temporal.io/encyclopedia/retry-policies> (read 2026-08-06)
- Temporal — *Activity definition* (Idempotency).
  <https://docs.temporal.io/activity-definition> (read 2026-08-06)
- Temporal — *Activities*.
  <https://docs.temporal.io/activities> (read 2026-08-06)
