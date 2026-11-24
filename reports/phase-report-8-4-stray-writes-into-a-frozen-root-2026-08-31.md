# Phase 8.4 — two stray directories were created inside a frozen root, and removed

**Incident record.** The generalised defect this is an instance of is filed
separately in the backlog; this document is the account of what happened, what
was removed, and the evidence that the root is intact afterwards.

**No committed artefact was affected.** Commit `828a3fb` never contained either
stray, and `b2-paired-v2-s3-2026-08-28` verifies 18 OK / 0 FAILED before and
after the removal.

---

## 1. What was written, and by what

Both writes landed in
`experiments/results/b2-paired-v2-s3-2026-08-28/`, in the tracked Windows clone,
on 2026-08-31.

| path | written by | cause |
|---|---|---|
| `.ai/track.md` | the session activity hook | wrote to a relative path while the shell's cwd was the frozen root |
| `phase8-driver/derive_negations.py` | operator command | `mkdir -p phase8-driver` intended for the repository root, run with a stale cwd |
| `phase8-driver/publish_from_sums.sh` | operator command | same |

**The cause was a stale working directory.** A verification step earlier in the
same session ran `cd experiments/results/b2-paired-v2-s3-2026-08-28 && sha256sum
-c SHA256SUMS`. The shell's cwd persists between commands, so the next relative
`mkdir` resolved inside the frozen root rather than at the repository root. The
hook's own relative write followed the same cwd — its three recorded lines
reference `../../../../phase8-driver/...`, which is the visible fingerprint of
where it was standing.

## 2. Why nothing was committed

`.gitignore` ignores `experiments/results/b2-paired-v2-s3-2026-08-28/*` and
re-opens only the paths `SHA256SUMS` names. Both strays fell under the wildcard
and neither was ever staged. `git status --short` listed neither, and
`git ls-files` on the root returns the same 19 paths before and after.

**This is luck rather than protection, and it should be read that way.** The
negation block was written to track exactly the frozen set; keeping the strays
out was a side effect of that, not a check that noticed them. Nothing warned that
a frozen root had grown two directories.

## 3. Why `sha256sum -c` did not notice either

`sha256sum -c` verifies the entries a manifest names. It has no concept of a file
the manifest does not name, so an addition is invisible to it by construction.
Both roots reported 18 OK / 0 FAILED throughout — while one of them contained
three files that were not there at freeze time.

**A passing digest check is not a statement that a root is unchanged. It is a
statement that the named files are unchanged.** That distinction is the subject
of the backlog item this incident is filed under.

## 4. The removal, and the constraint it was done under

A recursive delete driven by a stale cwd inside a frozen root is how run
directories get lost, and the cause here *was* a stale cwd. So:

- the root was enumerated completely first — every file and every directory, by
  absolute path — and the listing inspected before anything was removed;
- the three files were removed **individually, by explicit absolute path**, with
  no wildcard and no `rm -rf`;
- the two directories were removed with **`rmdir`**, which fails on a non-empty
  directory. That is the safety property: had the enumeration been wrong, `rmdir`
  would have refused rather than deleted.

`.ai/track.md` was copied to
`/mnt/d/personal/AEP/phase8-raw-archive/stray-track-md-from-s3-root.txt` before
removal. It is hook telemetry, not evidence, but it is the only record of where
the hook was standing.

## 5. State afterwards, verified

| check | result |
|---|---|
| files anywhere under the root | **19** |
| directories under the root | 2 — the root and `analysis/` |
| entries in `SHA256SUMS` | 18 |
| files present that `SHA256SUMS` does not name | **0** |
| entries named that are absent from disk | **0** |
| `sha256sum -c SHA256SUMS` | **exit 0, 18 OK / 0 FAILED** |
| `git status --short` | nothing new |
| `git ls-files` on the root | 19, unchanged |

The tracked clone's copy of this root is now **18 of 19 files attested, 94.7%** —
against **18 of 1827, 1.0%** for the complete root on the collection host. The
committed tree looks almost fully verified precisely because the evidence is not
in it. That contrast belongs beside B15 rather than as reassurance.

## 6. Not fixed here

Nothing prevents this recurring. The remedy is not "be careful with cwd" — it is
that a frozen root should be able to refuse a write, or at minimum that the freeze
should be checkable for *additions* and not only for modifications. Filed in the
backlog; not implemented in this phase.
