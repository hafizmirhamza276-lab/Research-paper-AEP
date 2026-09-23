# arXiv submission metadata — paste-ready

> **Status: PREPARED, NOT SUBMITTED.** Nothing in this file has been uploaded
> anywhere. No arXiv account, draft or submission exists. This is copy for a
> human to paste after the independent audit returns a SUBMIT verdict.

> **The abstract below is generated, not transcribed.** It is rendered from
> `paper/main.tex` by `scripts/render_arxiv_abstract.py`, with any generated
> macros resolved from `paper/generated/numbers.tex`. **Do not hand-edit it.**
> Edit the manuscript, then run `python scripts/render_arxiv_abstract.py
> --write`. `--check` runs in the test suite and turns red when this file and
> the manuscript disagree — which is how the previous transcription was allowed
> to fall an entire generation behind the paper it claimed to quote.

---

## Title

Checked against `main.tex`'s `\title{}` by `render_arxiv_abstract.py --check`.

```
AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys
```

## Keywords

From `main.tex`'s `IEEEkeywords` block; each is checked to be present here.

```
Fault tolerance, non-idempotent APIs, idempotence, distributed coordination, write-ahead logging, fault injection, reliability engineering, autonomous agents
```

> **"autonomous agents" is a keyword about the motivating setting, not about
> the evaluation.** §I states the position in as many words: *"Autonomous
> agents are the setting in which this is now most visible, and we use them
> throughout as the motivating example; the problem belongs to the endpoint,
> and any caller that can fail mid-call inherits it."* The evaluation's caller
> is scripted, which §II says outright. Nothing in this file may be read as
> claiming an agent was evaluated.

## Categories

| Field | Value |
|---|---|
| **Primary** | `cs.SE` — Software Engineering |
| **Secondary** | `cs.DC` — Distributed, Parallel, and Cluster Computing |

> **These are an author choice with no source in the manuscript**, so no check
> can derive them — unlike the title, the keywords and the abstract, which are
> all checked against `main.tex`. Recorded here as a decision. They match the
> cover letter's fit argument: a reliability-engineering contribution evaluated
> by fault injection, not a distributed-systems-theory one.

## Comments field

```
2 figures, 11 tables. Code, manuscript source, and tracked derived analysis:
https://github.com/hafizmirhamza276-lab/Research-paper-AEP
Raw evidence archive is assembled and verified in two parts (26,300 + 18,494
files; manifests 87fa2d53... and 54d1ab0f...), deposited under one Zenodo
record. Insert the DOI here and do not submit this metadata until it
resolves.
```

> **Counted from the source, not estimated.** 2 `figure` and 11 `table`
> environments across `main.tex`, `sections/*.tex` and `generated/*.tex`,
> which is the submitted document; 5 of the 11 tables are generator-produced.
> `supplementary.tex` adds 1 figure and 2 tables and is a separate document —
> if it is bundled, the line reads 3 and 13. **This said "3 figures, 12
> tables" until 2026-09-22 and matched neither scope.** Re-count if the
> manuscript changes:
> `grep -c 'begin{figure' paper/main.tex paper/sections/*.tex paper/generated/*.tex`.

> **Where the DOI comes from.** It is defined once, in `paper/main.tex` at the
> `\newcommand{\archivedoi}` line, and it already holds the real value,
> `10.5281/zenodo.22766567`. It is **reserved, not resolving** — the record is
> still a draft. Take the value from there rather than re-typing it, so this
> file and the manuscript cannot disagree, and do not submit this metadata
> until it resolves. What changes at publication is the line below it,
> `\archivedoistate`, not `\archivedoi`. `docs/29-archive-deposit.md` §5 is the
> checklist.
>
> **In the anonymous build the DOI is withheld**, exactly as the GitHub URL is:
> a Zenodo record names its depositor, so citing it under double-anonymous
> review defeats the anonymisation. The anonymous branch of the toggle never
> reads `\archivedoi`, so it cannot leak even if one is inserted. If this
> metadata accompanies an anonymous submission, the archive line must read
> "available via the submission system" and carry no DOI.

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

**Generated. Do not edit by hand.** Rendered from `main.tex`'s `abstract`
environment: LaTeX markup removed, em-dashes as `--`, `x` for the
multiplication sign, `^` for exponents, generated macros resolved. arXiv's
abstract field is plain text and reflows, so the paragraph breaks below are
the only formatting that survives.

<!-- BEGIN GENERATED ABSTRACT -- render_arxiv_abstract.py -->
```
Many enterprise APIs are non-idempotent, accept no idempotency key, and cannot be asked afterwards whether a mutation was applied. A caller that crashes around such a call (an autonomous agent, a workflow engine) has no safe option: retrying risks a second real-world effect nobody observes, not retrying an effect no record accounts for. We argue this is not an engineering-quality problem but a three-way trade whose third corner a system must make reachable: silent failure converted into declared, durable, bounded ambiguity an operator can act on.

We present AEP, a fail-closed protocol in which every external side effect is preceded by a durably acknowledged write-ahead intent, every state write is fenced by lock ownership and an expected-version CAS in one atomic script, and every unresolvable outcome escalates rather than guessing. We evaluate it against five baseline designs under SIGKILL faults, across endpoint capabilities differing in what a read-back can settle.

Our central result separates two claims usually sold as one. Detection (no undetected duplicate and no lost effect, leaving a residual of declared ambiguity) comes from the pre-dispatch record and a transition table that forbids re-entry into dispatch, not from the durability barrier. Prevention is what the barrier contributes, against a narrower fault than it appears: it withholds dispatch when the store dies inside the acknowledgment window, not when storage discards writes while reporting success, which we injected and where it dispatched. Because detection does not depend on the barrier, its cost is a deployment choice, not the protocol's price.
```
<!-- END GENERATED ABSTRACT -->

**Length: 1 646 characters**, measured by the renderer on every run under the
strictest reading — every byte of the block above, newlines counted. arXiv's
limit is 1 920: *"abstracts longer than 1920 characters will not be accepted"*,
[info.arxiv.org/help/prep.html](https://info.arxiv.org/help/prep.html), read
2026-08-21. **274 characters of headroom**, and the renderer fails the build
rather than truncating if a manuscript edit ever crosses the limit.

> **There is no longer a short form, and that is the point.** This file used to
> carry a hand-written 1 906-character abridgement because the abstract of the
> day rendered to 3 252 characters and could not be pasted. The manuscript's
> abstract has since been rewritten and now fits with room to spare, so the
> abridgement has been deleted rather than updated: it was a second
> hand-maintained copy of the abstract, and it had drifted too.

---

## Pre-submission checklist for the human

- [ ] The independent audit has returned a SUBMIT verdict.
- [ ] `python scripts/render_arxiv_abstract.py --check` passes. It runs in the
      suite, so a red build means this file is stale — regenerate, do not
      hand-edit.
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
- [ ] Re-count the figure and table totals in the comments field if the
      manuscript has gained or lost either since 2026-09-22.
- [ ] Create and verify the new immutable release/tag, upload **both** raw
      archives (including `results/voided/` and each archive's own SHA-256
      manifest) into the existing reserved record, publish it, and update the
      comments field only after the DOI resolves. `docs/29` is the checklist;
      do not create a new Zenodo record, which would mint a different DOI.
- [ ] Upload the PDF built by `scripts/build_paper.sh`, or the source tree —
      arXiv prefers LaTeX source; if source is used, confirm `IEEEtran.cls`
      resolves on arXiv's TeX Live and that `paper/generated/*.tex` and
      `paper/figures/*` are included.
