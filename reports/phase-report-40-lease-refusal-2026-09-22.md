# Phase 40 — the lease refusal: what it is, and three ways out

**No live call. No harness or protocol code changed.** This establishes facts
and drafts options. Cumulative live spend unchanged at **USD 0.00359020**.

The amendment-9 draft in §3 is **not committed** and not written to `prompts/`.

---

## 1. The facts

### 1.1 The execution lease

| | |
|---|---|
| TTL | **`lock_ttl_seconds = 25`** (`run-config.json`, every phase-40 run) |
| acquired by | `SET NX EX`, `locks.acquire_lock` |
| returned when already held | **`None` — not an error.** *"None is NOT an error; the orchestrator owns backoff/retry policy."* |
| held after `SIGKILL` | the dead worker's token, in Redis. Nothing releases it — the process is gone and cannot run `release_lock` |
| acquirable again | **25 s after acquisition**. Renewal is a heartbeat from the owning process, so death stops renewal and the key expires on its own TTL |

**`LockAcquisitionError` is not raised by "the lock is held".** It comes from
`intent_workflow._acquire_with_jitter`, which retries
`lease_acquire_attempts = 3` times with backoff ceilings of 0.05 s and 0.10 s
and then raises:

```python
raise LockAcquisitionError(
    f"execution lease remained unavailable for {execution_id}")
```

### 1.2 The timing, measured

`phase40-stub-paired-2026-09-22`, `aep_full…-r0`, execution 0, seconds from the
run's first event:

```
 4.498  worker_started            (lifetime 1)
 4.602  execution_started  ex0        <- lease acquired about here
 5.369  durability_ack_observed
 5.379  provider_request_transmitted
 5.780  crash_injected
 5.809  worker_spawned            (lifetime 2)
11.114  worker_started            (lifetime 2)      +5.33s after the crash
11.217  execution_started  ex0    (the re-dispatch) +5.44s
11.332  execution_failed   LockAcquisitionError     +5.55s
```

The same run's second crash reproduces it to the hundredth: crash 22.449,
respawn 27.783 (**+5.33 s**), failure 28.001 (**+5.55 s**).

| quantity | value |
|---|---|
| crash → replacement `worker_started` | **5.33 s** (process startup; lifetime 1 took 4.50 s from spawn to start) |
| crash → re-dispatch attempted | **5.44 s** |
| re-dispatch → `LockAcquisitionError` | **0.115 s** — exactly the three attempts and two sub-100 ms backoffs |
| **lease life remaining at that moment** | **≈ 19.5 s of 25 s** |

**The replacement tries for 0.115 s to take a lease with 19.5 s left to live.**

### 1.3 What AEP does if the same payment is dispatched again *after* expiry

It still does not re-send, and the reason is the intent ledger rather than the
lease.

`execute()` mints a fresh `intent_id` per call and writes it through
`create_intent`, which enforces (`intents.py:345-364`):

> *"at most one unresolved intent is allowed per step_id"*

and (`intents.py:61-63`):

```python
UNRESOLVED_INTENT_STATUSES = frozenset(
    {IntentStatus.ABOUT_TO_FIRE, IntentStatus.FIRED_UNCONFIRMED})
```

**`FIRED_UNCONFIRMED` is unresolved**, and `FIRED_UNCONFIRMED` is exactly what
recovery resolves a crashed mid-dispatch intent *to* — it is AEP's declared
ambiguity, the state the whole protocol exists to produce. So the prior intent
is unresolved when the crash happens and **stays** unresolved after recovery
has run.

A re-dispatch therefore hits the intent CAS, which returns `-5` and raises
`IntentInvariantError` — *"immutable, append-only, uniqueness, attempt,
deletion, or TTL invariant"*. Not a re-send, not a dedup, not a fresh
ambiguity: a **fail-closed refusal**.

So: **AEP will not re-dispatch a payment whose prior intent is unresolved, at
any time, lease or no lease.** The matrix has never exercised this, because
`AEP_FULL` uses `NEXT_EXECUTION` and never re-dispatches; the agent branch is
the first thing that asks.

### 1.4 Recovery cannot race the re-dispatch — it is strictly later

