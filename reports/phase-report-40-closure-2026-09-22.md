# Phase 40 — closure: the record, the manuscript ruling, and what may outlive it

**No live call was made in this session.** No manuscript file was edited.

| | |
|---|---|
| decision | **close phase 40 at stage 100's first failure**, by author decision |
| stop rule | **did not fire** — none of §9's three conditions is met |
| closure document | `prompts/phase-40-closure-2026-09-22.md` |
| §9's on-stop procedure | applied: partial record committed, `docs/33` status lines updated |
| manuscript | **unchanged**, and §3 below sets out why, form by form |
| total spend, whole workstream | **USD 0.00775720**, 38 live calls, 0 voided |

---

## 1. The closure, in one table

| | |
|---|---|
| stages run | stub, 10, 30, 100 |
| stage verdicts | 10 **passed** (C4-as-written failed twice, amendment 5); 30 **PARTIAL** (clause 1 withdrawn, amendment 7); 100 **FAILED** |
| stage 300 | never opened |
| declared ambiguities, `AEP_FULL` | **1** |
| undetected duplicates, `B0_NAIVE_RETRY` | **0** |
| re-decisions offered, stages 30 + 100 | **12** |
| agent re-dispatches | **0** |
| §8's F1 | **not evaluated** — defined over 20 runs, 4 collected |
| amendments | 9, of which 2 were overrides |
| instrument findings | 3 — amendments 6, 8, 9 |

§9 did not fire on any limb: spend **0.078 %** of the USD 10 threshold, **one**
stage failure where the rule needs two, and **23 days** left on the 2026-10-15
date. The full reasoning is in the closure document §2; the operative sentence
is that continuing required a **third** override of the pre-registration's own
gates to collect more of a result that had not varied in 12 of 12 offers, and
the author chose the instrument's credibility over the marginal evidence.

---

## 2. §9's on-stop procedure, item by item

> On stop: the partial record is committed, `docs/33`'s status lines are updated
> again to say so, and no manuscript text depends on it — §VI-F does not exist
> and is not created until stage 300 passes.

| clause | done | where |
|---|---|---|
| the partial record is committed | ✔ — and was already: every stage has a report, and the text evidence for stages 10, 30 and 100 is tracked | `reports/phase-report-40-*.md`, `reports/raw/phase40-*/` |
| `docs/33`'s status lines are updated again to say so | ✔ — head status line, a third §0 banner, and §6's "yet" settled | `docs/33-agent-workload.md` |
| no manuscript text depends on it | ✔ — **no manuscript file is edited**, so nothing in it can depend on the collection | §3 below |
| §VI-F does not exist and is not created | ✔ — it never existed; §6 of `docs/33` now records that the condition under which it could have been created is spent | — |

---

## 3. The manuscript — decided from the text, no prose written into it

### 3.1 The four rules that govern this, quoted in full

**R1 — `docs/33` §3.2**, which the pre-registration's §0 quotes as already
binding on this workstream before it began:

> A hosted API *"is a remote, versioned, silently-updated dependency with no
> digest, no pin, and no guarantee that the same prompt returns the same
> completion tomorrow. A result computed through one cannot be regenerated, only
> re-observed… **No number that reaches the manuscript may come from it.**"*

**R2 — pre-registration §2**:

> **Never as a rate. Never in a table beside the matrix.** No value from this
> collection enters `paper/generated/`, `numbers.tex`, or any table that a
> reader could read as comparable to a matrix cell. **If it appears in the
> manuscript at all it appears as prose with a pointer to the archived
> transcripts.**

**R3 — pre-registration §9, the on-stop clause**:

> On stop: … and **no manuscript text depends on it** — §VI-F does not exist and
> is not created **until stage 300 passes**.

**R4 — pre-registration §10, "What is *not* pre-registered here"**:

> * The manuscript prose. **No §VI-F, no §I change, until stage 300 passes and
>   the result is known.**

