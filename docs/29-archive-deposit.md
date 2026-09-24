# Depositing the raw evidence archive — a do-it-by-hand checklist

**For the operator, through the Zenodo web interface. No API token, no script.**
About twenty minutes, most of it upload time.

**Read §0 first. It tells you the one thing that is easy to get wrong and
impossible to undo.**

Rewritten 2026-09-16. The previous version was written in Phase 12 for a single
archive and amended twice at the top without the body being updated, so §1 told
you to upload three files while §0b said the deposit was two archives, and §5
told you to replace a `PENDING` that no longer exists. Every step below has been
re-checked against the tree as it stands.

---

## 0. The shape of the deposit, and the two ways to ruin it

**One record. Two archives. Six files. One DOI — the one that already exists.**

```
https://doi.org/10.5281/zenodo.22766567     <- RESERVED, already a draft
├── aep-raw-evidence-2026-09-03.tar.gz        from /root/aep-raw-archive
├── MANIFEST-2026-09-03.sha256                from /root/aep-raw-archive
├── ARCHIVE-METADATA-2026-09-03.json          from /root/aep-raw-archive
├── aep-raw-evidence-2026-09-15.tar.gz        from /root/aep-raw-archive-ext
├── MANIFEST-2026-09-15.sha256                from /root/aep-raw-archive-ext
└── ARCHIVE-METADATA-2026-09-15.json          from /root/aep-raw-archive-ext
```

**Ruin #1 — creating a new record.** `10.5281/zenodo.22766567` is *reserved*: a
draft record already holds it, and that identifier is already written into
`paper/main.tex`, the built PDF, `README.md`, `ARTIFACT.md` and `docs/36`.
**Open the existing draft and upload into it.** Creating a new record mints a
*different* DOI and orphans every one of those references. There is no step
anywhere in this checklist that creates a record on zenodo.org.

**Ruin #2 — uploading one archive.** Both are required. The extension carries
the WS-5 deployment sweep, the real-Temporal baseline and the write-loss cell —
numbers §VI of the paper states. §6's verifier now refuses a record that is
missing any of the six files, but that check runs *after* publication and a
published record cannot be replaced.

### Why one record rather than two

Decided 2026-09-16. Two archives under one identifier, not two identifiers:

* the reserved DOI already exists and is already committed into the manuscript,
  and `\archivedoi` is a scalar that the whole three-state switch in
  `paper/main.tex` assumes. Two records would mean a second reserved DOI, a
  second macro, a second availability clause in §9, and the anonymity check
  extended to a second identifier;
* it is one evidence set behind one paper. A reviewer should cite one thing;
* Zenodo's versioning is for successive versions of one deposit, not for two
  halves of one. Sibling records invite "which one is *the* archive?".

The cost is that four filenames collide, which §1 handles.

### The filenames are date-suffixed, and the manifests are not

Both archive roots hold files named `aep-raw-evidence.tar.gz`,
`MANIFEST.sha256` and `ARCHIVE-METADATA.json`. One record cannot hold two files
with the same name, so **the deposited copies carry a date suffix**. Renaming a
file does not change its bytes, so every digest in §1 is equally a digest of the
local file and of the deposited one.

**This must be said in the record's description, and §3 says it.** A reader who
downloads `aep-raw-evidence-2026-09-03.tar.gz`, extracts it and runs
`sha256sum -c MANIFEST-2026-09-03.sha256` will find the manifest naming paths
*inside* the archive, which carry no suffix — that is correct and is not a
mismatch. The suffix exists only at the record level.

---

## 0a. This deposit is not a formality

Every copy of the raw evidence is on **one machine**. Both archives exist twice:
in the WSL distro's ext4 image (`/root/aep-raw-archive`,
`/root/aep-raw-archive-ext`) and on the Windows volume
(`/mnt/d/personal/AEP/aep-raw-archive`, `…-ext`). Verified clean 2026-09-16 —
26 300/26 300 and 18 494/18 494 files, 0 failed, 0 missing — which is the good
news and also the whole exposure: verified copies on the same host are
redundancy against deletion, not against loss.