Same run:

```
21.165  recovery_pass        (every 2.0 s from here)
22.449  crash_injected            lease expires about 46.3
27.886  execution_started    (re-dispatch)
28.001  execution_failed     LockAcquisitionError
…
48.981  recovery_resolution  FIRED_UNCONFIRMED      <- the FIRST resolution
```

Recovery passes ran nine times between the crash and its first resolution and
resolved nothing, because **recovery needs the same lease** — it has its own
copy of the retry loop at `intent_recovery.py:327`. Its first resolution lands
**26.5 s after the crash**, about 2.7 s after the lease expires, and **21 s
after the re-dispatch had already failed**.

**There is no race.** In the crashed regime the ordering is fixed: re-dispatch
(+5.5 s) → lease expiry (+25 s) → recovery resolution (+26.5 s).

### 1.5 Every exception that `classify_outcome` maps to `server_error`

```python
if error is not None:
    name = type(error).__name__.lower()
    if "timeout" in name:
        return TIMED_OUT
    return SERVER_ERROR
```

Any exception whose class name lacks "timeout" becomes `server_error`. On the
AEP dispatch path:

| exception | raised by | reachable on B0? |
|---|---|---|
| `LockAcquisitionError` | lease unavailable after 3 attempts; Redis transport fault; intent CAS `-3` (expired/mismatched lease token); state write `-3`; empty lock token; lease-helper argument validation | **no** — `uses_lease=False` |
| `IntentInvariantError` | intent CAS `-5`, incl. the uniqueness rule of §1.3 | **no** — no intent ledger |
| `IllegalIntentTransitionError` | intent CAS `-4` | **no** |
| `IntentStateError` | intent CAS operation failed | **no** |
| `StaleWriteError` | expected-version CAS `-1` | **no** — `uses_fenced_state_writes=False` |
| `Phase2StateProtectionError` | state write `-4` | **no** |
| `WriteAheadWorkflowError` | missing execution state, barrier failure, `request-preparation-rejected` | **no** |

**And the finding underneath all of them.** `experiments/baselines/common.py`'s
`transmit_once`:

```python
except MockLegacyApiAmbiguity:
    return Verdict.AMBIGUOUS
except Exception:
    # Any other connector failure is ambiguous too.
    return Verdict.AMBIGUOUS
```

**B0 catches `Exception` and returns a verdict.** It resolves; it does not
raise. `b0_naive_retry.py` raises only `ValueError` and `RuntimeError`, both at
construction.

So the entire **`error is not None` branch of `classify_outcome` is reachable
on `AEP_FULL` and, in practice, not on `B0_NAIVE_RETRY`.** The lease case is
one instance of a general asymmetry, not a special case.

`timed_out` and `server_error` remain reachable on both arms through the
*resolved* branch, which reads `transport_result` and `provider_status`. It is
the exception branch that only one arm can enter.

---

## 2. Verdict: (a) and (b), in layers — and the defect is neither

**The specific `LockAcquisitionError` observed is (a), a harness timing
artifact.** The replacement worker asks for a lease 5.44 s after the crash and
gives up 0.115 s later, with 19.5 s of TTL left. Nothing about AEP's semantics
was consulted; the protocol never got to answer.

**The refusal itself is (b), the protocol's intended answer.** Even with the
timing fixed, §1.3 shows the re-dispatch is refused — by the uniqueness
invariant, because the prior intent is `FIRED_UNCONFIRMED` and stays so. AEP
declining to re-send a payment whose fate is undetermined is the protocol
working exactly as designed. It is the whole point of AEP.

**A note on why the lease cannot simply be shortened.** `locks.py` enforces
`buffer_margin_seconds >= 15` and `ttl_seconds > buffer_margin_seconds`, so the
TTL can never go below about 16 s, while the respawn costs 5.3 s of process
startup. **The lease will always outlive the respawn by at least 10 s.** That
closes the obvious option before it is proposed.

**The defect is neither (a) nor (b): it is that both are reported to the agent
as `server_error`**, whose wording asserts *"the provider returned a server
error before applying it"* — when the provider never saw the request. The agent
makes its next decision on a false premise, and it is a premise only one arm
can be given.

