# WS-7 — the TLA+ specification

**Status.** Design and specification complete; model-checked locally in sixteen
configurations. **The CI job (WS-7 task 7.2) is deliberately not written yet**,
and neither is the new §IV-D (task 7.3). This pass is the specification and the
evidence about what it does and does not establish.

**Files.**

| Path | Role |
|---|---|
| `AEP.tla` | The specification. |
| `configs/*.cfg` | Sixteen configurations. Each declares, on its first line, whether it must pass or must fail and why. |
| `../scripts/run_tlc.sh` | Runs every configuration and holds it to its declared expectation. |
| `../scripts/check_tla_transitions.py` | Holds `AEP.tla` to the implementation it claims to model. |
| `../tests/test_check_tla_transitions.py` | Exercises that gate on the branches where it fails. |

---

## 1. What this is, and what it is derived from

The state machine, the guards on every write, the creation fence, the recovery
classification table and the dispatch-authorization chain are transcribed from
the **implementation** — `aep_core/core/intents.py`,
`intent_workflow.py`, `intent_recovery.py`, `connector_contract.py`,
`durability.py` — and from `docs/22-formal-model.md`, which is itself a
code-derived document with `file:line` citations. They are **not** transcribed
from §IV of the manuscript. §6 below records the four places where the two
differ.

That ordering is not pedantry. WS-4 and WS-6 both found the code and its
description disagreeing, and a specification written from prose would have
reproduced the prose and then certified it. A model checker asked about the
wrong state machine does not complain; it reports success.

Because a transcription is a copy and a copy drifts,
`scripts/check_tla_transitions.py` re-derives the transition table and the
status alphabet from `aep_core.core.intents` and fails if `AEP.tla` disagrees.
This follows the precedent `scripts/gen_state_machine.py` already set for the
paper's state-machine figure, for the reason stated in that file: *"A hand-drawn
figure is a claim about the protocol that nothing checks, and this repository's
audit history is largely a history of documents that claimed properties the code
did not have."*

## 2. Running it

```sh
# needs a JRE and tla2tools.jar (TLA_TOOLS=/path/to/tla2tools.jar to override)
scripts/run_tlc.sh                  # all sixteen configurations
scripts/run_tlc.sh base aof-rewind  # named ones

python scripts/check_tla_transitions.py --all   # the drift gate
```

## 3. The model

### 3.1 Principals and state

One execution, one step, `Workers` workers, one recovery service, one
non-cooperative endpoint.

| Variable | Meaning |
|---|---|
| `store` | Committed Redis state: version, lock holder, per-intent status, per-intent reconciliation attempts, the dispatch-authorization key. |
| `disk` | The fsynced prefix — what survives a restart. |
| `minted` | Intent ids ever created. Models UUID freshness, and is deliberately **not** rewound by `Restart`: a crashed Redis does not cause a UUID to be drawn twice. |
| `effect` | **God view.** Whether the endpoint really applied intent *i*. |
| `pc`, `ctx` | Worker location and local context; `ctx` is lost on crash. |

`disk` and `store` together give append-only-file semantics: `Barrier` and
`BackgroundFsync` advance `disk` to `store`, and `Restart` sets `store` back to
`disk`. A write is lost exactly when it falls after the last flush — which is
what `appendfsync everysec` means, and why a lock release can be lost while the
state write that preceded it survives. That is the mechanism R1-3 turns on.

### 3.2 The endpoint is not cooperative

This is the modelling decision the paper's claim rests on, so it is made in one
place and enforced mechanically.

1. **It cannot be enrolled.** `Transmit` reads nothing — not the ledger, not
   `minted`, not any earlier effect. No modelled action lets AEP change the
   endpoint's behaviour, so no idempotency key, nonce or coordinator exists to
   be offered. If `Transmit` runs twice, two effects exist.
2. **It fails indistinguishably.** `AllowedEvidence` puts `"AMBIGUOUS"` in
   *every* set, on every path, so the caller can never rely on a definitive
   answer and can never separate "no effect" from "effect, answer lost".
3. **The protocol cannot see `effect`.** No worker or recovery action reads it.
   `check_tla_transitions.py --check-oracle` enforces this textually across
   nineteen protocol definitions, and
   `test_a_protocol_action_reading_the_oracle_is_rejected` exercises the
   rejection. If a guard could branch on `effect`, the model would verify a
   protocol strictly stronger than the implementation and every property would
   still come back green — the one failure mode a formal artifact must not have.

