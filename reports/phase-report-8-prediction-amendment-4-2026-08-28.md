# Phase 8 · pre-registration, AMENDMENT 4 — a run whose fault did not land

**Committed while session 2 is still collecting, before it completes and before
any of its outcome columns have been read.** Amends `16abc99` as further amended
by `5b601d0`, `f29f3ae` and `850f221`. Everything not amended here stands.

---

## 1. The event

Session 2, run 3 of 120, `B3_INTENT_NO_BARRIER / ledger_postings / rep0`:

```
FAILED: FaultInjectionError: the hard kill did not land: Redis reports
uptime_in_seconds=42, so it is the same server process the run started with
and no infrastructure fault was injected
```

`run_matrix.py:1054` records such a run as `failed` and continues — "one bad run
must not end the matrix" — and writes no `summary.json`. The run therefore does
not reach the analysis at all. Left alone, the session finishes with **119 runs**
and one cell holding **29**.

## 2. Why this is not a result-dependent exclusion

The pre-registration's protection is against dropping runs because of what they
showed. This exclusion is of a different kind, and the difference is checkable:

- **The criterion is evaluable without reference to any outcome.** `Redis
  reports uptime_in_seconds=42, so it is the same server process` is a statement
  about the *instrument*, established from the server's own uptime before any
  outcome column is consulted.
- **No fault was injected, so the run is not a member of the regime.** The
  regime `redis-kill-preack` is *defined* by a hard Redis kill between the intent
  CAS and the barrier ack. A run in which the kill did not land did not run that
  condition. It is not a run of this experiment that came out badly; it is not a
  run of this experiment.
- **The harness, not the analyst, makes the call**, at collection time, in code
  written long before this phase. Nothing here is a judgement applied after the
  fact.

## 3. The registered handling: refill, and disclose the position

**A run that raises `FaultInjectionError` is refilled** via
`run_matrix.py --resume`, which skips already-collected runs and re-runs only
what is missing. Seeds are unaffected: `cell_seed` derives from `cell.key` and
`MATRIX_VERSION` (`run_matrix.py:526`), so the refill carries the same seed the
failed attempt had.

**Why refill rather than report 119.** Refilling is the option that leaves every
registered gate *literally* intact. The §3.4 canary condition —
`canary_survived + canary_lost ≠ 30 in any arm` — is written against 30 runs per
arm. Reporting 119 would trip it, and the alternative would be to reinterpret a
stop condition in the middle of a collection, which plan §6 rules out. Refilling
changes no gate, no threshold and no k; it restores the count the gates were
written for.

**What must be disclosed, per run refilled:**

1. **That the run was collected out of position.** The amended design is
   interleaved at run level precisely because position and arm were collinear,
   and a refilled run sits at the end of the session rather than at its original
   index. With the drift's sign unstable between sessions (amendment 3 §1), the
   displacement is not signable in advance, which is exactly why it is disclosed
   rather than argued away.
2. **The original index, the refill index, and the session's drift slope**, so a
   reader can bound the effect themselves.
3. **The count.** If more than **3 runs of 120** in any session require refilling,
   that is not a stray fault but a sick instrument: the session is reported as
   such and **not** refilled, because at that point the refills are a material
   fraction of the session and the out-of-position argument stops being about a
   single run. **This threshold is fixed here, before the session's total is
   known.**

## 4. What this does not license

- It does not license re-running a run that *completed*. Only runs the harness
  itself refused to record, for a stated instrument reason, are refilled.
- It does not license re-running a run because its outcome looked wrong. There
  is no outcome to look at: no `summary.json` is written.
- It does not extend k, relax a HALT, or alter the primary, either secondary, the
  integrity check or the balance check.

## 5. Unchanged

k = 4 and the no-extension commitment; the primary, both secondaries and the
integrity check; amendment 1's interleaving; amendment 2's residual prediction
and per-session Theil–Sen requirement; amendment 3's degeneracy procedure and its
fixed 0.02 threshold; the corrected wall-time threshold (6426 s); the HALT set;
the tertiary scheme, closed.
