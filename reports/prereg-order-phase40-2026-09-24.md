# `check_prereg_order.py`'s four failures: a gate-table omission, not a missing pre-registration — 2026-09-24

**Nothing was fixed by this session.** `scripts/check_prereg_order.py` is
unchanged and the gate still exits 1. This report establishes *why* it fails and
specifies the exact entry each of the four roots needs, so that the fix is a
transcription rather than a judgement.

**Repository state:** `59ea288`, working tree clean. A concurrent session added
the phase-53 pre-registration (`ba1638c`) and its blob record (`59ea288`) while
this was being written; the gate's output is unchanged by them
(`cells: 35   ok: 27   exempt: 4   failing: 4`), because the root that entry
names does not exist yet and so is not discovered. Their bearing on the fix is
in §3.

Raised as **S6** and **S10** in `reports/external-audit-2026-09-23.md` (§4.4, §7)
and conceded in `reports/audit-response-2026-09-23.md` §4 row 1.

---

## 1. The gate output, run here

```
$ python scripts/check_prereg_order.py; echo "EXIT=$?"
...
reports/raw/phase40-deployment-2026-09-18            UNMAPPED                    FAIL
reports/raw/phase40-stage-10-interactive-2026-09-21  UNMAPPED                    FAIL
reports/raw/phase40-stage-100-2026-09-22             UNMAPPED                    FAIL
reports/raw/phase40-stage-30-2026-09-21              UNMAPPED                    FAIL

pre-registrations byte-identical to their first commit: yes

cells: 35   ok: 27   exempt: 4   failing: 4

FAILURES
  - reports/raw/phase40-deployment-2026-09-18: tracked collection with no entry
    in EXPECTED. Either it is pre-registered and the table must say where, or it
    was collected without a pre-registration -- which is the finding this check
    exists to surface.
  [... the same message for the other three ...]
EXIT=1
```

The check enumerates from the **data**, not from the predictions
(`scripts/check_prereg_order.py:10-15`), so a tracked collection root with no
`EXPECTED` entry is a failure by design. That is the mechanism firing correctly.
What it surfaced is the second of its two alternatives, not the first.

---

## 2. Were the collections pre-registered? Yes

`prompts/phase-40-agent-reachability.md` is the pre-registration for the whole
phase. Its first commit precedes the first data commit of all four roots:

| artifact | first commit | committed |
|---|---|---|
| **`prompts/phase-40-agent-reachability.md`** | `8abac01` | **2026-09-17T15:16:42+05:00** |
| `reports/raw/phase40-deployment-2026-09-18` | `08f6e4d` | 2026-09-18T14:51:43+05:00 |
| `reports/raw/phase40-stage-10-interactive-2026-09-21` | `fac3be0` | 2026-09-21T14:54:16+05:00 |
| `reports/raw/phase40-stage-30-2026-09-21` | `9d26f79` | 2026-09-21T17:52:27+05:00 |
| `reports/raw/phase40-stage-100-2026-09-22` | `5f484c4` | 2026-09-22T14:58:59+05:00 |

Reproduce with
`git log --all --reverse --format='%h %cI' -- <path> | head -1`.

The governing amendment also precedes its own stage in every case, which is the
stronger property — the pre-registration in force at collection time, not merely
the original:

| stage | governing amendment(s) | amendment committed | data committed |
|---|---|---|---|
| stage-10-interactive | a4 `733e1ff` interactive loop; a5 `860d008` cost criterion | 2026-09-18T18:37; 2026-09-21T11:36 | 2026-09-21T14:54 |
| stage-30 | a6 `66dd35e` same-payment re-decision | 2026-09-21T15:19 | 2026-09-21T17:52 |
| stage-100 | a7 `88b8e92`, a8 `6f0dc4e`, a9 `4db3ee3` | 2026-09-22T11:03, 11:42, 12:49 | 2026-09-22T14:58 |

Each collection's own `README.md` names its governing amendment independently of
this reconstruction — `phase40-stage-30-2026-09-21/README.md`: *"The first
collection under amendment 6"*; `phase40-stage-100-2026-09-22/README.md`: *"The
first collection under **paired seeding** (amendment 8) and under the
**transmission boundary** (amendment 9)"*.

