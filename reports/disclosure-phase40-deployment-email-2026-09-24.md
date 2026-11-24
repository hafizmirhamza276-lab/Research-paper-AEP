# A third party's work e-mail address was committed and is public — 2026-09-24

**Status: RESOLVED in the working tree, DELIBERATELY NOT RESOLVED in history.**

Found while scanning the newly-built third archive part before deposit. It is
not a deposit problem: **it was already public**, and has been since
2026-09-18.

## 0. What was decided, and what was done

Author decisions, 2026-09-24, recorded before the detail so the disposition is
not buried:

| # | decision | done |
|---|---|---|
| 1 | **Redact** `createdBy` and `lastModifiedBy` in the working tree, in a normal commit, removing only what identifies a person | **yes** — §3.1 |
| 2 | **Do not rewrite git history.** The address remains reachable in `08f6e4d` | **yes, and stated plainly** — §3.2 |
| 3 | Keep the root **out of the archive** | **yes** — it is in the 2026-09-24 part's exclusion list with this reason |
| 4 | The author tells the person himself; **nothing is drafted on his behalf** | **yes** — §5 is the factual account only, not a message |
| 5 | `stage3-replication-2026-08-13` stays out of the deposit | unrelated to this finding; recorded in the deposit plan §15 |

**The address is still reachable in this repository's history and always will
be.** That is decision 2, taken knowingly, for the reason in §3.2. Anyone
reading this file should not conclude the exposure has been undone.

---

## 1. What, and where

`reports/raw/phase40-deployment-2026-09-18/deployment-show.json`, lines 64 and
67:

```json
    "createdBy": "<redacted>@<employer-domain>",
    ...
    "lastModifiedBy": "<redacted>@<employer-domain>",
```

- **Committed:** `08f6e4d`, *"prereg: amendment 1 — the deployment reports an
  alias, not a snapshot"*, 2026-09-18T14:51:43+05:00.
- **Pushed:** yes. `git branch -r --contains 08f6e4d` returns `origin/main`.
  The repository at `https://github.com/hafizmirhamza276-lab/Research-paper-AEP`
  is public and is named in the manuscript's Section 8.
- **Exposure:** six days, in a public repository, in git history.
- **Scope:** exactly one tracked file, two fields.
  `git grep -l` for the employer domain returned that file and nothing else. No other
  e-mail-shaped string exists anywhere under `reports/raw/` or `experiments/`.

## 2. Why it matters more than a normal path leak

This is not the hostname-and-directory-layout disclosure that `docs/29` §0c
already discusses and defends. Three differences:

1. **It is a person, and not you.** The author of record is Hamza Khan
   (`hafizmirhamza276@gmail.com`, ORCID `0009-0005-9380-2188`). This is a
   different individual's corporate account. Whatever consent exists for the
   author's own identifiers to be public does not extend to theirs.
2. **It identifies an organisation.** The domain names the employer whose
   Azure tenant hosted the phase-40 planner deployment. The repository
   otherwise says nothing about any institution except the author's university.
3. **It contradicts the deposit's own stated standard.** `docs/29` §0c and §3
   both assert the archive contains **no e-mail addresses**, and the 2026-09-03
   scan is quoted as `0`. Publishing this file under the DOI would make that
   sentence false on the record that carries it.

**Someone already redacted this file by hand and missed these two fields.** The
same JSON carries `"id": "/subscriptions/<subscription-or-tenant-id-redacted>/…"`.
The subscription identifier was recognised and removed; `createdBy` and
`lastModifiedBy` were not.

## 3. What was done

### 3.1 The working tree — redacted

`reports/raw/phase40-deployment-2026-09-18/deployment-show.json`, two lines,
nothing else:

```diff
-    "createdBy": "<redacted>@<employer-domain>",
+    "createdBy": "<azure-account-redacted>",
-    "lastModifiedBy": "<redacted>@<employer-domain>",
+    "lastModifiedBy": "<azure-account-redacted>",
```

The marker matches the style already in the file, whose `id` field reads
`/subscriptions/<subscription-or-tenant-id-redacted>/…`.

**Only what identifies a person was removed.** Everything amendment 1 rests on
is byte-for-byte unchanged, verified after the edit:

