# The Zenodo deposit: state, ordering against phase 53, pre-publication checks, and the steps only the author can take — 2026-09-24

**Nothing was published, no upload was started, and no archive was rebuilt.**
Both archive roots were read and hashed; neither was modified. No `paper/` file
was edited, no PDF built, no full suite run.

**Repository state:** `cb3cad8`, working tree clean.

**Why now.** TSE is single-anonymous
(`reports/tse-venue-2026-09-24.md`), so a Zenodo record naming its depositor no
longer breaks anything. Publishing closes the audit's blocker B3 and
`reports/claims-to-review.md` entry 3.

---

## 0. The finding that changes the plan

**The deposit as prepared does not cover the paper.** Five tracked collection
roots that supply **18 manuscript macros** are in neither archive, and
`docs/29-archive-deposit.md` §3's ready-to-paste description **claims two of
them are**. Publishing it as written would put a false statement of contents on
an immutable record.

This is independent of phase 53 and would have been true yesterday. §2 has the
detail. **The deposit is not ready to publish today for a reason that has
nothing to do with the new collection**, and the phase-53 question in §3 then
settles the ordering.

---

## 1. What exists, and whether it still verifies

### The two parts, on disk

| | WSL | Windows (checked here) |
|---|---|---|
| 2026-09-03 | `/root/aep-raw-archive/` | `D:\personal\AEP\aep-raw-archive\` |
| 2026-09-15 | `/root/aep-raw-archive-ext/` | `D:\personal\AEP\aep-raw-archive-ext\` |

**One record, two archives, six files**, per `docs/29` §0.

### Sizes and digests — all six match `docs/29` §1 exactly

Recomputed here with `sha256sum` against the Windows copies:

| deposited as | bytes | sha256 | matches §1 |
|---|---|---|---|
| `MANIFEST-2026-09-03.sha256` | 4 287 997 | `87fa2d53…3e2d7` | **yes** |
| `ARCHIVE-METADATA-2026-09-03.json` | 15 052 | `cf75e723…220e5` | **yes** |
| `aep-raw-evidence-2026-09-03.tar.gz` | 24 257 505 | `fec959b5…7353` | **yes** |
| `MANIFEST-2026-09-15.sha256` | 3 027 470 | `54d1ab0f…3cd5` | **yes** |
| `ARCHIVE-METADATA-2026-09-15.json` | 8 650 | `91fbd343…486a2` | **yes** |
| `aep-raw-evidence-2026-09-15.tar.gz` | 17 563 367 | `6ef11d7c…eebf1` | **yes** |

**The archives are byte-identical to what was verified on 2026-09-16.** Nothing
has drifted. Uncompressed they stream to 492 905 568 and 355 492 262 bytes,
matching the description's figures.

### Are the manifests current against the data as it stands today?

**Against their own contents: yes** — each manifest is internally consistent and
its digest is unchanged, so `sha256sum -c` will pass.

**Against the repository as it stands today: no.** The manifests were frozen at
`repository_head` `c194dc7` (2026-09-03) and `eef35f8` (2026-09-15). Eleven
tracked collection roots have appeared or been left out since. §2.

### The DOI, and what is uploaded

| | |
|---|---|
| reserved DOI | `10.5281/zenodo.22766567` |
| state | `RESERVED` — a draft record holds it; `paper/main.tex:126` is `\archivedoistate{RESERVED}` |
| files uploaded | **none.** `ARTIFACT.md` §5: *"the record is a draft and the files are not uploaded, so the DOI does not resolve yet"* |
| what resolving requires | publishing the draft |

**Do not create a new record.** The identifier is already written into
`paper/main.tex:125`, the built PDFs, `README.md`, `ARTIFACT.md`, `CITATION.cff`
and `docs/36`. A new record mints a different DOI and orphans all of them
(`docs/29` §0, "Ruin #1").

---

## 2. The coverage gap — five roots, 18 macros, and a false description

### Which tracked roots are in which archive

Computed by comparing `check_prereg_order.discover()` — every tracked collection
root, 35 of them — against the top-level directory names inside each manifest.

**In neither archive (11):**

| root | manuscript macros | disposition |
|---|---|---|
| **`experiments/results/ws5-2026-09-10/t1-p0-everysec`** | **9** | **must be deposited** |
| **`experiments/results/fsync-always-2026-09-14`** | **5** | **must be deposited** |
| **`experiments/results/ws5-2026-09-10/t2-p30`** | **3** | **must be deposited** |
| **`experiments/results/ws5-2026-09-10/t2-keying`** | **1** | **must be deposited** |
| `experiments/results/ws5-2026-09-10/t1-incomplete` | 0 | deposit — it is the incomplete sibling of a cell that is cited, and a discarded collection is evidence about the instrument |
| `experiments/results/stage3-replication-2026-08-13` | 0 | author's call; predates rule 5 and no number derives from it |
| `reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14` | 0 | recommend **excluding**, declared by name — it is quarantined debris, not a collection |
| `reports/raw/phase40-deployment-2026-09-18` | 0 | §4.3 |
| `reports/raw/phase40-stage-10-interactive-2026-09-21` | 0 | §4.3 |
| `reports/raw/phase40-stage-30-2026-09-21` | 0 | §4.3 |
| `reports/raw/phase40-stage-100-2026-09-22` | 0 | §4.3 |

### The 18 macros

`paper/generated/numbers.tex`, attributed by walking each macro's provenance
comment block:

**From `ws5-2026-09-10/t1-p0-everysec` (9)** — `\BarrierCostFifteen`,
`\BarrierCostFifteenLow`, `\BarrierCostFifteenHigh`,
`\ProtocolMinusBarrierFifteen{,Low,High}`,
`\ProtocolMinusBarrierLowerMode{,Low,High}`.

**From `fsync-always-2026-09-14` (5)** — `\BarrierCostAlwaysFortyFive{,Low,High}`,
`\AepAlwaysFortyFiveMedian`, `\BthreeAlwaysFortyFiveMedian`.

**From `ws5-2026-09-10/t2-p30` (3)** — `\PthirtyComparisons`, `\PthirtyRuns`,
`\PthirtyExecutions`. **From `t2-keying` (1)** — `\KeyingAmbiguityOracle`.

`\BarrierCostFifteen` = 1 939.7 ms is **RQ3's headline**, the 15-run barrier
cost the external audit recomputed and matched. Its raw runs exist in exactly
one place: this host's working tree, untracked (11 337 files on disk, 36
tracked) and unarchived.

### The description is wrong about this

`docs/29` §3's paste-ready HTML, the block that becomes the published record's
description, says of the 2026-09-15 extension:

> *"the trees the first archive did not reach — **the WS-5 deployment sweep
> behind Section VI's fsync-policy and payload-size results**, the real-Temporal
> (B5) baseline sessions …, the WS-4 block-level write-loss cell and its voided
> arm, and **the 45-run appendfsync=always extension**."*

The extension actually contains eleven roots: `ws4-writeloss` ×2, `ws6-b5` ×3,
`phase13-armA` ×4 and `phase13-inflight` ×2. **No WS-5. No
`fsync-always-2026-09-14`.** Two of the four things that sentence names are not
there.

**A Zenodo record cannot be edited after publication.** Pasting that description
publishes a false statement of contents under a DOI the paper cites.

### Why the gap was not caught

`scripts/verify_published_archive.py` checks that the record carries all six
files, that nine digests match, that every file verifies against its own
manifest, and that run-directory counts agree. **It has no notion of whether the
archive covers the roots the paper cites** — it verifies the deposit against
itself, not against the manuscript. Both archives pass it today and the gap
survives.

`ARCHIVE-METADATA-2026-09-15.json`'s `excluded` list is a verbatim copy of the
2026-09-03 one and names nothing about WS-5 or the 45-run always arm. So they
were not excluded with a reason — **they were missed.**

---

## 3. Phase 53, and the ordering — stated plainly

### The collection is running now

`experiments/results/abd-immediate-2026-09-24/` — **25 of 45 run directories**
at 12:03, started 10:46, estimated 1.74 h by the planner. Untracked so far.
**This session did not touch it.**

### Must the deposit include the phase-53 collection? — **Yes**

`prompts/phase-53-abd-immediate-2026-09-24.md` §5 is explicit that the cell
produces manuscript content:

> *"**This cell is reported separately, as its own session**, with its own
> macros, its own n, and its date. … The manuscript states that the cell was
> re-collected, why, and that the two are not pooled."*

New macros in the manuscript mean new numbers a reviewer must be able to check.
If the deposit is the evidence behind every quantitative claim — which is what
its description says it is — then it must carry the runs behind those macros.

The same pre-registration also changes **existing** numbers: §5.1 rules that the
pooled baseline rates are computed *the exclusion way*, which moves
`\BaselineDupLow`/`\BaselineDupHigh` from 0.77–0.83 to 0.74–0.78 and every
baseline cell of Table 7 (`reports/audit-response-2026-09-23.md` §1.6). Those
recomputations are over the **existing** matrix, which is already deposited — so
that half does not add a deposit requirement. The new macros do.

### Would publishing before it lands make the archive incomplete? — **Yes, twice over**

1. **Against phase 53**, for the reason above: the paper would cite macros whose
   raw runs are not in the record it points at.
2. **Against the paper as it already stands**, for the reason in §2: 18 macros
   already have no raw evidence in the deposit, including RQ3's headline.

Point 2 is the one that matters most, because it is true *now* and would have
been true if this had been published last week.

### The correct order

**Collect → analyse → freeze → re-manifest → deposit → publish → flip the state.**

| # | step | who | blocking on |
|---|---|---|---|
| 1 | Let phase 53 finish and be analysed, reported and committed | the other session | in progress, ~25/45 |
| 2 | Decide the disposition of each of the 11 uncovered roots (§2 table) | **author** | step 1 |
| 3 | Build a **third archive part** covering the uncovered roots + phase 53 | script | steps 1–2 |
| 4 | Verify the new part end-to-end, locally | script | step 3 |
| 5 | Re-scan the new part (§4) | script | step 3 |
| 6 | Rewrite `docs/29` §1's digest table and §3's description for **nine** files | — | step 4 |
| 7 | Rehearse on sandbox.zenodo.org | **author** | step 6 |
| 8 | Upload into the existing draft and publish | **author only** | step 7 |
| 9 | Flip `\archivedoistate` and the seven non-LaTeX sites; rebuild; tag | — | step 8 |

**A third part rather than rebuilding both.** The two existing archives are
verified, digest-stable, and already described in `CITATION.cff`, `ARTIFACT.md`
and `README.md` by digest. Rebuilding changes those digests and invalidates
every one of those statements. Adding a third part changes nothing that already
exists. The cost is that the record goes from six files to **nine**, and three
places need a third entry:

- `scripts/verify_published_archive.py` — the `ARCHIVES` tuple and the
  required-files check (`:88`, `:177`);
- `docs/29` §1's table and §3's description;
- `CITATION.cff` and `ARTIFACT.md`, which name the parts by digest.

**Do not publish a two-part record now and add a third part as a new version
later.** Zenodo versioning mints a new version DOI; `paper/main.tex` carries the
version DOI of *this* draft, so the paper would cite a record that is missing a
third of its evidence, with the complete one at a different identifier.

---

## 4. Pre-publication checks, and their results

All scans ran over the **packed parts**, streamed through `tarfile` member by
member, reporting which files matched and never the matched value.

### 4.1 Credentials and key material

| category | 2026-09-03 | 2026-09-15 | verdict |
|---|---|---|---|
| `AZURE_OPENAI_API_KEY` (the var name) | 0 | 0 | **clean** |
| `"api-key"` request header | 0 | 0 | **clean** |
| `Ocp-Apim-Subscription-Key` | 0 | 0 | **clean** |
| `Bearer <token>` | 0 | 0 | **clean** |
| OpenAI-style `sk-…` | 0 | 0 | **clean** |
| PEM private-key block | 0 | 0 | **clean** |
| AWS access key id | 0 | 0 | **clean** |
| Azure 84-char key shape | 0 | 0 | **clean** |
| `password`/`passwd`/`secret` assignment | 0 | **5** | resolved below |
| 32-hex value | **8** | **940** | resolved below |

**The Azure key is not in either archive, and could not be.** Two independent
reasons:

1. **No phase-40 artifact is in either archive at all** — `phase40`,
   `planner-transcript`, `planner-cumulative` and `gpt-5.6-luna` all return
   **0 matches in both parts**. The Azure client is only ever invoked by the
   phase-40 planner path.
2. **The client is built so the key cannot reach a file.**
   `experiments/harness/azure_client.py:24-27`: *"The key is never written
   anywhere. It is read from the environment into one local, sent in one header,
   and never placed on the call object, in the transcript, in an exception, or
   in a log line. `__repr__` is overridden because a traceback prints arguments,
   and a traceback is a file."* The single read is `api_key()` at `:209-214`,
   which returns it and stores it nowhere.

> **One scope limit, stated rather than glossed.** I did not read `D:\personal\AEP\.env`
> and so did not perform a *literal* match of the key's value against the
> archives — the tool sandbox declined access to the credential file, and I did
> not work around it. What is reported above is a search for the key's **shape**,
> its **environment-variable name**, its **request header**, and for any
> phase-40 artifact that could carry it. If you want the literal check, run it
> yourself; it is one command and it never prints the key:
>
> ```sh
> set -a; . /mnt/d/personal/AEP/.env; set +a
> for a in /root/aep-raw-archive /root/aep-raw-archive-ext; do
>   printf '%s: ' "$a"
>   tar -xzOf "$a/aep-raw-evidence.tar.gz" \
>     | grep -c -a -F "$AZURE_OPENAI_API_KEY"
> done   # expect 0 and 0
> ```

### 4.2 The non-zero categories, each identified

**(a) `password`/`secret` assignments — 5 matches, 5 files, extension only.**

- `compose.temporal.yml` ×3, in `ws6-b5-s1-2026-09-08-{VOIDED-attempt1,attempt2,attempt3}`
- `observers/containers.json` ×2, the `docker inspect` output echoing the same

The literal, confirmed against the repository's own tracked copy at
`experiments/baselines/b5_temporal/compose.temporal.yml:34,61`:

```yaml
      POSTGRES_PASSWORD: temporal
      POSTGRES_PWD: temporal
