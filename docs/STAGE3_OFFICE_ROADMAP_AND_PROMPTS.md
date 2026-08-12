# AEP Stage 3 — Office Machine Roadmap and Codex Prompts

Date prepared: 2026-08-12
Scientific baseline: `c2fffa61961228de8466b12939ef1c578506e7ba` (`Close Stage 2 verification and typesetting`)

## 1. Current truth

- Stage 2 is complete and pushed at `c2fffa6`.
- Stage 3 scientific collection has not started: `0` new runs and `0` new executions.
- The original raw evidence behind the committed aggregates was not recovered:
  - 432 runs
  - 3,780 executions
  - 126 cells
  - historical `results/voided/` evidence
- The home machine is not suitable for collection: critically low physical disk, unhealthy Docker overlay storage, NTFS/v9fs workspace, incomplete locked Linux environment, and unstable load.
- There is a useful but unverified Stage 3 preparation change-set: 14 modified tracked files plus six untracked files.
- The preparation change-set has good focused evidence (`109 passed`) and an earlier complete run reached `1,736 passed, 34 skipped`, but the latest exact-tree run ended with three failures and three errors caused by disk exhaustion. Therefore it is WIP, not merge-ready.
- Frozen files already created:
  - `reports/stage3-pre-run-protocol-2026-08-12.md`
    - SHA-256: `8b0c3f009f8b266c1a885e989ec325d6afd1da40b8c17606cd659f25522ce864`
  - `reports/stage3-experiment-plan-2026-08-12.json`
    - SHA-256: `b5e4a39fa83d30065b060960a6862eaf4fdc3d897df368aff7104cf8afdd7f9a`
  - Matrix seed: `20260812`

## 2. What should be pushed tonight

Yes: preserve the useful current work in a dedicated remote WIP branch so it is available on the office machine.

Do **not** merge it into `main` and do **not** represent it as tested Stage 3 closure.

Recommended branch:

`stage3-prep-office-20260812`

### Commit and push these files as a WIP checkpoint

1. `experiments/analyze.py`
2. `experiments/harness/config.py`
3. `experiments/harness/orchestrate.py`
4. `experiments/harness/runner.py`
5. `experiments/harness/tests/test_stale_shards.py`
6. `experiments/run_matrix.py`
7. `experiments/statistics.py`
8. `experiments/tests/test_per_cell_regimes.py`
9. `experiments/tests/test_statistics.py`
10. `scripts/fsync_always_benchmark.sh`
11. `scripts/paper_tables.py`
12. `experiments/tests/test_stage3_analysis_provenance.py`
13. `experiments/tests/test_stage3_collection_safety.py`
14. `tests/test_fsync_stage3_safety.py`
15. `reports/stage3-experiment-plan-2026-08-12.json`
16. `reports/stage3-pre-run-protocol-2026-08-12.md`
17. `reports/stage3-external-submission-inputs-2026-08-12.md`
18. `docs/25-stage3-office-roadmap-and-prompts.md` (this file after placing it in the repository)

### Do not include these generated files in the WIP checkpoint

- `paper/generated/numbers.tex`
- `paper/main.pdf`
- `paper/main-anon.pdf`

Those three changed only because the source census moved from 87 files / 22,218 lines to 89 files / 23,546 lines. No experimental result changed. They must be regenerated only after the preparation code passes the complete suite on the office machine.

### Never put these in Git

- raw run directories
- `results/voided/` evidence archives
- Docker volumes or Redis AOF files
- clean-room artifact archives
- secrets, credentials, tokens, local machine paths, or private configuration

## 3. Expected core workload on the office machine

| Work | Runs | Executions | Cells | Repository-derived runtime |
|---|---:|---:|---:|---:|
| New replication of the original matrix, if raw evidence remains absent | 432 | 3,780 | 126 | about 11.57 h |
| Mandatory B2 | 120 | 120 | 4 | included below |
| Mandatory B3 | 36 | 360 | 4 | included below |
| Mandatory B2 + B3 | 156 | 480 | 8 | about 1.63 h |
| Core replication + B2 + B3 | 588 | 4,260 | 134 | about 13.20 h |

