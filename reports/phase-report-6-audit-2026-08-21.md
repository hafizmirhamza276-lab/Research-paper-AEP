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
