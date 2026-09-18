# Amendment 4 — the loop observes an outcome, and the cap is re-derived

**Amends `prompts/phase-40-agent-reachability.md`** §1 (the turn structure) and
§3 (the per-run cap). The pre-registration is not edited. Written and committed
**before any live call on the interactive loop**.

---

## 1. The gap this closes

§1 says three decision turns are "enough to plan, observe an outcome, and
re-plan". The middle step did not exist. `agent_worker_items` asked the planner
for every turn, built the whole workload, and only then handed it to
`worker.py`; at decision time nothing had run, so there was no outcome to
observe and there never could be in that shape.

The first corrected live stage shows what that cost. Both agents reasoned about
ambiguity — *"prior non-idempotent capture attempts may already have
applied"* — but they were reasoning from the tool description, not from an
observation, because nothing had told them anything had happened. What the
stage measured was **an LLM choosing calls**. What the paper claims is **an LLM
re-planning after an ambiguous outcome**, and running 30 calls through the old
loop would have collected more of the former.

## 2. What the agent is told: `last_outcome`

The test applied to every candidate field: **would a caller of this provider
have it, whichever system it is using?** Failing either half — not
caller-visible, or visible on only one arm — excludes it.

### 2.1 Included

| field | why a real caller has it |
|---|---|
| `result` | `timed_out`, `server_error`, `acknowledged`, `unknown_process_died`. Derived from the transport alone: no response within the timeout; a 5xx; a 2xx; or the process died before an answer arrived. Every caller of every HTTP provider has exactly this and nothing finer. |
| `turn` | Bookkeeping, so an outcome cannot be read against the wrong call after a respawn. Not evidence. |

### 2.2 `rejected` was approved and is **not** included, because the check failed

A fourth value `rejected` (4xx) was proposed and approved on the reasoning —
correct in general — that a real caller distinguishes "definitely didn't
happen" from "don't know", and that collapsing the two would manufacture
ambiguity rather than measure it. That reasoning is recorded here because it
governs any future addition.

It was made conditional on 4xx being reachable identically on both arms. **It
is not**, and the check found two independent reasons:

1. **There is no injected 4xx fault.** `experiments/mock_api/service.py` injects
   exactly three: `server_error` ("refuse **before** applying, with **503**"),
   `timeout`, and `duplicate_response`. The mutation route's 4xx paths — 400
   unparseable, 404 unknown endpoint, 422 unidentifiable — fire only for
   malformed requests, which the harness never sends.
2. **Where a 4xx is reachable in normal operation, it is AEP-only.** The 409s
   and 422s live on the **read-back** routes, and `B0_NAIVE_RETRY` performs no
   read-back at all. A `rejected` value could therefore appear on one arm and
   never on the other — precisely the leak class §2.3 excludes
   `dispatch_attempts` for.

So `rejected` is folded into `server_error`, and nothing is lost by it: in this
harness **503 already means refused before applying**. The
definitely-didn't-happen distinction the approval was protecting is preserved —
it is carried by `server_error`, not by a status code that never arrives.

### 2.3 Excluded, and this is a standing constraint

| field | why it is out |
|---|---|
| `outcome_class` | The oracle's verdict in the oracle's vocabulary. `DECLARED_AMBIGUOUS` is the answer the experiment asks the agent to reach unaided. |
| `request_fingerprint` | Literally the oracle's identity function — what amendment 3's guard exists to keep the agent away from. |
| `status` | An `IntentStatus` under AEP, a baseline's own string under B0. **Different vocabulary per arm.** |
| `dispatch_attempts` | 1 under AEP by construction, higher under B0 when it retries. **The most direct arm label there is.** |
| `intent_id` | Exists only under AEP. Its presence or absence is a one-bit arm label. |

**The standing constraint, which governs anything added to `last_outcome`
later:**

> **An agent that can tell which arm it is in is a second uncontrolled
> variable, and the comparison stops meaning anything.**

The experiment runs one fixed caller against two systems and attributes the
difference in outcomes to the systems. An agent able to infer "I am on the
naive baseline" may reason about duplicates it was never told about, or behave
more cautiously under AEP because it has noticed the protocol. Either way the
caller is no longer fixed, the two arms are no longer comparable, and the
result measures the agent's inference rather than the protocol's effect.

Three of the five exclusions above are on those grounds rather than on
oracle-leak grounds, and that distinction was not obvious: `dispatch_attempts`
looks like innocuous transport metadata and is in fact the cleanest arm label
in the record.