Estimated core raw storage is about 942.3 MiB, but this is an extrapolation, not an observed final archive size. Require at least 15 GiB genuinely free physical capacity; 50 GiB or more is preferable for Docker, builds, renders, duplicate verification copies, and the clean-room package.

The 13.20-hour figure excludes environment setup, tests, analysis, PDF inspection, and clean-room reproduction. Plan for at least two uninterrupted work periods.

## 4. Execution order and stop/go gates

1. Preserve and push the current WIP branch from the home machine.
2. Fresh-clone the WIP branch on the office machine into a Linux-native filesystem.
3. Run read-only baseline and host preflight. Stop if any safety gate fails.
4. Audit and repair the preparation code. Run focused and complete tests with zero failures.
5. Make a formal evidence decision:
   - if original raw evidence is found, verify it byte-for-byte; or
   - if it remains absent, declare a new versioned replication dataset. Never call it the historical raw dataset.
6. Append a dated amendment and generate a new immutable machine plan for the actual office host. Do not edit the frozen 2026-08-12 protocol or plan.
7. Run a small non-confirmatory pilot in a separate pilot/voided root. Its outputs do not enter scientific denominators.
8. If raw evidence is absent, recollect the original 432-run matrix as the new replication dataset.
9. Run mandatory B2 (120 runs / 120 executions).
10. Run mandatory B3 (36 runs / 360 executions).
11. Freeze and verify all raw/voided evidence before analysis.
12. Analyze via the pipeline, revise claims honestly, rebuild both PDFs, and run all gates.
13. Build and clean-room verify the DOI-ready archive outside Git.
14. Perform an independent rereview.
15. Only after a passing rereview, commit and push the validated implementation/results documentation to the feature branch. Merge/release/deposit/submission remain separate decisions.

`redis-kill-inflight`, `p30`, and `ORACLE_FINGERPRINT` are optional secondary work. Do not run them until B2/B3 and the core replication are frozen and analyzed.

B1 block-write-loss is separately privileged. It is not part of the normal office run and must not be attempted without explicit user approval on a disposable native-Linux block device.

---

# Sequential Codex prompts

Use the prompts one at a time. Do not paste all of them into one Codex turn. Review each phase report before sending the next prompt.

## Prompt 0 — Tonight: preserve the useful WIP work on Git

