# Stage 1 external and human blockers — 2026-08-11

This report records work that cannot be completed truthfully from the repository
alone. It is a release checklist, not an availability claim. No DOI, release,
affiliation, disclosure, experiment outcome, or verification result is implied
by an unchecked item.

## Raw-evidence archive and DOI

- [ ] Upload the complete frozen raw evidence to Zenodo or OSF and mint an
  immutable DOI. No working archive URL or DOI is present as of 2026-08-11.
- [ ] Include all 432 raw run directories used by `experiments/analyze.py`.
- [ ] Include `experiments/results/voided/`, especially the excluded
  oracle-disagreement run and its explanation. That directory is not present in
  the current Git working tree.
- [ ] Generate a complete SHA-256 manifest covering every raw file, every
  voided file, the matrix manifest, and all derived analysis products. The
  tracked `experiments/results/matrix/SHA256SUMS` covers 17 listed matrix files,
  only seven of which are present in the Git clone; it is not a complete archive
  manifest.
- [ ] Download the deposited archive into a clean environment, verify the DOI
  resolves, run `sha256sum -c` against the complete manifest, and record the
  exact retrieval and verification commands in `ARTIFACT.md` and the manuscript.
  Do not add a placeholder DOI to submission prose.

The DOI must be integrated at these reviewed points after it exists:

- `ARTIFACT.md` §5: archive asset name, byte size, resolver URL, archive
  SHA-256, extraction command, and complete-manifest verification command;
- `paper/sections/09-artifact.tex`: immutable DOI and an exact statement of
  which evidence it contains;
- `paper/cover-letter-tse.md` and `paper/arxiv-metadata.md`: the same resolver
  URL and immutable release/tag;
- `CITATION.cff`: the real version, release date, DOI, and preferred citation;
- a clean-clone gate that downloads the named asset, verifies the archive hash,
  extracts it, and runs `sha256sum -c` from
  `experiments/results/matrix/`.

The post-extraction checksum command is already exact in `ARTIFACT.md`. An
exact retrieval command cannot be written until the repository has a real
resolver URL and asset filename; inventing either would create a false
availability claim.

## Author-supplied metadata and disclosure

- [ ] Supply and verify the author's institutional affiliation. The repository
  currently contains a name and email but no verified affiliation.
- [ ] Have the author review the actual assistance used and provide the exact
  IEEE-compliant AI-assistance disclosure required by the target policy. The
  repository does not contain enough verified information to write this on the
  author's behalf.
- [ ] Resolve the public-versus-anonymous artifact policy before submission;
  the public repository URL identifies its owner.

## Immutable release

- [ ] After the scientific revision, raw archive, DOI, affiliation, and
  disclosure are final, create a new immutable release/tag that identifies the
  exact reviewed source and derived artifacts. Stage 1 did not create, tag,
  commit, push, or publish a release.
- [ ] Update `CITATION.cff`, arXiv metadata, cover letter, and artifact text only
  with the real tag, DOI, checksum, and verified metadata.

## Experiments requiring unavailable host resources

- [ ] Re-run or extend the full-system block-loss experiment on Linux with root,
  loop-device, device-mapper, `dm-flakey`, and a Docker/Redis setup mounted on
  that device. The current write-loss evidence tests the `WAITAOF` premise, not
  full AEP/B3 outcomes under block loss.
- [ ] Expand the Redis-kill prevention experiment beyond the one measured
  `NO_READBACK` capability, one pre-acknowledgement fault point, 30 runs per
  system, and one host if a broader prevention claim is desired.
- [ ] Collect the implemented in-flight Redis-kill variant, the 30% crash
  regime, alternative read-back keying, and additional run clusters if claims
  beyond the current fixed design or stronger cluster-aware equivalence are
  desired.

These experiments require an appropriate Linux/Docker host and were not
fabricated or marked complete during this revision.
