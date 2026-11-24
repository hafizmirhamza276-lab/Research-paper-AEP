# Survey (a) — every ledger on this host is an empty page with its data in an uncheckpointed WAL

**Read-only. No ledger was opened, for reading or writing.** `os.stat` only — no
`sqlite3` import, no file handle on any database. Opening a WAL-mode database is
itself a mutating act: SQLite may checkpoint and truncate the WAL on connect or
close, which would destroy the exact evidence being surveyed.

Proof rather than assertion: the size and mtime of **every** `-wal` and `-shm`
under each tree were captured before and after the walk and compared.

| tree | WAL/SHM files stamped | changed | vanished | appeared |
|---|---|---|---|---|
| `/root/aep-phase8/experiments/results` | 1284 | **0** | 0 | 0 |
| `/root/aep/experiments/results` | 902 | **0** | 0 | 0 |

---

## 1. The Phase 8 collection tree — 13 roots, not 11

**A correction first.** This tree holds **13** result roots. Earlier work in this
task said "all 11 roots" — asserted from memory rather than counted. The number
below is from the listing.

| root | dbs | bare 4096 B | `-wal` | `-shm` | **BARE+WAL** | db MB | wal MB |
|---|---|---|---|---|---|---|---|
| `b2-2026-08-21` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| `b2-paired-s1-2026-08-28` | 120 | 120 | 120 | 120 | **120** | 0.49 | 12.07 |
| `b2-paired-v2-s1-2026-08-28` | 120 | 120 | 120 | 120 | **120** | 0.49 | 12.00 |
| `b2-paired-v2-s2-2026-08-28` | 120 | 120 | 120 | 120 | **120** | 0.49 | 11.90 |
| `b2-paired-v2-s2-aborted-2026-08-28` | 26 | 26 | 26 | 26 | **26** | 0.11 | 2.36 |
| `b2-paired-v2-s2-operator-aborted-2026-08-28` | 16 | 16 | 16 | 16 | **16** | 0.07 | 1.25 |
| `b2-paired-v2-s3-2026-08-28` | 120 | 120 | 120 | 120 | **120** | 0.49 | 11.70 |
| `b2-paired-v2-s4-2026-08-28` | 120 | 120 | 120 | 120 | **120** | 0.49 | 11.97 |
| `b2-s1-2026-08-21` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| `b2-s2-2026-08-21` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| `b2-s3-2026-08-21` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| `fsync-always` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| `matrix` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| **TOTAL** | **642** | **642** | **642** | **642** | **642** | **2.63** | **63.25** |

**BARE+WAL** = the `.sqlite3` is exactly one 4096-byte page *and* its `-wal` is
non-empty: the database file holds no data at all and the ledger lives entirely
in the uncheckpointed WAL.

**642 of 642 — 100%.** Not one database on this tree contains its own data.

### The six roots showing zero are not missing their ledgers

They never held runs. Each contains 8 files and **zero** run directories — they
are the analysis-only roots that arrive with the git clone, exactly as
`.gitignore` intends. "Zero ledgers" here means "no raw runs were ever on this
host under this path", not "the databases are gone".

## 2. Where the manuscript's raw evidence actually is

`matrix` shows 0 above, and `matrix` is the root the manuscript rests on. That
needed settling rather than assuming, so every `ground_truth.sqlite3` under
`/root` was located:

| directory | ledgers |
|---|---|
| `/root/aep-phase8/experiments/results` | 642 |
| **`/root/aep/experiments/results`** | **451** |
| `/root/phase82-verify` | 60 |
| `/root/aep-5b/repo/.scratch/reproduce` | 7 |

**The manuscript's raw runs are in a different clone**, `/root/aep`, not in the
Phase 8 tree:

| root | dirs | run dirs | ledgers | summaries |
|---|---|---|---|---|
| `matrix` | 434 | **432** | **432** | 432 |
| `voided` | | 1 | 1 | 1 |
| `fsync-always` / `matrix-smoke` / `smoke` | | 6 each | 6 each | 6 each |

432 runs and `results/voided/` holding 1 — matching `ARTIFACT.md:239-246`
exactly. The evidence exists and is intact in count.

**And it has the same shape:**

