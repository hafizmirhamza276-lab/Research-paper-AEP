# Phase 20 — WS-5: accounting for what was destroyed

**Part 1 (below) halted at step 1 for a ruling, as instructed. Part 2, at
the end of this file, is steps 0 and 2–7 after it.** Part 1 is left
exactly as it was written, including its "steps 2–7 are not started".

## Asked / Done

Asked: seven steps — recover-or-confirm-lost (1), a retroactive census from the
archive manifest (2), digests over every pre-WS-5 root (3), correct the
reproducibility claims (4), make R16 enforceable (5), rule on the quarantine
files (6), R15 (7).

Done, in part 1: **step 1 only.** Step 1 carries its own stopping
instruction —

> If they are present, the data is **not lost** and the disposition changes
> entirely — say so plainly and stop at the end of this step for a ruling before
> proceeding.

They are present. Steps 2–7 are not started. §"Not done" says what each now
looks like in light of the answer, because three of them were scoped on the
assumption the data was gone.

---

## 1. Was the data recoverable from the archive? **Yes. Twice over.**

Plainly: **nothing was lost.** Six run directories, 112 files, all present, all
digest-verified, in two independent copies. The deletion happened exactly as the
incident report describes; the consequence it asserted did not.

### The archive is the one `README.md` names

```
$ cd /root/aep-raw-archive && sha256sum MANIFEST.sha256
87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7  MANIFEST.sha256
```

That is `README.md`'s `87fa2d53…` in full. The other three artefacts match
`ARTIFACT.md` §5 exactly:

| artefact | digest | matches ARTIFACT.md |
|---|---|---|
| `aep-raw-evidence.tar` | `3aa90b21…6fbcc94` | ✔ |
| `aep-raw-evidence.tar.gz` | `fec959b5…2ac07353` | ✔ |
| `ARCHIVE-METADATA.json` | `cf75e723…a220e5` | ✔ |

So the archive is not merely *an* archive; it is the verified Phase-11 artefact,
unmodified since 2026-09-03 — eleven days before the deletion.

### It lists the destroyed directories by name

The manifest holds **112** entries under `fsync-always/`, covering all six run
directories. Each run carries **16** files, including `summary.json`,
`events.jsonl` and the per-worker attempt logs:

```
events-recovery.jsonl   events-runner.jsonl   events-worker-0-attempt-1.jsonl
events-worker-1-attempt-1.jsonl   events.jsonl   ground_truth.run.jsonl
ground_truth.sqlite3{,-shm,-wal}   mock-api.log   mock-api.yaml
recovery-stderr.log   recovery-stdout.log   recovery.stop
run-config.json   summary.json
```

### The bytes are present and they verify — in both copies

```
COPY 1  tar -xf aep-raw-evidence.tar fsync-always/
        extracted files: 112    run directories: 6
        sha256sum -c  →  FAILED lines: 0

COPY 2  /root/aep/experiments/results/fsync-always   (dated 2026-08-07)
        files: 112             run directories: 6
        sha256sum -c  →  FAILED lines: 0    MISSING: 0
```

Copy 2 is the tree the archive was *built from* — `build_raw_archive.py:94`
declares `source="/root/aep/experiments/results/fsync-always"`. **The checkout
that was damaged was never the canonical copy.**

### And they back the tracked numbers

```
archived analysis/latency-and-throughput.csv : BYTE-IDENTICAL to the tracked copy
archived analysis/per-execution.csv          : BYTE-IDENTICAL to the tracked copy
/root/aep  analysis/latency-and-throughput.csv : BYTE-IDENTICAL
/root/aep  analysis/per-execution.csv          : BYTE-IDENTICAL
```

So `\BarrierCostAlways`, `\AepAlwaysMedian` (`AEP_FULL,2063.36409`) and
`\BthreeAlwaysMedian` (`B3_INTENT_NO_BARRIER,2048.378017`) **are** recomputable
from raw. ARTIFACT.md §5's existing claim — that `analyze.py` re-run over the
extraction reproduces every tracked analysis file — stands unqualified for this
cell.

