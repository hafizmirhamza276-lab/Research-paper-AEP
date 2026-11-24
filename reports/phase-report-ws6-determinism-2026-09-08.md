# WS-6 — why three of four B5 intervals are zero-width

**8 September 2026.** Reading `0c6bcf4`'s session, analysis at `3e633d7`.
Nothing was fixed in this pass and nothing in the paper was touched.

**Conclusion first: the determinism is an artefact of the harness, not a
property of the engine. The `DISAGREES` reading does not yet support a claim
about B4.**

---

## 1. The determinism is total

Per-run counts, straight from `b5-runs.jsonl`, over the non-void runs of each
cell:

| Cell | metric | min | median | max | **distinct values** |
|---|---|---|---|---|---|
| `B5_TEMPORAL` AUTHORITATIVE | duplicate applications | 4 | 4 | 4 | **`[4]`** |
| `B5_TEMPORAL` NO_READBACK | duplicate applications | 4 | 4 | 5 | `[4, 5]` |
| `B5B` AUTHORITATIVE | lost effects | 3 | 3 | 3 | **`[3]`** |
| `B5B` NO_READBACK | lost effects | 3 | 3 | 3 | **`[3]`** |

Every run in three cells produced an identical count. `executions` is 10 in all
120 runs. In the fourth cell, 25 runs gave 4 and 3 gave 5.

A cluster bootstrap over 30 identical clusters resamples 30 identical values, so
every resample has the same mean and the interval collapses to the point. **The
estimator is not doing anything wrong** — it is correctly reporting that this
data has no between-run variability. The defect is upstream of it.

## 2. The cause: every run's provider was seeded identically

All **120** per-run provider configs carry `seed: 20260908`. The 120
`ledger_path` values are distinct, so per-run ledger isolation works — only the
seed does not vary.

`collect.RunProvider.start()` derives each run's config by copying the template
and rewriting one line:

```python
if line.startswith("ledger_path:"):
    out.append(f"ledger_path: {self.ledger_path}")
```

`experiments/mock_api/supervisor.py` already provides the right facility —
`render_config(template, dest, ledger_path=…, seed=…)` — and its module
docstring exists **because this exact hazard was found once before**, in Session
3's D0(ii) gate:

> One provider process per run, one ledger per run, one freshly seeded generator
> per run. A run's fault stream is then a function of its seed alone…

`RunProvider` does not use it. It fixed the ledger half of that lesson and
dropped the seed half.

`MockLegacyAPI` draws its three fault decisions from one
`random.Random(config.seed)` per process (`service.py:102,156-158`). Same seed,
same process-lifetime stream, same decisions at the same request ordinals.

### Verified on the data, not only in the code

Fault-decision signatures from each run's `ground_truth.run.jsonl`:

| Cell | runs | **distinct fault-stream signatures** | distinct metric values |
|---|---|---|---|
| `b5_temporal` / payments | 30 | **1** | `[4]` |
| `b5b` / ledger_postings | 30 | **1** | `[3]` |
| `b5b` / payments | 30 | **1** | `[3]` |
| `b5_temporal` / ledger_postings | 30 | 3 | `[4, 5]` |

The correspondence is exact: **the only cell with any outcome variation is the
only cell with any fault-stream variation.** There, 25 runs made 15 provider
requests and 3 made 16 — a longer request sequence walks further into the same
RNG stream, which is the one place genuine engine nondeterminism leaked through.

## 3. Separating the three candidates

- **The crash fires at a fixed point.** True — `crash_probability=1.0` at one
  crash point — and it fixes *when* the worker dies. Contributory, not
  sufficient.
- **The supervisor respawns once, so the retry set is fixed.** Also
  contributory: every run records `worker deaths=1, respawns=1`.
- **The provider's 15% timeout and 5% error should have introduced variation and
  did not.** **This is the decisive one**, and the discriminating evidence is
  that *the harness seed did vary*: `session.py` sets
  `seed=arguments.seed + entry["repetition"]`, so all 30 runs of a cell had
  different `RunConfig` seeds and therefore different targets and execution ids.
  The outcome still did not move. What did not vary was the provider's RNG, and
  the outcome tracked the provider's RNG.

## 4. What this means for reporting an interval

