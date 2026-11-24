# Stage 3 human and external submission inputs — 2026-08-12

Status: **prepared as a blocker-aware handoff, not an authorization to upload,
release, or submit**. No DOI, deposit, tag, release, arXiv submission, or IEEE
submission was created.

## Files ready for Zenodo or OSF

The exact ready-for-upload set is currently **empty**. A DOI-ready upload must
not be assembled from tracked aggregates while the original 432 raw run
directories and historical `results/voided/` evidence are missing. Mandatory
Stage 3 B2/B3 collection is also blocked by the preflight recorded in
`reports/stage3-pre-run-protocol-2026-08-12.md`.

After those blockers are resolved, the single versioned archive must contain:

- the complete original or fully recollected raw evidence and every Stage 3
  raw run directory;
- every ground-truth ledger, run configuration, ordered seed, event log,
  provider log, summary, environment record, immutable matrix plan, and
  pre-run protocol;
- the complete `results/voided/` tree and all machine-readable void reasons;
- raw-to-analysis provenance, analysis CSVs, generated tables/figures/macros,
  `MANIFEST.csv`, `MANIFEST.md`, and recursive `SHA256SUMS`;
- base Git SHA, collection-source manifest, `uv.lock`, reproduction/retrieval
  instructions, `LICENSE`, and supported third-party notices; and
- this deposit metadata after final human review.

No placeholder archive filename or checksum is presented as uploadable.

## Proposed deposit metadata (not yet a deposit)

- **Title:** *Declared Ambiguity: Agent Execution Protocol (AEP) — Expanded
  Experimental Evidence and Reproducibility Artifact*
- **Version:** `2026.08-stage3` (proposed deposit-version label, not a Git tag)
- **Creators:** Hamza Khan; institutional affiliation and ORCID must be supplied
  and verified by the author before deposit.
- **Description:** Reproducibility package for the AEP manuscript, including
  raw isolated fault-injection runs, independent provider ledgers, immutable
  run plans and seeds, voided attempts, cluster-aware analysis outputs,
  generated manuscript artifacts, and clean-room verification records. The
  description must be narrowed if the full raw archive is not recovered.
- **Keywords:** agent reliability; durable execution; declared ambiguity;
  write-ahead intent; non-idempotent APIs; Redis; fault injection;
  reproducible research; autonomous agents.
- **License:** MIT for repository-authored code and documentation, matching the
  tracked `LICENSE`. Raw data and third-party components require a final rights
  review; do not assume MIT covers third-party material.
- **Related identifier:** repository URL only until a versioned release exists.
  The article DOI and arXiv identifier remain blank.
- **Access:** open only after the secret/path scan and checksum/clean-room audit
  pass. Do not describe the raw evidence as public before deposit and retrieval
  verification.

After a deposit, update and verify all of these locations with the real DOI and
retrieval URL: `CITATION.cff`, `README.md`, `ARTIFACT.md`, manuscript artifact
section, cover letter, arXiv metadata/comments, archive `README`, and release
notes. Resolve the DOI and retrieve the archive independently before changing
availability wording.

## IEEE/TSE requirements checked from official sources

Checked 2026-08-12:

- The IEEE Computer Society's current author-resource page says IEEE
  Transactions on Software Engineering does **not** offer the optional
  double-anonymous review route. The author should therefore prepare the public
  TSE identity/affiliation metadata, while retaining the anonymous build only
  for another venue or an editor's specific instruction:
  <https://www.computer.org/publications/author-resources>.
- The official TSE call describes empirical studies with potential software-
  engineering impact as in scope, identifies TSE as hybrid, and encourages
  associated data publication:
  <https://www.computer.org/digital-library/journals/ts/cfp-ieee-transactions-on-software-engineering>.
- IEEE journals require ORCIDs for authors at peer-review submission; the
  current metadata has no ORCID:
  <https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/tools-for-ieee-authors/>.
- IEEE's article-structure guidance requires author-provided affiliation
  details including department/institution, city, country, and corresponding
  author email. No affiliation may be inferred or fabricated:
  <https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/structure-your-article/>.
- The corresponding author is the publication's contact and has explicit
  authorship responsibilities:
  <https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/ethical-requirements/>.
- IEEE's current AI guidance requires disclosure of AI-generated content,
  identifying the system, affected sections, and level of assistance;
  editing/grammar use is treated separately and disclosure is still recommended
  by the April 2024 guidance:
  <https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/>.

The authoritative TSE submission form must be rechecked at the actual submission
date. This report does not substitute for the live form or author attestations.

## Identity, affiliation, release, and anonymity decisions

- Observable author identity: `Hamza Khan` in the public LaTeX branch and
  `CITATION.cff`; a personal email and GitHub account are present in public
  manuscript/repository metadata.
- **Missing:** verified institutional department, institution, city, country,
  postal code if applicable, ORCID, IEEE membership grade if claimed, and final
  corresponding-author confirmation.
- `v1.0.0-rc1` is the only tag. It peels to
  `31664ca9171935cbeb7718fbd5541b917203d3ee`, 16 commits behind the Stage 2 base
  `c2fffa61961228de8466b12939ef1c578506e7ba`; it is stale and must not label a
  Stage 3 deposit. No replacement tag may be created without authorization.
- For TSE, use the public artifact policy because the current Computer Society
  guidance says TSE does not offer double-anonymous review. If a different venue
  requires anonymity, the author must choose before depositing: a public DOI,
  personal repository URL, and public preprint can defeat anonymity. Do not
  claim both policies simultaneously.

## Observable AI-assistance material

The repository visibly contains `CODEX_PROMPTS.md`, `WEEKEND_CODEX_PROMPTS.md`,
`AEP_CLAUDE_CODE_BUILD_PROMPT.md`, agent/orchestrator descriptions in
`docs/build-log.md`, and numerous audit/review reports. File presence proves
that this material exists; it does **not** prove which system was actually run,
which output was retained, who accepted it, or the assistance level in any
manuscript section. This Stage 3 work also used Codex, but only the author can
confirm the complete history and final disclosure scope.

### Candidate disclosure for author verification — do not insert as fact

> During development and revision, the authors used [confirm systems and
> versions, potentially OpenAI Codex and Anthropic Claude] to assist with
> [confirm: code generation/review, test design, analysis scripting,
> documentation, and/or language editing] in [identify exact manuscript
> sections and artifact files]. The systems' assistance level was [describe
> whether suggestions, drafts, or generated code/text were used]. The authors
> reviewed, tested, and take responsibility for all retained content and
> results. No AI system is an author.

Before insertion, the author must confirm:

1. every AI system actually used, its product/model if known, and dates;
2. whether generated text, figures, code, analysis, or only editing was
   retained;
3. the exact affected manuscript sections and artifact components;
4. the level of generation versus critique/editing;
5. that raw evidence and reported results were independently verified; and
6. the venue's required placement and citation format at submission time.

## Remaining external actions requiring the author

1. Recover the original raw archive or authorize and complete a full
   recollection; unblock B2/B3 infrastructure; pass clean-room reproduction.
2. Supply and verify affiliation, ORCID, corresponding-author data, and final
   author list.
3. Approve the artifact anonymity/publicity policy.
4. Verify the AI-assistance inventory and wording.
5. Approve a release version/tag only after the evidence archive verifies.
6. Upload the verified archive, retrieve it independently, then provide the real
   DOI/URL for repository and manuscript regeneration.
7. Recheck the live TSE requirements and submission metadata, then separately
   authorize any submission.
