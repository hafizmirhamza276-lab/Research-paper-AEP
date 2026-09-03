# Depositing the raw evidence archive — a do-it-by-hand checklist

**For the operator, through the Zenodo web interface. No API token, no script.**
About ten minutes, most of it upload time.

Prepared by Phase 12. The archive itself was built and verified by Phase 11 —
`reports/phase-report-11-rescue-2026-09-03.md`. Nothing here re-derives
anything; every value below is transcribed from that verification and can be
re-checked with the commands in §6.

---

## 0. Before you start: what the leakage scan found

`scripts/scan_archive_for_leakage.py` read all 26 300 files, 493 MB, before
this checklist was written. Full result:
`reports/raw/phase12-leakage-scan.{txt,json}`.

| category | files | distinct values | verdict |
|---|---|---|---|
| credentials, keys, tokens, passwords | **0** | — | clean |
| email addresses | **0** | — | clean |
| OS/account names | **0** | — | clean |
| `C:\Users\<name>` paths | **0** | — | clean |
| MAC addresses | **0** | — | clean |
| GitHub handles/URLs | **0** | — | clean |
| environment dumps | **0** | — | clean |
| hostname | 9 | 1 — `KP248` | present, disclosed below |
| Windows drive path | 153 | 1 — `D:\134` (the 9p device name) | present, disclosed |
| WSL absolute paths | 549 | 200+ — `/root/aep/…` | present, **load-bearing** |
| drvfs paths | 568 | 44 — `/mnt/d/personal/AEP/…` | present, **load-bearing** |
| "non-loopback IP" | 3 717 | 1 — `6.6.114.1` | **false positive**: the kernel version |

**There is no personal identifier of any kind in the archive.** What is there is
a machine name and a directory layout. Both are disclosed in the description in
§3 rather than removed, and §4 of the phase report explains why removal was not
recommended. **Nothing has been stripped; that decision is yours.**

---

## 1. The one file that matters, and its digest

Upload **three** files, in this order (the two small ones first, so a reader
browsing the record sees the map before the territory):

| # | file | size | sha256 |
|---|---|---|---|
| 1 | `MANIFEST.sha256` | 4 287 997 B | `87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7` |
| 2 | `ARCHIVE-METADATA.json` | 15 052 B | `cf75e7232ad9a97ee989760ca05cda758c67d4da0245a7929ba12706f7a220e5` |
| 3 | `aep-raw-evidence.tar.gz` | 24 257 505 B | `fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353` |

They are at **`D:\personal\AEP\aep-raw-archive\`** on the collection host (and
at `/root/aep-raw-archive/` inside WSL — the same bytes, verified by digest when
they were mirrored).

Confirm before uploading, from Windows PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 D:\personal\AEP\aep-raw-archive\aep-raw-evidence.tar.gz
Get-FileHash -Algorithm SHA256 D:\personal\AEP\aep-raw-archive\MANIFEST.sha256
```

If either differs from the table, **stop** — the file has changed since Phase 11
verified it and the description below would be false.

---

## 2. Sandbox first — yes, and here is exactly what to look at

Use **https://sandbox.zenodo.org** for the first pass. It is a throwaway
instance: the DOI it mints is not real and the record can be deleted. The upload
is 24 MB, so a full rehearsal costs a couple of minutes and removes the only
irreversible step from the real run.

On the sandbox record, before you would have published, check:

- [ ] all three files are listed, with the **sizes in §1**;
- [ ] the description renders as headings and a table, not as raw HTML tags;
- [ ] the digest `87fa2d53…` appears in the rendered description and is not
      broken across a line in a way that makes it uncopyable;
- [ ] the related identifier appears as a link to the GitHub repository;
- [ ] the licence shows as **MIT**;
- [ ] the author name renders as you want it cited.

Then delete the sandbox draft and repeat on **https://zenodo.org**.

> **Zenodo records are immutable once published.** New versions can be added,
> but a published file cannot be replaced or withdrawn. Everything above is
> cheap; that step is not.

---

## 3. The metadata, field by field — paste these

**Upload type:** `Dataset`

**Title:**

```
Raw run archive for "Declared Ambiguity: The Agent Execution Protocol (AEP) for Autonomous Agents Calling Non-Idempotent Legacy APIs"
```

**Authors:** `Khan, Hamza` — affiliation as you wish it cited; ORCID if you have
one. This must match `CITATION.cff`, which currently carries
`family-names: Khan`, `given-names: Hamza`.

**Description** — paste the whole block. Zenodo's description field accepts
HTML; this is written for it.

