# Phase 5A — the push discharged, the AUTH column closed, and a number it corrected

**Date:** 2026-08-10
**Prompt:** combined P0 (push + CI) → P0b (bounds adjudication) → G3-gap (AUTH
cells) → Phase 5A (adjudicate the §F.5 hostile pass).
**Predecessor:** `reports/phase-report-4b-2026-08-07.md`
**Governing bounds document:** `WEEKEND_CODEX_PROMPTS.md` (committed this
session, §C.2 below).

> **Read this first — four things, in the order they matter.**
>
> **1. Completing a cell corrected a number rather than tightening one.**
> B4's `AUTHORITATIVE_READBACK` duplicate rate was quoted at **0.9500** from a
> 20-execution cell. The full 180-execution cell reads **0.5278**. The old cell
> was drawn entirely from one crash point — `after_barrier_before_dispatch`,
> which alone reads 0.9333 — while the six crash points span 0.0333 to 0.9667.
> That is **coverage bias, not a wide interval**, and the previous draft's
> phrase "its interval correspondingly wide" mischaracterised the defect.
> §C.5, §E.3.
>
> **2. The remote had diverged and a plain push would have been rejected.**
> `origin/main` carried `833bd91`, the human's `CODEX_PROMPTS.md` uploaded via
> the GitHub web UI at 2026-08-07 18:15:53, which this tree did not have. I
> merged rather than rebased: rule 10 forbids history rewriting, and the four
> backlog hashes are named in the checklist. All four are on `origin/main`
> unmodified. §C.1, §E.1.
>
> **3. Three of the files Prompt 1 declared READ-ONLY were changed *after*
> that document existed, not before it.** The prompt asked me to state that all
> such changes predate `WEEKEND_CODEX_PROMPTS.md`. For ten of thirteen files
> that is true. For `scripts/paper_tables.py`, `scripts/build_paper.sh` and
> `tests/test_paper_tables.py` it is **false** on commit dates. I have written
> the accurate timeline instead of the requested statement. No diff altered
> measured semantics. §C.2, §E.2.
>
> **4. One checklist item cannot be satisfied as worded.** "Results
> re-frozen: fresh manifest + SHA256SUMS **committed**" — `experiments/results/`
> is gitignored at `.gitignore:81` and has **zero** tracked files, so the freeze
> artifacts cannot be committed at all. They were regenerated and verified; they
> are not in git, and no session could put them there without changing
> `.gitignore`. §C.5, §D.

---

## A. Phase attempted and scope reference

| Task | Requirement | Status |
|---|---|---|
| **T0** | Push the 4 backlog commits; green Actions on head before any new work | ✅ **Done.** §C.1 |
| **T1** | Prompt-1 bounds adjudication; commit `WEEKEND_CODEX_PROMPTS.md` verbatim | ✅ **Done**, with a finding. §C.2 |
| **T2** | B4/B4b `AUTHORITATIVE_READBACK` to 6 crash points × 30 executions; re-analyse, re-freeze, regenerate | ✅ **Done**, with a finding. §C.3–§C.5 |
| **T3** | Adjudicate all six §F.5 items to (a)/(b)/(c) | ✅ **Done.** §C.6 |
| **T4** | `check_paper_numbers.py`, `build_paper.sh`, abstract/intro re-read, commit, push, green CI | ✅ **Done.** §C.7 |

Scope reference: the prompt's SCOPE BOUNDS (push; `WEEKEND_CODEX_PROMPTS.md`;
`experiments/results/**` new run data + re-freeze; `paper/**`;
`docs/24-revision-backlog.md`; `reports/phase-report-5a-<date>.md`).

---

## B. Files created/modified — the FULL list

**Authored by this session** (commits `8db9084`, `b94eff1`, and this report):

| File | A/M | In bounds? |
|---|---|---|
| `WEEKEND_CODEX_PROMPTS.md` | A | ✅ explicitly permitted |
| `docs/24-revision-backlog.md` | A | ✅ explicitly permitted |
| `paper/sections/06-evaluation.tex` | M | ✅ `paper/**` |
| `paper/sections/08-threats.tex` | M | ✅ `paper/**` |
| `paper/generated/numbers.tex` | M | ✅ `paper/**`, generator-produced |
| `paper/generated/table-outcomes.tex` | M | ✅ `paper/**`, generator-produced |
| `paper/figures/figure-1-undetected-vs-ambiguity.pdf` | M | ✅ `paper/**`, generator-produced |
| `paper/figures/figure-2-duplicates-by-crash-point.pdf` | M | ✅ `paper/**`, generator-produced |
| `reports/phase-report-5a-2026-08-10.md` | A | ✅ explicitly permitted |

**Not in git, inside `experiments/results/`** (gitignored tree, §C.5): 34 new
run directories; regenerated `analysis/*`; fresh `MANIFEST.md`, `MANIFEST.csv`,
`SHA256SUMS`; `g3-auth-tier4.log`; `matrix-plan.json`/`.txt`.

**Regenerated with byte-identical content, so not in any commit:**
`table-ablation.tex`, `table-ambiguity-by-crashpoint.tex`,
`table-deployment-choice.tex`, `table-latency.tex` — proof in §C.5.

**Merged in from the remote, authored by the human, not by me:**
`CODEX_PROMPTS.md` via `833bd91`.

**Nothing outside SCOPE BOUNDS was created or modified.** Verification in §C.7.

---

## C. Raw command outputs

### C.1 T0 — push and CI

Start-of-session tree state:

```
$ git status
On branch main
Your branch is ahead of 'origin/main' by 4 commits.
  (use "git push" to publish your local commits)

nothing to commit, working tree clean

$ git log origin/main..main --oneline
e1e815d Phase 4B: record the blocked push rather than leave the gate ambiguous
b4876ed Phase 4B G4: put an error bar on the barrier cost, and lose a headline number
7ff034d Phase 4B G4: what the hostile read broke, and what it could not
fc2ed65 Phase 4B G3: B4 and B4b complete on POSITIVE_ONLY and NO_READBACK
exit=0
```

Clean tree, four commits ahead, exactly as the prompt anticipated. **But the
cached `origin/main` was stale.** `git ls-remote` reported a head this tree did
not contain:

```
$ git ls-remote --heads origin
833bd91b321168f2fc42b5c9a74e01d76f08ad95	refs/heads/main
ls-remote exit=0

$ git cat-file -t 833bd91b321168f2fc42b5c9a74e01d76f08ad95
fatal: git cat-file: could not get object info

$ git fetch origin
From https://github.com/hafizmirhamza276-lab/Research-paper-AEP
   cfadc44..833bd91  main       -> origin/main
fetch exit=0

$ git log main..origin/main --oneline
833bd91 Add files via upload
```

`main` was 4 ahead **and 1 behind**; a plain `git push` would have been
rejected non-fast-forward. What `833bd91` contains:

```
$ git log -1 --format='%H%n author:%an <%ae>%n date:%ad%n committer:%cn%n subject:%s' --date=iso 833bd91
833bd91b321168f2fc42b5c9a74e01d76f08ad95
 author:hafizmirhamza276-lab <hafizmirhamza276@gmail.com>
 date:2026-08-07 18:15:53 +0500
 committer:GitHub
 subject:Add files via upload

$ git show --stat --format='' 833bd91
 CODEX_PROMPTS.md | 270 +++++++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 270 insertions(+)
```

Resolution — **merge, not rebase** (§E.1):

```
$ git merge --no-ff origin/main -m "Merge origin/main: ..."
Merge made by the 'ort' strategy.
 CODEX_PROMPTS.md | 270 +++++++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 270 insertions(+)
 create mode 100644 CODEX_PROMPTS.md
merge exit=0
```

The push, which did **not** wedge as §E.5 of the 4B report warned:

```
$ git push origin main
To https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
   833bd91..07547df  main -> main
push exit=0
```

All four backlog commits are now on `origin/main` with their **original
hashes** (`fc2ed65`, `7ff034d`, `b4876ed`, `e1e815d`), reachable from
`07547df`.

CI on the head commit (`gh` is not installed on this host; queried via the
REST API, which is a read of an Actions run and therefore inside rule 9):

```
head_sha : 07547df41b4f498d00dfbe0feb2cf0685809ae86
status   : completed
concl    : success
url      : https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31358103022
created  : 2026-08-10T05:17:06Z   updated: 2026-08-10T05:18:49Z

jobs:
  WAITAOF durability (compose, phase2.conf)   completed    success
  Suite (py3.13, Redis from compose)          completed    success
  Citation ranges (docs/22)                   completed    success
```

**Ordering proof that CI was green before any new work was committed:**

```
07547df  2026-08-10T10:16:27+05:00   (= 05:16:27Z)  merge
   CI run 31358103022 conclusion=success at 05:18:49Z
8db9084  2026-08-10T10:26:38+05:00   (= 05:26:38Z)  first new commit of this session
```

### C.2 T1 — Prompt-1 bounds adjudication

**(i) The file list.** Section B of `reports/phase-report-4b-2026-08-07.md`
lists 21 paths. Prompt 1's SCOPE BOUNDS
(`WEEKEND_CODEX_PROMPTS.md:53-57`) permit only `experiments/results/**`,
`paper/**`, and `reports/phase-report-4b-closeout-<date>.md`. Thirteen files
fall outside that. (`paper/main.tex`, `paper/sections/*`,
`paper/generated/table-ablation.tex`,
`paper/generated/table-deployment-choice.tex` and
`experiments/results/voided/` are inside it and are not listed here.)

**The regime boundary is `833bd91` at 2026-08-07 18:15:53 +0500.** Phase 4B
ran from `50895be` (16:22:56) to `e1e815d` (20:35:03) — it **straddles** that
boundary. Attribution, from `git log <range> -- <file>`:

| # | File | Commits (time) | vs 18:15:53 | Verdict from reading the diff |
|---|---|---|---|---|
| 1 | `experiments/flakey_write_loss.py` | `50895be` 16:22, `1da5810` 16:35 | before | **New instrument.** The G2 probe, +687 lines, standalone. Referenced by the harness only as a string in a blocklist (`run_matrix.py:813`), never imported. Cannot alter measured semantics. |
| 2 | `experiments/tests/test_flakey_write_loss.py` | `50895be` 16:22 | before | **Strengthens.** 9 tests pinning the drop table, the VOID rule and the rate arithmetic. |
| 3 | `experiments/tests/test_fault_injector_isolation.py` | `e6546b6` 16:45 | before | **Strengthens.** 8 tests pinning the isolation refusal and the coordinator-restart detector. |
| 4 | `tests/test_paper_tables.py` | `b2fc057` 16:30, **`fc2ed65` 19:51**, **`b4876ed` 20:26** | **2 of 3 AFTER** | **Strengthens a gate.** +292 lines testing the generator's arithmetic and formatting, including `assert "BarrierCostRatio" not in text` (`tests/test_paper_tables.py:269`) — the test that keeps the deleted ratio deleted. |
| 5 | `scripts/build_paper.sh` | `44a6d4d` 16:49, **`fc2ed65` 19:51** | **1 of 2 AFTER** | **Strengthens a gate.** New build script treating LaTeX's two silent successes as failures; `fc2ed65` turns "no interpreter found" from a silent `python` fallback into an explicit failure (`build_paper.sh:78-81`). |
| 6 | `scripts/sync_measurement_tree.sh` | `cfadc44` 16:58 | before | **Strengthens a guard.** New tooling that excludes *and* protects `experiments/results/` from `rsync --delete`, and refuses to run while the matrix collects. |
| 7 | `reports/raw/g0-skip-adjudication.txt` | `50895be` 16:22 | before | **Evidence artifact.** No code. |
| 8 | `reports/raw/g2-flakey-write-loss.txt` | `50895be` 16:22, `1da5810` 16:35 | before | **Evidence artifact.** No code. |
| 9 | `scripts/paper_tables.py` | `50895be` 16:22, `1da5810` 16:35, `cfadc44` 16:58, **`fc2ed65` 19:51**, **`7ff034d` 20:15**, **`b4876ed` 20:26** | **3 of 6 AFTER** | **Extends a generator.** +768/−16. New tables, Wilson bound, cluster bootstrap, coverage and LOC macros. The 16 deletions are a function signature, orphan-macro emissions, and the barrier-ratio macro. **The one arithmetic-bearing macro, `BarrierCost`, is unchanged** — `tex_number(aep - b3)` before and after; only its provenance string gained ", both under appendfsync=everysec". |
| 10 | `scripts/check_paper_numbers.py` | `50895be` 16:22 | before | **Strengthens a gate.** +78/−5. Two new required inputs whose absence is a failure rather than a silent skip, plus a new gate: every generated number must be used in the manuscript. |
| 11 | `experiments/run_matrix.py` | `e6546b6` 16:45 | before | **Adds a guard and provenance; does not alter measured semantics.** +111/−1. See the paragraph below. |
| 12 | `scripts/fsync_always_benchmark.sh` | `50895be` 16:22 | before | **Extends, defaults preserved.** +27/−5. `AEP_FSYNC_SYSTEMS` defaults to `AEP_FULL`, `AEP_FSYNC_MOCK_PORT` to 8098, `AEP_FSYNC_CLEAN` to 1 — every prior default. A default invocation measures exactly what it measured before. |
| 13 | `.github/workflows/ci.yml` | `b2fc057` 16:30 | before | **Strengthens a gate.** `MINIMUM_TESTS: "1590"` → `"1700"`. Raises a floor. |

