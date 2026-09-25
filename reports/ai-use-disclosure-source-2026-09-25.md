# Source material for the separate AI-use report — 2026-09-25

**Why this file exists.** The supervisor's instruction is that the manuscript
carries no Acknowledgment section and no reference to AI tools or coding agents
anywhere in it, and that the disclosure is submitted as a separate report
alongside the paper. This file preserves everything that separate report needs,
recorded **before** the removal so nothing is lost with it.

**It is written to be sufficient on its own.** The separate report can be
written from this file without opening the manuscript, the PDFs or the removal
commit.

**Repository state:** `1cca797`, with all four PDFs freshly built and every gate
green. The removal is the commit that follows this file.

**Related, and not superseded:** `reports/ai-disclosure-2026-09-24.md` holds the
IEEE policy analysis, the argument that naming the systems does not de-anonymise
the author, and the reasoning behind the wording that was in the manuscript
until today. Read it for *why*; read this for *what*.

---

## 1. The disclosure text, verbatim, from both builds

Both are `\aidisclosure` in `paper/main.tex`, rendered under
**ACKNOWLEDGMENT** after §IX and before the references. Quoted here from the
built PDFs at `1cca797`, not from source, so line-breaking and ligatures are the
reader's.

### 1.1 Named build — `paper/main.pdf`, p. 24, from `main.tex:206-234`

> The author used Anthropic's Claude (Claude Code, with Opus, Sonnet and Haiku
> models) and OpenAI's Codex as coding and drafting assistants throughout this
> work. Their use was not confined to one part of it: the protocol
> implementation, the fault-injection harness, the analysis pipeline, the
> verification gates, the supporting documentation and the prose of this
> manuscript were all produced with that assistance, under the author's
> direction and subject to the author's review. The exact model identifiers are
> not listed here because such a list goes stale. For Claude they are recorded
> in the artifact repository: the commit trailers name the model that signed
> each commit, and the per-assistant configuration files committed beside them
> name the model each subagent ran. No model identifier was recorded for Codex
> at the time of use and the project does not reconstruct one after the fact, so
> its use is evidenced by the committed prompt files rather than by an
> identifier. The phase prompts issued from Phase 8 onward are committed in that
> repository, each before the data of the phase it governs; Phases 1A–7 carry no
> such record, and the project's own audit records that gap rather than
> reconstructing it.
>
> No AI system is an author. Every measurement reported here was collected by
> the harness on the author's host and is reproducible from the archived raw
> runs; every number in the manuscript is generated from those results by the
> artifact's table generator and re-derived by its independent number check. The
> author is solely responsible for the content of this article, including all
> claims, analysis and conclusions.

### 1.2 Anonymous build — `paper/main-anon.pdf`, p. 24, from `main.tex:167-176`

> The author used Anthropic's Claude (Claude Code, with Opus, Sonnet and Haiku
> models) and OpenAI's Codex as generative-AI coding and drafting assistants
> throughout this work: the protocol implementation, the fault-injection
> harness, the analysis pipeline, the verification gates, the supporting
> documentation and the prose of this manuscript were all produced with that
> assistance, under the author's direction and subject to the author's review.
> No AI system is an author; the author is solely responsible for the content of
> this article, including all claims, analysis and conclusions.

### 1.3 The difference between them, and why

The anonymous branch drops the third and fourth sentences because they point at
a repository whose URL that build withholds: the trailers, the configuration
files and the phase-prompt record are all *in* the artifact repository, and a
reviewer who found it from the description would have the author's name. The
anonymous branch names the systems and stops. Both were correct as worded at
`1cca797`; §4 below records the one claim in the named build that is weaker than
it sounds.

---

## 2. Every AI system and model identifier the repository records, and where

| identifier | kind | where recorded | count |
|---|---|---|---|
| `Claude Opus 5 (1M context)` | commit trailer | `Co-Authored-By:` trailer on commits | **444 of 536** at `26d4d84`; **447 of 539** at `1cca797` |
| `claude-opus-4-7` | subagent model | `.claude/agents/aep-orchestrator.md:4`, `.claude/agents/opus-fixer.md:4` | 2 files |
| `claude-sonnet-4-6` | subagent model | `.claude/agents/implementer.md:4`, `.claude/agents/tech-designer.md:4` | 2 files |
| `claude-haiku-4-5-20251001` | subagent model | `.claude/agents/hld-designer.md:4` | 1 file |
| **any OpenAI Codex model** | — | **nowhere** | **0** |

