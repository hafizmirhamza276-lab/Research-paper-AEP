# Phase 8 — B2 plan (rev. 3)

**Status:** 8.0 executed (this commit). 8.1.0 executed and written up in
`reports/phase-report-8-1-0-2026-08-27.md`. **Everything from 8.1 onward is
planned and not started**, pending review of the re-derived k (§6) and the
measured timing bound (§7, step 8.2).

Prompt of record: `prompts/phase-8-b2.md`, committed before any Phase 8 data.

**Revision history.** Rev. 1 answered the issued prompt. Rev. 2 folded in CHANGE 1
(step 8.1.0; do not lock the estimand or k until the invariant question is
answered) and CHANGE 2 (rescue the Phase 9 data first). Rev. 3 folds in
AMENDMENT 1 (the invariant must not set k) and AMENDMENT 2 (bound the ack emit's
timing effect rather than asserting it away), and records what 8.0 and 8.1.0
actually found — including two corrections to rev. 2's own §0.

---

## 0. Context

**1. B2 has already been attempted, and its positive control failed.** `HEAD` was
a Phase 9 commit. Phase 9 pre-registered B2's prediction
(`reports/phase-report-9-prediction-2026-08-21.md`, `85e6c54`), ran the control
first as that pre-registration required, and the control failed: AEP-full's
`NO_READBACK` applied count was 10, 20, 12, 4, 7 out of 30 across five identical
sessions — over-dispersion **5.37** against binomial
(`phase-report-9c-result-2026-08-21.md` §3). P9-A §3 forbids a cross-class claim
from a session whose control failed, so **AUTH was never collected**.

The backlog's design — one 30-run AUTH cell compared against the frozen
`NO_READBACK` cell — therefore cannot work. A between-session comparison of a
quantity ranging 4→20 measures the session.

**2. The cause is already in the run logs.** 9C §6 named the provenance gap as
missing Docker daemon state. But the harness already records the proximate
quantity: `kill_redis()` returns `command_ms` (`redis_kill.py:108`) and the
watchdog emits `issue_to_return_ns` (`redis_kill.py:305`) into every run's
`events.jsonl`.

AEP-full dispatches only if `WAITAOF` returns before Redis dies. **The kill
latency is the width of that race.** A slower daemon gives the ack more time to
win, so AEP-full dispatches and applies more often. B3 never waits, so the race
cannot touch it.

**Run-level evidence, all 150 AEP-full runs across five sessions:**

| | n | applied | median latency, applied | median, not applied | difference | permutation p |
|---|---|---|---|---|---|---|
| **AEP_FULL** | 150 | 53 | 1114.0 ms | 919.9 ms | **+194.1 ms** | **0.00005** |
| B3 (control) | 150 | 140 | 958.3 ms | 970.3 ms | −12.1 ms | 0.76 |

20 000 relabellings, `random.seed(4242)`. The B3 control is what makes this a
mechanism rather than a correlation: B3 never waits for the barrier, and its
applied outcome is accordingly independent of kill latency.

**Correction to rev. 2 §0 — the session-level ordering is NOT monotone.** Rev. 2
reported "monotonic in all four" from the four Phase 9 sessions. 8.0 recovered
the fifth (§8.0 below), and it breaks the pattern:

| session | filesystem | AEP median kill latency | AEP applied |
|---|---|---|---|
| **2026-08-07** (the paper's cell) | **ext4** | **858.9 ms** | **10**/30 |
| `b2-s2-2026-08-21` | drvfs | 880.6 ms | 4/30 |
| `b2-s3-2026-08-21` | drvfs | 945.0 ms | 7/30 |
| `b2-s1-2026-08-21` | drvfs | 1025.2 ms | 12/30 |
| `b2-2026-08-21` (P9-B) | drvfs | 1215.7 ms | 20/30 |

**Spearman ρ falls from 1.000 over four sessions to 0.700 over five.** The
2026-08-07 session has the lowest median latency and yet applied more often than
two slower sessions. Rev. 2's four-session claim was true of those four and did
not survive the fifth. The run-level result above is the robust one and is
unaffected; the session-median ordering is a weaker aggregate view and is
reported as such. **8.1 must use the run-level statement, not the ordering.**

**3. The consequence for what may be claimed** (CHANGE 1). If AEP-full's applied
count is counting how often the ack won that race, then `UnwantedPrevented =
28 − (times the ack won)` is **a property of the fault injector's timing
distribution, not of the protocol**. A clustered interval on it makes an injector
characteristic look like a protocol constant with error bars.

---

## 0.5 Step 8.1.0 — the fail-closed invariant is NOT checkable retroactively

Full write-up: `reports/phase-report-8-1-0-2026-08-27.md`. Summary:

**(a) NO.** `applied ⇒ durable ack issued` cannot be checked against runs already
collected. Four independent reasons:

1. **No ack event exists in any stream.** The worker stream is exactly
   `clock_reference`, `worker_started`, `composition_validated`,
   `execution_started`, `redis_kill_armed`, `execution_failed`,
   `redis_kill_issued`, `worker_finished`. Nothing about the barrier or the ack.
2. **`dispatch_attempts = 0` in all 240 Phase 9 runs**, both arms, applied and
   not. The per-execution record does not capture the dispatch.
3. **`failure_class = LockAcquisitionError` in all 240 runs**, identically across
   arms and outcomes — no discriminating information.
4. **`applied` is provider-side**, from `oracle_effect_executions` in
   `summary.json`. The provider knows a request arrived and nothing about
   worker-side authorization. The authorization lives in a Redis key
   (`intents.py:1076`) that the kill destroys and nothing dumps.

**(c) It can be added for new runs, in the harness only — no `aep_core` edit.**
The protocol already calls
`_checkpoint("AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT")`
(`intent_workflow.py:492-494`) immediately after the ack is issued and the
authorization recorded, and `_checkpoint` delegates to the harness
(`intent_workflow.py:204-210`). In this regime the installed injector is the
`RedisKillInjector` (`worker.py:119,127,155`), whose `checkpoint()` receives
every boundary and discards the ones it is not armed for
(`redis_kill.py:260-263`). The harness already receives the post-ack signal and
throws it away. This matters because audit finding **S4-A** was that `aep_core`
changed after being certified untouched.

**(d) One-directional.** `ack ⇒ applied` is **false** — the kill can land after
the ack and before transmission, and the crash-point vocabulary names that exact
window (`crash_points.py:117-119`). Only `applied ⇒ ack` is claimed.

**Honesty caveat, carried into the report.** The invariant is *enforced in code*
(`DispatchAuthorizationError`, `intents.py:136,1119,1142,1161,1229`), and
`_checkpoint` is awaited on the protocol path, so `dispatch ⇒ checkpoint
traversed` holds by construction. Zero exceptions is near-certain, and what the
check primarily exercises is the harness's emission fidelity along a single code
path. It is **confirmatory of code-enforced behaviour**, not an independent
discovery.

---

## 0.6 The estimand decision

**Primary estimand for the phase: §3.1, the covariate-adjusted class effect.**
That is the question B2 exists to answer. *(AMENDMENT 1.)*

Rev. 2 made the conditional invariant primary and derived k from its
rule-of-three bound. That was wrong for the reason rev. 2 itself stated twice and
then ignored: the invariant is near-certain by construction, so sizing the phase
around it would have sized it around the quantity least able to be informative.

**The invariant is retained as a pre-registered integrity check with a HALT**
(§3.3). After 8.2 it costs nothing and rides along on any collection.

**For 8.1, which may use only data that already exists:** the clustered interval,
reframed as a characterisation of the fault injector. Forced, not chosen — §0.5
shows the invariant is unavailable retroactively. The substantive point survives,
because the §0 mechanism *is* checkable on existing runs.

---

## 1. Coverage, derived from data

Source: `experiments/results/matrix/analysis/per-execution.csv` (3 780 rows,
tracked, frozen). Endpoint ↔ response class is 1:1 (`run_matrix.py:94-98`).

| regime | endpoint | capability class | systems | runs | executions |
|---|---|---|---|---|---|
| `(session-3)` | `payments` | AUTHORITATIVE_READBACK | 7 | 117 | 1 170 |
| `(session-3)` | `notifications` | POSITIVE_ONLY_READBACK | 7 | 117 | 1 170 |
| `(session-3)` | `ledger_postings` | NO_READBACK | 7 | 117 | 1 170 |
| `p0` | `payments` | AUTHORITATIVE_READBACK | 7 | 21 | 210 |
| `redis-kill-preack` | `ledger_postings` | **NO_READBACK only** | 2 | 60 | 60 |
| `redis-kill-inflight` | — | — | **0** | **0** | **0** |

117×3 + 21 + 60 = **432 runs**, reconciling exactly with the paper's headline
count. Ablation systems are `AEP_FULL` and `B3_INTENT_NO_BARRIER`
(`run_matrix.py:113-116`).

**Do data and prose disagree about capability classes under `redis-kill-preack`?
No.** Data says NO_READBACK only; `main.tex:148`, `08-threats.tex:85`, the
roadmap and backlog B2 all agree. This was audit blocker PR-1 and Phase 7 fixed
it in all four places. **The prose is correct.**

Three adjacent disagreements, which are not that question:

1. The regime definition describes a two-endpoint design never fully collected
   (`run_matrix.py:249` and its justifying comment). Only `ledger_postings` has
   data. Not an error — uncollected cells are printed in the plan — but the
   comment reads as description and is intent.
2. `redis-kill-inflight` is fully defined (`run_matrix.py:259-279`) with zero runs.
3. 240 runs existed on disk that no tracked file accounted for. **Closed by 8.0.**

---

## 2. Reachability

**AUTH — reachable today, no code change.**

```
uv run python -m experiments.run_matrix \
  --regime redis-kill-preack \
  --results-root <root> \
  --max-tier 2
```

`payments` is already in the regime's `endpoints` (`run_matrix.py:249`); the
regime pins its own shape — `runs_per_cell=30`, `executions_per_run=1`,
`workers=1`, `systems=ABLATION_SYSTEMS` (`run_matrix.py:239-242`). Omitting
`--endpoint` collects **both** endpoints, which is the paired design. Tier 2
(`_tier`, `run_matrix.py:408-409`).

**POS_ONLY — NOT reachable, and the repo says twice that it is.**

```python
# run_matrix.py:249
    endpoints=("payments", "ledger_postings"),

# run_matrix.py:441-445
        regime_endpoints = [
            entry for entry in endpoints
            if regime.endpoints is None or entry[0] in regime.endpoints
        ]
```

`notifications` is filtered out *after* `--endpoint` is applied
(`run_matrix.py:626-637`), so `--endpoint notifications --regime
redis-kill-preack` yields **zero cells, silently**. Both
`docs/24-revision-backlog.md:81-83` and audit §S4.10 item 1 claim "no code
change" for auth **and** pos-only: **true for AUTH, false for POS_ONLY.**

**POS_ONLY deferred; the route is a new regime, not an edit.** Extending the
tuple would be *identity*-safe — `Cell.key` omits `response_class`
(`run_matrix.py:341-349`), `cell_seed` derives from `cell.key` and
`MATRIX_VERSION` (`run_matrix.py:526`), and `test_cell_identity.py:88-103`
asserts subset-and-uniqueness rather than counts — but identity-safe is not
provenance-safe: the tuple would no longer describe what the frozen cells were
collected under. POS_ONLY gets a new `REGIME_REDIS_KILL_PREACK_POSONLY`,
leaving `REGIME_REDIS_KILL_PREACK` byte-for-byte intact and putting the
provenance in the slug hash. **Out of scope for Phase 8.**

**Why AUTH and NO_READBACK are the right pair** — the regime's own comment
(`run_matrix.py:243-248`): they are where the same mechanism has two different
consequences. They are the extremes; POS_ONLY interpolates. That, not "no code
change", is the reason.

---

## 3. Prediction — pre-registered in 8.3, before any 8.4 run

Mechanism statement inherited verbatim from P9-A §4 (`85e6c54`, before any data
existed): whether an effect reached the provider is a fact about what was put on
the wire; a read-back is exercised afterwards, by recovery, and can change what
the system is able to **say**, not what was **done**.

### 3.1 PRIMARY — the class effect on the applied column, covariate-adjusted

Logistic regression of applied ∈ {0,1} on capability class, with
`log(issue_to_return_ns)` as covariate and session as a fixed effect.

| | Predicted | CONFIRMS | CONTRADICTS |
|---|---|---|---|
| class coefficient | **0** | 95% CI contains 0 | CI excludes 0 |

**A contradiction is the finding.** If class moves the applied column, that
contradicts the mechanism as the paper describes it. The report says so, names
the affected claims in `06-evaluation.tex` and `08-threats.tex`, and does **not**
re-run to see whether it goes away — Phase 9C set that precedent explicitly.

### 3.2 SECONDARY — the unadjusted paired difference

`d_i = applied_AUTH(i) − applied_NO_READBACK(i)` for AEP-full, session as the
unit, mean with a two-sided 95% t-interval on k−1 df. A robustness check on 3.1.
**The naive Wilson interval on pooled runs is forbidden** — 9C §3 shows it four
times too narrow.

### 3.3 INTEGRITY CHECK (not an estimand) — the fail-closed invariant

For every AEP-full execution with an applied effect, the run must show traversal
of `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT` for that execution.
Predicted: **zero exceptions**, near-certainly, by construction (§0.5).

**Any exception HALTS the phase** — it would mean a dispatch without
authorization, which `DispatchAuthorizationError` is supposed to make impossible.
Reported and minimised, not re-run away. **The report must state that this is
confirmatory of code-enforced behaviour along a single code path**, and must not
present it as a discovered property. One-directional: `ack ⇒ applied` is not
claimed.

### 3.4 Checks carried forward

- **Unfalsifiability check (P9-A §4.4), verbatim.** If AUTH's declared ambiguity
  does not drop below 30/30, the read-back is not being exercised and the cell
  measures something other than what it claims; the applied-effect comparison is
  then uninterpretable regardless of what it shows, and the output is a **defect
  report about the cell**, not a finding about the mechanism.
- **Balance check.** Runs are ordered cell-by-cell, not interleaved
  (`run_matrix.py:451-482`), so a session's two arms are ~18 min apart. Compare
  arms' `issue_to_return_ns` distributions per session; pre-declared threshold
  **|median difference| ≤ 100 ms**, half the measured 194 ms run-level effect.
  Failing sessions are reported individually; **no session is dropped**.
- **HALT (P9-A §4.3):** any `undetected_duplicates > 0`; any `lost_effects > 0`;
  `executions ≠ runs × 1` in any cell; a `(system, response_class)` pair twice.

---

## 4. Integrity

**Where new data lands.** `experiments/results/b2-paired-s<N>-<date>/`, one root
per session. **Never** into `experiments/results/matrix/` — writing a
re-collected NO_READBACK row into the frozen tree would move
`\UnwantedPrevented{}`, `\UnwantedP{}` and the headline row.

**Freeze and verify, per root, in order:**

1. `analyze.py --results-root <root>` → `analysis/`.
2. `freeze_results.py --results-root <root>` → `MANIFEST.csv`, `MANIFEST.md`,
   `SHA256SUMS` over the manifest plus every file in `analysis/`
   (`freeze_results.py:174-179`). **Run it under Linux** — see §9 finding 1.
3. **On-disk proof:** `sha256sum -c SHA256SUMS`; paste raw output and exit code.
4. **Staged-blob proof:** after `git add`, `git cat-file blob :<path> | sha256sum`
   compared against that file's `SHA256SUMS` line. This is the check that caught
   `core.autocrlf` corrupting 6 of 7 committed CSVs in Phase P while `git diff`
   showed clean. `.gitattributes:19` *should* make it impossible — which is why
   it is verified, not assumed.
5. Any mismatch: **STOP**, report BLOCKED. Do not regenerate the manifest to make
   it agree.

**Tracking.** `.gitignore` excludes `experiments/results/*`; each new root needs
the negation pattern (re-open each level, then re-close it). Analysis products
and manifests only.

---

## 5. Blast radius

| File | Phase | Change |
|---|---|---|
| `prompts/phase-8-b2.md` | 8.0 ✅ | new |
| `.gitignore` | 8.0 ✅, 8.4 | negations |
| `experiments/results/b2-*-2026-08-21/` | 8.0 ✅ | 32 files tracked |
| `reports/plan-phase-8-b2.md` | 8.0 ✅ | this document |
| `PAPER_ROADMAP.md` | 8.0 ✅ | provenance; CURRENT PHASE; rows 8/9 |
| `reports/phase-report-8-1-0-2026-08-27.md` | 8.1.0 ✅ | new |
| `paper/sections/06-evaluation.tex`, `08-threats.tex` | 8.1 | interval + mechanism |
| `paper/generated/numbers.tex` | 8.1 | via generator only |
| `scripts/paper_tables.py` | 8.1 | new macros |
| `experiments/harness/redis_kill.py` | 8.2 | ack event; surface kill latency |
| `experiments/analyze.py` | 8.2 | kill-latency column |
| `experiments/harness/runner.py` | 8.2 | daemon identity; harness version |
| `reports/phase-report-8-prediction-<date>.md` | 8.3 | before any run |
| `experiments/results/b2-paired-s*/` | 8.4 | new data |
| `reports/phase-report-8-b2-<date>.md` | 8.6 | result |

**Paper numbers that could move.**

*From 8.4: none.* AUTH data lands in a separate root; `numbers.tex` is generated
from `experiments/results/matrix/analysis/`, untouched.

*If AUTH were later folded into the frozen tree* — not this phase.
`paper_tables.py:1546-1600` is already prepared (Phase 9's P9-0, `71ddf7a`):
**8 new macros** suffixed `Auth`, and **0 existing macros change** —
`HEADLINE_KILL_CLASS = "NO_READBACK"` (`paper_tables.py:1549`) binds the headline
set explicitly (`paper_tables.py:1602-1651`). **Gate consequence:** the orphan
check (`check_paper_numbers.py:168-184`) fails on any macro defined and not
cited, so folding AUTH in *forces* prose citing all 8.

*From 8.1: this is where numbers move.* Macros consumed at `main.tex:168-171`,
`06-evaluation.tex:332-415,588`, `08-threats.tex:69-85,364`.
`\UnwantedPrevented{}` = 18 becomes an interval plus a mechanism statement.
Enumerated exactly in 8.1's pre-flight, before any generator edit.

---

## 6. Cost, and k re-derived from the primary estimand

**The wall-time model is right, and I checked it.** `estimated_run_seconds`
(`run_matrix.py:491-516`): `crash_probability = 0.0` zeroes the lease and retry
terms, and both arms have `has_recovery_service=True` (`contract.py:252,326`):

```
2.5 + 1×3.2 + 25.0 + 5.0 = 35.7 s/run   →   60-run session = 2 142 s
```

Observed (9C §9): s1 **2 173 s** (1.014), s2 **2 140 s** (0.999), s3 **2 143 s**
(1.000), P9-B **2 712 s** (1.266, on the busiest host). **Within 1.5% on three of
four.** A quiescent-host model, to be read as a floor.

### k = 4, derived from §3.1

*(AMENDMENT 1: rev. 2's k came from the invariant's rule-of-three bound. That
calculation is discarded, not reused.)*

The design blocks on session and adjusts for kill latency, which is what brings
the residual variance back to roughly binomial — 9C measured over-dispersion
**5.37** for unblocked pooling, so **the binomial calculation below is valid
only because of the blocking**. Baseline `p₀ = 53/150 = 0.3533` (AEP-full,
NO_READBACK, five sessions). Per-arm n = 30k. MDE at 80% power, α = 0.05
two-sided:

| k | n/arm | **MDE (pp)** | §3.2 half-width (pp) | run time |
|---|---|---|---|---|
| 2 | 60 | 24.4 | 110.8 | 2.4 h |
| 3 | 90 | 20.0 | 30.6 | 3.6 h |
| **4** | **120** | **17.3** | **19.6** | **4.8 h** |
| 5 | 150 | 15.5 | 15.3 | 6.0 h |
| 6 | 180 | 14.1 | 12.9 | 7.1 h |

**The stated minimum detectable class effect is 17.3 percentage points**, which
is **30% of the barrier's own measured effect** (B3 140/150 vs AEP-full 53/150 =
58.0 pp). Rationale: the paper's claim is that capability class moves the
*ambiguity* column by ~100 pp and the *applied* column not at all. A movement of
the applied column by a third of the barrier's own effect would materially
qualify that claim; a smaller one would not change what the paper says.

**k = 4 is also the point where the two analyses become commensurable** — 3.1's
MDE (17.3 pp) and 3.2's half-width (19.6 pp) agree, so the robustness check can
actually corroborate the primary. At k = 3 they diverge badly (20.0 vs 30.6),
which would make 3.2 decorative.

**Sensitivity to Uncertain #3** *(AMENDMENT 1, fourth bullet)*. If AUTH's applied
fraction differs from NO_READBACK's 0.358, the variance and hence the MDE move.
At k = 4:

| AUTH applied fraction | 0.05 | 0.10 | 0.20 | 0.358 | 0.50 | 0.65 |
|---|---|---|---|---|---|---|
| **MDE (pp)** | 13.4 | 14.4 | 15.9 | **17.3** | 17.7 | 17.3 |

**The MDE is bounded in [13.4, 17.7] pp across the entire plausible range**, so
the design's power does not depend on guessing AUTH's rate correctly. This is the
one input that could have invalidated the calculation, and it does not.

**k = 4 is committed and will not be extended.** If realised precision is worse,
it is reported worse. Adding sessions after seeing results is optional stopping.

**Cost:** 4 × 120 runs × 35.7 s = **4.76 h** run time; budget **5.5 h**.

**Stop mid-run and come back if:** any HALT in §3.4 fires, or any §3.3 exception;
`canary_survived + canary_lost ≠ 30` in any arm; `uptime_after_seconds` large in
any run (`redis_kill.py:330-333`); host load outside 9C's observed 0.10–2.49; a
session kill-latency median outside the 859–1 216 ms envelope (record, then
continue); `git status` not clean at session start; session wall time > 1.5×
model (3 213 s). Stopping means: finish the run in flight, freeze what exists,
report the partial session, and **do not** fold it into the k = 4 set.

---

## 7. Sequenced steps

### 8.0 — Provenance and rescue. ✅ DONE (this commit).

1. **The four Phase 9 roots are frozen and tracked.** `freeze_results.py` per
   root: 60 runs, 60 executions, 2 cells, 0 incomplete, each. `sha256sum -c`
   **16/16 OK, exit 0** in all four. **28/28 staged blobs** re-hashed with
   `git cat-file blob` and matched against `SHA256SUMS`; the four `SHA256SUMS`
   blobs are byte-identical to disk with 0 CR bytes. `git add` reported 32
   additions and 0 modifications. Commit `b2ab570`.
2. **Uncertain #3 resolved: the 2026-08-07 kill runs survive.** `/root/aep` is
   intact (496 MB) and holds all 60 kill-cell run directories under the same cell
   hashes (`8530cc0f`, `99ac28be`), with `events.jsonl` present in **60 of 60**.
   §0's mechanism therefore rests on **five** sessions and 150 AEP-full runs.
   Extending to five broke the session-level monotonicity (§0) and left the
   run-level result intact and stronger.
3. `prompts/phase-8-b2.md` committed, with the `--plan-only` correction.
4. This plan committed.
5. **Prompt provenance** note in `PAPER_ROADMAP.md`.
6. CURRENT PHASE refreshed; Phase 8 and 9 rows added.

### 8.1.0 — ✅ DONE. `reports/phase-report-8-1-0-2026-08-27.md`.

### 8.1 — The paper fix, from data that already exists. No new runs. ~3 h.

1. **Poolability — and 8.0 found a new obstacle to it.** 9C §6 records identical
   cell hash, per-run seed, `platform` fingerprint, pinned Redis digest, and 40
   of 44 `run-config.json` keys. **List the four differing keys and adjudicate
   each** — 9C names one (`suspend_disabled_declared`) and calls the other three
   "bookkeeping" without listing them.
   **Then adjudicate the filesystem difference (§9 finding 2), which no config
   key records.**
2. **Interval**, session-clustered, session as the unit. Naive Wilson on pooled
   150 is **forbidden**.
3. **Mechanism** (§0): the run-level +194.1 ms at p = 0.00005 over 150 runs, with
   the B3 control at −12.1 ms, p = 0.76. **Use the run-level statement. Do not
   claim a monotone session ordering** — ρ = 0.700, not 1.000.
4. **B3's flatness as control:** 28/30 in five sessions, range 0.
5. **`08-threats.tex`:** magnitude is session-variable, direction held 5/5, and
   the effect size is a function of the host's kill-latency distribution.
6. **Enumerate every macro and table that moves** before editing the generator.

**Verification:** `check_paper_numbers.py` exits 0; `build_paper.sh` succeeds;
full pytest as CI runs it; every changed macro traced to a CSV cell.

### 8.2 — Instrumentation. ~1.5 h.

1. **The ack event** (§0.5) — emit on traversal of
   `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT`, carrying `execution_id`.
   Harness only; **no `aep_core` edit**.
2. **Surface the kill latency**: add `issue_to_return_ns` and `command_ms` to
   `RedisKillRecord.echo()` (`redis_kill.py:325-354`, which omits both) and emit
   a per-run column from `analyze.py`.
3. **Daemon identity and harness version** into `run-config.json`
   (`runner.py:426`) *(AMENDMENT 2c)*.

**The timing bound — measured, not asserted** *(AMENDMENT 2a)*. `EventLog.emit`
does `json.dumps` + `write` + **`flush()`** (`events.py:105-121`); the flush is a
real syscall, and the ack emit would sit on an awaited call at the exact boundary
where the race is decided. Measured on this host, 2 000 iterations of a
representative 364-byte record:

| filesystem | median | p95 | max |
|---|---|---|---|
| ext4 (WSL native) | **5.4 µs** | 11.3 µs | 212.5 µs |
| drvfs (`/mnt/…`, the Windows drive) | **229.7 µs** | 371.9 µs | 2 276.8 µs |

Against the kill-latency envelope (session medians 859–1 216 ms; the
discriminating run-level difference is 194 ms):

- on **ext4**: median cost is **0.0005%** of a ~1 s race and **0.003%** of the
  194 ms difference — negligible by three orders of magnitude;
- on **drvfs**: median **0.02%** of the race, worst observed case 2.28 ms =
  **0.23%** of the race and **1.2%** of the discriminating difference.

**Both are negligible; ext4 is negligible by a margin that needs no argument.**
Per AMENDMENT 2b, buffering is therefore *not* required — but **8.4 must collect
onto ext4**, which drops the cost ~40× and also removes the confound in §9
finding 2. If a future collection must use drvfs, buffer the emit and flush after
the execution completes.

**Show it cannot alter counts.** All three additions are records outside the
protocol path: `kill_redis` already computes `command_ms` and discards it; the
ack emit is on a checkpoint the injector already receives and already discards
(`redis_kill.py:260-263`); the daemon probe runs at run construction, before the
worker starts. Nothing reads them back.
**Verification:** (a) full pytest green; (b) re-run `analyze.py` over an
*untouched* Phase 9 root and confirm every pre-existing column is byte-identical
to its frozen copy, with only the new column added. **(b) tests analysis, not
collection timing** — the timing argument above is what covers collection, and it
is stated as a measured bound rather than as an assertion.

### 8.3 — Pre-registration. Commit before any 8.4 run. ~1 h.

`reports/phase-report-8-prediction-<date>.md` containing §3 verbatim: primary
3.1, secondary 3.2, integrity check 3.3, **k = 4 with the §6 derivation and its
stated 17.3 pp MDE**, the balance check, the unfalsifiability check, HALT
conditions, and the no-extension commitment. Record `git rev-parse HEAD`,
`git status --porcelain`, and P9-A §2's four commands re-run at this commit.

**Verification:** the pre-registration's commit hash precedes the first data
commit. The one property that cannot be repaired afterwards.

### 8.4 — Collection. 4 sessions, **on ext4**. ~5.5 h.

Per session: confirm host quiet and `git status` clean; record host load; run
`run_matrix.py --regime redis-kill-preack --max-tier 2` (both endpoints,
unfiltered) with the results root **on the WSL native filesystem**; record load
again; freeze and verify per §4; commit before the next.

**The report must state that Phase 9's roots and Phase 8's were collected under
different harness versions and on different filesystems**, so nobody later pools
them without noticing *(AMENDMENT 2c)*.

**Verification per session:** 120/120 runs; `sha256sum -c` N/N OK; staged blobs
match; canaries 30/30 in all four arms; no HALT; no §3.3 exception.

### 8.5 — Analysis. ~2 h.

Integrity check 3.3 first (it gates), then the balance check, then primary 3.1,
then secondary 3.2. **Compute in that order and say so.** Score the prediction
honestly, as 9C §7 did, including what was predicted wrongly.

### 8.6 — Report. ~2 h.

Sections A–H, §F non-empty. If a prediction is contradicted, report it as the
finding; do not re-run.

---

## 8. What this does not do

- **Two capability classes on one host at one crash point is still one host at
  one crash point.** POS_ONLY is deferred to a new regime; the crash point stays
  `after_intent_before_barrier`; `redis-kill-inflight` stays at zero runs.
- **§0 sharpens why that matters.** The effect size is a function of the host's
  `docker kill` latency distribution. A second host would not add a replicate —
  it would sample a different distribution and probably a different magnitude.
- **The integrity check is confirmatory, not exploratory** (§0.5, §3.3).
- **The barrier's durability claim is untouched.** Backlog B1 remains the gap; no
  process-level fault can close it (`redis_kill.py:26-40`).
- **Detection is not re-examined.** 540 crashed-regime executions per arm across
  three classes stand unchanged.
- **No submission, upload, DOI, or tag.**

---

## 9. Found but not fixed

1. **`scripts/freeze_results.py` is not portable, and run on Windows it produces
   an unverifiable manifest.** `path.relative_to(root)` yields backslash
   separators and `write_text` yields CRLF, so a Windows-generated `SHA256SUMS`
   reads `analysis\table-1.csv` with a trailing `\r` and `sha256sum -c` fails to
   open all 16 entries (observed: `WARNING: 16 listed files could not be read`,
   exit 1). The committed convention is forward-slash + LF. Phase Q's
   `.gitattributes` fixed the *checkout* direction; this is the *generation*
   direction and is unfixed. **Worked around in 8.0 by generating under WSL** —
   §4 step 2 now says so. A one-line fix (`as_posix()` and `newline="\n"`) would
   close it.
2. **The paper's kill cell and all four replication sessions were collected on
   different filesystems, and no config key records it.** The 2026-08-07 cell is
   in `/root/aep` (ext4); the four `b2-*` roots are on the Windows drive, reached
   from WSL through drvfs — confirmed by their absence from
   `/root/aep/experiments/results`. Measured, event-log append+flush costs
   **5.4 µs on ext4 and 229.7 µs on drvfs, a ~40× difference** (§7, 8.2). 9C's
   "40 of 44 config keys identical" check is structurally unable to see this,
   because it is not in the config. **This is a live poolability question for
   8.1, and a candidate partial explanation for why the 2026-08-07 session breaks
   the session-level ordering in §0.** Stated as a difference that must be
   adjudicated — *not* as a demonstrated cause. Nothing here shows drvfs latency
   changes the applied rate; it shows the environments differ systematically in a
   quantity plausibly on the critical path.
3. **`docs/24-revision-backlog.md:81-83` and audit §S4.10 item 1 both say B2
   needs "no code change"** for auth *and* pos-only. False for pos-only
   (`run_matrix.py:249`), which yields zero runs silently.
4. **`--plan-only` is not read-only** (`run_matrix.py:1182-1191`). Corrected in
   `prompts/phase-8-b2.md`.
5. **The harness records the kill latency but nothing surfaces it.** Reaching §0
   required parsing 300 `events.jsonl` files. *(Fixed in 8.2.)*
6. **No ack is recorded anywhere** (§0.5). *(Fixed in 8.2, prospectively only.)*
7. **`redis-kill-inflight` is fully defined with zero runs**
   (`run_matrix.py:259-279`).
8. **`CLAUDE.md` at the repo root is not instructions** — an unexecuted
   `wsl … cat >> CLAUDE.md` shell command referencing a `stage3-prep-office-…`
   branch and a `docs/STAGE3_OFFICE_ROADMAP_AND_PROMPTS.md` that do not exist
   here. Untracked; P9-A §1 noted it as "untracked, unrelated, pre-existing".
9. **`\UnwantedPrevented{}` = 18 is printed as a point estimate** for a quantity
   ranging 8–24. Promoted to a phase (8.1).
10. **`execution_failed` and `redis_kill_issued` carry the same `seq` from the
    same `source`** — the watchdog thread and the event loop race on the sequence
    counter. Cosmetic for every number here (both read by name, not order), but
    `seq` is not a total order within a run and must not be relied on as one.

---

## 10. Uncertain

1. **Whether the 2026-08-07 cell pools with the four 2026-08-21 sessions.** Now
   turns on *two* things: the three unlisted `run-config.json` keys, and the
   filesystem difference in §9 finding 2. **Resolved by:** 8.1 step 1.
2. **AUTH's applied fraction.** §6 shows the MDE is bounded in [13.4, 17.7] pp
   across the whole plausible range, so this no longer threatens the design.
   Reported from the first session; **not** acted on — k stays 4.
3. **sd(d) under pairing.** §6 uses ≈3.70 counts, assuming pairing removes the
   whole between-session component. If the session effect acts differently on the
   two arms, §3.2's interval widens. Reported wider; k unchanged.
4. **Whether within-session drift breaks the pairing.** Cells run as consecutive
   30-run blocks ~18 min apart. **Resolved by:** the balance check (§3.4).
5. **Whether 8.1's reframing survives review.** Five replications plus a measured
   mechanism is, I argue, more than one cell plus a point estimate. A reviewer may
   read a widened interval as a retreat regardless. **Resolved by:** human review.
