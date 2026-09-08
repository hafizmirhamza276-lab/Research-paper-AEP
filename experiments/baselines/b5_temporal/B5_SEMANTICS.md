# B5 semantics: what the vendor's engine can be crashed at, and what it cannot

**Written as design only; §6a now carries what was measured.** The mapping below
was written before anything ran, from documentation and structural argument. Two
of its claims have since been checked on the real stack and the results are in
**§6a** — point 6 is observable (so it stays *approximate*, not *absent*), and
B5 needs a worker supervisor it does not have. Everything not marked there is
still unconfirmed against a running server.

Structured to be read side by side with
[`../B4_SEMANTICS.md`](../B4_SEMANTICS.md), which uses the same six sections.
Where B4's document says *"B4 is our model"*, this one says what the vendor's
engine actually does — and, in §2, where it cannot be made to do it at all.

---

## 1. The system B5 runs

**Temporal** (temporal.io) — the same engine `B4_SEMANTICS.md` §1 says B4
models, but the real server and the real SDK rather than a re-implementation of
one mechanism.

* **B5** — `maximumAttempts` unlimited (the vendor default), the configuration
  B4 models.
* **B5b** — `maximumAttempts = 1`, the documented at-most-once configuration
  B4b models.

The point of WS-6 is to convert §VIII-A(i) from *"B4 is not Temporal"* into
*"B4 is our model of Temporal; B5 is the vendor's engine, and here is how far
they agree"* — with the disagreements reported, not smoothed.

> **Quotation provenance.** `B4_SEMANTICS.md`'s quotations were retrieved
> **2026-08-06** and its §6.4 already says they must be re-verified before
> submission. **They have not been re-verified in this pass** — re-reading live
> vendor pages was out of scope here. Treat every Temporal behaviour claim in
> this document as *documented as of 2026-08-06 and unconfirmed against the
> running server*.

---

## 2. The mapping — the load-bearing part of this document

The six crash points are **not restated from memory**. They were read from
`experiments/harness/crash_points.py`, whose `ROADMAP_CRASH_POINTS` mapping is
the canonical list and whose insertion order is asserted by test:

```
before_intent_write, after_intent_before_barrier, after_barrier_before_dispatch,
mid_dispatch, after_response_before_resolution, after_resolution_before_barrier
```

The pattern for a partial mapping is also not invented here. It already exists in
`experiments/baselines/crash_points.py`, which maps each roadmap name either to a
real position in that system **or to `None`**, where `None` means *this system
has no such moment*; `run_matrix.py` then records the cell as `not_applicable`
with a reason and the paper's tables carry the gap rather than filling it. That
module's own docstring states the principle this document is bound by:

> "Aliasing the missing point onto the nearest one that does exist would produce
> a full row of numbers for a cell whose experiment was never performed, and
> nothing in the output would say so."

**Temporal's activity lifecycle does not have six points.** The mapping below is
therefore 3 exact, 2 approximate, 1 absent — and the absent one is the
expensive one.

### 2.0 The structural reason the mapping cannot be clean

In AEP, the worker performs the durable write *and* waits for the acknowledgement,
so "written but not yet acknowledged" is an instruction boundary **in the process
being killed**. In Temporal it is not. The worker issues an RPC
(`RespondWorkflowTaskCompleted`, `RespondActivityTaskCompleted`) and the **server**
performs the persistence transactionally before replying. There is no worker-side
instant at which a record exists un-acknowledged, because from the worker's side
the write and its acknowledgement are one round trip.

**Every approximation and the one absence below trace to that single fact.** Both
of AEP's `*_before_barrier` points name a window that, in Temporal, lives inside
the server and is unreachable by `SIGKILL` of the worker.

### 2.1 The table

