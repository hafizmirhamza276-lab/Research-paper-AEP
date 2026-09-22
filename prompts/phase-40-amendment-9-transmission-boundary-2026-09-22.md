# Amendment 9 — a caller-visible outcome begins at transmission

**Amends `prompts/phase-40-agent-reachability.md`** §1 and amendment 4 §2, for
the **agent branch only**. Committed before the code that implements it.

**Justified under amendment 6 §8 as the leak category**: arm-specific paths to
caller-visible outcomes. It also closes a false statement made to the agent.
Amendment 6 §8 still governs — further amendments require a **named** crash,
leak or malformed path.

**Option 1 of `reports/phase-report-40-lease-refusal-2026-09-22.md` §3 was
rejected by the author** and is not adopted: making the agent branch wait for
the lease would change `AEP_FULL`'s lock-acquisition policy for phase 40 only,
and the system under test would then no longer be the matrix's `AEP_FULL`.
**Option 2 was rejected** for the reason the report gives: a value only one arm
can produce is a one-bit arm label.

**The claim that AEP refuses a re-dispatch anyway, after the lease expires, is
therefore not asserted. It is tested** — §6.

---

## 1. The rule, as a principle

Not a lease patch. The lease is one instance.

> **A caller-visible outcome is derived from whether TRANSMISSION to the
> provider occurred, and from nothing else.**
>
> 1. **A refusal before transmission is not a dispatch.** It produces **no new
>    observation**. The agent's knowledge state for that payment remains
>    exactly what it was.
> 2. **After transmission, only the transport result counts**: `timed_out`,
>    `server_error`, or `acknowledged`.
>
> What refused the request before transmission — a lease, an invariant, a
> fence, a barrier, a binding — is **the oracle's business and never the
> agent's**. It is recorded in the event log and never in `last_outcome`.

This replaces the rule the implementation actually had, which was *"any
exception that is not named `*Timeout*` is a `server_error`"* — a rule about
Python class names rather than about what happened.

## 2. The boundary is `docs/31`'s transmission event, and it is the right one

`docs/31-transmission-event.md` §1: `provider_request_transmitted` is emitted
on entry to `MockLegacyApiConnector.mutate`, and

> *"the event is **the last observable point at which no provider byte can have
> left** — an instruction boundary, not an approximation of one."*

The workflow states the same boundary from the other side
(`intent_workflow.py:574-578`):

> *"a process cut before this line has provably not dispatched; a process cut
> **after** this line may have."*

**That is exactly the distinction this amendment needs**, and it already
exists, is already emitted, and is already pinned by six tests. `docs/31` §2
records that the observer changes no protocol behaviour: it is a passthrough
that re-raises exceptions as themselves.

**One qualification, stated rather than glossed.** The observer wraps `mutate`,
which is the AEP path; `B0_NAIVE_RETRY` reaches the provider through
`connector.transmit` inside `transmit_once` and emits no such event. The
*boundary* is right for both arms; the *event* is currently emitted on one. §4
is why that costs nothing here, and §7 records it as a limit.

## 3. The nine points of the report, classified

`reports/phase-report-40-lease-refusal-2026-09-22.md` §4 listed every point
where one arm can produce a caller-visible outcome by a path the other lacks.

| # | point | pre- or post-transmission | code path |
|---|---|---|---|
| 1 | the whole exception branch of `classify_outcome` | **both** — it is the subject of this rule, not an instance | `agent_loop.classify_outcome` |
| 2 | lease acquisition failure, 3 attempts exhausted | **pre** | `intent_workflow._acquire_with_jitter`, before `create_intent` and long before `mutate` |
| 2b | lease failure via intent CAS `-3` / state write `-3` (fencing) | **pre on creation, post on resolution** — see §4 | `intents` CAS, `storage` write |
| 3 | intent-ledger invariants (uniqueness, attempt, append-only) | **pre** on `create_intent`; the resolution transitions the *same* intent and cannot breach uniqueness | `intents._ledger_keys_and_uniqueness`, CAS `-5` |
| 4 | fenced-write refusals (`StaleWriteError`, state write `-4`) | **pre on seeding, post on resolution** — see §4 | `storage.save_state` |
| 5 | durability-barrier failure | **pre** | `intent_workflow._confirm_barrier`, before `AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION` |
| 6 | request-binding / vault rejection | **pre** | `binding_service.prepare`, before the intent is created |
| 7 | recovery resolving an unfinished execution | **neither** — not caller-visible; it reaches the oracle | `intent_recovery` |
| 8 | `resume_reexecuting_crashed` vs `NEXT_EXECUTION` | **neither** — closed by amendment 6 §4.3 on this branch | `runner.resume_from_index` |
| 9 | the provider's fault stream | **post**, and **symmetric** — closed and verified by amendment 8 | `mock_api.service.draw_faults` |

**Everything that can refuse an AEP dispatch before any byte leaves is
pre-transmission**, and under §1 produces no observation. That is the whole of
the asymmetry the report found.

## 4. The post-transmission cases, and why no mapping is invented for them

Points 2b and 4 have a post-transmission form: `mutate` returns, and the
resolution write at `intent_workflow.py:628` then fails because the lease has
expired underneath it. A caller would have transmitted and then learned
nothing. B0 has no such step and cannot reach it.

