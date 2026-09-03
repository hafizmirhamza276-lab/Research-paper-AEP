# Phase 11 — Data rescue, gate triage, and host-degradation characterisation

**Date:** 2026-09-03  **Branch:** `main`  **Host:** `KP248`
**Prompt:** `prompts/phase-11-rescue.md` (verbatim, committed `c194dc7` before any other work)
**Direction:** `docs/26-journal-readiness-direction.md` §4 WS-2, §2 A2, §3 rules

---

## Asked

Rescue and triage, not science. Three things:

1. **Build the raw evidence archive first** — every run directory any tracked
   analysis product was derived from, deterministic tar, `MANIFEST.sha256`, and a
   verification that extracting it reproduces the tracked CSVs.
2. **Triage the failing gates** — command, raw output, start commit, manuscript
   impact; fix only what is unambiguous; say how long the repository has been red.
3. **Recover the storage backing retrospectively**, while the host still exists,
   and **characterise the four degradation surfaces** Phase 10 named.

No new claim was collected. Nothing under any raw run directory was modified.

---

## Gate triage

### The state of the gates, before and after

| gate | before this phase | after | changed by |
|---|---|---|---|
| `pytest … --cov-fail-under=90` | 2 failed / 1792 passed (a second run: 3 failed) | **1 failed, 1793 passed, 0 skipped, 0 xpassed, coverage 91.18%** | G2's regeneration removed nothing; **G3 (the barrier flake) did not fire in either of two full runs today** |
| `scripts/check_paper_numbers.py` | 13 passed, 2 failed | **14 passed, 1 failed** | **G2 fixed** |
| `make reproduce-figures` (6 `.tex`) | 1 differs | **all 6 IDENTICAL** | **G2 fixed** |
| `make reproduce-figures` (2 PDFs) | 2 differ | 2 differ | **G4: proved a false positive of the gate, not a moved value** |
| `scripts/validate_citations.py` | 371 citations, 0 invalid | unchanged | — |
| `scripts/verify_measurement_host.py` | passes | `"gates": {"passed": true, "failures": []}` | — |

Two full suite runs were made today, four hours apart, on the same tree. Both
gave **exactly `1 failed, 1793 passed`**, and the one failure was the same test
in both.

### G1 — `tests/test_paper_tables.py` asserts a macro that was deliberately withdrawn

**Command and raw output:**

```
$ uv run --frozen pytest -q -ra --strict-markers --cov=aep_core --cov-fail-under=90
…
        macros = dict(
            (name, value)
            for name, value, *_ in flakey_macros(
                [_payload(60, 60, 60, [_trial()] * 60)]
            )
        )
        # 0/10 lost under a process kill vs 60/60 under write loss.
>       assert macros["FlakeyVsProcessKillP"] == "2.5\\times10^{-12}"
E       KeyError: 'FlakeyVsProcessKillP'
tests/test_paper_tables.py:242: KeyError
=========================== short test summary info ============================
FAILED tests/test_paper_tables.py::test_the_cross_fault_comparison_is_against_the_process_kill_probe
1 failed, 1793 passed, 3 warnings in 265.56s (0:04:25)
```

**Start commit: `9545ccba02252d85bef48b89aceb5caa324bb90b`, 2026-08-31T16:36:40+05:00,
*"Withdraw the flakey probe's two p-values; state the separation instead"*.**

Bisected by **running the test**, not by reading the diff — a git worktree at that
commit and at its parent, the single test executed against each
(`reports/raw/phase11-gate-bisect-stale-macro-test.txt`):

```
withdrawal commit : 9545ccb…  2026-08-31T16:36:40+05:00 Withdraw the flakey probe's two p-values
its parent        : e6ff293…  2026-08-31T16:33:30+05:00 F.0e: the second instance rests on an account

=== e6ff2936832b4a04b79ebdc3dfa6368823d00d79 ===
    1 passed in 0.12s
    -> pytest exit 0
=== 9545ccba02252d85bef48b89aceb5caa324bb90b ===
    E       KeyError: 'FlakeyVsProcessKillP'
    1 failed in 2.73s
    -> pytest exit 1
```

**Three minutes.** The macro was withdrawn at 16:36:40 and the suite was red at
16:36:41. As of this report it has been red for **2 days, 17 hours and 51
minutes.**

**Does it affect a number in the manuscript? No.** The macro is not in the
manuscript; it was withdrawn *because* it should not be, and the reason is in the
implementation, verbatim (`scripts/paper_tables.py:708`):

```
# \FlakeyBarrierP and \FlakeyVsProcessKillP are deliberately NOT emitted.
# Both were Fisher exact two-tailed, and Fisher assumes two independent
# samples. These are not two samples: one_trial() writes an acknowledged
# and an un-acknowledged record in the SAME trial …
```

**This is a CI failure, not merely a local one.** `.github/workflows/ci.yml:145`
runs the full suite. The repository's central credibility claim — CI green, numbers
machine-checked — **has been false since 2026-08-31T16:36:40+05:00.**

**Not fixed. Two options, and the choice is a scientific-record decision:**

