# Phase 40 — WS-1b reduced: agent reachability, pre-registered

**Committed before any code is written, any stub run, and any paid call.**

This is a pre-registration, not a plan. Its purpose is to fix the design before
any outcome is visible, and it is committed *before* stub mode deliberately.
Stub mode exercises parts of this design, and a design adjusted in the light of
what stub mode shows — before it was ever committed — would be indistinguishable
to a later reader from a design that was right the first time.

> **Amendments are expected and will be recorded as amendments.** If stub mode,
> or any later stage, shows something here is wrong, the correction is a commit
> that says what changed and why, in the form
> `docs/26` §3 rule 4 and `prompts/phase-8-b2.md` already use. Nothing in this
> file is edited in place to match what was found.

---

## The prompt, as issued

> Go. Two commits this turn, in this order. Still no harness code and no model
> calls.
>
> COMMIT 1 — correct the two stale documents. […]
>
> COMMIT 2 — write the pre-registration. Follow the phase-prompt convention in
> `prompts/` — read two or three existing ones first and match their structure,
> not my phrasing. […] I disagree with your recommendation to commit it after
> stub mode. A pre-registration exists to fix the design before any outcome is
> seen, and stub mode tests parts of the design. Commit it BEFORE stub mode. If
> stub mode then shows something in it was wrong, write an amendment commit
> saying what changed and why — that is a more honest record than a
> pre-registration quietly adjusted before it was ever committed.

The author's fixed decisions, not revisited here: provider Azure OpenAI; model
GPT-5.6 Luna only; `reasoning.effort` low, pinned; snapshot pinned, not an
alias; hard budget ceiling USD 20 for the entire experiment.

---

## 0. What this experiment is for

`docs/26` A1: *"Title/framing says 'Autonomous Agents'; the evaluation contains
no agent."* T6 offered two answers — retitle, or make the framing load-bearing.
Option A was executed (`74ea31f`). This reopens Option B in a **reduced** form.

**The claim is reachability, not rate.** That the failure modes the paper
measures are reachable when the caller is a real LLM agent rather than a
scripted one — that the problem is not an artefact of the scripted workload.

**This experiment produces no headline rate and re-runs no part of the matrix.**
That is not a preference; `docs/33` §3.2 already forbids it:

> A hosted API *"is a remote, versioned, silently-updated dependency with no
> digest, no pin, and no guarantee that the same prompt returns the same
> completion tomorrow. A result computed through one cannot be regenerated, only
> re-observed… **No number that reaches the manuscript may come from it.**"*

That rule stands. This design is compatible with it because its output is a
count with transcripts, not a rate.

---

## 1. The design, fixed now

| axis | value | why this one |
|---|---|---|
| systems | `AEP_FULL`, `B0_NAIVE_RETRY` | one that exhibits the failure mode, one that prevents it. The other five add cost, not reachability |
| crash point | `mid_dispatch` | the project's established single-crash-point choice; the B5/engine session used it |
| capability class | `POSITIVE_ONLY_READBACK` | the only class where AEP-full's residual ambiguity is non-zero, so both failure modes are observable. `AUTHORITATIVE_READBACK` resolves everything and would show nothing |
| regime | `crashed` | the regime RQ1 is about |
| runs | **10 per system, 20 total** | an existence claim does not need an estimate |
| decision turns | **3 per run** | enough to plan, observe an outcome, and re-plan |

### 1.1 The target stays harness-assigned

The planner chooses **tool, action and amount**. The **target is assigned by the
harness from the execution id**, exactly as `workload.py` does today.

**This is what removes the WS-1a prerequisite.** `docs/33` §2 exists because a
re-planning agent collides targets, and the published duplicate metric
attributes an applied effect to an execution *by* `target`. Target collision is
only needed to make **plan drift** observable. This design does not measure plan
drift, so targets need not collide, so the existing attribution stays sound and
no ledger schema change, no execution-id column, no four proofs and no §VIII
construct-validity concession are required.

**Plan drift is explicitly not measured.** `docs/33` §4 is out of scope. Any
later pass that wants it must restore WS-1a first, as `docs/34` §7 costs.

---

## 2. The metric, and how it may be reported

**Binary reachability, per system.** For each of the two systems: was the
failure mode observed at least once across its 10 runs?

* `B0_NAIVE_RETRY` — at least one **undetected duplicate**.
* `AEP_FULL` — at least one **declared ambiguity**.

Reported as **counts with transcripts**: *n* of 10 runs in which the outcome
occurred, and the transcript that produced it.

**Never as a rate. Never in a table beside the matrix.** No value from this
collection enters `paper/generated/`, `numbers.tex`, or any table that a reader
could read as comparable to a matrix cell. If it appears in the manuscript at
all it appears as prose with a pointer to the archived transcripts.

---

## 3. Spending controls, all five, with their numbers

| control | value | note |
|---|---|---|
| per-run call cap | **36 attempts** | 3 turns × (1 call + 1 malformed retry) × 2 for post-crash re-entry × 3 attempts per call |
| per-collection call cap | **1 000 attempts** | the collection stops on breach |
| `max_tokens` per call | **1 024** | what makes the ceiling finite |
| per-run cost counter | written into the run directory | visible during a collection, not on the invoice |
| cumulative cost counter | **persisted to disk** | in memory it would reset on a crash-restart loop, and the ceiling below would be worthless |

Every model call passes through **one wrapper**, and the wrapper counts at the
**HTTP transport** layer, not the SDK method — the SDK's automatic retries on
429 and timeout happen *inside* a single `responses.create()` call and are
invisible above it. A retry that is not counted is a retry that is not capped.