```text
Continue in the current Research-paper-AEP repository on the home machine.

This task is only a non-destructive Git preservation checkpoint. Do not run experiments, rebuild PDFs, delete files, clean caches, reset Docker, stash, restore, discard, merge to main, tag, release, or submit anything.

Expected baseline:
- branch: main
- HEAD and origin/main: c2fffa61961228de8466b12939ef1c578506e7ba
- exactly 14 modified tracked files and six untracked files from the Stage 3 preparation work
- the roadmap has been placed at docs/25-stage3-office-roadmap-and-prompts.md

First verify the exact status and stop if it materially differs.

Verify these frozen hashes before staging:
- reports/stage3-pre-run-protocol-2026-08-12.md
  8b0c3f009f8b266c1a885e989ec325d6afd1da40b8c17606cd659f25522ce864
- reports/stage3-experiment-plan-2026-08-12.json
  b5e4a39fa83d30065b060960a6862eaf4fdc3d897df368aff7104cf8afdd7f9a

Create and switch to a new branch named stage3-prep-office-20260812. If that local or remote branch already exists, stop and report it rather than overwriting it.

Stage only these files:
- experiments/analyze.py
- experiments/harness/config.py
- experiments/harness/orchestrate.py
- experiments/harness/runner.py
- experiments/harness/tests/test_stale_shards.py
- experiments/run_matrix.py
- experiments/statistics.py
- experiments/tests/test_per_cell_regimes.py
- experiments/tests/test_statistics.py
- scripts/fsync_always_benchmark.sh
- scripts/paper_tables.py
- experiments/tests/test_stage3_analysis_provenance.py
- experiments/tests/test_stage3_collection_safety.py
- tests/test_fsync_stage3_safety.py
- reports/stage3-experiment-plan-2026-08-12.json
- reports/stage3-pre-run-protocol-2026-08-12.md
- reports/stage3-external-submission-inputs-2026-08-12.md
- docs/25-stage3-office-roadmap-and-prompts.md

Explicitly do not stage:
- paper/generated/numbers.tex
- paper/main.pdf
- paper/main-anon.pdf

Before committing:
- show the staged name/status list;
- verify the staged set is exactly the allowlist above;
- run git diff --cached --check;
- scan the staged content for real credentials, tokens, private paths, raw evidence, and accidental binaries;
- confirm the two frozen-file hashes still match;
- confirm no raw result tree or archive is staged.

Do not rerun the complete suite because the home disk is unsafe. Record that this is an unverified WIP preservation commit, not a passing scientific or merge gate.

If every check passes, commit with:
WIP: preserve Stage 3 preparation for office validation

Push only the new branch to origin and set its upstream. Do not push or modify main.

After pushing, verify the remote branch SHA and show git status. The only remaining local changes should be the three excluded generated files. If anything else remains unexpectedly, report it without modifying it.

Return the branch name, commit SHA, remote SHA, exact committed file list, frozen hashes, staged secret-scan result, and remaining worktree status.
```

## Prompt 1 — Office: fresh clone and host preflight

```text
Work on the heavy-duty office machine. This is Stage 3 office preflight only. Do not edit source, run scientific experiments, restart/kill Redis, delete data, or rebuild manuscript outputs.

Fresh-clone the Research-paper-AEP repository into a Linux-native filesystem, not an NTFS/v9fs mounted path. Fetch origin and check out origin/stage3-prep-office-20260812 as a new local branch with the same name.

Verify:
- c2fffa61961228de8466b12939ef1c578506e7ba is an ancestor;
- the WIP preservation commit contains only the intended preparation/report/roadmap files;
- the working tree is clean;
- the frozen protocol and plan hashes match their recorded values;
- the three generated paper files remain at their Stage 2 baseline versions.

Perform a read-only preflight and record:
- native OS, kernel, CPU, RAM, filesystem and mount type;
- physical free space on the filesystem that will hold the repository, Docker data, raw evidence, voided evidence, and clean-room copy;
- Python and uv versions plus uv.lock SHA-256;
- whether uv sync --frozen can complete;
- Docker Engine/Compose versions, storage driver and docker system df health;
- Redis image digest, Redis version, loopback exposure, appendonly/appendfsync settings, DB number, health and restart count;
- whether a dedicated disposable AEP Redis instance can be created without touching unrelated services;
- LaTeX, BibTeX, Poppler and font-inspection tools;
- clock synchronization, sleep/suspend state and current CPU/load stability.

Hard GO requirements:
- at least 15 GiB real physical free space; prefer 50 GiB or more;
- repository/results on Linux-native ext4 or another native Linux filesystem;
- healthy Docker storage with no missing snapshot/overlay error;
- locked environment synchronizes;
- stable, low competing load;
- a uniquely named disposable Redis instance isolated from all unrelated Redis/database projects;
- no production or shared data involved.

If the office host is Windows/WSL2, clearly distinguish the WSL ext4 filesystem from /mnt/c or another Windows mount. B2/B3 may proceed only if repository/results are inside WSL ext4, physical backing space is sufficient, Docker/Redis namespaces are verified, and timing stability is defensible. B1 remains forbidden in WSL/Docker Desktop.

Return READY or BLOCKED with exact evidence for every gate. Stop after the report.
```

## Prompt 2 — Repair and validate the Stage 3 preparation code

