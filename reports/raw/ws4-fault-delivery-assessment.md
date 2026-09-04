# WS-4 precondition: is fault delivery on this host trustworthy enough to collect?

**2026-09-04. Assessment only. Nothing has been collected and nothing is
pre-registered.**

`docs/24-revision-backlog.md` B1 sets a blocker that is stronger than a
precision concern:

> In Phase 8 the kill is a *side condition*: a run whose fault did not land is
> discarded and the estimand is measured on the runs where it did. **In B1 the
> fault *is* the measurement.** […] An instrument that intermittently fails to
> deliver the fault does not cost B1 precision — it silently removes the
> phenomenon while leaving runs that look successful.

So the question is not the outcome rate. It is whether a non-delivery would be
**seen**.

---

## 1. The instrument delivers, and it checks itself

`experiments/results/g2-flakey-write-loss{,-rep2,-rep3}.json`, three independent
replications on this host:

| | rep1 | rep2 | rep3 |
|---|---|---|---|
| trials | 30 | 30 | 30 |
| `void` | **0** | **0** | **0** |
| trials with `error` | **0** | **0** | **0** |
| `unacknowledged_loss_rate` | **1.0** | **1.0** | **1.0** |

**90 of 90 trials delivered the fault.** Not one void, not one error.

More important than the rate: **each replication runs a self-test before any
trial**, and records it:

```
selftest: { before_the_cut_survived: true,
            after_the_cut_survived:  false,
            valid: true }
```

The instrument writes a key before the cut and one after, and verifies the first
survives and the second does not. **A dm-flakey table that was not actually
dropping writes would fail that check and the run would not proceed.** That is
precisely the failure mode B1 names, and it is detected rather than silent.

## 2. The other fault surface, post-Phase-10

Phase 8.4's blocker was raised because the *Redis-kill* fault failed to land
twice, against 0 in 360 prior runs — read as host degradation. Phase 13
re-measured that surface on this host after Phase 10 moved to the native Docker
runtime:

| collection | runs | non-delivery |
|---|---|---|
| Arm A (controlled), 3 sessions | 540 | **1** |
| In-flight, 2 sessions | 240 | **0** |
| **total** | **780** | **1** |

And the one non-delivery was **detected and refused**, not silently scored:

> `FaultInjectionError: the hard kill did not land: Redis reports
> uptime_in_seconds=35, so it is the same server process the run started with
> and no infrastructure fault was injected`

The harness aborted that run rather than counting it. On both surfaces, this
host fails *loudly*.

## 3. The composition blocker is gone — tested, not assumed

`paper/sections/08-threats.tex` states that WS-4 could not be run because
*"the harness's Redis is a container whose bind mounts this Docker resolves in
the Windows filesystem, so the two do not currently compose."*

Tested directly: loop device → `dm-flakey` (v1.5.0, pass mode) → ext4 → mount →
the **pinned** `redis:7.2.5-alpine@sha256:6aaf…f44` container bind-mounting it
with `--appendonly yes --appendfsync everysec --dir /data`. The container stayed
up and wrote `appendonlydir` onto the flakey device. Torn down afterwards.

**It composes.** That sentence in §VIII is now false and will need updating when
WS-4 lands.

---

## 4. Verdict

**Fault delivery on this host is reliable enough to collect — with one
qualification that must be pre-registered rather than assumed away.**

The evidence above is for the **probe configuration**: a standalone Redis, two
keys, no harness. WS-4 runs the *harness's* Redis on the flakey device, under
the crash injector, the recovery service, and 10 executions per run. **Delivery
has not been demonstrated in that configuration**, and it is a different
exercise — more moving parts, more ways for the drop to land at the wrong
instant or not at all.

What follows for the pre-registration:

1. **Run the instrument's self-test inside the harness configuration**, per
   session, and record it. The two-key probe's self-test is the reason this
   assessment is positive; the harness cell must inherit it rather than
   assume it.
2. **Report non-delivery as a first-class number**, which `docs/24` B1 already
   requires. Not a footnote, and not folded into a void count.
3. **A pre-registered abort rule.** If non-delivery exceeds a threshold fixed in
   advance, the cell is reported as inconclusive rather than analysed — because
   under write loss a missing fault removes the phenomenon rather than adding
   noise.

## 5. What this assessment does not establish

* **It is still one host.** `docs/24` B1 says the second host *"is required for
  B1's fault delivery to be trustworthy at all"*. The evidence here argues the
  *reason* behind that requirement is addressed — non-delivery is detectable on
  both surfaces — but it does not satisfy the requirement as written, and a
  reviewer may reasonably hold us to it.
* **Two of the three degradation surfaces were not re-measured.** Phase 8.4 read
  degradation from fault delivery, within-session drift whose sign reversed, and
  the kill-latency envelope. Only the first is re-measured above.
* **No protocol outcome under write loss has been measured.** That is the whole
  of WS-4 and none of it is done.
