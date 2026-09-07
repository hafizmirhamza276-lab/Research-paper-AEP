# Phase 14 / WS-4: the block-level write-loss cell

**Collected 2026-09-07** (`252e2d3`), read with `scripts/analyse_write_loss.py`
unmodified (`1d13868`). This closes the workstream `docs/24` B1 opened.

**This cell is evidence about Redis, not about the protocol.** Everything below
follows from that, and it is the reason the write-up is not organised around a
prevention result.

---

## 1. What was collected

60 runs, exactly as `d8b2ca5` pre-registered: 30 per arm × 10 executions,
`AEP_FULL` and `B3_INTENT_NO_BARRIER`, `ledger_postings` (`NO_READBACK`) only,
regime `write-loss-preack`, the fault delivered by `dm-flakey drop_writes` armed
at the intent CAS, before the barrier. `run_matrix rc=0`; every row
`status=collected`; zero aborts. Attempt 5 of a maximum of 6 under §10 of the
blocked report.

The fault was delivered. The device table read
`0 1048576 flakey 7:0 0 0 1 1 drop_writes` during collection, and non-delivery
never approached the pre-registered 5% void threshold.

## 2. The result

| arm | executions | applied | rate | lost effects | undetected duplicates | declared ambiguous |
|---|---|---|---|---|---|---|
| `AEP_FULL` | 300 | 285 | **0.9500** | **0** | **0** | 49 |
| `B3_INTENT_NO_BARRIER` | 300 | 287 | **0.9567** | 0 | **0** | 61 |

The pre-registration predicted AEP-full at or near **0** and B3 at or near
ceiling. Both arms are at ceiling. On the numbers the prediction is **refuted**.

And the numbers are not the finding.

## 3. What actually happened: a durability acknowledgement that was false

`observe_behaviour()` classified all 30 AEP-full runs as
**`SILENT_APPEND_FAILURE`**: `durability_acks_after_the_fault: 300`,
`post_fault_failures: 0`.

**`WAITAOF` returned success 300 times out of 300 after block-level write loss
had already made the append impossible.**

The chain is mechanical, and every link is doing what it is specified to do:

1. `dm-flakey drop_writes` **silently discards** each write bio and reports
   success. That is the target's definition, not a malfunction.
2. The kernel therefore sees no error. `write(2)` succeeds; so does `fsync(2)`.
3. Redis, running `appendfsync everysec`, has no way to learn otherwise, and
   `WAITAOF` reports the append durable.
4. AEP's barrier is told the record is durable, so it dispatches.

The barrier withholds dispatch on a **failed or absent** durability
acknowledgement. It received a successful one, 300 times. It behaved exactly as
specified, on an input that was false.

## 4. What this cell shows, and what it does not

**It does not show the barrier fails to withhold under write loss.** The
condition the cell exists to test — the barrier meeting a durability
acknowledgement that does not arrive, or arrives as a failure — **was never
reached.** No run presented the barrier with the input its guarantee is defined
over.

**It does not show the barrier works.** Nothing here exercised withholding at
all. A reader who wants evidence for the barrier under write loss will not find
it in this cell in either direction.

**It shows a durability acknowledgement that was false, and therefore that the
protocol's guarantee is only as good as the acknowledgement it rests on.** AEP's
durability argument has an unstated premise: that `WAITAOF` success means the
record is on the device. Under a storage stack that discards writes silently,
that premise is false, and every guarantee built on it inherits the falsehood.
No amount of protocol correctness recovers it — the protocol cannot detect a lie
told beneath it.

**This is a sharper result than the prediction would have been, and it is worth
saying so plainly** (`docs/26` §3 rule 11). Had the prediction held, the cell
would have shown that a barrier withholds when its precondition fails — which is
what a barrier is *for*, and close to true by construction. What it produced
instead is a boundary on the guarantee that no confirmatory run could have
found: it identifies the assumption the whole durability argument rests on and
shows it is not self-checking. That is a contribution about the interface between
a protocol and its store, and it is more useful to a practitioner than a
successful prediction would have been.

### 4.1 Two pre-registered exact quantities did hold

They are not weakened by anything above, and they belong in the record:

* **`lost_effect_executions = 0` for AEP-full.** Predicted exactly.
* **`undetected_duplicate_applications = 0` for both arms.** Predicted exactly.

So the cell's headline prediction was refuted while both of its exact
point-predictions were met. Nothing dispatched twice without being noticed, and
nothing was lost.

## 5. Why a REFUTED verdict is credible here

`scripts/analyse_write_loss.py` was **written and committed before any
write-loss data existed** and was run **unmodified** against this session, with
its thresholds, its behaviour classifier and `classify_reading()` all fixed in
advance — which is the only reason a refutation reported by the same person who
made the prediction is worth anything.

`d8b2ca5` **enumerated this behaviour in advance** as one of three plausible
Redis responses when its AOF device fails, and flagged this one specifically as
the one that *"would complicate the reading"*. `classify_reading()` exists so the
script could say so on its own, and it did:

> **READING: REFUTED, and the third Redis behaviour was observed:** WAITAOF
> acknowledged after the device stopped accepting writes. Whatever the numbers
> say, they were not produced by the mechanism the prediction describes.

The interpretation in §3 is not a rescue constructed after an unwelcome number.
It is the reading the pre-registration named before the number existed.

## 6. Scope, and what would change the answer

**One host, one Redis version, one fault emulation.** Redis 7.2.5,
`appendfsync everysec`, `dm-flakey` on a loop device on WSL2. Nothing here
generalises to other stores or other Redis configurations without being run
there.

**The false acknowledgement is a property of this fault class, and that is a
real class, not an artefact.** `drop_writes` was chosen precisely because it
emulates storage that discards silently — the failure mode of a device or
volatile write cache that acknowledges a flush it did not perform. A storage
stack that returns `EIO` instead would let `fsync(2)` fail and `WAITAOF` report
it, and the barrier would then meet the input its guarantee is defined over.
**So this cell bounds the guarantee to storage that reports its own failures**,
and says nothing about storage that does.

**What it does not license.** No claim that AEP is unsafe, and none that it is
safe under write loss. The honest statement is that under silent write loss the
protocol is blind, along with everything else above the block layer.

## 7. Relation to the existing write-loss probe (§VI, `sec:eval-durability`)

They test **opposite orderings** and do not conflict:

* the existing probe acknowledges through `WAITAOF` **before** arming
  `drop_writes`, and finds the acknowledged record survives — *acked before the
  loss ⇒ durable*, which is true;
* WS-4 arms `drop_writes` **first**, at the intent CAS, and the acknowledgement
  arrives **after** — *acked after the loss ⇒ meaningless*.

Together: an acknowledgement is trustworthy only if the loss began after it.
Neither probe alone says that.

## 8. Findings recorded, deliberately not fixed in the reading pass

* **`analyse_write_loss.py:200`** reads `applied_effects_total` from
  `matrix-progress.jsonl`, where that key does not exist (`summary` there is a
  path string; the column of that name is in `redis-kill-ablation.csv`). The
  per-run column is zero by construction and contradicts the totals above it.
  Display only — the verdict path never touches it. Left unedited because the
  script's value is that it predates the data. By rule 13 the column is
  decoration and should be made real or removed. **Separate prompt.**
* **Regime-label drift**: the analysis labels this cell `redis-kill-preack`
  rather than `write-loss-preack`. Known, recorded, **separate prompt**.
* **R12** (`docs/25`): orphaned providers on 8099 survive teardown. Twice.
* **R12a**: unexplained container restarts, third occurrence, did not touch the
  data, not chased.

## 9. Status

**WS-4 is complete, not cut.** §10's cut condition was not reached: attempt 5
produced a full 60-run session. `docs/24` B1's fault-delivery question is
**answered for this host** — the fault is deliverable, reliably, for a full
session; what is not trustworthy is the durability signal above it.

Artefacts: `reports/raw/ws4-writeloss-s1-2026-09-07/` (data and analysis),
`ws4-writeloss-s1-2026-09-07-verdict.txt` (raw verdict),
`ws4-writeloss-s1-2026-09-07-reading.md` (the reading),
`ws4-sigterm-bound-2026-09-07.md` (the lifecycle bound).