```text
Continue only if Prompt 1 returned READY. This phase may edit source/tests/reports, but must not run scientific experiments or regenerate manuscript numbers/PDFs.

Audit the WIP preparation diff against c2fffa61961228de8466b12939ef1c578506e7ba. Preserve the frozen 2026-08-12 protocol and plan byte-for-byte.

Resolve every known WIP risk before collection:
1. Add an explicit run-config/1 import/compatibility boundary and direct tests for run-config/2 field binding and digest behavior.
2. Add direct tests for nonempty run-directory refusal and document the resume contract.
3. Test host-snapshot capture and platform fallbacks.
4. In experiments/run_matrix.py, resolve the accidental default-matrix change from 1,068 to 1,128 runs; version the matrix schema if semantics changed; make void-reason creation crash-safe/atomic enough that an infrastructure failure cannot leave unaccounted evidence; add interruption and integration coverage.
5. Decide and regression-test the exact bootstrap percentile/quantile convention so experiments/statistics.py and the former paper_tables.py implementation cannot silently shift an interval endpoint.
6. Add end-to-end raw-fixture coverage for provenance, void accounting, plan/run agreement, duplicate run IDs/seeds, and invalid-infrastructure exclusion.
7. In scripts/fsync_always_benchmark.sh and tests, behaviorally cover zero, negative, noninteger and invalid values; actual resume preservation; configuration-gate failure; versioned roots; and the absent historical three-run raw dataset.
8. Confirm no collection path deletes or overwrites valid or voided evidence and no path uses FLUSHALL, FLUSHDB, unrestricted KEYS, rm -rf on result roots, outcome-dependent retries, or fakeredis-only behavior.

Evidence decision:
- search only authorized locations for the original 432 raw runs and historical voided evidence;
- if found, verify counts/hashes/structure and do not alter the source copy;
- if not found, create an append-only dated amendment formally declaring that the office collection will be a new replication dataset, not reconstruction of historical raw evidence;
- create a new dataset ID and a new immutable machine-readable plan bound to the current Git SHA, office environment, Redis digest/configuration, seeds and exact result root;
- do not edit the frozen 2026-08-12 hypothesis text or plan.

Run focused Stage 3 tests, Stage 1/2 regressions, then the complete pytest suite. Require zero failures and report environment-gated skips exactly. Also run git diff --check, secret/private-path scan, plan validation, and generated-number reproducibility without promoting changed generated files.

Do not commit or push yet. Return READY FOR PILOT only if all local gates pass and list all changes, tests and exact new amendment/plan hashes. Otherwise return BLOCKED.
```

## Prompt 3 — Non-confirmatory pilot and 432-run replication

```text
Continue only if Prompt 2 returned READY FOR PILOT.

First run a minimal engineering pilot in a separately named pilot root. The pilot must never enter confirmatory denominators or the final raw-results root. Use it only to verify the disposable Redis marker, namespace-limited cleanup, plan binding, fixed seed handling, restart/kill observation, ledger capture, environment capture, resume behavior, void preservation, disk growth and shutdown behavior.

If the pilot exposes a defect, preserve it under pilot/voided with a machine-readable reason, fix the defect, rerun the complete relevant tests, append a dated protocol amendment when required, and generate a new plan/hash before scientific collection. Do not silently reuse a pilot as a valid run.

If the original 432-run raw archive remains absent, collect a new versioned replication dataset matching the repository’s historical collected matrix:
- exactly 432 valid runs;
- exactly 3,780 executions;
- exactly 126 cells;
- the repository-defined systems, regimes, crash points, seeds and executions per run;
- fixed predeclared order or documented fixed interleaving;
- no outcome-dependent stopping, favorable-seed replacement or silent rerun;
- infrastructure-invalid attempts preserved under results/voided with their original bytes and reasons;
- every run bound to dataset ID, plan hash, Git SHA, run ID, seed, Redis digest/configuration, environment record and raw-directory hash;
- independent ground-truth ledgers preserved.

Do not call this historical evidence. Call it a new replication dataset and keep it separate from the Stage 2 aggregate-only dataset.

After collection, freeze the dataset and verify counts, unique IDs/seeds, plan agreement, void accounting, manifests and recursive SHA-256. Run analysis only far enough to compare the new replication against the committed aggregates and expose any mismatch; do not revise the manuscript or pool datasets yet.

Stop and report PASS, PARTIAL or BLOCKED, including exact runtime, valid/void counts, counts by cell, archive size, hashes and every contradiction. Do not commit, push, or start B2/B3 in this prompt.
```

