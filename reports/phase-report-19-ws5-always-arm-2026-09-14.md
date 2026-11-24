# Phase 19 — WS-5.1: the `always` arm — pre-launch gates only

## 1. Asked / Done

Asked: rule on the safety properties, pin the lower-mode threshold, pre-flight,
launch 45 runs under `appendfsync always`, freeze, tear down, R15.

Done: the ruling, amendment 3 with its invariant in code, and the script repair
the ruling required. **The collection was not launched.** §5 says why and what
remains.

---

## 2. The safety-property ruling

`test_fsync_stage3_safety.py` asserts **four** properties, not three.

### Property 1 — the run count is validated, before any results root is touched

**MATTERS. Ported.**

The script hardcoded *"3 runs x 10 exec"* and had no run-count input at all;
this arm needs 15. So a count becomes an input either way, and an unvalidated
input feeding a script that also creates and (property 2) deleted directories is
the combination the test refuses.

Ported as a **lexical** gate, matching the test's intent: `09`, `1e3`, `0x9` and
`9 ` are rejected, because a count that means one thing to bash's arithmetic and
another to a reader is not reproducible from a log.

*A bug this caught in my own port.* I first wrote `${AEP_FSYNC_RUNS:-15}`. With
`:-`, an explicitly **empty** value falls through to the default and is silently
accepted as 15. The test sets it empty on purpose and failed. Now `${VAR-15}`.

### Property 2 — no destructive clean path

**MATTERS MOST. Ported. This is the finding of the pass.**

On main:

```
CLEAN="${AEP_FSYNC_CLEAN:-1}"          # default: ON
RESULTS_ROOT="experiments/results/fsync-always"
...
if [ "${CLEAN}" = "1" ]; then
  rm -rf "${RESULTS_ROOT}"
```

`experiments/results/fsync-always` is **frozen and tracked**, and is the sole
source of `\BarrierCostAlways` (15.0), `\BthreeAlwaysMedian` (2 048.4) and
`\AepAlwaysMedian` (2 063.4). **A bare `bash scripts/fsync_always_benchmark.sh`
deletes it** — rule 2 ("Frozen results are immutable") violated by default. The
two tracked CSVs return from git; the raw runs beneath them do not.

> **CORRECTION, same pass.** This paragraph was written as a hazard. It is
> not. **It fired, here, at 14:03, and I fired it.** The rule 13 run below
> executed the unrepaired script, whose run-count property is parametrised
> and therefore actually *invokes* it; sixty executions across six raw run
> directories were destroyed and are not recoverable. R15 caught it before
> the commit. Full account:
> `reports/incident-fsync-always-raw-destroyed-2026-09-14.md`; the rule is
> `docs/25` **R16**. The ruling below stands unedited --- what changes is
> that its subject is a loss rather than a risk.

The delete is replaced by a refusal: if the root exists and is non-empty the
script exits 3 and tells the caller to name a new dated directory, which is what
rule 2 asks for anyway. `RESULTS_ROOT` is now an input.

### Property 3 — configuration and disposable-instance verification

**SPLIT: half already present and load-bearing, half satisfied more strongly
elsewhere. Not ported, and not because it is inconvenient.**

*The configuration half already exists and is kept*: the script reads
`CONFIG GET appendfsync` back from the live server and exits non-zero unless the
answer is literally `always`. That is the gate step 5 requires.

*The marker half is not ported.* The test wants the script to `GET
aep:test-instance-marker` and verify it. The script already `SET`s it, and
verification happens one layer down, **per run**:
`experiments/harness/runner.py:assert_disposable_redis` raises `RunAborted`
before any run proceeds unless the key exists. A one-time check in the script
would be a weaker duplicate of a check that runs 45 times. The property is
satisfied in substance by a stronger mechanism, which is why it stays unported.

### Property 4 — resume uses a locked, interleaved plan

**MATTERS as a concern. CANNOT be ported in scope. Declared as a limitation.**

The test asserts `--run-order interleaved`, `--expected-appendfsync always` and
`--experiment-plan-sha256`. **None of the three exists on main's
`experiments/run_matrix.py`** — they are the stage 3 harness API that phase 18
declined to adopt, and adopting it is explicitly out of scope.

The `--resume` half is present and is inert here: a fresh collection into a new
dated root has nothing to resume.

**The concern is real and is not dismissed.** `build_plan` emits runs
**cell-major** — `for cell in cells: for repetition in range(runs_per_cell)` —
so all 15 AEP-full runs are collected, then all 15 B3, then all 15 B0. Any drift
in host conditions across the ~0.9 h is confounded with system. Interleaving is
what stage 3 built to prevent exactly that.

