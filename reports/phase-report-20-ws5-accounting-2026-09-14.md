# Phase 20 — WS-5: accounting for what was destroyed — **step 1 only, halted for a ruling**

## Asked / Done

Asked: seven steps — recover-or-confirm-lost (1), a retroactive census from the
archive manifest (2), digests over every pre-WS-5 root (3), correct the
reproducibility claims (4), make R16 enforceable (5), rule on the quarantine
files (6), R15 (7).

Done: **step 1 only.** Step 1 carries its own stopping instruction —

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
