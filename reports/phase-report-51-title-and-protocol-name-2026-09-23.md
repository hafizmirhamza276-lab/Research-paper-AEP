# Phase 51 — the title and the protocol's name

> ## DECIDED AND APPLIED, 2026-09-23
>
> **The author adopted T2 and E3.** This report was written as a proposal and is
> kept as written; the record of what was decided and applied is §8, appended.
>
> | | |
> |---|---|
> | title | **T2** — `AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys`, applied in `67092b2` |
> | expansion | **E3** — no expansion. AEP introduced as a bare name in `47119dd` |
> | *"Agent Execution Protocol"* | **NOT reinstated.** Three reasons, §8.2 |

**Written as a PROPOSAL. §§1–7 are as drafted, before any decision.** The
recommendation is at §7; what was decided is at §8.

**No live calls.**

---

## 1. Where things stand

### 1.1 The title, quoted, with counts

`paper/main.tex:250-251`, set across two lines with an explicit `\\` so
IEEEtran breaks it where the author chose:

```latex
\title{Declared Ambiguity: Fail-Closed Execution for Non-Idempotent\\
Legacy APIs Without Idempotency Keys}
```

As one line: **11 words, 97 characters.**

> Declared Ambiguity: Fail-Closed Execution for Non-Idempotent Legacy APIs
> Without Idempotency Keys

### 1.2 The running head

Yes, there is one. `paper/main.tex:259-260`:

```latex
\markboth{IEEE Transactions on Software Engineering}%
{Declared Ambiguity for Non-Idempotent Legacy APIs}
```

The second argument is the recto running head: **6 words, 49 characters.** It is
already a shortened form of the title and drops *Fail-Closed Execution* and
*Without Idempotency Keys*.

### 1.3 "Agent Execution Protocol" is absent; "AEP" is everywhere and is never introduced

| string | occurrences in `paper/` |
|---|---|
| `Agent Execution Protocol` | **0** |
| `AEP` | **102** |

The 102 break down as `main.tex` 3, `supplementary.tex` 11, and 88 across the
sections — `06-evaluation` 37, `07-related` 28, `08-threats` 9, `02-motivating`
6, `01-introduction` 3, `03-model` 2, `05-implementation` 2, `04-protocol` 1,
`09-artifact` 0.

**The first use is `sections/01-introduction.tex:65`:**

> What a designer can choose is where the uncertainty is allowed to surface.
> **AEP** places it in a durable state that an operator can see, and never in
> the accounts.

There is no introduction, no expansion and no definition of `AEP` anywhere in
the manuscript or the supplementary. **A reader meets the name cold, 65 lines
into §I, and is never told what it is.** This is a defect independent of the
title question.

### 1.4 The commit that removed it, and its stated reason

**`241292e`, 2026-09-04 — "WS-1 Option A, part 1: retitle around the API
problem".**

It replaced this title:

```latex
\title{Declared Ambiguity: The Agent Execution Protocol (AEP) for\\
Non-Idempotent Legacy APIs}
```

and this abstract opening:

> We present the Agent Execution Protocol (AEP), a fail-closed execution
> protocol…

The reason, quoted from the commit message:

> Reverses the Option B decision. The paper is retitled […] **so the subject is
> the class of callers that cannot be made idempotent rather than autonomous
> agents specifically.**

`docs/33-agent-workload.md` §0 carries the matching banner:

> **SUPERSEDED 2026-09-04: Option A was executed instead.** […] the paper is
> retitled around the API problem […] **and autonomous agents become the
> motivating deployment context in §I and §II rather than the subject.**

So the expansion was not dropped for length. It was dropped because it named
agents as the subject, and the paper decided they are not.

---

## 2. Everything a title or name change would have to touch

Verified by search, not by memory.

### 2.1 Rendered manuscript — must change

| # | location | what |
|---|---|---|
| 1 | `paper/main.tex:250-251` | `\title{}`, with its `\\` break |
| 2 | `paper/main.tex:259-260` | `\markboth{}` running head, second argument |
| 3 | `paper/supplementary.tex:64-66` | `\title{Supplementary Material for\\ \emph{<full title>}}` — carries the title verbatim |

