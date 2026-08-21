# Phase 9 · P9-A — the pre-registered prediction for backlog B2

**This file exists to be checked against data that does not exist yet.**

`docs/24-revision-backlog.md` §B2 says the expectation *"should be recorded
before the run"*. This repository has never done that prospectively. Recording
it makes the result falsifiable rather than a search for confirmation, and the
value of this file is **entirely** in the fact that it precedes the data — so
everything below is written to be verifiable by a reader who does not trust the
author.

---

## 1. The tree state this prediction was made against

```
$ git rev-parse HEAD
71ddf7afa03f933926f186c278cf9b91a8b0a10c

$ git log -1 --format='%h %ad %s' --date=iso
71ddf7a 2026-08-21 19:44:09 +0500 Phase 9 P9-0: key the kill macros by (system, response_class), before any data exists

$ git status --porcelain
?? CLAUDE.md                      # untracked, unrelated, pre-existing
```

**The prediction is made against `71ddf7a`.** That commit fixed the generator's
kill-macro binding and changed no data: all six generated files regenerate
byte-identically from the existing CSVs, verified in its own commit.

## 2. Proof that no AUTH `redis-kill-preack` data exists at this point

```
$ awk -F, 'NR>1{print $1" "$3}' experiments/results/matrix/analysis/redis-kill-ablation.csv | sort -u
redis-kill-preack NO_READBACK

$ grep -c AUTHORITATIVE_READBACK experiments/results/matrix/analysis/redis-kill-ablation.csv
0

$ ls -d experiments/results/b2-* 2>/dev/null
  (no such directory)

$ find experiments/results -type d -name '*payments*' | grep -i 'redis\|kill'
  (no output)
```

**Zero rows of `AUTHORITATIVE_READBACK` × `redis-kill-preack` exist anywhere in
the tree.** The results root this phase will create, `experiments/results/b2-*`,
does not exist. A reader can re-run all four commands at this commit and get the
same output.

---

## 3. The positive control — **read first, before the AUTH result**

The audit's finding **A3** attributes part of the existing effect size to this
host's `docker kill` latency. That latency is not fixed by configuration and may
have drifted since the original cells were collected. **If it has, AEP-full's
applied count moves for a reason that is not capability class** — which is
exactly the confound that would fake a contradiction.

So the run re-collects the **`NO_READBACK`** cells alongside the AUTH cells, in
the same session, on the same host. It is a measurement with a known expected
value, and it is read **first**.

**The ordering is deliberate and is recorded here so it cannot be rearranged
after the fact.** Reading the control second invites motivated interpretation:
a surprising AUTH result would arrive first and the control would then be read
looking for a reason to keep or discard it.

| Control quantity | Expected | PASS band (Wilson 95%, n=30) | FAIL |
|---|---|---|---|
| AEP-full `executions_with_an_applied_effect` | **10/30** | **5 ≤ k ≤ 16** | k ≤ 4 or k ≥ 17 |
| B3 `executions_with_an_applied_effect` | **28/30** | **23 ≤ k ≤ 30** | k ≤ 22 |
| canary survived, both arms | **30/30** each | exactly 30/30 | anything else |

**If the control FAILS: the host has drifted, and no cross-class claim may be
made from this session.** The output is then "this session cannot compare
classes", the original cell stands unreplicated, and the AUTH numbers are
reported as uninterpretable rather than as a finding. **The original
`NO_READBACK` cells are not overwritten** — the re-collection lands under a
separate results root.

---

## 4. The AUTH prediction — thresholds, not prose

**Mechanism under test.** Whether an effect reached the provider is a fact about
what was put on the wire. A read-back capability is exercised *afterwards*, by
recovery. It can change what the system is able to **say**; it cannot change what
was **done**.

**Cell:** `redis-kill-preack` × `after_intent_before_barrier` × `payments`
(`AUTHORITATIVE_READBACK`), n=30 per arm, 1 execution per run, 1 worker.

### 4.1 The applied-effect column — predicted UNCHANGED

| Quantity | Predicted | **CONFIRMS** | **CONTRADICTS** |
|---|---|---|---|
| AEP-full applied | **10/30** | **5 ≤ k ≤ 16** | **k ≤ 4 or k ≥ 17** |
| B3 applied | **28/30** | **23 ≤ k ≤ 30** | **k ≤ 22** |
| difference (B3 − AEP) | **18** | **8 ≤ d ≤ 24** | d ≤ 7 |
| Fisher two-tailed, applied | **1.9×10⁻⁶** | **p < 0.05** | p ≥ 0.05 |

