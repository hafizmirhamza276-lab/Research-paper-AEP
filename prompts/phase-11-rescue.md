# Phase 11 — Data rescue, gate triage, and host-degradation characterisation

The prompt below is recorded **verbatim**, before any other work in this phase,
per `docs/26-journal-readiness-direction.md` §3 rule 4.

---

## Read first
- reports/phase-report-10-wsl2-native-docker-2026-09-02.md (in full, including the storage-backing enumeration and the four degradation surfaces)
- docs/26-journal-readiness-direction.md §4 WS-2, §2 finding A2, §3 rules
- ARTIFACT.md §5 (the pending raw archive)
- docs/24-revision-backlog.md B1's Phase-8.4 addendum on fault delivery

## Context
Phase 10 found that this host is degrading on four independent surfaces, and that no tracked file records redis_storage_backing for any collection. Both facts point at the same unmanaged risk: the raw evidence for every number in the manuscript — the 432 run directories, results/voided/, and the Phase-8/9 collections under /root/aep and /root/aep-phase8 — exists only on this host, and the metadata needed to interpret it exists only in that host's live state. If the host is lost, the artifact can never be published and the storage-backing question can never be answered.

This phase is therefore rescue and triage, not science. It collects no new claim. Its purpose is to make every later phase possible.

Order matters: do step 1 before anything else, and do not begin step 3 until step 1's manifest verifies.

## Bounds
- In scope: scripts/ (new), docs/ (new files only), reports/ (new), prompts/, ARTIFACT.md (§5 only), the archive output directory, and — for step 2 only — whatever the two failing gates require.
- Out of scope: paper/sections/**, paper/generated/** (except a single make reproduce-figures if step 2 determines that is the correct fix for \HarnessLoc — see step 2), aep_core/**, any re-analysis of any frozen cell.
- Under no circumstances modify, move, or delete anything under any raw run directory. Copy only, read-only, verify by digest.

## Steps

1. RESCUE FIRST. Build the raw evidence archive before touching anything else.
   - Locate every raw run directory that any tracked analysis product was derived from, on every path on this host — the clone's experiments/results/**, /root/aep, /root/aep-phase8, the s3/s4 archives named in Phase 10's enumeration, and results/voided/ wherever it lives. Phase 10's storage-backing section already enumerates these; use it as the starting list and state anything it missed.
   - Write scripts/build_raw_archive.py: deterministic tar (sorted entries, fixed mtimes where the content is what matters, no compression-level nondeterminism), emitting MANIFEST.sha256 with a digest per file and a top-level digest of the manifest itself.
   - Verify the archive is sufficient: extract to a scratch path, run experiments/analyze.py over it, and byte-compare the derived products against the tracked CSVs in experiments/results/**/analysis/. Report every file that matches and every file that does not. A mismatch is a finding, not a failure to hide — report it and state what raw evidence is missing or divergent.
   - Report the archive's total size, file count, run count per collection root, and its top-level digest.
   - Do not upload anything yet. Publication is the next phase; this phase produces a verified archive and its manifest.

2. Gate triage. Two gates fail and pre-date this phase, and \HarnessLoc needs a regeneration Phase 10's bounds forbade.
   - State each failure precisely at the top of the report: the command, the raw output, the commit at which it began failing (bisect if cheap, say so if not), and whether it affects a number in the manuscript or only the artifact's hygiene.
   - Fix only what is unambiguous. \HarnessLoc is a line count, not a result: if make reproduce-figures is the correct regeneration and it changes only that macro, run it, and show the full diff of paper/generated/** in the report so the change is auditable. If it changes anything else, stop and report the diff without committing it.
   - For the other failure, if the fix is not unambiguous, do not guess. Report the diagnosis and the options, and stop on that item.
   - The repository's central credibility claim is that CI is green and the numbers are machine-checked. A red gate that predates this phase is a finding about the project, and the report should say for how long it has been red.

3. Storage backing — recover retrospectively while the host still exists.
   For every raw run directory in step 1's list, determine the filesystem and device its results_root was on at collection time, and the redis_storage_backing in force, using evidence that exists on this host right now: absolute paths recorded anywhere in run artifacts, docker volume inspection, mount tables, container state, file timestamps against known collection windows, and the phase reports' own statements about where they ran.
   - Record the result per root in docs/28-storage-backing-recovery.md with, for each: the determination, the evidence it rests on quoted verbatim, and a confidence of DETERMINED / INFERRED / UNDETERMINED. Never upgrade an inference to a determination.
   - Then restate Phase 10's finding with the recovered information: how many of the 12 §VI paragraphs still span an UNDETERMINED backing, and which.
   - Do not edit the manuscript. Do not re-analyse anything. Establish the facts only; I will decide what the manuscript says about them.

4. Characterise the four degradation surfaces.
   Phase 10 named four. For each: what exactly degraded, the measurement that shows it, whether it is monotonic or intermittent, whether it affects fault delivery specifically, and whether it is recoverable by a reboot, a reinstall, or not at all on this host. Then state the consequence explicitly: which categories of future collection this host can still support at a quality a top-tier venue would accept, and which it cannot. Be concrete about fault delivery, because B1 and WS-3 both turn on it.

5. Report: reports/phase-report-11-rescue-<date>.md
   Sections: Asked / Gate triage (lead with this) / Archive: contents, manifest digest, verification result / Storage backing recovered / Degradation surfaces and what this host can still measure / Not done and why / Findings outside scope.

## Acceptance criteria
- A verified archive exists whose extraction reproduces the tracked analysis products, with every mismatch enumerated.
- MANIFEST.sha256 covers every file; the top-level digest is stated in the report and in ARTIFACT.md §5.
- Every raw run directory on this host is either in the archive or explicitly listed as excluded with a reason.
- Both failing gates are diagnosed with raw output and a stated start commit; any fix applied is shown as a full diff.
- Storage backing is recorded per root with quoted evidence and an explicit confidence level.
- Nothing under any raw run directory was modified (prove it: digests taken before and after).
- Reply in chat in at most 6 lines: archive size and digest, whether verification reproduced the tracked CSVs, the two gate diagnoses in one line each, and how many §VI paragraphs remain UNDETERMINED.

---

# Notes recorded with the prompt, not applied silently

Nothing in this phase was corrected or amended by the operator after issue. This
section exists so that its absence is explicit rather than inferred.

One inherited condition is recorded here because it bears on step 2 and was
decided in a previous phase rather than in this one: Phase 10's report,
*Not done and why* item 1, states that `paper/generated/numbers.tex` was left
stale because ADDITION 3 to the Phase 10 prompt required a harness change and
Phase 10's bounds forbade regenerating `paper/generated/**`. This prompt's step 2
is the explicit, bounded permission to close that.
