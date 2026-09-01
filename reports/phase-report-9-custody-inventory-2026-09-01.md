# Custody inventory — where the raw evidence is, before a DOI is minted

**Unit 0 of the pre-Phase-10 assessment.** A DOI is permanent. This establishes
where the evidence behind the manuscript physically exists, separately from what
the manuscript claims. **Custody and claims are separate verdicts and neither
absorbs the other**; the claims assessment is units 1 and 1b.

Tool: `phase8-driver/custody_survey.sh`. Read-only — `find`, `ls`, directory
counts. No ledger opened, no WAL checkpointed, nothing written into any results
root.

---

## 1. The survey is INCOMPLETE, and it says so

Three trees could not be read from this session:

```
=== /root/aep/experiments/results ===
  UNREADABLE (parent /root denied) -- re-run with sudo
=== /root/aep-phase8/experiments/results ===
  UNREADABLE (parent /root denied) -- re-run with sudo
=== /root/aep-stage3/experiments/results ===
  UNREADABLE (parent /root denied) -- re-run with sudo
```

The default WSL user is `hamzakhan`; `/root` is `700`. **The script exits 2 and
states that it has not established the unreadable trees are empty.** The WSL half
of §3 below is therefore taken from the committed record (B15) and is labelled as
such. The privileged re-run is pending.

### The first version of this script was fail-open, and I wrote it

It tested `[ ! -d "$base" ]` and printed **ABSENT** — which is what an
unprivileged shell gets for `/root`. So a tree holding 432 run directories
reported as holding nothing, in a survey whose entire purpose is to find out
whether the evidence still exists.

**"There is no data here" and "I am not allowed to look" rendered identically.**
That is F.0d's fail-open class — the same shape as `pgrep` matching nothing, and
the same shape as §F.0f's incomplete search — now in a tool written for a task
about custody. It failed in the direction that makes the situation look
*resolved*: three empty trees would mean everything is in one place and simply
findable.

The script now distinguishes three outcomes — **ABSENT** (verified, every parent
readable), **UNREADABLE**, and a count — and an UNREADABLE sets a non-zero exit
so a caller cannot mistake a blocked survey for a complete one.

---

## 2. Derived directly: the Windows side

| root | run directories in the working clone |
|---|---|
| `matrix` | **84** |
| `b2-2026-08-21` | **60** |
| `b2-s1-2026-08-21` | **60** |
| `b2-s2-2026-08-21` | **60** |
| `b2-s3-2026-08-21` | **60** |
| `b2-paired-s1`, `b2-paired-v2-s1…s4`, `b2-paired-v2-s2-aborted` | **0 each** |
| `smoke` | 6 |
| `fsync-always`, `selfcheck`, `selfcheck-c5`, `throughput` | 0 each |

Independently corroborated against a second copy: `matrix` 84, and each of the
four 21 August `b2` roots at 60.

### Archives

```
b2-paired-v2-s3-2026-08-28.tar.gz   1 208 538 bytes   31 Aug 11:59
b2-paired-v2-s4-2026-08-28.tar.gz   1 214 718 bytes   31 Aug 11:59
```

**Two tarballs. Both written 31 August.** Each carries a full SHA-256 manifest
and before/after ledger mtimes; that part is done properly. There is no archive
of anything else.

---

## 3. From the committed record (B15) — pending privileged re-verification

`matrix` is complete only at `/root/aep/...` at **432** runs. `/root/aep-phase8`
holds **0** runs for the 21 August roots and **120 each** for Phase 8.4's s1–s4.
**No single tree on this machine holds all of the project's raw evidence.**

---

## 4. What it adds up to

| evidence | where it lives | archived? |
|---|---|---|
| **`matrix`, 432 runs** | complete only in WSL; **19.4%** in the working clone | **no** |
| **21 Aug `b2` roots, 240 runs** | working clone on `D:` only | **no** |
| **Phase 8.4 s1, s2** | WSL only | **no** |
| Phase 8.4 s3, s4 | WSL, plus a tar on `D:` | yes |

**`main.tex`'s numbers-discipline header names
`matrix/analysis/per-cell-metrics.csv` as "the ONLY quotable source for rates".**
So the manuscript's headline detection result rests on the one tree with no
archive of any kind.

> **Nothing the paper depends on has an off-host copy, and the only archive
> written covers the two newest and least load-bearing roots.**

### The tar is not a backup in the sense that matters

`D:` is off the WSL ext4 VHDX and **on the same physical machine**. It removes
the one-filesystem risk. It does not remove the one-machine risk. **There is no
off-host copy of any raw run, for any phase.** The only off-host material is the
tracked derived products via `origin` — roughly 1% of each root.

The archive is therefore correctly described as a *second-filesystem copy of two
roots*, not as a backup of the evidence.

---

## 5. Two obligations, two dates, and only one is three weeks old

| | recorded | age at 1 Sep | obligation |
|---|---|---|---|
| **D4** — the raw archive is undeposited (`reports/paper-review-2026-08-11.md`) | **11 Aug** | **21 days** | **reproducibility** |
| Handover §7 — no off-host raw storage | **31 Aug** | **1 day** | **durability** |

> **Correction, same day, before the recommendation was written.** The first
> row of this table originally read *"the raw archive is unpublished **while §IX
> asserts availability**"*. **That second clause is false and I did not check it
> before writing it.** `09-artifact.tex:4-10` reads:
>
> > "It does *not* currently contain the 432 raw run directories, the voided
> > run, or a complete raw-evidence checksum manifest. No immutable external
> > archive DOI is currently available. Those materials must be deposited and
> > verified before an availability claim is made for the full raw evidence."
>
> **D4's manuscript half is closed.** The review offered two remedies — publish
> the archive, or rewrite §IX to say what is tracked versus archived — and the
> second was taken. **What is open is the deposit itself, which is Phase 10's
> job**, and the 21 days attach to that and not to an overclaim. Asserting from
> memory what a section says, in a report about whether claims are supported.

These are different problems with different remedies. Publishing the archive
would discharge D4 and would incidentally discharge durability; taking an
off-host copy would discharge durability and not D4. **Conflating them makes the
durability exposure look three weeks stale and the reproducibility gap look
one day old, and neither is true.**

---

## 6. Custody verdict

**The claims assessment is not affected by anything here**, and this verdict does
not enter it.

- **Integrity of what exists: good.** Roots are frozen, manifests exist, the two
  archives carry full manifests and mtime evidence, and B15 already records
  precisely what `SHA256SUMS` does and does not cover.
- **Durability: bad, and worst where it matters most.** The single tree the
  manuscript's headline rates come from has no archive, and no raw run of any
  phase exists off this machine. **One machine failure ends the ability to
  re-derive any rate in the paper from raw evidence.**
- **This is not an argument against minting a DOI. It is an argument for doing
  something before the DOI makes the citation permanent**, because a permanent
  identifier pointing at evidence that exists in one place is a stronger promise
  than the storage supports.

**Not fixed here.** No remedy is proposed or applied; that is a separate decision
with a cost.
