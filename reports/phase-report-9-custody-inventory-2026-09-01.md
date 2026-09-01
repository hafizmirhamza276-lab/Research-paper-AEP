# Custody inventory — where the raw evidence is, before a DOI is minted

**Unit 0 of the pre-Phase-10 assessment.** A DOI is permanent. This establishes
where the evidence behind the manuscript physically exists, separately from what
the manuscript claims. **Custody and claims are separate verdicts and neither
absorbs the other**; the claims assessment is units 1 and 1b.

Tool: `phase8-driver/custody_survey.sh`. Read-only — `find`, `ls`, directory
counts. No ledger opened, no WAL checkpointed, nothing written into any results
root.

---

> **SUPERSEDED IN PART, 1 Sep.** Sections 1, 3 and 5a were written while `/root`
> was unreadable. The privileged survey has since run and **§5b–§5e are derived
> from it**. Where they disagree with §3 or §5a, §5b–§5e are authoritative. §1 is
> kept because the fail-open story in it is the reason the later sections can be
> trusted.

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

## 5a. Derived inventory, 1 Sep — and it is still INCOMPLETE

**Privilege was authorised for reads. It could not be used: `sudo -n true`
returns *"a password is required"*, and I cannot supply one.** The `/root` half
is therefore still undrived. **The tool is not at fault** — it reports
`UNREADABLE (parent /root denied)` and exits 2, which is the fail-closed
behaviour §1 describes. No `ABSENT` was printed for a tree that exists.

**The one command that closes this**, to be run with a leading `!`:

```
! wsl -- sudo bash /mnt/d/personal/AEP/Research-paper-AEP/phase8-driver/custody_survey.sh
```

Read-only: `find`, `du`, `ls`. No ledger opened, no WAL checkpointed, nothing
written anywhere.

### What the survey does establish (Windows side, measured)

| root | runs | `.sqlite3` / `-wal` / `-shm` | triple | size |
|---|---|---|---|---|
| `matrix` | **84** | 84 / 84 / 84 | OK | **54 M** |
| `b2-2026-08-21` | 60 | 60 / 60 / 60 | OK | 12 M |
| `b2-s1-2026-08-21` | 60 | 60 / 60 / 60 | OK | 12 M |
| `b2-s2-2026-08-21` | 60 | 60 / 60 / 60 | OK | 12 M |
| `b2-s3-2026-08-21` | 60 | 60 / 60 / 60 | OK | 12 M |
| `b2-paired-*` (6 roots) | **0** | 0 | — | 84–104 K each (analysis only) |
| `fsync-always` | **0** | 0 | — | **24 K (analysis only)** |
| `throughput` | 0 | 0 | — | 9.2 M |
| `smoke` | 6 | 6 / 6 / 6 | OK | 1.9 M |
| **clone total** | | | | **114 M** |

**Every ledger triple present is complete.** `db = wal = shm` in every root that
has runs, so no triple has been split by a copy.

### The roots the manuscript actually quotes, derived from the generator

`scripts/paper_tables.py` and its invocation consume **ten** result roots:

`matrix` · `fsync-always` · `b2-2026-08-21` · `b2-s1/s2/s3-2026-08-21` ·
`b2-paired-v2-s1/s2/s3/s4-2026-08-28`

**`throughput`, `smoke`, `selfcheck*` and the superseded `b2-paired-s1` are not
quoted by the manuscript.** They are not custody priorities.

### The finding that makes the privileged run necessary

> **`fsync-always` is quoted by the manuscript — it is the entire `always` column
> of the deployment table — and its run directories are in no tree I can read.**
> The clone holds 24 K of analysis products and zero runs.

Either its runs are under `/root` and the privileged survey will find them, **or
a manuscript-quoted collection has no raw evidence anywhere on this machine.**
The survey cannot currently tell those apart, and that is precisely the
distinction §1 exists to preserve.

### Size, extrapolated and labelled as such

