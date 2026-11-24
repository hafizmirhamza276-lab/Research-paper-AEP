# Corrections applied to `reports/audit-pack.md` — 2026-09-24

**This is the working paper behind the pack edits.** Every correction below has
been applied to `reports/audit-pack.md` in the same commit as this file.

**Nothing under `paper/` was changed.** `paper/` was read — including
`pdftotext` on the built PDFs, which is how three of these findings are
evidenced — and not written. No PDF build was run, no test suite, no live calls.

**Repository state:** `44cb5d1` (`origin/main` +7, tree clean). The audit
examined `3b55fc5`. The only difference that touches anything here is a one-line
`paper/generated/numbers.tex` regeneration (`HarnessLoc` moved with a docstring)
in `3b097ce`, which does not affect any count below; the counts are stated at
`44cb5d1` and should be re-run there.

**Provenance of the corrections.** `reports/external-audit-2026-09-23.md` §7
listed nine pack claims it found untrue, inaccurate or unconfirmed.
`reports/audit-response-2026-09-23.md` §4 verified each finding by finding and
conceded the four that were checkable without a network. This session re-verified
all four independently, settled the fifth (the venue) with the web check the
earlier session could not make, and fixed two more the earlier session had
verified but left in place.

---

## 1. "gates green" — **untrue, corrected**

**Pack, header table, before:**

> | state | builds green, gates green, **not submitted anywhere** |

**Evidence.** `python scripts/check_prereg_order.py` exits **1**:

```
cells: 35   ok: 27   exempt: 4   failing: 4
```

with four `UNMAPPED  FAIL` rows, each *"tracked collection with no entry in
EXPECTED"*:

```
reports/raw/phase40-deployment-2026-09-18
reports/raw/phase40-stage-10-interactive-2026-09-21
reports/raw/phase40-stage-100-2026-09-22
reports/raw/phase40-stage-30-2026-09-21
```

**What it is.** A gate-table omission, not a missing pre-registration:
`prompts/phase-40-agent-reachability.md` was committed 2026-09-17, before all
four, and each stage's governing amendment precedes its own data. Established in
full, with the exact `EXPECTED` entry each root needs, in
`reports/prereg-order-phase40-2026-09-24.md`. **The gate and the table are
unchanged; the gate still exits 1.**

**Corrected to** a state row that names the failing gate and points at that
report, rather than asserting a green it never had. The pack's §3 gate table
gains the same note in its `check_prereg_order.py` row.

**Note on the sibling claim.** The pack's §2.4 and §3 say
`check_paper_numbers.py` is *"43 checks, 0 failing"*. The auditor got **39
passed, 2 failed**, both `main.bbl/main.log exists`, because their LaTeX install
lacks `IEEEtran.cls` — an environment difference, not an author defect, and the
audit says so. Left as written.

---

## 2. The macro-source table — **inaccurate, rebuilt**

