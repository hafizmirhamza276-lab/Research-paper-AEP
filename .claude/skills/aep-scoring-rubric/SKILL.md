---
name: aep-scoring-rubric
description: The 1-10 scoring rubric and the >=9 approval gate the orchestrator applies to every phase report.
---

# AEP scoring rubric

The orchestrator scores every subagent report against the five dimensions below. Each dimension is rated **1–10**. A phase is **APPROVED** only if **every** dimension scores **≥9**. Otherwise the phase is **REJECTED** with per-dimension reasons and re-delegated to the same agent (attempt 2), then escalated to `opus-fixer` after a second strike.

## Dimensions

1. **Correctness (1–10)** — Does the work match the AEP invariants (Timeout, CAS Fencing, Fail-Closed) and the explicit definition of done? Any invariant violation forces a low score.
2. **Completeness (1–10)** — Does the work cover every required piece named in the phase's deliverable list, with no silent gaps and no "TODO" placeholders?
3. **Robustness (1–10)** — Are edge cases and failure modes covered explicitly (corrupt payload, missing key, stale write, lease cap hit, lock-ownership mismatch, schema migration miss)?
4. **Clarity (1–10)** — Is the output unambiguous and well-structured? Can a reader tell exactly what the design / code / test / finding means without rereading?
5. **Honesty (1–10)** — Does the work avoid overclaimed guarantees? Does it use the honest phrasing ("detectable + fail-closed," not "absolute atomicity")? Are assumptions and residual risks stated?

## The ≥9 gate

```
approve  <=>  min(correctness, completeness, robustness, clarity, honesty) >= 9
reject   <=>  any dimension < 9
```

There is no average / weighting trick. **One dimension below 9 fails the gate.**

## Passing breakdown (example)

```
Correctness:   9/10  — All three invariants honored; CAS Lua returns documented codes.
Completeness:  9/10  — All schemas, contracts, recovery paths, and failure modes listed.
Robustness:   10/10  — Stale write, corrupt payload, lease cap, lock loss all covered.
Clarity:       9/10  — Module contracts unambiguous; minor wording tweak suggested.
Honesty:      10/10  — Explicit residual risk note; no overclaim.
=> APPROVED
```

## Failing breakdown (example)

```
Correctness:   8/10  — CAS check uses raw SET in one branch; Fencing Invariant violated.
Completeness:  9/10  — All deliverables present.
Robustness:    7/10  — Lease-cap exhaustion path not covered.
Clarity:       9/10  — OK.
Honesty:       6/10  — Report claims "atomic across failover" — overclaim.
=> REJECTED. Feedback:
   - Replace raw SET in storage.write with the CAS Lua.
   - Document lease-cap exhaustion behavior (renewal stops, lock expires).
   - Remove "atomic across failover" wording; use "detectable + fail-closed."
```

The orchestrator must write a similarly explicit breakdown into `docs/build-log.md` for every score.
