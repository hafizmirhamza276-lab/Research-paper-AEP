# Phase 35 — the archive extended: every cited cell now inside it

## Asked / Done

Asked: disposition all five trees, verify each before archiving, extend
additively, declare by name whatever cannot be archived, make the four documents
agree, record where the archive lives.

Done: all of it. **Three trees archived into a second archive; two declared by
name.** The 2026-09-03 archive was not reopened and `87fa2d53…` still verifies.

**A correction to phase 34: the 852 MB figure was right about what sat outside
the archive and wrong to imply all of it was evidence. 408 MB was, and is now
archived. 444 MB never was.**

---

## 1. Per-tree disposition

| tree | size | run dirs | backs | disposition |
|---|---|---|---|---|
| `/root/aep-phase14` | 62M | 333 | **§VI-C** write-loss cell; six macros name it by path | **archived** |
| `/root/aep-ws6` | 146M | 280 | **§VI-A** B5 Temporal; every B5 macro | **archived** |
| `/root/aep-phase13` | 200M | 932 | **§VIII**'s replication interval; `docs/31` | **archived** |
| `/root/aep-5b` | 220M | 7 | nothing | **declared** — already excluded by name in 2026-09-03 |
| `/root/aep-stage3` | 224M | **0** | nothing | **declared** — a source checkout, not a collection |

**Phase 13 was ruled on explicitly rather than by omission.** It is not merely
`docs/31` support: `numbers.tex:529-543` derives `\ReplicationSessions` and the
`\ReplicationPrevented*` pair from `phase13-armA-*`, and §VIII quotes that
interval as *"the only session-clustered interval in this paper that excludes
zero"*. It backs a published claim and is archived.

**The two declared trees, and why silence was not available.** `/root/aep-5b`'s
only run directories are `repo/.scratch/reproduce/smoke` — seven runs of
`make reproduce-smoke`, which regenerates them on every invocation, and which
the **2026-09-03 archive already excluded by name with that reason**. Phase 35
does not disturb that ruling; it records that the exclusion already existed.
`/root/aep-stage3` has **zero run directories**: it is `ARTIFACT.md`,
`CHANGELOG.md`, `LICENSE`, briefs and prompts — a checkout, whose code is in git
history. A reader can recompute every number in the manuscript without either.

## 2. Verification, per tree, with the forward-only caveat

Every root was digested as part of the build and then verified by extracting the
finished tar and checking it against its own manifest:

```
extracted files : 18 494
sha256sum -c    : 18 494 OK, 0 FAILED, 0 missing
```

**The caveat, stated per phase 20's precedent and true of all eleven roots:** a
digest taken on 2026-09-15 binds every pass from 2026-09-15 onward and
**certifies nothing about the past**. It does not establish that these trees are
unchanged since the analyses that used them in September. What binds those is
weaker and is already on the record: the tracked `analysis/*.csv` in
`reports/raw/` and `experiments/results/phase13-*/`, which `check_paper_numbers`
regenerates and diffs on every run.

**No tree was found incomplete or drifted**, so there is no repair to have
declined. Two counts worth stating plainly rather than leaving in a log: the
builder reported `0 runs` for the WS-4 and WS-6 roots because its run-directory
detector looks for a `*-r<N>` suffix those roots do not use at top level. The
data is present — **1 332 run directories and 1 269 `summary.json` counted
directly in the extracted tar** — and the `0` is a cosmetic defect in the
builder's summary line, not a gap in the archive.

## 3. The extension, and that it is additive

```
                    roots  run dirs   files      MANIFEST.sha256
2026-09-03             20     1 458  26 300      87fa2d53…e2d7
extension 2026-09-15   11     1 332  18 494      54d1ab0f…3cd5
                                     ------
total                  31     2 790  44 794
```

Extension payload 355 492 262 bytes; `.tar` 375 429 120
(`61ecd2a4…13813e3`); `.tar.gz` 17 563 367 (`6ef11d7c…37eebf1`).

**Additive, and checked three ways:**

* `MANIFEST.sha256` of the original still digests to
  `87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7`, and its
  tar to `3aa90b21…6fbcc94` — the values README and `ARTIFACT.md` have always
  stated.
* The original manifest still has **26 300 entries**.
* **The two manifests share zero paths.** Nothing is archived twice, so there is
  no question of which copy is authoritative.

The original was never reopened: the extension is a separate output directory
built by the same script through a new `--extension` flag selecting a separate
`EXTENSION_ROOTS` table. Voided collections are included — four of them — on the
precedent the original set, that a voided collection is evidence about the
instrument.

## 4. What the deposit will and will not contain

**Will:** both archives, uploaded together and verified **each against its own
manifest**. `docs/29` §0b says so and warns against inventing a combined
manifest at upload time, which would be a new artefact nobody has verified.

**Will not:** `/root/aep-5b` and `/root/aep-stage3`, named in `docs/29` §0b with
what each is and what a reader can still recompute without it.

## 5. Where the archives live, and how many copies

| | filesystem | contents |
|---|---|---|
| `/root/aep-raw-archive` | ext4, `/dev/sdd` | all four artefacts |
| `/mnt/d/personal/AEP/aep-raw-archive` | 9p, `D:\` | manifest, metadata, `.tar.gz` |
| `/root/aep-raw-archive-ext` | ext4, `/dev/sdd` | all four artefacts |
| `/mnt/d/personal/AEP/aep-raw-archive-ext` | 9p, `D:\` | manifest, metadata, `.tar.gz` — **created this pass** |

The extension existed in **one** copy when it was built. It now has two, on two
filesystems, digest-verified after copying. **Both archives remain on one
machine**, which is the exposure `docs/29` §0a already records and which the
deposit is what actually fixes.

## 6. Not done, and why

* **The Zenodo upload**, out of scope by the bounds.
* **The builder's `0 runs` summary line** for roots without a `*-r<N>` suffix.
  It is a reporting defect in a script that has now produced both archives
  correctly; fixing it means touching the archive builder again, and the archives
  are built. Recorded for the pass that next opens that file.
* **No existing archive content was re-hashed**, as required — which also means
  this pass did **not** re-verify the 26 300 original entries file-by-file. It
  verified the manifest digest and the tar digest, which is what "still
  verifies" means here. Phase 20 did the file-by-file pass on the `/mnt/d` copy
  and found 26 300/26 300.

## 7. Raw outputs

```
extension build          EXIT=0, 18 494 manifest entries
extension verify         18 494 OK, 0 FAILED, 0 missing
original MANIFEST        87fa2d53…e2d7   (README's value, unchanged)
original tar             3aa90b21…6fbcc94 (ARTIFACT.md's value, unchanged)
original entries         26 300
manifest path overlap    0
run dirs in extension    1 332 (by *-r<N>), 1 269 summary.json
mirrored to /mnt/d       3 files, all digests matched
documents updated        README.md, ARTIFACT.md §5, docs/29 §0b, docs/36 §4
deletions                0
.tex changed             0
```
