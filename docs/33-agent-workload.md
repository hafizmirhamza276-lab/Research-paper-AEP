# The agent workload — design

**WS-1 Option B, task 1B.1. Design only; nothing here is implemented.**

`docs/26-journal-readiness-direction.md` §4 names this file `27-agent-workload.md`;
that number was taken by `27-measurement-host.md` before this was written, so it
is **33**. Nothing else about the task changes.

---

## 0. The decision, and what this document is

**Option B is decided: the agent workload goes ahead.** This document is its
design. The A-versus-B question is closed and is not reopened below; where the
comparison to Option A appears it is to record what B costs, not to reconsider
it.

The blocker being answered is **A1**:

> **Title/framing says "Autonomous Agents"; the evaluation contains no agent.**
> "agent" occurs 0 times in `03-model`, `04-protocol`, `05-implementation`,
> `06-evaluation`, `09-artifact`; no LLM anywhere in `experiments/`. […] A
> reviewer's first note will be "the framing is decorative".

Option B makes the agent load-bearing: a planner chooses which non-idempotent
tool to call and with what arguments, drives the existing harness, and is
measured on the existing three outcomes plus one new one.

**§2 is a prerequisite and blocks all agent code.** It is not part of the
workload; it is a repair to an existing metric that the workload would otherwise
silently change. Read it before writing anything.

---

## 1. The workload

### 1.1 What changes, and what deliberately does not

Today `experiments/harness/workload.py` derives every execution from
`(run_id, seed, worker_index, execution_index)`: the identifier, the target, the
amount, and whether it was selected to crash. The plan is fixed before the run
starts and is *recomputable* — a worker respawned after `SIGKILL` reconstructs
exactly the plan the dead one was working through.

The agent workload changes **who decides the next action** and nothing else. It
does not change the connector, the vault, the barrier, the recovery service, the
oracle, or the metrics. The system under test is unchanged; only the caller
above it is.

> **The replay property is not negotiable.** A worker killed mid-run and
> respawned must reconstruct the same plan, or the crash regimes stop measuring
> what they measure. Every planner in §3 is therefore required to be a pure
> function of recorded inputs. §3.3 is where that requirement is discharged, and
> it is the single hardest constraint in this design.

### 1.2 The tool schema

Three tools, one per existing endpoint. The mapping is deliberately 1:1 so that
the agent workload reuses the capability-class axis the paper already has rather
than introducing a second one.

| tool | endpoint | reconciliation capability | what a read-back can settle |
|---|---|---|---|
| `charge_card` | `payments` | `AUTHORITATIVE_READBACK` | applied *and* not-applied |
| `send_notification` | `notifications` | `POSITIVE_ONLY_READBACK` | applied only; silence is not evidence |
| `post_ledger_entry` | `ledger_postings` | `NO_READBACK` | nothing |