**The load-bearing fact.** R2's permissive clause — *"If it appears in the
manuscript at all"* — is the only sentence in the whole pre-registration that
contemplates a manuscript mention. R3 and R4 both gate manuscript prose on
**stage 300 passing**. Stage 300 did not pass, was never opened, and will not be
attempted. **The condition is therefore never satisfied, and R2's permission
never activates.**

### 3.2 The permission table

| # | form of mention | permitted? | rule, quoted |
|---|---|---|---|
| **1** | **A result** — any count from the collection, in prose, a table, or a macro | **FORBIDDEN**, three independent grounds | R1: *"**No number that reaches the manuscript may come from it.**"* — unconditional, not gated on any stage. R2: *"No value from this collection enters `paper/generated/`, `numbers.tex`, or any table that a reader could read as comparable to a matrix cell."* R3: *"**no manuscript text depends on it**"* |
| **2** | **A threats-to-validity note about phase 40** — e.g. "an LLM caller declined to re-dispatch in our trial" | **FORBIDDEN** | R3: *"**no manuscript text depends on it**"*. A threat sentence that reports what the collection showed depends on the collection by construction. R4 gates *"the manuscript prose"* on stage 300, which did not pass |
| **2b** | **A threats note about the caller being scripted**, making no reference to phase 40 | **PERMITTED — and already present, twice.** Nothing to add | Not gated: it depends on the *matrix*, not on phase 40. Already written at `sections/02-motivating.tex:9` and `sections/08-threats.tex:284` — see §3.4 |
| **3** | **A future-work sentence** — "future work should place a real LLM in the caller position" | **PERMITTED in principle, but NOT RECOMMENDED — it would now be inaccurate** | R3 and R4 bar text that *depends on* the collection; a sentence that names no result does not. **But**: phase 40 did place a real LLM in the caller position, and a sentence implying the question is untouched would be false by omission. The only accurate version states the result, which form 1 forbids. **The two constraints have no overlap.** |
| **4** | **An artifact pointer** — a sentence in §IX directing readers to `reports/raw/phase40-*` | **FORBIDDEN as a manuscript sentence, and unnecessary** | R3: a pointer to the collection is text that depends on it. R2's *"prose with a pointer to the archived transcripts"* is the clause that would allow it, and R4 gates it on stage 300. **Unnecessary** because the evidence is already public without it: §IX describes the repository as the artifact, and `reports/` and `reports/raw/phase40-*/` are in the repository |

**Net ruling: no manuscript text may mention phase 40 in any of the four
forms.** Forms 1, 2 and 4 are forbidden. Form 3 is technically permitted and
would be inaccurate, so it is not drafted. Form 2b needs nothing because it is
already written and remains true.

### 3.3 One consequence worth stating plainly

**The closure creates no manuscript debt.** Because no manuscript text ever
depended on phase 40 — §10 forbade writing any until stage 300 passed, and
stage 300 never passed — **there is nothing to retract, correct, or soften.**
The Option A position that `docs/33` §0's 2026-09-04 banner records is exactly
where this closure leaves the paper. That is the pre-registration's discipline
working: the prose was gated on the result, so an absent result costs no prose.

### 3.4 Every current mention of agents, T6, or phase 40 — and whether it is still accurate

Scanned across `paper/main.tex`, `paper/supplementary.tex`, all nine
`paper/sections/*.tex` and all six `paper/generated/*.tex`,
case-insensitively, for *agent*, *T6*, *phase 40*, *phase-40*, *LLM* and
*language model*.

**"T6" occurs zero times. "phase 40", "phase-40", "LLM" and "language model"
occur zero times.** T6 is a blocker identifier in `docs/26`, not a manuscript
element.

**"agent" occurs on 11 lines in 4 files — `main.tex` 3, `01-introduction` 2,
`02-motivating` 2, `07-related` 4 — falling in 9 distinct places**, audited
below. `supplementary.tex` has **none**, and so does every file under
`paper/generated/`, which is the tree R2 names first.