| field | value | role |
|---|---|---|
| `properties.model.name` | `gpt-5.6-luna` | **amendment 1's finding** — the deployment reports an alias |
| `properties.model.version` | `2026-07-09` | the version the ARM read returns |
| `properties.model.format` | `OpenAI` | |
| `name` | `gpt-5.6-luna` | the deployment name |
| `properties.provisioningState` | `Succeeded` | |
| `systemData.createdAt` / `lastModifiedAt` | `2026-08-17T13:15:02…` | **kept** — a timestamp is not a person |
| `systemData.createdByType` / `lastModifiedByType` | `User` | **kept** — the *type* is not an identity |

The file is still valid JSON with the same nine top-level keys.
`prompts/phase-40-amendment-1-snapshot-2026-09-18.md:38` cites this file for
`model`, `id` and the capability fields and never for its audit metadata, so
no pre-registration, report or check reads the redacted fields.

**No manifest covers this file**, so the redaction invalidates nothing:
`grep -c phase40-deployment` returns 0 in all three archive manifests. The root
is in neither published part and is excluded from the 2026-09-24 part.

### 3.2 History — deliberately not rewritten

**The address remains reachable in `08f6e4d` and will stay reachable.** Author
decision, with the reasoning recorded here because a future reader will
otherwise assume it was an oversight:

> This project pins commit SHAs in a way most repositories do not.
> `reports/prereg-blobs.json` records each pre-registration's blob hash at its
> **first commit**; `scripts/check_prereg_order.py` tests that a prediction is
> an **ancestor** of the data it governs, not merely older by date; and phase
> reports quote SHAs as the evidence that an ordering held. A rewrite changes
> every SHA after `08f6e4d` — which is 2026-09-18, before phases 40's closure,
> 41–53, and the whole prereg-order audit. Every one of those records would
> become a reference to a commit that no longer exists, and the pre-registration
> ordering guarantee — the thing this project treats as its strongest integrity
> claim — would have to be re-established against a history nobody had seen
> before. That record is worth more than removing an address that has already
> been public for six days.

Two further facts that informed it, and neither is a reason to relax:

- A force-push does not delete anything immediately. GitHub keeps unreferenced
  objects reachable through the API for a period, and any existing clone or
  fork keeps the old objects indefinitely.
- The exposure is one work e-mail address of a colleague, not a credential.
  Nothing authenticates with it.

**This is a trade, not a fix.** It is recorded as one.

### 3.3 The archive — the root stays out

Excluded from the 2026-09-24 part, which carries 8 roots rather than 9.
`ARCHIVE-METADATA.json` declares the exclusion with this reason rather than
omitting the root silently — which is the exact failure mode the rest of this
session was spent fixing.

**This contradicted decision A**, which was to include all four phase-40 roots;
the author has since confirmed the exclusion. The other three phase-40 roots —
stages 10, 30 and 100 — are in the part and scan clean.

**It stays out even though the working tree is now redacted.** Two reasons.
The deposit is immutable once published and the file's audit metadata serves no
claim, so there is nothing to gain by carrying it. And re-adding it would
change the part's three digests and the `ARCHIVES` entry for the sake of two
files of deployment metadata.

## 4. Is there anything else? A full sweep says no

Every tracked file in the repository and **all three archive parts**, swept for
six classes of third-party identifier. The author's own identifiers
(`hafizmirhamza276@gmail.com`, the `hafizmirhamza276-lab` handle, the ORCID,
the name) are excluded as expected-and-deliberate, so what remains is only what
belongs to someone else.

| class | repository | 2026-09-03 | 2026-09-15 | 2026-09-24 |
|---|---|---|---|---|
| e-mail addresses | **clean** (see below) | **clean** | **clean** | **clean** |
| Azure principal fields | **clean** — both now redacted | **clean** | **clean** | **clean** |
| corporate domains | **clean** (see below) | **clean** | **clean** | **clean** |
| Azure subscription / tenant GUID | **clean** (see below) | **clean** | **clean** | **clean** |
| phone numbers | **clean** | **clean** | **clean** | **clean** |
| GitHub handles | organisations only | **clean** | organisations only | **clean** |

**The e-mail addresses that remain are these five, and none is a third party:**

| address | what it is |
|---|---|
| `hafizmirhamza276@gmail.com` | the author's, in `main.tex`'s named branch |
| `63538732+hamza276@users.noreply.github.com` | the author's GitHub noreply — identical to `git log -1 --format='%an <%ae>' 08f6e4d` |
| `noreply@anthropic.com` | the `Co-Authored-By` commit trailer. Not a person |
| `t…@example.invalid`, `pa…@example.invalid` | synthetic fixtures in three test files. `.invalid` is reserved by RFC 2606 and cannot resolve |