Bands are Wilson 95% two-sided on the observed `NO_READBACK` counts, converted to
integer counts at n=30; the difference band is Newcombe on the two Wilson
intervals. Derivation is arithmetic from 10/30 and 28/30 and is reproducible:
AEP CI [0.1923, 0.5122] → [5, 16]; B3 CI [0.7868, 0.9815] → [23, 30]; difference
[0.2746, 0.7892] → [8, 24]. For reference, the weakest AEP count still
significant at 0.05 against B3=28/30 is **k = 21**; k = 22 gives p = 0.0797.

### 4.2 The declared-ambiguity column — predicted to MOVE

| Quantity | Now (`NO_READBACK`) | Predicted (AUTH) | **CONFIRMS** |
|---|---|---|---|
| AEP-full `declared_ambiguous` | 30/30 | **≈ 0/30** | **k ≤ 6** |
| B3 `declared_ambiguous` | 30/30 | **≈ 0/30** | **k ≤ 6** |

Under `AUTHORITATIVE_READBACK` a read-back **proves absence**, so recovery
refutes rather than declaring. `\AepAmbAuth{}` and `\BthreeAmbAuth{}` are both
`0.0000` in the crashed regime. See §5 — this is the prediction I am least
confident in.

### 4.3 HALT conditions — stop the phase, report, collect nothing further

| Quantity | HALT if |
|---|---|
| `undetected_duplicates`, either arm, either class | **> 0** |
| `lost_effects`, either arm, either class | **> 0** |
| `executions` ≠ `runs × 1` in any cell | **any mismatch** (the resume double-count signature) |
| a `(system, response_class)` pair appearing twice in the analysis | **any** |

### 4.4 The unfalsifiability check

**If AUTH's declared ambiguity does NOT drop below 30/30, the read-back is not
being exercised and the cell is measuring something other than what it claims.**
In that case the applied-effect comparison is uninterpretable regardless of what
it shows, and the correct output is a defect report about the cell, not a finding
about the mechanism. This check is stated now precisely because it is the one
that would otherwise be easy to skip when the applied column looks obliging.

---

## 5. What I expect to be uncertain about

A prediction confident about everything is either lucky or not honest. These are
the quantities I would **not** bet on, named before the data arrives.

1. **The declared-ambiguity value under AUTH — my weakest prediction, and it is
   load-bearing.** I predict ≈0 from `\AepAmbAuth{}` = 0.0000, but that macro
   comes from the **crashed** regime, which has worker `SIGKILL`s and a running
   recovery service. `redis-kill-preack` is a different shape: no worker crash,
   one worker, one execution, and Redis itself is killed and restarted
   mid-execution. **Whether recovery performs the read-back the same way after a
   Redis restart is not something I can assert from the data I have.** I would
   bet on the *direction* (below 30/30) and not on the value. This is also
   exactly the quantity §4.4 depends on, so if I am wrong here the experiment is
   less informative than planned — and I would rather have said so first.

2. **`confirmed_not_applied`.** I expect the complement of applied to land here
   (~20/30 AEP, ~2/30 B3), but it could instead remain unresolved if the
   reconciliation budget expires or the Redis restart disrupts the recovery pass.
   **Low confidence; no threshold set**, and I will not treat whatever appears as
   confirmatory of anything.

3. **Host-drift magnitude.** Unpredictable by construction — it is why §3 exists.
   I am not predicting the control will pass; I am predicting that reading it
   first is what makes the AUTH number interpretable either way.

4. **The exact AEP applied count.** The band [5, 16] is wide because n=30 is
   small. A point-agreement at exactly 10/30 would be luck, not confirmation, and
   I will not report it as though it were striking.

### Two confounds I checked for and did *not* find

Recorded because a null check is evidence too, and because both would have
undermined the comparison had they been present.

- **Per-endpoint tier difference.** `run_matrix.py:414` returns a different tier
  for `payments`, which would have meant the two endpoints ran under different
  conditions. It is unreachable here: `:408` returns tier 2 for **any** regime
  with `redis_kill_point is not None`, before that branch.
- **Per-endpoint provider behaviour.** In `experiments/configs/matrix.yaml` the
  three endpoints differ **only** in `response_class`; `identity_fields` are
  identical and the delay, timeout, error and duplicate probabilities are set
  once for the provider, not per endpoint. **The endpoints are matched on
  everything except the capability class**, which is what makes this a clean
  comparison rather than a confounded one.

---

## 6. Scope of what this phase can claim afterwards

**`POSITIVE_ONLY_READBACK` is not collected this phase.**
`experiments/run_matrix.py:249` pins the regime's endpoints to
`("payments", "ledger_postings")`, and `:441-444` intersects the CLI
`--endpoint` with that tuple, so `notifications` is unreachable without editing
`:249`. That is a collection-side code change and it was ruled out of this phase.

