# Getting the raw evidence off this machine — options, not a decision

**Unit 2. This is a report. Nothing here is acted on and nothing here is
recommended as decided.** Sizes come from
`reports/phase-report-9-custody-inventory-2026-09-01.md` §5a, where the
extrapolated ones are labelled.

---

## 0. Two of your four constraints need amending, and one is understated

**Constraint 1 — the sqlite triple must travel together, no checkpointing.**
**Correct, and stronger than stated.** Every triple in every readable root is
complete (`db = wal = shm`). The failure mode is not just splitting them: **1093
of 1093 ledgers are bare 4096-byte pages with the ground truth in uncheckpointed
WALs**, so a copy that takes only `*.sqlite3` produces files that open cleanly
and contain nothing. No option below checkpoints anything.

**Constraint 2 — any copy needs a manifest covering every file.** **Correct.**
`SHA256SUMS` names zero run directories, so a partial copy verifies exactly as
well as a complete one. The `s3`/`s4` archives already do this properly — a full
manifest plus before/after ledger mtimes — and are the template.

**Constraint 3 — git is not the vehicle.** **Correct on policy, and your size
figure is low.** It is not 50 MB of run directories: the working clone alone
holds **114 M**, and the manuscript-quoted evidence is **≈ 420 M uncompressed**.
Git is more wrong than you thought, not less.

**Constraint 4 — no upload authorised, and say plainly if an upload is the only
real answer.**

> **An upload, or physical media, is the only real answer. There is no
> same-machine arrangement that protects against machine loss, and I am not
> going to present one as though there were.**

Everything in §2 that stays on this host protects against *some* failures. None
of them protects against the one that ends the project.

**And the size finding changes the shape of this decision.** At the `s3`
tarball's ≈ 20:1 ratio, **the entire manuscript-quoted raw evidence is ≈ 21 MB
compressed.** That is an email attachment. **Cost is not the obstacle; authorisation
is.**

---

## 1. What each option protects against — the axis that matters

| failure | same-machine copy | off-host copy |
|---|---|---|
| accidental `rm` of one root | **yes** | yes |
| WSL VHDX corruption | **yes** | yes |
| a tool that opens and checkpoints ledgers | **yes** (if the copy is not the target) | yes |
| **disk failure** | **no** — `D:` and the VHDX share one device unless `D:` is a separate physical disk, **which the survey has not established** | yes |
| **machine loss, theft, fire** | **no** | **yes** |
| ransomware reaching mounted volumes | **no** | only if the target is offline or immutable |

**The `D:` tarballs protect against VHDX corruption and against a mistake made
inside WSL. They do not protect against disk failure — and whether `D:` is even a
separate spindle from the VHDX is not established by any survey run so far.**
That is a weaker guarantee than "different filesystem" implies.

---

## 2. The options

### A — Complete the same-machine archive set (finish what 31 Aug started)

Extend the `s3`/`s4` pattern to the other eight manuscript-quoted roots: one
`tar.gz` per root, full SHA-256 manifest of every file, before/after ledger
mtimes, triples intact, nothing opened.

- **Size:** ≈ 21 MB total.
- **Effort:** the two existing archives prove the procedure works. **There is no
  archive script** — `Makefile:38`'s `ARCHIVE ?=` is an input path — so this is
  writing one, and B5 (freeze portability) is separately open.
- **Protects against:** accidental deletion, VHDX corruption, a checkpointing
  tool.
- **Does NOT protect against:** disk failure, machine loss, theft, fire.
- **Risk:** the archiving step is the dangerous one. A naive `find -name
  '*.sqlite3'` publishes empty pages; a "verify before archiving" step can
  checkpoint and destroy originals. **The risk is to the evidence itself, not to
  the copy.**
- **Verdict:** necessary groundwork for every other option and **not a solution
  to the problem you asked about.**

### B — Off-host to a second machine you control

A → `scp`/`rsync` of the tarballs to another machine.

- **Size:** 21 MB. Minutes.
- **Protects against:** everything in the table, including machine loss.
- **Does NOT protect against:** both machines lost together (same building,
  fire, theft); nothing an outside reader can cite.
- **Risk:** low. The copy is of tarballs, not of live roots, so the ledgers are
  never touched again after A.
