# Phase 40 — the fault schedule is not symmetric across the arms

**STOP. Stage 100 was not run.**

The pre-flight symmetry check required before stage 100 found that
`AEP_FULL` and `B0_NAIVE_RETRY` **do not face the same provider faults**. The
fault stream is seeded from a key whose first component is the system name, so
the two arms draw different faults for the same repetition.

That is an instrument fault under amendment 6 §8 — a **leak of arm identity**,
here into the conditions rather than into the prompt. No live call was made.
Cumulative live spend is unchanged at **USD 0.00359020**.

**No design change is proposed in this report.** It establishes the fact and
stops.

---

## 1. Why a 503 was injected at all under this regime

The regime line in every collection log reads:

> `(session-3)  p(crash)=1.0  runs=2  shape=1 x 3`
> `every execution crashed, no infrastructure fault`

**"No infrastructure fault" means no Redis kill and no partition.** It does not
mean the provider is quiet. `mock-api.yaml`, identical in both arms:

```yaml
defaults:
  faults:
    delay: {distribution: constant, seconds: 2.0}
    duplicate_response_probability: 0.0
    server_error_probability: 0.05
    timeout_probability: 0.15
```

Provider faults are **always on**: 5 % server error, 15 % timeout, per request.
So a 503 under this regime is expected, not anomalous. The regime description
is accurate about infrastructure and silent about the provider, and reading it
as "nothing else can fail" was my error at stage 30.

## 2. The schedules are NOT identical across arms

### 2.1 The seeds, from the archives

Read from each run's `run-config.json` and `mock-api.yaml` (the two agree in
every run):

| collection | `AEP_FULL` seed | `B0_NAIVE_RETRY` seed | identical? |
|---|---|---|---|
| stage 10 interactive | 1 174 872 249 | 4 811 467 | **no** |
| stage 30 | 1 174 872 249 | 4 811 467 | **no** |
| stub rpc2, rep 0 | 1 174 872 249 | 4 811 467 | **no** |
| stub rpc2, rep 1 | 1 244 684 929 | 321 273 130 | **no** |
| stub a6 | 1 174 872 249 | 4 811 467 | **no** |

The same two values recur across collections because the seed is derived, not
drawn — which is how the archives can be compared at all, and is also how the
asymmetry is reproducible rather than incidental.

### 2.2 What the seed is derived from

`experiments/run_matrix.py:653-663`:

```python
def cell_seed(matrix_seed: int, cell: Cell, repetition: int) -> int:
    material = f"{matrix_seed}|{MATRIX_VERSION}|{cell.key}|{repetition}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
```

and `cell.key` (`:475-483`) begins with the system:

```python
parts = [
    self.system.value,        # <- the arm
    self.crash_point,
    self.endpoint,
    self.readback_keying.value,
]
```

Recomputed against the archives, and it reproduces them exactly:

```
MATRIX_VERSION = aep.matrix/1
  AEP_FULL       rep0  key='AEP_FULL|mid_dispatch|notifications|CALLER_REFERENCE'
                       seed=1174872249      <- matches every AEP archive
  AEP_FULL       rep1                       seed=1244684929
  B0_NAIVE_RETRY rep0  key='B0_NAIVE_RETRY|mid_dispatch|notifications|CALLER_REFERENCE'
                       seed=4811467         <- matches every B0 archive
  B0_NAIVE_RETRY rep1                       seed=321273130

the same key without the system name:  seed=68413130
```

The last line is the control: strip the arm out of the key and the seed changes,
which is what identifies the system name as the term that makes the two differ.

**So the answer to "is the schedule seeded by anything arm-specific" is yes,
and it is the arm name itself.**

### 2.3 What that produced, per collection

From each run's `ground_truth.run.jsonl` — the provider's own record of what it
did:

| collection | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| stage 10 | `mutation_applied` | **`mutation_refused` 503**, then `mutation_applied` |
| **stage 30** | `mutation_applied` | **`mutation_refused` 503** |
| stub rpc2 rep 0 | (none recorded) | **503**, applied, **503**, applied |
| stub rpc2 rep 1 | (none recorded) | applied ×3 |
| stub a6 | (none recorded) | **503**, applied, **503**, applied |