**The 33 541 "subscription GUID" matches in the repository, and the 900 050
across the three archives, are false positives** — the pattern matches any
UUID. Attributing them by JSON key:

| key | count |
|---|---|
| `execution_id` | 9 386 |
| `intent_id` | 1 861 |
| `hostId` | 8 — Temporal/Docker host UUIDs, machine-generated |

the rest being the same identifiers appearing unkeyed in `events.jsonl` and
`ground_truth.sqlite3-wal`. **The only Azure subscription/tenant context
anywhere in the tree is `deployment-show.json:3`, and it was already redacted**
before this session: `"id": "/subscriptions/<subscription-or-tenant-id-redacted>/…"`.
No real Azure subscription or tenant identifier exists in the repository or in
any archive part.

**The "corporate domain" matches were regex artifacts** of `\.local\b` —
`arguments.local` in `verify_published_archive.py`, `settings.local` in
`.gitignore`, and similar. The only real one was the employer domain, and only in
this report.

**The GitHub handles are organisations, not people:** `docker-library`,
`temporalio`, `tlaplus`, `example`, and the author's own
`hafizmirhamza276-lab`.

### 4.1 One the sweep caught in this session's own work

**The first draft of this report quoted the address verbatim, four times.** In
writing up a leak I created a second copy of it, in a new tracked file, which
would have been committed and pushed. The sweep caught it and it is now
`<redacted>@<employer-domain>` throughout. It is recorded here rather than
quietly fixed, because "the report about the leak leaked it" is exactly the
kind of thing a later reader should know the sweep is capable of catching.

## 5. What you need to be able to say

Factual account only, as you asked. **Nothing below is drafted to be sent**;
it is the set of facts, so you can put them in your own words.

**What was exposed.** One work e-mail address, appearing twice, in the
`createdBy` and `lastModifiedBy` fields of a single JSON file
(`reports/raw/phase40-deployment-2026-09-18/deployment-show.json`). The file is
the output of `az cognitiveservices account deployment show` against the Azure
OpenAI deployment used by the phase-40 experiment. Azure records the account
that created and last modified the deployment; that is where the address came
from. **No password, token, key or other credential was involved.** Nothing
authenticates with the address.

**When, and for how long.** Committed 2026-09-18 at 14:51:43 +05:00 in
`08f6e4d`, and pushed to `origin/main` the same day. Public in
`https://github.com/hafizmirhamza276-lab/Research-paper-AEP` from then until
the redaction on 2026-09-24 — **six days**. The repository is public and is
cited by name in the manuscript's Artifact Availability section.

**What else was in the same file.** The Azure resource path, including the
resource-group name `Azure-RnD_ResourceGroup` and the account name
`kps-rnd-foundry`, and the deployment name `gpt-5.6-luna`. The subscription or
tenant identifier in that path had already been redacted by hand before the
file was committed. The resource-group and account names are still present and
were not treated as personal data; **if either is considered sensitive by the
organisation, that is a separate decision and has not been taken.**

**What is redacted now.** Both fields read `<azure-account-redacted>` in the
current tree, as of the commit carrying this report. Nothing else in the file
changed.

**What remains, and this is the part worth being straightforward about.** The
address is **still reachable in this repository's git history**, in commit
`08f6e4d`, and will remain so. It was a deliberate decision not to rewrite
history, for the reason in §3.2 — this project's integrity claims are pinned to
commit identity — not an oversight and not a cost-saving. Anyone who clones the
repository and reads that commit can see it. Any existing clone or fork already
has it.

**What it was never in.** It is in no published archive and no deposit: the
Zenodo record has not been published, and the root containing this file is
excluded by name from the archive part prepared for it. It does not appear in
the manuscript, in either PDF, or in any other file in the repository.

**Who found it and how.** An automated scan of the archive part, run before
deposit, as part of checking the record for anything that must not be
published. It was not reported from outside.

## 6. What to check before the next deposit

The scan that found this is in the plan
(`reports/zenodo-deposit-plan-2026-09-24.md` §4). It should be run over **any**
new part, not just the two that existed when `docs/29` §0c was written. The
first two parts were scanned and are clean on this category — **0 e-mail
matches in both** — so this is specific to the phase-40 material, which is the
only part of the corpus that ever touched a hosted API and therefore the only
part carrying cloud-provider audit metadata.

**Nothing in this session redacted, rewrote or deleted anything.**