### What was searched before, and why it found nothing

The incident report asserted "no archive, no tarball, no WSL copy and no
manifest — all five searched, all five empty". Three searches were actually run:

| search | could it have found the archive? |
|---|---|
| `find . -name "*.tar*"` inside the repo | no — the archive is outside the repo |
| `find /d/personal/AEP -maxdepth 3 -name "*fsync-always*"` | no — wrong name, and the archive is on the ext4 side |
| `ls -d /root/*fsync* /tmp/*fsync*` | no — the directory is `aep-raw-archive` |

**The instrument was a name-matcher; the conclusion was a claim about
existence.** And the answer was inside the repository the whole time:
`ARTIFACT.md` §5 names the archive, its manifest digest, *and*
`/root/aep/experiments/results/fsync-always` as this cell's source. Filed as
`docs/25` **R14 instance 9** — the first instance where the faulty instrument
was not a script but three globs and a universal quantifier.

### What is still true

The deletion was real and the repair to `scripts/fsync_always_benchmark.sh`
stands. So does R16: the script would have done the same to a root with no copy,
and the mechanism is the rule's subject, not the size of the loss it happened to
cause this time.

What the episode actually exposes is narrower and, I think, more useful: **the
recovery came from an artefact this checkout does not contain and never
references by path.** For several hours the loss looked total from inside the
repository, because from inside the repository it *is* total. An off-repository
manifest that the repository never points at protects the data and not the
reader.

---

## 2. Corrections made in this step

Three committed documents asserted the data was unrecoverable. All three are
corrected in place with the chain left visible, per the standing practice:

| file | what changed |
|---|---|
| `experiments/results/fsync-always/RAW-RUNS-DESTROYED.md` | rewritten: the deletion stands, "not recoverable" retracted, both copies tabulated, superseded text kept below the line |
| `reports/incident-fsync-always-raw-destroyed-2026-09-14.md` | correction banner; severity, §1 "What does not", §3's bullet and §5's item 3 corrected and marked; body otherwise unedited |
| `docs/25-collection-tooling-rules.md` R16 | the "not recoverable / unmanifested" claim corrected; the rule itself unchanged; R14 instance 9 added; header count 8 → 9 |

Nothing else was touched. Frozen roots are unmodified: `git status` on
`experiments/results/` shows only the un-ignored `RAW-RUNS-DESTROYED.md`.

---

## 3. Not done, and what the answer changes about it

**Step 2 (the census) is the one step that gets *more* valuable, not less.** It
was scoped as "detect whether anything else is already lost without anyone
knowing" — and step 1 has just demonstrated that a loss can sit undetected and
then be *mis-reported as permanent*, both from the same blind spot. The manifest
is a verified 2026-09-03 snapshot of 26 300 files across 20 roots, and diffing it
against the tree today is still the only instrument that can see backwards. That
argument is unaffected by `fsync-always` turning out fine.

**Step 3 (digests over pre-WS-5 roots)** is unchanged, and its stated limitation
is now demonstrated rather than argued: a digest taken today certifies nothing
about the past, which is exactly why the 2026-09-03 manifest — and not
`digest_results_tree.py` — is what answered step 1.

**Step 4 (correct the reproducibility claims)** changes direction. The prompt
anticipated this: "or, if step 1 recovered them, true by a route that must be
named." `ARTIFACT.md` §5 is **not** false about this cell. What is missing is the
route: neither `ARTIFACT.md` nor `README.md` tells a reader standing in
`experiments/results/fsync-always` where the raw is. And `docs/29`'s new
precondition is *weaker* than the prompt supposed — the archive is not the sole
copy of this cell, `/root/aep` is a second — but the deposit still matters,
because both surviving copies are on **one host**, and that is now a stated fact
rather than an assumption.

