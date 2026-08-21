# Phase 6 — Independent adversarial audit

**Auditor:** Claude Opus 5, a different session and instrument from the 4B/5A/5B/5C
sessions, from the `audit-report-2026-08-10.md` auditor, and from the
`paper-review-2026-08-11.md` reviewer.

**Subject — and it changes between sections, deliberately.**

- **S1** audits `Research-paper-AEP` at **`a03985c`**, the 5C submission
  candidate, over the range `e1e815d..a03985c` (16 commits).
- **S2 and S3** audit **`origin/main` @ `c2fffa6`**, the current head, which is
  eleven commits further on. Retargeted on instruction once S1 established that
  the 5C candidate's known defects are already closed upstream, making a sweep of
  it archaeology. `a03985c` remains an ancestor of `c2fffa6`; no history was
  rewritten.

Each section states its own subject and range at its head. **Do not read a verdict
in one section as covering the range of another.**

**Structure.** Three sessions, each appended to this file: **S1** = bounds and
git integrity; **S2** = the denominator audit and the §G.1 defect class; **S3** =
claims, manuscript, venue, the `a03985c..c2fffa6` bounds check, and the diff
against the two prior passes.

**Two prior passes exist and were read in full before this audit began** —
`audit-clone/reports/audit-report-2026-08-10.md` (verdict FIX FIRST, with an
applied fix log) and `audit-clone/reports/paper-review-2026-08-11.md` (verdict
Major Revision). **Every finding below therefore carries a prior-art tag:**

| Tag | Meaning |
|---|---|
| `NEW` | In neither prior report. |
| `CONFIRMS` | Prior report found it; re-derived independently here and agreed. |
| `CONTRADICTS` | Prior report found it and reached a different conclusion. |
| `PRIOR-MISSED` | A prior instrument was pointed at this and returned nothing. |

**Severity.** `SUBMIT-BLOCKER` — a reviewer or editor meeting this alone would
reject or require the claim withdrawn, or the manuscript cannot be submitted as
it stands. `MAJOR` — the claim is true but its support is materially weaker than
the prose implies; fixing it needs new data or a rewritten claim.
`MINOR` — correct and supported, but imprecise or inconsistent; fixable by
editing prose. **Prior disclosure moves a finding at most one step down, and only
when the disclosure is in the *manuscript*. No disclosure removes a finding.**

---

## PRE-AUDIT REGISTER — three findings produced during planning, sealed before execution

Recorded so they cannot be presented as audit output. Full derivations are in the
plan file; they are adjudicated in **S3**, not here.

| ID | Finding | Prior art |
|---|---|---|
| **PR-1** | `main.tex:90-95` — the abstract lists "block-level write loss" among the faults the five-baseline evaluation ran under. `experiments/flakey_write_loss.py:61-76` imports no `aep_core` and no harness; it writes two keys (`:78-79`). No protocol outcome was ever measured under write loss. | `NEW` |
| **PR-2** | `scripts/verify_refs.py:54-61` `NON_DBLP_SOURCES` has drifted from `refs.bib`: of seven non-DBLP URL entries, **two are swept at wrong addresses** (`redis-locks`, `temporal-activity-definition`) and **one is never swept at all** (`temporal-activity-failures`). | `NEW` |
| **PR-3** | "agent" occurs 0 times in `03-model`, `04-protocol`, `05-implementation`, `06-evaluation` and `09-artifact` — the entire technical core. No LLM/planner reference anywhere in `experiments/**`. | `NEW` |

---

# S1 — Bounds and git integrity (A0)

> ### ⚠ AUDITED RANGE OF THIS SECTION — read before trusting any "clean" verdict below
>
> **S1 audited `e1e815d..a03985c` — the 4B handoff through the 5C submission
> candidate — and its predecessors. Nothing in S1 examined anything after
> `a03985c`.**
>
> This section is committed on a head that contains **eleven commits S1 never
> looked at**: `e8c3568`, `06188d1`, `399e502`, `4b910d3`, `f4de834`, `d08fdc6`,
> `bf68440`, `aef47f9`, `335bdb9`, `b9617e4`, `c2fffa6` — the Monday audit, its
> post-audit fixes, the D6/D11/D12 closures, the TSE paper review, and the Stage 1
> and Stage 2 closures. Those eleven commits touch `paper/**`, `scripts/**` and
> `tests/**` and include a wholesale rewrite of `paper/generated/numbers.tex`,
> `paper/refs.bib` and `paper/sections/07-related.tex`.
>
> **`a03985c..c2fffa6` is NOT bounds-audited by this section.** It is added to
> S3's scope as a separate bounds check. The commit that carries this section was
> rebased onto `c2fffa6` so that the audit lands on the mainline; the rebase moved
> only this audit's own unpushed commit and rewrote no published history.
> **Do not read the rebase as coverage.**
>
> Verified as part of that landing: `a03985c` **is** still an ancestor of
> `origin/main`, so the eleven commits were added on top rather than replacing the
> audited head — no force-push, and the range S1 audited is intact in history.

## S1.0 A precondition that failed, identically to the prior audit

**Finding S1-A · MINOR · `CONFIRMS` (prior audit D9).** The three prompt files the
sessions actually ran under — `COMBINED_PROMPT_P0_5A.md`,
`COMBINED_PROMPT_PRE5B_5B.md`, `COMBINED_PROMPT_PRE5C_5C.md` — are **not in this
repository, not in git history at any revision, and not anywhere under
`D:\personal\AEP` to depth 5.**

```
$ ls COMBINED_PROMPT*                                    → none in repo root
$ git log --all --name-only | grep -i COMBINED_PROMPT    → (empty)
$ find D:/personal/AEP -maxdepth 5 -iname "*COMBINED_PROMPT*" -o -iname "*PRE5B*" -o -iname "*PRE5C*"
                                                          → (empty)
```

The consequence is exactly the one the prior audit stated and it is worth
restating rather than inheriting: **bounds can be audited against each report's
*declared* scope, not against the prompt actually issued. A session that widened
its own declared bounds to match what it did is invisible to this instrument and
to the previous one.** Two independent audits now share this blind spot. It is
structural, not fixable retrospectively, and it is the single largest limitation
on both bounds audits.

`WEEKEND_CODEX_PROMPTS.md` is in the repo and is byte-identical to the human's
upload — `git rev-parse 833bd91:CODEX_PROMPTS.md` and
`git rev-parse HEAD:WEEKEND_CODEX_PROMPTS.md` both resolve to blob
`62c33844bf36ad2fbce79d267622f52cc4366337` — but it describes a *planned* regime
that the combined prompts superseded.

## S1.1 Report §B against git, per session

Derived from git first, then compared to each report's §B — not the other way
round.

| Session | Range | Files (git) | §B claims | Verdict |
|---|---|---|---|---|
| 5A | `07547df..eca6fcd` | 9 | 9 | ✅ exact |
| Phase P | `eca6fcd..9975dc1` | **22** | "**21 files**" | ⚠️ **S1-B** |
| 5B | `9975dc1..454a825` | 5 | 5 | ✅ exact |
| **5B report commit** | **`454a825..31664ca`** | **2** | **not in §B** | ⚠️ **S1-C** |
| Q + 5C | `c262f0f..a03985c` | 14 | 2 (Q) + 13 (5C) = 14 | ✅ exact |

**Finding S1-B · MINOR · `CONFIRMS` (prior audit D1).** Phase P's §B table lists
22 files and its bold summary says "**21 files**". I counted the table rows
independently: 9 source/config files + 5 matrix analysis CSVs + `coverage.json` +
`MANIFEST.csv` + `SHA256SUMS` + 2 fsync-always CSVs + 3 flakey JSONs = 22. Every
file is listed; the total is wrong. Nothing is undisclosed.

**Finding S1-C · MINOR · `NEW` and `PRIOR-MISSED`.** **5B's §B, which declares
itself "the FULL list", omits a manuscript edit.** Commit `31664ca` ("Phase P +
5B: the session report, and a sixth bad number the report found") modified
**two** files:

```
$ git diff --name-status 454a825..31664ca
M	paper/sections/06-evaluation.tex
A	reports/phase-report-5b-2026-08-10.md
```

5B's §B has a "Phase P" block (22 files) and a "Phase 5B" block (5 files, commit
`454a825`). Neither covers `31664ca`. The manuscript edit it carries appears in
no §B table.

*Why the prior audit did not catch it:* its §1.1 range table audits
`07547df..eca6fcd`, `eca6fcd..9975dc1`, `454a825`, and `c262f0f..a03985c`.
**`31664ca` falls between `454a825` and `c262f0f` and is in none of them.** The
prior audit's union-of-bounds check did cover the file (`paper/**` is in bounds),
so it correctly concluded no out-of-bounds file changed — but its per-session §B
reconciliation has a hole, and "all three match exactly" is true only of the
three ranges it chose.

