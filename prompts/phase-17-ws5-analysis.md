# Phase 17 — WS-5.analysis: analyse the 612 collected runs against the pre-registration

**Rule 4.** Committed before anything else in this pass. The prompt is recorded
as issued; corrections are recorded alongside it, never silently applied.

**Issued:** 2026-09-14. **Preceded by:**
`reports/phase-report-ws5-prediction-2026-09-10.md` (`47d8a23`), its amendment 1
(`684c5fb`), `prompts/phase-16-ws5-power-and-cells.md`, and the collection
commit `729fbfa`.

---

## The prompt, as issued

> ## Read first (do not skip)
> - `docs/26-journal-readiness-direction.md` §3 (rules 1–14) and §4 WS-5
> - `reports/phase-report-ws5-prediction-2026-09-10.md` — the pre-registration (§2.2 H1–H5, §2.3 the exact analysis, §2.4 stopping rule)
> - `reports/phase-report-ws5-prediction-amendment-1-2026-09-10.md` — §1, how a mixture arm is reported
> - `prompts/phase-16-ws5-power-and-cells.md` — the collection prompt and its four recorded corrections
> - `git show 729fbfa` — the collection commit message, in particular the "NOT ANALYSED" and "STILL OUTSTANDING" blocks
> - `scripts/power_analysis.py`, `experiments/analyze.py`, `scripts/freeze_results.py`
> - `docs/25-collection-tooling-rules.md` R15
>
> ## Context
> 612 runs / 6 120 executions / 44 cells sit under `experiments/results/ws5-2026-09-10/`
> in four steps (`t1-p0-everysec` 105, `t1-incomplete` 12, `t2-p30` 315,
> `t2-keying` 180). Only MANIFEST.md / MANIFEST.csv / SHA256SUMS are tracked; the
> raw run tree is on the measurement host per `.gitignore:128`. Nothing has been
> computed from them — no rate, no mixture test, `power_analysis.py` untouched.
> This pass runs the analysis exactly as pre-registered, produces the tracked
> analysis CSVs, and rules on H1–H5. It is the pass that decides whether §VI-RQ3's
> 28.0 ms decomposition claim survives.
>
> ## Bounds
> - In scope: `experiments/results/ws5-2026-09-10/**/analysis/` (new files only),
>   `scripts/power_analysis.py` and its test, `reports/phase-report-17-*.md`,
>   `prompts/phase-17-*.md`.
> - Out of scope: **the paper**. No `.tex` edit in this pass, not even a number.
>   Also out: every previously frozen directory under `experiments/results/**`
>   (rule 2), `paper/generated/**`, and the two outstanding collections named below.
> - If you find a defect outside scope: record it under "Findings outside scope"
>   and stop.
>
> ## Steps
> 1. Commit this prompt as `prompts/phase-17-ws5-analysis.md` before anything else.
> 2. **Prove you are analysing what was collected.** Verify all four `SHA256SUMS`
>    against the raw tree on the measurement host and report OK/total per step.
>    If any digest mismatches, stop and report — do not analyse a modified tree.
>    This is what SHA256SUMS was committed for.
> 3. **Settle the `settled=false` runs first, before any outcome is computed.**
>    19 of 315 in `t2-p30` and 53 of 180 in `t2-keying` carry `settled=false`;
>    the harness voided nothing and the collection pass deliberately did not
>    classify them. Decide under the pre-registered rule whether an unsettled run
>    is a measurement, state the rule you applied and where it comes from, and
>    record the decision **before** you look at any rate or timing value. A
>    classification made after seeing the outcomes is a fitted classification.
> 4. Run the analysis as fixed in pre-registration §2.3 and nowhere else:
>    cluster bootstrap over **runs**, 10 000 resamples, seed **20260806**;
>    `power_analysis.py --section degeneracy` as the mixture instrument.
> 5. Apply amendment 1 §1 to every arm the mixture test flags: mode-conditional
>    medians after the largest-gap split, upper-mode fraction with a run-clustered
>    interval, pooled median descriptive only. **Differences are differences of
>    lower-mode medians.** If no arm is flagged at 15 runs, say so explicitly —
>    that is H2 refuted, and it is reported, not quietly dropped.
> 6. Rule on H1–H5 one at a time, each with the number that decides it.
>    H2 is load-bearing: if the upper-mode fraction falls outside [0.15, 0.40],
>    **H1's estimand must be reconsidered before any timing number is quoted.**
>    TOST for H5 at α = 0.05 against ±5 pp; Bonferroni across the three capability
>    classes.
> 7. Write the analysis CSVs into each step's `analysis/` directory and track them,
>    the way every other collection does.
> 8. R15 — verify the change with the gate that covers what you changed:
>    `uv run --frozen pytest -q -ra --strict-markers --cov=aep_core --cov-fail-under=90`,
>    then `scripts/validate_citations.py`, `scripts/check_paper_numbers.py`,
>    `make reproduce-figures`. The paper must still build both ways unchanged:
>    `bash scripts/build_paper.sh && bash scripts/build_paper.sh --anonymous`.
>
> ## Acceptance criteria (all must be true)
> - 4/4 SHA256SUMS verified OK before any number was computed, output pasted.
> - The `settled=false` ruling is stated, sourced to the pre-registration, and
>   timestamped before the first outcome computation.
> - Every timing interval quoted rests on ≥ 15 runs.
> - Each of H1–H5 has an explicit verdict: supported / refuted / not decidable,
>   with the deciding number and its CSV cell.
> - Analysis CSVs are committed; `MANIFEST` counts and the CSVs cannot disagree
>   (both go through `experiments.analyze.load_run`).
> - Suite green, 0 skipped, all gates pass, paper byte-identical to HEAD's build.
> - Zero `.tex` files changed in this commit.
>
> ## Report
> `reports/phase-report-17-ws5-analysis-<date>.md` with sections:
> Asked / Done / H1–H5 verdicts / **What this means for §VI-RQ3 and §VIII, stated
> but not yet applied to the paper** / Not done and why / Raw outputs for every
> headline number / Findings outside scope / Environment.
> Do not summarise beyond a 5-line pointer in chat.
>
> ## Explicitly still outstanding after this pass — do not start them here
> - The `always` arm of task 5.1 (`scripts/fsync_always_benchmark.sh`, second Redis
>   on its own port, refuses unless `CONFIG GET appendfsync` reads back `always`).
> - The two extra class-sweep sessions, 4 → 6, per amendment 1 §2.

