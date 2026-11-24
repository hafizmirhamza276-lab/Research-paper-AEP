# Phase 54 — detection under record loss: does the barrier make the difference?

**Pre-registered 2026-09-24, before any code for it exists and before any data
is collected.** Committed first, as rule 5 requires, so that
`check_prereg_order.py` can establish by ancestry that this file predates its
data rather than by trusting a date in it.

**Author decision, 2026-09-24:** blocker B1 is answered by option (ii) of
`reports/b1-plan-2026-09-24.md` — rescope the wording first, then run this
cell — with option (iii)'s addition that the model's prediction is stated in
the manuscript as a falsifiable prediction.

---

## 1. The question

The paper claims that *detection* — no undetected duplicate and no lost effect —
comes from the pre-dispatch record and the no-re-entry transition table, **not**
from the durability barrier. Every cell collected to date either left the
record readable or never restarted the store, so the claim is established only
for faults that do not destroy the record.

**Does detection survive a fault that destroys the pre-dispatch record, and is
the barrier what makes the difference?**

## 2. The discriminating pair, and why `drop_writes` is the wrong fault

The project's own TLA+ model already answers this, and it contains its own
control. Holding the fault fixed and the `fsync` truthful:

| config | `BarrierEnabled` | `TruthfulFsync` | `SingleTimeline` | committed expectation |
|---|---|---|---|---|
| `formal/configs/b3-no-barrier.cfg` | FALSE | TRUE | TRUE | **pass** |
| **`formal/configs/b3-no-barrier-restart.cfg`** | **FALSE** | TRUE | **FALSE** | **fail `NoLostEffect`** |
| **`formal/configs/aof-rewind.cfg`** | **TRUE** | TRUE | **FALSE** | fail `P1_VersionMonotone` only — **`NoLostEffect` holds** |
| `formal/configs/write-loss.cfg` | TRUE | **FALSE** | FALSE | **fail `NoLostEffect`** |
| `formal/configs/write-loss-no-restart.cfg` | TRUE | FALSE | TRUE | pass |

`SingleTimeline = FALSE` enables the spec's `Restart` action, which is F3:

```
Restart ==
    /\ ~SingleTimeline
    /\ store' = disk
```

— the in-memory store is replaced by the durable prefix.

**Rows 2 and 3 are the experiment.** Barrier off and the store rewinds: the
effect is lost. Barrier on and the same rewind: it is not. The barrier is
exactly what separates them.

### Why this cell must use `error_writes` and not `drop_writes`

**`drop_writes` would make both arms lose and separate nothing.**
`drop_writes` is the *lying* fsync — `TruthfulFsync = FALSE` — which with a
restart is row 4, `write-loss.cfg`, and that row **expects `NoLostEffect` to
fail with the barrier enabled**. Concretely:

- **AEP-full** issues `WAITAOF`, which returns success because the device lies;
  it dispatches; the restart rewinds past the record; the effect is lost.
- **B3** issues no `WAITAOF`, dispatches, and loses the record the same way.

Both arms lose. The cell would produce a null that means nothing about the
barrier. This is recorded here because it is the cell the external audit of
2026-09-23 proposed, and running it as proposed would have cost two days and
measured nothing.

**`error_writes` makes the device fail writes honestly.** The `WAITAOF` the
barrier issues then **fails**, so AEP-full withholds dispatch and has no effect
to lose, while B3 — which never asks — dispatches and then loses its record to
the rewind. That is rows 2 and 3, realised on this host.

**What this cell therefore establishes, stated precisely.** For AEP-full the
mechanism that protects it here is *prevention* — the barrier withholding on a
failed acknowledgement — not the durability of a record that survived. A clean
result **reassigns** the claim rather than restoring it: it shows the barrier
matters under F3, by withholding. The manuscript must say that in those terms
and must not claim the barrier made the record survive.

## 3. Scope, fixed in advance