**Pack §2.2, before** (*"Distinct sources cited across `numbers.tex`, by
frequency"*), among other rows:

> | `analysis/redis-kill-ablation.csv` (matrix) | 25 macros — the ablation |
> | `analysis/per-cell-metrics.csv` (matrix) | 3 — the rate source |

The audit called this "inaccurate"; the 2026-09-23 response agreed and put
`per-cell-metrics.csv` at 56. **56 is right.**

### How I counted, so it can be rechecked

Two independent counts, on `paper/generated/numbers.tex` at `44cb5d1`:

**(a) Provenance comment lines — one command per row:**

```
grep -c -- "per-cell-metrics.csv" paper/generated/numbers.tex
```

This counts every line of the file containing that basename. It is the
reproducible number and the one the table now prints.

**(b) Macros attributed — for cross-checking (a).** Walk the file; accumulate
consecutive `%` lines into a block; when a `\newcommand` is reached, attribute it
to each distinct source basename named anywhere in its block, then reset. This
answers "how many macros does this file supply", which is what the pack's
original column heading claimed.

### The rebuilt table

| source (basename) | (a) comment lines | (b) macros |
|---|---|---|
| `per-cell-metrics.csv` | **56** | 55 |
| `redis-kill-ablation.csv` | 41 | 40 |
| `comparisons-vs-aep-full.csv` | 20 | 19 |
| `e1-kill-latency-by-run.csv` | 19 | 19 |
| `per-execution.csv` | 11 | 11 |
| `phase13-model-gap.json` | 10 | 10 |
| `latency-and-throughput.csv` | 9 | 8 |
| `g2-flakey-write-loss*.json` | 9 | 8 |
| `coverage.json` | 7 | 7 |
| `phase13-fault-landing.json` | 5 | 5 |

### Three facts that make the two columns reconcilable

1. **`numbers.tex` defines 221 macros** (`grep -c 'newcommand'`, which matches
   the pack's own §2.1 figure). **182** carry a named source in their comment
   block; **39** are derived from other macros and name no file — e.g.
   `\BaselineDupLow` restated as a percentage. 182 is the sum of column (b).
2. **No comment block names two different sources.** Checked explicitly; the
   count is 0. So column (b) has no double-counting and the two columns measure
   the same thing at different granularity.
3. **Column (a) exceeds column (b) by exactly 1 for five rows, and by 0 for the
   other five.** The five are `per-cell-metrics.csv`,
   `latency-and-throughput.csv`, `redis-kill-ablation.csv`,
   `comparisons-vs-aep-full.csv` and `g2-flakey-write-loss*.json` — which are
   precisely the five files named in the file's own 5-line header banner
   (`numbers.tex:1-5`). That banner line is the +1. It is the whole discrepancy,
   and it is why the audit's counts (52 / 19 / 19) and the 2026-09-23 response's
   (56 / 41 / 20 / 19) differ from each other and both differ from the pack's.

### Why the pack said "3"

A regex for the literal string `analysis/per-cell-metrics.csv` finds 3. The
other attributions do not write the directory: **52** name the basename bare,
and **2** carry a `ws5-2026-09-10/t2-*/analysis/` prefix. The pack's table was
built from a path regex over a file whose own provenance comments are
inconsistent about whether they include a directory — so the table was wrong for
the same reason correction 3 below exists.

### What is not fixed

The pack's §2.2 table mixed two axes — some rows named a CSV basename, some named
a collection directory (`ws5-2026-09-10/t1-p0-everysec/`,
`ws4-writeloss-s1-2026-09-07/`, `fsync-always-2026-09-14/`). The rebuilt table is
on one axis, the source file, and the collection-directory view is not
reproduced. Anyone who wants it can get it by attributing full paths rather than
basenames; the largest entries are `reports/raw/e1-kill-latency-by-run.csv` 19,
`b2-paired-v2-*/analysis/redis-kill-ablation.csv` 12,
`ws5-2026-09-10/t1-p0-everysec/analysis/per-execution.csv` 9, and
`ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv` 5.

---

## 3. `\WriteLossAepApplied`'s provenance path — **a defect in the generated provenance**

The audit filed this against the pack, which quotes the comment as an example of
the evidence chain. **The pack copied it correctly; the generator emits a path
that resolves nowhere.** Recording it as a pack error alone would have hidden the
real defect, which is what this section exists to prevent.

### The defect

`paper/generated/numbers.tex:325-326`:

```
% ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv |
%   executions_with_an_applied_effect, AEP_FULL row
\newcommand{\WriteLossAepApplied}{285}
```

`experiments/results/ws4-writeloss-s1-2026-09-07` **does not exist**. The tree is
only at `reports/raw/ws4-writeloss-s1-2026-09-07`.

### Why the bare path is actively misleading rather than merely terse

Every *other* bare directory prefix in `numbers.tex` resolves under
`experiments/results/`:

| bare prefix in `numbers.tex` | `experiments/results/` | `reports/raw/` |
|---|---|---|
| `ws5-2026-09-10` | yes | no |
| `fsync-always` | yes | no |
| `fsync-always-2026-09-14` | yes | no |
| `b2-paired-v2-s1-2026-08-28` | yes | no |
| `phase13-armA-s1-2026-09-03` | yes | no |
| **`ws4-writeloss-s1-2026-09-07`** | **no** | **yes** |

A reader who learns the convention from the first five applies it to the sixth
and lands nowhere. The audit's §7 row reached the same conclusion by `find`.

### Scope: seven macros

`WriteLossRunsPerArm`, `WriteLossExecPerArm`, `WriteLossExecPerRun`,
`WriteLossAepApplied`, `WriteLossBthreeApplied`, `WriteLossAcksAfterFault`,
`WriteLossAckFailures` — `grep -c 'ws4-writeloss-s1-2026-09-07'
paper/generated/numbers.tex` → 7.

### Where it would have to be fixed

`scripts/paper_tables.py`, `writeloss_cell_macros()` at line **625**. Every one
of the seven comments is built from `root.name`:

- lines ~652-665: five comments of the form
  `f"{root.name}/analysis/redis-kill-ablation.csv | …"`
- lines ~679-687: two comments of the form
  `f"{root.name} | analyse_write_loss.observe_behaviour, …"`

`Path.name` is the last component and drops the parent. The `root` passed in is
the `--writeloss-cell` argument, whose default is set at
`scripts/paper_tables.py:3451` as
`ROOT / "reports" / "raw" / "ws4-writeloss-s1-2026-09-07"` — so the full,
correct, repository-relative path is available at the point the comment is
built.

**The fix:** replace `root.name` with `root.relative_to(ROOT).as_posix()` in
those seven f-strings, then regenerate. The comments become
`reports/raw/ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv`.

**Worth checking at the same time**, since the same class of bug is likely:
every other emitter that builds a provenance comment from a `Path`. `root.name`
is the right choice only when the directory is unambiguous under
`experiments/results/`, and this session did not audit the other emitters.

### Why it is not fixed here

Editing `scripts/paper_tables.py` without regenerating leaves the generator and
`paper/generated/numbers.tex` out of step, which
`check_paper_numbers.py::check_generated_tables` exists to catch; regenerating is
a write under `paper/`, which this session is barred from. **Left for a session
that can rebuild.** The pack's §2.1 now flags the path so that an auditor
following the example is not sent to a directory that does not exist.

---

## 4. What the PDF says about the archive DOI — **misquoted, corrected**

**Pack §7.4, before:**

> A reserved DOI is minted but does not resolve until published, so
> `\archiveavail` renders the honest *"not yet deposited"* sentence.

**Evidence.** `paper/main.tex:145` is `\archivedoistate{RESERVED}`. The macro has
three branches (`main.tex:231-242`); `RESERVED` selects the branch at `:238`. The
*"prepared and verified but not yet deposited"* text is the **PENDING** branch at
`:232`, which is not selected.

Rendered — `pdftotext -layout paper/main.pdf -`, §8 Artifact Availability:

> "It does not contain the raw run directories, which are bulk data: those are
> carried by a separate archive, prepared and verified, with the Zenodo record
> reserved under DOI 10.5281/zenodo.22766567; the identifier is fixed and begins
> resolving when the record is published."

Counts across all four builds:

| build | `not yet deposited` | `begins resolving` |
|---|---|---|
| `paper/main.pdf` | 0 | 1 |
| `paper/main-anon.pdf` | 0 | 0 |
| `paper/supplementary.pdf` | 0 | 0 |
| `paper/supplementary-anon.pdf` | 0 | 0 |

The anonymous build renders a third thing entirely, from the
`\ifanonymous` branch at `main.tex:158`: *"those are carried by a separate
archive, available via the submission system."*

**Corrected to** the rendered RESERVED wording, with the anonymous build's
different sentence noted, and with the substantive point preserved unchanged: a
reviewer still cannot verify the evidence, and the deposit is still the
submission blocker.

---

## 5. Target venue "double-anonymous" — **wrong, corrected**

**Pack, header table, before:**

> | target venue | IEEE Transactions on Software Engineering, double-anonymous |

The audit flagged this as *"Not confirmed; likely wrong"*. The 2026-09-23
response recorded **CANNOT VERIFY**, correctly, because that session made no
network calls. It is now settled.

**Evidence.** IEEE Computer Society, *How to Get Published: Author Guidelines for
IEEE Computer Society Publications*,
https://www.computer.org/publications/author-resources, retrieved 2026-09-24:

> "IEEE Transactions on Cloud Computing, IEEE Transactions on Computers, **IEEE
> Transactions on Software Engineering**, IEEE Transactions on Dependable and
> Secure Computing, and IEEE Transactions on Emerging Topics in Computing do not
> offer this option."

Full treatment, including the page limit, the overlength-charge mechanism, and
an honest account of what could not be retrieved, in
`reports/tse-venue-2026-09-24.md`.

**Corrected to** single-anonymous, with a pointer to that report and a note that
the anonymous builds and `prove_anonymous_gate.sh` are built for a review model
this journal does not run. The pack's §7.5 camera-ready framing — *"Things
invisible to a double-anonymous reviewer"* — is corrected in the same pass: under
single-anonymous review those items are visible to reviewers from the start.

---

## 6. "caught by an external reviewer" — **unsupported, restated**

**Pack §2.2, before:**

> An auditor should know that the second rule was violated once and caught by an
> **external reviewer**, not by the gates — see §8.2.

and §8.2's heading, *"An own-rule violation was found by an external reviewer,
not by the gates"*.

**Evidence.** `reports/paper-review-2026-08-11.md:9` describes its own
environment:

> "Environment note for reproducibility of this review: the reviewer's container
> has Python 3.12 + `uv 0.11.7`, no Docker, and outbound network limited to
> package registries and web search."

Lines 1-9 name no person and no affiliation. That description is consistent with
an agent sandbox. **I cannot establish who or what wrote it**, and that is the
point: "external" asserts an independence the repository never establishes, and
the pack's whole purpose is to be a map an auditor can trust.

**Corrected to** what is verifiable and is in fact the load-bearing part of the
claim: a review conducted in a **separate session, blind to `reports/`, against
the tracked CSVs in its own clone** — which the review's own §Review protocol
documents in detail (stage 1 written from `paper/main.pdf`, `ARTIFACT.md` and the
public tree only; every stage-1 computation run against the tracked CSVs). The
substantive finding is untouched: the pooling violation was found by that review
and not by the gates, and `check_paper_numbers` still verifies a number against
its source and not the choice of source.

---

## 7. Roman-numeral section references — **mismatch, converted**

**Evidence.** The compsoc build renders Arabic numerals.
`pdftotext -layout paper/main.pdf -` gives `8 ARTIFACT AVAILABILITY`,
`6.3.1 Detection is the record's, not the barrier's`, `6.5 RQ4: recovery`,
`9.1 Construct validity`. The pack used `§VI-B`, `§VIII` and so on throughout —
33 references across 26 lines.

**The trap, and why this was not done with `sed`.** Artifact Availability and
Threats to Validity were swapped on 2026-09-23 (pack §6). The **file** names kept
their original numbers, so `paper/sections/08-threats.tex` renders as
**Section 9**. The pack was written across that boundary and uses `§VIII` for
*both* sections in different places — §2.3's *"§IX describes it"* is about the
archive, which is now Section 8, while §8.1's *"§VIII says it plainly"* quotes
`08-threats.tex`, which is now Section 9. Each reference was therefore resolved
**by its subject**, not by a numeral substitution.

Map used for the unambiguous ones:

| pack | renders as |
|---|---|
| §I | Section 1 |
| §III | Section 3 |
| §IV | Section 4 |
| §V | Section 5 |
| §VI | Section 6 |
| §VI-A | Section 6.2 (RQ1) |
| §VI-B | Section 6.3 (RQ2) |
| §VI-C | Section 6.4 (RQ3) |
| §VI-D | Section 6.5 (RQ4) |
| §VII | Section 7 |

`§VIII` and `§IX` were resolved one at a time against what the sentence is about:
the artifact/DOI/repository → Section 8; threats, limitations, the oracle, the
detection finding's lack of an external referent → Section 9.

---

## 8. Claims the audit raised that are **not** changed

| audit §7 row | finding | why unchanged |
|---|---|---|
| §1.3 C3 *"in any cell measured"* | audit: **True** | no correction owed |
| §5.2 no manuscript text mentions phase 40 | audit: **True** | no correction owed |
| §2.4 / §3 `check_paper_numbers` *"43 checks, 0 failing"* | auditor got 39/2 | environment difference (`IEEEtran.cls` absent), not an author defect; the audit says so |

---

## 9. The line added to the pack

A paragraph now sits directly under the pack's opening, before the header table,
recording that the pack was itself audited on 2026-09-23, naming
`external-audit-2026-09-23.md` §7 as the source of the findings,
`audit-response-2026-09-23.md` §4 as the finding-by-finding verification, and
this file as the record of what was changed and what was left. It also names the
one correction the pack could not make — the generated provenance path of §3 —
and where it has to be made instead.

The pack's opening already says *"Where this document and the repository
disagree, the repository wins."* It did disagree, in seven places. That sentence
was load-bearing and is now evidenced.