* **(a) Delete the test.** Minimal, and loses the pin: nothing would then fail if
  the withdrawal were silently undone.
* **(b) Invert it** — assert `"FlakeyVsProcessKillP" not in macros`, with the
  withdrawal's reasoning as the docstring. Stronger, and it makes the deliberate
  absence itself a tested property, which is this project's own idiom.

(b) is the recommendation. It is not applied, because the prompt's instruction was
"if the fix is not unambiguous, do not guess", and changing what a test *asserts*
about a deliberately withdrawn statistic is a decision about the record.

### G2 — `\HarnessLoc` — **FIXED, and the complete diff is two lines**

Phase 10's *Not done and why* item 1: ADDITION 3 to the Phase 10 prompt required a
harness change, `\HarnessLoc` counts lines of Python under `experiments/`, and
`paper/generated/**` was out of Phase 10's bounds. This phase's step 2 was the
bounded permission to close it.

Regenerated into a scratch directory first and diffed in full before anything
under `paper/` was touched (`reports/raw/phase11-gate-harnessloc-regeneration.txt`):

```
=== COMPLETE diff, paper/generated/ -> fresh regeneration ===
  DIFFERS   numbers.tex
@@ -554,6 +554,6 @@
 \newcommand{\CoreLoc}{6\,862}

 % lines of Python under experiments/, excluding __pycache__
-% 90 files; regenerated on every run of this script
-\newcommand{\HarnessLoc}{23\,022}
+% 91 files; regenerated on every run of this script
+\newcommand{\HarnessLoc}{23\,243}

  IDENTICAL table-ablation.tex
  IDENTICAL table-ambiguity-by-crashpoint.tex
  IDENTICAL table-deployment-choice.tex
  IDENTICAL table-latency.tex
  IDENTICAL table-outcomes.tex

=== anything in paper/generated the regeneration did NOT produce ===
```

