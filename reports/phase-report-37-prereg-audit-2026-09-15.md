# Phase 37 — WS-10: the pre-registration order audit

## Asked / Done

Asked: build `check_prereg_order.py`, enumerate cells **from the data**, check
both orderings, watch it fail, report every cell including passes, state the
domain, wire it into CI.

Done: all of it. **31 cells: 27 ok, 4 exempt, 0 failing.** No ordering violation
exists, and nothing was fixed by rewriting history — there was nothing to fix.

**Two things the audit caught on its own first run, and one it caught in
itself**, are in §4 and §5. Neither is a rule-5 violation; both are the kind of
defect an audit is supposed to produce.

---

## 1. The per-cell table

Enumeration runs from `git ls-files`, so a collection with no pre-registration
cannot hide by being absent from the prediction list. **A root missing from the
table is a failure, not a skip.**

| collection root | prediction | pred date | first data | data date | verdict |
|---|---|---|---|---|---|
| `b2-2026-08-21` | `9-prediction` | 08-21 | `b2ab570` | 08-27 | ok |
| `b2-s1-2026-08-21` | `9c-prediction` | 08-21 | `b2ab570` | 08-27 | ok |
| `b2-s2-2026-08-21` | `9c-prediction` | 08-21 | `b2ab570` | 08-27 | ok |
| `b2-s3-2026-08-21` | `9c-prediction` | 08-21 | `b2ab570` | 08-27 | ok |
| `b2-paired-s1-2026-08-28` | `8-prediction` | 08-27 | `73381e6` | 08-28 | ok |
| `b2-paired-v2-s1-2026-08-28` | `8-amendment-1` | 08-28 | `75a9019` | 08-28 | ok |
| `b2-paired-v2-s2-2026-08-28` | `8-amendment-1` | 08-28 | `4d1d309` | 08-28 | ok |
| `b2-paired-v2-s2-aborted-2026-08-28` | `8-amendment-1` | 08-28 | `0f0ee8f` | 08-28 | ok |
| `b2-paired-v2-s3-2026-08-28` | `8-amendment-1` | 08-28 | `828a3fb` | 08-31 | ok |
| `b2-paired-v2-s4-2026-08-28` | `8-amendment-1` | 08-28 | `828a3fb` | 08-31 | ok |
| `phase10-replication-drvfs` | `10-prediction` | 09-02 | `c63aea0` | 09-02 | ok |
| `phase10-replication-drvfs-arbb30` | `10-prediction` | 09-02 | `c63aea0` | 09-02 | ok |
| `phase10-replication-ext4` | `10-prediction` | 09-02 | `c63aea0` | 09-02 | ok |
| `phase10-replication-ext4-arbb30` | `10-prediction` | 09-02 | `c63aea0` | 09-02 | ok |
| `phase13-armA-s1` | `13-prediction-armA` | 09-03 | `c25dfd0` | 09-04 | ok |
| `phase13-armA-s2` | `13-prediction-armA` | 09-03 | `c25dfd0` | 09-04 | ok |
| `phase13-armA-s3` | `13-prediction-armA` | 09-03 | `c25dfd0` | 09-04 | ok |
| `phase13-inflight-s1` | `13-prediction-inflight` | 09-04 | `c25dfd0` | 09-04 | ok |
| `phase13-inflight-s2` | `13-prediction-inflight` | 09-04 | `c25dfd0` | 09-04 | ok |
| `ws4-writeloss-s1-2026-09-07` | `ws4-prediction` | 09-04 | `252e2d3` | 09-07 | ok |
| `ws6-b5-s1-2026-09-08` | `ws6-prediction` | 09-07 | `0c6bcf4` | 09-08 | ok |
| `ws6-b5-s1-2026-09-08-attempt3` | `ws6-prediction-corrected` | 09-08 | `7fddd91` | 09-08 | ok |
| `ws5-2026-09-10/t1-p0-everysec` | `ws5-prediction` | 09-10 | `729fbfa` | 09-11 | ok |
| `ws5-2026-09-10/t1-incomplete` | `ws5-prediction` | 09-10 | `729fbfa` | 09-11 | ok |
| `ws5-2026-09-10/t2-p30` | `ws5-prediction` | 09-10 | `729fbfa` | 09-11 | ok |
| `ws5-2026-09-10/t2-keying` | `ws5-prediction` | 09-10 | `729fbfa` | 09-11 | ok |
| **`fsync-always-2026-09-14`** | **`ws5-amendment-3`** | **09-14** | `3778199` | 09-14 | **ok** |
| `matrix` | — | — | `831c796` | 08-10 | **EXEMPT** |
| `fsync-always` | — | — | `831c796` | 08-10 | **EXEMPT** |
| `stage3-replication-2026-08-13` | — | — | `57793b1` | 09-14 | **EXEMPT** |
| `INCIDENT-fsync-always-destroyed` | — | — | `1e37fff` | 09-14 | **EXEMPT** |