| # | Roadmap point | Temporal position | Quality | What it costs |
|---|---|---|---|---|
| 1 | `before_intent_write` | Workflow task polled and executing; killed before `RespondWorkflowTaskCompleted` carries `ScheduleActivityTask` | **approximate** | §2.2 |
| 2 | `after_intent_before_barrier` | — | **ABSENT** | §2.3 — the expensive one |
| 3 | `after_barrier_before_dispatch` | `ActivityTaskStarted` durably recorded; activity function entered; killed before the provider call | **exact** | — |
| 4 | `mid_dispatch` | Killed by deferred watchdog while the provider HTTP call is in flight | **exact** (same deferred delivery as AEP's) | — |
| 5 | `after_response_before_resolution` | Provider response received and classified in a local variable; killed before the activity returns | **exact** | — |
| 6 | `after_resolution_before_barrier` | Killed during the `RespondActivityTaskCompleted` RPC | **approximate** | §2.4 |

Points 3 and 4 share one physical position and differ only in delivery —
synchronous at the checkpoint versus deferred watchdog — which is **exactly**
how `experiments/baselines/crash_points.py` already treats them for B4
(`BEFORE_REQUEST_TRANSMISSION` "serves both"). That correspondence is clean and
needs no special pleading.

### 2.2 Point 1 is approximate, and the cost is small

AEP's `before_intent_write` means *the lease is held and nothing has been written
anywhere*. At the analogous Temporal moment, the server has already durably
recorded `WorkflowTaskStarted` — so something **has** been written, just nothing
about the activity.

**Cost: low, and it is a difference in bookkeeping rather than in the quantity
under test.** No `ActivityTaskScheduled` exists, so no activity can be re-run,
so neither a duplicate nor a lost effect is reachable from this point in either
system. Both should report zero of both. If B5 reports non-zero here, that is a
finding about the harness, not about Temporal.

### 2.3 Point 2 is ABSENT, and this is the one that damages the comparison

`after_intent_before_barrier` is *the record of intent exists and has not been
acknowledged durable*. In Temporal there is **no such worker-side instant**
(§2.0). The window exists inside the server, between accepting
`RespondWorkflowTaskCompleted` and committing the history transaction, and no
`SIGKILL` of the worker reaches it.

Three things follow, and all three must survive into the paper:

1. **B4 has data here and B5 cannot.** `experiments/baselines/crash_points.py`
   gives B4 and B4b `_WITH_PRE_DISPATCH_RECORD`, which maps this point to a real
   position, and the frozen `per-cell-metrics.csv` carries B4 and B4b cells at
   `after_intent_before_barrier` on all three response classes. **So the
   B4↔B5 comparison has a hole exactly where B4 has numbers.** WS-6's hypothesis
   (§4) is therefore not testable at this crash point, and must not be reported
   as though it were.
2. **It is the point the paper's central claim turns on.** This is the residual
   pre-ack window `docs/22-formal-model.md` declares for P2, the point the
   Phase 13 prevention result is collected at, and the point WS-4 armed
   `drop_writes` at. The one crash point B5 cannot deliver is the one that
   matters most.
3. **The honest framing is a narrower claim, not a hedged one.** B5 can support
   *"the vendor's engine reproduces our model's duplicate/loss behaviour at the
   crash points both can be cut at"*. It cannot support *"B5 confirms B4"*
   without qualification, and §VIII must say which.

**What would close it, and why it is not being done here.** The window is
reachable by killing the **Temporal server** (or its datastore) rather than the
worker — but that is a different fault class (F3 crash-stop of the state store,
the Redis-kill class), not the worker-crash class WS-6 is defined on, and mixing
them would answer a different question. Recorded as an open question (§7), not
silently substituted.

### 2.4 Point 6 is approximate, and the cost is that the window is not ours to set

AEP's `after_resolution_before_barrier` means *the outcome is in Redis and the
fsync has not been acknowledged*. The nearest Temporal moment is the worker dying
during `RespondActivityTaskCompleted`: the result exists in the worker, and
whether the server persisted it is genuinely racing.

Two differences, and the second is the one that costs:

* **Weaker.** In AEP the record demonstrably reached the store. Here it may never
  have left the worker, so "written but unacknowledged" and "not written at all"
  are both inside this crash point and are not distinguishable from the worker.
* **Not controllable.** AEP's window is an fsync interval the harness sets and
  measures. This one is a network RPC plus a server-side transaction — its width
  is set by the server and the loopback, and nothing in the harness controls it.
  **So a rate measured at point 6 in B5 is measured over a window of unknown and
  unequal width to B4's**, and the two should be compared with that stated
  rather than as like for like.

### 2.5 What a mapping claiming six clean correspondences would have hidden

Had this document asserted six exact points, it would have hidden: that Temporal
has no worker-side pre-ack window at all (§2.0); that the paper's most important
crash point is unreachable (§2.3); and that one of the remaining five is measured
over a window the harness does not control (§2.4). All three change what the
result means, and none is visible in a row of numbers.

---

## 3. What B5 implements, knob by knob

Same fairness-statement format as `B4_SEMANTICS.md` §3. The column that matters
is the middle one: with B5, most answers become "yes, really" — that is the whole
point of running the vendor's engine.

| Mechanism | In B4 (our model) | In B5 (vendor engine) |
|---|---|---|
| Durable append-only event history | Yes — Redis list | **Yes — the server's own history, its persistence** |
| History durably committed before proceeding | Yes — same `WAITAOF` barrier | **Yes — server-side transaction, not ours to observe** (§2.0) |
| Replay; memoised completion not re-run | Yes | **Yes — real SDK replay** |
| Re-execution of a scheduled-but-uncompleted activity | Yes (modelled) | **Yes — real Start-To-Close timeout and retry** |
| `maximumAttempts` unlimited (vendor default) | Yes | **Yes — B5** |
| `maximumAttempts = 1` (at-most-once) | Yes, as B4b | **Yes — B5b** |
| Retry backoff / jitter | No | **Yes, unavoidably** — see below |
| Heartbeating | No | **No** — not configured; same argument as B4 §5 |
| Activity idempotency | **No — deliberately** | **No — deliberately.** Same reason: the workload is a non-idempotent legacy mutation with no idempotency key. Modelling it deletes the experiment. |
| Task queues, sticky execution, workflow versioning | No | Present in the engine; not exercised — one activity, one version, one worker slot |

**Retry timing stops being free.** B4 omits backoff because retry *timing* is not
under test. B5 cannot omit it: a real server schedules the retry after a real
Start-To-Close timeout plus backoff. That interacts with the harness's
`recovery_deadline_seconds` (default 120 s) and creates an outcome B4 cannot
produce — **the retry has not happened yet when the run ends**. See §4 and the
open question in §7.

---

## 4. B5b, and the third outcome neither B4 nor B4b can produce

B5b is B5 with `maximumAttempts = 1`, mirroring `B4_SEMANTICS.md` §4 exactly:
the attempt budget is spent, the activity is recorded as failed, the failure
propagates, and **nothing tells an operator that a real-world effect may be
unaccounted for**. That non-escalation is the property the paper's three-way
table turns on, and it should hold in the vendor's engine for the same reason it
holds in B4 — the fact needed (did the provider apply the mutation?) is not in
the history and cannot be put there.

The three-way table B5 is expected to reproduce, from `B4_SEMANTICS.md` §4:

| | caller-caused duplicate | lost effect | ambiguity declared |
|---|---|---|---|
| B5 (`maximumAttempts` unlimited) | expected **yes** | no | no |
| B5b (`maximumAttempts = 1`) | no | expected **yes** | **no** |
| AEP-full | no | no | **yes**, bounded and measured |

**The new outcome: `PENDING_AT_DEADLINE`.** If the Start-To-Close timeout plus
backoff exceeds the run's recovery deadline, B5 ends the run with the activity
neither re-run nor abandoned. This is **not** a duplicate and **not** a lost
effect; it is a run in which the engine had not yet decided. It must be counted
and reported as its own outcome, never folded into either — folding it into
"no duplicate" would make B5 look better than B4 for a reason that is purely an
artefact of the observation window.

---

## 5. Two things B5 does not model, and the argument that it need not

**Activity idempotency** — unchanged from `B4_SEMANTICS.md` §5, and the argument
is unchanged: the paper's premise is a non-idempotent legacy endpoint with no
idempotency key. Where a caller *can* make the effect idempotent, it should, and
AEP is not needed.

**Heartbeating** — also unchanged. It changes how quickly a retry is scheduled,
not whether one is. But it costs more here than in B4: because B5's retry timing
is real (§3), omitting heartbeats makes `PENDING_AT_DEADLINE` **more** likely
than a heartbeat-configured deployment would see. That biases B5 *against*
producing a duplicate, which is the conservative direction for the paper's claim
but must still be stated, because it means B5's duplicate rate is a **lower
bound** on what a tuned deployment would show.

---

## 6. What a hostile reviewer should still be told

1. **B5 cannot be crashed at `after_intent_before_barrier`** — the point the
   prevention result and WS-4 both turn on. §2.3. This is the first thing to say,
   not the last.
2. **Two of the five reachable points are approximate**, one of them over a
   window the harness does not control. §2.2, §2.4.
3. **B5's duplicate rate is a lower bound**, because heartbeating is off and the
   observation window is finite. §4, §5.
4. **A `PENDING_AT_DEADLINE` run is not a clean run.** If these dominate, the
   comparison is uninformative and should be reported as such rather than as
   agreement.
5. **The 2026-08-06 quotations are still unverified.** `B4_SEMANTICS.md` §6.4
   already required re-verification before submission; this pass did not do it.
6. **No B5 latency number is Temporal's recovery latency.** Same caveat as B4,
   and stronger: the timeout and backoff are configured by us.

---

## 6a. Two things measured on the real stack (added 2026-09-07)

**Point 6 is observable, so it stays approximate rather than absent.** Eight of
eight trials reached `DURING_COMPLETE_RPC`, fired, and had already called the
provider. Section 2.4's *other* caveat is untouched: the window is a network RPC
plus a server-side transaction, its width set by the server and the loopback and
not by the harness, so a rate measured there is **not like-for-like with B4's**
fsync-width window.

Had it proved unhittable, B5 would have been crashable at only **four of six**
roadmap points, missing **both** `*_before_barrier` positions -- the two that
name the window AEP's durability argument is entirely about -- and the comparison
would have reduced to *agreement where neither engine has a durability window to
be cut in*. That cost is **not** incurred, and it is recorded here because it was
one measurement away from being.

**B5 needs a worker supervisor, and does not have one.** Temporal schedules the
retry after the worker dies, but a retry needs a **live worker** to poll for it.
The probe kills its single worker and never respawns it, so across three
Start-To-Close values (2.5 s, 4 s, 8 s) every run sat `PENDING_AT_DEADLINE` at
150 s with **zero provider calls** -- a measurement of the harness, not of the
engine.

**No B5 cell can measure a duplicate until this exists**, because a duplicate is
by definition what the *second* attempt does. B4's harness respawns after
`SIGKILL`, which is what makes its replay observable; B5 needs the equivalent.
This is a prerequisite for collection that four earlier rounds did not surface.

**Built 2026-09-08** as `supervisor.py`, following `runner.py:201`
`run_worker_slot` — bounded lifetimes, the fault armed on attempt 1 only
(`runner.py:244`, so a respawning arm does not take more faults than a
non-respawning one), and every lifetime recorded. B4's `from_index` resume is
deliberately **not** carried: what to re-execute is the engine's decision and is
the thing under measurement.

With it, the retry lands in **23.9–26.7 s** at Start-To-Close values of 2.5 s,
4 s and 8 s — all COMPLETED, against PENDING_AT_DEADLINE at 150 s with zero
provider calls without it. At 2.5 s the provider was called **twice**: the
caller-caused duplicate, produced by the vendor's engine for the first time.
The 120 s recovery deadline accommodates this with roughly fourfold margin, so
it does not move for B5 and B5's runs stay comparable to B4's frozen ones.

---

## 7. Open questions for the collection pass

Recorded rather than resolved, because settling any of them requires running
something and this pass may not.

1. **The image digest is not pinned.** `compose.temporal.yml` pins version tags.
   A tag is not a pin. The digests must be resolved and committed **before any
   data**, exactly as the Redis image is pinned.
2. **What Start-To-Close timeout?** It sets whether a retry lands inside the run.
   Too long and every run is `PENDING_AT_DEADLINE`; too short and the timeout
   fires before the provider replies, producing a retry that is an artefact of
   the timeout rather than of the crash. Must be measured against the mock
   provider's response-time distribution and fixed **before** collection.
3. **Does `recovery_deadline_seconds = 120` accommodate it?** If not, the
   deadline moves for B5's cells only — which makes B5's runs not directly
   comparable to B4's frozen ones, and that has to be stated rather than absorbed.
4. **Is the point-6 race actually observable?** On loopback the
   `RespondActivityTaskCompleted` window may be too narrow to hit reliably. If
   the crash almost never lands inside it, point 6 is effectively absent too, and
   the mapping table above must be corrected to say so.
5. **Can the server's own pre-commit window be reached at all**, by killing the
   server rather than the worker (§2.3)? That is a different fault class and is
   *not* proposed here; the question is only whether it is worth a separate cell.
6. **Does the harness's crash injector reach an SDK worker?** The existing
   injector kills a harness worker process it spawned. A Temporal SDK worker is
   also a process, but the crash points are inside SDK callbacks rather than
   inside `aep_core` checkpoints, so the delivery mechanism has to be rebuilt and
   its own gate proven able to fail (`docs/26` §3 rule 13).

---

## References

Inherited from `B4_SEMANTICS.md`, all read 2026-08-06 and **all due
re-verification**:

- Temporal — *Detecting Activity failures*.
  <https://docs.temporal.io/encyclopedia/detecting-activity-failures>
- Temporal — *Retry Policies*.
  <https://docs.temporal.io/encyclopedia/retry-policies>
- Temporal — *Activity definition* (Idempotency).
  <https://docs.temporal.io/activity-definition>
- Temporal — *Activities*. <https://docs.temporal.io/activities>

Read from this repository, not from memory:

- `experiments/harness/crash_points.py` — `ROADMAP_CRASH_POINTS`, the canonical
  six and their order.
- `experiments/baselines/crash_points.py` — the partial-mapping pattern,
  `None` for an absent moment, and `CrashPointNotApplicable`.
- `experiments/results/matrix/analysis/per-cell-metrics.csv` — B4 and B4b have
  cells at `after_intent_before_barrier`, which is what makes §2.3 a hole rather
  than a shared absence.