| # | file:line | text, abridged | role | accurate after closure? |
|---|---|---|---|---|
| 1 | `main.tex:213` | *"…recorded in the artifact repository's commit trailers and in its `.claude/agents/` definitions"* | **not a mention of agents at all** — a directory name in the AI-assistance disclosure | **✔ unaffected** |
| 2 | `main.tex:265` (abstract) | *"A caller that crashes around such a call --- an autonomous agent, a workflow engine --- has no safe option"* | agent as one named example of a caller class | **✔ accurate.** A claim about callers in general, evidenced by the matrix. Does not assert an agent was evaluated |
| 3 | `main.tex:293` (keywords) | *"…reliability engineering, autonomous agents."* | index term | **✔ accurate.** Matches §I's framing of agents as motivating context |
| 4 | `sections/01-introduction.tex:4` | *"An autonomous agent is asked to post a journal entry, issue a refund, or file a regulatory notification."* | the opening scenario | **✔ accurate.** A scenario, not a result |
| 5 | `sections/01-introduction.tex:7` | *"Autonomous agents are the setting in which this is now most visible, and **we use them throughout as the motivating example**; the problem belongs to the endpoint, and any caller that can fail mid-call inherits it"* | **the Option A position, stated explicitly** | **✔ accurate, and load-bearing.** This is the exact sentence the retitle decision turns on. It claims agents as *motivating example* and locates the problem at the endpoint. Closure changes nothing about it |
| 6 | `sections/02-motivating.tex:9–11` | *"**It is a scripted caller, not an agent** --- the traces show what the endpoint does to a caller that crashes, which is the property an agent deployment would inherit."* | the honest disclosure about the workload | **✔ accurate, and it is form 2b.** Still literally true: the traces come from the scripted workload. Phase 40's collections are not in the manuscript and were never traces in §II |
| 7 | `sections/07-related.tex:225–227` | *"**Agent execution reliability** Three contemporaneous systems overlap… agent tool failures and uses postcondition verification, verify-before-retry…"* | related work | **✔ accurate.** A description of others' systems |
| 8 | `sections/07-related.tex:236` | *"broader in agent-state-machine structure where AEP is narrower"* | related work comparison | **✔ accurate** |
| 9 | `sections/07-related.tex:242` | *"semantic rollback during agent checkpoint-restore~\cite{zheng2026acrfence}"* | related work citation | **✔ accurate** |

**All nine places are accurate after closure, and none requires an edit.** Every one is
either a description of the motivating setting, a description of other people's
work, or the explicit disclosure that the caller is scripted. **Not one claims
that an agent was evaluated**, which is exactly the property the Option A
retitle was chosen to produce — and the reason closure costs the manuscript
nothing.

Two adjacent paragraphs are worth naming because they already do the work a
post-closure threats note would have done:

* `sections/08-threats.tex:284–289`, *"The motivating traces come from our own
  harness"* — *"It establishes that the failure modes are reachable under the
  stated fault model; it is not evidence about their frequency in production
  deployments, and we have none."*
* `sections/08-threats.tex:123–130`, *"Declared ambiguity is not evaluated as an
  operational outcome"* — *"It does not show that declaring is better in
  practice; that would require an operator study, and we have run none."*

Both are true before and after phase 40, and neither is strengthened or
weakened by it.

### 3.5 Drafted text

**None.** Form 1 is forbidden, form 2 is forbidden, form 4 is forbidden, and
form 3 is permitted only in a shape that would misstate the record (§3.2). Form
2b is already written. **There is nothing to draft that the rules allow and the
facts support**, so this section contains no draft rather than a draft the
author would have to reject.

Had the author wished to overrule §3.2's reading — which is the author's to do,
and which would be a fourth override — the single sentence that would carry the
least risk is recorded here **as an illustration of what would be involved, not
as a proposal**:

> % NOT PROPOSED. Would require overriding §9/§10 of the phase-40
> % pre-registration, which gate all manuscript prose on stage 300 passing.
> A separate pre-registered trial placing a hosted language model in the caller
> position is archived with the artifact; it is not part of this evaluation, and
> no number in this paper comes from it.

Even this is form 4 — an artifact pointer — and is therefore forbidden as
written. It is shown so the author can see the shape of the decision rather than
having to reconstruct it.

---

## 4. For a supervisor discussion — methodological findings that might stand on their own

**This is a list for a conversation, not a set of claims.** Nothing here is
asserted as a result, none of it has been checked against related work, and none
of it is evidenced at a scale that would support publication as stated. Each
entry names what was observed and where the evidence is, so the conversation can
start from the record rather than from a recollection.

### 4.1 Putting an LLM in the caller position leaks arm identity into a paired comparison, in ways the protocol's own tests cannot see

**The strongest candidate, and the one that generalises furthest.** Three
distinct leaks were found in one small workstream, each by a different check,
and each would have silently confounded the comparison it was meant to enable.

| leak | mechanism | how it was found | evidence |
|---|---|---|---|
| **Supervisor-owned retry** | `B0_NAIVE_RETRY`'s `ResumePolicy` issued `REEXECUTE_CRASHED` and `AEP_FULL`'s did not, so the second dispatch was the *harness's*, on one arm only | reading the event log of the first live stage and asking who made each dispatch | amendment 6; `reports/phase-report-40-amendment-6-2026-09-21.md` |
| **Arm-keyed randomness** | `cell_seed(matrix_seed, cell.key, repetition)` derives from `cell.key`, which begins with `system.value`, so the two arms drew **different workloads and different fault schedules** | an explicit fault-symmetry precondition run before the paired stage | amendment 8; `reports/phase-report-40-fault-symmetry-2026-09-22.md` |
| **Arm-specific failure vocabulary** | `AEP_FULL` can refuse locally before transmission (expired lease); the harness reported that to the caller as `server_error`, a value `B0_NAIVE_RETRY` could not produce by that route | tracing why a refusal at +5.5 s against a 25 s TTL reached the agent as a provider error | amendment 9; `reports/phase-report-40-lease-refusal-2026-09-22.md`, `-amendment-9-2026-09-22.md` |

**The common structure is what makes this interesting.** All three are invisible
to a scripted caller, because a scripted caller does not need the two arms to be
*indistinguishable from the caller's side* — it needs only that they be
correctly implemented. Introducing a model as the caller converts the comparison
into something closer to a blinded trial, and blinding has failure modes that
correctness testing does not cover. **A short methods note on "blinding a
paired systems comparison when the caller is a language model" is the shape this
would take**, with the three leaks as worked examples and the checks that caught
them as the contribution.

**What it lacks:** any survey of whether this is already known in the
A/B-testing, clinical-trial or systems-benchmarking literatures; and evidence
from more than one harness.

### 4.2 A pre-registration with stage gates can deadlock against its own failure definition

**Second strongest, and it is a finding about pre-registration design rather
than about systems.** Phase 40's §6 gates each stage on the previous one
passing; its §8 defines the publishable negative result (**F1**) over the 20-run
design that only the *final* stage collects; and its §9 abandons the workstream
after two failures of any stage. The result is that **the evidence needed to
report the negative finding is reachable only through a gate that the negative
finding itself keeps shut.**

This was not a drafting error that a careful reader would have caught — the
structure is the standard one (escalating cost gates, a pre-declared failure
condition, a stop rule), and the deadlock appears only when the failure
condition's *scale* differs from the gate's scale.

**Evidence:** `prompts/phase-40-agent-reachability.md` §§6, 8, 9;
`reports/phase-report-40-stage-100-2026-09-22.md` §6.3, which sets the deadlock
out in four steps; and the closure document §2.3.

**What it lacks:** it is one instance. Whether the pattern recurs in registered
reports elsewhere is exactly the question a supervisor would ask first.