```html
<p>The complete raw evidence behind every quantitative claim in the AEP manuscript: <strong>1&nbsp;458 run directories across 20 collection roots, 26&nbsp;300 files, 492&nbsp;905&nbsp;568 bytes uncompressed</strong>. The GitHub repository linked below tracks only the derived analysis products; this is what they were derived <em>from</em>.</p>

<h3>Files</h3>
<ul>
<li><code>aep-raw-evidence.tar.gz</code> &mdash; the archive, 24&nbsp;257&nbsp;505 bytes, sha256 <code>fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353</code>. Uncompressed it is <code>aep-raw-evidence.tar</code>, sha256 <code>3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94</code>.</li>
<li><code>MANIFEST.sha256</code> &mdash; a SHA-256 for every one of the 26&nbsp;300 files. <strong>The manifest's own sha256 is <code>87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7</code></strong>, and that single digest attests the whole archive.</li>
<li><code>ARCHIVE-METADATA.json</code> &mdash; per collection root: source path, filesystem at archive time, run and file counts, and the derived analysis directory it produced. It also lists <em>every</em> raw run directory on the build host that was excluded, with the reason, so no collection is silently absent.</li>
</ul>

<h3>Contents</h3>
<p>The 432-run <code>matrix</code> evaluation, from which every outcome rate in the paper is computed; <code>fsync-always</code>, the appendfsync=always arm behind every "always" latency and throughput figure; <code>results/voided/</code>, including the excluded oracle-disagreement run and its written explanation; four prevention-replication sessions from 2026-08-21; six paired prevention collections from 2026-08-28, two of them aborted and retained as such; four runtime-replication arms from 2026-09-02; and two arms voided for having been collected against the wrong container runtime, retained because a voided collection is evidence about the instrument.</p>

<h3>Reproducing from it</h3>
<pre>tar xzf aep-raw-evidence.tar.gz
sha256sum -c MANIFEST.sha256
python -m experiments.analyze --results-root matrix --destination /tmp/derived</pre>
<p>Verified before deposit: the archive was extracted, checked file-by-file against the manifest (26&nbsp;300 verified, 0 problems), and <code>analyze.py</code> re-run over the extraction using each root's own recorded bootstrap seed and resample count. Against every analysis product tracked in the repository the result was <strong>114 byte-identical, 8 identical after the two normalisations below, and none differing</strong>.</p>

<h3>Two declared normalisations &mdash; expect these; they are not corruption</h3>
<p>Two changes to <code>experiments/analyze.py</code> postdate the frozen analysis products, so a fresh re-derivation differs from the repository's tracked CSVs in exactly two ways and no others:</p>
<ol>
<li><strong>The crash-always regime's label.</strong> Products frozen on 2026-08-10 write it <code>(session-3)</code>; today's <code>analyze.py</code> writes <code>crashed</code>. Same regime, same rows, different display string. A script joining a frozen CSV to a fresh one on <code>regime</code> will silently select zero rows &mdash; which is why it is stated here rather than left to be discovered.</li>
<li><strong>Two columns added to <code>per-execution.csv</code></strong>: <code>redis_kill_latency_ms</code> and <code>durability_ack_observed</code>. Rows and all pre-existing columns are unchanged, verified at row level: zero differing keys and every shared column agreeing on every row across the 3&nbsp;780 executions of the main matrix.</li>
</ol>
<p>One further point of provenance: <code>matrix/analysis/comparisons-vs-aep-full.csv</code> is the one tracked results file <code>analyze.py</code> did not produce. It was regenerated regime-labelled by <code>experiments/rebuild_comparisons.py</code>, because the original pooled three fault regimes, which the paper's own reporting rule forbids. Run through that script over a fresh re-derivation it is byte-identical.</p>

<h3>Collection host, and what is in these files</h3>
<p>All runs were collected on one host: Ubuntu 24.04 inside WSL2 on Windows 11, kernel 6.6.114.1-microsoft-standard-WSL2, with Redis pinned by digest to <code>redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44</code>. Collections before 2026-09-02 ran under Docker Desktop; those from 2026-09-02 under a native Docker Engine inside the distribution.</p>
<p>The run artifacts contain the host's name (<code>KP248</code>) and absolute filesystem paths (<code>/root/aep/&hellip;</code>, <code>/mnt/d/personal/AEP/&hellip;</code>). These are retained deliberately: they are the evidence from which the collection path of the frozen evaluation was reconstructed, and removing them would invalidate the manifest and delete a determination the analysis depends on. The archive was scanned before deposit and contains no credentials, no email addresses, no account names and no hardware identifiers.</p>
```

**Version:** `1.0.0`

**Language:** `eng`

**Keywords** — one per line:

```
agent reliability
durable execution
write-ahead intent
fail-closed protocol
non-idempotent APIs
distributed coordination
Redis
fault injection
research artifact
raw experimental data
```