### 2.2 Rendered manuscript — must change only if the name changes

| # | location | what |
|---|---|---|
| 4 | `sections/01-introduction.tex:65` | the first `AEP`, where an introduction would go |
| 5 | abstract, `main.tex:264-290` | currently names no protocol; a name in the title normally appears here too |

### 2.3 Source comments and metadata — must change for consistency

| # | location | what |
|---|---|---|
| 6 | `paper/main.tex:2-3` | file header comment, already the short form *"AEP: Declared Ambiguity for Non-Idempotent Legacy APIs"* |
| 7 | `paper/supplementary.tex:2` | header comment quoting the full title |
| 8 | `paper/arxiv-metadata.md:22` | the `## Title` block |
| 9 | `paper/arxiv-metadata.md:30` | the `## Keywords` block, only if keywords change |
| 10 | `paper/cover-letter-tse.md:3` and `:15` | both quote the title |
| 11 | `CITATION.cff:3` | `title:` |
| 12 | `README.md`, `ARTIFACT.md` | quote the title |
| 13 | `docs/26`, `docs/29`, `docs/33` | quote the title; these are records, so a note is better than an edit |

### 2.4 `paper/generated/` — nothing to change, and one thing that must NOT

**No generated file contains the title.** Confirmed by search across all six.

**`AEP_FULL` and `AEP-full` appear in all six generated files** —
`numbers.tex`, `table-ablation`, `table-ambiguity-by-crashpoint`,
`table-deployment-choice`, `table-latency`, `table-outcomes`. These are **system
identifiers read out of the analysis CSVs**, alongside `B3_INTENT_NO_BARRIER`.
They are data, not prose. **A rename must not touch them**, and `paper_tables.py`
would overwrite any hand edit on the next regeneration.

### 2.5 `render_arxiv_abstract.py` — no code change, one hard constraint

`extract_title()` at line 82 parses the title generically:

```python
match = re.search(r"\\title\{(.*?)\}\s*\n\n", main_tex, re.DOTALL)
title = match.group(1).replace("\\\\", " ")
```

It hardcodes no title. **Two constraints survive any retitle:**

1. `\title{...}` must be followed by a **blank line**, or the regex fails and
   the script raises `RenderError("no title in main.tex")`.
2. The only line-break form inside the title may be `\\`, which is stripped to a
   space. `test_the_title_loses_its_typesetting_line_break` asserts this.

**`--write` does not write the title.** It replaces only the block between the
`BEGIN/END GENERATED ABSTRACT` markers. `check()` at line 286 *verifies* the
title is present in `arxiv-metadata.md` and reports if not. **So the Title block
in `arxiv-metadata.md` must be edited by hand**, and the suite will fail until it
is — which is the correct behaviour and is how this session's abstract drift was
caught.

---

## 3. Confirmation: no gate, test or build step blocks a title change

| gate | title dependency | blocks a change? |
|---|---|---|
| `scripts/check_paper_numbers.py` | **structural only.** It locates the byline as *"the line after the last title line and before the abstract"* (l. 588) by scanning page 1 for the line before `Abstract`. It never reads the title's text and does not care how many lines it occupies | **no** |
| `scripts/build_paper.sh` | none | **no** |
| `scripts/prove_anonymous_gate.sh` | none | **no** |
| `scripts/check_no_repo_paths.py` | none | **no** |
| `tests/test_arxiv_abstract.py` | **consistency only.** Compares `main.tex`'s extracted title against `arxiv-metadata.md`. `test_known_positive_a_changed_title_is_caught` tampers with the title to prove the check fires; it does not pin the real string | **no** — but it **will fail** until `arxiv-metadata.md:22` is updated by hand |
| `main.tex:177` `\hypersetup{pdftitle={}}` | **anonymous branch sets it empty deliberately**, so the title never reaches DocInfo | **no** — and it must stay empty |