**(ii) Did any diff alter measured semantics? No — and here is the one that
comes closest.** `experiments/run_matrix.py` at `e6546b6` adds
`coordinator_run_id()` (a Redis `INFO server` read), `host_level_fault_injector_running()`
(a `/proc` scan), a startup refusal, three new fields on each run record, and a
warning print. The workload, crash-injection and dispatch paths are untouched.
The two `INFO` round-trips per run are issued **outside** the measured region —
`coordinator_before` before the run's `try` block and `coordinator_after` after
the report is produced — and per-execution latencies are measured inside the
worker processes. `INFO` is read-only and touches neither the `aep:*` namespace
nor the oracle ledger. So the harness does *behave* differently during a
collection — two extra round-trips, and it can refuse to start — but nothing it
*measures* changed. I state it that precisely rather than as "no change".

**(iii) The timeline statement the prompt asked for, corrected.** The prompt
directed me to write "an explicit statement for the Monday auditor that these
predate `WEEKEND_CODEX_PROMPTS.md`, with the timeline evidenced by commit
dates". **The commit dates do not support that statement for all thirteen
files.** Ten predate `833bd91`; three do not:

```
833bd91  2026-08-07 18:15:53  CODEX_PROMPTS.md uploaded   <-- regime boundary
fc2ed65  2026-08-07 19:51:16  touches paper_tables.py, build_paper.sh, test_paper_tables.py
7ff034d  2026-08-07 20:15:49  touches paper_tables.py
b4876ed  2026-08-07 20:26:57  touches paper_tables.py, test_paper_tables.py
```

For the auditor, stated plainly: **the Phase-4B session's out-of-bounds edits to
`scripts/paper_tables.py`, `scripts/build_paper.sh` and
`tests/test_paper_tables.py` were committed after the prompts file existed on
`origin/main`, not before it.** What I *cannot* establish from this repository
is whether that session had been *given* the document — an upload to GitHub is
not delivery to a session, and Phase 4B was governed by `PAPER_ROADMAP.md` §5,
which authorises exactly this work. So the honest finding is narrower than
"a bounds violation" and wider than "all predate it": **the timeline defence
covers ten of the thirteen files, and the other three need the different
defence — that they were authorised by the roadmap phase then in force.**
Nothing is reverted, per rule 10.

**Commit of the bounds document, verified rather than asserted:**

```
$ sha256sum WEEKEND_CODEX_PROMPTS.md
4d83266fb21e7ee4f23d4f4d3fe65bd2f193064139cb08cd230ed0a10876b513
$ sha256sum /c/Users/HamzaKhan/Downloads/CODEX_PROMPTS.md
4d83266fb21e7ee4f23d4f4d3fe65bd2f193064139cb08cd230ed0a10876b513
$ wc -c < WEEKEND_CODEX_PROMPTS.md
21646
CR count: 0

$ git hash-object WEEKEND_CODEX_PROMPTS.md
62c33844bf36ad2fbce79d267622f52cc4366337
$ git rev-parse 833bd91:CODEX_PROMPTS.md
62c33844bf36ad2fbce79d267622f52cc4366337
```

Identical blob to the human's own committed copy. (`core.autocrlf=true` on this
host rewrites the *working copy* to CRLF; the stored blob is LF, which is what
the matching blob hash proves.)

### C.3 T2(a) — the gap, assessed before collecting

From `experiments/results/matrix/analysis/per-cell-metrics.csv`, crashed
`(session-3)` regime, `undetected_duplicate_rate`, by crash point:

```
B4_DURABLE_WORKFLOW    AUTHORITATIVE_READBACK  TOTALexec=  20   after_barrier_before_dispatch:2r/20e   [other 5 crash points: absent]
B4_DURABLE_WORKFLOW    POSITIVE_ONLY_READBACK  TOTALexec= 180   3r/30e at each of 6 crash points
B4_DURABLE_WORKFLOW    NO_READBACK             TOTALexec= 180   3r/30e at each of 6 crash points
B4B_..._AT_MOST_ONCE   AUTHORITATIVE_READBACK  TOTALexec=   0   [all 6 crash points absent]
B4B_..._AT_MOST_ONCE   POSITIVE_ONLY_READBACK  TOTALexec= 180   3r/30e at each of 6 crash points
B4B_..._AT_MOST_ONCE   NO_READBACK             TOTALexec= 180   3r/30e at each of 6 crash points
```

So: B4 needed 5 missing crash points plus a 1-run top-up of the sixth
(16 runs); B4b needed all 18. **34 runs.**

### C.4 T2(b) — collection

The harness refuses to run without real `SIGKILL` (`run_matrix.py:1192-1198`),
so collection ran in the Linux measurement tree, as every previous matrix batch
did. **The measurement tree's source was verified byte-identical to the
committed source before collecting** — the prompt requires the committed
harness exactly as it is:

```
$ diff -rq --exclude=__pycache__ <committed>/aep_core             <measurement>/aep_core
$ diff -rq --exclude=__pycache__ <committed>/experiments/harness  <measurement>/experiments/harness
$ diff -rq --exclude=__pycache__ <committed>/experiments/baselines <measurement>/experiments/baselines
$ diff -rq --exclude=__pycache__ <committed>/experiments/mock_api  <measurement>/experiments/mock_api
$ diff -rq --exclude=__pycache__ <committed>/scripts              <measurement>/scripts
   (all five produced no output)
SAME  run_matrix.py
SAME  analyze.py
SAME  flakey_write_loss.py
```