**Step 5 (enforce R16)** is unchanged and still required.

**Step 6 (the quarantine files)** is unchanged: they are still in the third
state, untracked and unrecorded.

**Step 7 (R15)** was not run as a full pass. This step changed only Markdown; the
two cheap gates were run and are green (below). The suite was not re-run because
no code changed in this step.

Out of scope and untouched: the paper (**zero `.tex`**), the `always` arm
collection, the class sweep, any re-analysis.

---

## 4. Raw outputs

```
$ sha256sum /root/aep-raw-archive/MANIFEST.sha256
87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7

$ grep -c "  fsync-always/" MANIFEST.sha256
112

COPY 1 (tar extraction)
  extracted files: 112
  run directories: 6
  sha256sum -c fsync.sums | grep -c ': FAILED'   →  0

COPY 2 (/root/aep/experiments/results/fsync-always)
  run directories: 6
  files:           112
  sha256sum -c fsync.sums | grep -c ': FAILED'   →  0
  grep -ci 'No such file'                        →  0

analysis CSVs vs the tracked copies
  latency-and-throughput.csv : BYTE-IDENTICAL   (both copies)
  per-execution.csv          : BYTE-IDENTICAL   (both copies)

AEP_FULL,2063.36409
B3_INTENT_NO_BARRIER,2048.378017

$ python scripts/check_paper_numbers.py   →  33 passed, 0 failed
$ python scripts/validate_citations.py    →  OK: 371 citations, 0 invalid
$ git status --short -- '*.tex' | wc -l   →  0
```

---

## 5. Findings outside scope

1. **Both surviving copies are on the same host.** The archive
   (`/root/aep-raw-archive`) and the canonical tree (`/root/aep`) are both in
   the WSL distro. The Windows-side copy at `/mnt/d/personal/AEP/aep-raw-archive`
   has `MANIFEST.sha256`, `ARCHIVE-METADATA.json` and the **`.tar.gz`** — but
   **not the uncompressed `.tar`**. That is still a second copy of the payload
   and it was not verified in this step. It should be, and it is the thing that
   makes `docs/29`'s deposit urgent rather than ceremonial. Recorded, not acted
   on.
2. **`ARTIFACT.md` §5 and `README.md` describe the archive but never say where
   it is.** `reports/phase-report-11-rescue-2026-09-03.md` §"Where it is" does.
   A reader of the two front-door documents cannot find the raw data that backs
   the paper. This is step 4's substance and is left for the ruling.

---

## 6. Environment

`uv run --frozen --extra dev --extra cov --extra experiments --extra analysis
--extra b5`, CPython 3.13.0, WSL2 6.6.114.1. Read-only against
`/root/aep-raw-archive` and `/root/aep`; the tar was extracted to a scratch path
under `/root/p20-extract`, which is not a results root. No Docker, no Redis, no
collection, no frozen root modified.


---
---

# Phase 20, resumed — steps 0 and 2–7

Step 1 stood and is unchanged above. This part was run after the ruling.

## Step 0 — the `/mnt/d` copy: verified

It holds three of the four artefacts and lacks the uncompressed `.tar`:

```
PRESENT  MANIFEST.sha256          87fa2d53…e2d7   ✔ matches ARTIFACT.md
PRESENT  ARCHIVE-METADATA.json    cf75e723…a220e5 ✔
PRESENT  aep-raw-evidence.tar.gz  fec959b5…07353  ✔
ABSENT   aep-raw-evidence.tar
```

The missing `.tar` costs nothing, and that is shown rather than assumed:

```
$ gunzip -c aep-raw-evidence.tar.gz | sha256sum
3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94   ← the .tar's digest
```

Decompressing it reproduces the `.tar` bit for bit, so the payload is complete.

**File-level verification, all 26 300:**