```

**That is the Temporal development stack's published default**, for a Postgres
container that existed only for the duration of the B5 runs and no longer
exists. It is not a credential to anything reachable. **Disposition: publish as
is, and say so** — the compose file is part of how the Temporal baseline was
configured, and removing it would invalidate the manifest and hide a
configuration a reader needs. Recommended: one clause in the record description.

**(b) 32-hex values — 8 in the first part, 940 in the extension. All three
sources identified; none is a secret.**

| where | count | what it is |
|---|---|---|
| `phase10-replication-drvfs{,-arbb30}-2026-09-02/COLLECTION-PROVENANCE.json` | 8 | Fields literally named `token` and `seen`, values `aep-host-verify-<fs>-<32hex>`. Generated at `scripts/verify_measurement_host.py:160` as `f"aep-host-verify-{name}-{uuid.uuid4().hex}"` — a random nonce written to a canary file to prove a filesystem write landed where it was supposed to. **The field name is why the pattern fired.** |
| `ws6-b5-s1-*/observers/temporal.log` | 928 | Temporal server task-queue identities, `"wf-task-queue-name":"<pid>@KP248-<32hex>"`. Server-generated per-worker identity. Carries the hostname `KP248`, already disclosed |
| `ws6-b5-s1-*/measurement-host.txt` | 12 | The same host-verify nonces |

### 4.3 Identity material — deliberate, not accidental

| category | 2026-09-03 | 2026-09-15 | disposition |
|---|---|---|---|
| email addresses | 0 | 0 | none present |
| GitHub handle `hafizmirhamza276` | 0 | 0 | none present |
| ORCID `0009-0005-9380-2188` | 0 | 0 | none present |
| `C:\Users\…` paths | 0 | 0 | none present |
| `AzureAD+…` account strings | 0 | 0 | none present |
| hostname `KP248` | 17 | 935 | **deliberate**, disclosed in `docs/29` §3 |
| `/root/aep…` paths | 869 | 9 853 | **deliberate and load-bearing** |
| `/mnt/d/personal/AEP…` paths | 797 | 14 884 | **deliberate and load-bearing** |

**There is no personal identifier in either archive.** A machine name and a
directory layout are present, and `docs/29` §3's description already states why
they are retained: *"they are the evidence from which the collection path of the
frozen evaluation was reconstructed, and removing them would invalidate the
manifests."* Under single-anonymous review this is no longer even a tension —
the submitted paper names the author on page 1.

**This also extends `docs/29` §0c's caveat.** That section recorded that the
extension *"has not been through this scan"* and asked for one before uploading.
**It has now been scanned, and it is clean on every credential and identity
category.** The two categories that fired are identified above.

### 4.4 Phase 40, and what the closure governs

**The closure restricts the manuscript, not the archive.** Read directly:

- `prompts/phase-40-closure-2026-09-22.md` §9, *What is preserved, and where*,
  names `reports/raw/phase40-*/` as **committed text evidence** and
  `AEP/stub-results/phase40-*/` as the full live collections. Preservation is
  the disposition, not suppression.
- §8's disposition, quoted in the closure: *"**Both failures are reportable
  results.** Neither is a reason to leave the experiment out of the record."*
- The forbidden form is a **manuscript sentence**.
  `reports/phase-report-40-closure-2026-09-22.md` §3 row 4: *"An artifact
  pointer — a sentence in §IX directing readers to `reports/raw/phase40-*` —
  **FORBIDDEN as a manuscript sentence, and unnecessary** … because the evidence
  is already public without it."*

So **nothing forbids the archive from containing phase-40 data**, and the
closure's own logic — the evidence is already public in the repository — argues
mildly for including it.

**Two things to weigh, and this is the author's call:**

1. **A Zenodo description is not manuscript text**, so listing a phase-40 root
   in the record's contents does not violate the closure. But the description is
   a public document attached to the paper's DOI, and a reader who sees
   *"phase40-stage-100"* listed will go looking. The closure's reasoning is that
   the experiment's record belongs in `reports/`, which it does; the question is
   whether the deposit is also "the record".
2. **What would be deposited is not the live collection.** `reports/raw/phase40-*`
   is the committed *text evidence* — 2, 28, 28 and 55 files. The full live
   collections are at `AEP/stub-results/phase40-*`, outside the repository. If
   phase-40 material is deposited at all, decide which of the two, because they
   are different artifacts and only one has ever been committed.

**Recommendation:** deposit `reports/raw/phase40-*` with the rest, because the
deposit's stated purpose is the raw evidence behind the repository and these are
tracked repository contents; and say nothing about phase 40 in the manuscript,
which is what the closure actually requires. **But this is a judgement the
closure leaves open, and it should be made explicitly rather than by whoever
runs the archive script.**

---

## 5. The steps only you can perform

Everything below needs a browser, a Zenodo login, or a decision. Nothing in this
list can be scripted from here.

| # | step | why only you |
|---|---|---|
| **A** | **Decide the disposition of the 11 uncovered roots** (§2 table), in particular whether `stage3-replication-2026-08-13`, the `INCIDENT-` debris and the four `phase40-*` roots go in | It is a judgement about what the evidence record is, and §4.4 is deliberately left open |
| **B** | **Decide part-3-versus-rebuild** — the recommendation is a third part (§3), but it costs three files and a third `ARCHIVES` entry | Changes what is published under a DOI the paper cites |
| **C** | **Rehearse on https://sandbox.zenodo.org** — create a record, upload all nine files, paste the description, publish, then run `verify_published_archive.py --doi <sandbox-id>` and confirm it also **fails** when you delete one file | Requires a Zenodo account; `docs/29` §2. This is the only exercise of the fetch-by-DOI path, which has never run |
| **D** | **Open the existing draft holding `10.5281/zenodo.22766567` and upload into it** | Requires login. **Do not create a new record** — `docs/29` §0 "Ruin #1" |
| **E** | **Paste the corrected description** — `docs/29` §3's block with §2's false sentence fixed and the third part added | The correction is mine to draft, the publication is yours |
| **F** | **Press Publish** | Irreversible. A published Zenodo file cannot be replaced or withdrawn |
| **G** | **Confirm the version DOI did not change** after publishing | `docs/29` §4 — if it changed, something created a new record and every downstream step is wrong |

Steps that do **not** need you, once A and B are decided: building the third
part, re-verifying, re-scanning, rewriting `docs/29`, updating
`verify_published_archive.py`, flipping the state and rebuilding.

---

## 6. What changes in the manuscript once the DOI resolves

### The macro

`paper/main.tex:126`:

```latex
\newcommand{\archivedoi}{10.5281/zenodo.22766567}   % leave alone
\newcommand{\archivedoistate}{RESERVED}             % -> PUBLISHED
```

`RESERVED` selects the branch at `main.tex:238`. Anything that is neither
`PENDING` nor `RESERVED` selects the resolving branch; `PUBLISHED` is the
conventional value.

### The sentence

Section 8, Artifact Availability. **Before**, as it renders today:

> "those are carried by a separate archive, prepared and verified, with the
> Zenodo record reserved under DOI 10.5281/zenodo.22766567; the identifier is
> fixed and begins resolving when the record is published."

**After**:

> "those are carried by a separate archive, deposited at
> https://doi.org/10.5281/zenodo.22766567."

`docs/29` §5 records a dry run confirming **exactly one sentence changes**, and
that `main-anon.pdf` is byte-identical in text before and after because the
anonymous branch never reads `\archivedoi`. **That dry run was done at 23 pages
and the body is now 24**, so the page count should be re-checked on the rebuild
rather than assumed.

### Does `claims-to-review` entry 3 then close with no text change? — **Yes**

Entry 3 was reopened because `paper/sections/08-threats.tex:223-227` says the
voided run *"is in the **published** archive under `voided/`"* while
`\archivedoistate` is `RESERVED`.

Two things make it close cleanly:

1. **The archive genuinely contains it.** `voided/` is a top-level root of the
   2026-09-03 part, 24 files, confirmed in that manifest here — the half the
   2026-09-23 closure verified correctly.
2. **Publication makes "published" true**, and the sentence is in
   `08-threats.tex`, which contains no DOI and no `\archivedoistate`
   conditional. Nothing in it needs editing.

**So entry 3 closes as RESOLVED with no manuscript text changed, the moment the
record is published** — which is the outcome the reopening recommended over
rewording. The only edit anywhere is `\archivedoistate` in `main.tex`, and that
is Section 8's sentence, not Section 9's.

### The seven other sites

`docs/29` §5 lists them with line numbers: `README.md:8` and `:10-13`,
`ARTIFACT.md:348-356`, `CITATION.cff:2`, `:24-27` and `:33-42`,
`paper/arxiv-metadata.md:32-35`, `:38-45` and `:203-207`,
`docs/36-repository-inventory-2026-09-15.md:189`, and `docs/29` itself.

**One addition to that list from this session.**
`paper/arxiv-metadata.md:83-88` justifies withholding the DOI from the anonymous
build on the ground that *"a Zenodo record names its depositor, so citing it
under double-anonymous review defeats the anonymisation."* Under single-anonymous
review that rationale does not hold
(`reports/single-anonymous-implications-2026-09-24.md` §4a). The mechanism can
stay — it costs nothing — but the stated reason should be corrected rather than
left as a premise the project has since refuted.

---

## 7. Summary

| question | answer |
|---|---|
| Do the archives still verify? | **Yes.** All six digests match `docs/29` §1 exactly; nothing has drifted since 2026-09-16 |
| Are the manifests current against today's data? | **No.** Frozen at `c194dc7` / `eef35f8`; 11 tracked roots are in neither |
| Is the deposit publishable today? | **No** — and not because of phase 53. 18 macros, including RQ3's headline `\BarrierCostFifteen`, have no raw evidence in it, and `docs/29` §3's description claims two of the missing roots are present |
| Must the deposit include phase 53? | **Yes.** Its pre-registration §5 commits the manuscript to new macros with their own n |
| Would publishing early make the archive incomplete? | **Yes, twice**: against phase 53, and already against the paper as it stands |
| Correct order? | Collect → analyse → freeze → **re-manifest as a third part** → verify → re-scan → deposit → publish → flip the state |
| Credentials in the archive? | **None found.** No Azure key name, header, or shape; no phase-40 artifact at all. The 5 `password` hits are `POSTGRES_PASSWORD: temporal`, the Temporal dev default; the 948 32-hex values are `uuid4` canary nonces and Temporal task-queue identities |
| Identity material? | No email, no GitHub handle, no ORCID, no `C:\Users`. Hostname and WSL paths present, deliberate, already disclosed |
| Phase 40 in the archive? | The closure governs the **manuscript**, not the archive, and names `reports/raw/phase40-*` as preserved evidence. Including it is permitted; the decision is yours |
| Does entry 3 close with no text change? | **Yes**, the moment the record is published |

**Nothing was published, uploaded, rebuilt or edited by this session.**