| root | dbs | bare 4096 B | BARE+WAL | db MB | wal MB |
|---|---|---|---|---|---|
| `matrix` | 432 | 432 | **432** | 1.77 | **184.59** |
| `fsync-always` | 6 | 6 | **6** | 0.02 | 2.26 |
| `matrix-smoke` | 6 | 6 | **6** | 0.02 | 1.67 |
| `smoke` | 6 | 6 | **6** | 0.02 | 1.04 |
| `voided` | 1 | 1 | **1** | 0.00 | 0.14 |
| **TOTAL** | **451** | **451** | **451** | **1.85** | **189.70** |

**Across both trees: 1093 ledgers, 1093 bare pages, 1093 non-empty WALs. 100%,
without a single exception.**

For `matrix` specifically: **1.77 MB of `.sqlite3` files against 184.59 MB of
WAL.** The evidence is 104× the size of the files named after it.

### What this means for the Phase 10 archive

This is survey (b)'s hazard, now measured on the tree it actually threatens.
An archive built by copying `*.sqlite3` — the obvious glob, and the one that
matches the filename a reader would look for — would publish **432 empty
4096-byte pages** under a DOI, permanently, while appearing complete. A tool that
opens each ledger to "verify" or "compact" it before archiving could checkpoint
and truncate the WALs, which is worse: it destroys the originals rather than
merely omitting them.

`ARTIFACT.md` specifies the archive's *contents* and nowhere states that these
databases are empty or that the `-wal`/`-shm` triple must travel together. There
is still no archive script; `Makefile:38`'s `ARCHIVE ?=` is an input path.

## 3. `analysis-interim/` — a long-standing disclosed item, not a new finding

**Correction to this document's first version, which framed `analysis-interim/`
as an undisclosed duplicate and filed it with B15a. Both were wrong.**

The measurements stand: `matrix` holds `analysis-interim/` beside `analysis/`
with the same 15 filenames, all 15 differ, it is systematically smaller
(`per-execution.csv` 366334 bytes against 999731), it is three days older
(2026-08-07 against 2026-08-10), and `SHA256SUMS` names none of its files.

**What was wrong is the framing. It is declared, and it was filed twice on
10 August.**

- `experiments/results/matrix/MANIFEST.md:154-158` lists it by name under
  *"Directories without a parsing run log"*, with the stated purpose that "the
  difference between the directory count and the run count is accounted for
  rather than noticed". **`MANIFEST.md` is itself hashed by `SHA256SUMS`**, so
  the disclosure is inside the attested set even though the directory is not.
- `reports/phase-report-5a-2026-08-10.md` **§F.7** records it as stale analysis
  output contributing to no number, and **§G item 4** lists it among issues
  deliberately not touched.
- `reports/phase-report-5b-2026-08-10.md` **item 5** records it again as still
  present.

**Why it is still there is also on the record, and it is a good reason.** Both
filings say removing it would violate the standing rule against editing or
deleting frozen data. It persists because the alternative was worse.

**It is therefore not B15a's shape.** B15a is about duplicate artefacts that
*nothing declares* — the root-level copies of three analysis products, which no
manifest mentions and no policy ranks. This one is declared, ranked and twice
reported. Filing it under B15a would have counted a disclosed, deliberately
retained item as an undetected defect.

**The one residue, and it is already owned.** §F.7 itself notes that the manifest
*flags* the directory under a category — interrupted attempts — that does not
quite describe stale analysis output, so a reader learns a directory is anomalous
without learning what it is. That is a wording point on an existing disclosure,
not a new item, and 5a §G already classes it out of scope.

**Nothing here casts doubt on any published number**, and nothing here is new.

## 4. Verdict

1. **The bare-page-plus-WAL shape is universal on this host**, across both trees,
   both phases, and every root that holds runs: 1093 of 1093.
2. **The manuscript's raw evidence exists**, in `/root/aep`, 432 runs plus 1
   voided, and is unattested by any manifest (B15).
3. **No ledger was opened.** 2186 `-wal`/`-shm` files stamped across both trees;
   zero size or mtime changes.
4. `analysis-interim/` is **not** a new finding. It is disclosed in the hashed
   `MANIFEST.md` and was filed on 10 August in 5A §F.7 and §G-4 and in 5B item 5,
   and retained deliberately because deleting it would edit frozen data. **Not**
   filed with B15a, which concerns duplicates nothing declares.