```
extracted files: 26300
sha256sum -c MANIFEST.sha256  →  OK 26300   FAILED 0   missing 0
fsync-always: 6 run directories, 112 files
```

**What this does and does not change.** It is a third verified copy, on a
different filesystem and a different device — the Windows NTFS volume rather
than the distro's ext4 image — so the cell survives the loss of either
filesystem. It is **not** off-host redundancy: all three copies are on this one
machine, and the prompt's phrase "no longer single-host" overstates what was
established. Single-*filesystem* is what ended. That distinction is the reason
`docs/29` gained a precondition rather than a footnote.

## Step 2 — the backward-looking census

**The instrument, and why it is the only one available.** A digest taken today
certifies what is present today. It says nothing about what was present
yesterday, and *nothing that is run now can ever say anything about yesterday* —
so a loss that already happened is invisible to every forward-looking tool in
this repository. That property is exactly what let the 14 September deletion
look total from the inside. The 2026-09-03 manifest is the one artefact that
predates the question, which is what makes it a census rather than a snapshot.

**Method, and a trap avoided.** Of the 20 archived roots, only **6** were
collected in this checkout; 14 came from `/root/aep`, `/root/aep-phase8` or
`/root/aep-phase10`. Diffing the whole manifest against this checkout would have
reported roughly 17 000 files "missing" that were never here — a census that is
mostly an artefact of where the collections ran, and precisely the kind of
number that gets quoted. Each root is therefore diffed against **its own
recorded `source_path`**, and where that source is is reported beside the count.

### Presence

| root | where | archived | present | **missing** | extra |
|---|---|---|---|---|---|
| matrix | off-checkout | 9410 | 9410 | **0** | 0 |
| fsync-always | off-checkout | 112 | 112 | **0** | 0 |
| voided | off-checkout | 24 | 24 | **0** | 0 |
| b2-2026-08-21 | this checkout | 920 | 920 | **0** | 0 |
| b2-s1-2026-08-21 | this checkout | 920 | 920 | **0** | 0 |
| b2-s2-2026-08-21 | this checkout | 920 | 920 | **0** | 0 |
| b2-s3-2026-08-21 | this checkout | 920 | 920 | **0** | 0 |
| b2-paired-s1-2026-08-28 | off-checkout | 1819 | 1819 | **0** | 0 |
| b2-paired-v2-s1-2026-08-28 | off-checkout | 1821 | 1821 | **0** | 0 |
| b2-paired-v2-s2-2026-08-28 | off-checkout | 1827 | 1827 | **0** | 0 |
| b2-paired-v2-s3-2026-08-28 | off-checkout | 1827 | 1827 | **0** | 0 |
| b2-paired-v2-s4-2026-08-28 | off-checkout | 1827 | 1827 | **0** | 0 |
| b2-paired-v2-s2-aborted-2026-08-28 | off-checkout | 406 | 406 | **0** | 0 |
| b2-paired-v2-s2-operator-aborted-2026-08-28 | off-checkout | 178 | 178 | **0** | 0 |
| phase10-replication-ext4-2026-09-02 | off-checkout | 448 | 448 | **0** | 0 |
| phase10-replication-ext4-arbb30-2026-09-02 | off-checkout | 735 | 735 | **0** | 0 |
| phase10-replication-drvfs-2026-09-02 | this checkout | 451 | 451 | **0** | 0 |
| phase10-replication-drvfs-arbb30-2026-09-02 | this checkout | 734 | 734 | **0** | 0 |
| phase10-VOIDED-ext4-wrong-runtime | off-checkout | 446 | 446 | **0** | 0 |
| phase10-VOIDED-ext4-arbb30-wrong-runtime | off-checkout | 554 | 554 | **0** | 0 |

**Total missing: 0.** No collection other than the recovered `fsync-always` copy
has lost a file since 3 September.

### Integrity, because presence is the weak claim