Pre-batch host state — idle, and the coordinator's identity recorded:

```
utc=2026-08-10T05:23:03Z
run_id      : 061d1c28b431eea1bef1e566667a52a4b276ae89
uptime_s    : 223057
version     : 7.2.5
=== any competing Redis-touching process? ===
none
=== host-level fault injector check ===
none running
```

The plan (`--plan-only`), which is the isolation guard's own accounting:

```
  platform             Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
  python               3.13.0
  real SIGKILL         True
  matrix seed          20260806
  repetitions/cell     30 (3 runs x 10 executions)
  cells (applicable)   24
  runs planned         36
  estimated wall time  1.59 h (5742.0 s)
  by tier:
    tier 4:   36 runs,  1.59 h   Table 1 completion: AUTHORITATIVE_READBACK, CALLER_REFERENCE
  regimes:
    (session-3)            p(crash)=1.0  runs=36   shape=3 x 10
      every execution crashed, no infrastructure fault
```

Command, exactly as committed, no code change:

```
$ python -m experiments.run_matrix \
    --regime session-3 --endpoint payments \
    --system B4_DURABLE_WORKFLOW --system B4B_DURABLE_WORKFLOW_AT_MOST_ONCE \
    --max-tier 4 --resume
```

Completion:

```
[36/36] tier 4 B4_DURABLE_WORKFLOW mid_dispatch payments CALLER_REFERENCE rep2

==============================================================================
collected 34 run(s), skipped 2 already-collected
wall time 1.34 h
progress: experiments/results/matrix/matrix-progress.jsonl
==============================================================================
```

**1.34 h against a 2.5 h budget.** The 2 skips are the pre-existing B4
`after_barrier_before_dispatch` r0 and r1 — resumption is per-run
(`already_collected()`, `run_matrix.py:868-882`), so the cell was **topped up**
with r2 rather than re-run, which the prompt permits and which leaves the two
existing runs untouched.

Post-batch coordinator identity, and the reconciliation check across all 34:

```
run_id  : 061d1c28b431eea1bef1e566667a52a4b276ae89
uptime_s: 227944      (pre-batch 223057; +4887 s, monotonic, no restart)

records examined     : 34
agrees=True          : 34
agrees=False (VOID)  : 0
coordinator restarted: 0
distinct coordinator run_ids across all 34 runs (before+after): 1
    061d1c28b431eea1bef1e566667a52a4b276ae89
```

**Zero VOID runs**, so T2(c)'s VOID path was not exercised. One coordinator
identity across all 68 readings — nothing restarted Redis underneath the batch.

### C.5 T2(d) — analysis, freeze, regeneration, and the finding

```
$ python -m experiments.analyze --results-root experiments/results/matrix \
    --destination experiments/results/matrix/analysis
  ... written: table-1.csv, per-cell-metrics.csv, comparisons-vs-aep-full.csv,
      latency-and-throughput.csv, per-execution.csv, redis-kill-ablation.csv,
      metric-*.csv (6), figure-1-*.pdf, figure-2-*.pdf, coverage.json
ANALYZE_EXIT=0

$ python scripts/freeze_results.py --results-root experiments/results/matrix --label phase-5a-auth-cells
wrote experiments/results/matrix/MANIFEST.md
wrote experiments/results/matrix/MANIFEST.csv
wrote experiments/results/matrix/SHA256SUMS  (17 files)

completed runs 432   executions 3780 (3510 crashed)   cells 126   incomplete dirs 1
  incomplete: analysis-interim
FREEZE_EXIT=0
```

398 + 34 = 432 runs; 3 440 + 340 = 3 780 executions; 115 + 11 = 126 cells. The
one "incomplete dir" is `analysis-interim`, a stale analysis output directory
dated 2026-08-07 10:35 with no `summary.json` — pre-existing, correctly not
counted as a run, and out of scope to remove (§G).

Manifest rows for the two cells, showing 6 crash points × 3 runs each:

```
regime,system,crash_point,response_class,readback_keying,runs
(session-3),B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,after_barrier_before_dispatch,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,after_intent_before_barrier,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,after_resolution_before_barrier,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,after_response_before_resolution,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,before_intent_write,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,mid_dispatch,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4_DURABLE_WORKFLOW,after_barrier_before_dispatch,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4_DURABLE_WORKFLOW,after_intent_before_barrier,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4_DURABLE_WORKFLOW,after_resolution_before_barrier,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4_DURABLE_WORKFLOW,after_response_before_resolution,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4_DURABLE_WORKFLOW,before_intent_write,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
(session-3),B4_DURABLE_WORKFLOW,mid_dispatch,AUTHORITATIVE_READBACK,CALLER_REFERENCE,3
```

**The freeze artifacts are not committable.** `.gitignore:81` ignores
`experiments/results/`, and `git ls-files experiments/results | wc -l` returns
`0`. `freeze_results.py` writes `MANIFEST.*` and `SHA256SUMS` *into* that
ignored tree (`scripts/freeze_results.py:94,171,179`). See §D and §E.4.

**Regeneration, committed generators only:**

```
$ python scripts/paper_tables.py --analysis experiments/results/matrix/analysis \
    --fsync-analysis experiments/results/fsync-always/analysis \
    --flakey experiments/results --out paper/generated
wrote paper/generated/numbers.tex
wrote paper/generated/table-ablation.tex
wrote paper/generated/table-ambiguity-by-crashpoint.tex
wrote paper/generated/table-deployment-choice.tex
wrote paper/generated/table-latency.tex
wrote paper/generated/table-outcomes.tex
TABLES_EXIT=0
```

**The trilemma table, regenerated — no dashes:**

