# Pre-registration — WS-4: the protocol under block-level write loss

**Written, committed and pushed before any WS-4 data exists.** Rule 5 of
`docs/26-journal-readiness-direction.md` §3.

WS-4 (`docs/26` §4) and backlog item **B1** (`docs/24-revision-backlog.md`). The
gating assessment is `reports/raw/ws4-fault-delivery-assessment.md`; this
document is what it licensed, with the qualifications it raised carried forward
rather than dropped.

---

## 1. What is being measured, and why it is not already known

`experiments/flakey_write_loss.py` establishes the *premise* the barrier's
durability argument rests on: a `WAITAOF`-acknowledged key survives a device
that stops accepting writes and an unacknowledged one does not. It exercises
**two Redis keys, not AEP**. No *protocol* outcome — undetected duplicate, lost
effect, declared ambiguity, unwanted applied effect — has ever been measured
under write loss, so the durability half of the barrier's case is a premise plus
an argument rather than a system-level result. §VIII-A(b) says so in the paper.

This cell measures the protocol outcomes.

## 2. The prediction

> **AEP-full withholds dispatch when the record it depends on was destroyed;
> B3, having no barrier to withhold on, proceeds.**

| quantity | pre-registered |
|---|---|
| **AEP-full**, unwanted applied effects | **at or near 0** of 300 executions |
| **B3**, unwanted applied effects | **at or near ceiling** |
| AEP-full `lost_effect_executions` | **0** — it does not dispatch, so there is nothing to lose |
| both arms, `undetected_duplicate_applications` | **0** |

### This prediction is structural, and does not use a race model

Stated explicitly because Phase 13's landing-latency model was refuted
(`reports/raw/phase13-armA-model-gap.md`). This prediction rests on a
*mechanism*, not a timing comparison: writes are dropped at the instant the
intent CAS returns, so the fsync that `WAITAOF` waits for cannot complete, so no
`DurabilityAck` is issued, so `authorize_dispatch` refuses. There is no window to
model and no latency distribution to transport.

**What could still make it wrong**, and is therefore not predicted away: Redis's
behaviour when its AOF device fails is version-specific. It may return an error
to `WAITAOF`, block until timeout, or continue serving reads while the append
fails silently. Any of those is consistent with the prediction's *direction*;
only the third would complicate the reading, and it is recorded here in advance
so it cannot be discovered afterwards and narrated as expected.

## 3. What the probe evidence does and does not cover

**Stated plainly, because the temptation is to let 90/90 stand in for more than
it is.**

**Covered.** Delivery of the write-loss fault in the **standalone probe
configuration**: one Redis, two keys, no harness. Three independent
replications, **90 of 90 trials delivered**, `void: 0`, zero errors,
`unacknowledged_loss_rate: 1.0` in each. Each replication self-tests before any
trial and records it — a key written before the cut must survive, one written
after must not.

**Not covered.** Delivery in the **harness configuration**: the harness's
containerised Redis with its `dir` on the flakey device, under the crash
injector, the recovery service, a lock heartbeat, and 10 executions per run.
More moving parts, more instants at which the drop can land in the wrong place
or not at all. **Nothing in the probe evidence demonstrates delivery there**,
and this collection is the first time it will be exercised.

That gap is why §4 and §5 exist. They are not boilerplate.

## 4. The self-test, carried into the harness configuration

**Per session, before the first run, recorded as a first-class artifact.**

The probe's self-test is the reason the assessment was positive, so this cell
inherits it rather than assuming it:

1. With the dm-flakey table in **pass** mode, write a key through the harness's
   Redis and `WAITAOF` it. It must survive a restart.
2. Switch the table to **`drop_writes`**. Write a second key without waiting.
   It must **not** survive a restart.
3. Record both outcomes plus the two `dmsetup` table lines in the session root.

**If the self-test does not pass, the session does not run.** A dm-flakey table
that is not actually dropping writes produces runs that look successful and
measure nothing, which is the exact failure B1 names.

## 5. Non-delivery is a first-class number, and the abort rule is fixed now

`docs/24` B1 requires that B1 *"report its own non-delivery count as a
first-class number rather than as a footnote"*. It is reported in the results
table, per session, whatever its value.

