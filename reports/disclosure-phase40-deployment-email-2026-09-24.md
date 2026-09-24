# A third party's work e-mail address is committed and public — 2026-09-24

**This needs your decision, and it is the most important finding of this
session. Nothing has been redacted, rewritten or deleted.**

Found while scanning the newly-built third archive part before deposit. It is
not a deposit problem: **it is already public**, and has been since
2026-09-18.

---

## 1. What, and where

`reports/raw/phase40-deployment-2026-09-18/deployment-show.json`, lines 64 and
67:

```json
    "createdBy": "umer_qureshi@global.komatsu",
    ...
    "lastModifiedBy": "umer_qureshi@global.komatsu",
```

- **Committed:** `08f6e4d`, *"prereg: amendment 1 — the deployment reports an
  alias, not a snapshot"*, 2026-09-18T14:51:43+05:00.
- **Pushed:** yes. `git branch -r --contains 08f6e4d` returns `origin/main`.
  The repository at `https://github.com/hafizmirhamza276-lab/Research-paper-AEP`
  is public and is named in the manuscript's Section 8.
- **Exposure:** six days, in a public repository, in git history.
- **Scope:** exactly one tracked file, two fields.
  `git grep -l "global.komatsu"` returns that file and nothing else. No other
  e-mail-shaped string exists anywhere under `reports/raw/` or `experiments/`.

## 2. Why it matters more than a normal path leak

This is not the hostname-and-directory-layout disclosure that `docs/29` §0c
already discusses and defends. Three differences:

1. **It is a person, and not you.** The author of record is Hamza Khan
   (`hafizmirhamza276@gmail.com`, ORCID `0009-0005-9380-2188`). This is a
   different individual's corporate account. Whatever consent exists for the
   author's own identifiers to be public does not extend to theirs.
2. **It identifies an organisation.** `global.komatsu` names the employer whose
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

## 3. What I did about it, and what I did not

**Did:** excluded `reports/raw/phase40-deployment-2026-09-18` from the third
archive part and rebuilt it. The part now carries 8 roots rather than 9, and
`ARCHIVE-METADATA.json` declares the exclusion with this reason rather than
omitting the root silently — which is the exact failure mode the rest of this
session was spent fixing.

**Note this contradicts your decision A**, which was to include all four
phase-40 roots. I judged that an instruction given without knowledge of the
e-mail should not be executed as written, and that publishing another person's
personal data under a DOI is not reversible. The other three phase-40 roots —
stages 10, 30 and 100 — are in the part as you decided; they scan clean.

**Did not:** redact the file, rewrite history, force-push, contact anyone, or
delete anything. All of those are yours, and two of them are irreversible in
their own way.

## 4. Your options

### 4.1 For the deposit — settled either way

Nothing needs deciding to keep the deposit safe: the part is already built
without it. If you redact (4.2), the root can be added back and the part
rebuilt, which changes its three digests and the `ARCHIVES` entry. That is
twenty minutes and no decision.

### 4.2 For the working tree — redact, and it is low-cost

Replace both values with a marker in the same style the file already uses:

```json
    "createdBy": "<azure-account-redacted>",
    "lastModifiedBy": "<azure-account-redacted>",
```

**Nothing depends on those two fields.** Amendment 1's finding is that the
deployment's `model` key reports the alias `gpt-5.6-luna` rather than a
version-pinned snapshot — a different key in the same file
(`prompts/phase-40-amendment-1-snapshot-2026-09-18.md:38`). The pre-registration
cites the file for `deployment-show.json`'s `model`, `id` and capability fields
and never for its audit metadata.

This is an edit to tracked evidence, so it should be a commit that says what it
changed and why, not a quiet fix.

### 4.3 For the history — your call, and the trade is real

Redacting the working tree does **not** remove the address from git history;
`08f6e4d` still carries it and is on `origin/main`. Three options:

| option | effect | cost |
|---|---|---|
| **Leave history** | Address stays reachable to anyone who reads the commit | Zero work. The exposure continues |
| **Rewrite and force-push** | Removes it from the branch | Rewrites every SHA after `08f6e4d`. **This project pins commit SHAs**: `reports/prereg-blobs.json` records blob hashes, `check_prereg_order.py` tests ancestry, and phase reports quote SHAs. `--update-blobs` would be needed and every quoted SHA becomes wrong. GitHub also keeps unreferenced objects reachable for a while, so the rewrite is not immediate removal |
| **Rewrite and ask GitHub to purge caches** | The above, plus a support request to expire the cached view | Same cost, plus a ticket |

**My recommendation: 4.2 now, and leave history.** The rewrite's cost to this
project is unusually high — commit identity is load-bearing here in a way it
is not in most repositories — and the exposure is one address of a colleague
rather than a credential. But this is a judgement about someone else's data,
and it is not mine to make.

**One thing I would do regardless of which you pick:** tell the person. They
are the only party here who has not had a say, and a six-day exposure of a work
address in a public research repository is something they would probably rather
hear from you than find.

## 5. What to check before the next deposit

The scan that found this is in the plan
(`reports/zenodo-deposit-plan-2026-09-24.md` §4). It should be run over **any**
new part, not just the two that existed when `docs/29` §0c was written. The
first two parts were scanned and are clean on this category — **0 e-mail
matches in both** — so this is specific to the phase-40 material, which is the
only part of the corpus that ever touched a hosted API and therefore the only
part carrying cloud-provider audit metadata.

**Nothing in this session redacted, rewrote or deleted anything.**