`effect` is read by `Transmit` (the endpoint deciding what it did), by
`AllowedEvidence` / `AllowedReadback` (the endpoint deciding what it *says* —
an endpoint does know what it did), and by the invariants. Nowhere else.

### 3.3 Faults

`Crash(w)` is enabled at **every** worker location, which is strictly more
adversarial than the six crash points the harness injects at and covers the 22
named in `tests/mock_connector.py:59`. `LeaseExpires` is enabled at any moment.
`Restart` is the AOF rewind. These are F1, F5 and F3 of §III.

---

## 4. Properties, configurations, and results

### 4.1 The properties checked

| Property | Kind | What it says |
|---|---|---|
| `TypeOK` | invariant | Nothing leaves its declared domain. |
| `P1_VersionMonotone` | action | The fencing counter never goes backwards — P1's "one monotonic Redis timeline". |
| `P1_NoStatusRegression` | action | No status is superseded and then resurrected. |
| `P2_LegalEdgesOnly` | action | Every status change follows one of the code's ten edges. |
| `P2_NoReentry` | action | Nothing re-enters `ABOUT_TO_FIRE`. This is what "never silently re-dispatched" means. |
| `P2_AtMostOneUnresolved` | invariant | At most one unresolved intent at a time — "never silently dropped", safety half. |
| `P2_EventuallyResolved` | temporal | A durable `ABOUT_TO_FIRE` reaches a terminal automated state. Liveness half. |
| `P3_BoundedAttempts` | invariant | Reconciliation stays inside its attempt budget and escalates at exhaustion. |
| `NoUndetectedDuplicate` | invariant | If more than one effect exists, the ledger declares ambiguity. |
| `NoLostEffect` | invariant | An effect is never recorded as `FAILED_CONFIRMED`, and never has no record at all. |

`NoUndetectedDuplicate` and `NoLostEffect` are the trilemma's first two horns.
The third — declared ambiguity — is not a violation, and that asymmetry is the
protocol's entire position stated formally.

`NoLostEffect` permits the transient `ABOUT_TO_FIRE` and `FIRED_UNCONFIRMED`
statuses, because an invariant holds at every state including mid-flight ones.
That those statuses do not persist is `P2_EventuallyResolved`'s job. **The two
properties are only meaningful together**, and neither alone should be quoted as
the safety result.

### 4.2 The configuration matrix

Nine of the sixteen configurations exist to show that a stated assumption is
*load-bearing*, or that a liveness antecedent is reachable. Each declares the
outcome it must produce on its own first line, and `run_tlc.sh` reports a
configuration that fails for the wrong reason, or that passes when it should
fail, as an error. A model checker run only where everything passes is the same
shape as a gate that cannot fail (`docs/26` §3 rule 13).

That mechanism has already earned itself once. `untruthful-endpoint` was
committed expecting `NoUndetectedDuplicate`; it fails `NoLostEffect` instead,
because the lost effect is seven steps cheaper. The runner reported
`WRONG-REASON` rather than a green tick, the expectation was corrected to what
the model actually does, and the duplicate horn got its own configuration —
which is the outcome an expectation-free runner would have missed entirely.

All sixteen matched their declared expectation. TLC 2.19; `scripts/run_tlc.sh`.

**Assumptions hold — the protocol's claims (7 configurations).**

| Configuration | Switched | Distinct states | Depth | Result |
|---|---|---|---|---|
| `base` | — (all assumptions hold) | 31,484 | 22 | **pass**, all 10 properties |
| `b3-no-barrier` | `BarrierEnabled=FALSE` | 182,056 | 28 | **pass**, safety |
| `b3-no-barrier-liveness` | `BarrierEnabled=FALSE`, `MaxVersion=4` | 87,156 | 27 | **pass**, liveness |
| `write-loss-no-restart` | `TruthfulFsync=FALSE` | 200,400 | 28 | **pass**, safety |
| `no-readback` | `Capability=NO_READBACK` | 10,568 | 22 | **pass** |
| `positive-only` | `Capability=POSITIVE_ONLY_READBACK` | 16,012 | 22 | **pass** |
| `undeclared-capability` | `Capability=UNDECLARED` | 10,568 | 22 | **pass** |

These counts are complete state spaces and are reproducible run to run.