| | |
|---|---|
| systems | `AEP_FULL` and `B3_INTENT_NO_BARRIER`, two arms, paired |
| regime | `write-loss-restart` — a new regime; the device fails writes, then Redis is killed and restarted |
| fault mechanism | `dm-flakey` `error_writes`, armed at the fault point |
| restart trigger | the existing `kill_and_restart` path: `docker kill -s KILL` then `docker start`, with the post-restart `uptime_in_seconds` verification the `redis-kill-*` regimes already perform |
| ordering | arm the device → the intent write and (for AEP-full) the `WAITAOF` → dispatch decision → kill Redis → restart → recovery reads the replayed AOF |
| `appendfsync` | `everysec`. **`always` would make the cell vacuous** — the record would be on disk before the fault |
| capability class | `NO_READBACK` only. A lost effect is observable only where nothing can be reconciled afterwards |
| keying | `CALLER_REFERENCE` |
| crash point | none. The fault is the store's, not the worker's |
| runs | **30 per arm** |
| executions | **10 per run — 300 per arm, 600 in the cell** |
| seed | **20260806**, the seed the existing cells use |
| tiers | ≤ 4 |

Run and execution counts match `reports/raw/ws4-writeloss-s1-2026-09-07`
exactly (`\WriteLossRunsPerArm` 30, `\WriteLossExecPerArm` 300) so the two
cells can be read side by side.

**Why 300 executions per arm is enough for what is claimed.** The prediction is
a separation on a binary per-execution outcome, not an estimate of a rate. At
300 executions a true B3 lost-effect rate of even 5% makes an observed zero
essentially impossible, so **B3 at 0/300 is a genuine refutation and not an
underpowered null**. AEP-full at 0/300 gives a one-sided 95% Wilson upper bound
of 1.0%, the same form the paper already uses for its zero-event bounds.

## 4. The prediction

**Taken from the model, not from a hope, and fixed before any data exists.**

> **Barrier off, the effect is lost. Barrier on, it is not.**
>
> * `B3_INTENT_NO_BARRIER`: **lost effects strictly greater than 0** in 300
>   executions.
> * `AEP_FULL`: **0 lost effects** in 300 executions.

Derived from `b3-no-barrier-restart.cfg` (`EXPECT: fail NoLostEffect`) and
`aof-rewind.cfg` (`NoLostEffect` among its invariants and not among its
expected failures). Both files are committed and unchanged; their blobs are
pinned by `reports/prereg-blobs.json`.

Secondary, recorded but not the prediction: AEP-full's `dispatch_attempts` and
`executions_with_an_applied_effect` are expected to be **0**, because the
barrier withholds. If AEP-full dispatches at all under this fault, the
mechanism is not the one described in §2 and §6 applies.

## 5. What each outcome establishes

| outcome | what it establishes |
|---|---|
| **AEP 0/300, B3 > 0/300** | The prediction holds. Detection does **not** survive record loss without the barrier, and the barrier is what prevents it. Every unscoped statement listed in `reports/b1-plan-2026-09-24.md` §1.2 must be rescoped, and the paper gains a positive, two-sided decomposition |
| **Both > 0/300** | The barrier does not help under this fault either. The claim is false under F3 **and** the barrier's value there is not established. Both are narrowed. Reported as such |
| **AEP > 0, B3 = 0** | Contradicts the model in the opposite direction. Treat as an instrument fault, stop, and report it as a defect in the cell rather than a finding about the protocol |
| **Both 0/300** | **Void by default — see §6.** Only promotable to a real null if every delivery check in §6 passes |

**On refutation.** A refuted prediction is reported as refuted, in the phase
report and in the manuscript if the manuscript says anything at all about this
cell. This phase will not be re-run to obtain a different answer. If the
prediction is refuted the honest conclusion is that the model's row 2 does not
describe this host, and *that* is the finding.

## 6. The instrument hazard, named in advance

**`dmsetup suspend` calls `freeze_bdev()`, which syncs the filesystem.** The
existing provisioning already guards this — `experiments/flakey_write_loss.py`
reloads with `suspend --noflush --nolockfs` — but the hazard is that a sync at
the wrong moment flushes the very record the cell is trying to lose, and the
result is **both arms at zero, which looks exactly like the claim being
vindicated.**

**A both-arms-zero result is an instrument failure and not evidence, unless
all four of these hold.** Each is recorded per run, and a run failing any of
them is **void**, reported with its reason, and excluded with the cell reported
at the reduced n rather than re-run:

1. **The table declares the fault.** `dmsetup table` read back after arming
   names `error_writes`. Issuing a reload and the reload taking effect are
   different events.
2. **The canary write FAILED.** A key written to Redis after arming must
   return an error. `error_writes` is an honest failure, so this is directly
   observable — which is why this fault is a better instrument than
   `drop_writes`, whose canary can only be checked after the fact.
3. **The restart actually happened.** `uptime_in_seconds` after the restart is
   small, and the container id is unchanged — the same check
   `restart_after_hard_kill` already performs.
4. **The canary key is ABSENT after the restart.** If a key written after
   arming survives the rewind, writes were reaching the platter and the fault
   did not land. This is the direct test for the `freeze_bdev` sync.

**If checks 1–4 pass and both arms are still at 0/300, that is a real null**
and refutes the prediction under §5 row 2. If any fails, the cell is void.

`reports/raw/ws4-writeloss-s1-2026-09-07`'s `R10` gate is the inverse of check
3 and is reused with its sense flipped: WS-4 required that Redis **not** have
restarted, and voided a run where `coordinator_restarted_unexpectedly` was
true. **Here the restart is the experiment**, so a run in which it did not
happen is void.

## 7. Not pooled, with anything

**The load-bearing constraint, as in phase 53.**

1. This is a **2026-09-24 session** on a fault no other cell used. It is
   **not pooled** with the WS-4 write-loss cell, with the matrix, with the
   `redis-kill-*` regimes, or with phase 53.
2. It is reported **as its own session**, with its own macros, its own n and
   its own date.
3. **No macro mixes this collection with any other.** No rate is computed over
   a union.
4. Any comparison against WS-4's cell is a **between-session** comparison of
   two different faults and is labelled as such. It is not a paired test.

## 8. Analysis, fixed in advance

**Reported, per arm and pooled within this collection only:** `lost_effect`
count and rate; `undetected_duplicate` count and rate; `dispatch_attempts`
distribution; `executions_with_an_applied_effect`; the count of runs and
executions; every void run with its reason and which of §6's four checks it
failed.

**Not reported from this collection:** timing. The host is not declared
suspend-disabled for this cell, so the E5 gate contributes nothing and **no
latency macro may take a value from here.**

**Zero-event bounds** use the same one-sided 95% Wilson form the paper already
uses, at execution level, with the clustering caveat the paper already states.

## 9. Stop rule

* **Stop and report** on any harness error, any refusal by the runner, any
  device that cannot be armed or restored, or any run that leaves the dm
  device suspended.
* **Stop** if more than **6 of 60 runs** (10%) are void under §6. A cell that
  cannot deliver its fault nine times in ten is an instrument problem, and
  continuing would produce a number whose denominator is the real finding.
* The device is restored to pass mode between runs; a run that begins already
  armed is refused, as the existing write-loss path already refuses one.
* **One collection.** This phase is not re-run to obtain a different answer.

## 10. What the manuscript may say, per outcome

Fixed before the data, so that the reporting rule is not chosen after seeing
it.

| outcome | permitted |
|---|---|
| prediction holds | The rescoped claim, plus this cell as the measured boundary. The decomposition becomes two-sided: the record delivers detection under record-preserving faults, the barrier under record-destroying ones **by withholding** |
| both arms lose | The rescoped claim, plus: under record loss neither arm detects, so the barrier's value does not extend to this fault |
| real null (§6 checks pass) | The rescoped claim stands unqualified for this fault too, and the model's row 2 is recorded as not describing this host |
| void | **Nothing.** A void cell produces no manuscript sentence. It is reported in `reports/` and the claim stays rescoped-and-untested, which is option (i) of the B1 plan |

**In every case the wording of §1.2's eight unscoped statements is corrected
first**, by the rescope that precedes this collection. This cell does not
license leaving them as they are.

## 11. Where the outputs go

| | |
|---|---|
| collection root | `experiments/results/b1-record-loss-2026-XX-XX` |
| report | `reports/phase-report-54-record-loss-restart-2026-XX-XX.md` |
| gate entry | `scripts/check_prereg_order.py`, `EXPECTED`, naming this file |

The date suffix is left open because the collection has not been scheduled;
the `EXPECTED` entry is added with this commit so the gate sees the root the
moment data lands.