---

## 3. DRAFT — amendment 9. **NOT COMMITTED**, offered for the author's ruling

> ### Amendment 9 (draft) — what an agent is told when nothing was sent
>
> **The fault, named:** amendment 6 §8's leak category. `classify_outcome`'s
> exception branch is reachable on `AEP_FULL` and structurally not on
> `B0_NAIVE_RETRY` (§1.5), and in the crashed regime it fires on every
> agent-authorised re-dispatch, telling the agent the provider returned an
> error it never saw.
>
> #### Option 1 — the replacement waits for the lease
>
> | | |
> |---|---|
> | **what changes, where** | harness only: the agent branch waits for the dead holder's lease to expire before the re-dispatch, using **`acquire_lease_or_wait`, which already exists** in `experiments/baselines/common.py` and is already used by B1, B2, B4 and `harness/composition.py`. Its bound is `default_lease_wait_seconds = lock_ttl_seconds + margin`. **No protocol semantics change, and no new mechanism.** |
> | **caller-visible result** | the re-dispatch reaches AEP's real answer — the uniqueness refusal of §1.3 — which still raises, still maps to `server_error`, and is **still false**. |
> | **amendment 4's two tests** | visible to a real caller: yes. Identical in range and path across arms: **no** — unchanged, the exception branch is still AEP-only. |
> | **per-run cap** | unchanged. Waiting costs no model call. |
> | **wall time** | **+≈19 s per crashed execution that the agent re-dispatches.** Stage 100 at 4 runs × 3 payments ≈ +2–3 minutes. |
> | **record left valid** | everything. Nothing already collected changes meaning. |
>
> **On its own it does not fix the defect.** It changes which exception fires,
> not that one does. Its value is that it makes the recorded refusal AEP's
> genuine answer rather than a startup-time artifact.
>
> **The helper's own docstring is worth quoting**, because it says what this
> wait measures: *"it is the throughput cost a lease imposes under crashes, and
> it is the whole of what B1's and B2's leases buy over B0 -- a delay, not a
> prevention."* The harness already treats this wait as a result rather than an
> inconvenience, and already returns the seconds waited.
>
> #### Option 2 — classify a local refusal as a new value
>
> *Included because it is the obvious move, and evaluated honestly.*
>
> | | |
> |---|---|
> | **what changes, where** | instrument only: a fifth `last_outcome` value, e.g. `not_sent`, for any failure raised **before** the request left the process. |
> | **caller-visible result** | *"your request was not sent"* — **true**, and the most informative thing that could be said. |
> | **amendment 4's two tests** | visible to a real caller: yes. Identical in range and by the same path on both arms: **NO.** B0 has no pre-dispatch gate — `transmit_once` swallows every failure into a verdict — so `not_sent` is reachable on AEP and on B0 never. |
> | **per-run cap / wall time** | unchanged. |
> | **record left valid** | everything, but every future collection carries a value that labels the arm. |
>
> **Recommended against.** It is the truthful option and it fails the
> constraint that matters most. A value only one arm can produce is a one-bit
> arm label in `last_outcome`, which is exactly what amendment 4 §2.3 excludes
> `intent_id` and `dispatch_attempts` for, and what amendment 6 §6 restated as
> a standing rule. Making it arm-neutral would mean giving B0 a pre-dispatch
> gate — **OUT OF SCOPE: that reshapes the system under test.**
>
> #### Option 3 — a refusal before transmission is not a dispatch
>
> | | |
> |---|---|
> | **what changes, where** | instrument only. If the system refuses before any bytes are sent, the harness records `planner_redispatch_refused` in the **event log** — the oracle's side of the wall — and the agent's `last_outcome` for the next turn remains `unknown_process_died`. |
> | **caller-visible result** | unchanged from before the attempt: *"you do not know whether it was sent, whether it arrived, or whether it was applied."* **True** — no bytes left the process, so nothing about the payment's fate changed. |
> | **amendment 4's two tests** | visible to a real caller: yes. Identical in range and by the same path on both arms: **yes** — the value set stays the same four, and `unknown_process_died` is reached on both arms by the same event, a crash. The arm-specific fact moves to the oracle's record, where arm-specific facts belong. |
> | **per-run cap** | unchanged; `MAX_DECISIONS_PER_EXECUTION = 2` already bounds re-asking. |
> | **wall time** | unchanged. |
> | **record left valid** | everything. It also makes stage 30's and the stub runs' `server_error` entries legible as what they were. |
>
> **Cost, stated plainly:** the agent can no longer distinguish "I chose not to
> send" from "I chose to send and the system would not let me". That is a real
> loss of fidelity — but it is a loss of fidelity about *the protocol*, which
> the oracle measures, rather than about *the provider*, which is what the
> agent is supposed to be reasoning over. And it is strictly better than the
> present state, where the agent is told something false.
>
> #### Recommendation
>
> **Option 3, and Option 1 with it if wall time allows.**
>
> Option 3 alone removes the false statement, keeps the four values and their
> arm-neutrality, costs nothing, and leaves every collected record valid. It is
> the smallest change that makes the instrument honest.
>
> Option 1 is complementary rather than alternative: it does not fix the
> mislabelling, but without it the refusal the harness records is an artifact
> of Python startup time rather than AEP's answer. If stage 100 is to say
> anything about what AEP does when an agent asks it to re-send, Option 1 is
> what makes the recorded answer AEP's. Its cost is about 19 s per re-dispatched
> execution and no model calls.
>
> Option 2 is the one to refuse, and refusing it is the point: the truthful
> value is the one that breaks the comparison.

