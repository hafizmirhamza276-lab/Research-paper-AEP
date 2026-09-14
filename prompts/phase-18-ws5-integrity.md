# Phase 18 — WS-5.integrity: the four load-bearing claims that do not hold

**Rule 4.** Committed before anything else in this pass.

**Issued:** 2026-09-14. **Follows:** phase 17 (`d57bdbe`), whose report §1.2,
§7.3 and §7.4 record three of the four defects closed here; the fourth is in the
pre-registration itself.

---

## The prompt, as issued

> ## Read first (do not skip)
> - `reports/phase-report-17-ws5-analysis-2026-09-14.md` — §1.2, §7.3, §7.4 and §5
> - `reports/phase-report-ws5-prediction-amendment-1-2026-09-10.md` §1, **final
>   paragraph** ("If no arm is flagged at fifteen runs…")
> - `reports/phase-report-ws5-prediction-2026-09-10.md` §2.2 H1, §2.3
> - `git show 729fbfa` — the sentence claiming SHA256SUMS proves what was analysed
> - `docs/25-collection-tooling-rules.md` R13, R14, R14a and the R14 instance list
> - `docs/26-journal-readiness-direction.md` §3 rules 5, 12, 13, 14
> - `README.md` (the `make reproduce-figures` line), `ARTIFACT.md` §5, `Makefile`
>
> ## Context
> Phase 17 produced verdicts on H1–H5 and, in the same pass, found that three of
> the instruments those verdicts rest on claim more than they do. A fourth defect
> is in the pre-registration itself: H2's hypothesis and H2's instrument returned
> opposite answers and the report ruled for the hypothesis. All four are closed
> here, before any finding reaches the manuscript. Nothing in this phase changes a
> measured number — except that §2 may change which measured number H1 is about.
>
> ## Bounds
> - In scope: `scripts/power_analysis.py` and its test, `scripts/` provenance
>   tooling and its test, `Makefile`, `README.md`, `ARTIFACT.md`,
>   `docs/25-collection-tooling-rules.md`, new files under `reports/`, new
>   digest files under `experiments/results/ws5-2026-09-10/**`.
> - Out of scope: **the paper** — zero `.tex` changes again. Also out: any new
>   collection, any edit to an existing report or to a commit message, and any
>   re-run of the phase 17 analysis beyond the recomputation §2 requires.
> - If you find a defect outside scope: record it under "Findings outside scope"
>   and stop.
>
> ## Steps
>
> 1. Commit this prompt as `prompts/phase-18-ws5-integrity.md` before anything else.
>
> 2. **Settle the H2 conflict, and price it.**
>    Amendment 1 §1's final paragraph states the decision rule: flag not fired ⇒
>    mixture reporting omitted, pooled median stands, H2 refuted. The phase 17
>    report rules H2 supported at 0.20 while recording that the flag disagreed.
>    Quote the governing sentence verbatim, state which reading governs and why,
>    and then **compute H1's barrier cost and protocol−barrier under both
>    readings** — as differences of lower-mode medians, and as differences of
>    pooled medians — with intervals, side by side. If the two readings produce
>    different H1 verdicts, that is the headline of this phase. Record the
>    resolution as `reports/phase-report-ws5-prediction-amendment-2-<date>.md`;
>    amendment 1 and the pre-registration stay unedited (rule 5).
>    A pre-registration ambiguity discovered on contact with data is recorded,
>    never silently resolved.
>
> 3. **Give the collection a digest that covers what it claims to cover.**
>    `SHA256SUMS` holds two entries per step — the manifests — so `729fbfa`'s
>    claim that it lets a later pass prove what it analysed is false. Repair,
>    in this order:
>    a. Check first whether anything already inside the run directories binds
>       them — the 612 distinct per-run config digests named in `729fbfa`, or any
>       per-run hash the harness writes. If such a binding exists, say exactly
>       what it covers and what it does not; it may give partial retroactive
>       binding that a digest taken today cannot.
>    b. Produce a real per-run and tree-level digest over the raw tree on the
>       measurement host, via a committed script with a test (rule 14), and track
>       it per step alongside the existing file under a distinct name.
>    c. **State the residual in plain terms:** this tree was hashed on <date>,
>       N days after collection. It binds every future pass. It does not
>       retroactively bind phase 17, and no digest taken now can.
>    d. Record `729fbfa`'s false sentence in
>       `reports/correction-729fbfa-sha256sums-scope-<date>.md`. The commit
>       message is history and is not rewritten.
>
> 4. **R14 instance 8 — an empty section that reads like a verdict.**
>    `--section degeneracy` printed an empty A2 that was indistinguishable from
>    "H2 refuted". Make that impossible: an empty section exits non-zero or emits
>    an explicit sentinel naming what it found nothing for. Rule 13 — exercise the
>    failing branch: add a test that feeds it an input which produces an empty
>    section and asserts the new behaviour fires. A test that only ever sees a
>    populated section is the same decoration this rule exists to catch.
>    Add it to `docs/25` as R14 instance 8, in the same form as the other seven.
>
> 5. **`make reproduce-figures` — decide whether it can pass in a fresh clone at
>    all.**
>    This clone's matrix is an 84-run snapshot; the tracked figures were built
>    from 432. `README.md` puts this command in the first code block a reader
>    sees, and `ARTIFACT.md` maps paper claims to reproduction commands. Either
>    the target runs against tracked frozen inputs and passes for anyone, or the
>    two documents are corrected to state exactly what it needs, where that lives,
>    and that it is not runnable from the clone today.
>    **Do not repoint it at the 84-run snapshot** — that produces different
>    numbers under the same command name, which is worse than a command that
>    fails honestly. Rule 13 applies either way: exercise the branch on which the
>    gate fails and show that it does.
>
> 6. R15: `uv run --frozen pytest -q -ra --strict-markers --cov=aep_core
>    --cov-fail-under=90`, `scripts/validate_citations.py`,
>    `scripts/check_paper_numbers.py`, and the paper built both ways —
>    byte-identical to HEAD's build.
>
> ## Acceptance criteria (all must be true)
> - H1 is reported under both readings, with intervals, and amendment 2 exists.
> - A digest covering the raw run tree is tracked, produced by a committed and
>   tested script, with its temporal limitation stated in the file itself.
> - `correction-729fbfa-*.md` exists; no existing report or commit message edited.
> - `--section degeneracy` cannot print an empty section silently, and the test
>   proving it was seen to fail on the old code.
> - `make reproduce-figures` either passes from a clean clone, or README and
>   ARTIFACT.md say plainly that it does not and what it needs.
> - Suite green, 0 skipped, all gates pass, zero `.tex` files changed.
>
> ## Report
> `reports/phase-report-18-ws5-integrity-<date>.md`: Asked / Done / **H1 under
> both readings** / What each of the four claims said versus what it did / Not
> done and why / Raw outputs / Findings outside scope / Environment.
> Five-line pointer in chat, no more.
>
> ## Still outstanding — do not start here
> - The `always` arm of task 5.1 (`scripts/fsync_always_benchmark.sh`).
> - The class sweep, 4 → 6 sessions, per amendment 1 §2.
> - Applying H1–H5 to §VI-RQ3 and §VIII. **H4's +9.33 pp on POS-ONLY is the
>   finding with the most paper-level consequence** — a sensitivity check
>   predicted null that moved a headline rate — and it waits until the remaining
>   two collections land, so §VI is rewritten once rather than three times.

---

## Corrections, recorded rather than applied silently

None at the time of committing. Any that arise are appended here and repeated in
the phase report.
