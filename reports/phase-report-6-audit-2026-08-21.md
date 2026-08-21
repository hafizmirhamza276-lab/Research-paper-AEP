# Phase 6 — Independent adversarial audit

**Auditor:** Claude Opus 5, a different session and instrument from the 4B/5A/5B/5C
sessions, from the `audit-report-2026-08-10.md` auditor, and from the
`paper-review-2026-08-11.md` reviewer.

**Subject:** `Research-paper-AEP`, branch `main`, HEAD `a03985c` — the 5C
submission candidate. Working tree clean apart from an untracked `CLAUDE.md`.

**Audited range:** `e1e815d` (4B handoff) → `a03985c` (head), 16 commits.

**Structure.** Three sessions, each appended to this file: **S1** = bounds and
git integrity; **S2** = the §G.1 defect class; **S3** = claims, manuscript,
venue, and the diff against the prior audit. This section is S1.

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
