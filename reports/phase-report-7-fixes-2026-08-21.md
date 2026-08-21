# Phase 7 — the fix pass: findings

**Corrections forward.** This file records findings produced *during* Phase 7's
fix sessions. It does not amend `reports/phase-report-6-audit-2026-08-21.md`;
where Phase 7 found the audit incomplete, that is recorded here as a forward
correction, per rule 10.

**Sessions covered so far:** P7-A (`e59102d`), P7-B commit 1 / T1 (`83cccdc`),
P7-B commit 2 / T2–T4b (`97c44ff`).

**Severity** as in the Phase 6 report: `SUBMIT-BLOCKER` / `MAJOR` / `MINOR`.

---

## F7-1 · MAJOR · PR-1's audit scope was incomplete: the blocker was in three files, and the audit found one

The Phase 6 audit adjudicated PR-1 as its only SUBMIT-BLOCKER and located it at
`paper/main.tex:146`. **A repo-wide sweep run before the fix found the same
false claim in three files, four occurrences:**

| Site | Status when Phase 7 began |
|---|---|
| `paper/main.tex:145` | found by the audit |
| `paper/arxiv-metadata.md:79` (full paste-ready abstract) | **missed** |
| `paper/arxiv-metadata.md:130` (short form) | **missed** |
| `CITATION.cff:16` | **missed** |

`CITATION.cff` claimed a *"432-run evaluation under real SIGKILL, hard Redis
kills and block-level write loss"*. The 432 runs **are** the SIGKILL matrix; the
hard Redis kill is a separate 60-run ablation and the write-loss probe is not a
run of the evaluation at all. All four are corrected in `83cccdc`.

**Why the audit missed them, stated precisely rather than excused.** The audit
established PR-1 by reading `main.tex` and `flakey_write_loss.py` and never
asked *where else the same sentence lives*. Its own §S4.4 adjudication reasoned
about the claim's truth and its severity, and treated its **location** as given.
A claim that is false is false wherever it appears, and the instrument that
finds it must be a sweep, not a reading.

**Six further sites were checked in context and are accurate**, so the sweep
also bounds the problem: `paper/cover-letter-tse.md:53`,
`paper/sections/01-introduction.tex:87` (C3 enumerates the three collected
regimes exactly, and is more careful than the abstract was), `README.md:5`,
`ARTIFACT.md:79` and `:102`, `PAPER_ROADMAP.md:195` and `:211`. Post-fix
re-sweep returns **zero** remaining occurrences.

**Generalisation for future phases:** an adjudicated defect in prose should
close with a repo-wide sweep for its own wording before it is called fixed.
Severity is a property of the claim; **coverage is a property of the search.**

---

## F7-2 · MAJOR · `arxiv-metadata.md` sits outside the numbers discipline, and has produced six defects

### The record

| # | Defect | Found by |
|---|---|---|
| 1 | `"~2 780 characters"` — estimated, wrong | 5C §C.7 |
| 2 | `"~1 870 characters"` — estimated, wrong, and below the real limit | 5C §C.7 |
| 3 | `"2 figures, 9 tables"` — wrong; actually 3 and 12 | 5C §C.7 |
| 4 | Full-form count recorded **3 055**, measured **3 026** — stale by 29 | Phase 7 |
| 5 | Short-form count recorded **1 905**, measured **1 888** — stale by 17 | Phase 7 |
| 6 | Author-block checklist claim describes the pre-`bf68440` state | Phase 7 |

Defects 4 and 5 were measured against `HEAD` **before** any Phase-7 edit, so
they are not artifacts of this session's changes.

Defect 6, new here: `arxiv-metadata.md:172-173` tells the human *"The
manuscript's author block currently reads Anonymous Author(s) while `main.tex`
and §9 carry a GitHub URL naming a personal account."* That contradiction was
closed by `bf68440`. `main.tex:94` now yields `Anonymous Author(s)` in the
anonymous branch and `main.tex:106` yields `Hamza Khan` in the public branch;
each build is internally consistent. The checklist still warns about a defect
that no longer exists — which in a pre-submission checklist is a live hazard,
because it invites a human to "fix" something already correct.