Three of them carry most of the weight. **`no-readback` is the configuration
that matters most for the paper's framing**: the endpoint supplies nothing, can
be enrolled in nothing and answers no question, and the trilemma invariants
still hold — because the protocol takes the third horn every time.
**`b3-no-barrier` is what `docs/26:211` asks for** and it comes out as
predicted: P2 survives the ablation entirely, because the barrier does not
defend the state machine, it defends the record's existence, and nothing in that
configuration destroys records. **`write-loss-no-restart` is WS-4's fault with
the restart removed**, and it too passes — the lie costs nothing until the
moment it costs everything.

**Assumptions removed — what each one was holding up (9 configurations).**

| Configuration | Switched | Breaks | Depth | What it shows |
|---|---|---|---|---|
| `aof-rewind` | `SingleTimeline=FALSE` | `P1_VersionMonotone` | 4 | R1-3, probe-confirmed in `docs/22`, now also a model counterexample. `docs/26:214` asks for this figure. |
| `write-loss` | `TruthfulFsync=FALSE`, `SingleTimeline=FALSE` | `NoLostEffect` | 8 | WS-4. The barrier answered yes and the effect has no record. |
| `b3-no-barrier-restart` | `BarrierEnabled=FALSE`, `SingleTimeline=FALSE` | `NoLostEffect` | 8 | The ablation is harmless until a restart, and then is not. This pairing is the ablation's whole point. |
| `untruthful-endpoint` | `TruthfulEndpoint=FALSE` | `NoLostEffect` | 9 | The endpoint applies the mutation, reports failure, and the runner believes it. |
| `untruthful-endpoint-duplicate` | as above, duplicate horn only | `NoUndetectedDuplicate` | 16 | The wrong `FAILED_CONFIRMED` reopens the creation fence and a second effect follows. |
| `no-reconcile-delay` | `ReconcileDelayCovers=FALSE` | `NoLostEffect` | 10 | The F5 scheduling gap `docs/06-phase2-design.md:249-252` already declares. |
| `operator` | `OperatorEnabled=TRUE` | `NoLostEffect` | 12 | `docs/22` §5.3: an unauthenticated operator can convert declared ambiguity into a lost effect. |
| `vacuity-base` | — | `NoDurableIntentExists` | 4 | **Must fail.** Witness that a durable `ABOUT_TO_FIRE` is reachable, so `base`'s liveness result is not vacuous. |
| `vacuity-b3` | `BarrierEnabled=FALSE` | `NoDurableIntentExists` | 4 | The same witness for the ablation, whose durable prefix advances only on the background flush. |

**Do not quote a state count from this second table.** A failing run stops at
its first counterexample, so its count reflects the search order, not the model:
`write-loss` was observed at 705, 667 and 729 distinct states on three runs of
the identical configuration, while every passing configuration reproduced its
count exactly. The *depths* are stable and are the useful number —
they say how many steps of ordinary protocol behaviour it takes to reach the
violation, and the answer is between 4 and 16 in every case.

Two of these deserve emphasis. The `untruthful-endpoint` pair shows that **both**
trilemma horns open when the endpoint lies, and that the cheaper one is the lost
effect (9 steps) rather than the duplicate (16) — the creation fence is doing
real work, and a duplicate has to get past it. And the `vacuity-*` pair exists
because `P2_EventuallyResolved` is an implication: had its antecedent been
unreachable it would have passed while meaning nothing, and a liveness result
that cannot fail is the thing this whole file is trying not to produce.

### 4.3 Bounds, and the one place they were reduced

2 workers, 2 intent slots, 5 versions, attempt budget 2, one execution, one
step. `docs/26:212` asks for 2 workers and 3 versions; this is that or more on
every axis. The bounds are small, and §7 says what that costs.

**One exception, recorded rather than absorbed.** The barrier ablation's safety
is checked at `MaxVersion=5` (`b3-no-barrier`, 182,056 states) but its liveness
at `MaxVersion=4` (`b3-no-barrier-liveness`, 87,156). Without a barrier the
durable prefix advances only on the background flush and so lags by an arbitrary
amount, which is what makes that configuration's state space roughly six times
the base one's; liveness checking over the full graph did not finish inside 40
minutes. So the ablation's liveness is verified one version shallower than its
safety, and that is a cost decision, not a result.

Liveness is the whole expense here: `base` completes safety in seconds and
spends about six minutes on the temporal properties. When WS-7 task 7.2 wires
this into CI, the shape that follows is safety on every configuration and
liveness on a named subset — but that is a decision for the pass that writes it,
with its own budget.