A file that is present but altered is a loss the presence census cannot see, and
letting "present" stand in for "intact" is the same substitution that produced
R14 instance 9. So all 26 299 entries were re-digested:

```
TOTAL   checked 26299   OK 26287   ALTERED 12   MISSING 0
```

**All 12 are in `matrix/analysis/`. Zero raw run files were altered, in any
root.** And the 12 are explained, not merely tolerated:

* `/root/aep/experiments/results/matrix/analysis/` was regenerated on
  **2026-09-04 16:41** — one day after the freeze. Its `per-execution.csv`
  carries two extra columns, `redis_kill_latency_ms` and
  `durability_ack_observed`, which is one of the two normalisations
  `ARTIFACT.md` §5 already names.
* **Eleven of the twelve: the checkout's tracked copy matches the archive
  exactly.** The drift is in `/root/aep`, not in what the paper reads.
* **The twelfth is `comparisons-vs-aep-full.csv`, and it disagrees three ways** —
  manifest `c2a4cd3d`, `/root/aep` `d21cb08a`, checkout `a5310f3a`. It is
  tracked, so the gate reads it. This is documented: `ARTIFACT.md`'s provenance
  table records the regeneration in `b9617e4` with exactly these two digests as
  "Old" and "New", because the file had pooled three fault regimes in a way
  §VI-A forbids. Its own reproduction command was run verbatim:

  ```
  $ python -m experiments.rebuild_comparisons --analysis … --output /tmp/check.csv
  wrote 78 regime-labelled comparisons
  cmp: BYTE-IDENTICAL to the tracked copy
  sha256: a5310f3abf3cecfe6b82ac58591f4ed6f548bad244c30687cc85e95bc423ee12
  ARTIFACT.md "New digest": a5310f3abf3cecfe6b82ac58591f4ed6f548bad244c30687cc85e95bc423ee12
  ```

**Finding.** The archive's own `matrix/analysis/` is now stale relative to both
the checkout and `/root/aep`, by design in the first case and by drift in the
second. Nothing needs fixing — but the archive's `analysis/` directories should
not be treated as authoritative for any number. The tracked CSVs are. Recorded
here rather than acted on: `ARTIFACT.md` §5 was correct and step 4 was re-scoped
away from editing it.

## Step 3 — forward-looking digests

`digest_results_tree.py` was about to write a `RAW-SHA256SUMS` for the 16
analysis-only roots that contain no run directories. What that produces:

```
$ digest_results_tree.py --results-root <empty root>      # pre-fix
wrote …/RAW-SHA256SUMS  (0 runs, tree e3b0c44298fc1c14...)
exit=0
# COVERAGE. Every file in every run directory …
# runs: 0   files: (one line each, below)
# tree digest: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  --- file lines (non-comment) in it: 0 ---

  and a SECOND, unrelated empty root gets:
/tmp/p20-empty-root/RAW-SHA256SUMS  : # tree digest: e3b0c442…b855
/tmp/p20-empty-root-2/RAW-SHA256SUMS: # tree digest: e3b0c442…b855
```

`e3b0c442…` is the SHA-256 of the empty string. **Every empty root got the same
tree digest, exit 0, and a header declaring coverage.** That is R14's shape
inside the tool built to prevent R16's loss, so it was fixed before it was run:
`NoRunDirectories`, exit **3** (distinct from 2 "not a directory" and 1
"mismatch"), no file written. Rule 13 discharged — 3 new tests failed against
`HEAD`, 16 passed after.

**Written and tracked: 9.**