**No file in the repository hardcodes the title as a test expectation.** A
retitle is a content change with one manual follow-up (`arxiv-metadata.md`) and
one regeneration-safety rule (leave `AEP_FULL` alone).

---

## 4. Five title candidates

Each is ≤ 12 words, names no author or organisation, and asserts nothing about
agents or LLM callers having been evaluated.

### T1 — 7 words, 65 characters

> **Declared Ambiguity: Fail-Closed Execution for Non-Idempotent APIs**

**Claims:** that the paper presents a fail-closed execution discipline for
non-idempotent APIs whose residual is declared ambiguity. All three are the
body's own terms; C3 and §VI-A support it.

**Risk:** it drops *Without Idempotency Keys*, and that qualifier is not
redundant with *Non-Idempotent*. §VII discusses endpoints that are
non-idempotent **and** accept an `Idempotency-Key` header (Stripe, Adyen), which
are explicitly out of scope. A reviewer reading only the title may assume that
case is in scope. Mitigated, not removed, by the abstract's first sentence.

### T2 — 9 words, 72 characters

> **AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys**

**Claims:** names the protocol, the residual and the full endpoint scope
condition. The only candidate that shortens the title and keeps the scope
condition intact.

**Risk:** it leads with an acronym the reader has not met. If the expansion
question (§5) resolves to *do not expand*, the title's first word is a name that
is never unpacked anywhere in the paper. Some reviewers read acronym-first
titles as self-branding.

### T3 — 8 words, 72 characters

> **Detection Without Durability: Declared Ambiguity for Non-Idempotent APIs**