- **Requires:** a second machine, and your authorisation to move data off this
  one.

### C — Removable media, offline

A → an external disk or two USB drives, verified by manifest, then disconnected.

- **Size:** 21 MB.
- **Protects against:** everything B does, plus ransomware and anything that
  requires the volume to be mounted.
- **Does NOT protect against:** loss of the media; silent bit-rot on flash left
  unpowered for years; nothing citable.
- **Risk:** the verification must be done **from** the media after writing, or it
  attests a write that may not have landed.
- **Note:** the only option that needs no network and no external party.

### D — Deposit with an archive that issues a DOI (Zenodo, figshare, institutional)

A → upload → permanent identifier.

- **Size:** 21 MB, far inside every free tier.
- **Protects against:** everything, plus it is the **only** option that makes the
  evidence citable and discharges the §IX deposit obligation.
- **Does NOT protect against:** nothing relevant. It does mean **publishing**,
  which is irreversible in a way the others are not.
- **Risk:** publishing raw runs before they have been reviewed for anything that
  should not be public. **The ledgers are synthetic and the provider is a mock,
  so this risk is probably low — but "probably" is doing work I have not
  verified, and one pass over what a run directory actually contains should
  precede any upload.**
- **Requires:** your authorisation. **This is the option that actually solves the
  problem, and it is the one you have not authorised.**

### E — Do nothing yet, and record the exposure

- **Cost:** zero.
- **Protects against:** nothing.
- **Honest case for it:** the derived analysis products are already off-host via
  `origin`, and **every number in the manuscript comes from those.** Losing the
  raw runs costs the ability to *re-derive*, not the results.
- **Honest case against:** the ability to re-derive is what an artefact paper
  sells, and §IX commits to depositing exactly this material.
- **Verdict:** defensible for days, not for the interval since 11 August.

---

## 3. Which collections go first, derived

**Ranked by (cited by the manuscript) × (number of independent copies) ×
(irreplaceability).** Every root is irreplaceable — the collection host's timing
behaviour is not reproducible, which is the phase's own finding — so the ranking
turns on citation weight and copy count.

| rank | collection | why |
|---|---|---|
| **1** | **`matrix`, 432 runs** | `main.tex`'s header names `matrix/analysis/per-cell-metrics.csv` as **"the ONLY quotable source for rates"**. Every rate in the paper, the whole detection result, and the 4.77% bound come from it. **The clone holds 19.4% and there is no archive.** Largest single point of failure by a wide margin |
| **2** | **`fsync-always`** | Quoted — the entire `always` column of the deployment table — and **its runs are in no readable tree**. It may already be the answer to "missing from every tree", and it is the only root where that is even possible. **Rank 2 despite being small, because it may already be lost** |
| **3** | **`b2-paired-v2-s1`, `s2`** | Carry `\ClassPp*`, the registered primary estimand. **s3 and s4 are archived; s1 and s2 are not**, so this is the half of a pre-registered k = 4 set that has no second copy |
| **4** | **`b2-*-2026-08-21` ×4, 240 runs** | Carry `\ReplicationPrevented*` — **the only session-clustered interval in the paper that excludes zero**. Exist as run directories in the working clone only |
| 5 | `b2-paired-v2-s3`, `s4` | Already archived. Upgrading them from same-machine to off-host is cheap and comes last because they are the only two that already have a second copy |
| — | `throughput`, `smoke`, `selfcheck*`, `b2-paired-s1` | Not quoted by the manuscript. Not custody priorities |

**Your expectation that `matrix` comes first is correct and the derivation
supports it.** The derivation also produces something you did not predict:
**`fsync-always` is second, because it is the one manuscript-quoted collection
that may already have no raw evidence anywhere.** That is a finding about the
inventory, not about backup priority, and it resolves the moment the privileged
survey runs.

---

## 4. What I am not saying

- **Not recommending an option.** You asked for options with costs and risks.
- **Not proposing a same-machine copy as a solution.** Option A is groundwork.
  **Only B, C and D protect against machine loss, and all three need your
  authorisation.**
- **Not claiming the ranking is complete.** It ranks the ten manuscript-quoted
  roots. If the privileged survey finds a root under `/root` that no tree here
  knows about, the ranking changes.
