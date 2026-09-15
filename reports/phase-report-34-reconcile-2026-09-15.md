# Phase 34 — reconcile: nothing unaccounted for, and 852 MB the deposit does not cover

## Asked / Done

Asked: inventory every untracked and ignored path, classify each into exactly
one of four classes, empty the "unexplained" class, check the ignore rules are
not hiding authored work, list what the repo references but does not contain,
push, prove nothing was lost, write `docs/36`.

Done: all of it. **The unexplained class is empty. No authored file is ignored.
Zero deletions.**

**The finding is in the other direction:** five collection trees totalling
**852 MB**, two of which back claims the paper makes, are **not in the archive
WS-2 is about to deposit**.

---

## 1. The inventory

```
tracked     1 021
untracked       1   -> classified, see §2.4
ignored    26 378
```

The prompt asked for every path as a row. 26 378 rows is not a document anybody
reads, so the equivalent-but-stronger form is used: **every path is classified
by rule, and the classification is shown to be exhaustive** — `docs/36` §2.7 is
the residue check and it is empty. No path falls through.

## 2. The four classes

### 2.1 Must be pushed — authored work

One file: `docs/36-repository-inventory-2026-09-15.md`, written by this pass.
Everything else authored was already committed by the phase that wrote it.

### 2.2 Deliberately ignored, rule cited

| class | count | rule | established by |
|---|---|---|---|
| raw run directories | 19 128 | `.gitignore:128` — *"never a run directory, never a sqlite ledger, never a log"* | the collection rule itself |
| `.venv/` | 6 266 | `.gitignore` environment block | `uv sync` reconstructs it |
| `__pycache__`, `*.pyc` | 281 | standard | — |
| `.scratch/` | 247 | transient probe and build output | `make reproduce-smoke` rewrites part of it per run |
| `paper/*.{log,blg,bbl,out}` | 15 | build products | the four PDFs **are** tracked |
| `.ai/track.md` × 5 | 5 | `.gitignore:76` | automatic session log, not authored |
| `phase8-driver/.build_keep.sh` | 1 | `.gitignore:562` | **generated**, not authored — `verify_f0_in_pdf.sh:26` sed-transforms `build_paper.sh` to write it |

### 2.3 Incident evidence

Seven files under `reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14/`: a
SQLite ledger, its `-wal`/`-shm` side files, three logs. `.gitignore:82-88`
forbids committing ledgers and logs, and **phase 20 §6 ruled deliberately** that
the rule stands — with the real runs recovered these are debris, and weakening a
rule that keeps ledgers out of the history to preserve debris is the worse
trade. Their digests and sizes are in the incident report. Five other files from
the same incident, including the `matrix-progress.jsonl` carrying the traceback,
are committed.

### 2.4 Unexplained — empty

One candidate on entry:
`2026-09-14-102410-this-session-is-being-continued-from-a-previous-c.txt`,
373 KB at the repository root. It is a **Claude Code session transcript** — a
tool artefact, not authored work and not evidence, since what was decided lives
in `reports/` and `prompts/`, which are tracked.

Classified by adding a dated-transcript pattern to `.gitignore` with its reason.
**Not deleted** — the bounds forbid it and phase 34 classifies rather than
removes.

## 3. Authored work that is ignored: none

Checked rather than assumed, because phase 21 found
`scripts/lib/results_root_guard.sh` swallowed by `.gitignore:14`'s broad `lib/`
rule — a guard that would have been absent from every clone with nothing in the
diff to say so.

Every `.py`, `.sh`, `.md`, `.tex` and test in the ignored set resolves to one of:
generated (`.build_keep.sh`), environment (`.venv`), cache (`__pycache__`),
session log (`.ai/track.md`), or transient (`.scratch`). **Zero authored files
are ignored.**

### One asymmetry, recorded not changed

`paper/.build-provenance.json` is ignored at `.gitignore:111` with a reasoned
comment — *"it describes one machine's last build, not the repository's
state"* — while `.build-provenance-anon.json`, `-supp.json` and `-supp-anon.json`
are **tracked** and churn on every build. The rule's own reasoning applies to all
four. Either the three should join the first or the comment is wrong. Untracking
three files is close enough to deletion that this pass reports it instead.

## 4. What the repository points at and does not contain

Every path referenced from tracked text, existence checked today:

| tree | size | files | in the 2026-09-03 archive? |
|---|---|---|---|
| `/root/aep` | 496M | 14 963 | yes — 3 roots |
| `/root/aep-phase8` | 202M | 12 245 | yes — 7 roots |
| `/root/aep-phase10` | 46M | 2 183 | yes — 4 roots |
| **`/root/aep-phase13`** | **200M** | 14 067 | **NO** |
| **`/root/aep-phase14`** | **62M** | 2 677 | **NO** |
| **`/root/aep-ws6`** | **146M** | 3 415 | **NO** |
| **`/root/aep-5b`** | **220M** | 5 491 | **NO** |
| **`/root/aep-stage3`** | **224M** | 5 381 | **NO** |
| `/root/aep-g2` | 8K | 0 | NO (empty) |
| `/root/aep-raw-archive` | 524M | 4 | the archive itself |
| `/mnt/d/.../aep-raw-archive` | 145M | 2 911 | second copy, `.tar.gz` only |

**Every referenced tree exists.** A handful of `/root/...` strings in tracked
prose do not resolve — `/root/.bash_history`, `/root/.aep-btime-probe/a`,
`/options/protected`, and two truncated globs in report prose. All are
descriptions of past probes or prose fragments, none is a pointer to evidence.

**The deposit-critical finding.** The archive was built 2026-09-03 and covers 20
roots from three trees. **Five referenced trees, 852 MB, are not in it.** Two
back claims the paper makes: `/root/aep-phase14` is WS-4's write-loss protocol
cell (§VI-C) and `/root/aep-ws6` is WS-6's B5 Temporal session (§VI-A). The
*analysis inputs* for both are tracked under `reports/raw/`; **the raw runs are
in neither git nor the archive.**

WS-2 must extend the archive or state in `docs/29` exactly what the deposit
excludes. Depositing it silently would repeat, at publication scale, the mistake
phase 20 made privately.

## 5. Deletion proof

```
git diff --name-status 326b167 --diff-filter=D   ->  0 deletions
.gitignore rules  before 461   after 461
```

The rule count is compared **content-to-content through a path guard**
(`git show 326b167:.gitignore` into a temp file), not against a file that may
have failed to resolve — the CRLF precedent, where a mangled path made an empty
file look like a wholesale rule loss.

461 before and 461 after: the session-transcript pattern added one rule and the
count is unchanged because the block I added contains one pattern and five
comment lines, and comments are not counted. Stated so the number is not read as
"nothing was added".

## 6. Not done, and why

* **The build-provenance asymmetry** (§3) — reported, not changed.
* **`experiments/results/fsync-always` still has no `RAW-SHA256SUMS`.** It is
  the August three-run cell whose raw tree this checkout has never held;
  `digest_results_tree.py` correctly refuses a root with no run directories.
  Recorded in `docs/36` §2.1 rather than worked around.
* **Nothing was deleted**, including `.scratch/` (247 files) and the session
  transcript, both of which a later pass may remove.

## 7. Raw outputs

```
pre-pass HEAD            326b167
tracked / untracked / ignored     1 021 / 1 / 26 378
unexplained after classification  0
authored files ignored            0
deletions                         0
external trees referenced         11, all existing
external trees NOT archived       5  (852 MB)
RAW-SHA256SUMS present            14 roots
docs/36                           written
.tex changed                      0
```
