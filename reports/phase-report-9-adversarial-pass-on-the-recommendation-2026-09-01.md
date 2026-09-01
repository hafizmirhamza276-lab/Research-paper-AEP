# Adversarial pass on the recommendation — unit 5

**Read as someone who wants to mint the DOI today and is hunting the weakest
link in the argument against.** Four concessions, one of them structural enough
to change verdict 1's conditions.

---

## C1 — The recommendation conflated two deliverables, and the opponent is right

**Attack:** *"Phase 10's DOI is over the raw evidence archive. The manuscript
goes to TSE separately and is revised in review. Manuscript wording cannot gate
an artefact DOI."*

**Conceded, and this is a real defect in unit 4.**

`09-artifact.tex:7-10` and the handover's §6d agree on what the DOI covers: the
**432 raw run directories, the voided run, and a complete raw-evidence checksum
manifest** — with the ledger triples intact. That deposit does not contain the
manuscript.

**So the five wording changes gate manuscript submission, not the DOI.** Unit 4
listed them under "blocking items" for Phase 10 and attached them to the wrong
artefact.

### Verdict 1, restated correctly

| deliverable | verdict | conditions |
|---|---|---|
| **the manuscript** | **sound** | five one-clause changes before submission |
| **the raw-evidence DOI** | **blocked** | for custody and engineering reasons, none of them about what the paper claims |

The claims assessment itself is unaffected — units 1, 1b and 2 say what they
say. What changes is which gate the findings sit in front of.

## C2 — Items 1–3 are low severity, and the case for fixing them is cost, not gravity

**Attack:** *"These are hedging clauses inside a limitations section. Nobody's
headline moves."*

**Largely conceded.** Sharpened against my own filing: `08-threats.tex:385`'s
second sentence — *"It is the whole of the barrier's measured case"* — **is
true**, and unit 4 quoted it as though it were part of the defect. Only the
preceding clause is exposed.

**What survives is unchanged in substance and weaker in urgency.** The argument
for making these three changes is that each is one clause, that they are three
rather than one, and that one of them contradicts a corrected sibling 289 lines
away in the same file. **It is not that any of them misleads a reader about the
paper's result.** Unit 4 implied more weight than the items carry.

## C3 — "Sound" rests on a selection, and unit 2 already said so

**Attack:** *"Seven of twelve, out of 137 swept sentences. Your own unit 2 says
that is not a coverage statistic."*

**Conceded as a bound on confidence, not as a defect.** Verdict 1 means: the
twelve load-bearing claims were adjudicated and seven hold at stated strength;
the remaining 125 swept sentences were read and produced no further finding.
**That is weaker than an exhaustive audit and verdict 1 should not be quoted as
one.**

## C4 — "Assemble the deposit first" was a durability argument dressed as a minting argument

**Attack:** *"§IX already scopes the artefact to what the repository contains.
So mint that today and defer the raw-evidence DOI. Why is 'assemble first' the
primary recommendation?"*

**Conceded.** The reason to assemble the deposit now is that it discharges the
one-machine exposure — a durability argument. It is a good argument. It is not
an argument about what may be minted.

**And unit 4 understated how large that work is**, which cuts against my own
recommendation's feasibility rather than for it. From the record: **1093 of 1093
ledgers are bare 4096-byte pages with the ground truth in uncheckpointed WALs**;
the obvious `cp **/*.sqlite3` publishes 432 empty pages under a permanent DOI
while appearing complete; a tool that opens each ledger to verify it can
checkpoint and destroy the originals; **there is no archive script**; and **B5**
(freeze portability) is separately recorded as blocking. Unit 4 said "use the
s3/s4 archives as the template" and left all of that out.

---

## The weakest link in the argument against minting today

**It is that a repo-scoped artefact DOI is honestly available right now.**
`09-artifact.tex` already states that the repository does not contain the raw
runs and that no external archive DOI exists. **Someone who wants to mint today
can mint the repository as §IX already describes it, without changing a word and
without overclaiming anything.**

What they would not be minting is the raw evidence. **The argument against is
therefore not "you may not mint" but "what you would mint is not what 'the raw
evidence DOI' means"** — and if that distinction is stated in the deposit record,
minting today is defensible.

**I could not find a stronger objection than that, and I looked for one.**

---

## What survives the pass

- **The claims verdict.** Unattacked and unamended: the central result stands,
  seven of twelve load-bearing claims hold at stated strength, four of five
  explanatory chains are intact, and the broken chain explains the variance of
  the prevention result rather than the result.
- **The five wording changes**, now correctly attached to manuscript submission
  and correctly described as cheap rather than grave.
- **The custody position**, strengthened: the deposit is a design task with a
  silent catastrophic failure mode, not an upload.

## Corrected bottom line

**The manuscript is sound and needs five one-clause changes before submission.**

**The raw-evidence DOI is not ready**, for custody and engineering reasons that
have nothing to do with what the paper claims: no complete tree in one place, no
archive script, ledger triples that a naive copy silently empties, and B5 open.

**A repository-scoped DOI is available today** on `09-artifact.tex`'s existing
wording, if the deposit record says plainly that it is not the raw evidence.

**These are three decisions, not one, and unit 4 presented them as one.**