| root | runs | files | tree digest |
|---|---|---|---|
| b2-2026-08-21 | 60 | 780 | `f4b93ae9517c5b7d…` |
| b2-s1-2026-08-21 | 60 | 780 | `5fd88bb8a8a5a211…` |
| b2-s2-2026-08-21 | 60 | 780 | `c57c4e9ef280bbaf…` |
| b2-s3-2026-08-21 | 60 | 780 | `0e19d42704dc6251…` |
| matrix (the 84-run clone copy) | 84 | 861 | `abd4cebb5dac73f5…` |
| phase10-replication-drvfs-2026-09-02 | 18 | 396 | `48b7956adc920910…` |
| phase10-replication-drvfs-arbb30-2026-09-02 | 30 | 655 | `d34f0b6587c26985…` |
| phase10-replication-ext4-2026-09-02 | 18 | 394 | `8f7ad71e92faefb0…` |
| phase10-replication-ext4-arbb30-2026-09-02 | 30 | 657 | `c81d66e5c7293ae5…` |

All nine `--check` clean immediately: 0 missing, 0 added, 0 changed, tree digest
matches. Each carries, inside itself, the date it binds from and the statement
that it cannot bind any pass that ran earlier.

**Two deliberate exclusions, stated because a silent one reads as coverage.**

* **16 analysis-only roots** are refused, not digested. Their raw runs are in
  `/root/aep*`; a digest here would assert custody this checkout does not have.
* **`smoke`** has 6 run directories and was digested, then the file was
  **deleted and not tracked**: `make reproduce-smoke` rewrites that root on
  every invocation, so a tracked digest would fail `--check` during ordinary
  use. A gate that cries wolf is one people learn to ignore — the tool's own
  docstring makes that argument, and it applies to the tool.

**`matrix` here is the 84-run clone copy**, which `ARCHIVE-METADATA.json`
excluded by name as "an older, incomplete copy". Its digest binds what is in
this checkout. It is not the canonical 432-run root and must not be mistaken
for it — phase 18 declined to repoint anything at it and that still stands.

## Step 4 — the pointer, not a correction

`ARTIFACT.md` §5 was right and is untouched. What was missing was a route from
the front door to the data:

* **`README.md`** gains a table naming all three copies by path — the archive,
  the `/mnt/d` copy and what it lacks, and the collection trees — plus one
  sentence on why the paragraph exists.
* **`docs/29`** gains §0a: every copy is on one machine; all three verified
  clean on 14 September, *which is the exposure and not the reassurance*; and
  the deposit is therefore "the first copy that survives this host, and the
  first one a reader can reach without being told where to look", not the last
  administrative step before a DOI.

## Step 5 — R16 made enforceable

`scripts/results_root_guard.sh`, wired into the scripts that had the defect:

| function | refuses | exit |
|---|---|---|
| `aep_require_explicit_results_root` | an unset **or explicitly empty** root; there is no default, ever | 2 |
| `aep_refuse_nonempty_results_root` | a root that exists and has anything in it | 3 |
| `aep_guarded_rm_results` | any recursive delete of a path that has not opted in | 4 |

The delete guard is **rule 9's marker moved from Redis to the filesystem**. The
harness refuses a Redis that has not advertised `aep:test-instance-marker`
because it kills processes and deletes keys there; a directory about to be
recursively deleted now has to opt in the same way, by containing
`.aep-scratch-results-root`. A frozen results root will never contain one, which
is the point: **the guard cannot be satisfied by accident.** The check is `-f`,
not `-e`, so a directory of that name does not count as consent.

**A second instance of the R16 shape, found while wiring it.**
`scripts/wsl_launch_matrix.sh:13` read
`RESULTS_ROOT="${RESULTS_ROOT:-experiments/results/matrix}"` — defaulting a
*resumable* collection at the frozen 432-run root every outcome rate in the
paper is computed from. Not a delete, but the same property: a compiled-in
default pointing at published data. It now exits 2 with no root set.

`scripts/fsync_always_benchmark.sh` lost the default phase 19 left behind, and
its **usage header** was corrected — the bare invocation it documented is the
command that caused the loss, and it now exits 2.

**Rule 13, watched failing:**