## Prompt 4 — Mandatory B2 collection

```text
Continue only after the replication dataset is frozen and verified, or after the original raw archive was independently recovered and verified.

Run mandatory B2: redis-kill-preack at after_intent_before_barrier.

Exact four cells:
1. AUTHORITATIVE_READBACK × AEP_FULL
2. AUTHORITATIVE_READBACK × B3_INTENT_NO_BARRIER
3. POSITIVE_ONLY_READBACK × AEP_FULL
4. POSITIVE_ONLY_READBACK × B3_INTENT_NO_BARRIER

For each cell collect exactly 30 independent runs × one execution = 30 runs/executions. Total: 120 runs and 120 executions. Use the frozen unique seeds and fixed interleaved order. Use identical host/Redis settings and verify the disposable marker before every cleanup/restart/kill operation.

Preserve the falsifiable prediction: endpoint capability may change final declared ambiguity, but it must not retroactively change whether the provider received an effect. Report a contradictory applied-effect pattern honestly.

Primary outcomes:
- unwanted applied-effect rate;
- dispatch-withheld rate;
- declared-ambiguity rate;
- undetected duplicates;
- lost effects;
- barrier refusal/acknowledgement behavior;
- Redis kill/restart timing;
- independent ledger agreement.

Do not rerun a valid unfavorable run. Preserve every infrastructure-invalid attempt under results/voided. Do not pool capabilities or systems.

After collection, freeze and verify B2 raw evidence. Report per-cell raw counts/denominators, absolute differences, run-clustered intervals, and clearly labelled descriptive Fisher tests. Stop after the B2 report. Do not revise the paper, run B3, commit or push.
```

## Prompt 5 — Mandatory B3 timing collection

```text
Continue only after B2 is frozen and verified.

Run mandatory B3 crash-free timing evidence for four cells:
- AEP_FULL × appendfsync everysec;
- B3_INTENT_NO_BARRIER × appendfsync everysec;
- AEP_FULL × appendfsync always;
- B3_INTENT_NO_BARRIER × appendfsync always.

Each cell must have exactly nine independent valid runs and 10 executions per run. Total: 36 runs and 360 executions.

If the historical three-run raw directories remain absent, aggregate-only historical measurements do not count toward the nine; collect nine new raw-backed runs per cell in the new dataset. If three original raw runs per cell were genuinely recovered and verified, preserve them and append only six new independent runs per cell.

Use paired frozen seeds across AEP/B3 and both durability settings, fixed interleaved order, stable host load, and an explicit CONFIG GET appendfsync verification before each arm. Stop if effective configuration differs.

Primary estimand:
median AEP-full step latency minus median B3 step latency within the same appendfsync configuration, with uncertainty resampled at the run level.

Do not add runs based on significance or whether an interval crosses zero. Preserve unfavorable or tying results. Preserve infrastructure-invalid attempts under results/voided and do not include them silently.

Freeze and verify B3 raw evidence. Report exact medians, absolute differences, run-clustered intervals, valid/void counts, configuration evidence and host-load diagnostics. Stop after the B3 report. Do not revise the paper, commit or push.
```

## Prompt 6 — Freeze, analyze, and decide whether secondary experiments are justified

