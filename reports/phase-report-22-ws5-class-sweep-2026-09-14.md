# Phase 22 — WS-5: the class sweep, 4 → 6 sessions — **halted at step 5, for a ruling**

## Asked / Done

Asked: rule on `redis_container`, commit the prompt, establish what a session is
from the existing four, pre-flight, launch two sessions, freeze, tear down, R15.

Done: steps 1–4 in full, and step 5 was launched and then **deliberately
stopped at 19 of 60 runs**.

**The two new sessions cannot be made structurally equivalent to the existing
four, and the reason is that the existing four are the ones collected under a
superseded design.** That is a decision about the class sweep as a whole, not a
collection detail, so this pass stops and reports rather than spending two hours
producing data whose poolability is not mine to decide.

---

## 1. Ruling on `redis_container` — nothing to fix, written before launch

Committed in `a859b44`, before any run directory existed.

Phase 21's finding bites only when `--redis-url` points away from the compose
service. The class sweep does not do that — read from the existing four:

```
redis_url        redis://127.0.0.1:6381/15     (run_matrix's default)
redis_container  aep-phase2-redis72
redis_service    redis-phase2
```

6381 **is** that container's published port, so the field is accurate here. No
source change was needed, none was made, and the two new sessions stay
byte-comparable with the four on this field. The general defect stands as phase
21 recorded it, unfixed.

## 1b. A second ruling the prompt did not ask for, but the tree forced

The four existing sessions record **`suspend_disabled_declared = False`** on all
120 runs, while the acceptance criteria require **true**. Ruled: declare it
true, and record the asymmetry. It gates the **timing** path only, which the
class sweep does not use — verified from the frozen session's own analysis:

```
runs                                          30, 30
runs_with_usable_timing                        0,  0
runs_dropped_for_undeclared_suspend_policy    30, 30
```

**The trap, stated so the analysis pass does not walk into it:** a six-session
tree would hold four sessions with *zero* usable-timing runs and two with all of
them. **Any six-session claim from this tree is a rate claim only.**

---

## 2. Session-equivalence evidence — and the mismatch it found

Every property below was read from the existing run-configs, not remembered.

| property | all four existing sessions |
|---|---|
| runs | 60 = 30 `AEP_FULL` + 30 `B3_INTENT_NO_BARRIER` |
| regime | `redis-kill-preack` (`after_intent_before_barrier`, 1 kill execution) |
| endpoint | `ledger_postings` |
| shape | `workers=1`, `executions_per_worker=1` |
| keying | `CALLER_REFERENCE`; dispatch `EVALUATION` |
| redis | `redis://127.0.0.1:6381/15` |
| **run ids and seeds** | **identical across all four — 60 of 60** |

The seed identity is the important one: a session is a **pure replicate at fixed
seeds**, so the 21.3 pp between-session variance the pre-registration prices is
entirely execution-time nondeterminism. Sessions 5 and 6 therefore had to reuse
matrix seed `20260806`, and did.

### The mismatch: collection order

```
b2-2026-08-21                60 runs    2 blocks   CELL-MAJOR
b2-s1-2026-08-21             60 runs    2 blocks   CELL-MAJOR
b2-s2-2026-08-21             60 runs    2 blocks   CELL-MAJOR
b2-s3-2026-08-21             60 runs    2 blocks   CELL-MAJOR
b2-s4-2026-09-14 (aborted)   18 runs   18 blocks   INTERLEAVED
```

All four existing sessions run 30 `AEP_FULL` and then 30 `B3`. The new one
alternates run by run.

**This is not a defect in the new session. It is the fix.** Run-level
interleaving was introduced deliberately in `5b601d0`, **2026-08-28 12:02:54**,
*"Phase 8 pre-registration amendment 1: interleave at run level, because arm and
drift are collinear"*. Its own comment in `run_matrix.py` says why:

> one arm of a paired comparison was always the earlier block and the other
> always the later one, so arm and drift were *perfectly collinear*: not a large
> confound to adjust for, but a **non-identifiable** one that no number of
> sessions separates. The session's balance check failed at 213 ms against a
> 100 ms threshold, and kill latency is the measured cause of the applied rate
> it was comparing.

The four class-sweep sessions are dated **21 August** — a week before that
commit. They were collected under the design the amendment replaced, and were
never re-collected.

### The project has already answered this question once

```
b2-paired-s1-2026-08-28       120 runs    2 blocks   CELL-MAJOR
b2-paired-v2-s1-2026-08-28    120 runs   60 blocks   INTERLEAVED
```

On 28 August the same defect was found mid-phase. The response was **not** to
add interleaved sessions to cell-major ones. It was to re-collect the whole
comparison as **v2** — the `-v2-` in those root names *is* this decision. Four
v2 sessions exist; the v1 session is retained as evidence and not pooled with
them.

The class sweep never got its v2.

### Why I did not simply match

Matching the existing four would mean reverting `5b601d0` for this collection —
deliberately reintroducing a confound that a pre-registration amendment was
written to remove, in order to make new data resemble old data. That is the
wrong direction, and it is the same direction ruling 1b refused on `suspend`.

### What I got wrong, and when

Step 3 asked me to establish the session structure and say before launching if
anything could not be matched. I did that for the restart discipline. **I
verified the target and not the instrument**: I read the four sessions' order,
recorded "cell-major", and assumed `run_matrix` would still produce it. It was
caught nine minutes in by run 18 being `B3 rep8` where cell-major predicts
`AEP rep17` — by a progress line looking wrong, not by a check.