---

## 5. What is **not** checked, and why

A model checker that verifies only what is easy is the same shape as a gate that
cannot fail. These are the exclusions, each with the reason it is an exclusion
rather than an oversight.

1. **The request binding, the vault, and every cryptographic construction.**
   AES-GCM, the HMAC, the binding digest, the create-once vault. TLA+ models
   control flow; an uninterpreted function standing in for a hash proves
   nothing about the real construction, and modelling it as unforgeable would
   *assume* the property the code is supposed to have. Excluded entirely rather
   than modelled badly.

2. **The in-process `DurabilityAck` chain (R2-7).** The implementation's link
   from "a real fsync happened" to "dispatch is authorised" is a Python object
   guard: non-constructible, non-copyable, single-use, scope-bound. `docs/22`
   R2-7 already states plainly that this is *"an ordinary control-flow guard
   under trusted-code assumptions, not a cryptographic capability"* and that
   arbitrary same-process code can call the module-internal issuer without
   running the barrier. Modelling it as sound would assume exactly what R2-7
   says is not proven. So the model checks the part that is real and atomic —
   the Redis-visible authorization key, written by one script and re-checked by
   the preflight — and **assumes** the in-process link. `Authorize` carries this
   caveat inline.

3. **Real time.** The lease TTL budget $T_{client} \le T_{lock} - B$, the
   `PTTL` floor, backoff durations, the 31-day retention floor. The model is
   untimed. Where this cuts *for* the protocol it is neutralised — `LeaseExpires`
   fires at any moment, which is more adversarial than the real budget. Where it
   cuts *against*, it is named: see exclusion 4.

4. **The reconciliation delay, which is assumed rather than derived.**
   `reconcile_after = prepared_at + client_timeout + buffer_margin +
   settlement_lag` (`aep_core/core/intents.py:836-841`) keeps recovery from
   classifying an intent whose worker may still be about to transmit. Untimed,
   that becomes the constant `ReconcileDelayCovers` and the `InFlightAt` guard,
   plus weak fairness on `WorkerStep` so a stalled worker does not block
   recovery for ever. Both halves are assumptions the model imports, not results
   it produces. The `no-reconcile-delay` configuration removes the first half
   and shows what it was buying. **This is the single most important entry in
   this list**: `NoLostEffect` depends on it, and the dependency is not visible
   in §IV.

5. **Recovery crash interleaving.** Each recovery write is one atomic action
   that takes the lease and gives it back. The abstraction is sound here because
   every recovery write is independently fenced by the same CAS and separately
   barriered, and recovery is read-only with respect to the endpoint, so a crash
   between two recovery writes is observationally identical to not performing
   the later one — which the model already allows. What it costs: a *partial*
   recovery write is not modelled, and could not be, because the Lua script that
   performs it is atomic in Redis.

6. **Unbounded liveness.** `P2_EventuallyResolved` carries the disjunct
   `store.version = MaxVersion`, because the version bound makes the state space
   finite and a behaviour that exhausts it deadlocks for a reason belonging to
   the model. What the property establishes is therefore narrower than it looks:
   *no reachable state leaves a durable intent unresolved for a reason internal
   to the protocol, within the version budget*. It is not a termination proof.

7. **Assumption A1 — that the recovery loop runs at all.** `run_forever` is a
   library coroutine and the repository ships no supervisor (`docs/22` §1.1).
   The model gives recovery strong fairness, which asserts A1 rather than
   establishing it.