**What made this concrete.** On 2026-09-14 a collection script's default-on
clean path deleted a frozen results directory, and the loss was reported as
permanent in a committed file before anyone looked at the archive (`docs/25`
R16 and R14 instance 9). The data survived, because of an artefact with no DOI,
no external location and no reference from inside the repository — and the
recovery took a direct instruction to go and look for it.

So the deposit is **the first copy that survives this host, and the first one a
reader can reach without being told where to look.**

---

## 0b. What the deposit does NOT contain, named

Silence is not a disposition. Two referenced collection trees are excluded:

* **`/root/aep-5b`** (220 MB). Its only run directories are
  `/root/aep-5b/repo/.scratch/reproduce/smoke` — seven runs of
  `make reproduce-smoke`, which that target regenerates on every invocation.
  The 2026-09-03 archive already excluded this path by name, with the same
  reason. Nothing in the manuscript derives from it.
* **`/root/aep-stage3`** (224 MB). **Zero run directories.** A source checkout —
  `ARTIFACT.md`, `CHANGELOG.md`, `LICENSE`, briefs and prompts — not a
  collection. The code is in git history; no number derives from it.

A reader can recompute every number in the manuscript without either.
`docs/36` §4 lists every path this repository names that lives outside it.

---

## 0c. What the leakage scan found

`scripts/scan_archive_for_leakage.py` read all 26 300 files of the 2026-09-03
archive, 493 MB, before this checklist was written. Full result:
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
| hostname | 9 | 1 — `KP248` | present, disclosed in §3 |
| Windows drive path | 153 | 1 — `D:\134` (the 9p device name) | present, disclosed |
| WSL absolute paths | 549 | 200+ — `/root/aep/…` | present, **load-bearing** |
| drvfs paths | 568 | 44 — `/mnt/d/personal/AEP/…` | present, **load-bearing** |
| "non-loopback IP" | 3 717 | 1 — `6.6.114.1` | **false positive**: the kernel version |

**There is no personal identifier of any kind.** What is there is a machine name
and a directory layout, both disclosed in §3 rather than removed.

> **The extension archive has not been through this scan.** It was built after
> it (phase 35) and carries the same kind of content from the same host, but
> "the same kind of content" is an inference, not a scan. If that matters to
> you, run
> `python scripts/scan_archive_for_leakage.py --root /root/aep-raw-archive-ext`
> before uploading and record the result beside the first.

---

## 1. The six files, their digests, and where they are

| # | deposited as | from | bytes | sha256 |
|---|---|---|---|---|
| 1 | `MANIFEST-2026-09-03.sha256` | `aep-raw-archive/MANIFEST.sha256` | 4 287 997 | `87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7` |
| 2 | `ARCHIVE-METADATA-2026-09-03.json` | `aep-raw-archive/ARCHIVE-METADATA.json` | 15 052 | `cf75e7232ad9a97ee989760ca05cda758c67d4da0245a7929ba12706f7a220e5` |
| 3 | `aep-raw-evidence-2026-09-03.tar.gz` | `aep-raw-archive/aep-raw-evidence.tar.gz` | 24 257 505 | `fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353` |
| 4 | `MANIFEST-2026-09-15.sha256` | `aep-raw-archive-ext/MANIFEST.sha256` | 3 027 470 | `54d1ab0fc1e55283dc0aa1dabf121b047c432063d077074c3c45728735d63cd5` |
| 5 | `ARCHIVE-METADATA-2026-09-15.json` | `aep-raw-archive-ext/ARCHIVE-METADATA.json` | 8 650 | `91fbd343d255b3023ed36074a09db4c096e1091fdda967f09609b835d6d486a2` |
| 6 | `aep-raw-evidence-2026-09-15.tar.gz` | `aep-raw-archive-ext/aep-raw-evidence.tar.gz` | 17 563 367 | `6ef11d7c88eef5927f478941f7df71ae25685fdb153afd636fe0250dd37eebf1` |