Related and not a defect: the file's note that *"Page count is from the build in
§C.8 of the 5C report"* now points at an 18-page build; the manuscript is
**19 pages**. No page number is asserted in the file, so this is a stale
*pointer*, not a wrong number.

### The structural cause

`scripts/check_paper_numbers.py` regenerates and byte-compares
`paper/generated/*.tex`, and `check_macros_are_used` verifies every generated
macro is used somewhere in `paper/main.tex` and `paper/sections/*.tex`. **Its
reach stops at LaTeX.** `arxiv-metadata.md` is markdown holding *resolved*
values — arXiv's abstract field is plain text and cannot contain macros — so
every number in it is hand-transcribed and nothing checks it. Six defects in a
file that has existed for eleven days is the predictable consequence, not bad
luck.

### Is bringing it inside feasible? **Yes, partly, and cheaply. Recommended.**

Answering rather than leaving open, as instructed.

**What cannot be done simply.** A full check — verifying that the plain-text
abstract is a faithful rendering of `main.tex`'s abstract — needs a
LaTeX→plaintext normaliser (`\emph{}` stripped, em-dash → `--`, `\times` → `x`,
superscripts → `^`, macros resolved). That is real work with real edge cases,
perhaps 100–150 lines plus tests, and it would be brittle against ordinary
prose edits.

**What can be done cheaply, and would have caught five of the six.** A
*counts-only* check needs no rendering at all:

1. Parse the two fenced abstract blocks out of `arxiv-metadata.md`.
2. Recompute each block's character count; compare against the number recorded
   beneath it; fail on mismatch.
3. Fail if the short form exceeds **1 920** (the verified arXiv limit — see F7-3).
4. Recount `\begin{figure` and `\begin{table` across `main.tex`,
   `sections/*.tex` and `generated/*.tex`; compare against the comments field's
   *"N figures, M tables"*; fail on mismatch.

Roughly **40 lines** in `check_paper_numbers.py` plus a test. It would have
caught defects **1, 2, 3, 4 and 5** — everything except the stale prose claim,
which no counter can see.

**Recommendation: implement the counts-only check.** The generator needs to emit
nothing new; the check reads the manuscript and the markdown directly. **Not
implemented in this phase** — it is outside P7's scope and belongs with the
`verify_refs.py` work or its own session.

### Was the rest of the file ever swept? **No — until now.**

Stated plainly because "a swept file with five fixed defects" and "an unswept
file with five known defects" are different claims and the distinction matters.
Before this session **nobody had swept `arxiv-metadata.md` as a whole**; the
five earlier defects were each found incidentally while someone was there for
another reason. This session swept it. Results:

| Claim in the file | Verified against | Result |
|---|---|---|
| *"3 figures, 12 tables"* | 3 `figure` + 12 `table` environments in the manuscript | ✅ correct |
| 15 data numerals in the two abstracts (540, 0.50, 195, 193, 0.37, −1.11, 2.04, 0.3333, 0.9333, 30, 10, 28, 18, 90/90, 0/10) | the corresponding macros in `paper/generated/numbers.tex` | ✅ **0 mismatches** |
| Categories `cs.SE`, `cs.DC` | valid arXiv codes; primary/secondary as stated | ✅ well-formed |
| ACM codes D.2.4, D.4.5, C.2.4 | well-formed CCS codes | ✅ well-formed |
| Two character counts | measured 2026-08-21 | ✗ both stale — **fixed** |
| Author-block checklist claim | `main.tex:94` / `:106` and both builds | ✗ stale — **not yet fixed** |

**The data numerals are sound.** The defects are concentrated entirely in the
file's *self-descriptive* numbers — counts of its own text — which is exactly
the class a counts-only gate closes.

---

## F7-3 · MINOR · the 1 920 limit's provenance had never been checked, in any phase

Phase 7 performed character-level surgery with a handful of characters of
headroom against a number that had never been traced. **No phase, including the
audit, established where 1 920 came from.** It appears in `arxiv-metadata.md`
asserted, and every subsequent session — 5C, the Monday audit, Phase 6 — took
it from there.

**Now verified:**

