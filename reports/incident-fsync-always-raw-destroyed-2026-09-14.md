# Incident — the `fsync-always` raw run tree was destroyed, by me, during phase 19

**Date:** 2026-09-14, 14:03 local (WSL clock `started_at` 403740.9).
**Severity:** irrecoverable loss of raw data underneath three published macros.
**Cause:** my own rule-13 demonstration executed the unrepaired script.
**Paper impact:** none to the numbers. The provenance chain under them is gone.

---

## 1. What was lost

Six raw run directories, 60 executions:

```
aep_full-none-payments-e5e5c7dc-r0, -r1, -r2
b3_intent_no_barrier-none-payments-85b7630d-r0, -r1, -r2
```

plus that root's `matrix-plan.json`, `matrix-plan.txt` and `matrix-progress.jsonl`.

These are the raw runs behind `experiments/results/fsync-always/analysis/`, which
is the sole source of `\BarrierCostAlways` (15.0), `\AepAlwaysMedian` (2 063.4)
and `\BthreeAlwaysMedian` (2 048.4).

**What survives.** The two derived CSVs are *tracked* — `.gitignore:155-159`
un-ignores exactly them — and were restored with `git checkout --`. The
published numbers are intact and every gate is green again (33/33 in
`check_paper_numbers.py`, 42/42 in `tests/test_power_analysis.py`, citations OK).

**What does not.** The raw runs were gitignored (`.gitignore:154`), were never
committed, and existed in no archive, no tarball, no WSL copy and no manifest —
all five searched, all five empty. The cell's derived CSVs can no longer be
**recomputed from raw**. For `fsync-always`, `make reproduce-figures` now
reproduces from a CSV rather than from data.

---

## 2. What happened

`scripts/fsync_always_benchmark.sh` on main had:

```
CLEAN="${AEP_FSYNC_CLEAN:-1}"                       # default ON
RESULTS_ROOT="experiments/results/fsync-always"     # not an input
...
if [ "${CLEAN}" = "1" ]; then rm -rf "${RESULTS_ROOT}"
```

Phase 19 step 1 required ruling on the preserved stage-3 safety test, and rule 13
requires running that test against the **old** code first to watch it fail. One
of the four properties — the run-count gate — is not a source inspection. It is
**parametrised and it executes the script**, once per invalid value.

On the repaired script that is harmless: the lexical gate exits 2 before
anything is touched, and `AEP_FSYNC_RESULTS_ROOT` points the run at a sacrificial
directory anyway. On the **old** script neither existed. Each invocation fell
straight past the (absent) validation into `rm -rf` on the hardcoded frozen root,
and then into a real collection.

The traceback preserved in the quarantined `matrix-progress.jsonl` shows the
invocations racing each other:

```
FileNotFoundError: ... 'experiments/results/fsync-always/
                        aep_full-none-payments-e5e5c7dc-r0/run-config.json'
  runner.py:431  config_path.write_text(...)
```

The harness created its run directory and then could not write into it: another
invocation's `rm -rf` had removed it underneath the first. So the deletion is not
an inference from mtimes — one invocation's delete is recorded in another's
stack trace.

What was left at 14:03 was a single **failed, partial** AEP-full run sitting
inside a directory the paper cites, with freshly regenerated `matrix-plan.json`
and `matrix-progress.jsonl` around it. That is worse than an empty directory: it
is contamination shaped like data, and `experiments/analyze` pointed at that root
would have silently produced different published numbers from one broken run.

---

## 3. Disposition

* The 14:03 artefacts are **quarantined, not deleted**, at
  `reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14/`. They are the
  evidence for §2 and they are committed as such.
* `experiments/results/fsync-always/` now contains exactly its tracked content
  and nothing else — `git status` on that path is empty.
* `RAW-RUNS-DESTROYED.md` is placed in that root and un-ignored, so the next
  reader of the directory learns the raw tree is gone from the directory itself
  rather than from this report.

---

## 4. How narrowly the corruption was caught, and by what

Not by judgement. By **R15**: the phase-19 pass ran the gate covering what it
changed before committing, and `check_paper_numbers.py` failed with

```
FileNotFoundError: .../fsync-always/analysis/latency-and-throughput.csv
```

Had R15 been skipped — the changes were two scripts, none of them obviously
touching results — the commit would have gone out with the frozen root holding
one failed run, the two CSVs deleted, and nothing in the diff to show it, because
the raw runs are gitignored and the CSV deletions would have been staged along
with everything else by a `git add -A`.

**The first thing I said about this was wrong and is corrected here.** On seeing
the missing CSVs I said the raw runs were intact, because `grep` still found
`matrix-plan.json` and a run directory under that path. Both were files the
*failed 14:03 collection* had just written. A directory listing that is
non-empty is not a directory that survived.

---

## 5. Why this is not merely bad luck

Three properties combined, each individually defensible:

1. **The destructive default.** `CLEAN` defaulting to `1` over a hardcoded frozen
   root. Documented in the script's own usage header as a bare invocation.
2. **The gitignore asymmetry.** Un-ignoring the two derived CSVs and ignoring the
   raw runs makes the recoverable part of the tree invisible in `git status` and
   the unrecoverable part invisible *everywhere*. `git status` showed two deleted
   files; it could not show the sixty that mattered more.
3. **No manifest.** Phase 19 §7 had already recorded that this root has no
   `RAW-SHA256SUMS`. That finding was written hours before the loss and was, at
   that moment, describing the precise reason the loss would be undetectable.
   It was filed as an observation rather than acted on.

The third is the one I would change first. `digest_results_tree.py` exists, is
tested, and was built in phase 18 for exactly this. It had not been run over the
pre-WS-5 collections because they were "already frozen" — and frozen is precisely
the property that makes an unmanifested tree unrecoverable rather than merely
unverified.

---

## 6. Actions

**Done in this pass:** the script repaired (the repair is what phase 19's ruling
was about); the root restored and quarantined; `RAW-RUNS-DESTROYED.md` placed;
**R16** added to `docs/25`; phase 19's report and prompt corrected where they
described this defect as hypothetical.

**Not done, and recommended:** run `digest_results_tree.py` over every remaining
pre-WS-5 collection root. It cannot recover what is gone and it cannot make a
manifest retroactive — the tool states that limitation inside every file it
writes — but it is the difference between the next loss being detected and the
next loss being discovered by a `FileNotFoundError` months later.