Upload the small files before the big ones, so a reader browsing the record sees
the map before the territory.

**Where they are.** Both archives exist in two places, the same bytes:

| | WSL | Windows |
|---|---|---|
| 2026-09-03 | `/root/aep-raw-archive/` | `D:\personal\AEP\aep-raw-archive\` |
| 2026-09-15 | `/root/aep-raw-archive-ext/` | `D:\personal\AEP\aep-raw-archive-ext\` |

> **Do not select the whole folder in the upload dialog.**
> `D:\personal\AEP\aep-raw-archive\` also contains two loose run directories,
> `ws6-b5-s1-2026-09-08\` and `ws6-b5-s1-2026-09-08-attempt3\`, sitting beside
> the archive files. They are collection output, not deposit files, and their
> contents are already inside the tarballs. Select the three files by name.

**The uncompressed `.tar` is only in WSL.** The Windows copies hold the `.tar.gz`
but not the `.tar`. §3's description publishes the `.tar` digest and §6 checks
it, so if you are working from Windows only, regenerate it:

```sh
gunzip -k -c aep-raw-evidence.tar.gz > aep-raw-evidence.tar
sha256sum aep-raw-evidence.tar
```

gzip decompression is deterministic, so this reproduces the original bytes
exactly. Expect `3aa90b21…` for 2026-09-03 and `61ecd2a4…` for 2026-09-15.

**Confirm every digest before uploading**, from Windows PowerShell:

```powershell
cd D:\personal\AEP
Get-FileHash -Algorithm SHA256 aep-raw-archive\aep-raw-evidence.tar.gz
Get-FileHash -Algorithm SHA256 aep-raw-archive\MANIFEST.sha256
Get-FileHash -Algorithm SHA256 aep-raw-archive\ARCHIVE-METADATA.json
Get-FileHash -Algorithm SHA256 aep-raw-archive-ext\aep-raw-evidence.tar.gz
Get-FileHash -Algorithm SHA256 aep-raw-archive-ext\MANIFEST.sha256
Get-FileHash -Algorithm SHA256 aep-raw-archive-ext\ARCHIVE-METADATA.json
```

Or, from WSL, in one command that checks all six against this repository's own
table and needs no eyeballing:

```sh
uv run --frozen --extra experiments --extra analysis python \
  scripts/verify_published_archive.py \
  --local /root/aep-raw-archive --local /root/aep-raw-archive-ext \
  --skip-rederive
```

If anything differs from the table, **stop** — a file has changed since it was
verified and the description below would be false.

---

## 2. Rehearse on the sandbox, including the verifier

Use **https://sandbox.zenodo.org** for the first pass. It is a throwaway
instance: the DOI it mints is not real and the record can be deleted. The upload
is 42 MB, so a full rehearsal costs a few minutes and removes the only
irreversible step from the real run.

On the sandbox you *do* create a record — that is the point of a sandbox, and it
is the only place in this checklist where you create anything. Create it, upload
all six files, paste §3's metadata, and **publish it on the sandbox** so it gets
a resolvable sandbox DOI.

Then check, before you would have published for real:

- [ ] all six files are listed, with the **sizes in §1**;
- [ ] the description renders as headings and a table, not as raw HTML tags;
- [ ] both digests `87fa2d53…` and `54d1ab0f…` appear in the rendered
      description and are not broken across a line in a way that makes them
      uncopyable;
- [ ] the paragraph explaining the date suffixes is present and readable;
- [ ] the related identifier appears as a link to the GitHub repository;
- [ ] the licence shows as **MIT**;
- [ ] the author name renders as you want it cited.

**Then run the verifier against the sandbox DOI.** This is the only opportunity
to exercise the fetch-by-DOI path before the irreversible step, and that path is
the half of the script that has never run:

```sh
uv run --frozen --extra experiments --extra analysis python \
  scripts/verify_published_archive.py \
  --doi 10.5281/zenodo.<sandbox-id> \
  --json /tmp/sandbox-verification.json