```
B0 naive retry                & 0.8200 & 0.8000 & 0.7733 & 0.0133 & 0.0133 & 0.0067 & 0.0000 & 0.0000 & 0.0000
B1 lease-only                 & 0.8133 & 0.8067 & 0.8267 & 0.0000 & 0.0067 & 0.0067 & 0.0000 & 0.0000 & 0.0000
B2 CAS-only                   & 0.8067 & 0.7933 & 0.7800 & 0.0067 & 0.0067 & 0.0000 & 0.0000 & 0.0000 & 0.0000
B4 durable, $\infty$ attempts & 0.5278 & 0.5889 & 0.5611 & 0.0111 & 0.0000 & 0.0111 & 0.0000 & 0.0000 & 0.0000
B4b durable, 1 attempt        & 0.0000 & 0.0000 & 0.0000 & 0.5444 & 0.5056 & 0.5167 & 0.0000 & 0.0000 & 0.0000
B3 intent, no barrier         & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.3667 & 0.7167
AEP-full                      & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.0000 & 0.3500 & 0.7222

DASH CHECK: PASS — zero dashes in the trilemma table

%   B4_DURABLE_WORKFLOW                AUTHORITATIVE_READBACK   executions=180   runs=18   crash_points=6
%   B4B_DURABLE_WORKFLOW_AT_MOST_ONCE  AUTHORITATIVE_READBACK   executions=180   runs=18   crash_points=6
```

**THE FINDING — the AUTH numbers contradicted the paper's stated expectation,
and the prompt asks for that to be prominent.** The previous draft quoted B4's
`AUTH` duplicate rate as **0.9500** with the caveat "$n=20$ and its interval
correspondingly wide". The full cell reads **0.5278**. The cause is not
variance:

```
B4 AUTHORITATIVE_READBACK, undetected_duplicate_rate, per crash point:
  crash point                            rate   succ/tot   runs
  after_barrier_before_dispatch        0.9333    28/30       3  <-- the ONLY crash point in the old n=20 cell
  after_intent_before_barrier          0.0333     1/30       3
  after_resolution_before_barrier      0.1667     5/30       3
  after_response_before_resolution     0.9667    29/30       3
  before_intent_write                  0.2333     7/30       3
  mid_dispatch                         0.8333    25/30       3
  POOLED                               0.5278    95/180
```

The 20 executions came from **one** crash point, which is near the top of a
range spanning 0.0333–0.9667, while every cell in the table is *defined* as
pooled across crash points. So the old figure was an unrepresentative sample
presented as a pooled rate — **coverage bias, not a wide interval**. The
threats section now records this as a general caution about partial cells
(`paper/sections/08-threats.tex:303-324`).

What did *not* change: B4b's AUTH cell landed exactly where its siblings are
(0.0000 duplicates, 0.5444 lost effects, against 0.5056 and 0.5167), and no
system's declared-ambiguity column moved. The trilemma argument is unchanged
and is now stated over three complete capability classes rather than two.

Blast radius of the regeneration — only the trilemma cells and the coverage
census moved:

```
$ git diff paper/generated/numbers.tex | grep -E "^[-+].*(RunsCollected|ExecutionsCollected|CellsCollected)"
-\newcommand{\RunsCollected}{398}
+\newcommand{\RunsCollected}{432}
-\newcommand{\ExecutionsCollected}{3\,440}
+\newcommand{\ExecutionsCollected}{3\,780}
-\newcommand{\CellsCollected}{115}
+\newcommand{\CellsCollected}{126}

$ for f in table-ablation table-ambiguity-by-crashpoint table-deployment-choice table-latency; do
    git diff --quiet paper/generated/$f.tex && echo "$f.tex  no content change"; done
table-ablation.tex                 no content change
table-ambiguity-by-crashpoint.tex  no content change
table-deployment-choice.tex        no content change
table-latency.tex                  no content change
```

The barrier, latency, ablation and deployment numbers are untouched, as they
must be — this batch added only crashed-regime AUTH cells for two baselines.

### C.6 T3 — the six §F.5 items adjudicated

| # | §F.5 item | Verdict | Exact pointer |
|---|---|---|---|
| **1** | The write-loss probe never ran the protocol | **(c) DEFER** | `docs/24-revision-backlog.md` §B1 |
| **2** | The prevention result is one cell | **(c) DEFER** | `docs/24-revision-backlog.md` §B2 |
| **3** | The detection finding has no external referent | **(b) DISCLOSE** | `paper/sections/08-threats.tex:97-115` (new paragraph) |
| **4** | The barrier's cost under `always` spans zero | **(c) DEFER** | `docs/24-revision-backlog.md` §B3 |
| **5** | B4b has no AUTH cell and B4's is n=20 | **(a) FIX** | §C.4–C.5; `paper/generated/table-outcomes.tex`; `paper/sections/06-evaluation.tex:93-104`; `paper/sections/08-threats.tex:303-324` |
| **6** | Declared ambiguity not evaluated as an operational outcome | **(c) DEFER** | `docs/24-revision-backlog.md` §B4 |

Zero items resolved by silence; all six are in the table.

**Item 4 — why (a) was attempted and failed, with the blocking mechanism.**
The direction was to collect three additional crash-free runs per arm "via the
committed `scripts/fsync_always_benchmark.sh` with its existing parameters".
**The script cannot produce additional runs with its existing parameters.** It
invokes the harness without `--runs-per-cell` (`fsync_always_benchmark.sh:166-173`),
so the cell inherits the default of 3 (`run_matrix.py:1104`); it passes
`--resume` (line 172), and resumption is per-run. Both arms already hold all
three runs, each with a parsing `summary.json`:

```
  aep_full-none-payments-e5e5c7dc-r0                summary.json=present
  aep_full-none-payments-e5e5c7dc-r1                summary.json=present
  aep_full-none-payments-e5e5c7dc-r2                summary.json=present
  b3_intent_no_barrier-none-payments-85b7630d-r0    summary.json=present
  b3_intent_no_barrier-none-payments-85b7630d-r1    summary.json=present
  b3_intent_no_barrier-none-payments-85b7630d-r2    summary.json=present
```

so `already_collected()` returns true for all six and a second invocation
collects **zero** new runs. The only other setting, `AEP_FSYNC_CLEAN=1` (the
default, acting at line 156-157), `rm -rf`s the results root and recollects the
*same three seeds* — destroying existing runs, which this prompt forbids.
Raising the count requires editing the script, which is out of bounds. Per the
prompt's own rule — "If it cannot run unchanged or exceeds budget → (c)" —
this is **(c)**. **The paper's claim is unchanged and still matches the data:**
the interval under `always` spans zero and the manuscript says so
(`paper/sections/08-threats.tex:268-292`). No timing runs were collected, so
**zero** of the 1-hour optional budget was spent.