**So the strongest claim available after a CONFIRMS is: prevention measured on
two of three capability classes, not three.** Any text saying otherwise is
wrong, and §B2's own claim that *"the cells that would settle it are in the
plan"* is false for `POSITIVE_ONLY` and is corrected separately.

---

## 6A. AMENDMENT — the stopping rule *(added before collection, still no data)*

**P9-A as first written had no stopping rule.** n=30 was stated and nothing said
what happens when a run fails, a container dies, or a cell comes back short.
That gap is the one thing that would quietly destroy everything this
pre-registration is for: **a session in which runs are added until the numbers
settle, or a failed run is silently replaced, is no longer a pre-registered
experiment — and no gate in this repository could detect it, because the
resulting data would be internally consistent.**

This amendment is committed **before** any collection, so the stopping rule
precedes the data exactly as the prediction does.

### 6A.1 n is fixed

**n = 30 runs per arm per capability class. It is not raised, not lowered, and
not topped up after any result is seen.** Four cells: {AEP-full, B3} ×
{`NO_READBACK` control, `AUTHORITATIVE_READBACK`}. 120 runs attempted in total.
`runs_per_cell=30` and `executions_per_run=1` are regime constants
(`run_matrix.py:239-240`) and are **not** overridden on the command line.

**If a different n were wanted, it had to be said here. It is not wanted.**

### 6A.2 What may be replaced, and what may not

A replacement run is permitted **only** for a failure whose cause is
**infrastructural and checkable from a field independent of the run's outcome**.
The exhaustive list, fixed now:

| # | Qualifying cause | How it is checked, independent of the result |
|---|---|---|
| 1 | Redis container fails to start, or fails to come back after the kill | container `uptime` / `run_id` absent or unchanged |
| 2 | Mock provider unreachable, port in use, or process died | provider health check / connection error before dispatch |
| 3 | Docker daemon unavailable | command-level failure, no run artifacts |
| 4 | Disk full, or results root unwritable | OS error, no `summary.json` |
| 5 | Harness safety guard fires — test-instance marker absent, or a host-level fault injector detected beside the runner | the guard's own refusal message, exit before collection |
| 6 | **E5 timing gate**: host suspended mid-run, wall-vs-monotonic divergence beyond tolerance | the per-run monotonic check |
| 7 | **VOID: the injected kill did not land** — the fault under study never occurred | container `uptime` at zero / `run_id` change, a field that says nothing about what the system did |

**Cause 7 is the only outcome-adjacent one and it is deliberately narrow.** It
follows the void rule the paper already uses for the durability probe and the
one disagreeing B4b run: *a trial whose measurement precondition failed says
nothing about the system in either direction.* It is checkable from whether Redis
actually died, which is independent of what the system did about it.

**Never replaceable:** a run that **completed and produced a number**. Not
because it is surprising, not because it is off-prediction, not because the cell
aggregate is unwelcome. **There is no cause on this list that a result can
satisfy.**

### 6A.3 Replacement budget — a hard cap

**At most 12 replacement runs across the entire phase** (10% of 120). If the cap
is reached, **collection stops and the phase reports short cells with their
actual n**, rather than continuing. A cell that cannot reach n=30 within the cap
is reported at the n it reached, and its thresholds in §4 are recomputed at that
n and marked as recomputed.

This exists so "replace the voids until the cell fills" cannot become an
unbounded loop that quietly selects a sample.

### 6A.4 The denominator is attempted runs

**Every run attempted is reported, including every discarded one, with its
cause.** The report states:

```
attempted / completed / discarded (by cause) / analysed
```

**The report's denominator is attempted runs, not surviving runs.** A reader must
be able to see the discard rate and judge it, which is impossible if only
survivors are counted. If discards are concentrated in one arm or one class,
**that asymmetry is itself a finding** and is reported as one — an
infrastructural failure that correlates with the system under test is not
infrastructural.

### 6A.5 Order of collection, fixed

1. **`NO_READBACK` control — both arms — collected FIRST.**
2. Its verdict against §3's band is **read and written down** before AUTH numbers
   are looked at.
3. **`AUTHORITATIVE_READBACK` — both arms — collected second.**

**Nothing enforces this but the author.** It is recorded here so that a
deviation is visible as a deviation rather than invisible as a choice.

---

## 7. Signed state

| | |
|---|---|
| Prediction made against | `71ddf7afa03f933926f186c278cf9b91a8b0a10c` |
| AUTH `redis-kill-preack` rows in tree | **0** |
| `experiments/results/b2-*` | **does not exist** |
| Collection performed by this session | **none** |

*Nothing in this file may be revised after data arrives. If a threshold here
turns out to be badly chosen, that is recorded in the result report as a defect
in the prediction — not fixed here.*