**Conclusion: a gate-table omission.** The pre-registrations exist, precede their
data, and are byte-identical to their first commits (the check's own blob line
reports `yes`). What is missing is four rows in `EXPECTED`. The audit's reading
is right, and the pack's "gates green" was written without running the gate.

### One of the four is not a collection

`reports/raw/phase40-deployment-2026-09-18` holds two files and no run
directory:

```
account-show.json      181 B
deployment-show.json  2050 B
```

They are `az cognitiveservices account deployment show` / `account show` output,
captured as the evidence behind amendment 1 — the finding that the deployment
reports an alias (`gpt-5.6-luna`) rather than a version-pinned snapshot, which
made `SnapshotMismatch` unraisable. `prompts/phase-40-amendment-1-snapshot-2026-09-18.md:55-59`
points at this directory by name for exactly that purpose.

It is instrument metadata, not data a pre-registration predicts. Its entry
should say so rather than pretend to an ordering relation it does not need.

### A domain note worth recording

For the three stage roots, **the live collection is not in the repository.** Each
`README.md` says so: *"The live collection itself lives outside the repository
with every other agent-mode collection, at
`AEP/stub-results/phase40-live-…/`. This is the text evidence from it, copied
verbatim and unedited."* So what the gate checks here is the commit order of a
**tracked copy**, not of the collection itself — which is the third item the
check's own `DOMAIN` banner already disclaims (*"does not cover untracked
collections"*). Adding these rows does not change that; it records where the
pre-registration is, which is all this check claims to do.

---

## 3. Exactly what entry each root needs

Insert into `EXPECTED` in `scripts/check_prereg_order.py`, after the
`experiments/results/fsync-always-2026-09-14` entry and before the
`reports/raw/INCIDENT-…` entry so the file stays in rough chronological order:

```python
    "reports/raw/phase40-deployment-2026-09-18": Cell(
        None, None, predates_rule=True,
        note="NOT a collection. Two Azure metadata files (account-show.json, "
             "deployment-show.json) captured as the evidence for amendment 1 "
             "-- the deployment reports an alias, not a version-pinned "
             "snapshot. No run directory, nothing a prediction predicts.",
    ),
    "reports/raw/phase40-stage-10-interactive-2026-09-21": Cell(
        "prompts/phase-40-agent-reachability.md", None,
        note="Phase 40 stage 10, re-run on the interactive loop. In force at "
             "collection: amendments 4 (interactive loop, 2026-09-18) and 5 "
             "(cost criterion, 2026-09-21), both committed before it. The "
             "live collection is outside the repository; this is its tracked "
             "text evidence.",
    ),
    "reports/raw/phase40-stage-30-2026-09-21": Cell(
        "prompts/phase-40-agent-reachability.md", None,
        note="Phase 40 stage 30, the first collection under amendment 6 "
             "(same-payment re-decision, committed 2026-09-21T15:19, two and "
             "a half hours before the data).",
    ),
    "reports/raw/phase40-stage-100-2026-09-22": Cell(
        "prompts/phase-40-agent-reachability.md", None,
        note="Phase 40 stage 100 -- the stage that FAILED and closed the "
             "workstream by author decision. First collection under "
             "amendments 8 (paired seeding) and 9 (transmission boundary); "
             "amendment 7 withdrew the stage-30 clause before it.",
    ),
```

### Why the pre-registration goes in the `prediction` slot, not `prompt`

`prompts/phase-40-agent-reachability.md` lives under `prompts/`, so the `prompt`
slot looks like the natural home. It is the wrong one.

`prediction_paths()` (`scripts/check_prereg_order.py:225-227`) collects only
`Cell.prediction`, and that set is what `check_blobs()` pins against
`reports/prereg-blobs.json`. A pre-registration placed in the `prompt` slot is
order-checked but **not** blob-pinned, so it could be rewritten after the fact
and nothing would notice — which is precisely the blind spot phase 37 opened
`prereg-blobs.json` to close (`scripts/check_prereg_order.py:180-190`). Phase 40
is the workstream with nine amendments and two acknowledged stop-rule overrides;
it is the last one that should be exempt from content pinning.

Nothing in the check constrains a `prediction` to live under `reports/` — both
slots are plain path strings, and the labels are conventions.

