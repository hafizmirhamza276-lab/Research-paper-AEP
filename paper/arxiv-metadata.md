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
Declared Ambiguity: The Agent Execution Protocol (AEP) for Autonomous Agents Calling Non-Idempotent Legacy APIs
```

## Categories

| Field | Value |
|---|---|
| **Primary** | `cs.SE` — Software Engineering |
| **Secondary** | `cs.DC` — Distributed, Parallel, and Cluster Computing |

## Comments field

```
18 pages, 3 figures, 12 tables. Artifact, frozen results and manuscript source:
https://github.com/hafizmirhamza276-lab/Research-paper-AEP (tag v1.0.0-rc1)
```

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
faults, hard Redis kills and block-level write loss, across three endpoint
reconciliation capabilities.

Our central result separates two claims that the write-ahead pattern is usually
sold as one. Detection -- no undetected duplicate and no lost effect, with a
residual of declared ambiguity whose rate is set by what the endpoint can be
asked -- is produced by the durable pre-dispatch record alone. We show this by
ablation rather than by argument: removing the durability barrier and changing
nothing else leaves every detection metric unchanged over 600 executions per arm
-- undetected duplicates and lost effects are 0 and 0 in both systems, bounding
each rate and the difference between them below 0.64%, against baselines that
differ from both by 0.77--0.83; declared ambiguity differs by 2 executions in
600 (p = 0.95). Prevention is what the barrier contributes, and it is a
different quantity against a different fault: under a hard Redis kill placed
between the intent write and its acknowledgement, the barrier withholds an
effect the ablation puts on the wire, an unwanted-applied-effect rate of 0.3333
versus 0.9333 over 30 runs per system (10/30 versus 28/30, Fisher p =
1.9x10^-6) -- 18 real non-idempotent effects not committed.

The barrier's durability claim, which a process kill cannot exercise at all
because appendfsync everysec defers the fsync(2) and not the write(2), we test
directly by making the block device stop accepting writes: acknowledged records
survive 90/90 and unacknowledged ones are destroyed 90/90 (p = 2.2x10^-53),
against 0/10 lost under a process kill on the same probe. Because detection does
not depend on the barrier, its cost is a deployment choice rather than the
protocol's price, and we give three measured points on that curve.
```

**Character count of the abstract block above: 3 105** (measured, not estimated).
arXiv's abstract field is limited to 1 920 characters, so **this full form
cannot be pasted** — it is kept here only as the faithful rendering of the
manuscript's abstract. Use the short form below.

---

## Abstract — short form, within arXiv's 1 920-character limit

```
Autonomous agents increasingly invoke legacy enterprise APIs that are
non-idempotent, accept no idempotency key, and cannot be asked afterwards
whether a mutation was applied. When an agent crashes around such a call,
retrying risks a second real-world effect nobody observes and not retrying
risks an effect that exists while the records deny it. We argue this is a
three-way trade rather than a question of engineering quality, and that a
system should make the third corner reachable: converting silent failure into
declared, durable, bounded ambiguity an operator can act on.

We present the Agent Execution Protocol (AEP), a fail-closed protocol in which
every external side effect is preceded by a durably acknowledged write-ahead
intent, every state write is fenced by lock ownership and an exact
expected-version compare-and-swap in one atomic script, and every unresolvable
outcome halts and escalates rather than guessing. We evaluate AEP against five
baselines under real SIGKILL faults, hard Redis kills and block-level write
loss, across three endpoint reconciliation capabilities.

Our central result separates two claims the write-ahead pattern is usually sold
as one. Detection -- no undetected duplicate and no lost effect, with a residual
of declared ambiguity set by what the endpoint can be asked -- comes from the
durable pre-dispatch record alone, without the durability barrier: ablating the
barrier changes no detection metric over 600 executions per arm, against
baselines that duplicate in 0.77--0.83 of crashed executions. Prevention is what
the barrier buys, against a different fault: under a hard Redis kill between the
intent write and its acknowledgement it withholds effects the ablation puts on
the wire (10/30 versus 28/30, Fisher p = 1.9e-6). Detection is therefore nearly
free, and the barrier's cost is a deployment choice.
```

**Character count: 1 862** (measured, against arXiv's 1 920-character limit —
58 characters of headroom). arXiv counts characters, not words; re-measure with
`wc -m` if this text is edited at all.

---

## Pre-submission checklist for the human

- [ ] The independent audit has returned a SUBMIT verdict.
- [ ] Decide the anonymity question first — see `reports/phase-report-5c-2026-08-10.md`
      §G.2. The manuscript's author block currently reads *Anonymous Author(s)*
      while `main.tex` and §9 carry a GitHub URL naming a personal account.
      A public arXiv preprint and an anonymised TSE submission cannot both be
      served by the same PDF; **choose the author block before either
      submission**, and note that posting the preprint first is what makes the
      anonymised submission moot.
- [ ] Re-render the abstract from `paper/main.tex` if any number has been
      regenerated since 2026-08-10.
- [ ] `wc -m` the short abstract against arXiv's 1 920-character limit.
- [ ] Confirm the tag referenced in the comments field is the one intended to be
      public (`v1.0.0-rc1` is a release *candidate*).
- [ ] Upload the PDF built by `scripts/build_paper.sh`, or the source tree —
      arXiv prefers LaTeX source; if source is used, confirm `IEEEtran.cls`
      resolves on arXiv's TeX Live and that `paper/generated/*.tex` and
      `paper/figures/*` are included.