```
OLD (guard removed; NO collection script executed) : 10 failed,  4 passed, 3 deselected
NEW (guard in place)                               :  0 failed, 17 passed
```

The 4 that pass without the guard are the ones that do not depend on it,
chiefly the source assertion that no collection script contains an unguarded
`rm -rf` — which already held, because phase 19 removed the only one.

The 3 deselected are the tests that *invoke* a collection script. Their
evidence is the old source, not an execution:

```
HEAD  fsync_always_benchmark.sh:38  RESULTS_ROOT="${AEP_FSYNC_RESULTS_ROOT:-experiments/results/fsync-always}"
HEAD  wsl_launch_matrix.sh:13       RESULTS_ROOT="${RESULTS_ROOT:-experiments/results/matrix}"
now   fsync_always_benchmark.sh:51  aep_require_explicit_results_root AEP_FSYNC_RESULTS_ROOT || exit $?
now   wsl_launch_matrix.sh:19       aep_require_explicit_results_root RESULTS_ROOT || exit $?
```

**Why they are deselected, and this is the uncomfortable part.** The first
version of this harness did run the old scripts, and the old
`wsl_launch_matrix.sh` did what it is written to do: `nohup`'d a detached
`run_matrix`. **I reproduced R16 inside the harness written to enforce R16**,
hours after filing the rule. It was harmless — the launcher's `cd` target was
an empty pytest tmp directory with no `uv` project, so the child died at once;
`ps` showed no surviving `run_matrix` and nothing held 8098 or 8099, checked
by listing processes rather than by pattern-killing (R1). But it was harmless
by luck of the environment, not by design.

The lesson is narrower than "do not run old code" and worth stating:
**R13 and R16 conflict specifically for scripts that launch something
detached.** A refusal that fires before any side effect is safe to test by
execution — that is why the `fsync` tests run against the *current* script and
are kept. A script whose non-refusing path forks a collection is not safe,
because the failing branch of the test is the launching branch of the script.
For those, the failing-branch evidence has to be the source.

**One test is deliberately a source assertion and says so.** R16's own lesson
is that executing a collection script to test it is how the data was lost, so
the "no unguarded `rm -rf`" check reads the text instead of running it. That
is the weaker kind of check and the right kind here.

**A second near-miss, caught by reading `git status` before committing rather
than after.** The guard was first written to `scripts/lib/`, and
`.gitignore:14` ignores any `lib/`. Committed there it would have been
**absent from every clone**: both collection scripts would have died at their
`source` line and all 17 tests would have failed in CI, with nothing in the
diff to explain why. It was moved to `scripts/` rather than negating a
legitimate broad rule, and `test_the_guard_is_tracked_by_git` now asserts that
`git check-ignore` does not match it. Same shape as everything else in this
pass: the file that protects the data was invisible to the tool everyone
checks.

## Step 6 — the quarantine files: digests recorded, files left untracked

Ruled as directed, and the reasoning is in the incident file beside the digests.
Five of the twelve quarantined files are already committed, including
`matrix-progress.jsonl`, which carries the traceback that is the evidence for
what happened. The other seven — a SQLite ledger, its `-wal`/`-shm` side files
and three logs — are forbidden by `.gitignore:82-88`. With the real runs
recovered, these are debris from a failed collection rather than the last trace
of anything, and weakening a rule that keeps ledgers and logs out of the history
in order to preserve debris is the worse trade. Their SHA-256 digests and sizes
are recorded so they can be identified if ever cited.

The two zero-byte logs both digest to `e3b0c442…` — the same constant that
`digest_results_tree.py` was handing every empty results root. It appears twice
in one pass, in two unrelated places, for the same reason.

## Step 7 — R14b

`docs/25` gains **R14b: an empty result from a name-matching search is not
evidence of absence**, beside R14a. It names the three globs verbatim, the two
paths none of them could reach, and the one-line search that would have beaten
all three:

```sh
grep -rn "fsync-always" ARTIFACT.md README.md docs/
```