**Licence:** `MIT License` — must match the repository's `LICENSE`, which is
MIT, © 2026 Hamza Khan.

**Access right:** `Open Access`

**Related/alternate identifiers:** one entry —

| field | value |
|---|---|
| Identifier | `https://github.com/hafizmirhamza276-lab/Research-paper-AEP` |
| Relation | `is supplement to` |
| Resource type | `Software` |

---

## 4. After publishing: record the two DOIs

Zenodo mints **two**:

* the **version DOI**, which points at this exact deposit — this is the one the
  manuscript cites;
* the **concept DOI**, which always resolves to the newest version — this is the
  one to cite when you mean "the archive" rather than "this version of it".

Both appear on the record page. Write them down; §5 needs them.

---

## 5. Putting the DOI into the repository — one line

The DOI is defined in **exactly one place**:

**`paper/main.tex` line 99**, the `\archivedoi` definition (search for
`\newcommand{\archivedoi}` if the line has moved). It currently reads:

```latex
\newcommand{\archivedoi}{PENDING}
```

Replace `PENDING` with the bare version DOI, e.g. `10.5281/zenodo.1234567`.
Everything else follows automatically:

* `paper/sections/09-artifact.tex` renders "deposited at
  `https://doi.org/…`" instead of "prepared and verified but not yet
  deposited"; **no section file contains a DOI string and none needs editing**;
* the **anonymous build is unaffected by construction** — its branch never reads
  `\archivedoi`, so a DOI cannot leak into `main-anon.pdf` even if inserted.

Then, by hand, in four non-LaTeX files:

- [ ] `ARTIFACT.md` §5 — replace the "not yet uploaded" paragraph with the DOI
- [ ] `CITATION.cff` — add `doi:` and drop the "unreleased revision" `message:`
- [ ] `README.md` — add the DOI badge/line
- [ ] `paper/arxiv-metadata.md` — add the DOI to the submission metadata

- [ ] **Add the CI archive job.** It is deliberately *not* in
      `.github/workflows/ci.yml` yet — a job that cannot fail for the reason it
      was written is decoration, and with no DOI there is nothing for it to
      fetch. Paste this in when the DOI exists, substituting it in one place:

      ```yaml
        # Gate -- the published archive is the archive this repository describes,
        # and the paper's numbers follow from it. Added in the phase that minted
        # the DOI; before that it was recorded as pending in ARTIFACT.md 5
        # rather than added as a job that would pass without checking anything.
        archive:
          name: Published archive
          runs-on: ubuntu-24.04
          steps:
            - uses: actions/checkout@v4
            - uses: astral-sh/setup-uv@v5
            - run: uv sync --frozen --extra experiments --extra analysis
            - name: Verify the deposit and re-derive from it
              run: |
                uv run --frozen python scripts/verify_published_archive.py \
                  --doi 10.5281/zenodo.XXXXXXX \
                  --json archive-verification.json
            - uses: actions/upload-artifact@v4
              if: always()
              with:
                name: archive-verification
                path: archive-verification.json
      ```

      **Test it the way this project tests its gates:** before trusting a green
      run, change one character of `EXPECTED["tar_gz_sha256"]` in
      `scripts/verify_published_archive.py` on a scratch branch and confirm the
      job goes red. A digest check that has never been seen to fail has not been
      tested.
- [ ] **Tag `v1.0.0`** on the commit that carries the DOI edit, not on an
      earlier one. The archive's contents correspond to every commit from
      `c194dc7` onward (`git diff c194dc7..HEAD -- experiments/results/` is
      empty), so the tag should mark the commit whose `ARTIFACT.md` truthfully
      names the deposit.

---

## 6. Post-upload verification — run this, it is the point

```sh
uv run --frozen --extra experiments --extra analysis \
  python scripts/verify_published_archive.py --doi 10.5281/zenodo.XXXXXXX \
  --json reports/raw/verify-published-archive.json
```

It resolves the DOI, downloads the archive **from Zenodo rather than from
disk**, checks both digests against the values this repository tracks, extracts
all 26 300 files and verifies each against `MANIFEST.sha256`, then re-runs
`analyze.py` and byte-compares against the tracked CSVs.

Expected final line:

```
VERIFIED: the archive at this source is byte-for-byte the one this repository
describes, and the paper's analysis products follow from it.
```

Expected comparison line: **`IDENTICAL 114   IDENTICAL-after-normalisation 8
DIFFERS 0`**. Anything else is a finding — report it rather than re-uploading
over it, because a published record cannot be replaced.

The script's own local path (`--local /root/aep-raw-archive`) was exercised in
Phase 12 and passed; **only the fetch-by-DOI half is untested**, because there
was nothing to fetch.
