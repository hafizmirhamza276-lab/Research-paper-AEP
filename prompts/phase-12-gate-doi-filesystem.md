# Phase 12 — Close the red gate, publish the archive, and open the filesystem hypothesis

The prompt below is recorded **verbatim**, before any other work in this phase,
per `docs/26-journal-readiness-direction.md` §3 rule 4.

---

## Read first
- reports/phase-report-11-rescue-2026-09-03.md (in full, especially the two Gate 1 options and the four UNDETERMINED §VI paragraphs)
- docs/28-storage-backing-recovery.md
- reports/phase-report-8-1-0-2026-08-27.md §F (the 40x event-log append cost on drvfs, and the kill-latency race analysis)
- reports/phase-report-9c-result-2026-08-21.md (the over-dispersion 5.37 finding)
- docs/26-journal-readiness-direction.md §4 WS-2 and WS-3

## Context
Three separate things, in this order. The third is the reason for the first two: it is the phase that follows, and it must not begin on a red CI or an unpublished archive.

## Step 1 — Gate 1, the stale-macro test, red since 9545ccb for 2d 18h
Choose between your two options by one criterion, stated in the project's own words: a gate that cannot fail is decoration (README, CI section). Take whichever option leaves the gate able to fail for the reason it was written to catch, even if that option is more work. If both satisfy that, take the simpler and say why.
Then: fix it, prove the fix by making the gate fail deliberately on a scratch commit and pass on the real one, and show both outputs. State in the report how a red gate went unnoticed for 2d 18h and whether anything in CI should have surfaced it sooner. Do not add a new gate for that; just answer the question.
Acceptance: full suite green, 0 skipped, 0 xpassed, coverage >= 90%, citations valid, check_paper_numbers green, reproduce-figures identical — all on one commit, raw output for each.

## Step 2 — Publish the archive and mint the DOI (WS-2, closing finding A2)
I will supply a Zenodo account and a personal access token. Ask me for the token when you need it; do not proceed without it and do not commit it.
- Prepare the Zenodo deposition metadata as a tracked file (title, authors, description, license matching LICENSE, keywords, related identifier pointing at the GitHub repo). The description must state what the archive contains, the manifest digest, and the two declared normalisations Phase 11 found, so a reader reproducing it is not surprised by them.
- Upload the archive and MANIFEST.sha256. Publish. Record the DOI and the concept DOI.
- Tag the repository v1.0.0 on the commit whose state the archive corresponds to. If head has moved since the archive was built, say so and tag the correct commit rather than head.
- Write the DOI into ARTIFACT.md §5, CITATION.cff, README.md, paper/sections/09-artifact.tex, and paper/arxiv-metadata.md. This is the one manuscript edit this phase is permitted, and it is permitted only because §IX currently makes a false availability statement. Show the diff.
- Add a CI job that verifies the archive by digest — either by fetching it or by checking a cached copy's MANIFEST digest — and re-derives per-cell-metrics.csv from it. If fetching in CI is impractical, say why and implement the cached-digest form.
Acceptance: the DOI resolves; §IX's availability sentence is true; the new CI job is green and is itself tested (the project's rule that each gate is tested applies).

## Step 3 — Open the filesystem hypothesis. Establish, do not test yet.
Phase 11 found that the four §VI paragraphs whose results_root backing is UNDETERMINED are exactly the b2-*-2026-08-21 collections, which include the \UnwantedPrevented paragraph. Phase 8.1 measured a 40x cost difference on event-log appends between ext4 and drvfs. The prevention result's mechanism is a race: AEP-full dispatches only if WAITAOF returns before the kill lands. A systematic per-session difference in append cost would shift where each session sat in that race.

The hypothesis is therefore: the 4-20/30 spread in AEP-full's unwanted-applied count across the five sessions, which Phase 9C recorded as over-dispersion 5.37 and left unexplained, is partly or wholly explained by the results_root filesystem differing between sessions.

This step establishes whether the hypothesis is checkable from evidence that already exists. Do not collect anything.
- For each of the five sessions (the original b2-2026-08-21 cell and the four b2-paired-v2-* replications), determine the results_root filesystem with the method and confidence levels of docs/28-storage-backing-recovery.md. If a session is UNDETERMINED, say exactly what evidence would determine it and whether that evidence still exists on this host.
- Cross-tabulate, per session: results_root filesystem, AEP-full unwanted-applied count out of 30, B3's count, the recorded docker kill landing latency distribution if present, and the event-log append timing if recoverable from the run artifacts.
- State whether the sessions' filesystems actually vary. If they do not vary, the hypothesis is dead from existing data and you should say so plainly and stop the step there — that is a useful result and it saves the next phase.
- If they do vary, state whether the variation aligns with the count variation, and how many sessions sit on each side. Four sessions cannot establish a cause; do not claim one. Report the alignment as an observation with its n, and state what a designed test would need — that design is the next phase's, not this one's.
- Write this into reports/phase-report-12-filesystem-hypothesis-<date>.md as its own document, separate from the phase report, because the next phase will build on it directly.

Do not edit paper/sections/06-evaluation.tex. Do not re-analyse any frozen cell. Do not adjust \UnwantedPrevented.

## Bounds
- In scope: scripts/, docs/ (new), reports/ (new), prompts/, .github/workflows/ci.yml, ARTIFACT.md, CITATION.cff, README.md, paper/sections/09-artifact.tex and paper/arxiv-metadata.md (DOI only), the Zenodo metadata file.
- Out of scope: every other manuscript section, paper/generated/** except as a consequence of the gate fix, aep_core/**, all frozen results.

## Report
reports/phase-report-12-<date>.md with: Asked / Gate 1: option chosen and why, deliberate-failure proof, why it went unnoticed / Archive publication: DOI, concept DOI, tag, CI job / Filesystem hypothesis: the cross-tabulation, whether it is checkable, verdict / Not done and why / Findings outside scope.

Reply in chat in at most 6 lines: the DOI, whether all gates are green on one commit, and the filesystem hypothesis verdict in one sentence.

---

# Notes recorded with the prompt, not applied silently

No correction or amendment was issued by the operator after this prompt. This
section exists so that its absence is explicit rather than inferred.

Two conditions carried in from earlier phases bear on it and were decided
elsewhere, not here:

1. **Step 1's two options are Phase 11's, not this phase's.** They are stated in
   `reports/phase-report-11-rescue-2026-09-03.md` §"Gate triage / G1": (a) delete
   the test, (b) invert it to assert the macro is deliberately absent. Phase 11
   recommended (b) and deliberately did not apply it, because the prompt of that
   phase said not to guess. This prompt supplies the criterion for choosing.

2. **Step 2 requires a credential this session does not hold.** The Zenodo
   personal access token must be supplied by the operator. Nothing is uploaded,
   published or committed before it is.
