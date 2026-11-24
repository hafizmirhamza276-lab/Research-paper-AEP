# Phase 13 Step 4 — the in-flight Redis kill: verdict

**2026-09-04.** Collected 06:55–09:58 UTC against
`reports/phase-report-13-prediction-inflight-2026-09-04.md`, committed as
**77afd9a before any data existed**. Nothing below was chosen after seeing the
result; the criterion, the ceiling and the four mechanism-failure signatures were
all fixed in that commit.

This closes **M9** — `redis-kill-inflight` was fully defined in Phase 2b
(`experiments/run_matrix.py:259`) and had zero runs. The regime was not modified
to collect it.

---

## 1. Verdict: TIE, in all four class-sessions

| session | class | AEP-full | B3 | \|diff\| | verdict |
|---|---|---|---|---|---|
| s1 | AUTHORITATIVE_READBACK | 29/30 | 30/30 | 1 | **TIE** |
| s1 | NO_READBACK | 28/30 | 27/30 | 1 | **TIE** |
| s2 | AUTHORITATIVE_READBACK | 29/30 | 30/30 | 1 | **TIE** |
| s2 | NO_READBACK | 28/30 | 27/30 | 1 | **TIE** |

Every difference is 1, inside the pre-registered TIE band of ≤ 2. Both results
that would have outranked the tie are absent: `lost_effect_executions` and
`undetected_duplicate_applications` are **zero in every cell**, which is what
`phase-report-2b-session3b` §C.2 predicts — a process kill cannot lose the
record, because `appendfsync everysec` defers the `fsync(2)` and not the
`write(2)`.

**No mechanism-failure signature fired.** All four pre-registered checks are
clean across 240 runs: `redis_fault_mechanism` = `kill` in 240/240,
`redis_kill_point` = `mid_dispatch` in 240/240, `redis_kill_delay_ms` = 200 in
240/240, and zero runs with no kill event. E5: 0 clock drops, worst suspension
0.195 s, real `SIGKILL` throughout, 240/240 collected with no voids. Interleaving
realised at run level — longest same-arm streak 2, mean positions 58.5 / 60.5
against a 60.0 midpoint.

**What a tie does and does not mean.** It is evidence that *this fault class,
delivered at this point, cannot separate the arms* — not that the barrier is
without effect. That is why `redis-kill-preack` exists and why the prevention
result rests on it. §VI-C2 must not read the tie as a null result about the
barrier.

---

## 2. Session 2 is a deterministic replay, not an independent replication

**All 120 seeds are shared between the two sessions, and every one of the 120
per-run outcome tuples is identical.** The harness assigns seeds deterministically
per (system, endpoint, repetition), so two collections differ only through the
timing race. Where there is no race, the second collection reproduces the first
exactly — which is what happened here, run for run.

> **The effective run count for the applied counts is 120, not 240.** Session 2
> carries no independent information about them.

**The k = 2 justification in the pre-registration does not hold as written.**
§5 of that document argued for two sessions on the grounds that *"two sessions
still make a session effect visible; one would not, which is the Phase 9C
criticism."* That reasoning assumed a second session is a second draw. Under this
harness it is not, unless something in the run is non-deterministic. The
pre-registration should have said so, and did not.

This is not a defect in the collection — the runs are valid and the criterion was
met — but it changes what the design bought. Two sessions bought a **determinism
check**, not a replication. Stated here so §VI-C2 does not describe it as
"240 runs across two sessions" and imply more independent evidence than exists.

**The k = 2 interval caveat already pre-registered stands**, and now for a second
reason: a session-clustered bootstrap over two clusters can only draw
{s1,s1}, {s1,s2}, {s2,s2}, and here those three draws are the same numbers.
No interval is reported.

---

## 3. The absence of between-session variation is itself evidence

The replay finding cuts both ways, and the second way supports the prediction.

**Arm A ran on exactly the same shared-seed design** — its three sessions share
all 180 seeds — **and varied anyway**:

| Arm A, AEP-full applied | per session | varied |
|---|---|---|
| AUTHORITATIVE_READBACK | 0, 0, 0 | no |
| NO_READBACK | **1, 0, 1** | **yes** |
| POSITIVE_ONLY_READBACK | **0, 0, 1** | **yes** |

Identical seeds, and two of three classes still moved between sessions. What
moved them is the only thing left free: the timing race between `WAITAOF` and the
fault.

The in-flight cell shows **zero** variation across a complete replay — 120 of 120
outcome tuples identical. Under the same harness, the same host and the same seed
assignment, the cell with a race varied and the cell without one did not.

**That is a stronger form of the structural prediction than the tie counts.** The
pre-registration argued the fault lands after the branch point, so there is no
race to model. A cell with no race should be deterministic given its workload, and
this one is. The tie says the arms match; the determinism says there was nothing
that could have made them differ.

---

## 4. B3 NO_READBACK sits exactly on the threshold

`B3_INTENT_NO_BARRIER` on `NO_READBACK` applied **27 of 30 in both sessions** —
exactly the pre-registered ceiling of ≥ 27/30, which §4 of the pre-registration
makes the **primary mechanism-failure signature**.

> **This is the floor, not headroom.** One further non-applied run in that cell
> would have tripped the signature and put the whole tie in question, because two
> arms equally broken by a mis-timed injector is not a tie.

The analysis marks these cells `AT THRESHOLD` rather than `OK` for exactly this
reason, and `tests/test_inflight_tie_analysis.py` pins that distinction so a
later change cannot quietly render them as passing with room to spare.

Per-cell state, all eight:

| session | class | system | applied | state |
|---|---|---|---|---|
| s1 | AUTHORITATIVE_READBACK | AEP_FULL | 29/30 | OK |
| s1 | AUTHORITATIVE_READBACK | B3 | 30/30 | OK |
| s1 | NO_READBACK | AEP_FULL | 28/30 | OK |
| s1 | NO_READBACK | B3 | **27/30** | **AT THRESHOLD** |
| s2 | AUTHORITATIVE_READBACK | AEP_FULL | 29/30 | OK |
| s2 | AUTHORITATIVE_READBACK | B3 | 30/30 | OK |
| s2 | NO_READBACK | AEP_FULL | 28/30 | OK |
| s2 | NO_READBACK | B3 | **27/30** | **AT THRESHOLD** |

Because session 2 is a replay (§2), this is one cell observed twice, not two
independent observations landing on the floor.

**What the residual is has not been established.** Two to three runs per
NO_READBACK cell did not apply, in both arms. The pre-registration predicted
"at ceiling" and did not predict a specific residual, and nothing here
characterises it. It is not a difference between the arms — that is what the tie
measures — but why those runs did not apply is unexamined.

---

## 5. Provenance

| artifact | path |
|---|---|
| pre-registration (committed before data) | `reports/phase-report-13-prediction-inflight-2026-09-04.md`, commit `77afd9a` |
| session diagnostics | `reports/raw/phase13-inflight-s{1,2}-results.txt` |
| verdict analysis | `scripts/analyse_inflight_tie.py` |
| its test | `tests/test_inflight_tie_analysis.py` |
| fixture | `tests/fixtures/inflight/runs.json` |
| raw roots | `/root/aep-phase13/inflight-s{1,2}-2026-09-04` (measurement host) |

Every number in this note is regenerable:

```sh
python scripts/analyse_inflight_tie.py \
  --session /root/aep-phase13/inflight-s1-2026-09-04 \
  --session /root/aep-phase13/inflight-s2-2026-09-04 \
  --compare /root/aep-phase13/armA-s1-2026-09-03 \
  --compare /root/aep-phase13/armA-s2-2026-09-03 \
  --compare /root/aep-phase13/armA-s3-2026-09-03
```

**The same prose limitation applies as to `phase13-armA-model-gap.md`:** the test
pins what the script computes, not what this document says. The figures were
transcribed by hand. The gate that matters is `scripts/check_paper_numbers.py`,
which covers the manuscript; a figure quoted from here into §VI-C2 should be
re-derived from the script at that point rather than copied from this prose.

**§VI-C2 is not written.**