```

Point it at `sandbox.zenodo.org` by editing the `api` URL in `resolve_doi` on a
scratch branch if the sandbox host is not reachable from the production API
path; revert that edit afterwards. Expect the same final line §6 expects.

**Also confirm the gate can fail.** Delete one of the six files from the sandbox
record and re-run: it must exit non-zero with *"the record … is missing 1 of 6
required files"*. A gate that has never been seen to fail has not been tested.

Then delete the sandbox draft and go to §3 for real — **into the existing
draft**, not a new record.

> **Zenodo records are immutable once published.** New versions can be added,
> but a published file cannot be replaced or withdrawn. Everything above is
> cheap; publishing is not.

---

## 3. The metadata, field by field — paste these

Open **https://zenodo.org/deposit** → your draft holding
`10.5281/zenodo.22766567` → Edit.

**Upload type:** `Dataset`

**Title:**

```
Raw run archive for "Declared Ambiguity: The Agent Execution Protocol (AEP) for Autonomous Agents Calling Non-Idempotent Legacy APIs"
```

**Authors:** `Khan, Hamza` — affiliation as you wish it cited; ORCID
`0009-0005-9380-2188`. This must match `CITATION.cff`, which carries
`family-names: Khan`, `given-names: Hamza`.

**Description** — paste the whole block. Zenodo's description field accepts
HTML; this is written for it.

```html
<p>The complete raw evidence behind every quantitative claim in the AEP manuscript, in <strong>two archives deposited together under this one DOI</strong>: <strong>31 collection roots, 2&nbsp;790 run directories, 44&nbsp;794 files, 848&nbsp;397&nbsp;830 bytes uncompressed</strong>. The GitHub repository linked below tracks only the derived analysis products; this is what they were derived <em>from</em>.</p>

<h3>Files, and why their names carry dates</h3>
<p>Each archive was built with its files named <code>aep-raw-evidence.tar.gz</code>, <code>MANIFEST.sha256</code> and <code>ARCHIVE-METADATA.json</code>. One record cannot hold two files of the same name, so <strong>the deposited copies carry a date suffix</strong>. The bytes are untouched: each digest below is equally a digest of the file as built and of the file as deposited. <strong>The manifests name paths <em>inside</em> their archive, which carry no suffix</strong> &mdash; so extracting <code>aep-raw-evidence-2026-09-03.tar.gz</code> and running <code>sha256sum -c MANIFEST-2026-09-03.sha256</code> verifies correctly, and the absence of the suffix in the manifest is not a mismatch.</p>
<ul>
<li><strong>2026-09-03 archive</strong> &mdash; 20 collection roots, 1&nbsp;458 run directories, 26&nbsp;300 files, 492&nbsp;905&nbsp;568 bytes uncompressed.
<ul>
<li><code>aep-raw-evidence-2026-09-03.tar.gz</code> &mdash; 24&nbsp;257&nbsp;505 bytes, sha256 <code>fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353</code>. Uncompressed it is 520&nbsp;396&nbsp;800 bytes, sha256 <code>3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94</code>.</li>
<li><code>MANIFEST-2026-09-03.sha256</code> &mdash; a SHA-256 for every one of the 26&nbsp;300 files. <strong>The manifest's own sha256 is <code>87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7</code></strong>, and that single digest attests that archive.</li>
<li><code>ARCHIVE-METADATA-2026-09-03.json</code> &mdash; per collection root: source path, filesystem at archive time, run and file counts, and the derived analysis directory it produced. It also lists <em>every</em> raw run directory on the build host that was excluded, with the reason.</li>
</ul></li>
<li><strong>2026-09-15 extension</strong> &mdash; 11 collection roots, 1&nbsp;332 run directories, 18&nbsp;494 files, 355&nbsp;492&nbsp;262 bytes uncompressed.
<ul>
<li><code>aep-raw-evidence-2026-09-15.tar.gz</code> &mdash; 17&nbsp;563&nbsp;367 bytes, sha256 <code>6ef11d7c88eef5927f478941f7df71ae25685fdb153afd636fe0250dd37eebf1</code>. Uncompressed it is 375&nbsp;429&nbsp;120 bytes, sha256 <code>61ecd2a41cb38708ccb1b6bbc507b4248b95c76cb3bef8ed8f3468dae13813e3</code>.</li>
<li><code>MANIFEST-2026-09-15.sha256</code> &mdash; a SHA-256 for every one of the 18&nbsp;494 files, its own sha256 <code>54d1ab0fc1e55283dc0aa1dabf121b047c432063d077074c3c45728735d63cd5</code>.</li>
<li><code>ARCHIVE-METADATA-2026-09-15.json</code> &mdash; the same per-root record for the extension.</li>
</ul></li>
</ul>
<p><strong>The two manifests share no path, and each is verified only against its own.</strong> There is no combined manifest; inventing one at upload time would be a new artefact nobody has verified.</p>