---

## 4. Where else the same class can recur

Kept separate from the lease. **Every point where one arm can produce a
caller-visible outcome through a path the other structurally lacks.**

| # | path | arm | why the other arm lacks it |
|---|---|---|---|
| 1 | **the whole exception branch** of `classify_outcome` | AEP | `transmit_once` catches `Exception` and returns a `Verdict`; B0 resolves rather than raises (§1.5) |
| 2 | lease acquisition failure, all six sources | AEP | `uses_lease=False` |
| 3 | intent-ledger invariants — uniqueness, append-only, attempt, TTL, illegal transition | AEP | `writes_pre_dispatch_record=False`; no ledger |
| 4 | fenced-write refusals — `StaleWriteError`, state write `-3`/`-4` | AEP | `uses_fenced_state_writes=False` |
| 5 | durability-barrier failure (`WriteAheadWorkflowError` from `_confirm_barrier`) | AEP | `uses_durability_barrier=False` |
| 6 | request-binding / vault rejection surfacing as an exception | AEP | B0 builds bytes directly via `exact_bytes` and does not go through the binding service's failure path |
| 7 | **recovery** resolving an execution the worker never finished | AEP | `has_recovery_service=False`. Not caller-visible today — it reaches the oracle, not `last_outcome` — but it is the same asymmetry one layer out |
| 8 | `resume_reexecuting_crashed` vs `NEXT_EXECUTION` | B0 / AEP | closed by amendment 6 §4.3 on the agent branch; still live on the scripted and planned branches, correctly |
| 9 | the provider's fault stream | both | closed by amendment 8; verified paired |

**1 is the general case and 2–6 are instances of it.** Any future exception
added anywhere in `aep_core` lands in `server_error` on AEP and has no B0
counterpart, silently, without a test failing — because
`test_last_outcome_is_arm_neutral.py` tests `classify_outcome`'s mapping over
synthetic inputs and cannot see which inputs each arm can actually produce.

**7 is worth watching but is not a leak today**: recovery's verdict reaches the
oracle, and amendment 4 §2.3 already keeps `outcome_class` out of what the
agent sees.

**No remedy is proposed for any of these.** Naming them is what this report
does.

---

## 5. Verification

| | |
|---|---|
| live calls | **none**; cumulative USD 0.00359020 |
| harness or protocol code changed | **none** |
| committed | this report only |
| sources | `run-config.json`, `events.jsonl` and `events-recovery.jsonl` of `phase40-stub-paired-2026-09-22`; `aep_core/core/{locks,intents,intent_workflow,storage}.py`; `experiments/baselines/{common,b0_naive_retry}.py`; `experiments/harness/agent_loop.py` |