Nothing else moved, nothing is missing, and **no measured number changed** — every
generated table is byte-identical. The condition the prompt set ("if it changes
only that macro") is met, so it was applied. The applied diff, from `git diff`, is
the same two lines. Rule 1 is honoured: `scripts/paper_tables.py` wrote the file;
it was not hand-edited.

**Result:** `make reproduce-figures` now reports all six `.tex` files IDENTICAL,
and `check_paper_numbers.py` goes from `13 passed, 2 failed` to **`14 passed,
1 failed`**, with `numbers.tex matches the CSVs` now PASS.

### G3 — the `WAITAOF` barrier flake — **did not fire today, twice**

Phase 10's F2: two suite runs on the same tree failed *different* barrier tests,
all with `WriteAheadWorkflowError: durability barrier failed`, and a 20× repetition
of the most-studied instance failed 5/20 native and 2/20 on Docker Desktop
(Fisher p = 0.41 — not distinguishable).

**Today: two full suite runs, four hours apart, zero barrier failures in either.**
1793 passed both times. This is recorded as an observation, not as a fix: an
intermittent failure that did not occur in two trials is not an intermittent
failure that has gone away. Phase 10's own Wilson interval for the native rate was
**[0.112, 0.469]**, so two clean full-suite runs are entirely consistent with it
still being present.

### G4 — the two analysis figures — **a false positive of the gate, now proved**

**Not a moved plotted value.** `make reproduce-figures` regenerates the two figures
from `$(ARCHIVE)`, which the Makefile defaults to `experiments/results/matrix`
(`Makefile:38`). In this working clone that directory holds an **84-run partial**
— and `analyze.py` can load only 83 of them. The committed figures were made from
the full 432-run tree.

The Makefile's guard is
`if compgen -G "$(ARCHIVE)/*-r0" > /dev/null 2>&1`, which asks *"does ARCHIVE hold
run directories"*, not *"does ARCHIVE hold the collection the committed figures
came from"*. It sees 84 directories, takes the comparison branch instead of
printing `SKIPPED`, and reports a difference.

Phase 11's archive makes this checkable for the first time
(`reports/raw/phase11-gate-figures-from-full-tree.txt`):

```
=== A: paper/figures vs figures regenerated from the ARCHIVED 432-run tree ===
  IDENTICAL figure-1-undetected-vs-ambiguity.pdf (apart from 8 bytes of PDF CreationDate)
  IDENTICAL figure-2-duplicates-by-crash-point.pdf (apart from 8 bytes of PDF CreationDate)

=== B: paper/figures vs figures regenerated from the 84-run repo copy ===
  DIFFERS   figure-1-undetected-vs-ambiguity.pdf: 11726 bytes differ, and not only in the timestamp.
  DIFFERS   figure-2-duplicates-by-crash-point.pdf: 12551 bytes differ, and not only in the timestamp.

=== run counts the two branches see ===
  archived 432 tree    runs= 432 executions= 3780 cells=126
  repo 84 copy         runs=  83 executions=  830 cells=28
```

**11 726 and 12 551 bytes — the exact figures Phase 10 reported.** Same phenomenon,
now explained.

**How long has it been red? Since the figures were first committed — about 27
days.** The committed PDFs were compared against the 84-run partial's output at
every commit that has ever carried them
(`reports/raw/phase11-gate-bisect-figure-pdfs.txt`):

```
=== 118731c  2026-08-07T14:55:14+05:00 Phase 4: matrix closeout -- frozen results ===
    figure-1-undetected-vs-ambiguity.pdf   DIFFERS from the 84-run partial
    figure-2-duplicates-by-crash-point.pdf DIFFERS from the 84-run partial
=== fc2ed65 … b94eff1 … c2fffa6 …  (all four candidates) ===
    … DIFFERS from the 84-run partial, at every one
```

The 84 directories have been in the clone since **2026-08-06T09:18Z** — their
`ctime`s are all within 19 seconds of each other, while their `mtime`s span only
the first three hours of a collection that ran for four days. They are a snapshot
taken mid-collection on day one.

**It has never been green locally, and CI has never run it.** CI runs
`check_paper_numbers.py` and the suite, not `make reproduce-figures`
(`.github/workflows/ci.yml:334`), and CI has no raw run directories at all — they
are gitignored — so even if it ran the target it would take the `SKIPPED` branch.

**Not fixed.** The gate is failing *closed*, which is the safe direction, and two
repairs are possible: default `ARCHIVE` to a path that does not exist so the
branch prints `SKIPPED` honestly, or make the guard require a run count matching
the tracked `coverage.json`. Both change a gate's semantics; neither is forced by
the evidence. Reported, not guessed.

### G5 — `check_paper_numbers.py`: no `.build-provenance.json` — **not fixed, and it cannot be, locally**

```
  FAIL  build artifacts match current sources
        no .build-provenance.json in …/paper; the artifacts there were not
        recorded as produced from any source tree. Run scripts/build_paper.sh,
        or pass --build-dir for a staged build.
  SKIP  2 checks not run (bibliography, undefined references)
```

**This is local-only. CI is not affected:** `.github/workflows/ci.yml:326` runs
`bash scripts/build_paper.sh` before the gate, and `build_paper.sh:227` promotes
`.build-provenance.json` into `paper/`.

**The fix is not available on this machine, and the reason is already recorded** —
`docs/24-revision-backlog.md` B6: this host's TeX Live typesets 24 of the 29
`\bibitem` entries `bibtex` produces, so nine citations render as undefined and a
local build produces a PDF that is not the PDF the paper claims to be. Running
`build_paper.sh` here would write a provenance stamp attesting a broken build,
which is worse than the missing stamp. **Stopped on this item**, as instructed.
B6 already carries the two acceptable fixes and its deadline (before Phase 14).

---

## Archive: contents, manifest digest, verification result

### What was found, including what Phase 10's enumeration missed

Phase 10's storage-backing section was the starting list. A privileged sweep for
`run-config.json` across `/root` and `/mnt/d` found **four things it did not name**:

| found | what it is |
|---|---|
| `/root/phase82-verify/b2-s2` (60 runs) | A Phase-8.2 verification copy. Byte-identical to `experiments/results/b2-s2-2026-08-21` on all 60 run identities. Excluded as a duplicate. |
| `/root/aep/experiments/results/matrix-smoke` (6 runs) | A smoke run of the matrix orchestrator. Excluded. |
| `/root/aep-phase10/VOIDED/…` (18 + 23 runs) | Phase 10's voided wrong-runtime arms. **Included** — the Phase 10 report cites them, and a voided collection is evidence about the instrument. |
| the clone's `experiments/results/matrix` is **not** a subset copy | 84 runs, but they lack the ten per-worker attempt logs each run carries in `/root/aep`, and one run there predates the `redis_kill_point`/`suspend_disabled_declared` schema (`config_digest bda9f386…` against `284e6fb6…`). An older, incomplete snapshot. Excluded. |

### Contents

**20 collection roots, 1 458 run directories, 26 300 files, 492 905 568 bytes.**

```
  matrix                                        432 runs    9410 files
  fsync-always                                    6 runs     112 files
  voided                                          1 runs      24 files
  b2-2026-08-21                                  60 runs     920 files
  b2-s1-2026-08-21                               60 runs     920 files
  b2-s2-2026-08-21                               60 runs     920 files
  b2-s3-2026-08-21                               60 runs     920 files
  b2-paired-s1-2026-08-28                       120 runs    1819 files
  b2-paired-v2-s1-2026-08-28                    120 runs    1821 files
  b2-paired-v2-s2-2026-08-28                    120 runs    1827 files
  b2-paired-v2-s3-2026-08-28                    120 runs    1827 files
  b2-paired-v2-s4-2026-08-28                    120 runs    1827 files
  b2-paired-v2-s2-aborted-2026-08-28             26 runs     406 files
  b2-paired-v2-s2-operator-aborted-2026-08-28    16 runs     178 files
  phase10-replication-ext4-2026-09-02            18 runs     448 files
  phase10-replication-ext4-arbb30-2026-09-02     30 runs     735 files
  phase10-replication-drvfs-2026-09-02           18 runs     451 files
  phase10-replication-drvfs-arbb30-2026-09-02    30 runs     734 files
  phase10-VOIDED-ext4-wrong-runtime              18 runs     446 files
  phase10-VOIDED-ext4-arbb30-wrong-runtime       23 runs     554 files
```

### Digests

```
manifest entries : 26300
payload bytes    : 492,905,568
tar bytes        : 520,396,800
tar.gz bytes     : 24,257,505

MANIFEST.sha256      sha256  87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7
aep-raw-evidence.tar sha256  3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94
aep-raw-evidence.tar.gz      fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353
ARCHIVE-METADATA.json        cf75e7232ad9a97ee989760ca05cda758c67d4da0245a7929ba12706f7a220e5
```

**23 MB compressed.** Cost was never the obstacle; the absence of a verified
manifest was.

**Determinism.** Entries sorted by archive path; `uid`/`gid` zeroed, `uname`/`gname`
emptied, modes normalised to 0644, gzip member `mtime=0`. **File mtimes are
preserved deliberately** — §"Storage backing recovered" below turns on them, and
normalising them would destroy evidence to buy a determinism the sorted-entry rule
already provides.

**Where it is.** Built at `/root/aep-raw-archive` (the distro's ext4). The
compressed archive, the manifest and the metadata are mirrored to
`/mnt/d/personal/AEP/aep-raw-archive` and the copies verified by digest, so the
rescue survives `wsl --unregister`. **Nothing was uploaded.** Publication is WS-2.2.

### Every raw run directory is either in the archive or excluded with a reason

Ten exclusions, each recorded in `ARCHIVE-METADATA.json`: the four duplicate or
superseded copies above, four smoke roots, one harness self-check, and two
`.scratch/reproduce/smoke` trees regenerated by `make reproduce-smoke` on every
invocation.

### Verification: extraction reproduces the tracked analysis products

Extracted to a scratch path, checked against the manifest, then `analyze.py` re-run
over the *extracted* copy — never the source — with each root's own recorded
bootstrap seed and resample count, and the output byte-compared against every
git-tracked file in the corresponding `analysis/` directory.

```
extracting /root/aep-raw-archive/aep-raw-evidence.tar -> /root/aep-archive-verify/extract
  26300 files in 3.3s
checking the extraction against MANIFEST.sha256
  26300 files verified, 0 problems
…
IDENTICAL 114   IDENTICAL-after-normalisation 8   DIFFERS 0   NOT REGENERATED 8
```

**Zero mismatches.** The eight files that reproduce only after normalisation, and
the eight `analyze.py` does not write, are each accounted for below — the prompt
asked for every file that matches and every file that does not, so nothing here is
folded into a total.

**The eight normalised.** Two changes to `experiments/analyze.py` postdate the
frozen products, both declared in the verifier before it ran:

* **`regime-label`** — the crash-always regime is `(session-3)` in products frozen
  on 2026-08-10 and `crashed` in today's `analyze.py:406`. Affects `matrix`'s
  `coverage.json`, `per-cell-metrics.csv` and `per-execution.csv`. **This is Phase
  10's finding F5**, and it is now shown to bite the artifact's own verification.
* **`added-columns`** — `per-execution.csv` has gained `redis_kill_latency_ms` and
  `durability_ack_observed`. Affects `per-execution.csv` in seven roots.

A row-level check confirms the normalisation is not hiding anything: over the 3 780
matrix executions, **0 keys differ and every one of the 17 shared columns agrees on
every row** (`reports/raw/phase11-archive-mismatch-diagnosis.txt`).

**The eight not regenerated.** `container-precondition.json`,
`fault-injection-census.json` and `foreign-load-sample.json` in the Phase-8.4 roots
are written by the collection, not by `analyze.py`. **All eight are in the archive,
with digests byte-identical to the tracked copies.**

**One file needed a different producer, and this is documented rather than
discovered.** `matrix/analysis/comparisons-vs-aep-full.csv` is the only tracked
results file `analyze.py` did not produce — `ARTIFACT.md` §5 records that it was
regenerated regime-labelled by `experiments/rebuild_comparisons.py` in `b9617e4`.
Run through its actual producer over the archive-derived analysis it is
**byte-identical, 12 207 bytes against 12 207**. The verifier now tries both
producers and names which one matched.

### Nothing under any raw run directory was modified

The manifest is the before-state. After building and verifying, every source file
was re-digested against it:

```
$ python3 scripts/build_raw_archive.py --output /root/aep-raw-archive --verify-sources-unchanged
re-digested 26299 source files against /root/aep-raw-archive/MANIFEST.sha256
UNCHANGED: every source file still digests to its manifest value.
```

(26 299, not 26 300: the 26 300th manifest entry is `ARCHIVE-METADATA.json`, which
lives in the output, not in a source tree.)

---

## Storage backing recovered

Full record with verbatim evidence and per-root confidence:
**`docs/28-storage-backing-recovery.md`**. Instrument:
`scripts/recover_storage_backing.py`. Headline results only here.

### Counts across the 20 archived roots

| | DETERMINED | INFERRED | UNDETERMINED |
|---|---|---|---|
| `results_root_filesystem` | 13 | 3 | 4 |
| `redis_storage_backing` (as a recorded field) | 13 | — | 7 |

### The frozen `matrix` collection, which Phase 10 could only call UNDETERMINED

**Its collection path is now DETERMINED, by the collection's own artifact.** A
Python traceback landed in `matrix-progress.jsonl` with absolute paths:

```
"traceback": "Traceback (most recent call last):\n
  File \"/root/aep/experiments/run_matrix.py\", line 862, in execute_plan\n …
```

Fifteen distinct `/root/aep/…` paths appear in that one file. `results_root` is
recorded relative (`"experiments/results/matrix"`), so an absolute path to
`run_matrix.py` fixes the working directory. Corroborated independently:
`ctime == mtime` to the second on **all 432** run configs, so they were written
where they sit rather than copied there.

The **filesystem** is nonetheless recorded as **INFERRED, not DETERMINED** — the
path is `/root/…`, `/` is ext4 today, and the Phase-8 runs' own `environment` block
independently attests `/` as `ext2/ext3` on 2026-08-28, but no step of that is a
field the harness wrote on 2026-08-06. The prompt's rule is not to promote an
inference, including a strong one.

### The four `b2-*-2026-08-21` roots got *worse*, not better

240 runs carrying `\ReplicationPrevented*`. No `environment` block, no absolute
path in any artifact, and:

```
b2-2026-08-21     mtime 2026-08-21T15:11:43Z..15:51:35Z   ctime 2026-09-01T06:46:54Z..06:46:55Z
b2-s1-2026-08-21  mtime 2026-08-21T16:17:13Z..16:52:35Z   ctime 2026-09-01T06:46:55Z
b2-s2-2026-08-21  mtime 2026-08-21T16:55:54Z..17:30:52Z   ctime 2026-09-01T06:46:55Z
b2-s3-2026-08-21  mtime 2026-08-21T17:33:06Z..18:08:06Z   ctime 2026-09-01T06:46:55Z
```

Every one of the 240 inodes was changed at one instant **ten days after the write**,
so where the bytes sit now is not evidence of where they were written. Whether that
was a copy or a metadata change cannot be settled here: a copy creating new
directory entries is ruled out (three of the four parent directories have an
*earlier* mtime than the ctime event), an overwriting `cp -a` is not, and the
discriminator — file birth time — **is not reported by the 9p mount**, measured
directly:

```
--- /root/.aep-btime-probe/a ---     Birth: 2026-09-03 10:53:08 …
--- .scratch/.btime-probe/a ---      Birth: -
```

`reports/phase-report-8-1-0-2026-08-27.md:296-299` states the filesystem for all
four as `drvfs`, in a table. That is recorded and attributed in
`docs/28-storage-backing-recovery.md` §3.4 and **not used to raise the confidence**,
because the report gives no source for the column and the only supporting reasoning
this phase can find is the one the inode event invalidates.

### The finding the recorded field does not, by itself, support

**`redis_storage_backing.source` is byte-identical across the Phase 8 and Phase 10
collections and denotes two different filesystems on two different machines.**
Both record `/var/lib/docker/volumes/aep-phase2_redis-data/_data`. For Phase 10
that is a path in this distro on `/dev/sdd` ext4. For Phase 8 it is a path inside
the `docker-desktop` VM — Phase 10's own pre-change capture records both halves:

```
 Operating System: Docker Desktop
 Name: docker-desktop
 Docker Root Dir: /var/lib/docker
```
```
=== df -T for /var/lib/docker ===
df: /var/lib/docker: No such file or directory
```

`provenance.py` records what `docker inspect` returns and has no way to know whose
filesystem the answer describes. A later comparison keyed on that field would read
the two as sharing a backing.

### Phase 10's §VI finding, restated

Phase 10 listed **12 paragraphs** of `paper/sections/06-evaluation.tex` that put
numbers from different results roots side by side, and reported that in all but one
**both** sides were UNDETERMINED. With the recovery, using Phase 10's macro-to-root
mapping unchanged:

* **Paragraphs still spanning an UNDETERMINED *filesystem*: four** —
  `06-evaluation.tex:406-419`, `421-438`, `440-447`, `462-468`. All four are the
  ones drawing on `b2-*-2026-08-21`. **`462-468` is the paragraph carrying
  `\UnwantedPrevented{}` and the `\ReplicationAepMin`–`Max` range.**
* **Paragraphs spanning an UNDETERMINED *AOF backing*: zero.** Not because it is
  recorded — it is recorded for none of them — but because the *mount type* is
  determined for every quoted root from the pinned `compose.phase2.yml`, which has
  declared `redis-data:/data` as a named volume since `2fefe5e`
  (2026-08-05T18:00:31+05:00), before the first run of any collection, across a
  history of only two commits. Every collection the manuscript compares was served
  by the same named Docker volume inside the same `docker-desktop` VM. That is a
  uniformity, and it is the opposite of what Phase 10 had to assume.
* **The two paragraphs whose backing difference is deliberate — `525-534` and
  `558-568` — are now DETERMINED on both sides.** The write-loss probe's own JSON
  records its stack verbatim: `"dm_table_drop": "0 524288 flakey /dev/loop0 0 0 1 1
  drop_writes"` and a native `redis-server v=7.2.5`, with no Docker in the path.

**No claim is made that any comparison is wrong.** The manuscript was not edited,
nothing was re-analysed, nothing was corrected.

---

## Degradation surfaces and what this host can still measure

Phase 10 named four. **One was re-measured directly and its characterisation
changes materially. Three were not, and that is stated rather than glossed.**

### Surface 4 — wall-versus-monotonic clock divergence. **Episodic, and it is over.**

Phase 10 concluded: *"No timing number can be collected on this host in its current
state."* That is not what the evidence says.

**Measured directly today, twice** (`scripts/…`, raw in `.scratch`/report):

| condition | duration | worst wall − monotonic | shape |
|---|---|---|---|
| idle | 180 s | **−0.017 s** | 0 steps > 0.5 s — smooth |
| under the full suite, real Redis, real `SIGKILL` | 330 s | **−0.051 s** | 0 steps > 0.5 s — smooth |

Forty times *inside* the 2 s E5 tolerance, under exactly the kind of load a
collection imposes.

**And measured per run across all 1 458 archived runs**
(`scripts/clock_divergence_timeline.py`, `reports/raw/phase11-clock-divergence-timeline.json`):

```
root                                           dropped    median     worst  collection window (UTC)
matrix                                          7/432     +0.072 +65559.272  2026-08-06T06:17:35Z .. 2026-08-10T06:41:41Z
fsync-always                                    0/6       +0.051    +0.066  2026-08-07T09:38:47Z .. 2026-08-07T11:08:53Z
voided                                          0/1       +0.289    +0.289  2026-08-07T12:42:03Z
b2-2026-08-21                                   0/60      -0.036    -0.171  2026-08-21T15:11:43Z .. 15:51:35Z
b2-s1-2026-08-21                                0/60      -0.027    -0.069  2026-08-21T16:17:13Z .. 16:52:35Z
b2-s2-2026-08-21                                0/60      -0.015    +0.080  2026-08-21T16:55:54Z .. 17:30:52Z
b2-s3-2026-08-21                                0/60      -0.008    +0.065  2026-08-21T17:33:06Z .. 18:08:06Z
b2-paired-s1-2026-08-28                         0/120     -0.095    -0.326  2026-08-28T04:59:19Z .. 06:21:08Z
b2-paired-v2-s1-2026-08-28                      0/120     -0.094    -0.281  2026-08-28T07:24:37Z .. 08:42:19Z
b2-paired-v2-s2-2026-08-28                      0/120     -0.093    -0.199  2026-08-28T09:46:03Z .. 11:38:53Z
b2-paired-v2-s3-2026-08-28                      0/120     -0.100    -0.205  2026-08-28T11:48:44Z .. 13:06:35Z
b2-paired-v2-s4-2026-08-28                      0/120     -0.096    -0.209  2026-08-28T13:07:23Z .. 14:24:08Z
b2-paired-v2-s2-aborted-2026-08-28              0/26      -0.072    +0.189  2026-08-28T08:59:19Z .. 09:15:10Z
b2-paired-v2-s2-operator-aborted-2026-08-28     0/16      +0.000    -0.146  2026-08-28T09:41:00Z .. 09:44:30Z
phase10-VOIDED-ext4-wrong-runtime              16/18      +4.537    +6.437  2026-09-02T10:42:57Z .. 10:57:37Z
phase10-VOIDED-ext4-arbb30-wrong-runtime       23/23      +6.659   +13.335  2026-09-02T10:58:33Z .. 11:24:45Z
phase10-replication-ext4-2026-09-02            18/18      +6.590   +16.642  2026-09-02T11:30:25Z .. 11:49:49Z
phase10-replication-ext4-arbb30-2026-09-02     29/30      +5.806   +10.899  2026-09-02T11:50:49Z .. 12:21:45Z
phase10-replication-drvfs-2026-09-02           16/18      +6.654    +6.675  2026-09-02T12:23:52Z .. 12:38:27Z
phase10-replication-drvfs-arbb30-2026-09-02    30/30      +6.665   +10.002  2026-09-02T13:10:44Z
```

**The divergence is confined to a single window: 2026-09-02, 10:42Z to 13:10Z, two
and a half hours.** Median divergence per run jumps from ±0.1 s on every prior
collection day to **+4.5 to +6.7 s**, and returns to −0.05 s the next day. It was
present under **both** container runtimes — the two VOIDED roots at 10:42–11:24Z
were served by Docker Desktop — so it is not the runtime change.

**It is not a state, and no reboot fixed it.** `uptime` reports the distro up 20 h
43 m at 2026-09-03T06:18Z, i.e. booted **2026-09-02T09:35Z** — before the divergent
window and continuously since. Same boot, same kernel, same distro instance:
divergent for two and a half hours, clean before and after.

| | |
|---|---|
| **what degraded** | the wall clock ran **ahead** of the monotonic clock by 4.5–6.7 s per ~1-minute run |
| **measurement** | per-run `wall_span − monotonic_span` over the runner's own event records, the quantity `analyze.py:484-493` gates on; plus two direct samplings today |
| **monotonic or intermittent** | **intermittent and episodic** — one 2.5-hour window in four weeks and 1 458 runs |
| **affects fault delivery** | **no.** It corrupts *durations*. Counts are unaffected (`analyze.py:352-362`), which is why Phase 10's replication remains valid. |
| **recoverable** | **it recovered by itself, within one uptime, with no action.** Which also means it can return without warning. |

> **The corrected statement, replacing Phase 10's:** it is not that this host
> cannot produce a timing number. It is that this host produces a timing number
> that is silently wrong for hours at a time, and **the E5 gate is the only thing
> that catches it.** The gate worked: it dropped 132 of the 137 runs collected in
> that window. A collection reporting a high E5 drop rate must be **re-run**, never
> adjusted, and the gate must be read per collection rather than assumed.

### Surface 2 — the `docker kill` landing-latency envelope. **Re-measured; two points, no trend claimed.**

Same instrument as Phase 10 (`scripts/measure_kill_latency.py`, which calls the
harness's own `redis_kill.kill_redis` and reads its `command_ms`), same target (the
real `aep-phase2-redis72`), same n:

| | n | min | median | p95 | max | median 95% CI |
|---|---|---|---|---|---|---|
| Phase 10, 2026-09-02 | 100 | 264 | **317** | 361 | 397 | [312.5, 327.0] |
| Phase 11, 2026-09-03 | 100 | 279 | **341** | 389 | 572 | [336.5, 349.5] |
| historical, Docker Desktop shim (`e1-kill-latency-by-run.csv`) | 300 | 681.8 | **961.8** | — | 1673.9 | — |

The medians' intervals do not overlap: **+24 ms in one day**, and the maximum grew
from 397 ms to 572 ms.

| | |
|---|---|
| **what degraded** | the time from issuing `docker kill -s KILL` to its return |
| **measurement** | the harness's own timing, 100 trials, both days |
| **monotonic or intermittent** | **unknown — two points cannot distinguish them**, and this report will not pretend otherwise. What is established is that the envelope is not stationary at the 24 ms scale over one day. |
| **affects fault delivery** | **yes, directly.** Phase 8.1: AEP-full dispatches iff `WAITAOF` returns before Redis dies, and runs that applied an effect had +194.1 ms higher kill latency (p = 0.00005). A 24 ms shift is small against that; a shift of the size the runtime change produced (199.5 ms) is not. |
| **recoverable** | not applicable — the native runtime already improved it ~3×; the residual variation is the host. |

### Surfaces 1 and 3 — **not re-measured, and here is why**

* **Surface 1, within-session drift whose sign reverses between sessions.** Needs a
  fresh multi-session collection; this phase collects no data. Standing evidence is
  `reports/phase-report-8-5-step-5-run-position-2026-08-31.md:44-53`: the run-position
  coefficient is negative in all four Phase-8.4 sessions (−0.0456, −0.0883, −0.0319,
  −0.0520) with only session 2 exceeding |β/se| = 2, and conditioning on position
  cuts the latency coefficient by up to 54%.
* **Surface 3, kills that do not land.** The count that motivates B1's addendum —
  0 in 360 runs, then 2 in the first 26 of Phase 8.4 session 2 — can only be
  re-measured by collecting `redis-kill-preack` runs. Not done. Today's 100 kills
  all returned and were counted, but `counted` in that probe means the timing was
  usable, **not** that the server was confirmed dead, so it is not evidence about
  non-delivery and is not offered as such.

### What this host can and cannot still support

**Can, at a quality a top-tier venue would accept:**

* **Rate and count collections** — undetected duplicates, lost effects, declared
  ambiguity, recovery success. Counts survive an E5 drop by construction, Phase 10's
  replication reproduced four of five metrics exactly across two filesystems and two
  runtimes, and today's two suite runs and the archive verification all agree.
* **Anything with a per-run integrity gate that fails closed** — the E5 clock gate,
  the `run_id` daemon-identity gate Phase 10 added, the real-`SIGKILL` gate. Surface
  4 is the proof: the instrument was broken for 2.5 hours and the gate caught every
  affected run.
* **The archive-backed reproduction path**, now that a verified archive exists.

**Cannot:**

* **Absolute timing without a per-collection clock audit.** Not because the clock is
  broken now — it agrees to 51 ms today — but because it was wrong by 6 s per run
  for 2.5 hours within a single uptime and recovered unaided. Any timing collection
  must publish its E5 drop rate as a first-class number and be re-run if it is
  non-trivial. `\BarrierCost`-shaped claims are the exposed ones.
* **Anything where the fault delivery *is* the measurement, without a second host.**
  This is B1 and WS-3. Surface 3 is unmeasured and its motivating count (0 → 2) is
  a change in kind; surface 2 is non-stationary at a scale one order below the
  effect Phase 8.1 attributed to the race. **B1's Phase-8.4 addendum stands
  unchanged: a second host is required for B1's fault delivery to be trustworthy at
  all.** Phase 11 found nothing that weakens it.
* **Any claim resting on `b2-*-2026-08-21`'s storage backing being comparable to
  `matrix`'s.** Four §VI paragraphs, including the prevention paragraph.

---

## Not done and why

1. **G1 was not fixed.** The diagnosis is unambiguous; the repair is a choice
   between deleting a test and inverting it, and that is a decision about the
   scientific record. Both options are written out above. **The suite, and therefore
   CI, remains red.**
2. **G4 was not fixed.** The gate fails closed and both repairs change a gate's
   semantics.
3. **G5 cannot be fixed on this machine** — B6. Running `build_paper.sh` locally
   would stamp a build whose bibliography is truncated.
4. **Nothing was uploaded.** No DOI, no tag, no Zenodo deposit. That is WS-2.2 and
   the next phase; this phase produced a verified archive and its manifest, as
   instructed.
5. **The manuscript was not edited and no frozen cell was re-analysed.** The
   storage-backing facts are established only.
6. **Surfaces 1 and 3 were not re-measured** — see above.
7. **`scripts/check_pytest_gates.py` was not run in this phase.** It requires
   `--junit` and `--output`, and the gate script here did not produce a JUnit XML.
   Its specific checks are readable from the suite output regardless: **0 skipped,
   0 xpassed, 1 794 collected.** Its verdict would be red only because of G1.
8. **`.github/workflows/ci.yml` was not touched.** No new environment assertion is
   needed, and the two gate defects found (G4's `ARCHIVE` guard, G1's stale test)
   are repository defects, not CI-configuration defects.
9. **`PAPER_ROADMAP.md` has no Phase 11 row.** Unlike Phase 10, this phase's bounds
   do not list it as in scope, and a status row is an edit to a tracked file
   outside them. It needs one line whenever the next phase touches that file.

---

## Findings outside scope

Recorded, not fixed.

### F1 — the working clone's `experiments/results/matrix` is a stale, partial, mid-collection snapshot

84 run directories, `ctime` 2026-08-06T09:17:56Z–09:18:15Z, `mtime`s spanning only
the first three hours of a four-day collection. They lack the ten per-worker attempt
logs each run carries in `/root/aep`, and
`b4_durable_workflow-after_barrier_before_dispatch-payments-11d6b7e1-r2` there has
no `summary.json`, a shorter `ground_truth.run.jsonl`, and a `run-config.json`
predating the `redis_kill_point`/`suspend_disabled_declared` keys — `config_digest
bda9f386…` against `284e6fb6…` in the authoritative tree.

**This is what makes G4 fire.** It is also `docs/24-revision-backlog.md` B15's
"the raw trees are not consistent across copies, and nothing detects a partial",
now with a named run.

### F2 — the authoritative `matrix` tree's own `analysis/` still holds the banned pooled comparisons file

Running `make reproduce-figures ARCHIVE=<the extracted 432-run tree>` fails
immediately with:

```
comparisons-vs-aep-full.csv has no `regime` column. Re-run experiments.rebuild_comparisons;
pooled comparisons are not a valid paper source.
```

The regime-labelled regeneration recorded in `ARTIFACT.md` §5 was applied to the
repository copy and **not** to `/root/aep/experiments/results/matrix/analysis`. The
raw tree therefore carries a superseded derived product beside its runs. Harmless
for the paper — nothing reads it — but it is in the archive, and a future reader
unpacking the archive and pointing the Makefile at it will hit exactly this.

### F3 — a phase report asserts a filesystem it does not source

`reports/phase-report-8-1-0-2026-08-27.md:296-299` gives a `filesystem` column for
five sessions (`ext4`, then `drvfs` ×4). Phase 11 can find no measurement behind the
`drvfs` entries, and the reasoning that would have supported them is invalidated by
the 2026-09-01 inode event. Not corrected; recorded so that the value is not
recycled as evidence.

### F4 — `analyze.py` clamps the clock divergence at zero, which hides its sign

`analyze.py:493`: `suspension = max(0.0, wall_span - monotonic_span)`. The clamp is
right for the gate — a wall clock running *slow* is not a suspension. But it means
the recorded field cannot distinguish "the clocks agreed" from "the wall clock ran
slow", and the sign is the most informative thing about the mechanism: every
pre-Phase-10 collection sits at a small **negative** divergence and the 2026-09-02
window is strongly **positive**. `scripts/clock_divergence_timeline.py` records the
signed value alongside the clamped one; `analyze.py` was not changed.

### F5 — 9p does not report file birth time, so inode forensics is asymmetric

`statx` returns `Birth:` on ext4 and `Birth: -` on the drvfs mount. Every collection
written to the Windows drive is therefore less recoverable after the fact than one
written to the distro's own filesystem — which is the opposite of the direction the
Phase 10 replication's drvfs arm assumed was symmetric. Not a defect in this
project's code; recorded because it decided a determination in
`docs/28-storage-backing-recovery.md` §3.4.