<h3>Contents</h3>
<p><strong>2026-09-03 &mdash; 20 roots.</strong> The 432-run <code>matrix</code> evaluation, from which every outcome rate in the paper is computed; <code>fsync-always</code>, the <strong>six-run</strong> 2026-08-07 appendfsync=always arm; <code>voided/</code>, the excluded oracle-disagreement run and its written explanation; four prevention-replication sessions from 2026-08-21; six paired prevention collections from 2026-08-28, two of them aborted and retained as such; four runtime-replication arms from 2026-09-02; and two arms voided for having been collected against the wrong container runtime.</p>
<p><strong>2026-09-15 &mdash; 11 roots.</strong> The WS-4 block-level write-loss cell and its voided first attempt; the real-Temporal (B5) baseline, attempt 3 with the superseded attempt 2 and the voided attempt 1; the three phase-13 controlled-prevention sessions with the voided session-3 attempt stopped at run 152; and the two phase-13 in-flight-kill sessions.</p>
<p><strong>2026-09-24 &mdash; 9 roots.</strong> The trees neither earlier part reached. <strong>WS-5's deployment sweep</strong>: the 15-run crash-free <code>everysec</code> arm behind Section 6.4's barrier cost, the 30% crash-probability regime, the alternative read-back keying cell, and the incomplete sibling of the first. The <strong>45-run</strong> 2026-09-14 appendfsync=always arm &mdash; a different collection from the six-run <code>fsync-always</code> in the 2026-09-03 part, and the manuscript quotes both. And the phase-40 agent-reachability workstream's committed text evidence: the deployment metadata behind its first amendment, and stages 10, 30 and 100.</p>
<p><strong>A correction, stated rather than quietly fixed.</strong> Until 2026-09-24 this description claimed the 2026-09-15 extension contained &ldquo;the WS-5 deployment sweep &hellip; and the 45-run appendfsync=always extension&rdquo;. <strong>It did not.</strong> Those five roots were in neither part, and eighteen macros in the manuscript derive from them. They were missed rather than declined: the archive builder emitted one shared exclusion list into every part, so the extension's <code>ARCHIVE-METADATA.json</code> declared the first archive's exclusions and said nothing about its own coverage. The 2026-09-24 part carries them, its metadata names the omission as an exclusion of its own, and <code>scripts/check_archive_covers_macros.py</code> now fails if any root supplying a macro is absent from every part.</p>

<h3>Counting run directories</h3>
<p>A run directory is one holding a single run's artifacts, identified by an <code>-r&lt;N&gt;</code> name or by a <code>run-config.json</code>. <strong>The two tests do not agree, and the difference is a real property of the deposit rather than an error.</strong> In the 2026-09-03 archive one directory is named <code>&hellip;-r1.attempt-1</code> and so fails the name test: 1&nbsp;457 by name, 1&nbsp;458 by config, 1&nbsp;458 in all. In the extension 340 directories across four roots hold run artifacts with no <code>run-config.json</code>, because the B5 baseline runs through <code>session.py</code> rather than <code>run_matrix</code>: 1&nbsp;332 by name, 992 by config, 1&nbsp;332 in all. <strong>The per-root <code>runs</code> field in <code>ARCHIVE-METADATA-2026-09-15.json</code> therefore sums to 992, not 1&nbsp;332</strong>, because its counter counts run-configs. Both numbers are correct answers to different questions, and <code>scripts/verify_published_archive.py</code> prints all three.</p>