The clone's `matrix` is 54 M for 84 runs — **643 KB per run**. Applying that to
the 432 B15 records gives **≈ 278 M**, on the assumption that the 84-run subset
is size-representative, **which is not established**. The `b2` roots measure
200 KB per run directly.

| collection | runs | size |
|---|---|---|
| `matrix` | 432 | **≈ 278 M** (extrapolated) |
| `b2-*-2026-08-21` ×4 | 240 | **48 M** (measured) |
| `b2-paired-v2-*` ×4 | 480 | ≈ 96 M (extrapolated at 200 KB/run) |
| `fsync-always` | ? | ? |
| **manuscript-quoted total** | **1152 +** | **≈ 420 M** |

**Compression is the number that matters and it is large.** The `s3` tarball is
**1 208 538 bytes for 120 runs** whose uncompressed size is ≈ 24 M — roughly
**20:1**. At that ratio the entire manuscript-quoted raw evidence is **≈ 21 M
compressed**, which is small enough that size does not constrain any option in
the companion report.

## 5b. THE DETERMINATION: `fsync-always`'s runs exist

**Reported first and separately, because it was not a custody question until it
was answered.** If the runs had been absent, a manuscript-quoted collection would
have had no raw evidence anywhere, which is a reproducibility and honesty problem
about `09-artifact.tex` rather than a backup problem.

> **They exist.** `/root/aep/experiments/results/fsync-always` holds **6 run
> directories, 3.2 M, `db = wal = shm = 6`, triple intact.**

And the identification is by name, not by count. The tracked
`fsync-always/analysis/per-execution.csv` contains 60 execution rows over
**6 distinct `run_id`s**. The six directories under `/root/aep` are:

```
aep_full-none-payments-e5e5c7dc-r0   b3_intent_no_barrier-none-payments-85b7630d-r0
aep_full-none-payments-e5e5c7dc-r1   b3_intent_no_barrier-none-payments-85b7630d-r1
aep_full-none-payments-e5e5c7dc-r2   b3_intent_no_barrier-none-payments-85b7630d-r2
```

**Set-equal to the six `run_id`s in the tracked CSV.** This is the orphan gate's
shape applied to custody: two independently produced sets, no threshold, exact
equality. A count of 6 alone would have been consistent with six unrelated
directories.

**Consequence: nothing is filed against `09-artifact.tex`.** `fsync-always` is
not a submission item and not a reproducibility problem. Per your re-ranking it
slots back in after `matrix`, at rank 2.

**But its reason for being there has changed, and the ranking should not keep a
rationale the evidence has withdrawn.** The options report ranked it second
*"because it may already be lost"*. It is not lost. What justifies rank 2 now is
different and weaker: it is quoted, it exists in exactly one tree, and it is
3.2 M — cheap enough that ordering it below anything costs nothing. **That is a
convenience argument where the original was a risk argument.**

**What this cost, and it is worth stating.** While §5a stood — hours, not days;
it was written and superseded the same day — the honest position was "a
manuscript-quoted collection may have no raw evidence anywhere". That was
**entirely an artefact of a permission bit** — `/root` is `0700` and the
default WSL user is `hamzakhan`. The fail-closed rewrite is what kept it stated
as a question instead of resolved as an absence; the first version of the script
would have printed `ABSENT` and the report would have asserted the loss.

---

## 5c. The complete derived inventory, 1 Sep — privileged, `EXIT=0`

`sudo bash phase8-driver/custody_survey.sh`, run with the password supplied by
the operator. **No `UNREADABLE`, no `ABSENT`, exit 0** — every listed tree was
read. Read-only throughout: `find`, `du`, `ls`. No ledger opened, no WAL
checkpointed, nothing written under `/root`.

### `/root/aep` — TOTAL 284 M

| root | runs | triple | size |
|---|---|---|---|
| **`matrix`** | **432** | OK | **262 M** |
| **`fsync-always`** | **6** | OK | 3.2 M |
| `matrix-smoke` | 6 | OK | 2.6 M |
| `smoke` | 6 | OK | 2.0 M |
| **`voided`** | **1** | OK | 348 K |
| `throughput` | 0 | — | 9.2 M |