Reproduce with:

```
git log --format='%(trailers:key=Co-Authored-By,valueonly)' | grep -v '^$' | sort | uniq -c
grep -rn "^model:" $(git ls-files .claude)
```

**One vendor product that is recorded but is NOT an authoring assistant.**
`gpt-5.6-luna` appears in `experiments/harness/azure_client.py:136`,
`experiments/harness/planner.py:64`, the phase-40 prompts and
`tests/test_azure_client.py`. That is the **Azure planner deployment** for the
phase-40 agent-reachability experiment: an LLM placed in the *caller* position
as the object of study. It drafted nothing and wrote no code. **It must not be
offered in the AI-use report as a drafting assistant.** Naming it as one would
be a fabrication, and the manuscript's own rule against writing numbers it does
not have applies to identifiers too.

---

## 3. What each system was used for

From the disclosure, the `.claude/` configuration and the two Codex prompt
files. The scope statement in the manuscript was *"their use was not confined
to one part of it"*, and the six areas it enumerated were:

| area | detail |
|---|---|
| protocol implementation | `aep_core/`, the three Lua scripts on the intent path, the transition table and the dispatch guard |
| fault-injection harness | `experiments/harness/`, the crash-point injector, the mock provider and the baseline systems |
| analysis pipeline | `experiments/analyze.py`, `scripts/paper_tables.py` and the metric derivations |
| verification gates | `scripts/check_*.py`, `scripts/prove_anonymous_gate.sh`, `scripts/run_tlc.sh` |
| supporting documentation | `docs/`, `reports/`, the phase reports and the pre-registrations |
| manuscript prose | `paper/main.tex`, `paper/sections/*.tex`, `paper/supplementary.tex` |

### 3.1 Claude, by role

`.claude/` is tracked (12 files: 5 agent definitions, `settings.json`, 6 skill
files). `settings.json` is `{"agent": "aep-orchestrator"}`. The five agents and
the model each ran:

| agent file | model | role, from its own `description` |
|---|---|---|
| `aep-orchestrator.md` | `claude-opus-4-7` | main-thread build orchestrator; drives design, implementation, testing and security as a scored, gated loop. Writes no production code itself |
| `tech-designer.md` | `claude-sonnet-4-6` | turns an approved high-level design into schemas, module contracts, Lua/CAS logic and failure modes; also the default independent security reviewer |
| `implementer.md` | `claude-sonnet-4-6` | writes the Python from an approved technical design; also the default test executor |
| `hld-designer.md` | `claude-haiku-4-5-20251001` | fast first-pass high-level design and test-case enumeration |
| `opus-fixer.md` | `claude-opus-4-7` | escalation specialist, invoked after two failed quality-gate attempts; also hard test execution and deep security review |

The six tracked skills are `aep-context`, `aep-scoring-rubric`,
`aep-adversarial-testing`, `aep-security-review`, `redis-async-patterns`, and
`aep-context/references/brief.md`.

Claude Code (with the `Claude Opus 5 (1M context)` model recorded in the
trailers) was the interactive driver for the later phases, including the audit
responses, the B1 fix and this removal.

### 3.2 Codex, by task

Evidenced by name only, in two tracked files: `CODEX_PROMPTS.md` and
`WEEKEND_CODEX_PROMPTS.md`. Neither names a model. The closest either comes is
`CODEX_PROMPTS.md:263`, *"executed by a different model (Codex)"*.

The tasks described are an adversarial audit pass and a TLA+/Hypothesis
workstream, both of which reached the artifact. `CODEX_PROMPTS.md` is structured
as bounded prompts with `SCOPE BOUNDS`, `FORBIDDEN`, `TASKS` and
`EXPECTED RESULTS`, each verified by the author against `origin/main` and CI
before the next was issued.

**Because Codex work reached the artifact, dropping Codex from the disclosure is
not available as an option.** That was ruled out explicitly in
`reports/ai-disclosure-2026-09-24.md` §5 and is repeated here so the separate
report does not re-derive it.

---

## 4. The three facts the separate report must state accurately

### 4.1 The commit trailers: 444 of 536, and one identifier, not a per-commit one

The manuscript said *"the commit trailers name the model that signed each
commit"*. Two qualifications, and the second is the stronger:

1. **Not every commit carries one.** 444 of 536 at the audited commit `26d4d84`
   (447 of 539 at `1cca797`). **92 carry none**, spread from 2026-08-04 to
   2026-09-18, including the phase-40 amendment commits. The accurate form is
   *"the commits that carry a trailer"*. This is the second audit's §6.4
   finding and it is correct.