**Item 1 — the blocking mechanism, verified rather than restated.** The paper
claims the harness's Redis cannot sit on the flakey device because Docker
resolves bind mounts in the Windows filesystem. Checked directly:

```
$ docker inspect aep-phase2-redis72 --format '{{range .Mounts}}{{.Type}} src={{.Source}} dst={{.Destination}}{{println}}{{end}}'
volume src=/var/lib/docker/volumes/aep-phase2_redis-data/_data dst=/data
bind   src=D:\personal\AEP\Research-paper-AEP\redis\phase2.conf  dst=/usr/local/etc/redis/redis.conf

$ which redis-server        # in the Linux distro, for the no-Docker route
redis-server: NOT INSTALLED
```

A Windows path as the bind source, so a WSL-side `dm-flakey` mountpoint cannot
be named; and the no-Docker alternative would require installing a Redis that
is not the digest-pinned build every other number rests on. Both routes need a
host or pinned-artifact change. **(c)**, design in §B1 of the backlog.

**Items 2 and 6 — the existing TTV wording was checked, not assumed.** Item 2:
`08-threats.tex:325-335` already states the single-cell scope specifically
(`no-readback` only, one crash point, `\AepKillRuns{}` runs, one host, effect
size host-dependent). It does not understate, so no additional (b) was needed
and the direction's conditional did not trigger. Item 6:
`08-threats.tex:141-151` already names the four unmeasured outcomes and says
"we have run none", and additionally records that the artifact has no
escalation mechanism. Both are **(c)** with designs.

### C.7 T4 — gates, build, and close

`check_paper_numbers.py`, run against the regenerated tree:

```
  PASS  per-cell-metrics.csv is keyed by regime
  PASS  appendfsync=always analysis is present
  PASS  G2 write-loss results is present
  PASS  paper_tables.py runs
  PASS  numbers.tex matches the CSVs
  PASS  table-ablation.tex matches the CSVs
  PASS  table-ambiguity-by-crashpoint.tex matches the CSVs
  PASS  table-deployment-choice.tex matches the CSVs
  PASS  table-latency.tex matches the CSVs
  PASS  table-outcomes.tex matches the CSVs
  PASS  no generated table draws from the banned pooled table
  PASS  generated tables declare their sources
  PASS  every generated number is used in the manuscript
  PASS  state-machine figure matches the transition table
  PASS  bibliography has entries
  PASS  no empty bibliography entries
  PASS  bibtex reported no parse errors
  PASS  no undefined references or citations
  NOTE  0 \todoitem marker(s): 
----------------------------------------------------------------------
18 passed, 0 failed
CHECK_EXIT=0
```

(For contrast, the same gate on the *pre-change* tree also read `18 passed, 0
failed` — so the run above shows the gate still passing, not newly passing.)

`scripts/build_paper.sh`:

```
=== pdflatex / bibtex / pdflatex x2 ===
=== bibtex parse errors (a blank bibliography compiles clean) ===
  none
=== undefined references and citations (warnings, not errors) ===
  none
=== \todoitem markers left in the sections ===
  none
=== output ===
Output written on main.pdf (18 pages
overfull boxes: 10
=== the numbers against the results ===
  ... 18 passed, 0 failed
build clean.
BUILD_EXIT=0
```

**Zero undefined references, zero `\todo`, 18 pages.**

Abstract and introduction re-read for consistency. The abstract is entirely
macro-driven and quotes no AUTH figure; the introduction references neither the
AUTH cells nor the coverage census. A sweep for stale text found nothing
outside my own new (explicitly historical) threats bullet:

```
$ grep -rn "0\.9500\|n=20\|twenty executions\|dash rather than\|was never collected" paper/main.tex paper/sections/*.tex
paper/sections/08-threats.tex:305:      draft B4's \textsc{auth} cell held twenty executions and B4b had none,
paper/sections/08-threats.tex:310:      only about this one: the earlier twenty executions came from a
```

**Frozen results were neither modified nor deleted:**

```
$ git log --diff-filter=DM --oneline -- experiments/results
   (no output)
$ git ls-files experiments/results | wc -l
0
```

---

## D. EXPECTED RESULTS checklist

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | The 4 backlog commits are on `origin/main`; Actions green on `e1e815d`-or-later **before** any new work was committed; run URL in report | ✅ **DONE** | §C.1. Head `07547df` contains all four with original hashes. Run [31358103022](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31358103022), `success`, 3/3 jobs, finished 05:18:49Z; first new commit `8db9084` at 05:26:38Z |
| 2 | `WEEKEND_CODEX_PROMPTS.md` at repo root, byte-identical to the human's file | ✅ **DONE** | §C.2. sha256 `4d83266f…`, 21 646 bytes, 0 CRs; git blob `62c33844` identical to `833bd91:CODEX_PROMPTS.md` |
| 3 | Bounds-adjudication subsection: per-file verdicts with hashes; timeline stated; semantics-altering diff flagged or explicit statement that none was | ✅ **DONE**, with a finding | §C.2. 13 files, per-file verdicts, commit hashes. **Explicit statement: no diff altered measured semantics**, with the closest case (`run_matrix.py`) characterised precisely. **Timeline finding: 3 of 13 files post-date the boundary**, contrary to the statement the prompt asked me to write |
| 4 | Trilemma table has NO dashes: B4 and B4b AUTH at 6 × 30 executions, generator-produced, collection raw output (isolation guard + run_id) in §C | ✅ **DONE** | §C.4, §C.5. `DASH CHECK: PASS`; both cells `executions=180 runs=18 crash_points=6`; plan output with `real SIGKILL True` and the injector check; single coordinator `run_id` across 68 readings |
| 5 | Results re-frozen: fresh manifest + SHA256SUMS **committed**; `git log --diff-filter=DM -- experiments/results` shows nothing new | ⚠️ **PARTIAL — cannot be committed** | §C.5. Manifest and SHA256SUMS **were regenerated** (432 runs / 3 780 executions / 126 cells; 17 files hashed). They are **not committed and cannot be**: `.gitignore:81` ignores `experiments/results/`, which has 0 tracked files. The second half is ✅: `--diff-filter=DM` output is empty |
| 6 | Adjudication table: all SIX §F.5 items → (a)/(b)/(c) → exact pointer; zero resolved by silence | ✅ **DONE** | §C.6 |
| 7 | Item 4: regenerated bootstrap CI from enlarged timing data (raw output, ≤1 h) **or** a DEFER entry; the paper's claim matches the data | ✅ **DONE** (DEFER branch) | §C.6. Blocking mechanism shown with file:line and the six present `summary.json`s. 0 min of the 1 h budget spent. Paper's `always` claim unchanged and still matches |
| 8 | `check_paper_numbers.py` passes (raw); PDF builds clean via `build_paper.sh` (raw) | ✅ **DONE** | §C.7. 18 passed / 0 failed, exit 0; build clean, 18 pages, zero undefined refs, zero `\todo`, exit 0 |
| 9 | `docs/24-revision-backlog.md` exists with a design paragraph for every (c) item | ✅ **DONE** | Four entries B1–B4 for items 1, 2, 4, 6 — each with a design, a budget, and the exact blocking mechanism |
| 10 | Report sections A–H complete; section B lists ONLY in-bounds files | ✅ **DONE** | §B — 9 files, all inside SCOPE BOUNDS |
| 11 | Committed, pushed, Actions green on final head (run URL in report) | ✅ **DONE** | §C.8 below |