**A run counts as a non-delivery if** the harness cannot confirm that the drop
was in force across the window it was armed for — the same standard the
Redis-kill injector already applies when it refuses a run whose kill did not
land.

| per-session non-delivery | verdict, fixed in advance |
|---|---|
| **0** | proceed; report the zero |
| **1–5%** of runs | proceed, but the count is reported beside every rate, and no rate is quoted without it |
| **> 5%** of runs | **the session is VOID.** Not analysed, not partially analysed, not pooled |
| **> 5% across the collection** | **the cell is reported INCONCLUSIVE** and no protocol outcome is claimed from it |

**Why the threshold is an abort and not a caveat.** Under a crash fault a
non-delivered run is a missing sample and the estimand survives on the rest.
Under write loss the fault *is* the measurement: a run whose writes were never
dropped is a run in which the phenomenon did not occur, and it will look like a
clean success for both arms. Analysing a set contaminated with them would
understate exactly the effect the cell exists to find. **The rate is not
recoverable by excluding them afterwards**, because a silent non-delivery is not
distinguishable post hoc from a genuine survival — which is why §4's self-test
runs first and why this threshold is fixed before the data exists.

## 6. The one-host limitation, in B1's own words

`docs/24-revision-backlog.md` B1:

> So the second host is not merely a convenience for reaching `dm-flakey`, and
> not merely a way to sample a second timing distribution. **It is required for
> B1's fault delivery to be trustworthy at all**, and B1 must additionally
> report its own non-delivery count as a first-class number rather than as a
> footnote.

**This collection does not satisfy that requirement.** It is one host — the same
WSL2 host, on the native Docker runtime since Phase 10.

What the assessment established is narrower than the requirement, and the
difference should be read as it is written: the *reason* B1 gives for demanding
a second host is that an instrument which intermittently fails to deliver would
do so **silently**. On this host it does not fail silently — the write-loss
probe self-tests, and the Redis-kill injector detected and refused its one
non-delivery in 780 Phase 13 runs by naming `uptime_in_seconds` as proof the
process never died. **That addresses the reason behind the requirement without
satisfying its letter.**

A reviewer is entitled to hold the paper to the letter. If they do, this cell is
a single-host result and B1 remains open on that ground; the results section
will say so rather than argue the requirement away.

## 7. Design

* **Fault:** `dm-flakey` in `drop_writes`, armed at the instant the intent CAS
  returns and **before** the barrier could acknowledge.
* **Storage:** loop device → `dm-flakey` → ext4 → the harness's Redis `dir`, with
  `appendonly yes` and `appendfsync everysec` exactly as `redis/phase2.conf`
  sets them. **`redis_storage_backing` must be recorded and must differ from the
  frozen runs**; this is checked, not assumed (WS-4 task 4.1).
* **Systems:** `AEP_FULL` and `B3_INTENT_NO_BARRIER`.
* **Capability class:** `NO_READBACK` only. `AUTHORITATIVE_READBACK` is a
  separate collection and a separate pre-registration if it happens at all.
* **Shape:** 30 runs × 10 executions per arm = **300 executions per arm**.
* **Estimand:** `executions_with_an_applied_effect` from
  `redis-kill-ablation.csv`, read exactly as `\UnwantedPrevented` reads it, plus
  `undetected_duplicate_applications` and `lost_effect_executions`.
* **Unit of analysis:** the run.
* **Stopping rule:** fixed at the shape above. No interim look. No run dropped
  except by the harness's existing void criteria and §5's non-delivery rule,
  both reported as counts.

### Preconditions, checked not assumed

`scripts/verify_measurement_host.py` exits 0; `AEP_HARNESS_SUSPEND_DISABLED`
declared; the E5 clock check within tolerance; §4's self-test passes; and the
`dm-flakey`/container composition holds — verified once already
(`reports/raw/ws4-fault-delivery-assessment.md` §3) and re-verified per session
by the self-test.

## 8. Both outcomes are acceptable

If AEP-full withholds and B3 proceeds, §VI-C3 gains the system-level result the
paper currently says it lacks, and §VIII-A(b)'s *"we have not done it"* sentence
comes out.

If they do not separate, that is a finding about the barrier under a fault class
the paper has only argued about, and it is worth more than the sentence it would
have replaced. **Nothing will be tuned to make the arms agree or disagree.**