**Amendments are rows, not footnotes.** The `always` arm's pre-registration is
**amendment 3**, not the base file: amendment 3 pinned the lower-mode threshold
and was committed before a single run of that arm existed, which is the property
phase 19 stopped a launch to establish. The audit confirms it independently.

The v2 paired sessions point at **amendment 1**, not the base prediction,
because amendment 1 is what introduced run-level interleaving and is the reason
those sessions were re-collected at all.

## 2. Cells without a prediction

**Four, all EXEMPT, none a violation.** Three predate rule 5, which was adopted
in the phase 8 pre-registration on 2026-08-27:

* **`matrix`** — the 432-run evaluation, collected across early August. Its
  design is in the phase 2B and session-3 reports.
* **`fsync-always`** — the three-run `always` cell, 2026-08-07, under amendment
  F0(iii).
* **`stage3-replication-2026-08-13`** — two weeks before the rule existed;
  recovered onto `main` in phase 29.

A cell collected before rule 5 cannot retroactively acquire a pre-registration,
and backdating one would be the audit lying about its own subject. `EXEMPT` is
printed in the table rather than filtered out, so the exemption is visible on
every run.

The fourth, `INCIDENT-fsync-always-destroyed`, **is not a collection**: it is
quarantined debris from a failed run, retained under phase 20 §6.

## 3. Both orderings

Every non-exempt cell is checked twice: **commit date**, which is what a reader
sees in the log, and **ancestry** via `merge-base --is-ancestor`, which is what
survives a rebase or a clock skew. All 27 pass both.

## 4. What the audit caught on its first run

**A mistyped path in its own table.** The first run failed:

```
FAIL  experiments/results/fsync-always-2026-09-14:
      prompt prompts/phase-21-ws9-always-launch.md is not in the history
```

The file is `phase-21-ws5-...`. The check refused to skip a path that names
nothing — which is the behaviour that matters, because a lenient version would
have reported that cell as passing on a prompt that does not exist. There is now
a test for exactly this case, citing this incident.

## 5. What the audit caught in itself

The ancestry test failed at first, and for an instructive reason: `git log -- <path>`
searches only the current branch, so a prediction committed on an unmerged
branch was reported **"not in the history"** rather than **"not an ancestor"**.

Both are failures, so the audit's verdict was right either way. But the message
was wrong, and a reviewer reading *"not in the history"* about a file plainly
present in the repository would reasonably distrust the tool. `first_commit` now
searches `--all`, so such a file is **found and then rejected for ancestry**,
with the precise message.

## 6. The domain — what this cannot see

Printed on every run, because ten R14 instances say a green check means green
over the part it can see:

```
COVERS  : the ORDER of commits -- prediction before prompt before first data --
          by date and by ancestry, for every tracked collection root.
DOES NOT: (1) read the prediction's CONTENT, so a file committed early and
          rewritten later still passes here.
          (2) know when data was COLLECTED, only when it was COMMITTED.
          (3) cover untracked collections -- the /root/aep* trees in docs/36 §4.
```

**What covers each gap, honestly:**

1. **Nothing automatic.** `git log -p` on a prediction shows every edit, and
   rule 5's "amendments are new files, the original stays unedited" convention
   is what makes drift visible — but no gate enforces it. This is the largest
   hole and it is not closed by this pass.
2. **Partially.** Each phase report records the launch time, and the collection
   `MANIFEST.md` carries run timestamps, so collect-before-predict is
   reconstructible by hand from two sources. Not checked.
3. **The phase reports alone.** `docs/36` §4 lists them.

## 7. Failing-branch evidence

`tests/test_prereg_order.py`, seven tests, each building a throwaway git
repository in `tmp_path` — **nothing touches the real history** (R17), which
matters unusually here since the audit's subject *is* commit order.

```
prediction before data                        passes
prediction AFTER data                         FAILS  "AFTER first data"
a collection with no table entry              FAILS  "no entry in EXPECTED"
a prediction missing from history             FAILS  "not in the history"
ancestry checked, not only the date           FAILS  "not an ancestor"
an exempt cell is reported, not hidden        passes, prints EXEMPT
the domain is printed every run               passes
```

The fifth is the one a date-only check would pass: the prediction's date
precedes the data while its commit is unreachable from it.

## 8. CI

New job `prereg-order`, and **`fetch-depth: 0` is load-bearing** — the audit
reads commit dates and runs `merge-base`, and a shallow clone has neither, so
the check would pass by being unable to look. That is the R14 shape exactly, so
the depth is set deliberately and the comment in the workflow says why.

## 9. Raw outputs

```
check_prereg_order.py    cells: 31   ok: 27   exempt: 4   failing: 0
tests/test_prereg_order.py   7 passed
CI jobs                  citations, prereg-order, model-check, test,
                         waitaof-durability, paper-numbers
check_paper_numbers.py   43 passed, 0 failed
validate_citations.py    OK: 371 citations, 0 invalid
.tex changed             0
history rewritten        no commits amended, rebased or reordered
```
