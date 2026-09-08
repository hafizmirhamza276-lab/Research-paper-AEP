# WS-6 — B5 primary, attempt 1: VOID

**8 September 2026.** Session root `b5-s1-2026-09-08`, moved aside as
`VOIDED-b5-s1-2026-09-08-attempt1`. Nothing deleted.

**Attempt 1 of the 3 the pre-registration allows. Two remain.**

---

## 1. The decision, and what it was made on

**VOID**, under `reports/phase-report-ws6-prediction-2026-09-07.md` §4, on **two
independent grounds, either of which is sufficient**:

| §4 condition | Observed |
|---|---|
| the run count is short | **39 of 120** recorded |
| the engine restarts mid-collection | postgres and temporal both stopped while the driver was running |

**Decided on the run count alone, before any outcome was read** — the discipline
that kept WS-4 attempt 4's void defensible. The verdict column was counted for
bookkeeping (39 × `COMPLETED`, 0 voids) and nothing else: no rate, no per-cell
reading, and `analyse_b5_agreement.py` was **not** run.

### The evidence, measured

| Fact | Value |
|---|---|
| runs planned (`plan-primary.json`) | 120 |
| runs recorded (`b5-runs.jsonl`) | **39** |
| run directories on disk | 40 — 30 `B5_TEMPORAL`, 10 `B5B_TEMPORAL_AT_MOST_ONCE` |
| last record | `b5b_…-r8`; `r9` has a directory and no record — the run in flight |
| `stage-primary-finished.json` | **absent** |
| `### primary rc=` in `driver.log` | **absent** (0 occurrences) |
| traceback in `primary.log` | none (0 occurrences) |
| primary started | 06:55:56 UTC |
| last `b5-runs.jsonl` write | 07:39:32 UTC |
| last run directory created | 07:39:37 UTC |

Container exits, read by `docker inspect` earlier the same day and before
teardown removed the containers (the kill events remain in
`obs-2026-09-08/docker-events.log`):

* `aep-ws6-postgres` — finished `07:39:56Z`, exit 0
* `aep-ws6-temporal` — finished `07:42:46Z`, exit 255

The observer recorded `container kill` on both at 07:39:56, then stopped itself
at 07:40:06.

---

## 2. A second, independent disqualification: it was collected on uncommitted code

`docs/26` §3 rule 5 requires the collection path to exist, committed, before any
data does. At collection time:

* `experiments/baselines/b5_temporal/session.py` — **untracked**
* `experiments/baselines/b5_temporal/collect.py` — modified, uncommitted
* `experiments/baselines/b5_temporal/prove_attribution_gate.py` — modified, uncommitted

So even a complete 120-run session from this launch would have been
unpublishable. The run count decided the void first and on its own; this is
recorded because it would have decided it anyway, and because a void with two
independent grounds is worth more than one with a single contestable ground.

---

## 3. Why this is not merely a lost session

Two defects were found afterwards in the code that produced these 39 runs.
**Both were in the runner, both were silent, and either would have made a
finished session worthless.**

### 3.1 The injected crash point was a constant

`session.py` armed the literal string `"ACTIVITY_ENTERED_BEFORE_CALL"` for every
run, while labelling cells from the roadmap. The primary stage collects one
crash point, so the constant happened to be correct here. The **secondary
sweep** yields four — `before_intent_write`, `mid_dispatch`,
`after_response_before_resolution`, `after_resolution_before_barrier` — and all
240 runs would have taken the same fault under four different headings.

Nothing downstream could have caught it. The injected point appeared in no run
record, no per-cell metric and no gate; the run_id said one thing and the
instrument did another, and the two were never compared.

### 3.2 `crash_point` carried B5's vocabulary, where the reader keys on roadmap names

Every one of the 39 records wrote:

```
"crash_point": "ACTIVITY_ENTERED_BEFORE_CALL"
```

`analyse_b5_agreement.py` looks each cell up in the frozen per-cell file by
`crash_point`, and that file is keyed on **roadmap** names
(`after_barrier_before_dispatch`, …). The two vocabularies are disjoint, so
**every cell — primary included — would have found no frozen B4 counterpart.**

This one is not confined to the secondary sweep. It would have hit these 39 runs
had they become 120.

Both are fixed and proven at `593ea64`, with a rule-13 proof on the real stack in
both directions (`experiments/baselines/b5_temporal/prove_crash_point_binding.py`):
five crash points, five distinct armed positions, each recording the point its
label resolves to; and a run whose label and fault disagree refused before a
worker is spawned, reading `VOID_CRASH_POINT_MISMATCH`.

---

## 4. What actually stopped it — and a correction to `.wslconfig`

**The driver was killed with the client that launched it.** `b5_collect.sh` ran
`session.py` in the foreground, so the whole tree went down together. That is
what `driver.log` shows: the script never reached its own `### primary rc=`
line, and `primary.log` holds no traceback. The shell died, not the Python.

The containers went ~20 s later. With nothing left running, WSL idled the distro
out and took them with it. **The container kills at 07:39:56 are the
consequence, not the cause.**

### The `.wslconfig` comment should not be trusted

`.wslconfig` sets `vmIdleTimeout=-1` and its comment presents this as the fix
for exactly this failure. **It is not honoured by WSL 2.7.3.0** — accepted
silently, no effect. Measured 8 September, after a clean `wsl --shutdown` to
apply it:

| keepalive | a process running | distro after ~140 s |
|---|---|---|
| off | off | **Stopped** |
| off | on | Running |
| on | off | Running |

WSL keeps the VM up while **anything is running**. A detached collection
therefore holds the distro open by itself, which is why the fix is the detached
launch and not the setting. `scripts/wsl_keepalive.ps1` exists for the gaps —
the moments between a collection ending and the next command — and is defence in
depth, not the remedy.

This is the correction that matters for the next attempt: the earlier reading of
this failure blamed the idle timeout, which would have led to relying on a
setting that does nothing.

---

## 5. Disposition

The root is **moved aside, not deleted**, as
`/root/aep-ws6/VOIDED-b5-s1-2026-09-08-attempt1`, carrying a `VOID-REASON.md`
that states the decision at the data. `docs/25` R8a's principle applies to a
voided session as much as to a failed teardown: the evidence a void was decided
from is worth more than the space it occupies.

`b5-runs.jsonl` is left byte-identical, 39 lines. `session.py` now refuses a
session root that already holds runs rather than appending to it — it replans
from index 0, and the run count is what every void decision here is made on.

## 6. Before attempt 2

Closed and each verified by exercising it, not by reading the change:

1. **Runner committed** — `593ea64`, pushed. `b5_temporal/` has no dirty files.
2. **Launch detached** — `setsid`+`nohup`, PID recorded (R1); proven to survive
   its launching client.
3. **Used root refused** — exit 2, `b5-runs.jsonl` byte-identical, both
   directions tested.
4. **Distro** — keepalive proven in both directions; `vmIdleTimeout` proven
   ineffective.

Suite at the time of the fix: 1966 passed, 0 skipped.