**On per-run breach:** the run aborts and is marked **voided**, following the
`VOID_REASON.md` precedent. A voided run is not a result and does not reach
`analyze.py`.

**Ceiling if something goes wrong.** 1 000 attempts × (≤2 000 input + ≤1 024
output tokens) = ≤2 M input, ≤1.024 M output. At Azure Global Standard
$0.20/$1.20 per 1M (read 2026-09-17): **≈ USD 1.64**. At the pre-cut $1.00/$6.00
some deployments still bill: **≈ USD 8.14**. Both under the USD 20 ceiling.

---

## 4. `PLANNER_FILTERED` — a distinct void class

Azure filters requests and responses by default. A filtered call is **not** a
protocol outcome.

It is recorded as `PLANNER_FILTERED` in the event log and the run summary, the
run is marked voided, and it is **never folded into declared ambiguity**. A
filter block is a vendor policy decision; counted as ambiguity it would read as
protocol behaviour in the data and would inflate exactly the metric this paper
is most careful about.

**What it costs the paper:** a void rate that must be reported, and an admission
that the caller is subject to a filter the protocol does not control.

---

## 5. Transcripts are the only replay mechanism

A model call cannot be recomputed from a seed. Replay is served by a transcript,
and a respawned worker in replay mode **reads the transcript rather than calling
the model** — for cost as much as for correctness.

Each transcript entry records, keyed by `(run_id, worker_index, step_index)`:

full prompt · full completion · `model` · **snapshot** · `deployment` ·
`api-version` · `reasoning.effort` · temperature and top_p · prompt tokens ·
completion tokens · **reasoning tokens** · wall-clock timestamp · attempt number ·
outcome (`ok` / `filtered` / `malformed` / `retry`).

**A transcript is weaker evidence than a seed** — `docs/33` §3.3 — and the paper
must say so wherever a model-backed observation appears: a seed lets a reader
*recompute* a run, a transcript only lets them *check* it against what was
recorded.

---

## 6. Stage criteria, fixed in advance

Nothing advances automatically. The author raises each cap by hand.

| stage | must establish before the next is allowed |
|---|---|
| **stub** (0 calls) | exactly one mutation call per execution; oracle ledger and event log agree on every run; transcript written, and **replay from it reproduces the identical plan**; per-run and per-collection caps fire when forced; cost counters present and zero; `.env` absent and the harness still runs |
| **10 calls** | every call has a transcript, token counts and a cost; zero content-filter blocks, or each logged as `PLANNER_FILTERED`; zero malformed tool calls; measured cost within 20% of §3's model |
| **30** | at least one crashed run respawns and **re-enters the loop reading the transcript, issuing no new model call** for already-decided steps; void rate recorded |
| **100** | both failure modes observed at least once; cumulative spend < USD 1 |
| **300** | the full 20-run design collected; `plan_invariant.py` passes over every recorded plan; no key in any run directory; `scripts/scan_archive_for_leakage.py` clean |

---

## 7. What the paper must say about provider and model dependence

One vendor, one deployment, one pinned snapshot, one `api-version`, one
`reasoning.effort`, one date. Results **not reproducible, only auditable** from
archived transcripts. No claim about prompt sensitivity, model scale, planner
quality, or any other model — `docs/33` §5.2 already writes most of these
sentences and they carry over unchanged.

---

## 8. What would count as a FAILURE of this experiment

Written now, before any data exists, in the voice this project uses for its
other refuted predictions.

**F1 — neither failure mode is reached.** If across 20 runs no undetected
duplicate occurs under `B0_NAIVE_RETRY` and no declared ambiguity occurs under
`AEP_FULL`, the experiment has **refuted its own premise**: the failure modes
were not shown reachable with an LLM caller. The paper then says so. It does not
retry with a different prompt, a different crash point, or a larger model until
the result appears — that would make the experiment a search for a confirming
instance rather than a test. The reachability claim is dropped and §I keeps
agents as motivating context only.

**F2 — the agent cannot reliably issue one mutation call per execution.** If
malformed tool calls or refusals mean the agent does not produce exactly one
mutation call per execution in a clear majority of runs, then what was measured
is the prompt and the tool schema, not the protocol under an agent caller. The
result is reported as an instrument failure: *the harness could not put a real
LLM in the caller position reliably enough to observe anything about the
protocol*. That is a finding about this design, and it is stated as one rather
than repaired after the fact.

**Both failures are reportable results.** Neither is a reason to leave the
experiment out of the record. `reports/` carries the outcome either way.

---

## 9. The stop rule

Abandon this workstream and keep the Option A retitle if **any** of:

* **Spend.** Cumulative spend reaches **USD 10** — half the ceiling — without
  stage 100 having passed.
* **Stages.** Any stage fails its criterion **twice**. One failure is a bug; two
  is the design.
* **Date.** Stage 300 has not passed by **2026-10-15**. The paper is
  submission-blocked on the Zenodo deposit and the submission package, and this
  experiment is an enhancement to a framing decision that already has a defensible
  answer in Option A.

On stop: the partial record is committed, `docs/33`'s status lines are updated
again to say so, and no manuscript text depends on it — §VI-F does not exist and
is not created until stage 300 passes.

---

## 10. What is *not* pre-registered here

* Any rate, interval, or comparison against a matrix cell. §2 forbids it.
* Plan drift, and therefore the WS-1a restore. §1.1.
* Any second model, second prompt, or second provider.
* The manuscript prose. No §VI-F, no §I change, until stage 300 passes and the
  result is known.
