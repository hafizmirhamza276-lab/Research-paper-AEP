# WS-6 open questions, round 3: the gate is proven; three items still open

**No data collected**, no run directory written, `analyse_b5_agreement.py` not
written, and **the pre-registration not changed**.

The probe did not run to completion again. The reason is established this time,
and one of the two causes was mine.

---

## Q5b — the gate's both-branch proof: **CLOSED, rule 13 satisfied**

Both branches ran on the real stack:

```
branch A reachable     verdict=PENDING_AT_DEADLINE        void=False  reached=True  fired=True
branch B unreachable   verdict=VOID_INJECTOR_DID_NOT_FIRE void=True   reached=True  fired=False
    void reason: the worker reached 'ACTIVITY_ENTERED_BEFORE_CALL' but no kill
                 was recorded: the injector was disabled or failed to fire
rule 13 both branches  satisfied=True
```

**Branch A**: the injector reached the point, fired, and the gate was **silent** —
the run is reported as `PENDING_AT_DEADLINE`, a measurement.

**Branch B** (`B5_INJECTOR_DISABLED=1`): the run **voided**, and the reason names
the injector. It says nothing about the deadline, which is the entire point: the
previous instrument reported this exact situation as `PENDING_AT_DEADLINE`.

**A precision worth stating.** Branch B produced `VOID_INJECTOR_DID_NOT_FIRE`,
not `VOID_INJECTOR_NEVER_REACHED`. That is correct for how the branch is
induced — the worker *does* reach the point and is then told not to fire — and
both verdicts are void and both name the injector. The `NEVER_REACHED` verdict
was also exercised, independently, in Q5c below.

## The gate caught a real instrument failure in the field

Not a fixture. During Q5c the mock provider was dead, so the activity could not
get past its HTTP call, and the two crash points that sit *after* that call were
never reached. The gate returned:

```
AFTER_RESPONSE_BEFORE_RETURN   reached=False  fired=False  VOID_INJECTOR_NEVER_REACHED
DURING_COMPLETE_RPC            reached=False  fired=False  VOID_INJECTOR_NEVER_REACHED
```

**Before this gate existed those two runs would have been recorded as
`PENDING_AT_DEADLINE` and reported as data.** They were voided instead, with a
reason pointing at the injector rather than the timeout. That is the defect this
gate was built for, reproduced accidentally and caught.

## Q5c — the five crash points: **3 of 5, unchanged, and not claimed**

| point | reached | fired |
|---|---|---|
| `BEFORE_SCHEDULE_ACTIVITY` | yes | yes |
| `ACTIVITY_ENTERED_BEFORE_CALL` | yes | yes |
| `DURING_PROVIDER_CALL` | yes | yes |
| `AFTER_RESPONSE_BEFORE_RETURN` | **no** | — |
| `DURING_COMPLETE_RPC` | **no** | — |

**The two `no`s are not evidence about those points.** The provider was down for
that stage, so the activity never returned from its HTTP call and execution never
arrived at either. They remain **undemonstrated**, exactly as before, and are not
being claimed in either direction.

## Q2 — **still half closed**

This round's `q2a` failed with `httpx.ConnectError: All connection attempts
failed`. The **valid** measurement from the previous round therefore stands
unchanged and unrepeated:

```
n=30  answered=22  timed_out=3  refused={503: 5}
p50 = 2015.0 ms   p95 = 2024.2 ms   max = 2059.0 ms
```

A Start-To-Close timeout must clear ~2.06 s. **`q2b` — does the retry land inside
the run — did not execute**, so no timeout value is chosen and **H1's testability
remains unestablished**. That is not evidence H1 is untestable, and the
pre-registration is unchanged.

## Q3 — **OPEN**, blocked on `q2b`. ## Q4 — **OPEN**, not exercised

`B5_SEMANTICS.md` still marks `after_resolution_before_barrier` **approximate**.
Nothing was learned that would downgrade it, so it is not downgraded. If it later
proves unhittable it becomes a **second absent point**, and the cost of that is
worth stating in advance: B5 would then be crashable at only four of the six
roadmap points, missing both `*_before_barrier` positions — the two that name the
window AEP's durability argument is entirely about. The comparison would become
"the two engines agree where neither has a durability window to be cut in",
which is a much weaker claim than WS-6 was scoped to make.

---

## Why the probe did not finish, both causes

**Cause 1, mine.** While round 3's probe was mid-flight I ran a `pkill -f
experiments.mock_api` intending to clear a stale provider, and killed the live
one. That produced the `ConnectError` in `q2a` and the two unreached points in
`q5c`. An interfering command issued against a host with a probe running on it —
the same class as WS-4's stale-provider collisions, and the reason `docs/25` R12
exists.

**Cause 2, not mine and not established.** The Docker stack went away twice
during this pass — first both containers restarting mid-probe (`Up 2 minutes`
while the probe was still running), then the whole stack disappearing, with
`docker ps` returning nothing at all. WSL itself did not restart (uptime 6 h
56 m at the time) and there were no OOM kills (14 GB available). This is the
third and fourth occurrence of the unexplained-lifecycle class recorded as
`docs/25` **R12a**, and the first time it has interrupted work rather than merely
followed it. Not chased, per R12a.

**What the R14 hardening bought.** Round 2's probe died leaving no findings file
and no traceback, and its cause was never established. Round 3's wrote findings
after every stage and recorded stage failures instead of dying silently, which is
why both causes above are known and why the gate proof survived a run that later
failed. The R14 precheck also passed — `canary accepted (200)` — confirming the
probe was speaking the provider's contract before it measured anything, which is
what the previous two rounds could not tell.

---

## Teardown

R8a — evidence preserved first, `/var/tmp/b5-evidence`: `findings-final.json`,
the round-3 transcript, worker stderr, traces, server log.

R8 / R8b / R12 — verified from a script file, not asserted (an inline check
lost `$P` to the WSL bridge and printed three bare `HELD` lines, which is R14's
shape again and is why it was re-run properly):

```
ws6 containers left      : 0
port 7233 / 8233 / 8099  : free / free / free
redis-data volume present: 1
```

`compose down` without `-v`.

---

## Status

| Item | Status |
|---|---|
| Q5b gate, both branches | **CLOSED** — rule 13 satisfied, and the gate caught a real failure in the field |
| Q5c five crash points | **3 of 5** — the other two undemonstrated, provider was down |
| Q2 timeout | **HALF** — distribution stands from round 2; no value chosen; H1 testability unestablished |
| Q3 deadline | **OPEN** — blocked on `q2b` |
| Q4 point 6 race | **OPEN** — mapping left at approximate |

**WS-6 remains not ready to collect.** What is left is one uninterrupted probe
run on a stack that stays up: `q2b`, `q4`, and the two post-provider crash
points. Every instrument they need now exists and the gate they depend on is
proven.