<h3>Reproducing from it</h3>
<pre>tar xzf aep-raw-evidence-2026-09-03.tar.gz
sha256sum -c MANIFEST-2026-09-03.sha256
python -m experiments.analyze --results-root matrix --destination /tmp/derived</pre>
<p>Verified before deposit: each archive was extracted and checked file-by-file against its own manifest &mdash; 26&nbsp;300 and 18&nbsp;494 entries, 0 problems, 0 missing. For the 2026-09-03 archive, <code>analyze.py</code> was additionally re-run over the extraction using each root's own recorded bootstrap seed and resample count; against every analysis product tracked in the repository the result was <strong>114 byte-identical, 8 identical after the two normalisations below, and none differing</strong>. <strong>That re-derivation has not been repeated for the 2026-09-15 extension</strong>, which is stated here rather than left to be assumed.</p>

<h3>Two declared normalisations &mdash; expect these; they are not corruption</h3>
<p>Two changes to <code>experiments/analyze.py</code> postdate the frozen analysis products, so a fresh re-derivation differs from the repository's tracked CSVs in exactly two ways and no others:</p>
<ol>
<li><strong>The crash-always regime's label.</strong> Products frozen on 2026-08-10 write it <code>(session-3)</code>; today's <code>analyze.py</code> writes <code>crashed</code>. Same regime, same rows, different display string. A script joining a frozen CSV to a fresh one on <code>regime</code> will silently select zero rows &mdash; which is why it is stated here rather than left to be discovered.</li>
<li><strong>Two columns added to <code>per-execution.csv</code></strong>: <code>redis_kill_latency_ms</code> and <code>durability_ack_observed</code>. Rows and all pre-existing columns are unchanged, verified at row level: zero differing keys and every shared column agreeing on every row across the 3&nbsp;780 executions of the main matrix.</li>
</ol>
<p>One further point of provenance: <code>matrix/analysis/comparisons-vs-aep-full.csv</code> is the one tracked results file <code>analyze.py</code> did not produce. It was regenerated regime-labelled by <code>experiments/rebuild_comparisons.py</code>, because the original pooled three fault regimes, which the paper's own reporting rule forbids. Run through that script over a fresh re-derivation it is byte-identical.</p>

<h3>Every run's configuration verifies against its own digest</h3>
<p>Each run records a <code>config_digest</code> over every configuration field that could change a number. <strong>All 432 runs of the evaluation verify</strong>, and they are verified <em>per schema generation</em>: the harness's configuration grew twice during the evaluation, and the digest is computed over the field set in force when the run was collected, so checking a 2026-08-06 run against the final field set asks the wrong question. Three generations exist &mdash; 35 fields, 38, and 42 &mdash; and every stored digest is reproduced exactly by the generation in force at its run's collection, with <strong>none unexplained</strong>.</p>
<p><strong>What the check proves and what it does not:</strong> it proves each run's recorded configuration is the one its digest was computed over, so a field altered afterwards is caught and so is a digest matching no generation. It is a <em>tamper</em> check, not a correctness check &mdash; it says nothing about whether the configuration was the right one or whether the fault it names was delivered.</p>

<h3>Collection host, and what is in these files</h3>
<p>All runs were collected on one host: Ubuntu 24.04 inside WSL2 on Windows 11, kernel 6.6.114.1-microsoft-standard-WSL2, with Redis pinned by digest to <code>redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44</code>. Collections before 2026-09-02 ran under Docker Desktop; those from 2026-09-02 under a native Docker Engine inside the distribution.</p>
<p>The run artifacts contain the host's name (<code>KP248</code>) and absolute filesystem paths (<code>/root/aep/&hellip;</code>, <code>/mnt/d/personal/AEP/&hellip;</code>). These are retained deliberately: they are the evidence from which the collection path of the frozen evaluation was reconstructed, and removing them would invalidate the manifests. The 2026-09-03 archive was scanned before deposit and contains no credentials, no email addresses, no account names and no hardware identifiers.</p>
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