### `/root/aep-phase8` — TOTAL 134 M

| root | runs | triple | size |
|---|---|---|---|
| **`b2-paired-v2-s1-2026-08-28`** | **120** | OK | 25 M |
| **`b2-paired-v2-s2-2026-08-28`** | **120** | OK | 25 M |
| **`b2-paired-v2-s3-2026-08-28`** | **120** | OK | 25 M |
| **`b2-paired-v2-s4-2026-08-28`** | **120** | OK | 25 M |
| `b2-paired-s1-2026-08-28` (superseded) | 120 | OK | 25 M |
| `b2-paired-v2-s2-aborted-2026-08-28` | 26 | OK | 5.3 M |
| **`b2-paired-v2-s2-operator-aborted-2026-08-28`** | **16** | OK | 2.6 M |
| `b2-2026-08-21`, `b2-s1/s2/s3-2026-08-21` | **0** each | — | 52 K each |
| `fsync-always`, `matrix` | 0 | — | 28 K, 1.2 M |

### `/root/aep-stage3` — TOTAL 5.1 M

**No run directories at all.** `fsync-always` 0, `matrix` 0,
`stage3-replication-2026-08-13` 0. Analysis products only.

### Windows working clone — TOTAL 114 M

Unchanged from §5a: `matrix` 84, the four `b2-*-2026-08-21` at 60 each, `smoke`
6, everything else 0. Every triple complete.

### `D:\personal\AEP`, non-repo

| tree | size | raw runs |
|---|---|---|
| `phase8-raw-archive` | 3.0 M | 2 tarballs (`v2-s3`, `v2-s4`), 31 Aug |
| **`audit-clone`** | 67 M | **0 run directories** — `experiments/results` is **1.2 M** of analysis products for `matrix` and `fsync-always` only |
| `phase8-driver` | 156 K | — |

**`audit-clone` is not a second copy of any raw evidence.** Its 67 M is source
and build output. This matters for your corroboration: you reported *"I
corroborated the Windows-side custody counts independently from my own copy:
matrix 84, and each of the four 21 August b2 roots at 60."* Those counts are
right, and no second Windows tree on this machine holds run directories — so
that corroboration confirmed **the count in the same tree**, not the existence
of a second copy. If it came from a tree that is not the working clone and not
`audit-clone`, that tree is not on this machine and I would want to know where
it is.

### Sizes, now measured rather than extrapolated

| collection | runs | size | vs §5a's extrapolation |
|---|---|---|---|
| `matrix` | 432 | **262 M** | predicted 278 M — **6.1% high** |
| `b2-paired-v2-*` ×4 | 480 | **100 M** | predicted 96 M — 4.0% low |
| `b2-*-2026-08-21` ×4 | 240 | 48 M | measured then |
| `fsync-always` | 6 | 3.2 M | **not sized then** |
| **numerically-quoted total** | **1158** | **≈ 413 M** | predicted ≈ 422 M |
| `voided` (referenced, not quoted) | 1 | 348 K | not counted then or now |

**The extrapolation was about 2% high in aggregate — 422 M predicted against
413 M measured.** Not "under 2%": the error is 2.1% and stating it as "under 2%"
would round a miss into a hit. It held well; it did not hold better than it held.

**Counting note, because two sections of this report define the set
differently.** The 1158 figure covers the **ten roots the manuscript quotes
numbers from**. §5d(i) tabulates **eleven** rows because it adds `voided`, which
the manuscript *references* (`06-evaluation.tex:755`) without quoting a number
from it. **Eleven collections, 1159 run directories, of which 1158 are
numerically quoted.** Both figures are correct under their own definition and
neither is usable without it — which is the F.0i shape in a report rather than in
a rendered sentence.

