# Phase 12 — Close the red gate, prepare the deposit, and open the filesystem hypothesis

**Date:** 2026-09-03  **Branch:** `main`  **Host:** `KP248`
**Prompt:** `prompts/phase-12-gate-doi-filesystem.md` (verbatim, committed
`242ff02` before any work, with the operator's mid-phase correction recorded
verbatim alongside it in `785452a`)

---

## Asked

Three things. **Step 1** — close Gate 1, the stale-macro test, red since
`9545ccb`; choose between deletion and inversion by one criterion — *a gate that
cannot fail is decoration* — and prove the fix by making it fail deliberately.
**Step 2** — publish the archive and mint the DOI. **Step 3** — establish
whether the filesystem hypothesis for the prevention result's between-session
spread is checkable from existing evidence.

**Step 2 was revised mid-phase.** The operator has no Zenodo account and none is
needed: the deposit is to be **prepared for a manual web upload and not
performed**. The correction is recorded verbatim in the prompt file. Steps 1 and
3 became the phase's primary work.

The correction also referred to a leakage-scan specification "in my previous
message". **No such specification is in this session.** Rather than block or
silently substitute, `scripts/scan_archive_for_leakage.py` defines its own
category set and says so in its docstring, its output and the prompt file.

---

## Gate 1: option chosen and why, deliberate-failure proof, why it went unnoticed

### The criterion selected a third option, and it was the more work

The test asserted `macros["FlakeyVsProcessKillP"]`, a macro withdrawn in
`9545ccb` because Fisher's exact test assumes two independent samples and
`one_trial()` writes the acknowledged and unacknowledged record in the **same**
trial. Phase 11 offered two options and deliberately applied neither.

| option | can it fail? | for the reason it was written to catch? |
|---|---|---|
| **(a) delete the test** | **No.** | — |
| **(b) invert it** — assert the macro is absent | Yes, if someone re-emits it | **Only partly.** It would guard a *dead* macro. |
| **(c) invert it *and* re-point it at what replaced it** | Yes, two independent ways | **Yes.** |

The criterion is decisive once you ask what the test was written to catch: that
**the cross-fault comparison is against the process-kill probe, and computed
right.** That claim did not go away when the p-value was withdrawn — it moved.
`06-evaluation.tex:531-534` now makes it descriptively, out of
`\FlakeyPerRepAckSurvived` and `\FlakeyPerRepUnackLost` beside
`\ProcessKillUnackLost`.

**And those two macros had no test at all.** Nor did the guard that produces
them — `paper_tables.py:734`, `if len(per_rep) == 1:`, whose own comment reads
*"Guarded — if the replications ever disagree these do not exist and the
sentence quoting them fails."* Under option (b) the repository would have kept a
gate over a macro nothing emits while the arithmetic behind a live sentence
stayed unguarded. Option (c) was taken.

Two tests now, replacing one:

1. `test_the_cross_fault_comparison_is_stated_as_separation_not_as_a_p_value` —
   pins that `FlakeyVsProcessKillP` and `FlakeyBarrierP` are **absent**, and that
   the figures which replaced them are **present and correct**.
2. `test_the_per_replication_figures_vanish_when_the_replications_disagree` —
   **new**, and the gate that was missing: when replications disagree the pooled
   figures survive (`59/60`, honest about being pooled) and the per-replication
   ones must not be emitted, so no sentence can claim "in every one".

### The deliberate-failure proof

Run on a scratch branch, each break committed, the gate observed, the break
reverted. Full output: `reports/raw/phase12-gate1-deliberate-failure.txt`.

```
########## A. the real commit -- both tests must PASS ##########
2 passed in 0.42s                                              exit=0

########## B. scratch commit 1 -- undo the withdrawal (re-emit FlakeyVsProcessKillP) ##########
  patched: FlakeyVsProcessKillP is emitted again
>       assert "FlakeyVsProcessKillP" not in macros
E       AssertionError: assert 'FlakeyVsProcessKillP' not in {...}
FAILED ...::test_the_cross_fault_comparison_is_stated_as_separation_not_as_a_p_value
1 failed, 1 passed in 2.13s                                    exit=1

########## C. scratch commit 2 -- break the guard (emit per-rep macros unconditionally) ##########
  patched: the disagreement guard is removed; the first replication is quoted
>       assert "FlakeyPerRepAckSurvived" not in disagreeing
E       AssertionError: assert 'FlakeyPerRepAckSurvived' not in {...}
FAILED ...::test_the_per_replication_figures_vanish_when_the_replications_disagree
1 failed, 1 passed in 2.23s                                    exit=1

########## D. back on the real commit -- both tests must PASS again ##########
2 passed in 0.35s                                              exit=0
HEAD is 4e2d6b7 on main
```