> *"Keep it short — abstracts longer than 1920 characters will not be accepted;
> abridge your abstract if necessary."*
> — [info.arxiv.org/help/prep.html](https://info.arxiv.org/help/prep.html), read 2026-08-21

**The limit is correct. The counting rule is not stated.** The page gives the
number and no method: whether hard newlines, leading whitespace and line
wrapping count is unspecified. This matters because measurements of the *same
unedited text* differ by method — 1 888 as stored versus 1 886 flowed — and the
number recorded in the file differed from both by 17.

Both counts in `arxiv-metadata.md` are now recorded under the strictest reading
with the method stated alongside, and the unverified counting rule is flagged in
the file. Any headroom below ~20 characters should be treated as unconfirmed.

**The transferable point:** a constraint that governs an edit deserves the same
provenance check as a claim that appears in the paper. This one governed a
SUBMIT-BLOCKER correction and had been inherited unexamined through four phases.

---

## F7-4 · MAJOR · the instrument-failure pattern: five occurrences across four phases

**This is the most transferable thing the audit has produced, and it has been
scattered across four reports as anecdotes. Recorded here as one finding.**

In every case a tool returned a **confident, well-formed, wrong** answer, and in
every case only an **independent second method** exposed it. No instance was
caught by inspecting the tool, reading its code, or trusting its exit status.

| # | Instrument | The confident wrong answer | What exposed it |
|---|---|---|---|
| 1 | `verify_refs.py` | Exit **0** — success | Counting its own output: **14 of 23 lookups had failed** (HTTP 503/500) |
| 2 | `paper/main.log` (S3/S4) | **10 overfull boxes** | The file was untracked and two days stale; a fresh rebuild gave **0** |
| 3 | Leak check, first attempt (P7-B) | **0 identifying strings in `main-anon.pdf`** | It also returned 0 for `main.pdf`, which certainly contains them — no positive control |
| 4 | zlib PDF text extractor (P7-B) | Corrected wording **absent** from both PDFs | `pdftotext` found it; kerning splits strings across `Tj` operators |
| 5 | `grep -c` on flattened text (P7-B) | T4b fixed at **1 of 2** sites | `grep -o \| wc -l` gave **2**; `grep -c` counts matching *lines*, not occurrences |

Instances 3, 4 and 5 were caught **before** they reached a commit. Instances 1
and 2 reached reports — and instance 2 corrupted this audit's own S2.4/S3
evidence path, corrected forward in the Phase 6 report's §S4.8.

### The practice that catches it

**No tool's output becomes evidence until one of these has been done:**

1. **A positive control.** Run the instrument against an input that *must*
   produce a hit. A leak checker that reports "clean" on a file known to contain
   the leak is broken, not reassuring. This single step would have caught
   instances 3 and 4.
2. **A second method with different failure modes.** `pdftotext` versus a
   hand-rolled zlib extractor; `grep -o | wc -l` versus `grep -c`; a fresh build
   versus a build log on disk. Agreement is evidence; disagreement is a defect
   in one of them and must be resolved before either is quoted.
3. **Check what the tool did, not what it returned.** An exit code is a claim
   like any other. `verify_refs.py` exits 0 by construction; the only way to know
   it verified anything is to count what it resolved.

**A green result from an unvalidated instrument is not evidence of success — it
is evidence that the instrument returned green.** The repository already knows
this about its own test suite (`05-implementation.tex` declines to offer the
test count as assurance) and about `verify_refs.py`. The pattern is more general
than either, and it has now cost five occurrences across four phases.

**Cheapest durable mitigation:** where a check is automated, give it a
self-test — the write-loss probe already does exactly this, refusing to report
any Redis trial until it has demonstrated on the bare device that an
`fsync`-before-the-switch survives and an `fsync`-after does not. That pattern,
applied to `verify_refs.py` and to any future metadata gate, is the fix.

---

## Status

| Finding | Severity | Remedy | State |
|---|---|---|---|
| F7-1 | MAJOR | Sweep-then-fix; all four sites corrected | **closed** in `83cccdc` |
| F7-2 | MAJOR | Counts-only gate (~40 lines), recommended not implemented; defect 6 open | **open** |
| F7-3 | MINOR | Limit verified and cited; counting rule flagged unverified in the file | **closed** |
| F7-4 | MAJOR | Positive control or second method before any tool output is quoted | **practice, adopted here** |

*End of Phase 7 findings to date. P7-C (`verify_refs.py`) follows.*
