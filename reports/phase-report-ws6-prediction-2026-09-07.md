# WS-6 pre-registration: the real durable-execution engine as a baseline

**Written 2026-09-07, before any B5 data exists**, and committed and pushed
before collection, per `docs/26` §3 rule 5. Nothing in the pass that wrote this
was run: no image pulled, no stack raised, no test executed.

Companion document: `experiments/baselines/b5_temporal/B5_SEMANTICS.md`, which
carries the crash-point mapping. **Read its §2.3 before reading §2 below**, and
before believing any agreement this cell reports.

---

## 1. Hypothesis

From `docs/26` §4 task 6.3, stated as two hypotheses with the crash-point
restriction that task does not mention and that §2 makes unavoidable.

**H1 (duplicates).** At the crash points B4 and B5 can *both* be cut at, B5
(`maximumAttempts` unlimited) reproduces B4's undetected-duplicate rate, with the
two arms' run-clustered bootstrap intervals overlapping.

**H2 (lost effects).** At those same points, B5b (`maximumAttempts = 1`)
reproduces B4b's lost-effect rate, on the same interval criterion.

**H3 (non-escalation, the one that matters most).** Neither B5 nor B5b declares
ambiguity to an operator in any run. This is predicted at **exactly zero**, not
"low", because it is structural rather than statistical: the fact required —
whether the provider applied the mutation — is not in the engine's history and
cannot be put there. A single declared ambiguity in either arm refutes the
paper's characterisation of durable-execution engines and is a finding, not
noise.

### 1.1 What the hypotheses deliberately do not say

They do **not** say "B5 confirms B4". They cannot, because of §2.

## 2. The restriction that limits the whole cell

`experiments/harness/crash_points.py` `ROADMAP_CRASH_POINTS` names six crash
points. **B5 can be cut at five of them, and the missing one is
`after_intent_before_barrier`** — the residual pre-ack window
`docs/22-formal-model.md` declares for P2, the point Phase 13's prevention result
is collected at, and the point WS-4 armed `drop_writes` at.

The reason is structural, not a limitation of effort: in Temporal the worker
issues an RPC and the **server** performs the durable write transactionally
before replying, so no worker-side instant exists at which a record is written
but unacknowledged. `SIGKILL` of the worker cannot reach it.
`B5_SEMANTICS.md` §2.0 and §2.3 give the argument.

**B4 and B4b have frozen cells at that point on all three response classes**
(`experiments/results/matrix/analysis/per-cell-metrics.csv`). So the hole is not
shared: it is a hole in B5 where B4 has data.

**Pre-registered consequence.** H1 and H2 are **not tested** at
`after_intent_before_barrier`. That cell will be recorded `not_applicable` with
the reason, using the mechanism `experiments/baselines/crash_points.py` already
provides (`None` in the mapping → `CrashPointNotApplicable` → `not_applicable`
in `run_matrix.py`). **No B4↔B5 agreement claim may be made at that point, and
the paper must not present the comparison as complete.**

## 3. Design

| | |
|---|---|
| Systems | **B5** (`maximumAttempts` unlimited), **B5b** (`maximumAttempts = 1`) |
| Engine | Temporal server + SDK worker, `compose.temporal.yml` (digests to be pinned — §7) |
| Fault | `SIGKILL` of the SDK worker process |
| Crash points | the five reachable of the canonical six; `after_intent_before_barrier` `not_applicable` |
| Endpoints | `ledger_postings` (`NO_READBACK`) and `payments` (`AUTHORITATIVE_READBACK`), per task 6.4 |
| Oracle | the mock provider's ground-truth ledger — unchanged, and never the engine's history |

### 3.1 Run counts

**Primary comparison — 120 runs.** Crash point `after_barrier_before_dispatch`
(exact mapping, `B5_SEMANTICS.md` §2.1), both endpoints, both arms:

| | `NO_READBACK` | `AUTHORITATIVE_READBACK` |
|---|---|---|
| B5 | 30 runs × 10 executions | 30 × 10 |
| B5b | 30 × 10 | 30 × 10 |

30 runs per cell matches WS-4 and Phase 13. It is deliberately **ten times** the
frozen B4/B4b cells, which are 3 runs each: B4's headline 0.95 is a point
estimate on a thin row, and a comparison in which the new arm is as thin as the
old one could not distinguish agreement from coincidence.

**Secondary sweep — 240 runs, collected only if the primary completes.** The
remaining four reachable crash points, `NO_READBACK` only, both arms, 30 × 10.

**Total if both stages run: 360 runs.** At WS-4's observed 61.4 s/run this is
≈6.1 h, but that estimate is **not transferable** — B5's runs include a
Start-To-Close timeout B4's do not (§7 open question 2). The estimate is recorded
as untested and no constant will be edited to match whatever is observed.

### 3.2 Unit of analysis

**The run** (`docs/26` §3 rule 6). Rates are per run; intervals are
**session-clustered bootstrap**, the same estimator Phase 13 and WS-4 use.
Executions are never pooled as independent draws. "Within run-clustered
intervals" in task 6.3 is read as: the arms' intervals overlap.

### 3.3 The third outcome, pre-registered now

`PENDING_AT_DEADLINE` — the run ends with the activity neither re-run nor
abandoned, because the engine's retry had not yet fired. **B4 cannot produce
this** (it has no real timer) and it is neither a duplicate nor a lost effect.

It is registered **in advance** because it is the outcome most likely to be
quietly absorbed after the fact: counting it as "no duplicate" would make B5 look
better than B4 for a reason that is purely an artefact of the observation window.

