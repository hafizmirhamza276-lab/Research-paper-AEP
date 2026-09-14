# Phase 21 — WS-5.1: the `always` arm, launched

**Rule 4.** Committed before any run directory for this arm exists.

**Issued:** 2026-09-14. Phase 19 ruled on the safety properties and repaired the
script but did not launch; phase 20 accounted for what phase 19 destroyed and
turned R16 into a mechanism. This is the launch.

---

## The prompt, as issued

> 45 runs — AEP_FULL, B3, B0 at 15 each, ~0.9 h — under `appendfsync always`.
> Last Tier 1 item. The barrier's `everysec` cost (1 939.7 ms) is mostly the
> 1-second fsync boundary; `always` has no such boundary. This arm says whether
> the barrier costs anything once that is removed. **A near-zero or negative
> result is a valid outcome here, not a failure.**
>
> 1. Commit this prompt.
> 2. Prove the R16 guard covers this script, on its failing branch.
> 3. Pre-flight, verified not asserted.
> 4. Launch, detached, with `CONFIG GET appendfsync` read back as `always`.
> 5. Do not analyse. Counts, void counts, statuses only.
> 6. Freeze, and bind it at collection time. State where the canonical tree is.
> 7. Teardown verified (R8, R8a, R8b).
> 8. R15, scoped.
>
> Out of scope: zero `.tex`, the class sweep, any analysis of these runs, and
> phase 20's three unfixed findings.

---

## Why a near-zero result is the pre-registered expectation, not a failure

`reports/phase-report-ws5-prediction-2026-09-10.md:244` settled this before any
of it was collected:

> The acceptance criterion "intervals must exclude zero where the point estimate
> is > 0" is achievable for the barrier cost and is **not** a sensible target
> for the `always` policy, where the true effect may be near zero.

The frozen three-run cell already reports the barrier cost under `always` as
**[−1474.6, 22.7]** (line 43) — spanning zero, with a negative lower bound. This
arm is powered to narrow that interval, not to move it off zero. An interval
that still contains zero at 15 runs per arm is a result.

---

## Corrections and deviations, recorded rather than applied silently

*(Filled in as the pass proceeds; see
`reports/phase-report-21-ws5-always-launch-2026-09-14.md`.)*

**1. The results root is now a required input with no default.** Phase 20
removed the default that phase 19 had left pointing at the frozen
`experiments/results/fsync-always`. The launch names a new dated directory
explicitly, and a bare invocation exits 2.