2. **Every trailer carries the same string.** All 444 read
   `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. No
   other identifier appears in any trailer. So the trailers do **not**
   distinguish Opus from Sonnet from Haiku, and they are not a per-commit model
   record. The per-model record is `.claude/agents/*.md`, which says which model
   each *subagent* ran, not which model touched which commit.

**The separate report should say:** the repository records four Claude model
identifiers across two mechanisms — one in the commit trailers, uniformly, on
the commits that carry one, and three in the subagent configuration files.
Neither mechanism attributes a specific commit to a specific model.

### 4.2 The Codex gap

No model identifier was recorded for Codex at the time of use. The project does
not reconstruct one after the fact. No `.codex/`, `.openai/` or equivalent
configuration directory is tracked —
`git ls-files | grep -iE '^\.(codex|openai|agents)'` is empty. Codex's use is
evidenced by the two committed prompt files and by nothing else.

This asymmetry should be stated, not smoothed. A reader who greps for a Codex
identifier should find that the report already told them there is none.

### 4.3 The Phases 1A–7 gap

`prompts/` holds **42 tracked phase prompts**, the earliest being
`prompts/phase-8-b2.md`. Every phase from 8 onward has its prompt committed, and
`scripts/check_prereg_order.py` checks that each pre-registration precedes the
data of the phase it governs, by commit date and by ancestry
(`cells: 36  ok: 31  exempt: 5  failing: 0` at `1cca797`).

**Phases 1A–7 have no committed prompt record.** Their phase reports exist —
`reports/phase-report-1A-2026-08-05.md`, `-1b-`, `-2b-session1/2/3/3b`, and so
on — but the instructions that produced them were not committed. The project's
own audit records the gap rather than reconstructing it, and the separate report
should do the same.

---

## 5. What the `.claude/` configuration shows, as a whole

- **It is committed, and it is the authoritative per-model record.** 12 files,
  tracked, readable by anyone with the repository.
- **It describes a gated pipeline, not free-form generation.** The orchestrator
  delegates to four workers, scores the result against
  `.claude/skills/aep-scoring-rubric`, and escalates to `opus-fixer` after two
  failures. Model choice is per role: Haiku for first-pass drafting, Sonnet for
  design and implementation, Opus for orchestration and escalation.
- **Security and adversarial review were themselves delegated.**
  `tech-designer` is the default independent security reviewer and
  `opus-fixer` the deep one, with `aep-security-review` and
  `aep-adversarial-testing` as their skills.
- **What it does not show.** It does not record which model produced which
  file, which commit, or which sentence of the manuscript. No such record
  exists.

---

## 6. IEEE's requirement, for the separate report's framing

From `reports/ai-disclosure-2026-09-24.md` §1, IEEE Author Center, *Submission
and Peer Review Policies*, retrieved 2026-09-24. Three obligations:

1. **Where.** Disclosure goes *"in the acknowledgments section"*.
2. **Which system.** *"The AI system used shall be identified"*.
3. **Which sections, and how much.** Specific sections using AI-generated
   content *"shall be identified and accompanied by a brief explanation
   regarding the level at which the AI system was used"*.

The editing-and-grammar carve-out does not apply here: the assistance reached
implementation, harness, analysis, gates and prose.

**The conflict the supervisor's instruction creates, recorded and not
resolved.** IEEE's obligation (1) places the disclosure *in the
acknowledgments section of the article*. The manuscript will now have no
acknowledgment section and no disclosure. A separate report submitted alongside
satisfies the substance of (2) and (3) and the spirit of (1), but not its
letter. **This is the author's and the supervisor's call, and it is recorded
here so it is a decision rather than an oversight.** If the venue's editor
raises it, the material in §§1–5 above is what restores the acknowledgment in
one edit.

---

## 7. Restoring it, if that decision is reversed

The removal commit deletes, from `paper/main.tex`:

- the `\aidisclosure` definition in the anonymous branch (§1.2's text);
- the `\aidisclosure` definition in the named branch (§1.1's text);
- the `\section*{Acknowledgment}` and its `\aidisclosure` call, with the IEEE
  style comment above them.

Nothing else in the manuscript refers to AI assistance, so restoration is
`git revert` of that commit, or re-adding those three blocks from §1 of this
file, followed by a rebuild of all four PDFs.