**The author's instruction is to stop and flag any such point rather than
invent a mapping. It is flagged, and it is also not reachable**, which is
stated with its numbers rather than asserted:

| | |
|---|---|
| `lock_ttl_seconds` | 25 |
| `buffer_margin_seconds` | 15 |
| `client_timeout_seconds` | 5 |
| Timeout Invariant | `T_client <= ttl - buffer` → `5 <= 10` ✓ |
| slack before the lease could expire mid-execution | **20 s** |

`locks.py` **enforces** the invariant rather than documenting it: it raises
`LockAcquisitionError` if `buffer_margin_seconds < 15`, if
`ttl_seconds <= buffer_margin_seconds`, or if
`client_deadline_seconds > ttl_seconds - buffer_margin_seconds`. A run that
violated it would not start.

So with a 5-second client deadline inside a 25-second lease, the lease cannot
expire between `mutate` and the resolution write. **No mapping is invented for
these cases because they cannot occur while the invariant holds**, and if the
invariant is ever changed they become reachable and require their own ruling.
`tests/test_transmission_boundary.py` asserts the invariant holds for the
phase-40 configuration, so a future change to those numbers fails a test rather
than silently opening the case.

## 5. The agent-facing wording must be true — and one line of it was not

§1 makes the absorbed re-dispatch produce no observation, so the next text the
agent sees is **byte-identical to what it would have seen had it declined**.
The question is whether that text was true. One clause was not.

**Before**, `build_prompt` wrote:

```
Your previous call: your process then stopped. You do not know whether it was
sent, whether it arrived, or whether it was applied.
```

After an absorbed re-dispatch the agent *has* made a more recent decision, and
that decision's process did **not** stop — it was refused before transmission.
So `Your previous call:` names the wrong event, and `your process then stopped`
is false of it.

**After.** Two changes, both narrow:

* the label names the **payment**, not "your previous call", because
  amendment 6 already made the re-decision about the same payment:
  * on a re-decision: `What you know about this payment:`
  * on a new payment's first decision: `What you know about the previous payment:`
* `unknown_process_died`'s wording becomes a statement about the payment rather
  than about the most recent decision:

  > `your process stopped while a call for it was in progress. You do not know
  > whether it was sent, whether it arrived, or whether it was applied.`

Every clause is then true after an absorbed re-dispatch: the process *did* stop
while a call was in progress, and the three unknowns are still unknown, because
the absorbed attempt sent nothing and therefore changed nothing.

The other three are unchanged and were already true of the payment:
`timed_out`, `server_error`, `acknowledged`.

**Neither wording tells the agent that a refusal happened**, which is the
point: that fact is arm-specific and belongs to the oracle.

## 6. The claim about post-expiry refusal is tested, not asserted

The author's ruling requires it. `tests/test_transmission_boundary.py` drives
the real workflow against a real Redis and a real provider:

* an execution is dispatched and its intent left `FIRED_UNCONFIRMED`;
* the lease is allowed to expire — not shortened, **waited out** — so that
  lease acquisition succeeds;
* the same payment is dispatched again;
* the test asserts it is **refused by the intent-uniqueness invariant**, and
  that the provider's ledger shows **nothing was transmitted** by the second
  attempt.

If AEP were in fact to re-send after expiry, that test fails and this
amendment's §1 has mis-described the system. It is the tested form of *"it
would refuse anyway"*.

## 7. What is recorded, and where

**The oracle sees the absorbed re-dispatch. The agent never does.**

On absorption the event log receives `planner_redispatch_absorbed`, carrying
the execution, the decision index, and **the cause** — the exception class that
refused it. The run's counts therefore show that the planner chose to
re-dispatch and that nothing was sent, which is what a reader needs in order to
interpret a run in which an agent said "send again" and no effect appeared.

`planner-observations.jsonl` records nothing for an absorbed attempt, because
there was no observation. A decision with a recorded transcript entry and no
observation is already amendment 6 §3.2's signal for the crashed decision; an
absorbed re-dispatch is the last decision for its payment under
`MAX_DECISIONS_PER_EXECUTION = 2`, so it is never re-asked and the two cannot
be confused.

**A limit, recorded rather than discovered later.** §2 notes the transmission
event is emitted on the AEP path only. The implementation therefore treats an
*undetermined* transmission as **transmitted**, not as absorbed: absorbing an
unknown case would hide a real failure, and the safe direction is to report the
transport result. B0 never reaches the exception branch at all — `transmit_once`
catches `Exception` and returns a `Verdict` — so the undetermined case does not
arise there today, and `tests/test_transmission_boundary.py`'s reachability
test is what would notice if it ever did.

## 8. What is unchanged

§1's design, §1.1's harness-assigned target, §2's metric and its prohibition on
rates, §3's controls, §4's `PLANNER_FILTERED`, §5's transcript requirements,
§6's criteria and staging, §8's failure definitions, §9's stop rule as amended
by amendment 5.

Amendments 1–8 stand in full. **`AEP_FULL`'s lock-acquisition policy is
unchanged**, no protocol code is touched, the scripted branch and the matrix
are character-for-character as they were, and every collected `config_digest`
is unmoved.