### 4.3 "Reachability with an LLM caller" is a claim whose instrument has to be built before it can be asked

Phase 40 spent nine amendments and 38 live calls, and **four of those amendments
were corrections to the instrument rather than to the design** (2, 3, 6, 8, 9 —
five, counting the prompt revisions). The experiment as originally written could
not ask its own question: at stage 10 the loop decided all three turns before any
of them executed, so no outcome existed at decision time and the re-planning
claim had no referent.

**The transferable observation** is that placing a model in an existing
fault-injection harness is not an integration task. The harness's assumptions —
that the caller is replayable from a seed, that the supervisor may retry on the
caller's behalf, that an exception class is a faithful description of what the
caller experienced — are all violated at once, and each violation is silent.

**Evidence:** amendments 2, 3, 6, 8, 9 and their reports; the stage-10 report's
finding that *"the design cannot ask its own question"*.

### 4.4 A transcript is weaker evidence than a seed, and the difference becomes concrete when the deployment auto-upgrades

`docs/33` §3.3 states the principle — *"a seed lets a reader recompute the run, a
transcript only lets them check it against what was recorded"*. Phase 40 made it
concrete: amendment 1 found the Azure deployment reports an **alias**, not a
snapshot, so the model behind the recorded `api-version` can move without notice.
The archived transcripts remain auditable; the configuration that produced them
is not re-runnable even in principle.

**Evidence:** amendment 1; `reports/raw/phase40-deployment-2026-09-18/`;
pre-registration §7.

**What it lacks:** this is closer to a well-known caveat than a finding, and it
would need a sharper claim to be worth writing up separately. Listed because it
is the reproducibility argument in its most concrete available form.

### 4.5 A negative behavioural result about LLM callers and non-idempotent retries — flagged as the weakest, and why

Across 12 neutral offers on two arms, under total uncertainty about whether a
non-idempotent payment had been applied, **the model declined to re-dispatch
every time**, and gave the duplicate risk as its reason without having been told
duplicates were the subject.

**This is listed last and marked weakest deliberately.** It is one model, one
deployment, one prompt, one `reasoning.effort`, one date, on a deployment that
auto-upgrades; the sample is 12 decisions; and §7 of the pre-registration
forbids exactly this generalisation. **It is not a result about LLMs.** It is
recorded because it is the observation a supervisor is most likely to find
interesting and most likely to over-read, and both of those are reasons to have
it written down with its limits attached.

**Evidence:** `reports/phase-report-40-stage-30-2026-09-21.md` §6.3;
`reports/phase-report-40-stage-100-2026-09-22.md` §§3.1–3.3, which carry all
eleven stop reasons verbatim.

---

## 5. Open items, carried unresolved

Reproduced from the closure document §7 so the report is self-contained.

| # | item | status |
|---|---|---|
| 1 | `B0_NAIVE_RETRY` never passes the transmission counter (`mutate` vs `transmit_once`) — latent, never exercised | **open, not fixed** |
| 2 | One agent decision declined a never-attempted payment, against the separate-payments statement | **open, not fixed** |
| 3 | The invoice check — cost is *computed*, not verified as *billed* | **open**, from amendment 5 §4.2 |
| 4 | §5's `temperature` and `top_p` absent from the transcript rather than recorded as not settable | **open**, from amendment 5 §6 |
| 5 | Stage 300's shortfall, `N ≤ 15` against §1's 20 | **open**, from amendment 7 — now moot, stage 300 will not run |

Items 1 and 2 are the two the author named. **None is fixed by this closure**,
and fixing them would have made the closure a milestone rather than a stop.

---

## 6. Verification

| | |
|---|---|
| live calls this session | **none** |
| manuscript files edited | **none** |
| harness or protocol code changed | **none** |
| `docs/33` status lines updated | ✔ head line, §0 third banner, §6's "yet" settled |
| builds | four, supplementaries first |
| gate | `prove_anonymous_gate.sh` |
| suite | full |