Each tool takes the same argument shape, because the mock API fingerprints on
the same fields for all three (`identity_fields: [action, amount_minor]`, from
the run's `mock-api.yaml`):

```
tool_call := {
    tool:          "charge_card" | "send_notification" | "post_ledger_entry",
    target:        string,     # the resource the mutation applies to
    action:        string,     # identity field
    amount_minor:  integer     # identity field; minor units, never a float
}
```

`target`, `action` and `amount_minor` are exactly the fields that already enter
the oracle's fingerprint (`experiments/mock_api/fingerprint.py`, Definition 1):

```
F(r) = SHA-256( C({ v, method, endpoint, operation, operation_version,
                    target, identity: {action, amount_minor} }) )
```

**This is the load-bearing property of the schema.** Because the agent's whole
action space is inside the fingerprint, two actions are the same mutation *to the
oracle* exactly when the agent chose the same tool, target, action and amount. No
new identity function is needed, and §4 gets its metric for free.

### 1.3 The modelling decision that has to change

`workload.py` states it plainly:

> **Distinct targets.** Each execution mutates its own resource. […] two
> executions can then never share a fingerprint, so every duplicate group the
> oracle reports is a *duplicated effect on one intended mutation* rather than
> two intended mutations that happened to look alike.

**An agent workload must break this, because re-planning a duplicate action is
the phenomenon being measured.** If targets stay distinct, plan drift is
unobservable by construction.

Breaking it changes what an existing headline metric means. **That is §2, and it
is a prerequisite rather than a detail of this section.**

### 1.4 Shape of a run

An agent run is a **sequence** of decisions, not a fixed list. That is the
substantive difference from the current workload, and it means
`executions_per_run > 1` for every agent cell — the crash regimes that use one
execution per run cannot exercise re-planning at all, because there is no
"after" in which to re-plan.

```
observation_0 → planner → tool_call_0 → protocol → outcome_0
observation_1 → planner → tool_call_1 → protocol → outcome_1
   ...                                             (until STOP or budget)
```

The **observation** is what a real caller would have: the protocol's own declared
result for each prior step, and nothing else. Specifically the
`ReconciliationOutcome` (`CONFIRMED`, `REFUTED`, `PERMANENTLY_AMBIGUOUS`) plus
the step's declared status. **The planner never sees the oracle.** If it could,
plan drift would measure the oracle rather than the protocol, and the whole
experiment would be circular. This is the second non-negotiable constraint after
replayability.

---

## 2. Prerequisite workstream: the duplicate-metric repair

**This is its own workstream item and it lands before any agent code.** It
touches `undetected_duplicate_applications`, which is a headline metric in
`\cref{tab:outcomes}` and in the B4 duplicate claim. Nothing in §§1, 3–5 may be
implemented until it is done and verified.

### 2.1 What breaks

Once two *different* intents can share a fingerprint (§1.3), a duplicate group is
ambiguous:

* one intent applied twice — the protocol failed, which is what the metric claims
  to count; or
* two intents that chose the same mutation — the *planner* acted twice, which is
  not a protocol failure at all.

A `GROUP BY fingerprint` cannot tell these apart. Left unrepaired, the agent
workload would inflate `undetected_duplicate_applications` with planner
behaviour and the paper's duplicate numbers would stop meaning what they say.

### 2.2 The repair

`applied_mutations` already records what is needed
(`experiments/mock_api/ledger.py`): `fingerprint`, `client_reference`, `call_id`,
`target`, `endpoint`. Partition each duplicate group by `client_reference`:

| group shape | meaning | column |
|---|---|---|
| >1 row, **one** `client_reference` | one intent applied more than once | `undetected_duplicate_applications` — unchanged meaning |
| >1 row, **several** `client_reference`s | distinct intents, same mutation | **plan drift, applied** (§4) |

No oracle change is required; this is a classification change in the analysis.

### 2.3 The repair is partial, and the boundary is structural

**`client_reference` is not populated by every system, and that is by design.**
Measured across the frozen 432-run matrix:

```
total applied rows            : 4782
NULL client_reference         : 4171 (87.2%)
duplicate groups              : 1401
duplicate groups touching NULL: 1401
```

`experiments/baselines/contract.py` declares why: `sends_client_reference` is a
per-system capability, and the baselines pass `client_reference=None`
deliberately. Across all seven systems it takes exactly two values, and it
**coincides exactly with `can_declare_ambiguity`**:

| system | `can_declare_ambiguity` | `sends_client_reference` |
|---|---|---|
| `AEP_FULL` | True | True |
| `B3_INTENT_NO_BARRIER` | True | True |
| `B0_NAIVE_RETRY` | False | False |
| `B1_LEASE_ONLY` | False | False |
| `B2_CAS_ONLY` | False | False |
| `B4_DURABLE_WORKFLOW` | False | False |
| `B4B_DURABLE_WORKFLOW_AT_MOST_ONCE` | False | False |

**That coincidence is not luck and it resolves the problem.** Plan drift is
*defined* as re-planning after a declared ambiguity (§4.2), so it can only occur
in a system that can declare one. The discriminator the metric needs
(`client_reference`) exists in exactly the systems where the metric is
meaningful. Both follow from the same underlying property: a pre-dispatch intent
record the caller can name.

The consequence for the five systems that send no reference is therefore **not**
that their duplicate metric is unrepairable. It is that they never generate the
ambiguous case, provided the workload guarantees it — which is §2.4.

### 2.4 The workload invariant that makes the repair sufficient

> **Invariant.** The planner may emit a tool call whose fingerprint equals one it
> has already emitted **only** in response to a step whose declared outcome was
> `PERMANENTLY_AMBIGUOUS`.

Under this invariant a repeated fingerprint can only arise where an ambiguity was
declared, so it can only arise in a system with `can_declare_ambiguity=True`, so
it can only arise where `client_reference` is populated and the partition of §2.2
applies. For the other five systems, fingerprints remain distinct exactly as they
are today and their duplicate numbers keep their current meaning with no change
at all.

The invariant is checkable from the recorded plan and should be asserted in the
harness rather than trusted.

### 2.5 Effect on existing frozen cells: none, and this is measured

The metric must mean the same thing before and after, or every prior number
changes meaning. Checked against the frozen matrix rather than argued:

```
runs scanned            : 432
runs with a duplicate   : 185
duplicate groups        : 1401
groups w/ >1 reference  : 0
```

**No duplicate group in any frozen run has more than one `client_reference`**, so
the partition of §2.2 moves nothing: every existing group stays in
`undetected_duplicate_applications`, and every published duplicate number is
byte-identical after the repair. That is the property that makes this safe to
land, and it is why the repair must land *first* — proving it on frozen data is
only possible while the frozen data is the only data.

### 2.6 What breaks if this lands late

* **Collected agent cells would be unanalysable.** A run collected before the
  partition exists records the rows, but the classification would be made by
  code that cannot distinguish the two cases, and re-running the analysis later
  is not equivalent to having collected under a checked invariant (§2.4).
* **The frozen no-op proof becomes impossible.** §2.5 is provable now because
  every existing group has one reference. Once agent cells are in the tree, a
  reader can no longer distinguish "the repair changed nothing" from "the repair
  changed nothing *on the cells that predate it*", and the byte-identical check
  in `scripts/check_paper_numbers.py` would be comparing against numbers already
  produced under the new rule.
* **The B4 duplicate claim silently changes population.** B4 duplicates at the
  highest rate in the study and that is a load-bearing comparison. If agent cells
  enter `per-cell-metrics.csv` before the invariant is enforced, that rate mixes
  protocol duplicates with planner repetitions and the paper's sharpest
  duplicate sentence stops being true.

### 2.7 Acceptance for this item

1. Duplicate-group classification partitions on `client_reference`.
2. The §2.4 invariant is asserted in the harness, not assumed.
3. Re-running the analysis over the frozen matrix reproduces every duplicate
   number **byte-identically** — the check `scripts/check_paper_numbers.py`
   already performs for generated artifacts.
4. A test pins the two-case classification against a constructed fixture with
   both shapes, since the frozen data contains only one of them.

---

## 3. Three planners behind one interface

### 3.1 The interface

```
class Planner(Protocol):
    def next_action(self, observation: Observation) -> ToolCall | Stop: ...
```

One interface, three implementations, selected per run and recorded in the
`environment` block:

| planner | role | determinism |
|---|---|---|
| **scripted** | **primary — every paper number** | seeded RNG, pure function of recorded inputs |
| **local open-weights** | secondary — an existence proof | pinned weights, fixed seed, greedy decode, logged prompts and responses |
| **hosted API** | optional — not used for any claim | none available |

### 3.2 Why the scripted planner is primary

This is a reproducibility argument, not a convenience one, and it follows
directly from how the rest of this project already works.

**Everything else in this artifact is pinned or regenerated.** The Redis image is
pinned by digest and cross-checked in three files
(`tests/test_artifact_reproducibility.py`). Python is upper-bounded on purpose
because *"the artifact is evidenced on CPython 3.13 only"*. Every number in the
manuscript is generated from CSVs and re-derived byte-for-byte by
`scripts/check_paper_numbers.py`; the `paper/generated/**` tree is never
hand-edited. Analysis products are compared byte-for-byte against what is
committed. Run configurations are digested, and
`docs/32-config-digest-verifiability.md` exists because a digest that cannot be
verified is not a control.

**A hosted API breaks every one of those properties at once.** It is a remote,
versioned, silently-updated dependency with no digest, no pin, and no guarantee
that the same prompt returns the same completion tomorrow. A result computed
through one cannot be regenerated, only *re-observed* — and if it disagrees with
the recorded run there is no way to tell whether the protocol, the harness, or
the vendor changed. That is precisely the failure mode this project has spent
phases eliminating elsewhere. **No number that reaches the manuscript may come
from it.**

A local open-weights model is much better — weights pin by digest, a fixed seed
and greedy decoding make sampling deterministic — but it is not free either.
Determinism across *hardware* is not guaranteed for floating-point kernels; a
different GPU, driver, or kernel-selection heuristic can change a logit ordering
and therefore a token. The artifact would acquire a reproducibility caveat it
does not currently have, and it would be the only one.

**The scripted planner has none of these problems and loses less than it looks.**
It is a nondeterministic *policy* with a seeded RNG: it makes genuine choices —
which tool, which arguments, whether to re-plan after an ambiguous result — and
those choices vary run to run, but they are a pure function of the seed. It
replays after `SIGKILL`, it regenerates byte-for-byte, and it is diffable.

The honest statement of what this costs is in §5.2: a scripted planner is not an
LLM, and the paper must not imply that it is.

### 3.3 Determinism controls

The replay requirement of §1.1 applies to all three planners.

* **Scripted.** The RNG is seeded from `(run_id, seed, worker_index, step_index)`
  exactly as `workload.py` seeds today, so no global generator is consulted and a
  respawned worker recomputes the same decision. This is the existing discipline,
  unchanged.
* **Model-backed (local or hosted).** A model call cannot be recomputed from a
  seed alone, so replay is served by a **transcript**: every call records the full
  prompt, the sampling parameters, the model digest, and the completion, keyed by
  `(run_id, worker_index, step_index)`. A respawned worker in replay mode reads
  the transcript rather than calling the model. WS-1's acceptance criterion
  already requires this — *"LLM planner run is reproducible from recorded
  prompts/responses (log every call)"* — and it is what makes a model-backed run
  auditable after the fact even though it is not regenerable from a seed.

**A transcript is weaker evidence than a seed**, and the distinction should be
stated wherever a model-backed number appears: a seed lets a reader *recompute*
the run, a transcript only lets them *check* it against what was recorded.

### 3.4 The config-digest constraint

`docs/31-transmission-event.md` §4 records that `RunConfig._body()` iterates every
dataclass field into `config_digest`, so **adding a field changes the digest of
every run ever collected** — 150 of the 432 frozen matrix runs already fail that
check for exactly this reason. The planner selection must therefore follow the
route Phase 8.2, Phase 10 and Phase 13 all used: recorded in the `environment`
block, which `echo()` writes and `config_digest` excludes.

This is a design constraint the project discovered the hard way, and it is
cheaper to honour than to rediscover.

---

## 4. The new outcome: plan drift

### 4.1 The question

> After the protocol tells the caller that a mutation's outcome is unknowable,
> does the caller go on to perform that mutation again?

This is the outcome the paper's framing implies and its evaluation currently
cannot reach. Declared ambiguity is only useful if a caller *does something
different* with it; today the paper measures that the protocol declares
ambiguity, not that declaring it changes any downstream behaviour.

### 4.2 Definition

> **Definition (plan drift).** Let `s` be a step whose protocol-declared
> reconciliation outcome is `PERMANENTLY_AMBIGUOUS`, with request fingerprint
> `F(s)` and caller reference `c(s)`. The run exhibits **plan drift at `s`** iff
> the planner subsequently emits a tool call `s'` with `F(s') = F(s)` and
> `c(s') ≠ c(s)`.

Three things this definition is built to do:

* **`F(s') = F(s)`** — same tool, target, action and amount, so the oracle already
  considers them the same mutation (§1.2).
* **`c(s') ≠ c(s)`** — a *new intent*, not a retry of the old one. This is the
  discriminator §2 installs.
* **conditioned on `PERMANENTLY_AMBIGUOUS`** — drift after a `CONFIRMED` or
  `REFUTED` outcome is a planner acting on good information and is a different
  phenomenon. It should be counted, but separately, as a control.

**Scope.** By §2.3 the metric is defined only for `AEP_FULL` and
`B3_INTENT_NO_BARRIER`. The other five systems cannot declare ambiguity, so
they have no ambiguous step to drift from; their agent-workload cells contribute
the existing three outcomes and no drift figure. This is a property of the
metric, not a gap in the collection, and the paper should say so rather than
leaving a blank column unexplained.

### 4.3 Scoring it

Building on §2.2, with the third row being the one that carries the contrast:

| observation | metric |
|---|---|
| >1 row, several `client_reference`s | **plan drift, applied** |
| planner emitted `s'`, no second ledger row | **plan drift, withheld** |
| >1 row, one `client_reference` | `undetected_duplicate_applications` |

A planner can drift and the protocol can still refuse to dispatch. Separating
"the agent re-planned a duplicate" from "a duplicate reached the provider" is the
whole contrast between AEP-full and B3 under this workload.

**Denominator.** Plan drift is a rate over *ambiguous steps*, not over runs or
executions: a run with no ambiguous step cannot drift and must not dilute the
rate. This is the same discipline as §VI's *"the unwanted-applied-effect rate is
a rate over executions, not a count and not a rate over runs"*.

### 4.4 What must be pre-registered

Under this project's rules a new metric arrives with its criterion fixed in
advance. At minimum: the drift-rate difference between AEP-full and B3 that would
count as a real difference; the direction expected; the treatment of runs with
zero ambiguous steps; and — given Phase 13 — the between-session spread that
would make the comparison inconclusive. `docs/26` §3 Rule 5 applies unchanged.

**One prediction should be registered explicitly because it is uncomfortable:**
under `NO_READBACK` there may be *no difference at all* between the two arms.
Both declare ambiguity, both hand the planner the same observation, and the
planner is the same code. If the drift rate is identical, that is a finding about
where the protocol's value sits — in what reached the provider, not in what the
caller does next — and it must not be quietly reframed after the fact.

---

## 5. What this lets the paper claim

### 5.1 What it can claim that it currently cannot

* **That the evaluation contains an agent.** A1's literal complaint — no agent
  anywhere in `experiments/` — stops being true, and the title stops being
  decorative. This is the point of the workstream.
* **That declared ambiguity has a measurable downstream consequence.** Today
  ambiguity is an output; under this workload it is an *input* to a caller whose
  behaviour is measured. That is a claim about the protocol's usefulness, not
  only its correctness, and the paper currently has no evidence for it.
* **That the caller chooses its own arguments.** The distinct-target
  simplification is what makes the current workload obviously not agentic. A
  planner selecting tool, target and amount exercises the request-binding and
  fingerprint machinery over an input distribution the harness does not control.
* **A direct comparison to agent-framework retry semantics** rather than a
  motivational one — WS-8 task 8.3 is explicitly conditioned on this choice.

### 5.2 What it still cannot claim

Stated now, so the workstream is costed honestly rather than at the point where a
reviewer asks.

* **Nothing about real LLM agents, if the numbers come from the scripted
  planner.** A seeded policy is not a language model. Every paper number would
  come from a program the authors wrote, and the strongest available phrasing is
  *"a planner that re-plans under ambiguity"*, not *"an agent"*. The local-model
  arm is an existence proof that the interface accepts a real model; **it is not a
  second sample of the same population**, and pooling the two would be
  indefensible.
* **Nothing about prompt sensitivity, model scale, or planner quality.** One local
  model at one size with one prompt is one point. Whether a larger model drifts
  less is a question this design cannot answer and should not appear to.
* **Nothing about real tool ecosystems.** The three tools are the three existing
  mock endpoints. Their capability classes are the paper's own construct, chosen
  to span the reconciliation axis, and a real deployment's tools would not
  partition so cleanly.
* **No drift comparison against the baselines.** §4.2's scope restriction means
  B0, B1, B2, B4 and B4b have no drift figure. The paper cannot say a durable
  workflow engine drifts more or less than AEP-full, because the metric is
  undefined for it.
* **Nothing that survives the single-host limitation.** Every measurement is still
  from one machine (§VIII-C), and an agent workload does not change that.
* **No causal claim about *why* a planner drifts.** The design measures whether it
  does. Attributing drift to the observation's content rather than to the policy
  would need a manipulation this design does not contain.

---

## 6. Order of work

1. **§2, the duplicate-metric repair.** Blocks everything else. Ends with the
   frozen matrix reproducing byte-identically.
2. Planner interface and the scripted planner (§3), with the §2.4 invariant
   asserted.
3. Pre-registration (§4.4), committed before any agent cell is collected.
4. Collection, then the local-model arm as a secondary.

**Nothing in this document is implemented.** No manuscript text depends on it,
and §VI-F does not exist yet.