**Compression, with its precision honest.** The `s3` tarball is
**1 208 538 bytes** against a root `du -sh` reports as **25 M**. `du -sh` is
rounded to two significant figures, so the ratio is **≈ 21:1** and quoting it to
three figures would be precision the input does not carry. At ≈ 21:1 the entire
manuscript-quoted raw evidence is **≈ 20 MB compressed**. §5a's ≈ 21 MB stands.
**Cost is still not the obstacle.**

---

## 5d. The four questions, answered from the survey

### (i) Which root is the authoritative complete copy of each collection

| collection | authoritative copy | anything else? |
|---|---|---|
| **`matrix`, 432** | **`/root/aep`** | clone holds an **84-run subset (19.4%)** |
| **`fsync-always`, 6** | **`/root/aep`** | nothing |
| **`voided`, 1** | **`/root/aep`** | nothing |
| **`b2-2026-08-21`, 60** | **Windows working clone** | `/root/aep-phase8` has **0** |
| **`b2-s1-2026-08-21`, 60** | **Windows working clone** | `/root/aep-phase8` has **0** |
| **`b2-s2-2026-08-21`, 60** | **Windows working clone** | `/root/aep-phase8` has **0** |
| **`b2-s3-2026-08-21`, 60** | **Windows working clone** | `/root/aep-phase8` has **0** |
| **`b2-paired-v2-s1`, 120** | **`/root/aep-phase8`** | nothing |
| **`b2-paired-v2-s2`, 120** | **`/root/aep-phase8`** | nothing |
| **`b2-paired-v2-s3`, 120** | **`/root/aep-phase8`** | **tarball on `D:`** |
| **`b2-paired-v2-s4`, 120** | **`/root/aep-phase8`** | **tarball on `D:`** |

**No single tree holds the manuscript's evidence.** It is split three ways —
`/root/aep` (438 runs), `/root/aep-phase8` (480), the Windows clone (240) — and
**each of the three is the sole holder of part of it.** B15's record is confirmed
and is now derived.

### (ii) Which collections exist in exactly one place

**Nine of the eleven the manuscript relies on:** `matrix` (the clone's 84 is a
subset, not a copy), `fsync-always`, `voided`, all four `b2-*-2026-08-21`, and
`b2-paired-v2-s1` and `-s2`.

Also single-copy but not quoted: `b2-paired-s1` (120, superseded),
`b2-paired-v2-s2-aborted` (26), **`b2-paired-v2-s2-operator-aborted` (16)**,
`matrix-smoke` (6), `throughput`, `stage3-replication`.