8. **Byzantine Redis, direct socket writers (R1-1, NC-4), memory bounds
   (R3-6), multi-step executions, and duplicate provider *responses*
   (F4, still unmodelled in the code's own test suite).** Out of model in
   `docs/22` §2 and out of model here, for the same reasons.

9. **That the model is the implementation.** See §7.

---

## 6. Findings — where the code and the description differ

The instruction for this pass was to specify what the implementation does and
report divergences rather than specify the paper's version. Four, in descending
order of consequence. **None of them changes a measured number**; three are
completeness or precision defects in the description, and one is a framing
observation.

### F1 — `docs/26`'s own state-machine sketch is missing four of the ten edges

`docs/26:211` describes the machine as
`NONE → ABOUT-TO-FIRE → FIRED-UNCONFIRMED → {FIRED-CONFIRMED, FAILED-CONFIRMED,
PERMANENTLY-AMBIGUOUS}`. The code's `LEGAL_INTENT_TRANSITIONS` has ten edges,
and the sketch omits `ABOUT_TO_FIRE → FIRED_CONFIRMED` and
`ABOUT_TO_FIRE → FAILED_CONFIRMED` — **the ordinary path every non-crashed
dispatch takes** — as well as the `FIRED_UNCONFIRMED` self-loop that the
reconciliation budget counts on, and the two operator edges out of
`PERMANENTLY_AMBIGUOUS`.

The sketch also implies a direct `ABOUT_TO_FIRE → PERMANENTLY_AMBIGUOUS` edge.
There is none: escalation must pass through `FIRED_UNCONFIRMED` via the recovery
claim, which is what advances the version and consumes the lease, and which is
therefore what stops a late original worker from persisting its own resolution.

The manuscript is **not** affected: §IV defers to
`scripts/gen_state_machine.py`, which imports the edge set from the code. This
is a defect in the direction document, which is what a reader working from the
handoff would build from. `test_the_specification_has_exactly_the_code_s_ten_edges`
pins both absences.

### F2 — §IV describes one pre-dispatch failure path; the code has two

§IV (`04-protocol.tex:25-29`) documents the barrier-failure path:
`FAILED_CONFIRMED` with evidence `LOCAL_NO_DISPATCH`
(`intent_workflow.py:454-476`). The code has a second, at `:505-526`: a rejected
**preflight**, when the worker still owns the lease, also persists
`FAILED_CONFIRMED` — with reason `pre-dispatch-preflight-failure`, and with **no
evidence class at all**, where the barrier path sets `LOCAL_NO_DISPATCH`.

Both are sound: the preflight is before transmission, so no bytes were sent.
Neither reason string, and no consumer of `LOCAL_NO_DISPATCH`, exists anywhere
outside the line that writes it — `experiments/baselines/intent_classifier.py`
maps on **status**, not reason, so both paths classify identically and **no
measured number moves**. The defect is that §IV says *"this is the path that
produces the measured result of §VI"* about one of two paths that produce it.
Both are modelled (`BarrierFails`, `PreflightRejects`).

### F3 — the B3 ablation and the WS-4 write-loss regime are the same model state

`NoBarrierDurabilityBarrier.confirm_durable` returns `True` without issuing any
command (`experiments/baselines/b3_no_barrier.py:78-90`).
`RealWaitAofDurabilityBarrier.confirm_durable` returns `True` when Redis reports
`local_fsyncs >= 1` (`durability.py:332`) — which, under `dm-flakey
drop_writes`, it does on every request while the kernel discards the write.

Their *durability* behaviour is the identical model state — the barrier said yes
and `disk` did not advance — and in `AEP.tla` it is literally the same
expression: `Fsync(s) == IF BarrierEnabled /\ TruthfulFsync THEN s ELSE disk`.

**They are not, however, the same system, and the model checker is what makes
the difference measurable.** Compare the two configurations that explore a
*complete* state space, `write-loss-no-restart` and `b3-no-barrier`: 200,400
against 182,056 distinct states, both at depth 28. The 18,344-state gap is one
action. `BarrierFails` is guarded by `BarrierEnabled`, so the ablated barrier
*cannot report failure* — it returns `True` without asking anything — while the
real barrier under write loss still raises on a `WAITAOF` timeout or a malformed
response.

(The comparison is drawn between two *passing* configurations deliberately.
A failing configuration stops at its first counterexample, so its state count
reflects the search order rather than the model — `write-loss` was observed at
705, 667 and 729 distinct states on three runs of the identical config, while
every passing configuration reproduced its count exactly. §4.2 says so, and no
argument here rests on a failing run's count.)

So the precise statement is sharper than "AEP-full degrades into B3", and better
for the paper:

> Write loss removes the barrier's ability to **inform** while leaving its
> ability to **fail**. It keeps the failure mode that does not matter — Redis
> did not answer — and silently removes the only one that does: the write was
> not durable. The barrier is not a durability guarantee; it is a *query* about
> durability, and it inherits the truthfulness of whatever answers it.

That also explains why the ablation and the fault are not interchangeable as
evidence, which matters because `b3_no_barrier.py` already warns that *"any
B3-versus-AEP claim must say which fault was in force"*.

### F4 — the reconciliation delay is stated as politeness and used as a precondition

§III states the delay under F4 — *"recovery waits out a reconciliation delay
before drawing any conclusion"* — and separately declares the residual under
Clocks — *"a scheduling gap remains between a successful preflight and
transmission, and we declare it as such"*. So the paper does not hide it.

What the model adds is its **role**. `NoLostEffect` does not merely become
tidier with the delay; it is *false without it*, in eight steps
(`no-reconcile-delay`). The delay is a precondition of P2's soundness, not a
courtesy about late effects, and §IV's P2 argument — four links, barrier to
preflight — does not mention it. This is a reclassification of an existing
statement rather than a missing one, and it is the thing §IV-D should say when
it is written.

### A precision note on P2's wording

§IV's P2 reads *"eventually assigned **exactly one** of `FIRED_CONFIRMED`,
`FAILED_CONFIRMED` or `PERMANENTLY_AMBIGUOUS`"*. The code permits
`PERMANENTLY_AMBIGUOUS → FIRED_CONFIRMED` and `→ FAILED_CONFIRMED`
(`intents.py:87-94`), so an intent can be assigned two of the three over its
life. §IV's P3 paragraph does say the operator transition is the only exit, so
the manuscript is consistent with itself; the property *statement* is loose.
The model checks `store.status[i] ∈ Terminal`, i.e. reaches a terminal
**automated** state, and the `operator` configuration shows what the word
"automated" is doing: an unauthenticated operator (`docs/22` §5.3) can convert a
declared ambiguity into a lost effect, and nothing in the protocol checks the
assertion.

---

## 7. What a model-checked property does and does not establish

This section exists to be lifted into §VIII, scoped the way WS-4's and WS-6's
results are scoped.

**It is a statement about the model, not about the deployment.** TLC explored
every reachable state of `AEP.tla` under the bounds in §4.3 and found no state
violating the listed properties. That is a fact about a 329-line mathematical
object (`AEP.tla` is 732 lines, of which the rest is the commentary tying each
action to the `file:line` it was transcribed from), and it transfers to the
running system only as far as the object resembles it.

Specifically, a green run here does **not** establish:

- **That the Python implements the model.** Nothing connects them but a
  transcription performed by hand and one gate over the transition table and
  status alphabet. `check_tla_transitions.py` closes the drift that matters
  most and closes nothing else: it cannot tell whether `Resolve` still matches
  `WriteAheadRunner.execute`. Refinement is not proven and is not claimed.
- **That the Lua is correct.** The scripts are modelled by their *guards*, as
  read from the source. A defect in the Lua's JSON handling, its deep-equality
  check, or its arithmetic is invisible here.
- **That Redis behaves as assumed.** Script atomicity, expiry, `WAITAOF`
  semantics and AOF prefix behaviour are assumptions. WS-4 is the standing
  demonstration that one of them can be false in a way nothing detects — and
  it is modelled as an assumption switch precisely because it *was* false.
- **Anything at a larger scale.** Two workers, two intents, five versions, one
  step. Small-scope arguments are an empirical heuristic, not a theorem; a bug
  needing three workers or a second step would not appear.
- **Anything about the properties not checked.** §5 is eight items long and
  includes every cryptographic claim the implementation makes.
- **Anything about liveness in an unbounded run.** §5 exclusion 6.

What it *does* establish is narrower and still worth having:

- The state machine, the fences and the classification table **compose** into
  the trilemma properties. That was previously an argument over code paths;
  `docs/22` NC-12 says so in as many words — *"Argued from code paths, not
  model-checked"* — and NC-12 is the non-claim this workstream retires.
- **Which assumptions are load-bearing, and what each one costs.** This is the
  part an argument over code paths is worst at. Nine configurations each remove
  one stated assumption and produce a concrete counterexample trace: the AOF
  rewind un-fences a writer in 36 states; an untruthful endpoint produces an
  undetected duplicate; the ablated barrier is harmless until a restart, and
  then is not.
- **That two residuals already declared from probes have a second, independent
  derivation.** R1-3 and the F5 scheduling gap were confirmed by executable
  probes against the code; they now also fall out of a model built from the
  guards, which is a different kind of evidence for the same claim.

The honest summary for §VIII: *model checking moved AEP's safety argument from
"we read the code paths" to "the code paths, as transcribed, compose — and here
are the nine assumptions they compose under". It did not verify the
implementation, and no claim here is a claim about the deployed system.*