Both breaks are the real regressions, not proxies: (B) undoes the withdrawal,
(C) removes the guard. The working tree was clean at D.

### How a red gate went unnoticed for 2 days 18 hours

**Nothing in CI would have surfaced it sooner, because CI itself was the thing
that was red.** `.github/workflows/ci.yml:145` runs the full suite; the suite
failed from `9545ccb` (2026-08-31T16:36:40+05:00) onward. The signal existed and
was correct.

What was missing is that **nobody was reading it.** Three contributing
conditions, stated because the question was asked:

1. **`9545ccb` was one of nine commits to `paper_tables.py` within three hours**
   that afternoon (14:44Z to 17:19Z). A red run inside a rapid sequence reads as
   "the sequence is in progress".
2. **The phases that followed did not run the suite as a gate.** Phase 10 ran it
   and *reported* the failure — its F1 — but as a finding outside its scope, with
   its bounds forbidding the fix. Phase 11 reported it again with a proven start
   commit and, again correctly, did not fix it. The finding was recorded twice
   and closed neither time. That is the bounds discipline working as designed and
   costing two days.
3. **`gh` is not installed on this host**, so no phase could see CI's verdict
   directly; each re-derived it locally instead.

**No new gate is proposed** — the prompt said to answer the question, not to
build something. The honest answer is that this was a *process* gap, not an
instrumentation gap: the gate fired, correctly, for 2 days and 18 hours, into a
workflow whose bounds prevented three consecutive phases from acting on it.

### Acceptance: every gate green on one commit

All on `4e2d6b7` (and re-run on the current tree after the §IX edits). Raw:
`reports/raw/phase12-acceptance-gates.txt`,
`reports/raw/phase12-reproduce-figures-documented-archive.txt`.

| gate | result |
|---|---|
| `pytest … --cov-fail-under=90` | **1795 passed, 0 failed**, 3 warnings |
| `check_pytest_gates.py` | **OK: 1795 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed** |
| coverage | **91.18%** on `aep_core` (`TOTAL 2528 223 91%`) |
| `validate_citations.py` | **371 citations, 0 invalid** |
| `scripts/build_paper.sh` | **exit 0**, 18 passed / 0 failed, "build clean" |
| `check_paper_numbers.py` | **19 passed, 0 failed** |
| `make reproduce-figures ARCHIVE=<432-run tree>` | **exit 0**, all 6 `.tex` IDENTICAL, both PDFs IDENTICAL apart from the CreationDate |

**Two long-standing failures closed as a side effect, and both deserve saying
plainly.**

**B6 no longer reproduces.** `docs/24-revision-backlog.md` B6 records that this
host's TeX Live typeset 24 of 29 `\bibitem` entries, leaving nine citations
undefined, so `build_paper.sh` could not complete locally and
`check_paper_numbers.py` failed its `build artifacts match current sources`
check for want of a `.build-provenance.json`. **It now builds clean**: 21 pages,
zero undefined references, both the public and anonymous PDFs. B6's deadline was
"before Phase 14"; it should be re-verified rather than closed on one build, but
it did not reproduce today.

**Phase 11's G4 is confirmed as a gate defect, not a moved value.** With the
documented `ARCHIVE=<unpacked matrix>` the two analysis figures are byte-identical
to what is committed apart from 7–8 bytes of PDF `CreationDate`. The default
`ARCHIVE=experiments/results/matrix` still reports them as differing because that
directory holds an 84-run mid-collection partial. **`Makefile` is not in this
phase's bounds**, so the guard was not changed; the defect stands as Phase 11
recorded it, now with the passing invocation demonstrated end to end.

---

## Archive publication: prepared, not performed

### The leakage scan — verdict and recommendation

`scripts/scan_archive_for_leakage.py`, all 26 300 files, 493 MB, twelve
categories. Raw: `reports/raw/phase12-leakage-scan.{txt,json}`.

