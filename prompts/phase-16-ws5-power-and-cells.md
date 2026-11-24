# Phase 16 — WS-5: statistical power and the remaining cells

**Rule 4.** Committed before this phase's first data commit. The prompt is
recorded as issued; corrections are recorded alongside it, never silently
applied.

**Issued:** 2026-09-10. **Preceded by:**
`reports/phase-report-ws5-prediction-2026-09-10.md` (the pre-registration,
commit `47d8a23`) and its amendment 1, both committed before any run exists.

---

## The prompt, as issued

> Proceed as you recommended. Class sweep to 6 sessions, reported as a bound
> rather than a test. §VIII's conclusion-validity paragraph stands and gets
> strengthened to the theorem form: not that the study failed to find an
> effect, but that at four sessions the sign test's floor is p = 0.125, so no
> effect size could have produced a rejection. State the floor and the
> six-session minimum explicitly — that is a stronger and more useful sentence
> than the one there now.
>
> Before launching, two things.
>
> Settle the B3 mixture in the analysis, not just the collection. docs/26 5.1's
> remedy narrows the interval without fixing the estimand, and you have already
> established why. Decide how the arm gets reported — both modes with their
> proportions, or a summary that does not jump by half the gap when one
> execution crosses a boundary — and pre-register that decision before any new
> run exists. A choice made after seeing 15 runs is a fitted choice.
>
> Do not investigate why 27% of B3's crash-free executions cost three seconds
> more. Record it as an open question with what you know: 2,034 vs 5,033 ms,
> 27% under both fsync policies, the gap spanning 95% of the arm's range. It is
> the most interesting loose end here and it is not a precondition for this
> collection.
>
> Then fix the §VI reporting defect: RQ3 quotes 28.0 ms without the interval
> that qualifies it, while the interval — a factor of 56 — sits only in §VIII.
> Put the interval next to the figure. A number stated without its uncertainty
> in the section that features it is the same defect the conclusion-validity
> paragraph exists to name.
>
> Then launch tier 1 and tier 2, ~13 hours, detached with nohup setsid and the
> keepalive held. Rule 4 first. Do not run the analysis during collection —
> read run counts and void counts only.
>
> R1, R8, R8a, R8b, R12, R12a, R15 apply. Stop when the data is committed and
> pushed. No analysis, no verdict, paper untouched beyond the RQ3 interval fix.
>
> If the push hangs, handoff §5 has the HTTP/1.1 case.

---

## Corrections and deviations, recorded rather than applied silently

**1. Tier 1's run count was understated in the pre-registration by a factor of
three, and is corrected here before launch.** §3 of the pre-registration sized
the `p0` timing collection at "7 systems × 15 runs = 105 runs" on the assumption
that `p0` runs on one endpoint. It does not: the harness's default plan for
`p0` is 7 systems × **3 endpoints** = 21 cells. The frozen `p0` data was
collected on `payments` only, so the launch restricts to `--endpoint payments`,
which yields the 7 cells and 105 runs the pre-registration assumed. The
restriction is deliberate and is the frozen design, not a saving: crash-free
overhead is a property of the protocol's own work and the endpoint's
reconciliation capability cannot affect an execution that never reconciles —
which is the reason `REGIME_NO_CRASH` already pins its keying to one value.

**2. The `always` arm is collected by `scripts/fsync_always_benchmark.sh`, not
by a `run_matrix` invocation.** That script starts a *second* Redis on a
different port with its own volume, reads `CONFIG GET appendfsync` back and
refuses unless the answer is literally `always`. Using `run_matrix` directly
would have required a `CONFIG SET` on the matrix's Redis, silently changing the
durability policy under every other result in the paper.

**3. Exact plan, from `--plan-only`, not from arithmetic.**

| tier | task | command shape | cells | runs |
|---|---|---|---|---|
| 1 | 5.1 timing, `everysec` | `--regime p0 --endpoint payments --runs-per-cell 15` | 7 | 105 |
| 1 | 5.1 timing, `always` | `scripts/fsync_always_benchmark.sh` | — | ~45 |
| 1 | 5.4 the incomplete run | targeted re-collect | 1 | 1 |
| 2 | 5.2 30%-crash regime | `--regime p30 --runs-per-cell 15` | 21 | 315 |
| 2 | 5.3 alternative keying | `--keying ORACLE_FINGERPRINT --system AEP_FULL --endpoint payments --endpoint notifications --runs-per-cell 15` | 12 | 180 |

**4. The incomplete run of task 5.4 is identified as**
`b4_durable_workflow-after_barrier_before_dispatch-payments-11d6b7e1-r2`
(`reports/phase-report-4-session1-2026-08-07.md:493`).

---

## Host state at launch, verified rather than asserted

* `scripts/verify_measurement_host.py` exits 0; Redis image digest matches the
  pin in `compose.phase2.yml`; the container and the port agree on one server id.
* **E5 suspend declaration is true, and was checked before being made.**
  `powercfg /q SCHEME_CURRENT SUB_SLEEP` reports `STANDBYIDLE` and
  `HIBERNATEIDLE` both `0x00000000` on **AC and DC** — never sleep on idle.
  *Residual, stated:* the system does support S0 low-power idle, so a lid close
  or an explicit sleep would still suspend it. The declaration is about the idle
  policy, and the harness's per-run wall-versus-monotonic check remains the
  backstop that made 249 frozen runs unusable rather than silently wrong.
* **R12 pre-flight:** `ss -lptn 'sport = :8099'` shows no listener before launch.
* **Container restarts during pre-flight: observed, attributed, and NOT an
  R12a occurrence.** Both containers' `StartedAt` moved repeatedly during
  pre-flight, each time landing within a second or two of a newly issued
  command, with `RestartCount=0` throughout. It was initially recorded here as
  a possible fourth occurrence of R12a's unexplained-restart class. **That
  attribution was wrong and is withdrawn.**

  A 140-second continuous poll settles it: `StartedAt` changed once, at the
  instant the poll began, and then held constant for the remaining 130 seconds.
  The stack is not restarting on a timer. Each `wsl -u root -- bash …`
  invocation restarts a distro that has idled out since the previous one, and
  Docker Desktop's WSL integration brings the containers up with it;
  `RestartCount=0` is the tell, because these are *starts*, not crash-restarts.

  The distinction matters twice over. It would have been filed as a fourth
  sighting of a pattern that does not exist, which is worse than not recording
  it at all — R12a exists so that a real fourth occurrence is recognised, and
  padding it with an explained one destroys that. And it does not threaten the
  collection: a detached launcher holds the distro open continuously, which is
  the condition under which the restarts do not occur.