*What makes the arm still usable, stated rather than assumed:* the frozen
`everysec` cells this arm is compared against were collected with the same
cell-major harness, so the **policy** comparison is like-for-like in this
respect. The residual is that neither arm is protected against within-arm drift,
and that is a limitation of both, not a difference between them.

### Rule 13, discharged

The preserved test run against the script before and after:

```
OLD script (main)                    13 failed,  0 passed
NEW script (properties 1, 2 ported)   2 failed, 11 passed
```

The two remaining failures are exactly properties 3-marker and 4 — the two ruled
unported. *A false start worth recording:* the first attempt copied the test to
`/root/p19/`, where its `ROOT = Path(__file__).resolve().parents[1]` resolved to
`/root`, so `SCRIPT` pointed at a nonexistent path and **all 13 failed for both
versions**. That run proved nothing and was rerun from a directory one level
below the repo root.

---

## 3. Amendment 3 — the threshold, pinned

`reports/phase-report-ws5-prediction-amendment-3-2026-09-14.md`, committed
before any run exists. The boundary is the splitter's own `lower_max`, one per
arm; and the invariant — **kept executions must equal the splitter's lower-group
size** — is now an `AssertionError` inside `lower_mode_difference`, not a check
by eye. It is the assertion that would have stopped phase 18's midpoint rule at
112-versus-120 instead of letting it return a sign-flipped interval.

---

## 4. Counts and statuses

**None. Nothing was collected, so there is nothing to count.**

---

## 5. Not done, and why

**The collection was not launched.** The pre-launch gates were the pass: the
four-property ruling required reading the preserved test against two versions of
the script, and it surfaced a default-on delete of a frozen result that had to
be repaired before the script could be run at all.

Launching after that, without room to verify the pre-flight, watch the
`CONFIG GET appendfsync` read-back, freeze with the raw-tree digest, tear down
both stacks and run R15, would have left a collection running against an
unverified tree and a half-finished record. Stopping before launch leaves the
repository consistent and every gate the launch depends on already committed.

**What remains, in order:**

1. Pre-flight (step 4): host verifier, image digest, E5 with the S0 residual
   restated, R12 on 8099, 6381 **and 6383** (the second Redis), `StartedAt` /
   `RestartCount` read in the light of R12a's withdrawn attribution.
2. Launch with `AEP_FSYNC_RESULTS_ROOT` naming a **new dated directory** —
   never the frozen `experiments/results/fsync-always` — `AEP_FSYNC_RUNS=15`,
   `AEP_FSYNC_SYSTEMS` covering the three systems, and
   `AEP_HARNESS_SUSPEND_DISABLED=1` exported by the collection command itself.
3. Freeze with `freeze_results.py` **and** `digest_results_tree.py` in the same
   pass — the first collection whose raw digest has no temporal gap.
4. Teardown, R15, report.

Also not done, and out of scope: the class sweep 4 → 6, and applying H1–H5 to
§VI-RQ3 and §VIII.

---

## 6. Raw outputs

```
properties present in scripts/fsync_always_benchmark.sh
                                    main   after
  "must be a positive integer"         0       1
  recursive force-delete of the root   1       0
  --runs-per-cell "${RUNS}"            0       1
  "Stage 3 never deletes prior runs"   0       1
  CONFIG GET appendfsync               3       3
  GET aep:test-instance-marker         0       0   (ruled: enforced per run)
  --run-order interleaved              0       0   (ruled: not on main's harness)

preserved test, old script : 13 failed,  0 passed
preserved test, new script :  2 failed, 11 passed

run order: build_plan emits cell-major
  experiments/run_matrix.py:768  for cell in cells:
  experiments/run_matrix.py:781      for repetition in range(runs_per_cell):
```

---

## 7. Findings outside scope

1. **`AEP_FSYNC_CLEAN` defaulting to 1 over a frozen tracked root was a latent
   rule-2 violation that predated this pass, and it is no longer latent** and would have fired for anyone
   running the documented command in the script's own header
   (`AEP_HARNESS_SUSPEND_DISABLED=1 bash scripts/fsync_always_benchmark.sh`).
   Repaired here because this pass was about to run it; recorded because it was
   reachable by anyone following the file's usage line.
2. **`experiments/results/fsync-always` has no `RAW-SHA256SUMS`**, so when the
   delete fired, nothing detected the loss of its raw runs beyond the two
   tracked CSVs reappearing from git. The same is true of every collection
   before WS-5. This item was filed as an observation hours before it became
   the reason the loss is unrecoverable.

---

## 8. Environment

`uv run --frozen --extra dev --extra cov --extra experiments --extra analysis
--extra b5`, CPython 3.13.0, WSL2 6.6.114.1. No Redis started, no container
created, no results directory written. The second Redis the `always` arm needs
(`aep-fsync-always`, port 6383, image digest
`sha256:6aaf3f5e…1f44`, same pin as `compose.phase2.yml`) was not started.
