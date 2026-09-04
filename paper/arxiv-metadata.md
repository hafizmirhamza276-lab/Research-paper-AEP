# arXiv submission metadata — paste-ready

> **Status: PREPARED, NOT SUBMITTED.** Nothing in this file has been uploaded
> anywhere. No arXiv account, draft or submission exists. This is copy for a
> human to paste after the independent audit returns a SUBMIT verdict.
>
> Every number in the abstract below is the resolved value of a generated macro
> in `paper/generated/numbers.tex`. If the frozen results are ever recollected,
> regenerate rather than hand-edit: `python scripts/paper_tables.py`, then
> re-render this abstract from `paper/main.tex`.

---

## Title

```
Declared Ambiguity: Fail-Closed Execution for Non-Idempotent Legacy APIs Without Idempotency Keys
```

## Categories

| Field | Value |
|---|---|
| **Primary** | `cs.SE` — Software Engineering |
| **Secondary** | `cs.DC` — Distributed, Parallel, and Cluster Computing |

## Comments field

```
3 figures, 12 tables. Code, manuscript source, and tracked derived analysis:
https://github.com/hafizmirhamza276-lab/Research-paper-AEP
Raw evidence archive is assembled and verified (26,300 files, manifest sha256
87fa2d53...) but not yet deposited; insert its DOI here and do not submit this
metadata until the DOI resolves.
```

> **Where the DOI comes from.** It is defined once, in `paper/main.tex` at the
> `\newcommand{\archivedoi}` line, and currently reads `PENDING`. Take the value
> from there rather than re-typing it, so this file and the manuscript cannot
> disagree. `docs/29-archive-deposit.md` §5 is the checklist.
>
> **In the anonymous build the DOI is withheld**, exactly as the GitHub URL is:
> a Zenodo record names its depositor, so citing it under double-anonymous
> review defeats the anonymisation. The anonymous branch of the toggle never
> reads `\archivedoi`, so it cannot leak even if one is inserted. If this
> metadata accompanies an anonymous submission, the archive line must read
> "available via the submission system" and carry no DOI.

> Counted from the source, not estimated: 3 `figure` and 12 `table`
> environments across `main.tex`, `sections/*.tex` and `generated/*.tex`
> (5 of the 12 tables are generator-produced). Page count is from the build in
> §C.8 of the 5C report. Re-count if the manuscript changes.

## ACM classification (optional field)

```
D.2.4 Software/Program Verification; D.4.5 Reliability; C.2.4 Distributed Systems
```

## Licence

```
arXiv.org perpetual, non-exclusive license to distribute this article
```

---

## Abstract — plain text, paste-ready

> LaTeX macros resolved to their generated values; em-dashes rendered as
> `--`; `x` for the multiplication sign; `^` for exponents. arXiv's abstract
> field is plain text and does not render LaTeX markup.

```
Autonomous software agents increasingly invoke legacy enterprise APIs that are
non-idempotent, accept no idempotency key, and cannot be asked, after the fact,
whether a mutation was applied. When an agent crashes around such a call, every
available strategy loses something. Retrying risks a second real-world effect
that nobody observes. Not retrying risks an effect that exists and that no
record accounts for. We argue that the choice between these is not a question of
engineering quality but a three-way trade, and that a system's obligation is to
make the third corner reachable: to convert silent failure into declared,
durable, bounded ambiguity that an operator can act on. We present the Agent
Execution Protocol (AEP), a fail-closed execution protocol in which every
external side effect is preceded by a durably acknowledged write-ahead intent,
every state write is fenced by lock ownership and an exact expected-version
compare-and-swap in one atomic script, and every unresolvable outcome halts and
escalates rather than guessing. We evaluate AEP against five baseline designs,
one of them in two configurations -- naive retry, lease-only, CAS-only, an
ablation without the durability barrier, and a durable-execution engine in both
its vendor-default and at-most-once settings -- under real SIGKILL process
faults, across three endpoint reconciliation capabilities. Two narrower faults
target the barrier and its premise: a hard Redis kill, which we use as an
AEP-versus-ablation comparison on one capability class, and block-level write
loss, which we use to test that premise on durable records rather than on the
protocol's outcomes.

Our central result separates two claims that the write-ahead pattern is usually
sold as one. Detection -- no undetected duplicate and no lost effect, with a
residual of declared ambiguity whose rate is set by what the endpoint can be
asked -- is produced by the pre-dispatch record and a transition table that
prohibits re-entry into dispatch. In the crashed regime, B3 and AEP-full each
have 540 executions: both record zero undetected duplicates and zero lost
effects. The individual one-sided 95% Wilson upper bound for either zero-event
rate is 0.50%. Declared ambiguity is 195/540 versus 193/540 (B3 minus AEP-full,
0.37 percentage points; stratified run-cluster 90% interval [-1.11, 2.04]
percentage points). Prevention is what the barrier contributes, and the current
evidence is narrower: in one no-readback capability class, at one
pre-acknowledgement Redis-kill point, on one host, its unwanted-applied-effect
rate is 0.3333 versus 0.9333 over 30 runs per system (10/30 versus 28/30,
Fisher p = 1.9x10^-6) -- 18 real non-idempotent effects not committed.

The barrier's durability claim, which a process kill cannot exercise at all
because appendfsync everysec defers the fsync(2) and not the write(2), we test
directly by making the block device stop accepting writes: acknowledged records
survive 90/90 and unacknowledged ones are destroyed 90/90 (p = 2.2x10^-53),
against 0/10 lost under a process kill on the same probe. Because detection does
not depend on the barrier, its cost is a deployment choice rather than the
protocol's price, and we give three measured points on that curve.
```