**Stopping rule for it:** if `PENDING_AT_DEADLINE` exceeds **20%** of runs in any
cell, that cell is **uninformative** and is reported as such. H1/H2 are not
evaluated on it, and the fix is a design change to the timeout, re-registered
before recollection — not a re-reading of the data already in hand.

## 4. Stopping rule

- **Fixed n.** 120 runs primary, 240 secondary. No inspect-and-extend.
- **A session is void** if the engine or the provider restarts mid-collection, or
  the run count is short — **decided on the run count alone, before any outcome
  is read**, which is what kept WS-4 attempt 4's void defensible.
- **Attempt budget: 3.** WS-4 needed five attempts and the instrument was
  simpler. If three attempts fail to produce a complete session, WS-6 is reported
  as *not collected on this host*, with the defects found — the same explicit
  cut `reports/phase-report-14-write-loss-blocked-2026-09-04.md` §10 defines,
  written now rather than after the failures. An attempt is a session that
  collects run data; a launch aborting before any run directory exists is not one.
- **No knob is tuned after seeing an outcome.** The Start-To-Close timeout is
  fixed before collection (§7) and changing it afterwards voids the session.

## 5. The exact analysis to be run

```
uv run --frozen --extra experiments python -m experiments.analyze \
    --results-root <session root>
uv run --frozen --extra experiments python scripts/analyse_b5_agreement.py \
    --session <session root>
```

`scripts/analyse_b5_agreement.py` reads `analysis/per-cell-metrics.csv` for the
B5 arms and the **frozen** B4 cells, computes both session-clustered intervals,
and reports per crash point and endpoint: AGREES / DISAGREES / NOT TESTED, plus
the `PENDING_AT_DEADLINE` fraction and the §3.3 uninformative flag.

### 5.1 Yes — the verdict script will be written before collection

**Explicitly, and for the stated reason.** WS-4's REFUTED verdict was credible
only because `scripts/analyse_write_loss.py` was committed before any write-loss
data existed and run unmodified; the refutation could not have been shaped by the
result. WS-6 needs that more, not less: B5 is a baseline this author is choosing
the configuration of, and a favourable agreement result reported by the person
who predicted it is worth nothing without the ordering.

So: `scripts/analyse_b5_agreement.py` is **committed with its thresholds,
its interval method, and its AGREES/DISAGREES rule fixed, before the first B5
run**, with a test proving it non-vacuously on fixtures where the arms disagree
(rule 13 — a gate that cannot fail is decoration; rule 14 — it lives in
`scripts/` with a test). It is not written in this pass; it is the first task of
the next.

## 6. What each outcome would mean

| Result | Reading |
|---|---|
| H1 and H2 hold at the reachable points | B4 is a faithful model **where it can be checked**. §VIII-A(i) is narrowed, not deleted: "B4 is not Temporal" becomes "B4 agrees with Temporal at five of six crash points; the sixth is unreachable in the vendor's engine by worker crash." |
| H1 or H2 fails | **The more interesting outcome, and it is not a failure of the pass.** B4's rate would then be an artefact of our model rather than of event-sourced re-execution, and the paper must say so and re-scope every B4 claim. Registered now so it cannot be reframed later. |
| H3 fails (any declared ambiguity) | Refutes the paper's characterisation of durable-execution engines. Would be the single most important finding of WS-6. |
| `PENDING_AT_DEADLINE` dominates | The cell is uninformative (§3.3). Reported as such — **not** as agreement. |

**What no outcome licenses.** Nothing here supports a claim about Temporal's
throughput, latency, operational maturity, or correctness as a product, and none
is made. B5's duplicate rate is a **lower bound** — heartbeating is off and the
observation window is finite (`B5_SEMANTICS.md` §5).

## 7. Open questions, carried from `B5_SEMANTICS.md` §7

Settling any of these requires running something, which this pass did not do.
**All must be closed before the first data commit:**

1. **Image digests are not pinned.** `compose.temporal.yml` carries version tags
   and says so in a banner. A tag is not a pin. Resolve and commit the digests
   first.
2. **The Start-To-Close timeout is unset**, and it decides whether a retry lands
   inside the run — i.e. whether H1 is testable at all. Must be measured against
   the provider's response distribution and fixed before collection.
3. **`recovery_deadline_seconds = 120` may not accommodate it.** If it must move
   for B5, B5's runs stop being directly comparable to B4's frozen ones, and that
   is stated rather than absorbed.
4. **Point 6's race may be too narrow to hit on loopback**, in which case
   `after_resolution_before_barrier` is effectively absent too and the mapping
   table is corrected to say so.
5. **The crash injector has to reach an SDK worker.** The delivery mechanism is
   new — the crash points are inside SDK callbacks, not `aep_core` checkpoints —
   and its gate must be proven able to fail before it is trusted (rule 13).

---

## 8. Provenance

- Six crash points read from `experiments/harness/crash_points.py`
  (`ROADMAP_CRASH_POINTS`), **not restated from memory**.
- Partial-mapping pattern and `not_applicable` machinery read from
  `experiments/baselines/crash_points.py`.
- B4/B4b frozen cell inventory read from
  `experiments/results/matrix/analysis/per-cell-metrics.csv`.
- Task definition: `docs/26` §4 WS-6, tasks 6.1–6.4.
- Structure of the semantics document mirrors
  `experiments/baselines/B4_SEMANTICS.md` so the two read side by side.