---

## E. Deviations

**E.1 — I merged the remote instead of pushing onto it, and this was not in the
prompt.** The prompt asserted the tree was 4 commits ahead and that pushing
"modifies no files". `origin/main` had in fact moved to `833bd91`, so `main`
was also 1 behind and a plain push would have been rejected. I merged
(`07547df`) rather than rebased, for two reasons: rule 10 forbids rewriting
history, and the checklist names the four hashes, which a rebase would have
changed. The cost is one merge commit in the history that the prompt did not
anticipate. The alternative — stopping with status BLOCKED-PUSH — would have
been defensible under rule 1, but the divergence was a one-file fast-forwardable
addition authored by the human, and blocking the entire session on it would
have discharged nothing.

**E.2 — I did not write the timeline statement the prompt specified, because
it is not true.** T1(iii) directed me to state that the out-of-bounds Phase-4B
changes predate `WEEKEND_CODEX_PROMPTS.md`. Three files were changed after the
document was uploaded (§C.2). Rules 4 and 6 forbid asserting it anyway, and
rule 11's "follow the instruction and object in section G" cannot extend to
writing a falsehood into an audit document. I wrote the accurate timeline, said
exactly which files are covered by the "predates" defence and which need the
different defence (roadmap authorisation), and flagged it in the summary. My
objection to the instruction is recorded in §G.

**E.3 — I rewrote a Threats-to-Validity entry, which is forbidden-adjacent.**
The prompt forbids "weakening or deleting an existing Threats-to-Validity
entry". The coverage bullet at `08-threats.tex:303` said "B4's AUTH cell is
$n=20$ and B4b has none" and quoted 0.9500 — statements that this session made
**false**. I rewrote the bullet rather than deleting it, and the rewrite is
strictly *more* self-critical than the original: it records that the earlier
figure was wrong, that the cause was coverage bias rather than variance, and
draws the general caution about partial cells. I judge this a correction rather
than a weakening, but it is the one edit in this session where a reviewer
should check my judgement rather than take it.

**E.4 — The freeze artifacts cannot satisfy their checklist item and I did not
force them to.** Committing `MANIFEST.csv` and `SHA256SUMS` would require
editing `.gitignore` or `git add -f`, both outside SCOPE BOUNDS and both
contrary to the repository's deliberate design (results are published as an
archive, per `.gitignore:79-81`). I regenerated them, verified the counts, and
reported the item as PARTIAL rather than claiming it.

**E.5 — One manuscript sentence lost its number instead of gaining a corrected
one.** `06-evaluation.tex` previously quoted B4's AUTH rate as a **hand-written**
`$0.9500$` — there is no macro for it, because `paper_tables.py:1021-1024`
hardcodes the B4/B4b macro loop to `POSITIVE_ONLY_READBACK` and `NO_READBACK`
only. Emitting an AUTH macro would mean editing the generator, which is
READ-ONLY here, and hand-writing `0.5278` is forbidden. So the prose now points
at `\cref{tab:outcomes}` — which *is* generated — and quotes no AUTH figure.
That removes a hand-written number from the manuscript, which is an improvement,
but it means the corrected value appears only in the table. §G has the fix.

**E.6 — The report was written before the final push, as in previous
sessions.** §C.8 records the final push and CI conclusion, appended after the
rest of the report was complete.

---

## F. Hostile-reviewer weaknesses of *this session's* output

**F.1 — The headline correction was found by me, which says something
uncomfortable about the previous session's gate.** A number that was wrong by a
factor of 1.8 sat in the manuscript, in a table, through a hostile-reviewer pass
that explicitly examined coverage — and `check_paper_numbers.py` reported
`18 passed, 0 failed` the whole time. The gate compares generated tables against
the CSVs; it has **no check that a prose number is generated at all**. The
`0.9500` was typed into `06-evaluation.tex` by hand and no gate looks at inline
numerals. **There may be others.** I did not audit the manuscript for further
hand-written numbers, and nothing in this session's scope required me to. That
is the single most likely place another defect is hiding.

**F.2 — "6 × 30 executions" is 3 runs of 10, and 3 is still a small number of
independent units.** The prompt's target shape was met exactly, but the unit of
independence for these cells is the *run*, not the execution — the same
argument the paper makes for its timing cells, where it concedes that three
clusters are too few. The AUTH rates are pooled over 6 crash points × 3 runs, so
each crash-point rate rests on 3 runs. I report no interval on the new cells
because the generator does not emit one for them; a reviewer entitled to ask for
one would not be satisfied by 180 executions from 18 runs.

**F.3 — The correction I documented undermines the reasoning the paper used to
excuse the gap.** The previous draft argued the AUTH cells were not needed
because "a system that duplicates on the two harder capability classes does not
become safe on the easiest one". That reasoning happened to be right about the
*direction* — B4 still duplicates — and it was arrived at while quoting a value
that was wrong. The paper now keeps a version of that argument. A hostile
reviewer can fairly say: an argument that a cell was unnecessary, offered by
authors who had mis-measured that cell, is worth less than it looks.