```text
Freeze the core replication, B2 and B3 evidence before analysis. Do not collect more runs in this prompt.

Verify the expected core scope:
- replication: 432 runs / 3,780 executions / 126 cells, if recollection was required;
- B2: 120 runs / 120 executions / 4 cells;
- B3: 36 runs / 360 executions / 4 cells;
- combined new core: 588 runs / 4,260 executions / 134 cells when full recollection was required.

Rebuild analysis only from raw valid runs plus explicit void accounting. Every output must trace to dataset version, regime, system, capability, crash point, keying, durability, run ID, seed, execution count, inclusion/void status and raw-directory hash.

Treat runs as independent clusters. Keep p0, p30, every-execution-crashed, Redis-kill, timing and block-loss regimes separate. Report numerator/denominator beside every rate. Label Fisher tests as execution-level descriptive tests where clustering remains. Do not suppress contradictions or manually place values in LaTeX.

Compare the new replication dataset with the frozen Stage 2 aggregate values. If they differ, report and investigate the discrepancy without choosing the more favorable dataset.

Then produce a decision table—not new experiments—for:
- redis-kill-inflight: 120 runs / 120 executions / 4 cells / about 1.19 h;
- p30: 63 runs / 630 executions / 21 cells / about 0.91 h;
- ORACLE_FINGERPRINT: 351 runs / 3,510 executions / 117 cells / about 10.82 h.

For each, state the exact active manuscript claim it would test, whether the question remains unresolved after core evidence, expected value, cost and preregistered prediction. Recommend RUN or SKIP. Do not run any secondary cell until the user selects it.

Return the frozen core analysis and secondary-experiment recommendation. Do not edit the manuscript, commit or push.
```

## Prompt 7 — Optional selected secondary experiment

```text
Run only the secondary experiment explicitly selected by the user after Prompt 6. Do not expand it into the complete 1,068/1,128-run default matrix.

Before collection, append a dated pre-result question and falsifiable prediction, create a new immutable plan/hash, and record fixed seeds/order, run counts, exclusions, void rules, runtime and disk budget.

Keep its regime and dataset identity separate from replication, B2 and B3. Preserve every valid and voided attempt. Do not replace unfavorable seeds, stop on significance, or promote exploratory results to confirmatory evidence.

For redis-kill-inflight, preserve the prior prediction that arms may tie. For p30, answer only the intermediate crash-rate/overhead question. For ORACLE_FINGERPRINT, treat it as alternative-keying sensitivity rather than the primary result.

Freeze, checksum and report the selected experiment, then stop. Do not revise the manuscript or run another optional experiment.
```

Skip Prompt 7 if no secondary experiment is justified.

## Prompt 8 — Manuscript, PDFs, and DOI-ready artifact

```text
Continue only after all selected evidence roots are frozen and checksum-verified.

Regenerate all analysis CSVs, tables, figures and LaTeX macros from the raw evidence pipeline. Never hand-edit generated scientific values.

Update abstract, introduction, evaluation, threats, artifact section, conclusion, README, cover letter and metadata only where the new evidence supports a change. Keep prevention and detection distinct. If B2 does not replicate, narrow or withdraw the claim. If B3 remains uncertain or contradicts the directional claim, retain the uncertainty. Clearly distinguish the historical aggregate-only Stage 2 dataset from the new raw-backed replication dataset. Do not claim public availability or a DOI that does not exist.

Run:
- focused Stage 3 tests;
- Stage 1 and Stage 2 regressions;
- complete pytest suite with exact skips;
- analysis/provenance/count/manifest gates;
- make reproduce-figures;
- paper-number, citation, BibTeX and reference checks;
- public and anonymous PDF builds;
- git diff --check;
- secret/private-path and stale-claim scans.

Render every page of both PDFs at 250 DPI and inspect it. Require zero overfull boxes, no clipping/collisions, readable tables/figures, embedded fonts, no Type 3 fonts, no undefined citations/references, and a passing anonymous identity scan.

Build a versioned DOI-ready archive outside Git containing all raw valid runs, voided attempts/reasons, ledgers, configs, logs, environment records, plans/protocols/amendments, analysis inputs/outputs, MANIFEST.csv, MANIFEST.md, recursive SHA256SUMS, exact Git SHA/lockfiles, reproduction instructions, license and supported metadata. Scan it for credentials/private paths. Do not upload it.

Perform a clean-room verification in a fresh clone/worktree: verify checksums, regenerate analysis/tables/figures/numbers, run tests and paper gates, and compare outputs. Report any nondeterministic bytes.

Do not commit, push, merge, tag, release, deposit or submit. Return PASS, PARTIAL or BLOCKED with exact data counts, voids, statistics, changed claims, tests, PDF hashes, archive filename/size/file count/run count/hash and clean-room result.
```