**`b2-paired-v2-s2-operator-aborted-2026-08-28` appears in no other tree and in
no prior inventory** — the off-host options report anticipated this case
explicitly (*"if the privileged survey finds a root under `/root` that no tree
here knows about, the ranking changes"*). It is an aborted collection, it is not
quoted, and it does not change the ranking. Recorded because it was predicted
and found.

### (iii) Which have a second copy, and is it on the same machine

**Two: `b2-paired-v2-s3` and `-s4`.** Both second copies are the 31 August
tarballs on `/mnt/d`. **Same machine.**

`smoke` also exists twice (6 in `/root/aep`, 6 in the clone) and is not quoted.

> **No collection, quoted or otherwise, has a copy off this machine.** The
> survey has now established this by enumeration rather than by inference.

### (iv) Is anything the manuscript quotes missing from every tree

> **No. Every collection the manuscript quotes is present, complete, with an
> intact ledger triple.**

That includes `fsync-always` (§5b) and it includes the **`voided` run**, which
`06-evaluation.tex:755` says *"must ship in the external raw archive under
`results/voided/`"* and `09-artifact.tex:7` says is not in the repo. Both
statements are true, and the run exists at `/root/aep/experiments/results/voided`
at 348 K.

**`reports/paper-review-2026-08-11.md` finding #2 is half-resolved, and only the
half about existence.** That review observed *"no such path exists in the
clone"* and concluded the sentence was **unverifiable**. The path exists, in the
one tree the review could not read — so the *existence* question is closed.
**The availability question is not**, and closing it is the deposit, which is
Phase 10's job. A run that exists only under `/root` on one machine is not more
citable than it was in August.

**1158 numerically-quoted run directories, plus `voided`. All 1159 present.
None is missing.**
The custody problem is entirely one of *duplication*, not of *existence* — which
is a materially better position than §5a could establish, and it should be said
plainly rather than buried under the exposure that follows.

---

## 5e. Two findings about the instruments, and one open question

### The survey tool over-counts run directories

It reported `matrix` at **`runs=433`** against **`db=wal=shm=432`**. The triple
check passed, because the three ledger counts agree with each other; **what it
cannot see is a run directory with no ledger at all.**

`phase8-driver/matrix_ledger_gap.sh` identifies it: **`analysis-interim`**, a
derived-products directory dated 7 Aug holding an earlier `per-execution.csv`,
`table-1.csv` and two figure PDFs. **Not a run.** `matrix` is exactly **432**,
which is the number the manuscript uses.

**The bug:** `detail()` excludes only `analysis` and `voided` by name, so any
non-run directory inside a root is counted as a run. It is **fail-open in the
reassuring direction** — it reports *more* evidence than exists. A root that had
lost a run and gained a stray directory would read as intact. F.0d's class again,
in the same tool, in a second place; the fail-closed rewrite fixed the
permission axis and left this one.

**Fail-closed form, not built:** compare run-directory names against ledger-file
locations and report the difference by name, rather than comparing two counts.
The `fsync-always` determination in §5b did exactly that by hand, and it is the
reason that determination is trustworthy while `runs=433` was not.

### The 240 runs with no second copy are gitignored

`.gitignore:165-215` un-ignores each `b2-*-2026-08-21` root and then re-ignores
its contents (`experiments/results/b2-2026-08-21/*`) with allow-list exceptions
for `MANIFEST.csv`, `SHA256SUMS` and eight analysis CSVs. **Eight tracked files
per root; sixty run directories ignored.**

`git status --porcelain experiments/results/` prints **nothing**.

> **The only copy of 240 manuscript-quoted runs sits inside a git working tree,
> ignored, where `git clean -xdf` deletes it silently and `git status` never
> shows it.** These are the roots carrying `\ReplicationPrevented*` — the only
> session-clustered interval in the paper that excludes zero.

The ignore rules are correct policy (raw runs are not source). The exposure is
that *correct policy* and *invisible to every safety net git offers* are the same
configuration.

### OPEN QUESTION, recorded as a question and not an assumption

> **Is `D:` a separate physical device from the WSL ext4 VHDX?**

**Not established by any survey run to date.** The custody reports have said
"different filesystem", which is derived and true. Whether the two filesystems
sit on different *hardware* has never been checked, and the whole value of the
`D:` tarballs as protection against disk failure depends on it.

**If `D:` is a partition of the same drive that backs the VHDX, the two tarballs
protect against nothing that a single disk failure would not take with it**, and
the archive's status drops from "second-filesystem copy" to "second directory".

**Not resolved here**, because resolving it needs a hardware query
(`Get-PhysicalDisk` / `Get-Partition`) that is outside this task's scope, and
because it changes no action: **no same-machine arrangement protects against
machine loss regardless of the answer.** It changes only how much the existing
tarballs are worth.

---

## 5f. Credential exposure — clearing the history was the wrong remedy

I flagged the `sudo` password as possibly landing in Git Bash history and
recommended clearing it. **The clearing premise was wrong, the exposure is real,
and it is older and wider than shell history.**

### There is nothing to clear

| location | result |
|---|---|
| `C:\Users\HamzaKhan\.bash_history` | **41 lines, `mtime` 9 July 2026, `sudo` occurrences: 0** |
| `/home/hamzakhan/.bash_history` | **ABSENT** (verified — parent readable) |
| `/root/.bash_history` | **UNREADABLE** — not established |

**Bash appends to `HISTFILE` only when the shell is interactive.** Every shell in
the pipeline was non-interactive, so nothing was ever written. The Git Bash file
has not been touched since 9 July, which is evidence rather than assumption.

The password also never appeared on a command line that `sudo` logs: it went to
**stdin** via `-S`, and what `sudo` records is `bash <script>`.

**So "clear the history" would have been a remedy that changed nothing while
creating the impression the exposure was handled.** That is the same shape as a
check that passes by doing nothing.

### Where it actually is, and this is the finding

**Plaintext, at rest, in Claude Code session transcripts** under
`C:\Users\HamzaKhan\.claude\projects\D--personal-AEP\`:

| transcript | occurrences |
|---|---|
| the current session | 74 |
| **`bf5a247a-…`, mtime 24 August 2026** | **54** |

> **The exposure is not from today. The same password was used in a session on
> 24 August and has been sitting in plaintext on disk for eight days.** Today's
> use added to an existing exposure rather than creating one.

**Therefore: rotate, do not clear.** Clearing shell history removes nothing that
is there; the credential is in files that are the durable record of this work and
that I am not going to rewrite unasked — redacting them destroys the audit trail
that this whole phase depends on. **Rotation makes the stored copies inert
without touching the record.**

### A methodological note, because the first count was wrong

My first search matched `hamza[0-9]{3}` and reported hits in **sixteen**
transcripts. **Fourteen were false positives**: the git remote is
`hafizmirhamza276-lab`, so every transcript containing the repository URL
matched. The narrowed pattern finds the credential in **two** files.

**A credential search that over-reports is not the safe direction it looks
like.** It would have justified rewriting fourteen files of project record to
remove a string that was never in them.

### `/root/.bash_history` is not established

Reading it needs `sudo`, and re-running `sudo` would mean embedding the password
in another tool call — adding to the exposure in the course of measuring it.
**Not done.** The residual is small (non-interactive shells; no interactive root
shell was ever opened) but it is **unverified, and is recorded as unverified**:

```
! wsl -- sudo bash /mnt/d/personal/AEP/Research-paper-AEP/phase8-driver/history_check.sh
```

`phase8-driver/history_check.sh` reports `UNREADABLE` rather than `ABSENT` for
denied paths and exits 2 — **after its first version did the opposite.** It
printed `ABSENT: /root/.bash_history` from an unprivileged shell, because
`[ ! -e ]` is true for a path whose parent is `0700`. That version was written
**directly beneath a header comment stating that the survey must not assert an
absence it has not checked**, one function below the sentence forbidding it.

**Same defect, same session, same author, same file as the prohibition.** It is
F.0d's fail-open class and F.0c's "correct only for a reason nothing enforces",
and it is the strongest available evidence for the standing rule that the author
of a rule is its weakest enforcer.

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

### Amendment, 1 Sep, after the privileged survey

The verdict above survives derivation, with two corrections and one addition.

- **"Integrity of what exists: good" is now measured, not inferred.** 1159 run
  directories across eleven collections, **1159 present**, every ledger triple
  intact in every tree. **Nothing the manuscript quotes is missing.** §5a could
  not say this and
  reasonably feared the opposite about `fsync-always`.
- **"Durability: bad" is unchanged and now exact.** Nine of eleven quoted
  collections exist in exactly one place; the two that do not have their second
  copy **on this machine**; the evidence is split across three trees, **each the
  sole holder of part of it.**
- **Addition — the worst-placed copy is not in WSL.** The 240 runs behind the
  paper's only session-clustered interval that excludes zero live **only** in a
  git working tree, **gitignored**, invisible to `git status`, one `git clean
  -xdf` from gone (§5e). The `/root` trees are at least not sitting inside a tool
  whose routine housekeeping command deletes ignored files.

**This still is not an argument against minting the DOI.** It is a sharper
version of the same argument for doing something first, and the something is now
priced: **≈ 20 MB compressed.**
