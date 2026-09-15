# Phase 38 — the three loose ends, and one of them was a live defect

## Asked / Done

Asked: rule on the provenance-stamp asymmetry, dispose of `.scratch/` and the
session transcript, close the audit's content gap.

Done: all three. **Two turned out to be more than tidying.** The provenance
asymmetry was hiding a defect — the three tracked stamps could not verify in a
clean clone. And the content check, on its first run, found **two
pre-registrations edited after their first commit**, which is the gap phase 37
said nothing covered.

---

## 1. The four provenance stamps — all tracked

**The stated reason for ignoring one did not survive reading the file.**
`.gitignore:111` said it *"describes one machine's last build, not the
repository's state"*. The payload is `{sources: {relpath: sha256}, version}` —
no absolute path, no hostname. It records source-to-artifact correspondence,
which **is** repository state, and tracking it is what lets a clone check that
the shipped PDFs were built from the shipped sources. Untracked, that check
fails in every clone with *"no stamp"*.

**What was actually blocking it was a live defect.** Of the 24 sources, exactly
one was gitignored: `paper/.ai/track.md`, a session log. A clone does not have
it; `source_digests` walks the filesystem; `verify` treats a recorded-but-absent
source as STALE. **So the three already-tracked stamps read STALE in any clean
clone** — a gate that passed on this machine and failed anywhere else, for a
reason nobody had written down.

`paper_provenance.NON_SOURCE_DIRS` now excludes `.ai/`. Demonstrated both ways
against a clone simulated from `git ls-files paper`:

```
the clone has .ai/track.md?  NO -- as in any real clone
  .build-provenance.json            FRESH
  .build-provenance-anon.json       FRESH
  .build-provenance-supp.json       FRESH
  .build-provenance-supp-anon.json  FRESH

with the OLD behaviour (.ai/ counted as a source):
  sources the clone would be missing: ['.ai/track.md']
  -> a stamp written here would read STALE in the clone: YES
```

## 2. `.scratch/` and the transcript — both kept, and a correction

**Phase 34 classified `.scratch/` wrongly** as "transient build and probe
output". Much of it is. But it also holds **authored one-off probes** from the
phase-11 forensics: `phase11-clock.py`, `phase11-ctime.py`,
`phase11-e5-forensics.py`, `map_crossroot.py`, `map_macros.py`,
`HOLD-provenance.py`.

Their findings are already in the phase reports, so nothing depends on them.
Kept anyway: deleting authored work to reclaim 3.3 MB of ignored disk is
irreversible and buys nothing. **Neither ships** — `.scratch/` is gitignored, so
it is absent from every clone and from the deposit.

The **session transcript** is kept on the same reasoning with less to it: a tool
artefact, ignored, absent from clones, and the record of what was decided lives
in `reports/` and `prompts/` regardless.

Both dispositions are now stated in `docs/36` §2.5, with the correction.

## 3. The content gap — and what it found immediately

`reports/prereg-blobs.json` records each pre-registration's blob at its **first**
commit and at **HEAD**. The audit compares both: current-vs-record catches an
edit, first-vs-record catches a history rewrite. It does not prevent a rewrite;
it makes one visible — the relationship `RAW-SHA256SUMS` has to the raw trees.

**On its first run it failed, on two real files.** Both were examined; neither
was fixed by rewriting history.

**Phase 9** — two amendments appended in-file on 2026-08-21 at 19:55 and 20:09.
The first data commit is **2026-08-27**, six days later. 135 insertions, 0
deletions. *Ordering is sound.* The deviation is that the amendments went into
the original rather than into separate files, which is the convention rule 5
settled on afterwards.

**WS-6** — edited twice on **2026-09-09, after the 2026-09-08 data commit.**
That is the shape rule 5 exists to prevent, so it was read rather than assumed.
104 insertions, 0 deletions, and the added text labels itself in its first line:

> *"Recorded 8 September, after the corrected cell was read. Deliberately not
> fixed."*

It documents a defect in the verdict script — `cell_interval` defaulting a
missing metric field to zero — and **declines to change it**, precisely because
the script had read data. No hypothesis, threshold or margin was altered.

**Verdict: a convention violation, not a changed prediction.** Post-data material
belongs in a report, not appended to the pre-registration, because a reader
should not need `git` to tell which half is which. Recorded in `EDITED` with
that ruling.

**An `EDITED` entry records a ruling; it does not open the door.** The check
compares the current blob against the recorded current, so any *further* edit
fails — and a first/current divergence with no ruling fails too, so a record
written from an already-edited history cannot bless it silently.

## 4. Rule 13

`tests/test_prereg_order.py` is now 11 tests, each in a throwaway git repository
(R17 — nothing touches the real history):

```
an edited prediction is detected                    FAILS "EDITED"
an unexplained first/current divergence is flagged  FAILS "nobody has said why"
a classified edit passes, a further one does not    both directions
a prediction with no recorded blob fails            FAILS "no recorded blob"
```

**One defect found in my own wiring:** `audit()` read the *real* repository's
blob record regardless of which repo it was auditing, so two existing tests
broke when the check was added. The path is now repo-relative.

## 5. Raw outputs

```
check_prereg_order.py    cells: 31   ok: 27   exempt: 4   failing: 0
                         pre-registrations byte-identical to first commit: yes
tests/test_prereg_order.py   11 passed
check_paper_numbers.py   43 passed, 0 failed
validate_citations.py    OK: 371 citations, 0 invalid
provenance stamps        4 of 4 tracked, 4 of 4 FRESH in a simulated clone
.tex changed             0
deletions                0
```