---

## Corrections, recorded rather than applied silently

**1. Step 2 cannot be performed as written, and the reason is a defect in the
collection pass rather than in this prompt.**

Step 2 says *"Verify all four SHA256SUMS against the raw tree on the measurement
host … This is what SHA256SUMS was committed for."* Those files do not cover the
raw tree. Each of the four contains **two lines**:

```
<digest>  MANIFEST.md
<digest>  MANIFEST.csv
```

`scripts/freeze_results.py` says so in its own docstring — *"SHA256SUMS — over
the manifest and every analysis output"* — and at freeze time there were no
analysis outputs, so only the two manifests were digested. The tool did exactly
what it documents.

**The over-claim is mine.** Commit `729fbfa` asserts *"SHA256SUMS is what lets
the later pass prove it analysed what was collected."* It does not. It lets a
later pass prove the **manifests** are unchanged, which is a strictly weaker
statement and does not cover 331 MB of run directories.

*What is done instead, and what it is worth.* The two manifests are verified
against their committed digests, and the manifests are then **regenerated from
the present raw tree** and compared byte-for-byte. Because `freeze_results.py`
reads runs through `experiments.analyze.load_run` — the same loader the analysis
uses — a byte-identical regeneration establishes that the tree still yields the
same 612 runs, 44 cells and per-cell execution counts. That is real evidence and
it is not a full-tree digest: a change to a run's *contents* that left every
count identical would pass it. Stated here so the gap is visible rather than
implied.

**2. The raw-tree digest this pass could not use is out of scope to add here.**
The prompt confines writes to `**/analysis/` plus the named scripts and reports.
A `RAW-SHA256SUMS` at each step root is neither. Recorded under "Findings
outside scope" in the phase report instead of being added unasked.