| category | files | occurrences | reviewer-visible | docs28 load-bearing | distinct values |
|---|---|---|---|---|---|
| **credential / key / token / password** | **0** | 0 | 0 | 0 | — |
| **email address** | **0** | 0 | 0 | 0 | — |
| **OS / account name** | **0** | 0 | 0 | 0 | — |
| **`C:\Users\<name>`** | **0** | 0 | 0 | 0 | — |
| **MAC address** | **0** | 0 | 0 | 0 | — |
| **GitHub handle / URL** | **0** | 0 | 0 | 0 | — |
| **environment dump** | **0** | 0 | 0 | 0 | — |
| hostname | 9 | 17 | 1 | 0 | 1 — `KP248` |
| Windows drive path | 153 | 162 | 49 | 0 | 1 — `D:\134` (the 9p device name) |
| WSL absolute path | 549 | 2 079 | 190 | **11** | 200+ — `/root/aep/…` |
| drvfs path | 568 | 1 373 | 190 | **4** | 44 — `/mnt/d/personal/AEP/…` |
| "non-loopback IP" | 3 717 | 5 263 | 818 | 19 | **1 — `6.6.114.1`** |

**The IP category is a false positive and would have been reported as 3 717
files of leaked IP addresses had the scan not printed distinct values.** The one
distinct match is the kernel version. The first run of this scan reported the
count without the values; showing distinct values was added for exactly this
reason, and is noted in the script.

**Removing anything breaks a digest** — every file is covered by
`MANIFEST.sha256` and by the tar's own digest, so any edit invalidates both and
requires a full rebuild and re-verification of the archive.

> ### Recommendation: **publish as-is, with the residue disclosed in the deposit description.**
>
> 1. **There is no personal identifier in the archive.** No email, no account
>    name, no handle, no credential, no hardware address. What is present is a
>    machine name and a directory layout — they identify a computer and a folder,
>    not a person.
> 2. **11 of the affected files are load-bearing evidence.**
>    `docs/28-storage-backing-recovery.md` §3.1 determines the frozen
>    evaluation's collection path from `/root/aep/experiments/run_matrix.py`
>    appearing in a traceback the collection itself logged. Redacting it would
>    delete the only evidence a determination the project relies on rests on —
>    stripping identity the artifact does not contain, at the cost of provenance
>    it does.
> 3. **Anonymity is handled at the citation, not in the data.** The deposit is
>    made under the author's own name and licence; the review-anonymity problem
>    is solved by the manuscript not citing it in the anonymous build, which is
>    implemented below.
>
> The description in `docs/29-archive-deposit.md` §3 states the hostname and the
> paths explicitly and says why they are retained. **Nothing was stripped. The
> decision is the operator's.**

### The anonymity question, resolved and implemented

A Zenodo record names its depositor, so under double-anonymous review a DOI
defeats the anonymisation exactly as the GitHub URL did. It gets **the same
treatment, in the same block, for the same reason** — the pattern
`paper/main.tex` already established for `\artifacturl` / `\artifactavail`.

**The DOI is defined in exactly one place:**

> **`paper/main.tex:99` — `\newcommand{\archivedoi}{PENDING}`**

Everything derives from it:

| build | renders |
|---|---|
| **anonymous** | `available via the submission system` — **this branch never reads `\archivedoi`**, so a DOI cannot leak into `main-anon.pdf` even if one is inserted |
| **public, DOI pending** | `prepared and verified but not yet deposited; no DOI exists at the time of writing` |
| **public, DOI present** | `deposited at https://doi.org/<doi>` |

Verified on the built PDFs:

```
anonymous PDF, artifact sentence:
  available via the submission system
  available via the submission system
anonymous PDF mentions doi.org: 1     <- prose in IX: "resolved through doi.org"
anonymous PDF mentions the author: 0
public PDF, archive sentence:
  not yet deposited
```

`ARTIFACT.md` §5, `CITATION.cff`, `README.md` and `paper/arxiv-metadata.md` each
now state the archive as assembled-and-verified-but-not-deposited, carry the
manifest digest, and point at the checklist. `arxiv-metadata.md` additionally
records that the DOI must be withheld if the metadata accompanies an anonymous
submission.

### `docs/29-archive-deposit.md` — the hand checklist

Files and digests; sandbox-first with a six-item render check; every metadata
field's exact value including a copy-pasteable HTML description carrying the
manifest digest **and both declared normalisations**; the two DOIs to record;
the one-line insertion point; and the post-upload verification.

### `scripts/verify_published_archive.py` — tested, with one half untested and named

Takes a DOI or URL, resolves it through the Zenodo record API, downloads,
verifies both digests, extracts, checks all 26 300 files against the manifest,
re-derives and byte-compares. Local-path result:

```
=== 2. digests against what the repository expects ===
  aep-raw-evidence.tar.gz    MATCH    fec959b5...
  MANIFEST.sha256            MATCH    87fa2d53...
=== 3. extract and check every file against the manifest ===
  extracted 26,300 files
  26,300 files verified against the manifest, 0 problems
=== 4. re-derive and byte-compare against the tracked products ===
  IDENTICAL 114   IDENTICAL-after-normalisation 8   DIFFERS 0   NOT REGENERATED 8
  compared 122 tracked analysis files
VERIFIED: ...
```

**Only the fetch-by-DOI half is untested**, because there is nothing to fetch.

> **A defect in this script was found and fixed by testing it.** Its first run
> reported `IDENTICAL 0 … DIFFERS 0` and then printed `VERIFIED`. It had passed
> the wrong scratch directory to `verify_raw_archive.py`, which compared nothing
> — and the success test was `if "DIFFERS 0" not in stdout`, which is true of a
> run that did nothing. It now parses the counts and **fails when zero files were
> compared**, on the ground that a zero difference count over zero comparisons is
> not a pass. Recorded because it is the phase's own criterion applied to the
> phase's own work.

### The CI job: route taken, and why

**Route B — left out of CI entirely, recorded as pending in `ARTIFACT.md` §5.**

Not because the gate cannot express a skip: a GitHub Actions job takes an `if:`,
and `check_pytest_gates.py`'s zero-skipped rule governs *pytest*, not Actions
jobs, so a conditional job would not have weakened it. Route B was taken on the
prompt's own criterion. With no DOI there is nothing to fetch, so any job added
now could only pass without checking anything — the definition of decoration —
and a green tick beside "Published archive" while nothing is verified is worse
than a visible gap.

The job's YAML is written out in `docs/29-archive-deposit.md` §5, together with
the deliberate-failure test it must be subjected to before it is trusted
(change one character of the expected digest; confirm red).

### The tag

**`v1.0.0` was not created.** It should go on **the commit that inserts the
DOI**, not on an earlier one: a release tag should mark a tree whose
`ARTIFACT.md` truthfully names the deposit.

The archive corresponds to the raw run directories, which no commit changes, and
its recorded `repository_head` is `c194dc7`. That is not a constraint on the tag:
`git diff c194dc7..HEAD -- experiments/results/` is empty, so the tracked
analysis products the archive reproduces are byte-identical from `c194dc7`
through today.

---

## Filesystem hypothesis: cross-tabulation, checkability, verdict

Full document, with the calibration and the method:
**`reports/phase-report-12-filesystem-hypothesis-2026-09-03.md`**. Summary only
here.

**It is checkable, and the evidence is the collections' own event logs.** Phase
8.1 measured `EventLog.emit` at 5.4 µs on ext4 and 229.7 µs on drvfs — ~40×,
paid once per record inside the runs. `scripts/filesystem_fingerprint.py` reads
the low quantiles of inter-record `monotonic_ns` gaps and recovers that signature.

Calibrated on Phase 10's two arms — same cell, same day, same host, filesystem
recorded in every run config — it **separates at root level**: every ext4 root
below 57.7 µs, every drvfs root above 214.0 µs. It does **not** separate at run
level, which is stated in the output and bounds every verdict to a collection.
**Held-out validation: 5/5** — the five Phase-8.4 roots whose filesystem *is*
recorded are all classified correctly by a threshold that never saw them.

The four `b2-*-2026-08-21` sessions — **UNDETERMINED** in
`docs/28-storage-backing-recovery.md` — come out **drvfs** at 386–473 µs, against
79–110 µs for the same regime on ext4. Recorded as **INFERRED, not DETERMINED**:
it passes through a calibrated classifier and date, harness version and host load
are not held fixed.