The general form: a name-matching search is **sound for positives and unsound
for negatives**. Finding something proves it exists; finding nothing supports
only "not at these paths, under these names" — a statement about the search, not
about the world. The remedy is cheap and is now required: name the paths
searched next to the conclusion, so a reader can see what they could not reach.

## R15, and two acceptance criteria not met as written

```
full suite                       2033 passed, 34 skipped   (2013 before this pass: +3 digest, +17 guard)
check_paper_numbers.py           33 passed, 0 failed
validate_citations.py            OK: 371 citations, 0 invalid
the nine raw digests, --check    0 failing
zero .tex changed                0
```

**"0 skipped" was not met and is not reachable.** The suite skips 34,
unchanged from before this pass — they are pre-existing conditional skips,
not anything this pass introduced or silenced: every one is a Redis integration
test gated on `AEP_PHASE2_REDIS_INTEGRATION=1` with `compose.phase2.yml` up, plus
one gated on a Redis that can prove `WAITAOF` support. Bringing Docker up was
outside this pass. Reporting them rather than
quietly restating the criterion as satisfied.

**"Paper byte-identical to HEAD's build" was not met, and cannot be by this
build.** `scripts/build_paper.sh` pins no `SOURCE_DATE_EPOCH`, so every build
stamps a fresh timestamp and document ID. A rebuild differs from HEAD's PDF in
exactly **80 bytes of 432 930**:

```
CreationDate  HEAD: (D:20260911174053+05'00')    new: (D:20260914163844+05'00')
ModDate       HEAD: (D:20260911174053+05'00')    new: (D:20260914163844+05'00')
/ID           HEAD: [<9823E80B2F36A3B5...          new: [<7DF409663923D6D8...
```

The rest is the stream derived from `/ID`. The content is identical, the sizes
match, and **zero `.tex` changed** — which is the check that actually carries
the claim. The rebuilt PDF was reverted with `git checkout --`, so the tree
holds HEAD's.

*Recorded, not fixed:* the paper build is not reproducible byte-for-byte. No
gate depends on it — `make reproduce-figures` diffs tables, not the PDF — so
this is a latent claim rather than a broken one. Setting `SOURCE_DATE_EPOCH`
would close it and belongs in a pass that touches the build.

## Findings outside scope

1. **`scripts/wsl_launch_matrix.sh:18` uses `pgrep -f 'experiments.run_matrix'`**
   to decide whether a run is already in flight — a pattern match of exactly the
   kind R1 forbids, in a collection script, pre-dating this pass. Recorded, not
   fixed; fixing it means giving that launcher a PID file, which is a change to
   how collections are started and belongs in its own pass.
2. **The archive's `analysis/` directories are stale** relative to the tracked
   copies (step 2). Correct by design for `comparisons-vs-aep-full.csv`; drift
   for the other eleven. No number depends on them, but a future reader
   reproducing "from the archive" should take raw runs from it and analysis
   products from the repository.
3. **`voided`, `b2-paired-*` and the phase-10 ext4 roots have no digest in this
   checkout** because their raw runs live in `/root/aep*`. Those trees are
   unmonitored by anything in this repository. The archive manifest covers them,
   which is how step 2 could check them at all — but that manifest is frozen at
   3 September and will not notice a change made tomorrow.

## Environment

`uv run --frozen --extra dev --extra cov --extra experiments --extra analysis
--extra b5`, CPython 3.13.0, WSL2 6.6.114.1. Archive reads were read-only;
extractions went to `/root/p20-extract` and `/root/p20-mntd-extract`, neither a
results root. No Docker, no Redis, no collection. Rule-13 harnesses ran from
`.scratch/` one level below the repo root, with a sanity check that the copied
test module resolves the real script — the check exists because the first
attempt put it two levels down and every test errored for both versions,
proving nothing, which is phase 19's mistake repeated.