**Any field added to `last_outcome` in future must pass both tests — visible to
a real caller, and identical in range across both arms.**
`tests/test_last_outcome_is_arm_neutral.py` pins the second one: the set of
values `last_outcome` can carry is asserted identical for `AEP_FULL` and
`B0_NAIVE_RETRY`, so a future field that leaks arm identity fails a test rather
than being caught by a reader.

## 3. What a respawned agent sees

`result: unknown_process_died`, worded to the planner as *"You issued this call
and your process then stopped. You do not know whether it was sent, whether it
arrived, or whether it was applied."*

That is the exact position of a caller that crashed mid-call, and it is the
most interesting state in the experiment.

**The replayed observation is derived from the transcript, never from the event
log.** The respawned worker has `events.jsonl` in front of it, containing the
`execution_resolved` record for the turn the original agent died during.
Reconstructing the observation from that log would hand the replacement agent
the answer — arriving after the death that was supposed to deny it — and every
decision after it would be worthless as evidence. The transcript holds
decisions and observations the agent actually received; the event log is the
oracle's record and stays on the oracle's side of the wall.

A turn with a recorded decision and no recorded observation is
`unknown_process_died`.

One durability detail, verified rather than assumed: `Transcript.append` writes
and closes without `fsync`, but `SIGKILL` ends the *process*, not the host, so a
completed append survives in the page cache. A decision is lost only if the kill
lands inside the write itself — at most one per lifetime, which is what the `+L`
term in §4 pays for.

## 4. The per-run cap, re-derived: 36 → 28

§3's 36 was `3 turns × (1 call + 1 malformed retry) × 2 post-crash re-entry ×
3 attempts per call`. Two factors no longer hold: the transport is
`httpx.HTTPTransport(retries=0)`, so the ×3 is gone, and replay means a respawn
re-asks nothing already decided, so the ×2 is gone.

`(T + L) × A × W`:

| term | value | source |
|---|---|---|
| `T` turns | 3 | §1 |
| `A` attempts per decision | 2 | one call, one malformed retry — what `_ask` does |
| `L` lifetimes | 4 | `REEXECUTE_CRASHED` re-executes without re-crashing, so lifetimes ≈ executions + 1. Observed 3 and 2 in the live retry |
| `W` workers | 2 | the collected default |

`+L` rather than `×L` is the point: a respawn replays, so it costs new calls
only for the at-most-one decision a kill can land inside.

**(3 + 4) × 2 × 2 = 28.**

**This is a tightening, and the reason matters.**
`MAX_ATTEMPTS_PER_WORKER = 64` — a worker slot may burn 64 lifetimes before the
runner gives up. A pathological respawn loop could therefore reach
`64 × 2 × 2 = **256** calls in a single run`. **The per-run cap is the only
thing standing in front of that number.** At 28 it stops nine times sooner than
36 would, and 36 was never derived with 64 lifetimes in view.

**The collection-wide numbers do not move.** Worst case 20 runs × 28 = 560,
under §3's 1 000. Expected is far lower: 20 runs × 2 workers × 3 turns ≈ 120
calls for the entire design. The USD ceiling is untouched at
1 000 × $0.0016288 ≈ $1.63, well under $20.

## 5. What changes in the code, and what does not

The interactive path is a **third branch**, beside the scripted one and the
plan-then-execute agent one:

| branch | when | status |
|---|---|---|
| scripted | `AEP_PLANNER_MODE` absent or `scripted` | **character-for-character unchanged** |
| agent, planned | agent mode, `AEP_PLANNER_LOOP` absent or `planned` | unchanged; it is what the stub stage validated |
| agent, interactive | agent mode, `AEP_PLANNER_LOOP=interactive` | new |

`AEP_PLANNER_LOOP` is orthogonal to `AEP_PLANNER_MODE`, so the interactive loop
can be exercised in **stub mode at zero cost** before it is ever run live.

`tests/test_scripted_plan_is_frozen.py` still recomputes 51 already-collected
runs and compares against what they recorded. The counter, the transport, the
caps mechanism, amendment 3's amount guard and the empty-run gate all sit below
the loop and are untouched.

## 6. What is unchanged in the pre-registration

§1.1's harness-assigned target, §2's metric and its prohibition on rates, §3's
other four controls, §4's `PLANNER_FILTERED`, §6's staging, §8's failure
definitions, §9's stop rule. Amendments 1, 2 and 3 stand in full.