| session | fs | AEP | B3 | kill latency (n / median ms) | append p05 µs |
|---|---|---|---|---|---|
| `matrix` (the paper's cell) | ext4 | **10**/30 | 28/30 | not recorded | 38.8 |
| `b2-2026-08-21` | drvfs | **20**/30 | 28/30 | not recorded | 472.7 |
| `b2-s1-2026-08-21` | drvfs | **12**/30 | 28/30 | not recorded | 397.2 |
| `b2-s2-2026-08-21` | drvfs | **4**/30 | 28/30 | not recorded | 392.2 |
| `b2-s3-2026-08-21` | drvfs | **7**/30 | 28/30 | not recorded | 386.5 |
| `b2-paired-s1-2026-08-28` | ext4 | **13**/30 | 28/30 | 120 / 1138.8 | 109.8 |
| `b2-paired-v2-s1` | ext4 | **18**/30 | 28/30 | 120 / 1046.7 | 90.3 |
| `b2-paired-v2-s2` | ext4 | **18**/30 | 28/30 | 120 / 1096.4 | 94.0 |
| `b2-paired-v2-s3` | ext4 | **10**/30 | 28/30 | 120 / 1053.5 | 94.5 |
| `b2-paired-v2-s4` | ext4 | **12**/30 | 28/30 | 120 / 976.8 | 78.8 |

**B3 is 28/30 in all ten sessions** — an invariant across both filesystems, four
weeks and two container runtimes. Whatever moves AEP-full's count acts through
the barrier.

```
drvfs  n=4  [4, 7, 12, 20]              range  4-20  median  9.5
ext4   n=6  [10, 10, 12, 13, 18, 18]    range 10-18  median 12.5
ranges OVERLAP
```

> ### Verdict
> **The filesystems do vary — 4 drvfs against 6 ext4 — and the variation does not
> align with the counts.** The drvfs range *contains* the ext4 range, the medians
> differ by 3 points against within-group spreads of 16 and 8, and the direction
> is opposite to the naive prediction. Decisively: **the spread survives inside
> the ext4 group, where the filesystem is constant and DETERMINED from recorded
> fields** — six sessions, all ext4, still 10–18/30. That does not depend on the
> fingerprint being right.
>
> The hypothesis is **not refuted but demoted**: the filesystem cannot be the
> whole explanation and is not visibly part of one. Reported as an observation
> with its n — **4 against 6** — not as a test. No causal claim either way.

**One correction to the prompt's premise, recorded not applied silently.** The
prompt names the five sessions as "the original `b2-2026-08-21` cell and the four
`b2-paired-v2-*` replications". The 4–20/30 spread it refers to is a different
set — `matrix`'s 2026-08-07 cell plus the four `b2-*-2026-08-21` sessions
(10, 20, 12, 4, 7), per `reports/phase-report-8-1-0-2026-08-27.md:294-299`. All
ten are tabulated, which is what makes the verdict answerable: the prompt's
grouping has five ext4 sessions and one unknown, and could not have shown that
the spread survives with the filesystem held fixed.

---

## Not done and why

1. **Nothing was uploaded and no DOI exists.** That is the revised step 2.
2. **`v1.0.0` was not tagged** — it belongs on the DOI commit.
3. **No CI job was added** — route B above.
4. **The `Makefile`'s `ARCHIVE` guard was not fixed** (Phase 11's G4). Not in
   this phase's bounds; the passing invocation is demonstrated instead.
5. **`docs/28-storage-backing-recovery.md` was not amended** with the fingerprint
   result. It is a Phase 11 document and `docs/` is in scope for *new* files
   only; the upgrade from UNDETERMINED to INFERRED-drvfs is recorded in the
   filesystem-hypothesis document, which cites it.
6. **B6 was not closed**, only observed not to reproduce. One clean build is not
   a fix for an intermittent typesetting failure; its "before Phase 14" deadline
   stands.
7. **`PAPER_ROADMAP.md` has no Phase 12 row** — not in this phase's bounds, as in
   Phase 11.

---

## Findings outside scope

### F1 — the leakage scan's own first version would have produced a false alarm

Reporting 3 717 files of "non-loopback IP" without showing that the single
distinct value was `6.6.114.1` would have been a scan result no one could audit
and that a cautious reader would have acted on. Fixed within the phase by
recording distinct values; recorded here because the same shape — a count
without its values — is a general risk in any scanner, and this repository now
contains one.

### F2 — `paper/main-anon.pdf` and `paper/main.pdf` are tracked binaries that every build churns

Both are rebuilt by `scripts/build_paper.sh` and both are tracked, so any phase
that runs the build to satisfy `check_paper_numbers.py`'s provenance check
necessarily commits two changed PDFs. The provenance stamp itself
(`paper/.build-provenance.json`) is gitignored, so the *evidence* that the PDFs
match their sources is not tracked while the PDFs are. Not changed here; noted
because it makes "which commit's PDF is the submission PDF" harder to answer
than it should be.

### F3 — five sessions record `redis_kill_latency_ms` and five do not

The column was added to `per-execution.csv` after the earlier collections were
frozen. Its absence is "not recorded", never "zero" — so no comparison of kill
latency can span the 2026-08-21 and 2026-08-28 groups, and the cross-tabulation
above leaves those cells blank rather than imputing them. This is the same shape
as Phase 10's finding F5 (a schema change that silently changes what a join
returns) and is the reason ADDITION 3 to the Phase 10 prompt required the field
from that point onward.