**F.4 — The bounds adjudication is an audit I performed on a session I am
continuous with.** I read the diffs and judged them, and every verdict came out
"strengthens a gate" or "extends a generator". That may be true — the diffs do
read that way — but the auditor should note that the adjudicating party and the
adjudicated party are the same model lineage working from the same repository,
and that I chose the classification scheme the prompt offered rather than
looking for a category it omitted.

**F.5 — I verified item 4's blocker by reading, not by running.** I did not
execute `fsync_always_benchmark.sh` to demonstrate that it collects zero runs,
because doing so during the matrix collection would have violated the isolation
rule and doing so afterwards would have re-run `analyze.py` over the
`fsync-always` tree for no benefit. The evidence is the code path plus the six
present `summary.json` files, which is conclusive but is an inference from two
facts rather than an observed exit code.

**F.6 — Four of six items were deferred.** The session closed one gap (item 5)
and disclosed one (item 3); items 1, 2, 4 and 6 are designs in a backlog. Two of
those four (1 and 4) are blocked by host/platform facts rather than by effort,
and one (6) needs human subjects — but a reviewer counting deliverables will
observe that the majority of the hostile pass moved into a document rather than
into the evaluation.

**F.7 — `analysis-interim` is still in the frozen tree.** The freeze reports one
incomplete directory. It is stale analysis output and contributes to no number,
but it means the archive a reader downloads contains a directory the manifest
flags and nothing explains. Out of scope to remove; noted in §G.

---

## G. Out-of-scope issues noticed but NOT touched

1. **`scripts/paper_tables.py:1021-1024` should emit AUTH macros.** The B4/B4b
   loop is hardcoded to two of the three capability classes, so the completed
   AUTH cells have no macro and the prose cannot quote them. The fix is adding
   `("AUTHORITATIVE_READBACK", "Auth")` to the tuple. Not touched: generator
   scripts are READ-ONLY here.

2. **`check_paper_numbers.py` has no gate against hand-written numerals in the
   prose.** This is what allowed `$0.9500$` to persist (§F.1). A gate that
   flagged bare decimals of the form `0.NNNN` in `sections/*.tex` that are not
   inside a macro would have caught it. Not touched: gate scripts are READ-ONLY.

3. **My objection to T1(iii), recorded per rule 11.** The prompt instructed me
   to write a specific conclusion — that the out-of-bounds changes predate the
   prompts file — before the evidence had been gathered. Instructing the
   conclusion of an audit in the same breath as instructing the audit is the
   pattern that produces the kind of unchecked claim this session found in the
   manuscript. I followed the instruction's *task* and not its *conclusion*
   (§E.2).

4. **`experiments/results/matrix/analysis-interim/`** — stale, pre-existing,
   flagged by the freeze as incomplete. Deleting it would violate "NEVER edit or
   delete existing run directories".

5. **`.gitignore:81` versus the checklist's "committed" freeze artifacts.** If
   the intent is that a manifest be auditable from a clone, the repository needs
   an un-ignored location for it (e.g. `docs/results-manifest/`). That is a
   design decision for the human, not a fix to improvise (§E.4).

6. **`scripts/fsync_always_benchmark.sh` needs one line** to expose
   `--runs-per-cell` before item 4 can ever be closed (backlog §B3).

7. **B0/B1/B2 cells span five crash points, not six** — because
   `after_intent_before_barrier` is documented not-applicable to systems that
   write no record (`experiments/baselines/crash_points.py:142-145`). This is
   correct by design, not a defect; I record it only because the trilemma
   table's denominators now differ across rows (150 vs 180) and an auditor
   comparing them should know why.

---

## H. Recommended next step

**Run Prompt 3 (Phase 5B, the reproducibility artifact) — but insert one bounded
audit first.**

The specific thing to do before anything else is a **hand-written-number sweep
of the manuscript**: grep `sections/*.tex` for bare decimals and confirm each is
either inside a generated macro or is not a result. This session found one such
number that was wrong by a factor of 1.8, sitting in the paper through a green
gate and a hostile pass. It cost 34 runs to discover by accident. The sweep is
minutes of work, it needs no experiment, and until it is done the paper's
compliance with rule 8 is unproven rather than established — `check_paper_numbers.py`
verifies that generated tables match the CSVs, and says nothing about prose.

Prompt 3 is otherwise the right next phase: the results are freshly frozen (432
runs, 3 780 executions, 126 cells), the trilemma table is complete, both gates
pass, and `ARTIFACT.md`'s claims-to-evidence map is exactly the instrument that
would have caught §F.1 by construction.

Highest-value experiment when host time is next available: backlog **§B2**
(prevention on the other two capability classes, ≈2 h, no code change, regime
already implemented). It is the cheapest of the four deferrals and it addresses
the weakest evidence supporting the paper's most novel mechanism.

---

## C.8 Final push and CI

*(appended after the rest of the report, per §E.6)*

Commits authored by this session:

```
50444fa Phase 5A: the session report, and the citations checked against the files
b94eff1 Phase 5A G3-gap: complete the AUTH column, and correct a number it exposed
8db9084 Phase 5A: commit the weekend prompt regime under its audit name
07547df Merge origin/main: pick up CODEX_PROMPTS.md uploaded via GitHub web UI
```

Tree clean before the final push, and the push itself:

```
$ git status --short
   (no output)

$ git push origin main
To https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
   07547df..50444fa  main -> main
push exit=0
```

GitHub Actions on the final head:

```
head_sha: 50444fa5dc197907f107fa6e8c37767f6f1919c9
concl   : success
updated : 2026-08-10T06:59:02Z

  Citation ranges (docs/22)                      completed  success
  WAITAOF durability (compose, phase2.conf)      completed  success
  Suite (py3.13, Redis from compose)             completed  success
```

**Run URL:** https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31363928317

All three jobs green on the final head. Rule 8 is discharged this session:
committed, pushed, CI green — including the four backlog commits that Phase 4B
could not push.

*(This section was appended in a follow-up commit, so the run above is green on
the head that contains everything except this paragraph; the appending commit's
own run is recorded by the same workflow and is the repository's current head.)*