## Prompt 9 — Independent final rereview

```text
Perform an independent, skeptical rereview of the completed Stage 3 work. Do not edit files, run new experiments, commit, push, merge, tag, upload or submit.

Audit:
- baseline and complete diff;
- protocol/plan immutability and amendments;
- no outcome-dependent exclusions or seed replacement;
- exact valid/void/run/execution/cell counts;
- raw-to-analysis-to-LaTeX traceability;
- run-level clustering and regime separation;
- replication versus historical aggregate wording;
- B2/B3 conclusions, including contradictory results;
- all test/build/PDF/anonymity/font gates;
- recursive archive checksums and clean-room reproduction;
- credential/private-path scan;
- DOI, affiliation, AI disclosure, anonymity policy and release/submission blockers.

Return PASS, REQUIRES REVISION or BLOCKED with file/line-specific findings and severity. Do not call the paper submission-ready merely because local Stage 3 evidence passes.
```

## Prompt 10 — Validated checkpoint commit and push

```text
Run this only if Prompt 9 returned PASS or all of its findings were fixed and independently reverified.

Create a final Stage 3 checkpoint on the existing stage3-prep-office-20260812 feature branch. Do not merge main.

Before staging, verify the working tree, complete test/gate report, raw/archive exclusion rules, credential scan, git diff --check, manuscript numbers and PDF hashes.

Stage only intended source, tests, reports, manuscript sources, regenerated small tables/figures/macros, and the two verified PDFs if repository policy tracks them.

Never stage raw/voided result directories, clean-room archives, local environment files, Docker/Redis data, secrets or machine-specific paths.

Show the exact staged list and diff stat before committing. Commit with a precise message describing expanded evidence and artifact preparation; do not use “submission-ready.” Push only the feature branch and verify the remote SHA.

Return the commit SHA, remote SHA, exact files committed, excluded artifacts and remaining external blockers. Do not merge, tag, release, deposit, insert a DOI, or submit.
```

## Prompt 11 — B1, only if separately approved

```text
Do not execute B1 unless the user has explicitly approved privileged block-device fault injection and the host is disposable native Linux—not WSL, Docker Desktop, a shared server, or a production machine.

First resolve and display the exact disposable loop-device/dm-flakey/ext4 target and prove that no unrelated filesystem/service can be affected. Stop for confirmation before any privileged mutation.

If approved, follow docs/24-revision-backlog.md exactly: full AEP protocol, AEP_FULL versus B3, NO_READBACK, write loss after intent CAS and before barrier acknowledgement, independent ground-truth ledger, 60 runs / 600 executions / two cells, complete raw/void preservation, and no weakening to a two-key proxy.

Treat unavailable privilege or unsuitable topology as BLOCKED/DEFERRED, not a failed scientific result. Do not merge B1 into other regimes.
```

## 5. Final rule

The office machine solves the infrastructure problem; it does not solve the missing-evidence problem by itself. If the original raw archive remains absent, the scientifically valid path is a new, explicitly labelled replication dataset followed by B2 and B3. Never reconstruct raw evidence from aggregate CSVs, and never present a WIP preparation branch as validated Stage 3 closure.
