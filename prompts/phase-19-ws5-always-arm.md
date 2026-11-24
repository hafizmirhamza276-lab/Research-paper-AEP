# Phase 19 — WS-5.1: the `always` arm, collected

**Rule 4.** Committed with the pre-launch work, before any run directory exists.

**Issued:** 2026-09-14.

---

## The prompt, as issued

> 45 runs — AEP_FULL, B3_INTENT_NO_BARRIER, B0_NAIVE_RETRY at 15 each, ~0.9 h —
> under `appendfsync always`. This is the last Tier 1 item and the only remaining
> collection before the class sweep. It exists because the barrier's cost under
> `everysec` (1 939.7 ms) is dominated by the 1-second fsync boundary, and the
> `always` policy has no such boundary: it is the arm that says whether the
> barrier costs anything once you remove the thing it is mostly waiting for.
>
> 1. Rule on the three safety properties, before anything else.
> 2. Pin the lower-mode threshold before any new run exists (amendment 3).
> 3. Commit this prompt.
> 4. Pre-flight, verified rather than asserted.
> 5. Launch, detached, with `CONFIG GET appendfsync` read back as `always`.
> 6. Do not analyse.
> 7. Freeze, with the raw-tree digest at collection time.
> 8. Teardown verified, not asserted.
> 9. R15.
>
> (Full text in the issuing message; the steps above are the operative list.)

---

## Corrections and deviations, recorded rather than applied silently

**1. There are four properties, not three.** `test_fsync_stage3_safety.py`
carries four test functions: a parametrised run-count gate, and three
source-inspection checks. Each is ruled on separately in
`reports/phase-report-19-ws5-always-arm-2026-09-14.md` §2.

**2. The script on main deletes a frozen result by default, and that is why
this pass stopped short of launching.** `RESULTS_ROOT` defaulted to
`experiments/results/fsync-always` — a tracked, frozen directory that is the
sole source of `\BarrierCostAlways`, `\BthreeAlwaysMedian` and
`\AepAlwaysMedian` — and the clean path was a recursive force-delete of it with
`AEP_FSYNC_CLEAN` defaulting to `1`. A bare invocation of the script named in
step 5 destroyed published data (rule 2), and that is not a conditional: the
rule 13 run of the *old* script did exactly that, at 14:03, destroying sixty
executions across six raw run directories that are not recoverable. The
repair is the subject of the ruling; the loss is the subject of
`reports/incident-fsync-always-raw-destroyed-2026-09-14.md` and `docs/25`
R16.

**3. The collection was not launched in this pass.** The pre-launch gates —
the ruling, amendment 3, the script repair — consumed the pass. Launching after
them without room to verify the pre-flight, watch the `CONFIG GET` read-back,
freeze, tear down and run R15 would have left a running collection and an
unverified tree. What remains is listed in the phase report §5.