**Character count of the abstract block above: 3 252**, measured 2026-08-21 as
the block's length between the fences, newlines included. arXiv's abstract field
is limited to 1 920 characters — *"abstracts longer than 1920 characters will not
be accepted"*, [info.arxiv.org/help/prep.html](https://info.arxiv.org/help/prep.html),
read 2026-08-21 — so **this full form cannot be pasted**. It is kept here only as
the faithful rendering of the manuscript's abstract. Use the short form below.

> **arXiv does not state how it counts.** The help page gives the number and not
> the rule, so it is unspecified whether hard newlines, leading whitespace and
> line wrapping are included. Both counts in this file are therefore given under
> the strictest reading (every byte between the fences, newlines counted). Under
> a flowed-text reading the short form is 2 characters shorter. Any headroom
> below ~20 characters should be treated as unconfirmed.

---

## Abstract — short form, within arXiv's 1 920-character limit

```
Autonomous agents invoke legacy APIs that are non-idempotent, accept no
idempotency key, and cannot be asked afterwards whether a mutation was
applied. When an agent crashes around such a call, retrying risks a second
real-world effect nobody observes and not retrying risks an effect that exists
while the records deny it. We argue this is a three-way trade rather than a
question of engineering quality, and that a system should make the third
corner reachable: converting silent failure into declared, durable, bounded
ambiguity an operator can act on.

We present AEP, a fail-closed protocol in which every external side effect is
preceded by a durably acknowledged write-ahead intent, every state write is
fenced by lock ownership and an exact-version CAS in one atomic script, and
every unresolvable outcome halts and escalates rather than guessing. We
evaluate AEP against five baselines under real SIGKILL faults, across three
endpoint reconciliation capabilities. Two narrower faults target the barrier
and its premise: a hard Redis kill, and block-level write loss tested on
durable records, not protocol outcomes.

Our central result separates two claims the write-ahead pattern is usually
sold as one. Detection -- no undetected duplicate and no lost effect, with
residual declared ambiguity set by endpoint capability -- comes from a
pre-dispatch record plus no re-entry into dispatch. In the crashed regime, B3
and AEP-full each record zero such silent failures over 540 executions; their
ambiguity difference is 0.37 percentage points with a stratified run-cluster
90% interval of [-1.11, 2.04]. Prevention is what the barrier buys against a
different fault. In one no-readback capability class at one
pre-acknowledgement Redis-kill point on one host, it withholds effects the
ablation puts on the wire (10/30 versus 28/30, Fisher p = 1.9e-6). The
barrier's cost remains a deployment choice.
```

**Character count: 1 906**, measured 2026-08-21 under the strictest reading
above (every byte between the fences, newlines counted); 1 904 flowed. Against
the verified 1 920 limit that is **14 characters of headroom, worst case**.
arXiv counts characters, not words; re-measure if this text is edited at all,
and record the method alongside the number — the two counts previously recorded
in this file were both stale, by 29 and 17 characters respectively.

---

## Pre-submission checklist for the human

- [ ] The independent audit has returned a SUBMIT verdict.
- [ ] Decide which build to submit. The contradiction 5C §G.2 warned about —
      an *Anonymous Author(s)* block shipping alongside a GitHub URL naming a
      personal account — **was closed by `bf68440`**, which put the author block
      behind a switch. There are now two consistent builds: `main.pdf` names the
      author and carries the artifact URL and a correspondence footnote;
      `main-anon.pdf` carries neither, and is verified to contain no author
      name, account, repository name, email or identifying link annotation.
      Nothing here needs fixing. What remains is a *choice*: a public arXiv
      preprint and an anonymised TSE submission cannot both be served by the
      same PDF, and posting the preprint first is what makes the anonymised
      submission moot. **Decide the ordering, then pick the build.**
- [ ] Re-render the abstract from `paper/main.tex` if any number has been
      regenerated since 2026-08-10.
- [ ] `wc -m` the short abstract against arXiv's 1 920-character limit.
- [ ] Create and verify the new immutable release/tag, upload the complete raw
      archive (including `results/voided/` and its SHA-256 manifest), mint a
      DOI, and update the comments field only after the DOI resolves.
- [ ] Upload the PDF built by `scripts/build_paper.sh`, or the source tree —
      arXiv prefers LaTeX source; if source is used, confirm `IEEEtran.cls`
      resolves on arXiv's TeX Live and that `paper/generated/*.tex` and
      `paper/figures/*` are included.