**Claims:** leads with the paper's actual central result — detection comes from
the pre-dispatch record and the transition table, not from the durability
barrier (§VI, and the abstract's third paragraph).

**Risk:** *"Without Durability"* reads at a glance as *"this protocol does not
give you durability"*, which is the opposite of what §VI says. The barrier
exists, is measured, and costs `\BarrierCostFifteen{}` ms under `everysec`; the
claim is that **detection** does not depend on it. The strongest result, in the
most misreadable phrasing.

### T4 — 9 words, 59 characters

> **AEP: Fail-Closed Execution When an Endpoint Cannot Be Asked**

**Claims:** names the protocol and the defining condition — the endpoint cannot
be queried after the fact about whether a mutation was applied. Shortest of the
five.

**Risk:** *"cannot be asked"* is informal for TSE, and it flattens three
distinct capability classes (`\textsc{none}`, positive-only read-back,
authoritative read-back) into one binary. §VI's whole capability axis is that
*cannot be asked* is the worst of three cases, not the only one.

### T5 — 9 words, 73 characters

> **Converting Silent Failure into Declared Ambiguity for Non-Idempotent APIs**

**Claims:** exactly the abstract's third-corner framing — *"silent failure
converted into declared, durable, bounded ambiguity an operator can act on"*.
Both terms are defined in the body.

**Risk:** *Converting* foregrounds what the protocol achieves and says nothing
about what it costs, which is the one framing this paper has been careful to
avoid elsewhere; and it carries no protocol name, so it answers only half the
brief.

### Summary

| id | words | chars | names AEP | keeps full scope condition | leads with the central result |
|---|---|---|---|---|---|
| current | 11 | 97 | no | **yes** | no |
| T1 | **7** | **65** | no | no | no |
| T2 | 9 | 72 | **yes** | **yes** | no |
| T3 | 8 | 72 | no | no | **yes** |
| T4 | 9 | 59 | **yes** | no | no |
| T5 | 9 | 73 | no | no | no |

---

## 5. The protocol's name, and what AEP should expand to

### 5.1 Is "Agent Execution Protocol" still accurate after the phase-40 closure?

**No — and the reason is not that phase 40 failed.**

`reports/phase-report-40-closure-2026-09-22.md` §3.3 is explicit that the
closure costs the manuscript nothing:

> **The closure creates no manuscript debt.** Because no manuscript text ever
> depended on phase 40 […] **there is nothing to retract, correct, or soften.**
> The Option A position that `docs/33` §0's 2026-09-04 banner records is exactly
> where this closure leaves the paper.

And `prompts/phase-40-closure-2026-09-22.md` §6:

> §I is unchanged: **agents remain the motivating deployment context**, which is
> the Option A position `docs/33` §0's 2026-09-04 banner records and which this
> closure **leaves exactly where it found it.**

So the bar is the Option A position, which predates phase 40 and survived it
untouched. Against that bar, *Agent Execution Protocol* fails on three grounds,
each independently sufficient:

1. **It makes agents the subject.** `docs/33` §0: *"autonomous agents become the
   motivating deployment context in §I and §II **rather than the subject**"*. A
   protocol named *Agent Execution Protocol* has agents as its subject by
   construction.
2. **It contradicts §II's own disclosure.** `sections/02-motivating.tex:9`:
   *"**It is a scripted caller, not an agent** — the traces show what the
   endpoint does to a caller that crashes."* The closure report §3.4 #6 marks
   this as still accurate and as the honest disclosure about the workload.
3. **Nothing agent-shaped was evaluated.** Phase 40's collections are barred
   from the manuscript in all four forms by the closure report's §3.2 permission
   table, so the paper contains no agent execution at all. A name asserting one
   would be the strongest agent claim in the paper and the only unevidenced one.

**Re-introducing the string would reverse a decision that `241292e` took for a
stated reason and that the closure explicitly declined to reopen.**

### 5.2 Three candidate expansions

| # | expansion | overclaims? | implies an agent evaluation? |
|---|---|---|---|
| **E1** | **Agent Execution Protocol** | **Yes.** Names agents as the protocol's subject, which §II denies and §VI does not evidence | **Yes, directly.** See §5.1 |
| **E2** | **Ambiguity-Explicit Protocol** | **No.** *Declared ambiguity* is the paper's defined term and its measured residual; C3 states it over measured cells | **No.** Contains nothing about callers |
| **E3** | **no expansion — AEP is a bare name** | **No.** A name asserts nothing | **No** |

**E2's real cost, stated plainly:** it is a back-formation invented for the
paper. The repository expands the letters differently and publicly —
`README.md:1` is *"# Agent Execution Protocol (AEP)"* and `pyproject.toml:8`
describes the package as *"Agent Execution Protocol — fail-closed execution for
**agents** calling non-idempotent legacy APIs"*. Adopting E2 without saying so
would leave the paper and its own artifact expanding the same acronym two ways,
which a reviewer who opens the artifact at camera-ready will notice.

**E3's real cost:** a reader may ask what it stands for and find no answer, and
an unexpanded acronym is a weak first word for a title (T2, T4).

### 5.3 A finding that is independent of which expansion wins

**The artifact's own description still carries the Option B framing.**
`pyproject.toml:8` says the package is for *"agents calling non-idempotent legacy
APIs"*. The manuscript decided on 2026-09-04 that agents are the motivating
context and not the subject. Under double-anonymous review the artifact URL is
stripped, so this is invisible to reviewers now; at camera-ready it is not.
**Recorded, not fixed** — it is a repository-metadata question, not a manuscript
one.

### 5.4 Where the name should be introduced, and how it is used after

**Introduce it once, in §I, at the current first use — `01-introduction.tex:65`
— and nowhere else.** That line is already the first appearance; it needs a
clause, not a new paragraph.

Consistent with the existing arm names, which must not move:

| name | what it denotes | changes? |
|---|---|---|
| `AEP` | the protocol | introduced at first use |
| `AEP-full` | the arm with the barrier enabled | **no** |
| `B3` / `B3-mode` | the arm with the barrier removed | **no** |
| `AEP_FULL`, `B3_INTENT_NO_BARRIER` | the CSV system identifiers behind `paper/generated/` | **no, and cannot** — regenerated from data |

After §I, `AEP` continues to be used bare throughout, exactly as it is in all
102 current occurrences. Nothing downstream of the introduction changes.

---

## 6. What is NOT proposed here

* **No change to §I's Option A sentence** (`01-introduction.tex:7`), which the
  closure report §3.4 #5 marks *"accurate, and load-bearing"*.
* **No change to the `autonomous agents` keyword**, which §3.4 #3 marks accurate
  as an index term about the motivating setting.
* **No change to the abstract's `an autonomous agent, a workflow engine`**,
  which §3.4 #2 marks accurate as one named example of a caller class.
* **No new §VI-F and no agent claim of any kind.** Barred by the closure.

---

## 7. Recommendation

### 7.1 Title — **T2**

> **AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys**

**11 words → 9; 97 characters → 72.**

It is the only candidate that does both jobs the brief names: it shortens the
title **and** it puts the protocol's name where a reader looks for it. It is
also the only shortened candidate that **keeps the full scope condition**, which
matters more in this paper than in most, because the Stripe/Adyen case in §VII is
non-idempotent *and* key-accepting and is explicitly out of scope. T1 and T3 both
buy their brevity by dropping that distinction from the title.

T3 is the most interesting candidate and I am not recommending it: leading with
the paper's best result is attractive, but *"Detection Without Durability"* can
be read as a disclaimer about the protocol rather than a finding about what
detection depends on, and a title that can be misread as weaker than the work is
a bad trade.

**Running head, if T2 is taken:** leave `Declared Ambiguity for Non-Idempotent
Legacy APIs` as it is, or shorten to `AEP: Declared Ambiguity for
Non-Idempotent APIs` to match. Either is consistent; the running head is already
a reduction rather than a copy.

### 7.2 Expansion — **E3, with a gloss, not an expansion**

**Do not expand AEP into anything.** Introduce it as a name.

E1 is not available: §5.1 gives three independent reasons, and taking it would
reverse a decision the phase-40 closure deliberately left standing. E2 is
available and honest but invents a phrase for the paper that the artifact
contradicts, which trades one inconsistency for another.

E3 costs one thing — a reader wondering what the letters mean — and that cost is
paid by a single clause at the existing first use, something of the shape:

> We call the protocol AEP.

That is a name, not a claim, and it is the only option that asserts nothing the
body does not evidence. **It also resolves the defect in §1.3, which is real
whether or not the title changes:** as the manuscript stands, `AEP` is used 102
times and introduced zero times.

**If the author prefers an expansion,** E2 is the only usable one, and it should
carry a footnote at first use saying the artifact repository uses a different
expansion — because the alternative is letting a reviewer discover it.

### 7.3 Order of work, if both are taken

1. `main.tex` title and running head; `supplementary.tex` title; both header
   comments.
2. `01-introduction.tex:65` — the introducing clause.
3. `arxiv-metadata.md:22` by hand. **The suite fails until this is done**, which
   is the check working.
4. `CITATION.cff`, `cover-letter-tse.md`, `README.md`, `ARTIFACT.md`.
5. Leave `docs/26`, `docs/29`, `docs/33` alone and add a dated note; they are
   records of decisions, not current statements.
6. Never touch `paper/generated/` or the `AEP_FULL` identifiers.
7. Rebuild all four — supplementaries first, then `main-anon`, then `main` — and
   run the full suite.

---

## 8. Appended 2026-09-23: what was decided, and what was applied

*Everything above is as drafted, before the decision. This section is the
record of it.*

### 8.1 Title — T2, applied in `67092b2`

> **AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys**

11 words / 97 characters → **9 words / 72 characters.**

Eleven edits in eight files: `main.tex` (`\title`, `\markboth`, header
comment), `supplementary.tex` (title, header comment), `arxiv-metadata.md:22`,
`cover-letter-tse.md` (subject line and opening sentence), `CITATION.cff`,
`README.md`, `ARTIFACT.md`.

**The running head needed adjusting, not just checking.** It read *"Declared
Ambiguity for Non-Idempotent Legacy APIs"* and T2 drops *Legacy*, so it no
longer matched the title. It is now the title's first line exactly — *"AEP:
Declared Ambiguity for Non-Idempotent APIs"*, 47 characters against the old 49,
so it still fits.

**`ARTIFACT.md` was found carrying the pre-2026-09-04 title** — *"Declared
Ambiguity: The Agent Execution Protocol (AEP) for Autonomous Agents Calling
Non-Idempotent Legacy APIs"*. `241292e`'s message states *"A grep for the old
title returns nothing"*; it missed that file, which had described the current
artifact with a title naming autonomous agents as the subject for nineteen
days. Corrected in the same commit.

**`paper/generated/` untouched**, as §2.4 requires.

**One test pinned the old title and was updated rather than weakened.**
`test_the_title_loses_its_typesetting_line_break` asserted
`startswith("Declared Ambiguity:")` **and** `endswith("Without Idempotency
Keys")`. That pair is the test: it proves `extract_title` spans both authored
lines. Deleting either assertion would leave it passing on a title that lost
half of itself. The `startswith` string is now `"AEP: Declared Ambiguity"`, with
a comment recording why both must move together. Verified the guard still
bites: a title truncated to its first line fails the `endswith` assertion.

### 8.2 Expansion — E3, applied in `47119dd`, and "Agent Execution Protocol" is NOT reinstated

AEP is introduced as a **bare name** at its existing first use, with one
sentence of gloss and no expansion:

> What a designer can choose is where the uncertainty is allowed to surface.
> **We call our protocol AEP. It records an intent before every external call
> and fails closed when recovery cannot resolve the outcome.** AEP places the
> uncertainty in a durable state that an operator can see…

The gloss claims only what the abstract and §IV already state. It deliberately
does **not** say *"durably acknowledged"*, because the barrier is C4's subject
and C4's finding is that detection does not depend on it.

**"Agent Execution Protocol" is not reinstated. Three reasons, each sufficient
alone:**

1. **It makes agents the subject.** `docs/33` §0's 2026-09-04 banner:
   autonomous agents are *"the motivating deployment context in §I and §II
   **rather than the subject**"*. A protocol so named has agents as its subject
   by construction.
2. **It contradicts §II's own disclosure.** `02-motivating.tex:9`: *"**It is a
   scripted caller, not an agent** — the traces show what the endpoint does to a
   caller that crashes."*
3. **Nothing agent-shaped was evaluated.** The phase-40 closure bars that
   collection from the manuscript in all four forms of mention
   (`reports/phase-report-40-closure-2026-09-22.md` §3.2), so the paper contains
   no agent execution at all. A name asserting one would be the strongest agent
   claim in the paper and the only unevidenced one.

**This is not a consequence of phase 40 failing.** The closure report §3.3 says
the closure creates *"no manuscript debt"*, and the closure prompt §6 says §I is
left *"exactly where it found it"* — the Option A position, which predates
phase 40 and survived it untouched. That is the bar, and the expansion fails it.

### 8.3 One thing T2 creates that is worth a decision

**The title now leads with an acronym the abstract never uses.** §2.2 item 5
anticipated this: the abstract names no protocol, and with T1/T3/T5 that was
fine. With T2, a reader meets `AEP` on the title page and is not told what it is
until §I.

**Not changed, because it was not authorised and it is not free:** the abstract
is under a word limit, and any edit to it forces
`scripts/render_arxiv_abstract.py --write` and a fresh `arxiv-metadata.md`
check. **Recorded as a question for the author**, with two cheap answers if the
gap is judged too wide:

1. Name it once in the abstract's second paragraph — *"We present AEP, a
   fail-closed protocol in which…"* — which is where the protocol is first
   described anyway.
2. Leave it. The title page and §I are two pages apart in a journal two-column
   layout, and IEEE readers meet unexplained system names in titles routinely.

### 8.4 Not done, on instruction

* **`pyproject.toml:8`'s stale description** — moved to
  `reports/camera-ready-checklist.md` §1, together with `README.md:1`'s heading.
* **`docs/26`, `docs/29`, `reports/`** keep the old title. They are dated
  records; camera-ready gets a pointer note instead, checklist §3.