---

## 3. Counts and statuses — nothing was analysed

```
b2-s4-2026-09-14-ABORTED-order-mismatch    19 run dirs, 18 summaries  -- NOT a session
b2-s5-2026-09-14                           never started
sessions added to the class sweep          0
```

No rate, no sign test, no interval, no p-value. `power_analysis.py` was not run.

**The aborted directory is retained, not deleted**, following the precedent of
`b2-paired-v2-s2-aborted-2026-08-28`, and carries an `ABORTED.md` saying it is
not a session and must never be counted as one. It is left untracked.

---

## 4. Guard evidence, before any container was created

The driver is `python -m experiments.run_matrix`. The launcher sources the
committed R16 guard and refuses before reaching it:

```
A. no results root                                   exit 2
B. the frozen 432-run experiments/results/matrix     exit 3
C. a frozen class-sweep session (rule 2)             exit 3
D. aep_guarded_rm_results on that session            exit 4   (60 run dirs intact)
E. containers created by A-D                         none (only the pre-existing stack)
```

## 5. Pre-flight

```
verify_measurement_host.py   exit 0   gates.passed=True   failures=[]
redis image digest           sha256:6aaf3f5e…  matches the pin
suspend.declared             True (exported by the collection command)
clock within tolerance       True
flakey target                True
ports                        8099 free; 6381/6382 busy = the matrix stack this
                             collection uses
STANDBYIDLE / HIBERNATEIDLE  0x0 on AC and DC, read before declaring
targets                      both absent before launch
```

**S0 residual, restated:** `powercfg /a` reports *"Standby (S0 Low Power Idle)
Network Connected"* available. Timeouts of 0 remove scheduled sleep, not
lid- or user-triggered modern-standby entry, which no query can rule out. A
declaration is not a guarantee.

---

## 6. Not done, and why

**Steps 5 (completion), 6, 7 and the freeze: not done, because there is nothing
to freeze.** No session was completed, so there is no MANIFEST, no SHA256SUMS
and no raw-tree digest to write, and no canonical tree path to state.

The decision that has to come first:

1. **Collect 5 and 6 interleaved and pool all six.** Achieves the 2/2ⁿ = 0.03125
   floor, but the sign test then mixes two designs — four sessions in which arm
   and drift are collinear, two in which they are not. The floor would be
   honest; the homogeneity would not.
2. **Re-collect all six interleaved as a v2 class sweep.** Follows the project's
   own 28-August precedent exactly. ~6 h. The existing four stay frozen and
   unpooled, as `b2-paired-s1` did. This is the option the precedent points at.
3. **Stop at four and report the bound as it stands.** The floor stays 0.125 and
   §VIII's "could not have found one" sentence stands unchanged — which is
   already the pre-registered claim.

I have not chosen. Option 2 is what the repository's own history did when faced
with this defect, and it is the only one that yields six comparable sessions —
but it is six hours and it supersedes frozen data, which is a call for you.

**Also not done, and out of scope throughout:** zero `.tex` changed, no analysis
of anything, the four existing sessions untouched (verified: 60 run dirs each,
`git status` on `experiments/results/` clean apart from the aborted directory),
and phase 20's three findings not re-opened.

---

## 7. Teardown, verified

```
processes                clear (killed by PID: 739, 821, 917; table re-read)
port 8099                free
second Redis             none was ever started by this pass
matrix stack             aep-phase2-redis72 + toxiproxy, healthy
matrix appendfsync       everysec -- unchanged
dmsetup ls               No devices found
losetup -a               only Docker Desktop's own iso loop
four frozen sessions     60 run dirs each; git status on results/ clean
```

---

## 8. Findings outside scope

1. **`experiments/run_matrix.py:89` — `DEFAULT_RESULTS_ROOT = "experiments/results/matrix"`.**
   A bare `python -m experiments.run_matrix` writes into, and `--resume`s
   against, the frozen 432-run root every outcome rate in the paper comes from.
   **Third instance of the R16 shape**, and the first in the Python driver —
   phase 20's sweep only covered shell scripts, which is why it was missed.
   Recorded before launch, in `prompts/phase-22-ws5-class-sweep.md`.

2. **The class sweep's four sessions predate `5b601d0` and were never
   re-collected.** Independently of what is decided about sessions 5 and 6,
   §VIII's existing four-session result rests on the cell-major design whose
   collinearity that commit calls *non-identifiable*. That is a property of a
   published number, not of this pass.

3. **This session ran at roughly half the August pace** — 19 runs in ~19 min
   against 60 runs in 35–40 min on 21 August. Not investigated; the host has
   been through four Docker daemon restarts today (12:46, 13:51, 13:53, 16:08
   UTC), and the results root is on v9fs. Recorded only.

---

## 9. Environment

`uv run --frozen --extra experiments --extra analysis`, CPython 3.13.0, WSL2
6.6.114.1, Docker 29.4.3 (`aep-native`). Redis
`redis:7.2.5-alpine@sha256:6aaf3f5e…1f44` on 6381, the compose service, shared
with the existing four sessions by design. Harness commit `a859b44`. Matrix seed
`20260806`. No second Redis, no `CONFIG SET`, no frozen root modified.
