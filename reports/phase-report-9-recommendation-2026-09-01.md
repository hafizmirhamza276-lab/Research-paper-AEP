# Recommendation on Phase 10 — per claim, and two separate verdicts

**Unit 4.** Written after units 0–3 were committed, and referring only to them:
`80c5baf` + `aa5bf87` (custody), `1332519` (claims, sealed), `b352d60`
(argument, sealed), `d9d3423` (adversarial amendments), `15ae585` (B26–B29).
**No new analysis was done for this unit.** That ordering exists so the
recommendation cannot shape the findings it rests on.

**Custody and claims are separate verdicts and neither absorbs the other.**

---

## Verdict 1 — the claims: SOUND, with five wording changes

**The central result stands and is mintable as it is.** Detection is produced by
the pre-dispatch record and the missing re-entry edge and not by the barrier;
that claim, the 4.77% bound over 54 run clusters, the 77–83% baseline contrast
and the B4 decomposition were untouched by every correction this phase made.
**Seven of the twelve load-bearing claims hold at their stated strength.**
The corrections landed on the *prevention* half and on the *explanation* of the
prevention result — the newest material, which the paper's own threats section
already identified as its narrowest.

**Four of five explanatory chains are intact, and the broken one does not
propagate.** It explains why the prevention magnitude varies, not whether the
barrier prevents; the deployment recommendation rests on the prevention effect
itself, whose session-clustered interval excludes zero.

**This is a good outcome and it is not being dressed as a crisis.** Nothing
below requires new evidence. Every item is one clause.

### Blocking items — five, each a wording change

| # | site | asserts | evidence supports | smallest change that closes it |
|---|---|---|---|---|
| 1 | `08-threats.tex:385` | *"its effect size **is a function of** that host's `docker kill` latency. It is the whole of the barrier's measured case."* | one unreplicated session at p = 0.03; a four-session interval containing zero | **"may be a function of"**, and add *"which our measurement does not establish"*. Contradicts `:96` in the same file until it changes |
| 2 | `08-threats.tex:85` | *"an effect size we **can now show** is host-dependent rather than merely suspect it is"* | the same | revert the contrast: **"we suspect is host-dependent and have not established"** |
| 3 | `06-evaluation.tex:463` | *"…**therefore** not a constant of the protocol…: it is where one host's kill-latency distribution **happened to place a race**"* | the same | **delete the clause after the colon.** The disclaimer is the sentence's job and survives intact without it. The sentence that follows it is a design claim and stays |
| 4 | `main.tex` abstract, and `08-threats.tex:73` | prevention carried by one session's `p = 1.9 × 10⁻⁶`, with the four-session replication adjacent in neither | 5 measurements, 4–20, interval [6.1, 28.4] | add the range at both sites. `\ReplicationAepMin`/`\ReplicationAepMax` **already exist and are already used**, so this is an insertion, not a new number |
| 5 | `08-threats.tex:83-88` | the prevention claim's evidence is *"the weakest"* | on **scope** this is right and must not be softened; on **strength within scope** it is the only one of three session-clustered quantities whose interval excludes zero | add the interval. **Do not touch the scope criticism** |

**Items 1–3 are the same defect in three places** (B26). Item 4 is B27, item 5 is
B28. `06-evaluation.tex:393` is **not** on this list: it offers the mechanism as
a reason to distrust the number, and asserting a limitation on thin evidence is
conservative.

### Non-blocking

**B29** — `claim_sweep.py` is unwired. It is tooling and does not affect what the
paper claims. It does need a decision, because a tool in the tree that runs
nowhere reads as coverage.

---

## Verdict 2 — custody: the deposit does not exist and must be assembled first

**This is a separate problem with a separate remedy and it does not change
verdict 1.**

`09-artifact.tex` is honest: it states plainly that the repository does not
contain the 432 raw run directories, the voided run, or a complete raw-evidence
manifest, and that those must be deposited before an availability claim is made.
**Minting the DOI is the remedy for that obligation, not something blocked by
it.**

**What blocks it is that the thing to be deposited does not currently exist in
one place.**

| evidence | archived |
|---|---|
| `matrix`, 432 runs — *the only quotable source for every rate in the paper* | **no** |
| 21 August `b2` roots, 240 runs | **no** |
| Phase 8.4 s1, s2 | **no** |
| Phase 8.4 s3, s4 | yes — two tarballs, 31 Aug |

No single tree holds all of it, and **no raw run of any phase exists off this
machine.** The `D:` tarballs are a second filesystem on the same physical
host — they remove the one-filesystem risk and not the one-machine risk.

**Recommendation:** assemble and verify the complete deposit before minting,
using the s3/s4 archives as the template — they already carry full SHA-256
manifests and before/after ledger mtimes, and that part was done properly.
**Assembling the deposit discharges the durability exposure as a side effect**,
which is the argument for doing it now rather than treating it as a separate
project.

**The custody position does not weaken any claim in verdict 1.** Every number in
the manuscript is derived from tracked CSVs that are already off-host via
`origin`. What is at risk is the ability to *re-derive* them from raw evidence,
not the numbers themselves.

---

## The two verdicts together

**Mint it — after five one-clause wording changes and after the deposit is
assembled.** Neither condition needs new experiments, new analysis, or a
re-collection, and neither touches the central result.

**If the deposit cannot be assembled soon**, the honest alternative is to mint
the artefact **as scoped by `09-artifact.tex` as it already reads** — which
claims only what the repository contains — and defer the raw-evidence DOI. That
is a real option and `09-artifact.tex` already supports it without a word
changing.
