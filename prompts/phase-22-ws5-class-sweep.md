# Phase 22 — WS-5: the class sweep, 4 → 6 sessions

**Rule 4.** Committed before any run directory for sessions 5 and 6 exists, and
with the two pre-launch rulings (`redis_container`, session equivalence) already
written down.

**Issued:** 2026-09-14.

---

## The prompt, as issued

> Two sessions added to the existing four. Six is the minimum at which the
> paired sign test can reject at all — the floor is 2/2ⁿ, 0.125 at four and
> 0.03125 at six. **This is pre-registered as a bound, not a test.** Six
> sessions gives 80% power only against effects far larger than the ±5 pp
> margin; the claim made will be an interval plus an explicit statement of what
> it could not have detected. Do not report a p-value as the headline. ~3 h.
>
> 1. Rule on `redis_container` before collecting.
> 2. Commit this prompt.
> 3. Establish what a "session" is, from the existing four, not from memory.
> 4. Pre-flight, phase 21's form.
> 5. Launch. 2 sessions × 30 runs per arm × 2 arms.
> 6. Do not analyse.
> 7. Freeze with no temporal gap.
> 8. Teardown verified.
> 9. R15, scoped.
>
> Out of scope: zero `.tex`, any analysis of these runs, the four existing
> sessions (rule 2), phase 20's three findings.

---

## Ruling 1 — `redis_container`: nothing to fix here, and why

**Position: the field will be correct in these two sessions without any change,
and no change is made.**

Phase 21's finding was narrower than it looked. `redis_container` and
`environment.redis_storage_backing` record the **compose service's** container,
regardless of where `--redis-url` points. That is wrong only when the two
disagree — which is what happened in the `always` arm, where `--redis-url` aimed
at a second Redis on 6383 while the recorded container stayed
`aep-phase2-redis72`.

The class sweep does not do that. Read from the existing four rather than
assumed:

```
redis_url        redis://127.0.0.1:6381/15      (run_matrix's default)
redis_container  aep-phase2-redis72
redis_service    redis-phase2
```

6381 **is** the published port of `aep-phase2-redis72`. The container named is
the container used. Sessions 5 and 6 use the same default, so the field is
accurate for them too.

**So there is nothing to fix at the source for this collection, and fixing the
harness would change none of these 120 runs.** The general defect — that the
environment block follows compose rather than `--redis-url` — stands as phase
21 recorded it, unfixed, and is not re-opened here. This also keeps the two new
sessions byte-comparable with the four existing ones on this field, which is
what rule 2 and the session-equivalence requirement both want.

---

## Ruling 2 — `suspend_disabled_declared`: declared true, and the asymmetry is
## recorded rather than hidden

The four existing sessions record **`suspend_disabled_declared = False`** on all
120 runs. The phase 22 acceptance criteria require **true** on every new run.
Both cannot hold, so this is ruled explicitly.

**Position: declare it true for sessions 5 and 6.**

* E5 exists to stop undeclared collections. Collecting new data with worse
  provenance, in order to match a gap in older data, is the wrong direction.
* **It does not touch the quantity the class sweep measures.** `analyze.py`
  drops an undeclared run from the *timing* path only —
  `runs_dropped_for_undeclared_suspend_policy` — and the comment is explicit
  that "a run failing either contributes its **counts**". The class sweep is a
  **rate** comparison (per-session pp differences, `SESOI_RATE_PP`), and rates
  are unaffected.

Verified rather than argued, from the frozen session's own analysis:

```
runs                                          30, 30
runs_with_usable_timing                        0,  0
runs_dropped_for_undeclared_suspend_policy    30, 30
runs_dropped_for_clock_suspension              0,  0
```

All 120 existing runs are already excluded from timing. Nothing the class sweep
uses depends on it.

**The trap this creates, stated so the analysis pass does not fall into it.**
After this collection, a six-session tree will contain four sessions with **zero**
usable-timing runs and two with **all** of them. Any timing number computed
across "the six sessions" would be two sessions wearing a six-session label.
**The six-session claim is a rate claim only.** If a timing question is ever
asked of this tree, it has two sessions of data, not six.

---

## Ruling 3 — what a session is, established from the four

Not from memory. Every field below was read out of the existing run-configs.

| property | value, identical in all four |
|---|---|
| runs | 60 = **30 `AEP_FULL` + 30 `B3_INTENT_NO_BARRIER`** |
| regime | `redis-kill-preack` — `redis_kill_point=after_intent_before_barrier`, `redis_kill_executions=1`, `redis_kill_delay_ms=0` |
| endpoint | **`ledger_postings`** only (the regime defines two; the sweep uses one) |
| crash | `crash_point=None`, `crash_probability=0.0` |
| shape | `workers=1`, `executions_per_worker=1` |
| keying | `CALLER_REFERENCE` |
| dispatch | `EVALUATION` |
| redis | `redis://127.0.0.1:6381/15`, container `aep-phase2-redis72` |
| order | **cell-major** — all 30 `AEP_FULL`, then all 30 `B3` |

**The decisive property: all four sessions share identical run ids and identical
per-run seeds — 60 of 60, in every session.** A session is therefore a *pure
replicate at fixed seeds*, and the between-session variance the pre-registration
prices at 21.3 pp is entirely execution-time nondeterminism — kill timing and
scheduling, not different inputs. That is precisely why the session is the unit
of analysis (rule 6).

It also fixes the command: sessions 5 and 6 **must use the same matrix seed**
(`20260806`, the default). A new seed would make them draws from a different
experiment.

```
python -m experiments.run_matrix \
  --regime redis-kill-preack \
  --endpoint ledger_postings \
  --results-root experiments/results/<new session root> \
  --port 8099
```

`runs_per_cell=30`, `executions_per_run=1`, `workers=1` and the two systems all
come from the regime definition, not from flags — so there is nothing to get
wrong by hand.

### What cannot be matched, said before launching

**The restart discipline between the four sessions is not recoverable from the
artefacts.** Their `environment.redis_container_state` is `None` — the probe
that records `started_at`/`restart_count` post-dates them — so whether Redis was
restarted between sessions 1→2→3→4 is not written down anywhere. What *is*
recoverable is the wall-clock shape: each session ran 35–40 minutes, and the
gaps between them were 25 min, 3 min and 2 min.

Sessions 5 and 6 are therefore run **back-to-back against the same continuously
running Redis**, which matches the short-gap pattern of sessions 2→3→4 and is
the only discipline the evidence supports. This is a limitation, not a match:
if sessions 1–4 did restart Redis between them and the new two do not, that is
an unrecorded difference. It is recorded here instead.

---

## Finding raised before launch, not fixed

`experiments/run_matrix.py:89` — `DEFAULT_RESULTS_ROOT = "experiments/results/matrix"`.
A bare `python -m experiments.run_matrix` writes into, and `--resume`s against,
**the frozen 432-run root every outcome rate in the paper is computed from.**
This is a third instance of the shape behind `docs/25` R16, in the Python driver
— which phase 20's sweep never reached, because it only looked at shell scripts.
Out of scope here and recorded in the phase 22 report. This pass always passes
`--results-root` explicitly.