Then **Publish**. The DOI begins resolving within a few minutes.

---

## 4. After publishing: record the two DOIs

Zenodo shows **two**:

* the **version DOI**, pointing at this exact deposit. `10.5281/zenodo.22766567`
  is this one — a DOI reserved on a draft is that draft's version DOI, so the
  identifier already in the manuscript is already the right kind. **It should
  not change when you publish.** If it has, stop: something created a new
  record, and §5 onwards is wrong until that is resolved;
* the **concept DOI**, always resolving to the newest version. Record it in
  `docs/36` for completeness. The manuscript does not cite it.

---

## 5. Putting it into the repository

**The DOI is already in `paper/main.tex` and does not need to be typed.** What
moves is the *state*.

`paper/main.tex` line 125–126:

```latex
\newcommand{\archivedoi}{10.5281/zenodo.22766567}     <- leave this alone
\newcommand{\archivedoistate}{RESERVED}               <- change this one
```

Change `RESERVED` to `PUBLISHED`. Anything that is neither `PENDING` nor
`RESERVED` selects the resolving branch; `PUBLISHED` is the conventional value.

Verified by dry run on 2026-09-16 — **exactly one sentence in the manuscript
changes**, §9's availability sentence, from

> …carried by a separate archive, prepared and verified, with the Zenodo record
> reserved under DOI 10.5281/zenodo.22766567; the identifier is fixed and begins
> resolving when the record is published.

to

> …carried by a separate archive, **deposited at
> https://doi.org/10.5281/zenodo.22766567.**

Page count is unchanged at 23, and `main-anon.pdf` is byte-identical in text
before and after: the anonymous branch never reads `\archivedoi`, so a DOI
cannot leak into the anonymous build.

**No `.tex` file other than `main.tex` needs editing. No section file contains a
DOI string** — audited 2026-09-16 across `main.tex`, `sections/*.tex`,
`generated/*.tex`, `figures/*.tex` and `refs.bib`: one literal, at
`main.tex:125`.

### Then, by hand, in five non-LaTeX files

Each with its current line, so you can find it:

- [ ] **`README.md:8`** — "with a Zenodo record reserved under DOI …" → deposited
- [ ] **`README.md:10–13`** — delete the whole "**The DOI does not resolve yet**"
      block quote
- [ ] **`ARTIFACT.md:348–356`** — the "**Not yet published externally**"
      paragraph: "the record is a draft and the files are not uploaded, so the
      DOI does not resolve yet" → the published form, and strike the three
      "still pending" items
- [ ] **`CITATION.cff:24–27`** — "A Zenodo record is RESERVED under DOI …: the
      identifier is fixed, the record is still a draft … so it does not resolve
      yet" → the published form
- [ ] **`CITATION.cff:2`** — `message:` "describes an unreleased revision"
- [ ] **`CITATION.cff:33–42`** — the `identifiers:` block already carries the
      DOI and says RESERVED in its `description:`. Drop that word and promote
      the value to a top-level `doi:` as well, which is the field tools read
- [ ] **`paper/arxiv-metadata.md:32–35`** — the comments-field block
- [ ] **`paper/arxiv-metadata.md:38–45`** — "Where the DOI comes from"; it
      already points at `\archivedoistate`, so only the "reserved, not
      resolving" sentence changes
- [ ] **`paper/arxiv-metadata.md:203–207`** — the release checklist item
- [ ] **`docs/36-repository-inventory-2026-09-15.md:189`** — "**reserved, not yet
      resolving**"
- [ ] **`docs/29` §0, §0c, §4** — this file: the DOI is no longer reserved

### Then the CI job

It is deliberately *not* in `.github/workflows/ci.yml` yet — a job that cannot
fail for the reason it was written is decoration, and with no resolving DOI
there is nothing for it to fetch. Paste this in when the DOI resolves:

```yaml
  # Gate -- the published record is the deposit this repository describes, both
  # archives, and the paper's numbers follow from it. Added in the phase that
  # published the record; before that it was recorded as pending in ARTIFACT.md
  # §5 rather than added as a job that would pass without checking anything.
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
            --doi 10.5281/zenodo.22766567 \
            --json archive-verification.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: archive-verification
          path: archive-verification.json
```

**Test it the way this project tests its gates:** on a scratch branch, change
one character of a `tar_gz_sha256` in `ARCHIVES` in
`scripts/verify_published_archive.py` and confirm the job goes red. A digest
check that has never been seen to fail has not been tested.

### Then close it out

- [ ] Rebuild all four documents, supplementaries first — this order is not
      arbitrary, each build runs the staleness gate and the main build refuses
      to promote while a sibling disagrees:

      ```sh
      bash scripts/build_paper.sh --supplementary
      bash scripts/build_paper.sh --supplementary --anonymous
      bash scripts/build_paper.sh --anonymous
      bash scripts/build_paper.sh
      ```

- [ ] `uv run --frozen python scripts/check_paper_numbers.py` — expect
      **43 passed, 0 failed**
- [ ] Confirm the anonymous build is still DOI-free:

      ```sh
      pdftotext paper/main-anon.pdf - | grep -ci "10.5281\|zenodo\|22766567"
      ```

      Expect `0`. The anonymity check inside `check_paper_numbers.py` covers
      this too, but run it directly: it costs nothing and it is the one leak
      that cannot be withdrawn.
- [ ] `uv run --frozen pytest -q` — expect 2 081 passed, 34 skipped
- [ ] **Tag `v1.0.0`** on the commit carrying the state flip, not an earlier
      one. The archive's contents correspond to every commit from `c194dc7`
      onward (`git diff c194dc7..HEAD -- experiments/results/` is empty), so the
      tag marks the commit whose `ARTIFACT.md` truthfully names the deposit.

---

## 6. Post-upload verification — run this, it is the point

```sh
uv run --frozen --extra experiments --extra analysis \
  python scripts/verify_published_archive.py --doi 10.5281/zenodo.22766567 \
  --json reports/raw/verify-published-archive.json
```

It resolves the DOI, **confirms the record carries all six files and refuses if
it does not**, downloads both archives **from Zenodo rather than from disk**,
checks all nine digests against the values this repository tracks, extracts
26 300 and 18 494 files and verifies each against its own manifest, counts run
directories under both definitions, then for the 2026-09-03 archive re-runs
`analyze.py`, byte-compares against the tracked CSVs, and **verifies every run's
`config_digest` against the schema generation in force when that run was
collected** (`docs/32-config-digest-verifiability.md`).

Expected:

```
run directories: 1,458 (expected 1,458) -- 1,457 named -r<N>, 1,458 with a run-config.json
run directories: 1,332 (expected 1,332) -- 1,332 named -r<N>, 992 with a run-config.json
IDENTICAL 114   IDENTICAL-after-normalisation 8   DIFFERS 0
NONE UNEXPLAINED
VERIFIED: both archives at this source are byte-for-byte the ones this
repository describes, and the paper's analysis products follow from the
2026-09-03 archive.
```

Anything else is a finding — report it rather than re-uploading over it, because
a published record cannot be replaced.

**The extension is checked for integrity, not for sufficiency.** It has no
recorded re-derivation baseline, so the script prints `re-derivation: NOT RUN`
with the reason rather than passing silently. §9 of the manuscript says the same
thing. Establishing that baseline is open work, not a step in this checklist.

The digest audit can also be run on its own against an unpacked archive:

```sh
uv run --frozen --extra experiments --extra analysis python \
  scripts/audit_config_digests.py --root <unpacked>/matrix --require-runs 400
```

**What has been exercised, and what has not.** The `--local` path was run
end-to-end against both archives on 2026-09-16 and passed. **Only the
fetch-by-DOI half is untested**, because there is nothing to fetch — which is
why §2 asks you to run it against the sandbox DOI before the real publish.