**It should not be reported as one.** The 30 runs of a cell are 30 replays of a
single fault pattern, so the effective sample size for the quantity of interest
is **one fault pattern, not 30 runs**. The zero-width interval is a true
statement about the resampling distribution of 30 identical numbers and a
meaningless one about uncertainty in B5's rate: its coverage is 0%.

This is the same finding Phase 13 recorded about its in-flight variant —
*"Session 2 is a deterministic replay, not an independent replication… effective
n = 120, not 240"* — recurring in a different harness for a different reason.
There it was shared seeds across sessions; here it is one seed across all runs.

## 5. B4's width, read from the same place

B4's three runs, from `experiments/results/matrix/*/run-config.json` and
`summary.json` (cell: `after_barrier_before_dispatch`, payments):

| run | seed | duplicate applications | duplicate **executions** |
|---|---|---|---|
| r0 | 2132319289 | 13 | 10 |
| r1 | 243604778 | 12 | 9 |
| r2 | 1364984291 | *(no `summary.json`)* | 9 by difference |

The frozen cell records `successes 28 / total 30, runs 3, clusters 3`, and
10 + 9 + 9 = 28 accounts for it.

So **both** things the question offered are true, and they are different things:

- **B4's per-run counts genuinely vary** (9, 9, 10), and each run used a
  **different seed**. B5's do not vary, and every run used the same seed.
- **B4's width is also coarse because it has 3 clusters.** With three clusters
  of ten, resample means land on multiples of 1/30, which is why the interval
  reads as round as `[0.9, 1.0]`.

**But neither explains the non-overlap.** The gap is in the point estimates —
0.40/0.41 against 0.93/0.97, and 0.30 against 0.97/0.87 — roughly 0.5 wide.
B4's interval would have to be some five times wider to reach B5's. The
non-overlap is not an artefact of interval width on either side.

What *is* unsupported is the precision claimed on the B5 side: there is no
established error bar on B5's rate at all, because the data contains no
independent replication of the thing that drives it.

## 6. A second, independent defect: H1 compares two different quantities

Found while checking the above; **recorded, not fixed**.

`analyse_b5_agreement.py:371-374` maps the frozen metric to the B5 field:

```python
"undetected_duplicate_rate": "undetected_duplicate_applications",
"lost_effect_rate":          "lost_effect_executions",
```

The frozen numerators in `experiments/analyze.py:664-670` are **0/1 per-execution
indicators**:

```python
if metric == "undetected_duplicate_rate":
    return int(execution.is_undetected_duplicate)
if metric == "lost_effect_rate":
    return int(execution.is_lost_effect)
```

So:

- **H2 is units-consistent.** Both sides count *executions*.
- **H1 is not.** B5's numerator counts duplicate **applications**; B4's counts
  **executions that had any duplicate**. An execution with three duplicate
  applications contributes 3 on the B5 side and 1 on the B4 side.

The two are demonstrably different in this data. Each per-run `summary.json`
carries both, and they disagree:

```
  55 runs   applications=4   executions=3
   3 runs   applications=5   executions=4
  62 runs   applications=0   executions=0
```

The reconciler computes `undetected_duplicate_executions`, and B4's frozen row
is built from it — but `collect.py` does not write it into `b5-runs.jsonl`, so
the session record carries only the applications count. **The field is present
in all 120 per-run `summary.json` files, so this is recoverable without
recollecting anything.**

Correcting it would not reverse the direction — the executions-based B5 counts
are *lower* still (3 where applications are 4) — but H1 as reported is not the
comparison it claims to be.

## 7. What follows

- The `DISAGREES` reading **stands as a description of what was collected** and
  **does not yet support a claim about B4**. Two independent defects sit between
  it and any such claim: the collection constrains its own outcome, and H1's two
  sides are different quantities.
- **No knob was turned and no script was edited in this pass.**
  `analyse_b5_agreement.py`, `collect.py` and the manuscript are untouched;
  `agreement.txt` / `agreement.json` are kept as evidence of what was run.
- The repair — per-run provider seeds via `render_config`, and writing
  `undetected_duplicate_executions` into the session record — is a separate
  prompt. It changes what the collection measures, so it needs its own
  pre-registration and its own attempt against the budget. **Two of three
  attempts remain**, and this session is not spent: it is a complete, honest
  record of a harness that was too deterministic, which is a finding.