*Severity is MINOR, and here is why it is not more.* The change is benign and
disclosed elsewhere. It replaces a hand-typed word-number with the two macros:

```diff
-two executions in six hundred (\cref{tab:ablation}).
+$\BthreeVsAepAmbDelta{}$ executions in \BthreeVsAepN{} (\cref{tab:ablation}).
```

That is the correct direction — a hand-typed measurement becoming
generator-checked — and the commit message and 5B §C.6 (line 1064, "**sixth** — a
duplicate of the fifth, in a section I had just finished") both describe it. The
defect is that §B claims completeness it does not have, in a project whose
central discipline is that the file list is the audit surface.

## S1.2 Out-of-bounds files: none

Across the whole range, 46 distinct files changed. Every one falls inside the
union of declared bounds (`paper/**`, `reports/**`, `docs/24-revision-backlog.md`,
`WEEKEND_CODEX_PROMPTS.md`, `experiments/results/**` as `git add` only,
`.github/workflows/ci.yml`, `.gitignore`, `.gitattributes`, `ARTIFACT.md`,
`Makefile`, `README.md`, `CHANGELOG.md`, `CITATION.cff`, `scripts/paper_tables.py`,
`tests/test_paper_tables.py`, `PAPER_ROADMAP.md`).

**`aep_core/**` is untouched across the entire range** — no implementation change
could have moved a measured number. `scripts/` shows only `paper_tables.py`, so
`check_pytest_gates.py` and `verify_refs.py` were never edited. ✅ `CONFIRMS`.

## S1.3 Rule 10 — history integrity

```
author-date ≠ committer-date, over 16 commits in range :  0
deleted reports, ALL history                           :  1  (reports/_section_f_draft.md,
                                                              c5592b9 "Phase 4 Session 1",
                                                              a scratch draft, BEFORE the range)
frozen results modified or deleted (--diff-filter=DM)  :  0  (empty)
merges in range                                        :  1  (07547df, preserving 833bd91
                                                              as second parent)
reflog force/reset/rebase/amend entries                :  1  ("reset: moving to HEAD",
                                                              2026-08-06, a no-op, and it
                                                              PREDATES the range)
```

**No amended or rebased commit, no deleted phase report, no modified frozen
result, exactly one merge and it is a true merge.** ✅ `CONFIRMS` the prior audit
on every line.

**Limitation, stated because it bounds the claim:** `.git/logs/HEAD` holds 49
entries and a reflog is local and expiring. A force-push performed from a
different clone, or before this clone existed, leaves no trace here. **S1.3
establishes "no evidence of history rewriting", not "no history rewriting
occurred."**

## S1.4 Frozen-result bytes — 17/17, and stronger than the prior audit could get

```
$ cd experiments/results/matrix && sha256sum -c SHA256SUMS
MANIFEST.md: OK                     analysis/metric-known-ambiguity-rate.csv: OK
MANIFEST.csv: OK                    analysis/metric-lost-effect-rate.csv: OK
analysis/comparisons-vs-aep-full.csv: OK   analysis/metric-recovery-success-rate.csv: OK
analysis/coverage.json: OK          analysis/metric-state-corruption-rate.csv: OK
analysis/figure-1-undetected-vs-ambiguity.pdf: OK  analysis/metric-undetected-duplicate-rate.csv: OK
analysis/figure-2-duplicates-by-crash-point.pdf: OK analysis/metric-unverified-failure-rate.csv: OK
analysis/latency-and-throughput.csv: OK    analysis/per-cell-metrics.csv: OK
analysis/per-execution.csv: OK      analysis/redis-kill-ablation.csv: OK
analysis/table-1.csv: OK
EXIT=0        OK=17   MISSING=0   FAILED=0   of 17
```

**All 17 verify, exit 0.** The prior audit could only verify 7 of 17, because it
ran on a fresh clone where the other 10 are gitignored archive-layer files; it
recorded the non-zero exit as **D3**. This working tree carries the untracked
archive layer, so the manifest verifies completely.

**D3 is therefore confirmed as a clone-only artifact, not a content problem** —
the bytes are sound; only the evaluator experience is bad. ✅ `CONFIRMS`, with the
severity reduced by evidence the prior instrument could not reach.

`experiments/results/fsync-always/` still has **no** `SHA256SUMS` (it contains
only `analysis/`), while two of its CSVs are git-tracked. ✅ `CONFIRMS` 5C §G.5 /
prior audit D5. Unclosed.

## S1.5 Rule 9 — no external action

Two tags, both plain annotated tags: `v0.2.0` on `6079a19`, `v1.0.0-rc1` on
`31664ca`. No release objects reachable locally; the prior audit queried
`GET /repos/.../releases` and received `[]`. Every occurrence of upload language
in the reports is a negation ("nothing was uploaded to Zenodo, arXiv, any DOI
minter…", 5B:1154; "no account, token or draft exists on arXiv, any journal
system, Zenodo, any DOI…", 5C:1024). `paper/cover-letter-tse.md` and
`paper/arxiv-metadata.md` are in-repo drafts required by the 5C task list.

**No evidence of any external submission, upload, release or account.** ✅
`CONFIRMS`.

## S1.6 Did 5C stay inside "polish only"?

45 added/removed lines across the seven section files in `0e80297`. Filtering
that diff to lines containing a digit or a generated macro returns **exactly one
line pair**:

```diff
-right-hand column is why the known-ambiguity rate in \cref{sec:eval-rq1} varies
+right-hand column is why the declared-ambiguity rate in \cref{sec:eval-rq1} varies
```

Pure terminology. **No quantitative claim moved in 5C.** ✅ `CONFIRMS`.

The `refs.bib` change in the same commit is the URL repoint, and its own comment
is now load-bearing evidence for **PR-2**:

```
% The path recorded on 2026-08-07 (.../develop/use-cases/patterns/distributed-locks/)
% now returns HTTP 404 -- Redis moved the page from use-cases to clients
```

`verify_refs.py:59` **still sweeps the `use-cases` path** — the one the repository
itself records as dead. Adjudicated in S3.

## S1.7 A finding I nearly recorded wrongly, and the correction

Recorded because an audit that hides its own near-misses is not one.

`06-evaluation.tex:621` states "the voided attempt ships in the artifact under
`results/voided/`". I searched the working tree: **zero** directories or files
matching `voided`, against 84 run directories present under
`experiments/results/matrix/` and `coverage.json` claiming 432 runs. The
provisional reading was that the path exists nowhere — materially stronger than
the prior review's hedge ("presumably it lives in the unpublished archive").

**I checked before writing it, and the provisional reading was wrong.** The WSL
measurement tree named by `scripts/sync_measurement_tree.sh:28`
(`$HOME/aep`) exists and is root-owned:

```
/root/aep/experiments/results/voided                        ← exists
/root/aep/experiments/results/matrix/*-r[0-9]*  →  432       ← exactly coverage.json's figure
/root/aep/experiments/results/aep-matrix-results-2026-08-07.tar.gz
```

So the 432 runs and the voided run **do exist**, exactly as the reports say, on
one root-owned path on one machine. **The prior review's reading was correct and
mine would have been an overclaim.** The 432/432 match between the measurement
tree and `coverage.json` is also an independent provenance confirmation nothing
else in this audit could have supplied.

What survives is the *availability* claim, not the *existence* claim, and it is
carried to S3 for adjudication against `09-artifact.tex:4-6` ("the analysis
pipeline and the raw results are available at `<GitHub URL>`") — where only 13
analysis files are tracked. That is the prior review's **R4.1**, and S1 has now
established both halves of it: the raw results exist, and they are not where the
paper says they are.

---

## S1 verdict

**Bounds: clean. Rule 10: clean. Rule 9: clean. Frozen bytes: 17/17.**

Nothing in S1 threatens a measured result, and nothing in S1 is a
SUBMIT-BLOCKER. Three findings, all MINOR:

| ID | Severity | Finding | Prior art |
|---|---|---|---|
| S1-A | MINOR | Issued prompts unavailable; bounds audited against declared scope only. Two audits now share this blind spot. | `CONFIRMS` (D9) |
| S1-B | MINOR | Phase P §B says 21 files; git and the table both show 22. | `CONFIRMS` (D1) |
| **S1-C** | **MINOR** | **5B §B, declared "the FULL list", omits commit `31664ca`'s edit to `06-evaluation.tex`. The prior audit's range table skips that commit entirely.** | **`NEW` / `PRIOR-MISSED`** |

S1-C is the only thing in this session that neither prior pass found, and it is
minor. **The honest summary of S1 is that the prior audit's bounds work was
substantially correct and I could add one small hole to it.**

Carried to S3: the availability claim (S1.7), the `verify_refs.py` dead-path
sweep (S1.6 → PR-2), and the missing `fsync-always/SHA256SUMS` (S1.4).

*End of S1.*

---

# S2 — A1a: the denominator audit (SWEEP HALTED)

> **Subject of S2 and S3: `origin/main` @ `c2fffa6`, the current head — not
> `a03985c`.** Retargeted on instruction after S1 established that the 5C
> candidate's known A1 targets (§G.1, the Wilson label, the regime pooling) are
> all closed upstream. Auditing them there would have been archaeology.
>
> **A1a was mandated to run BEFORE the 47-sentence sweep and to be treated as
> potentially terminal. It has returned a result that triggers its own stop
> condition. The sweep has not been run.**

`paper/generated/numbers.tex` changed `\BthreeVsAepN` from **600** to **540**
between `a03985c` and `c2fffa6`. Sixty executions per arm left the denominator of
the paper's central ablation. A1a establishes what left, under what rule, when
that rule was written, whether it applied evenly, and whether the file
regenerates.

## S2.1 (i) — what left the denominator: nothing was deleted

The change is a **re-keying, not a removal**. `comparisons-vs-aep-full.csv` at
`c2fffa6` carries a `regime` column with three distinct values, and the macro now
selects one:

```
$ awk -F, 'NR>1{print $1}' comparisons-vs-aep-full.csv | sort -u
crashed
p0
redis-kill-preack

crashed,known_ambiguity_rate,B3_INTENT_NO_BARRIER,AEP_FULL,195,540,...,193,540,...,0.949435
p0,     known_ambiguity_rate,B3_INTENT_NO_BARRIER,AEP_FULL,  0, 30,...,  0, 30,...,1.0
```

540 crashed + 30 `p0` + 30 `redis-kill-preack` = **600**, exactly the prior
figure. The sixty executions are still in the file, as their own rows. The
comment header moved from `regime=(session-3)` — a session label that was not a
fault regime at all — to `regime=crashed`.

**The decisive control: the per-cell denominators did not move.**

```
a03985c  \newcommand{\AepExecAuth}{180}       c2fffa6  \newcommand{\AepExecAuth}{180}
a03985c  \newcommand{\BthreeVsAepN}{600}      c2fffa6  \newcommand{\BthreeVsAepN}{540}
```

Every rate the paper prints in `tab:outcomes` comes from `per-cell-metrics.csv` at
180 executions per capability class, and **180 is unchanged before and after**.
Only the cross-system comparison file moved. What the fix corrected was an
*inconsistency between two files*: per-cell always said 180 x 3 = 540, while the
comparison file said 600.

## S2.2 (iii) — was the exclusion symmetric? Yes, and where it is not, the reason is structural

Crashed-regime denominators, every system, from the committed CSV:

| System | n | runs | vs AEP-full |
|---|---|---|---|
| AEP_FULL (reference) | 540 | 54 | — |
| B3_INTENT_NO_BARRIER | **540** | 54 | **identical** |
| B4_DURABLE_WORKFLOW | 540 | 54 | identical |
| B4B_..._AT_MOST_ONCE | 540 | 54 | identical |
| B0_NAIVE_RETRY | 450 | 45 | −90 |
| B1_LEASE_ONLY | 450 | 45 | −90 |
| B2_CAS_ONLY | 450 | 45 | −90 |

**The ablation — the comparison that carries the paper's central structural
result — is exactly symmetric: 540 against 540, 54 runs against 54.** B0–B2 sit
at 450 because they run **five** crash points, not six: they have no
`after_intent_before_barrier` because they write no intent record. 5 x 3 x 30 =
450 against 6 x 3 x 30 = 540. That is the asymmetry the prior audit raised as
**D11** and that `f4de834` says it disclosed in the caption. It is structural, and
it is not an artifact of the regime filter.

## S2.3 (ii) — the rule, and its date. **This is the finding.**

**Finding S2-A · MINOR · `NEW` — the exclusion rule postdates the data it
excludes by 46 minutes.**

The rule is the manuscript's own §VI-A(e), still present verbatim at
`06-evaluation.tex`:

> *"First, **no pooled table**. A rate computed across fault regimes is a property
> of how many runs of each kind were collected, not of any system; our own
> analysis tool prints a warning whenever more than one regime is present, and
> every number below names its regime."*

Provenance, from git rather than from any report's prose:

```
rule text enters paper/sections/06-evaluation.tex  6cd6815  2026-08-07 12:51:39 +0500
main.tex "BANNED as a source" banner               6cd6815  2026-08-07 12:51:39 +0500
regime-keying gate, check_paper_numbers.py         6cd6815  2026-08-07 12:51:39 +0500
                                                   ("Phase 4: manuscript draft, generated
                                                     tables, and the numbers-drift gate")

redis-kill-preack data committed                   8446103  2026-08-07 12:05:28 +0500
                                                   ("Phase 2B Session 3B: E1-E6 amendments,
                                                     hard Redis kill, graded ambiguity")
```

**The data landed at 12:05. The rule landed at 12:51. Strictly, the answer to
"was the rule written down before the results it excludes were seen" is NO.**

That is recorded as a finding and not softened. Three pieces of evidence bear on
whether it is *outcome-motivated*, and all three point the same way:

1. **The correction moved the headline number against the paper.**
   `\BaselineDupMaxP` went from `2.1e-183` to `5.4e-182` — **25.7x weaker**. A
   post-hoc rule invented to flatter a result does not make the flagship p-value
   worse.
2. **The result it was supposed to protect did not change.** B3 vs AEP-full
   declared ambiguity differs by **2 executions** under the pooled figure and by
   **2 executions** under the filtered one (195/540 vs 193/540, Fisher
   p = 0.9494 against the previous 0.95). The ablation's conclusion is untouched
   in both magnitude and sign.
3. **The rule was identified by the session that collected the data**, not by a
   later session reading an unfavourable number: Session 3B's own report records
   that Table 1 "pools three fault regimes and is a coverage summary rather than a
   result." Phase 4 wrote it into the manuscript 46 minutes later. The gate, the
   banner and the prose all entered in **one commit**, which is what a rule being
   adopted looks like rather than a rule being reached for.

**What remains a real defect regardless of motive:** the manuscript's §VI-A(e)
asserts the rule as a standing methodological commitment without recording that
it was adopted after the first collection, and the same paragraph's *second* rule
does exactly the opposite — it says plainly, "*zero* runs collected before this
rule existed contribute a timing number." **The paper knows how to disclose a
retrospectively-adopted rule, does it for the E5 timing gate one sentence later,
and does not do it for the pooling rule.** One clause fixes it.

## S2.4 (iv) — regenerability: PASS, and the frozen artifacts are intact

`CLAUDE.md`'s Stage 3 rule 2 declares `numbers.tex` frozen at the `c2fffa6`
baseline and instructs a STOP if it changed. It has not:

```
$ git diff --stat c2fffa6 -- paper/generated/
   (empty)
```

The committed generator, run against the frozen results in the locked
interpreter, reproduces every generated artifact byte-for-byte:

```
$ sudo ./.venv/bin/python scripts/check_paper_numbers.py
  PASS  per-cell-metrics.csv is keyed by regime      PASS  table-latency.tex matches the CSVs
  PASS  appendfsync=always analysis is present       PASS  table-outcomes.tex matches the CSVs
  PASS  G2 write-loss results is present             PASS  no generated table draws from the banned pooled table
  PASS  paper_tables.py runs                         PASS  generated tables declare their sources
  PASS  numbers.tex matches the CSVs                 PASS  every generated number is used in the manuscript
  PASS  table-ablation.tex matches the CSVs          PASS  state-machine figure matches the transition table
  PASS  table-ambiguity-by-crashpoint.tex matches    PASS  bibliography has entries / no empty entries
  PASS  table-deployment-choice.tex matches          PASS  bibtex no parse errors / no undefined refs
----------------------------------------------------------------------
18 passed, 0 failed
```

**`numbers.tex` at `c2fffa6` is regenerable. There is no SUBMIT-BLOCKER on
regenerability.** Note what this does and does not establish: it proves the
manuscript's numbers follow from the committed CSVs by the committed arithmetic.
It does not prove the CSVs describe the runs — that is `SHA256SUMS` (S1.4,
17/17) and the 432/432 measurement-tree match (S1.7).

## S2.5 The bound arithmetic, re-derived independently

Since the same commit changed `\AblationZeroUpper` from `0.64` to `0.50`, both
values were re-derived here rather than accepted. The Wilson upper bound on a
zero numerator is `z^2/(n+z^2)`:

| n | one-sided 95% (z=1.645) | two-sided 95% upper (z=1.960) |
|---|---|---|
| 600 | 0.4489% | **0.6362%** |
| 540 | **0.4985%** | 0.7064% |

- `a03985c` committed **0.64** while the prose said "one-sided 95%" — that is the
  **two-sided** upper at n=600. Mislabelled, exactly as the prior review's
  Recomputation 3 found. ✅ `CONFIRMS`.
- `c2fffa6` commits **0.50**, which is the one-sided 95% bound at n=540 to two
  decimal places, and `06-evaluation.tex:285-289` now states the quantile choice
  explicitly ("one-sided bound using the 95th normal quantile; it is not the upper
  endpoint of a two-sided 95% Wilson interval, which uses the 97.5th quantile").
  **The fix is CORRECT** — label and value now agree, and the bound is correctly
  *looser* at the smaller n.

This answers Amendment 1's question for this fix: not merely present, but right.

## S2 verdict — sweep halted, one finding

| ID | Severity | Finding | Prior art |
|---|---|---|---|
| **S2-A** | **MINOR** | The no-pooling rule that removes 60 executions per arm entered the repo 46 minutes **after** the data it excludes. Not outcome-motivated on three independent lines of evidence, but the manuscript asserts it as a standing commitment while disclosing the adjacent E5 rule's retrospective adoption one sentence later. | `NEW` |

**Nothing terminal.** The denominator did not move "after the fact" in the sense
the stop condition was guarding against: nothing was dropped, the ablation is
symmetric at 540/540, the per-cell figures never moved, the correction cost the
paper 25.7x on its headline p-value, and the file regenerates byte-identically.

**The 47-sentence sweep has NOT been run.** Per the stop condition it is held
pending a decision, and S2.3's evidence is what that decision should rest on.

*End of S2.*

---

# S3 — A1a exhaustive, and the arithmetic sweep on `c2fffa6`

> **Subject: `origin/main` @ `c2fffa6`.** S3 supersedes S2's provisional reading of
> the pooling rule with an exhaustive one, then sweeps the current manuscript for
> the §G.1 defect class: *a sentence asserts a relationship between two
> correctly-generated numbers, and the relationship is false.*

## S3.1 A1a exhaustive — every macro, old rule against new

S2's case rested on two macros that happened to be checked. `numbers.tex` is
byte-regenerable, so the case is now measured rather than sampled.

Both revisions consume an **identical** `per-cell-metrics.csv` (757 rows, 702
`(session-3)` + 42 `p0` + 12 `redis-kill-preack`). The only changed input is
`comparisons-vs-aep-full.csv`, which at `a03985c` had **no regime column at all**
and carried pre-pooled rows. Pooling the new regime-keyed file reproduces the old
figures exactly:

```
$ awk -F, '$3=="B3_INTENT_NO_BARRIER" && $2=="known_ambiguity_rate" {s+=$5;t+=$6;rs+=$8;rt+=$9} END{...}'
  B3 pooled: 225/600    AEP pooled: 223/600
  old committed CSV:    B3 225/600, AEP 223/600     -> exact
```

**Full macro diff, old rule (`a03985c`) against new rule (`c2fffa6`):**

```
macros parsed:  old=89  new=101
  identical value : 84
  CHANGED value   :  5
  removed in new  :  0
  added in new    : 12
```

| Macro | Old (pooled) | New (crashed-only) | Direction for the paper |
|---|---|---|---|
| `BaselineDupMaxP` | `2.1e-183` | `5.4e-182` | **UNFAVOURABLE** — 25.7× weaker |
| `BthreeVsAepN` | 600 | 540 | **UNFAVOURABLE** — smaller n |
| `AblationZeroUpper` | 0.64 | 0.50 | favourable in isolation — **attributed below** |
| `CoreLoc` | 6,849 | 6,862 | neutral — LOC recount, Stage-1 code change |
| `HarnessLoc` | 21,458 | 22,218 | neutral — LOC recount |

**Attributing the one favourable movement.** `AblationZeroUpper` changed for
*two* reasons at once, and they pull in opposite directions. Wilson upper bound
on a zero numerator is `z²/(n+z²)`:

| | value | prints |
|---|---|---|
| committed OLD — n=600, two-sided z=1.960, **mislabelled** one-sided | 0.6362 | 0.64 |
| **pooling rule ALONE** — n 600→540, old convention kept | **0.7064** | would print **0.71** |
| label fix ALONE — n=600, correct one-sided z=1.645 | 0.4489 | would print 0.45 |
| committed NEW — n=540, correct one-sided z=1.645 | 0.4985 | 0.50 |

**The pooling rule on its own moves the bound 0.6362 → 0.7064 — looser, i.e.
against the paper.** The tightening comes entirely from the Wilson *label*
correction, which an external reviewer demanded and which is arithmetically
correct.

**The falsifiable question, answered:**

| | count |
|---|---|
| headline claims that **gain significance** under the new rule | **0** |
| headline claims that **change sign** | **0** |
| headline claims that **cross a threshold** | **0** — both p-values ≪ 0.05 before and after |

The pooling rule's isolated effect on **every one of 89 macros** is neutral or
unfavourable. The twelve added macros are all self-limiting disclosures
(`BarrierToProtocolRatio` replacing "two orders of magnitude";
`ProtocolMinusBarrierLow/High` adding an interval the paper did not have;
`BthreeVsAepAmbDiff*` adding an equivalence bound). None strengthens a claim.

**Finding S2-A is therefore settled at MAJOR — and the 46-minute gap is not the
finding.**

**Finding S2-A · MAJOR · `NEW`.** `06-evaluation.tex` §VI-A(e) presents the
no-pooling rule as a standing methodological commitment, in the same paragraph in
which it discloses the E5 timing gate's retrospective adoption — *"Under this
gate, **zero** runs collected before this rule existed contribute a timing
number"* — two sentences later. The paper demonstrably knows how to disclose a
retrospectively adopted rule and does not do it here, although the pooling rule
entered `6cd6815` at 2026-08-07 12:51:39, forty-six minutes after `8446103` at
12:05:28 committed the `redis-kill-preack` data it excludes.
**Remedy: one sentence disclosing the rule's date and the reason for it, matching
the E5 disclosure already two lines below.** No number changes; the audit above
establishes that no number would.

## S3.2 The arithmetic sweep

Candidate enumeration on `c2fffa6`, keyed on relational connectives with
word-numbers admitted as quantities (the keying that catches the original §G.1
instance; a numeral/macro-only sweep does not):

| File | candidates |
|---|---|
| `06-evaluation.tex` | 85 |
| `08-threats.tex` | 39 |
| **total** | **124** |

Every candidate asserting a derivable relationship was re-derived by hand against
`generated/numbers.tex` and the frozen CSVs. **20 formal derivations, plus the
seven `tab:latency` increments, plus the prose relationships stated in words.**

**Passing (selected, all re-derived here, not accepted):**

```
ProtocolMinusBarrier = B3med - B0med           28.0    = 2038.2 - 2010.2      PASS
ProtocolMinusBarrierPct                         1.4    = 28.0/2010.2*100      PASS
BarrierCost = AEPmed - B3med               1 966.7    = 4004.9 - 2038.2      PASS
ThirdBarrierStepPct                            24.6    = 983.3/4004.9*100     PASS
BarrierCostAlways                              15.0    = 2063.4 - 2048.4      PASS
BarrierToProtocolRatio                           70    = 1966.7/28.0 = 70.24  PASS
UnwantedPrevented                                18    = 28 - 10              PASS
AepUnwantedRate / BthreeUnwantedRate    0.3333/0.9333  = 10/30, 28/30         PASS
BthreeVsAepAmbDelta                               2    = |195 - 193|          PASS
BthreeVsAepAmbDiffPP                           0.37    = 2/540*100            PASS
AblationZeroUpper                              0.50    = one-sided 95% at 0/540 (0.4985)  PASS
"five percentage points = 27 escalations per 540"      = 540*0.05 = 27        PASS
"roughly a third of runs"                              = 10/30                PASS
"three runs per stratum"                               = 54/18                PASS
tab:latency, all seven "over B0" increments            re-derived from CSV    PASS
```

The equivalence block at `06:263-296` is correct throughout: the interval
`[-1.11, 2.04]` pp does lie within `±5` pp; the Bonferroni statement (joint
coverage ≥ 90%, not 95%) is right; and the explicit quantile sentence
("*this is a genuinely one-sided bound using the 95th normal quantile; it is not
the upper endpoint of a two-sided 95% Wilson interval, which uses the 97.5th
quantile*") is both correct and exactly the repair the prior review demanded.

### Finding S3-A · MINOR · `NEW` — the one genuine §G.1-class survivor

`06-evaluation.tex:567` and `08-threats.tex:312`, the **same claim in two
places**:

> *"…positive, but pinned only to within a factor of four."*

```
BarrierCostLow  =   477.9        BarrierCostHigh = 1 978.8
1978.8 / 477.9  =   4.1406
```

**The interval spans a factor of 4.14, not four.** The sentence claims marginally
*more* precision than its own generated numbers support. This is the §G.1 defect
class exactly — a relationship asserted between two correctly-generated numbers
that does not hold — and it is live on the current head, in two locations, found
by neither prior pass.

Severity is MINOR and honestly so: the error is 3.5%, the direction is
self-deprecating (the sentence exists to admit imprecision), and no conclusion
moves. **Remedy: "a factor of about four", or "a factor of 4.1".**

### Finding S3-B · MINOR · `NEW` — "independent confirmation" is not independent

`06-evaluation.tex:508-510`:

> *"B4 and B4b landing on the same figure with their own two acknowledged appends
> is **independent confirmation** that the cost is the barrier and not anything
> AEP does around it."*

The **arithmetic is true**: AEP-full 4 004.9 ms, B4b 4 013.4 ms, B4 4 015.7 ms —
within 0.27%. "The same figure" is fair.

**"Independent" is not.** B4 runs on the same Redis, uses the *same* `WAITAOF`
barrier (the paper says so at `06:98-100`), on the same host, in the same
harness, written by the same author. It is a second arm of the same experiment,
not an independent instrument. `08-threats.tex` §(h) already concedes B4 "is not
Temporal" and that "the decision is our code", so the ingredients of the
correction are in the paper; the word in this sentence contradicts them.
**Remedy: "is corroboration within the same harness" or drop "independent".**
Adjacent to, but distinct from, the prior review's R3.2(i), which objected to
B4's latency row appearing in a table without the caveat.

### Non-finding, recorded for completeness

`\BarrierCostEach` prints `983.3` where `1966.7 / 2 = 983.35`. The generator
emits `983.3` (binary float: 983.35 is stored as 983.3499…), the committed value
matches what the generator produces, and `check_paper_numbers.py` passes on it.
0.05 ms on a ~1 000 ms quantity. **Not a defect** — recorded so that a later
reader re-running this arithmetic does not mistake it for one.

## S3.3 Two collateral results the sweep produced

**A3.1 does not trigger, and my Amendment-3 reasoning is vindicated.** I declined
to promote A3 (the one-cell prevention result) into the top-two SUBMIT-BLOCKER
candidates, on the argument that its blocker-shaped part was the abstract losing
the scope. The abstract at `c2fffa6` now reads:

> *"**Prevention** is what the barrier contributes, and the current evidence is
> narrower: in one `no-readback` capability class, at one pre-acknowledgement
> Redis-kill point, on one host…"*

The scope is carried at first mention. The prior review's **R4.6** is closed, and
A3 stands at **MAJOR** (thin but disclosed and correctly scoped), not
SUBMIT-BLOCKER. The prediction recorded before execution was right for the
reason given.

**PR-1 is confirmed live on the current head, and the abstract is internally
inconsistent about it.** `main.tex:146` (¶1) still states the five-baseline
evaluation ran "under real `SIGKILL` process faults, hard Redis kills **and
block-level write loss**", while `main.tex:173` (¶3) correctly describes the
write-loss probe as measuring *records* — "acknowledged records survive … and
unacknowledged ones are destroyed". Two paragraphs of the same abstract describe
the same experiment at two different scopes. **Adjudicated in S4.**

## S3 verdict

| ID | Severity | Finding | Prior art |
|---|---|---|---|
| **S2-A** | **MAJOR** | §VI-A(e) presents the no-pooling rule as a standing commitment while disclosing E5's retrospective adoption two sentences later. Rule postdates its data by 46 min. Exhaustively established to change **no** claim's significance, sign or threshold. | `NEW` |
| **S3-A** | MINOR | "pinned only to within a factor of four" (×2 locations); the interval spans 4.14. | `NEW` |
| **S3-B** | MINOR | "independent confirmation" from B4/B4b, which share AEP's Redis, barrier, host and author. Arithmetic true, independence claim false. | `NEW` |

**No SUBMIT-BLOCKER in S3.** The sweep's headline result is that the arithmetic
of this manuscript is, on the current head, **sound**: 84 of 89 macros unchanged
under an adversarial rule reconstruction, every derivable relationship in 124
candidate sentences re-derived, and exactly one false relationship found — at
3.5% magnitude, in a self-deprecating direction.

That is a materially different manuscript from the one 5C §H warned about. The
"assume there are more of these" premise was **correct in kind and wrong in
degree**: there was one more, and it is trivial.

*End of S3.*

---

# S4 — claims, manuscript, venue, and the diff against the prior passes

> **Subject: `origin/main` @ `c2fffa6`.** S4 covers A2–A7, adjudicates the sealed
> pre-audit register, performs the `a03985c..c2fffa6` bounds check that S1 could
> not see, checks whether the applied fixes are *correct* rather than present,
> and asks the second question about that range: **did closing old findings open
> new ones?**

## S4.1 The `a03985c..c2fffa6` bounds check — the range no audit has covered

Eleven commits, **58 files**. Two results matter.

### Finding S4-A · MAJOR · `NEW` — `aep_core/**` changed, and both prior audits' certification does not cover it

The prior audit certified, in bold: *"**`aep_core/**` is untouched across the
entire range** — no implementation change could have moved a measured number."*
That was true of `e1e815d..a03985c`. **It is not true of `a03985c..c2fffa6`:**

```
$ git diff --stat a03985c..c2fffa6 -- aep_core/
 aep_core/core/durability.py      | ...
 aep_core/core/intent_workflow.py | ...
 aep_core/core/intents.py         |  5 +++--
 3 files changed, 28 insertions(+), 15 deletions(-)     [commit b9617e4]
```

**I read the whole diff. It is semantics-preserving:** docstrings, comments, and
two exception *message* strings. No condition, no branch, no value, no control
flow. The frozen results remain attributable to the code that produced them.

**But its substance is a retraction, and that is the finding's real content.**
`DurabilityAck` changed from *"Proof that a barrier reported the preceding write
durable… cannot be constructed, subclassed, or copied"* to *"an in-process
control-flow guard under a trusted-code assumption, **not a cryptographic
capability**… Python underscore naming and closure state are not security
boundaries."*

**The manuscript followed, correctly and voluntarily.** C2 — the paper's most
novel mechanism — was rewritten in the same commit:

```diff
-      the fsync acknowledgement mints an unforgeable, single-use, scope-bound token
+      under a trusted-code assumption, the fsync acknowledgement returns an opaque,
+      non-copyable, single-use, scope-bound in-process dispatch guard;
+      This is a control-flow invariant of the supported API, not a
+      cryptographic capability or a boundary against arbitrary code in the
+      same Python process.
```

"Unforgeable" now appears **nowhere** in the manuscript; `04-protocol.tex:96` and
`08-threats.tex:122` carry matching disclosures. This is a project weakening its
own headline novelty claim without being forced to. **Recorded as a finding
because the certification gap is real and a reader inheriting the prior audit's
"aep_core untouched" line would be misled — not because anything is wrong.**

### Finding S4-B · MAJOR · `NEW` — the frozen-results invariant is broken, for the first time in the project's history

Both prior audits verified this and both got an empty result:

```
$ git log --all --diff-filter=DM -- experiments/results     [at a03985c]
   (no output)          -> "No tracked results file has ever been modified or deleted."
```

**It is no longer empty:**

```
$ git log --diff-filter=DM --name-only a03985c..c2fffa6 -- experiments/results
b9617e4 Close Stage 1 scientific integrity and novelty issues
  experiments/results/matrix/SHA256SUMS
  experiments/results/matrix/analysis/comparisons-vs-aep-full.csv
```

The manifest hash for that one file was rewritten in the same commit:

```diff
-c2a4cd3d…  analysis/comparisons-vs-aep-full.csv
+a5310f3a…  analysis/comparisons-vs-aep-full.csv
```

**Mitigations, all verified here rather than assumed.** Exactly one derived file
changed; `per-cell-metrics.csv`, `per-execution.csv`, `coverage.json`,
`MANIFEST.csv` and `MANIFEST.md` retain their original hashes; the manifest was
updated atomically in the same commit rather than left stale; the regeneration is
performed by a committed, tested tool added in the same commit
(`experiments/rebuild_comparisons.py`, `experiments/tests/test_regime_comparisons.py`);
and **S3's exhaustive macro diff proves the change moved no claim in the paper's
favour.**

**Why it is still MAJOR.** The artifact's credibility rests on an invariant it
states plainly and that two audits verified. That invariant now holds only with a
qualification, and **nothing in the repository says so.** A reader who runs the
prior audit's own command today gets a different answer and no explanation.
**Remedy: a line in `ARTIFACT.md` and in the results manifest recording that
`comparisons-vs-aep-full.csv` was regenerated at `b9617e4` to fix the
regime-pooling defect, with the old hash, the new hash, and the tool that did
it.** No number changes.

Rule 10 is otherwise clean across the new range: **0** commits with
author≠committer date, **0** deleted reports, **0** merges.

## S4.2 Did closing old findings open new ones? Yes — one

### Finding S4-C · MAJOR · `NEW` — the equivalence margin is justified in units the paper says it cannot measure

The eleven commits added twelve macros. Eleven are self-limiting (an interval the
paper did not have, a ratio replacing a rounder claim, cluster/strata counts).
**One introduces a new claim: equivalence.**

`06-evaluation.tex:263-276` now argues the ablation is *equivalent* within a
stated margin, and justifies the margin operationally:

> *"…which lies within a ±5 percentage-point margin. We introduce that margin in
> this revision; it was not preregistered. **Operationally, five percentage points
> corresponds to 27 additional terminal escalations per 540 crashed executions,
> which we treat as the largest operationally immaterial difference for this
> workload.**"*

`08-threats.tex` §(i), unchanged, says:

> *"Declared ambiguity **is not evaluated as an operational outcome**… That would
> require an operator study — do teams resolve declared ambiguities, how long does
> it take, what fraction are resolved correctly, and does the queue stay bounded?
> — and **we have run none**. Relatedly, the artifact has no escalation
> mechanism: reaching the terminal state pauses the execution and alerts nobody."*

**The margin that licenses the equivalence claim is set in terminal escalations,
and the paper states in terms that it has no evidence about what a terminal
escalation costs anyone.** Twenty-seven escalations are declared immaterial by a
paper that also says it does not know whether operators resolve escalations at
all, and that nothing alerts them.

The statistical framing is scrupulous — "post hoc", "not preregistered",
"sensitivity analysis, not a strong general equivalence result", "only for this
fixed design", "we treat as". **The circularity is not disclosed anywhere.**
This is the paper's own backlog **B4** appearing as an unstated premise of a new
claim rather than as an acknowledged gap.

**Remedy: either justify the margin on non-operational grounds (e.g. as a
fraction of the baseline effect the paper is contrasting against, 77–83 pp), or
add one clause tying it to §VIII(i) as an explicitly unevidenced stipulation.**

## S4.3 Are the applied fixes correct, not merely present? (Amendment 1)

| Fix | Present? | **Correct?** |
|---|---|---|
| **F1** — the §G.1 sentence | yes | ✅ **Verified in S3.** 983.3 ≤ 1000; "near the top" = 98.3%; the mechanism disclaimer scopes *why the mean sits high*, not the bound, so it is coherent rather than self-contradictory as I suspected when planning. |
| **F2** — anonymity | yes | ✅ **Largely.** `\ifanonymous` switch; the public build now names an author (`Hamza Khan`) and carries a correspondence footnote — the "unfinished block" half is closed too. Decompressing all 145 PDF streams: `main.pdf` carries the URL ×4 and the email ×1 as expected; **`main-anon.pdf` carries zero hits on every needle.** ⚠️ *Instrument limit:* my URI-annotation extraction found 0 annotations in **both** files, i.e. it does not work on this PDF's compressed object streams. **The prior audit's 15/4 → 11/0 annotation result is therefore not independently confirmed here.** |
| **D6** — "two orders of magnitude" | yes | ✅ Now "a factor of roughly 70" (1966.7/28.0 = 70.24), **and** the sentence discloses that the denominator is pinned only to [27.1, 1524.6] ms, so "the factor is an estimate of an order of magnitude rather than of a figure". Stronger than the fix required. |
| **Ten overfull boxes** | yes | ✅ **Verified by independent rebuild, not by report.** Fresh `pdflatex`/`bibtex` ×3 from `c2fffa6` sources into `/tmp` (`paper/` never written): **19 pages, 0 overfull, 0 undefined references, 0 undefined citations.** |
| **Olive + the 2026 wave** (paper review's #1, its only Reject-capable finding) | yes | ✅ `refs.bib` 25 → **34** entries, now including Olive/Setty, ALICE/Pillai, CrashMonkey/Mohan, Torturing Databases, the IETF Idempotency-Key draft, the transactional-outbox pattern, LogAct, Sovereign Execution Broker and Verified Tool Calls. `07-related.tex` rewritten (202 lines changed). |

## S4.4 PR-1 — adjudicated **SUBMIT-BLOCKER**

`main.tex:146`:

> *"We evaluate AEP against five baseline designs, one of them in two
> configurations … **under real `SIGKILL` process faults, hard Redis kills and
> block-level write loss, across three endpoint reconciliation capabilities**."*

Measured coverage, from the frozen CSVs and the probe's imports:

| Fault class named | Systems actually exercised | Capability classes |
|---|---|---|
| `SIGKILL` process faults | **7 of 7** ✅ | 3 ✅ |
| Hard Redis kills | **2 of 7** (AEP-full, B3) | **1** (`no-readback`) |
| Block-level write loss | **0 of 7** — two Redis keys | **0** |

`experiments/flakey_write_loss.py` contains **zero** references to `aep_core`,
**zero** to `experiments.harness`, **zero** to `baselines`.

**Is `:146` defensible on its own terms? No, and I tried the charitable parse.**
The generous reading detaches the fault list from the baseline comparison — "we
evaluate AEP … under X, Y and Z" rather than "we evaluate AEP *against five
baselines* under X, Y and Z". That reading still fails: **AEP itself was not
evaluated under block-level write loss.** Nothing ran. No execution, no protocol
outcome, no capability class. There is no parse under which the sentence is true.

**Why the disclosure discount does not apply, stated explicitly rather than
resolved by placement.** My own severity rule discounts a finding one step when
the manuscript discloses the limit specifically — and `08-threats.tex` §(b) *does*
("The write-loss probe tests `WAITAOF`, not AEP"). I am declining the discount on
two grounds:

1. **The abstract contradicts itself, twice, and self-contradiction is not cured
   by disclosure fourteen pages later.** ¶1 says "hard Redis kills" without
   qualification; ¶2 says the prevention evidence is "in one `no-readback`
   capability class, at one pre-acknowledgement Redis-kill point, on one host".
   ¶1 says "block-level write loss"; ¶3 correctly describes a *records* probe
   ("acknowledged records survive … unacknowledged ones are destroyed"). The
   correction the reader needs is already in the same abstract, which means the
   authors knew the accurate scope while writing the inaccurate sentence.
2. **The discount presumes the reader reaches the disclosure.** An editor
   triaging on the abstract decides whether the claimed evidence exists before
   §VIII is read, and there is no later point at which that decision is revisited.
   A discount that assumes a reading which the defect's own location prevents is
   not a discount.

**The remedy is one clause** — delete "and block-level write loss" and qualify
"hard Redis kills". That it is trivial is an argument for its severity, not
against it: an easily-corrected false coverage claim in the abstract is exactly
what converts a paper's candour from an asset into a liability.

## S4.5 PR-2 / A2 — **MAJOR**, and now measured rather than argued

**The gate cannot fail, and I made it fail 14 times while it reported success.**
`scripts/verify_refs.py` run against the current head, this session:

```
queries printed  : 9  of 23
zero-hit queries : 0
LOOKUP FAILED    : 14        (HTTP 503 / HTTP 500 from DBLP, despite the 8 s sleep)
VERIFY_REFS_EXIT = 0
```

**Sixty-one percent of the bibliography sweep failed and the script exited 0.**
`main()` still ends in an unconditional `return 0`; a failed lookup only prints.
This is 5C §G.3 and the prior audit's D7, reproduced live on the current head,
after two commits touched this file. It is not a stale finding.

**PR-2's three drifts, re-verified on `c2fffa6`: one fixed, two survive.**

| `refs.bib` entry | Swept? |
|---|---|
| `redis-locks` → `…/develop/clients/patterns/…` | ✅ **FIXED** — now swept at the corrected path |
| `temporal-activity-definition` → `docs.temporal.io/activity-definition` | ❌ **still not swept**; the script sweeps `…/activity-execution`, which matches **no** `refs.bib` entry |
| `temporal-activity-failures` → `…/encyclopedia/detecting-activity-failures` | ❌ **still absent** from `NON_DBLP_SOURCES` |

`refs.bib` now holds 34 entries against 23 `QUERIES`. `09-artifact.tex` still
tells the reader *"Every bibliography entry was verified to exist before it was
written… The raw output of that sweep ships with the artifact."* **The sweep that
sentence points at exits 0 without verifying anything, on this host, today.**

Severity MAJOR rather than SUBMIT-BLOCKER because the *bibliography itself is
sound* — the prior audit spot-checked six entries against Crossref and arXiv
including the most attackable (`zheng2026acrfence`, arXiv 2603.20625, real) and
all six resolved. The defect is the assurance mechanism, not the references.

## S4.6 PR-3 / A4 — **MAJOR**: the agent framing is decorative

Occurrences of "agent" per file on `c2fffa6`, unchanged from `a03985c`:

| file | count | | file | count |
|---|---|---|---|---|
| `main.tex` (title/abstract/keywords) | 8 | | `06-evaluation.tex` | **0** |
| `01-introduction.tex` | 4 | | `07-related.tex` | 6 |
| `02-motivating.tex` | 1 | | `08-threats.tex` | 2 |
| `03-model.tex` | **0** | | `09-artifact.tex` | **0** |
| `04-protocol.tex` | **0** | | `05-implementation.tex` | **0** |

**Zero across the entire technical core** — model, protocol, implementation,
evaluation, artifact. And
`grep -rniE "\bllm\b|openai|anthropic|language model|gpt|planner" experiments/ --include=*.py -l`
returns nothing. The workload is synthetic payments;
`PAPER_ROADMAP.md` marks 3C (LLM-driven workload) not started.

**Is the framing load-bearing?** Test: replace "autonomous agent" with "any
client of a non-idempotent, non-cooperative endpoint" throughout. **No property
(P1/P2/P3), no research question, no metric, no baseline and no number changes.**
The framing is therefore decorative with respect to the evidence — the paper is a
distributed-systems protocol paper wearing an agents title.

That is not fatal and it is defensible as *motivation*: §VII now positions
against three 2026 agent-reliability papers, so the problem is genuinely live in
that literature. **The defect is the mismatch between the title's promise and the
evaluation's content**, and a reviewer is entitled to ask why a paper titled
"…for Autonomous Agents" contains no agent anywhere it measures anything.
`08-threats.tex` does not list this among its threats.

## S4.7 S3-B re-examined — upgraded to **MAJOR**, with the reasoning stated

You directed me to start from: the sentence's function is to exclude a confound,
and if B4 shares AEP's substrate the defence does not exist. **I examined it and
I agree, with one correction that changes the remedy rather than the severity.**

`06-evaluation.tex:508-510`: *"B4 and B4b landing on the same figure with their
own two acknowledged appends is **independent confirmation** that the cost is the
barrier and not anything AEP does around it."*

- The arithmetic is true: AEP-full 4 004.9 ms, B4b 4 013.4 ms, B4 4 015.7 ms.
- **The defence in that sentence does not exist.** B4 uses *the same `WAITAOF`
  barrier* — the paper says so itself at `06:98-100` — on the same Redis, the
  same `appendfsync everysec`, the same host, in the same harness, written by the
  same author. If the ~2 s came from the shared substrate rather than from the
  barrier, B4 would agree **for that reason**. The observation cannot discriminate
  between the hypothesis and its confound, so it confirms nothing.

**The correction: the paper is not left without a defence.** B3 supplies it, and
supplies it properly — B3 *is* AEP with only the barrier removed, so
AEP − B3 = 1 966.7 ms is attributable to the barrier by construction. The
confound is excluded two paragraphs earlier by the actual ablation.

**So the finding is precise: the sentence offers a non-existent defence for a
confound that is separately and validly excluded.** That keeps it below
SUBMIT-BLOCKER — no claim in the paper is left unsupported — and puts it well
above a 3.5% overstatement, because it is a false assertion about the *class* of
evidence held, in a paper whose principal asset is that its evidence claims can
be trusted literally.

**Remedy, recorded as you asked: delete the sentence.** An actually-independent
experiment is *not* required, because B3 already excludes the confound; the
sentence is evidentially redundant as well as wrong, so deleting it costs the
paper nothing. The alternative — keeping it while disclosing that B4 shares the
barrier — is self-defeating, since the disclosure destroys the sentence's only
function. A word swap ("corroboration" for "independent") is **not** an adequate
remedy: the problem is not the adjective, it is that a shared-substrate
observation is offered as evidence at all.

## S4.8 A gate weakness, and a correction to my own S3

**Finding S4-D · MINOR · `NEW`.** `check_paper_numbers.py` reads two untracked
build byproducts — `paper/main.bbl` (`check_bibliography`, :219-253) and
`paper/main.log` (`check_undefined_references`, :256-273) — with **no freshness
check**. On this machine:

```
paper/main.log   untracked   mtime 2026-08-10 16:04:43
paper/main.bbl   untracked   mtime 2026-08-10 16:04:38
HEAD (c2fffa6)   committed   2026-08-12 00:56:58
```

The artifacts predate the head by two days. In **CI** the gate is sound —
`ci.yml:327` runs `build_paper.sh` before `:334` runs the gate. Run standalone,
as the script's own docstring instructs (`uv run --frozen python
scripts/check_paper_numbers.py`), it silently validates whichever build happens
to be on disk.

**Correction to S2.4/S3, owed and stated plainly:** the `18 passed, 0 failed` I
reported included two checks that read those stale artifacts, so my evidence path
for "no undefined references" and "bibliography sound" was weaker than I
presented it. **The conclusion is unaffected** — the fresh rebuild in S4.3
independently returns 0 undefined references and 0 undefined citations from
`c2fffa6` sources — and the sixteen substantive checks, which regenerate the
tables and byte-compare, never touched the stale files. But I stated 18/18
without qualifying it, and the qualification belongs on the record.

**Near-miss also recorded:** I read "10 overfull boxes" out of that same stale
`main.log` and nearly reported the typesetting defect as open. It is closed. Two
near-misses now, both from trusting an artifact instead of regenerating it —
which is precisely the failure mode this repository built its gates to prevent.

## S4.9 What held — findings with the same standing as the defects

An audit that lists only defects misrepresents the artifact. These are results,
established here by re-derivation, and they are the strongest available evidence
that the numbers discipline works.

| # | Result | How established |
|---|---|---|
| **H1** | **84 of 89 macros are unchanged** when `numbers.tex` is regenerated under the superseded pooling rule. Of the five that move, two are LOC recounts and two move **against** the paper; the one favourable move is attributable entirely to a Wilson *label* correction, not to the rule. | S3.1, full macro diff + isolation arithmetic |
| **H2** | **`numbers.tex` is byte-regenerable.** The committed generator, run against the frozen CSVs in the locked interpreter, reproduces every generated artifact byte-for-byte. **18 passed, 0 failed** (16 substantive; see S4.8 for the two). | S2.4, executed |
| **H3** | **124 relational claims re-derived; one false, at 3.5%.** Twenty formal derivations, seven `tab:latency` increments, and the word-stated relationships. The only failure is "within a factor of four" for a span of 4.14 — and it is self-deprecating. | S3.2 |
| **H4** | **Frozen bytes verify 17/17, exit 0.** Stronger than the prior audit could reach (7/17 on a clone), because this tree carries the untracked archive layer. | S1.4 |
| **H5** | **432 run directories exist and match `coverage.json` exactly**, in the WSL measurement tree, together with the `results/voided/` the paper cites. Independent provenance confirmation nothing else in this audit could supply. | S1.7 |
| **H6** | **Rule 10 holds across the entire history.** Zero amended or rebased commits over 27 commits in two ranges, one deleted report ever (a pre-range scratch draft), one merge, and `a03985c` still an ancestor of the head. | S1.3, S4.1 |
| **H7** | **The project retracted its own most novel claim unforced.** C2's "unforgeable token" became "an in-process guard, not a cryptographic capability", in code and manuscript together, with matching disclosures in two further sections. | S4.1 |
| **H8** | **The typesetting defect is fully closed** — 10 overfull boxes → **0**, verified by independent rebuild rather than by report. | S4.3 |
| **H9** | **The paper review's only Reject-capable finding is closed.** Olive, ALICE, CrashMonkey, Torturing Databases, the IETF draft, the outbox pattern and all three 2026 agent-reliability papers are now cited; `refs.bib` 25 → 34. | S4.3 |

**H1–H3 together are the substantive answer to 5C §H's warning.** The class it
named is real and one more instance existed; the discipline that was supposed to
contain it does contain it.

## S4.10 A7 — venue fit: submit-ready is not the same as competitive

**The distinction, stated first.** *Submit-ready* means the manuscript's claims
match its artifacts and nothing in it is false. On `c2fffa6` that is true except
for **PR-1**, which is one clause. *Competitive at a top venue* means the evidence
answers the question that venue's reviewers are trained to ask. **The paper is
one clause from the first and materially short of the second at all four venues,
for four different reasons.**

| Venue | What it would demand that this paper does not have | Specific gap |
|---|---|---|
| **IEEE TSE** (current target) | Evidence that the *engineering claim* holds for engineers. TSE's question is whether declared ambiguity is better **in practice**, and the paper states it does not show that. Also open-science compliance and generality beyond one artifact. | **B4** (no operator study, and no escalation mechanism for one to study); §VIII(m) "the detection finding has no referent outside this artifact"; the raw archive is unpublished so `09-artifact.tex`'s availability sentence is false |
| **DSN** | Fault-injection breadth and a second host. The *instrument* is already DSN-grade; the *coverage* is not. | **A3/B2** — the barrier's only surviving claim rests on one cell (`no-readback`, one crash point, n=30, one host); **B1** — no protocol outcome has ever been measured under write loss |
| **Middleware** | Behaviour under load. The paper's cost story is its most decision-relevant artifact and rests on three crash-free runs per arm, with the `always` interval spanning zero. | **B3** (3 runs/arm); the paper's own admission that its workload "cannot exercise" write throughput; no concurrency cell, so P1 is never exercised under live contention |
| **IEEE TDSC** | An adversary model. **Weakest fit, and `b9617e4` made it weaker**: the paper now states explicitly that its dispatch guard is "not a cryptographic capability", there is no Redis ACL, and the failure model is "crash-and-delay, not Byzantine". | `tab:nonclaims` forecloses the property TDSC exists to evaluate |

### Ordered build list — what to build next, each tied to what it unlocks

Ranked by *evidence bought ÷ effort*, not by ease.

1. **B2 — prevention on `auth` and `pos-only`.** ≈2 h, **no code change** (the
   regime exists: `run_matrix.py --regime redis-kill-preack`). Takes the barrier's
   *only* remaining claim from one cell to three capability classes, with a
   falsifiable prediction already written in the backlog. → **Unlocks DSN;
   materially strengthens every venue.** This is the single highest-value hour in
   the project.
2. **Publish the raw archive and cite a DOI.** ≈1 h. Closes the `09-artifact.tex`
   availability overclaim, makes the two analysis figures reproducible, makes
   `SHA256SUMS` checkable on a clone, and makes `results/voided/` reachable. →
   **Blocking for artifact badging anywhere; TSE open-science compliance.**
3. **B3 — 9 crash-free runs per arm.** ≈1 h; the unblock is one line
   (`AEP_FSYNC_RUNS` → `--runs-per-cell`). Makes the `always` interval mean
   something instead of spanning zero. → **Middleware's cost story; removes the
   paper's weakest interval.**
4. **B1 — the protocol under write loss**, on a Linux host with a native Docker
   daemon. ≈2.5 h plus host. Converts the barrier's durability case from
   premise-plus-argument into a system-level result, and **retires PR-1 by making
   the abstract's sentence true** instead of deleting it. → **DSN; and it is the
   one item that turns a correction into a contribution.**
5. **A concurrency / live-contention cell.** P1 and the fenced-CAS machinery are a
   large fraction of the implementation and are never exercised with two live
   claimants. → **Middleware and DSN; closes the reviewers' R3.1 residual.**
6. **A write-heavy throughput workload.** → **Middleware only.** Skip unless
   targeting it.
7. **3C — an LLM-driven workload.** The only item that makes the *title* honest
   and gives the technical core a reason to say "agent". → **Removes the A4
   objection at every venue**; without it, retitling is the cheaper fix.
8. **B4 — the operator study** (12–16 practitioners, pre-registered, within-subject).
   Largest effort by far, and it is the TSE-shaped contribution. Requires building
   the escalation surface first, since the artifact has none. → **The item that
   makes TSE competitive rather than merely appropriate.**
9. **3A — a formal layer** (TLA+ or Hypothesis against the real Lua). Optional
   strengthener. → **TSE/TDSC polish; lowest priority given everything above.**

**The honest summary of A7: items 1–3 cost about four hours and move the paper
from "defensible" to "solid" at DSN and Middleware. Item 8 is what a top-tier TSE
acceptance actually requires, and it is weeks, not hours.** Choosing the venue is
therefore a decision about which of those two you are willing to fund.

## S4.11 What this audit cannot see

Stated because a reader who does not see it stated will assume coverage that does
not exist.

1. **Declared scope only.** The three prompt files the sessions ran under
   (`COMBINED_PROMPT_*`) do not exist in the repository, in git history, or
   anywhere on this host. Bounds were checked against each report's *declared*
   scope, not against the prompt actually issued. **A session that widened its own
   declared bounds to match what it did is invisible to this instrument — and to
   the previous one.** Two independent audits now share this blind spot, and it
   cannot be closed retrospectively.
2. **No result was re-run.** Every rate in this paper is taken on the authority of
   the frozen CSVs plus `SHA256SUMS` plus the 432/432 measurement-tree match. If
   the harness mismeasured systematically, every check in this audit passes and
   the paper is still wrong.
3. **No code review of `aep_core`.** P1/P2/P3 are taken as stated. I read the
   `a03985c..c2fffa6` diff for semantic effect only.
4. **The full test suite was not run** (scope choice, not a blocker — Docker and
   the locked interpreter are both available).
5. **PDF link annotations are unverified.** My extractor found zero annotations in
   both PDFs, i.e. it does not work here; the prior audit's 15/4 → 11/0 result
   stands unconfirmed by me.
6. **Reflog forensics are local.** A force-push from another clone before this one
   existed leaves no trace. S1.3 establishes "no evidence of", not "did not
   happen".
7. **The auditor is the same model lineage** as the sessions audited. Mitigated
   where cheap — every mechanism in PR-1, PR-2 and S4.1 was confirmed by reading
   source or executing, not by trusting a report — but not eliminated.

## S4.12 Verdict

### Completeness: **97%**

The 3% is **PR-1** (one clause), **S4-B** (one disclosure line), **S4-C** (one
clause), plus the unpublished archive, which is a human action and not a defect.
Nothing that remains is evidence.

### Findings, all sessions

| ID | Severity | Finding | Prior art |
|---|---|---|---|
| **PR-1** | **SUBMIT-BLOCKER** | `main.tex:146` states fault coverage the artifact does not have — write loss exercised **0 of 7** systems, hard Redis kills **2 of 7** — and the same abstract contradicts it twice. | `NEW` |
| **PR-2 / A2** | MAJOR | `verify_refs.py` exited **0 after failing 14 of 23 lookups**, measured this session. Two of three `NON_DBLP_SOURCES` drifts survive. `09-artifact.tex` points readers at this sweep as assurance. | `NEW` (drifts) / `CONFIRMS` (hollow exit) |
| **S4-A** | MAJOR | `aep_core/**` changed after the prior audit certified it untouched. Semantics-preserving, and the substance is a voluntary retraction — but the certification gap is real. | `NEW` |
| **S4-B** | MAJOR | The frozen-results invariant is broken for the first time: `SHA256SUMS` and `comparisons-vs-aep-full.csv` modified at `b9617e4`, undisclosed. | `NEW` |
| **S4-C** | MAJOR | The new equivalence margin is justified in terminal escalations, which §VIII(i) says the paper has no evidence about. | `NEW` |
| **S2-A** | MAJOR | §VI-A(e) presents the no-pooling rule as a standing commitment while disclosing E5's retrospective adoption two sentences later. Exhaustively shown to change no claim. | `NEW` |
| **S3-B** | MAJOR | "independent confirmation" from B4/B4b, which share AEP's barrier, Redis, host and author. Remedy: delete — B3 already excludes the confound. | `NEW` |
| **PR-3 / A4** | MAJOR | Zero occurrences of "agent" across the entire technical core; no LLM anywhere in `experiments/`. The framing is decorative w.r.t. the evidence. | `NEW` |
| **A3** | MAJOR | Prevention rests on one cell at n=30 — but the abstract now carries the scope at first mention, so it is disclosed, not hidden. | `CONFIRMS` |
| **S3-A** | MINOR | "within a factor of four" for a span of 4.14, in two locations. | `NEW` |
| **S1-C** | MINOR | 5B §B, declared "the FULL list", omits `31664ca`'s manuscript edit; the prior audit's ranges skip that commit. | `NEW` / `PRIOR-MISSED` |
| **S4-D** | MINOR | `check_paper_numbers.py` reads untracked build byproducts with no freshness check; sound in CI, silently stale standalone. | `NEW` |
| **S1-A** | MINOR | Issued prompts unavailable; bounds auditable against declared scope only. | `CONFIRMS` |
| **S1-B** | MINOR | Phase P §B says 21 files; git shows 22. | `CONFIRMS` |

**One SUBMIT-BLOCKER, seven MAJOR, five MINOR. Nine of fourteen are `NEW`.**

### Verdict: **FIX FIRST**

**S3's "no SUBMIT-BLOCKER" was true of S3 only and this verdict does not inherit
it.** PR-1 was unadjudicated when S3 closed; it is adjudicated now, and it blocks.

**Ordered, before submission anywhere:**

1. **PR-1** — correct `main.tex:146`. Delete "and block-level write loss";
   qualify "hard Redis kills" to the scope ¶2 already states. *One clause.*
2. **S4-C** — tie the ±5 pp margin to §VIII(i), or rejustify it non-operationally.
   *One clause.*
3. **S3-B** — delete the "independent confirmation" sentence. *One sentence.*
4. **S4-B** — record the `comparisons-vs-aep-full.csv` regeneration in
   `ARTIFACT.md` with both hashes and the tool. *One line.*
5. **S2-A** — disclose the pooling rule's adoption date, matching the E5
   disclosure two lines below it. *One sentence.*
6. **S3-A** — "a factor of about four", twice. *Two words.*
7. **PR-2** — either fix `verify_refs.py`'s exit code and the two drifts, or
   soften `09-artifact.tex`'s claim about what the sweep establishes.
8. **PR-3 / A4** — decide: retitle, or run 3C. Do not ship the current title with
   the current evaluation and no threat acknowledging the gap.

Items 1–6 are **six edits totalling well under a page** and none changes a
number. Item 7 is a script. Item 8 is a decision.

**Then, and only then, the venue question — and A7's items 1–3 (≈4 hours) before
submitting anywhere that will ask about the barrier's single cell.**

*End of S4. Audit complete.*