**This is already the project's practice, settled independently on the same
day.** Commit `ba1638c` pre-registers phase 53 and adds an `EXPECTED` entry
whose pre-registration lives under `prompts/`:

```python
    "experiments/results/abd-immediate-2026-09-24": Cell(
        "prompts/phase-53-abd-immediate-2026-09-24.md",
        "prompts/phase-53-abd-immediate-2026-09-24.md",
        note="... One file carries both the prediction and the issued scope ...",
    ),
```

It puts the `prompts/` file in the `prediction` slot — and in both slots, since
one file carries both roles — and `59ea288` then runs `--update-blobs` so the
file is pinned. The proposal above is the same shape applied to phase 40.

### The consequence, which must be carried out in the same change

Adding the path to `prediction` makes `check_blobs()` demand a recorded blob it
does not have:

> `prompts/phase-40-agent-reachability.md: pre-registered but has no recorded
> blob -- a new prediction was added without recording it, so a later edit to it
> would be invisible`

So the fix is two steps, not one:

1. add the four entries above;
2. run `python scripts/check_prereg_order.py --update-blobs`, which rewrites
   `reports/prereg-blobs.json` — **14** predictions instead of the 13 recorded
   at `59ea288`.

Verified in advance: the file is safe to pin as-is. Its blob at first commit and
its blob at `HEAD` are both `8f82bf2e`, so it needs **no** entry in `EDITED` —
unlike `phase-report-9-prediction-2026-08-21.md` and
`phase-report-ws6-prediction-corrected-2026-09-08.md`, which do. The gate already
reports `pre-registrations byte-identical to their first commit: yes`, and adding
this one keeps that true.

### One honest wart in the fourth entry

`predates_rule=True` is a misnomer for `phase40-deployment-2026-09-18`. That
collection is from 2026-09-18, three weeks *after* rule 5 was adopted; the flag
is being borrowed as a general "this root is not a collection" escape. The
existing `reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14` entry already
borrows it the same way, with the note `"NOT a collection. Quarantined debris
from a failed run"`. So the proposal above follows the established convention
rather than inventing one.

The honest version is a second flag — `not_a_collection: bool = False` on `Cell`,
printed as `NOT-A-COLLECTION` rather than `EXEMPT` — so the audit's own output
distinguishes "predates the rule" from "the rule does not apply". That is a small
change to `Cell`, to `audit()`'s exemption branch and to the two existing notes.
**Recommended, but it is a change to the check's semantics and is therefore the
author's call, not a transcription.**

### The alternative that was considered and rejected

`phase40-deployment-2026-09-18` would also pass as an ordinary cell:

```python
    "reports/raw/phase40-deployment-2026-09-18": Cell(
        "prompts/phase-40-amendment-1-snapshot-2026-09-18.md", None),
```

Amendment 1's first commit is `08f6e4d` — the **same commit** as the data. The
check tests `date > data_date`, which is false for equal dates, and `is_ancestor`
is reflexive, so this passes. It is rejected because passing on a technicality
about equal timestamps describes the artifact less truthfully than saying it is
not a collection, and because a future reader would have to rediscover why a
pre-registration and the thing it supposedly predicts share one commit.

---

## 4. What this does and does not settle

**Settles.** The four failures are a table omission. The phase-40 collections
were pre-registered, the pre-registration precedes every one of them, each
stage's governing amendment precedes its own data, and the pre-registration has
not been edited since. `reports/audit-pack.md`'s "gates green" was untrue and is
corrected in this session (`reports/audit-pack-corrections-2026-09-24.md`).

**Does not settle.** Whether the amendments themselves should be blob-pinned.
Nine amendments govern this phase and none would be pinned by the proposal
above, because `Cell` holds one prediction path. Two of the nine are
self-declared overrides of a fired stop rule (a5, a7), which is exactly the
material a reader would want protected from silent rewriting. Either `Cell`
grows a list, or the amendments are pinned by a separate mechanism, or the
project accepts that only the original is pinned and says so. **Open, and not
this report's to decide.**

**Not done.** `scripts/check_prereg_order.py` and `reports/prereg-blobs.json` are
untouched. The gate still exits 1.