**In every collection, every injected 503 landed on `B0_NAIVE_RETRY` and none
landed on `AEP_FULL`.** With 5 % per request and a handful of requests that is
not proof of bias on its own — but it is not chance either, because the streams
are deterministic: B0's seed produces those 503s every time it is run, and
AEP's seed does not.

### 2.4 The seed reaches further than the faults

The same arm-specific `seed` is also what `plan_workload` derives the workload
from (`experiments/harness/workload.py:149-170`): the execution ids, the
targets, the amounts and the crash selection all come from
`(config.run_id, config.seed)`, and `run_id` also carries the system slug.

That is why the two arms have never handled the same payments — stage 30's AEP
run worked 167 608 / 896 603 / 41 282 and its B0 run 775 463 / 610 310 /
473 905. At `p(crash)=1.0` the crash-selection term makes no difference (every
execution is selected on both arms), but the amounts, the targets and the
faults all differ.

## 3. Why this is an instrument fault under amendment 6 §8

Amendment 6 §8 reserves further structural amendments for **a crash, a leak, or
a malformed path**, and defines a leak as *"the agent can see the oracle's
verdict, or can tell which arm it is in."*

This is the second kind, arrived at from the other side. The agent cannot read
the seed — nothing in the prompt carries it, and §2.5 of the stage-30 report
confirms no excluded field appeared. But **arm identity determines the
conditions the agent is tested under**, which defeats the same control for the
same reason:

> Amendment 6 §6: *"An agent that can tell which arm it is in is a second
> uncontrolled variable, and the comparison stops meaning anything."*

The experiment runs **one fixed caller against two systems** and attributes the
difference in outcomes to the systems. If the two systems are also handed
different provider faults on different payments, a difference in outcome is not
attributable to the protocol. At the pre-registered *n* — 10 runs per system,
and 1 to 2 so far — there is nothing to average the fault stream out.

**This is not a defect the matrix has.** For the main matrix the per-cell seed
is correct and deliberate: each cell is its own condition, 30 repetitions deep,
and independent seeds are what make the cells independent. It becomes a
validity problem only in phase 40's **paired, small-*n*, binary-reachability**
framing, which compares two cells directly rather than comparing distributions.
The mechanism was right for the job it was built for and is wrong for this one.

## 4. What it does to the stage-30 record

**The exploratory addendum's §A.3 is withdrawn**, and
`reports/phase-report-40-stage-30-2026-09-21.md` now carries the correction at
the head of the addendum.

§A.3 read the two arms' different outcomes as *"the same agent decision was
correct on one arm and abandoned a payment on the other"*. It was not the same
situation. B0's payment was refused by an injected 503 that AEP's provider
never issued, so the reason B0's effect did not apply is the fault stream, not
the protocol and not the agent's choice. The facts in §A.1 stand — the payment
was not applied and was not re-sent — but the comparison built on them does not.

**Nothing in stage 30's criteria changes.** C1–C3, C4′, and amendment 6 §9's
clauses 2 and 3 are all properties of the instrument, not of the fault stream,
and each was verified from the run directories. The stage-30 verdict stands as
PARTIAL for the reason amendment 7 records.

## 5. What was checked, and what was not

| | |
|---|---|
| collections examined | stage 10 interactive, stage 30, stub rpc2 (4 runs), stub a6 |
| per run | `run-config.json` seed, `mock-api.yaml` seed, `config_digest`, `ground_truth.run.jsonl` |
| derivation | `cell_seed` recomputed and matched against every archive |
| control | the same key with the system name removed yields a different seed |

**Not examined, and deliberately:** whether any fix is possible, what it would
cost, or which of the several possible forms it should take. Amendment 6 §8
requires a further amendment to name which fault justifies it; naming the fault
is what this report does. **Choosing the remedy is the author's, and proposing
one here would be the same shortcut the report is about.**

## 6. Verification

| | |
|---|---|
| live calls | **none**; cumulative USD 0.00359020 |
| stage 100 | **not run** |
| full suite | 2 456 passed, 34 skipped |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
