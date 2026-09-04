# The agent workload — design

**WS-1 Option B, task 1B.1.**

**Status.** §2 (WS-1a, attribution) is **built and verified** — see its own
status line and `reports/phase-report-ws1a-2026-09-04.md`. §§1 and 3–5
(WS-1b, the agent workload) are **design only; none of it is implemented.**

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

### The workstream is split in two

**§2 is not a prerequisite tucked inside this workstream; it is its own.** It
grew to eleven acceptance items, four of them proofs and one a manuscript
change, which is not a metric repair. Keeping it inside WS-1 would have hidden
a ledger schema change and a construct-validity threat inside a workload task.

| | scope | this document |
|---|---|---|
| **WS-1a · Attribution** | the execution-id repair, its four proofs, and the §VIII threat statement | **§2** |
| **WS-1b · The agent workload** | tools, planners, plan drift, collection | §§1, 3–5 |

**WS-1a blocked WS-1b entirely, and is now complete**, so WS-1b is unblocked
and not started. Recorded in `docs/26-journal-readiness-direction.md` §4 and §5
so the direction document does not drift from this one.

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
new identity function is needed.

**That buys identity, not attribution, and the difference is the whole of WS-1a.**
An earlier draft said §4 got its metric "for free". It does not. The fingerprint
answers *"are these the same mutation?"*; the metric also needs *"which execution
caused this row?"*, and the agent workload is precisely what breaks the existing
answer to the second question. §2.4 goes further and requires the execution id to
be **excluded** from `F(r)` — so the two identifiers are deliberately disjoint,
and keeping them so costs a ledger schema change, four proofs and a §VIII threat
statement.

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

**Status: WS-1a is complete.** It was its own workstream item and it landed
before any agent code, as required — it touches
`undetected_duplicate_applications`, a headline metric in `\cref{tab:outcomes}`
and in the B4 duplicate claim. The four proofs in §2.8 hold. Closing report:
`reports/phase-report-ws1a-2026-09-04.md`. WS-1b is unblocked.

### The design, in short

> An applied effect is attributed to an execution by a **harness-supplied
> execution id**, carried on `X-AEP-Execution-Id`, recorded in
> `applied_mutations`, and read by the analysis — falling back to `target` for
> any ledger collected before the column existed.
>
> It is **excluded from `F(r)`**, the provider exposes **no accessor keyed on
> it**, and it is **never an input to duplicate detection**. It is
> instrumentation, not a protocol capability.

**Why that key and not another.** It is the only one that satisfies all three
constraints at once:

| constraint | `target` | `client_reference` | execution id |
|---|---|---|---|
| attributes an execution that died before recording anything | yes | **no** | **yes** |
| survives two executions sharing a resource | **no** | yes | **yes** |
| present for all seven systems | yes | **no** | **yes** |

**The principle underneath it — two identifiers, two owners.** Identity and
attribution are different questions with different trust models, and every wrong
design in this section collapsed them into one:

> The **oracle** owns *identity* — "are these the same mutation?" — and must
> answer it **taking nothing from the caller**, because the caller is the system
> under measurement.
>
> The **analysis** owns *attribution* — "which execution caused this row?" — and
> may take it **from the harness**, because the harness is not under measurement.

The execution id is admissible precisely because it is the harness's and not the
protocol's: the system under test cannot read it back, condition on it, or vary
it to its advantage.

### How to read the rest of this section

| | |
|---|---|
| **the problem** | §2.1 why `target` attribution is sound today · §2.2 why the agent workload breaks it for every system |
| **the design** | §2.4 the repair · §2.5 the schema bump · §2.6 the §VIII threat · §2.9 the workload invariant |
| **the evidence** | §2.8 the four proofs · §2.10 what breaks if this lands late · §2.11 acceptance |
| **the record** | §2.0, §2.3, §2.7 — three designs that were written down and refuted |

**§§2.0, 2.3 and 2.7 are not the design.** They are kept because they are the
reason the design is what it is: each was refuted by the code rather than by
argument, and two of the three were caught by tests and comments that already
existed. A reader who wants only the answer can stop after §2.9. The subsection
numbering is unchanged because `experiments/mock_api/ledger.py`,
`experiments/harness/plan_invariant.py`, `experiments/analyze.py` and the proof
tests all cite these numbers.

### 2.0 REFUTED DESIGN 1 — the first version of this section named the wrong function

> **Superseded by §2.4.** Kept as the record of why the design is what it is.

The first draft of this document said the repair was to partition
`GroundTruthLedger.duplicate_groups()` on `client_reference`. **That was wrong,
and the error is recorded here rather than silently replaced**, because the
reasoning that produced it is a trap the next reader can fall into.

`duplicate_groups()` implements Definition 3 and groups by *fingerprint*. It is
the oracle's own classification and it is used by the mock API's tests and
consistency reporting. **It does not produce any number in the manuscript.** The
published metric comes from a different path entirely:

```
analyze.py:255   is_undetected_duplicate = applied_effects > 1 and outcome != DECLARED_AMBIGUOUS
analyze.py:526   applied_effects = effects[target]
analyze.py:199   oracle_effects_by_target:  SELECT target, COUNT(*) ... GROUP BY target
```

The metric attributes ledger rows to executions **by `target`** — never by
fingerprint, never by `client_reference`. Partitioning `duplicate_groups()`
would have left the paper's numbers untouched while appearing to repair them.

### 2.1 Why target attribution is sound today

`target` is `account-{execution_id}`: **it encodes the execution**. Each
execution owns its resource — the *"distinct targets"* decision in
`experiments/harness/workload.py` — so counting rows per target is counting rows
per execution, and `applied_effects > 1` means one intent was applied more than
once.

Measured on the frozen 432-run matrix rather than assumed:

```
applied rows                       : 4782
targets carrying >1 row            : 1401
  ...of which >1 client_reference  : 0
```

1401 targets carry more than one row — those are the real duplicates — and **not
one carries rows from two distinct intents**. Per-execution attribution by target
is sound on all existing data.

### 2.2 Why the agent workload breaks it, for every system

The agent workload removes exactly the property that makes it sound. A planner
that re-plans onto a target another execution used makes `effects[target]`
count rows from *both*, and the earlier execution is flagged as an undetected
duplicate although the protocol applied it exactly once.

**This is worse than a `client_reference` problem, and it is worse in a specific
way.** `client_reference` is NULL for five of seven systems, so a repair keyed on
it would have been partial. `target` is populated for **all seven**, so
target-keyed attribution breaks for all seven — including the baselines, and
including the B4 duplicate rate the paper leans on.

### 2.3 REFUTED DESIGN 2 — the repair that was chosen first, and why it fails

> **Superseded by §2.4.** Kept as the record of why the design is what it is,
> and because its *proof* would have passed while proving nothing.

**Attributing by the caller reference was chosen and then rejected.** It is
recorded because the reason it fails is the reason the design below is what it
is, and because a reader who reaches for the obvious key should find out here
rather than after collection.

The proposal was: emit the caller reference on the harness's per-execution event
record, attribute applied effects by it, and fall back to target where there is
none. `experiments/harness/reconcile.py:7-13` had already considered and
rejected exactly this:

> **How an effect is attributed to an execution.** By `target`. The workload
> gives every execution its own resource (`account-<execution_id>`), so an
> applied mutation names the execution that caused it **without any cooperation
> from the protocol** — which matters, because the executions this harness cares
> most about are the ones **whose worker died before it could record anything**.
> A `client_reference` would only attribute the effects of executions that lived
> long enough to resolve […]

The fallback appears to cover that case, and today it does: a worker `SIGKILL`ed
before recording anything is still attributed, because its target encodes its
execution id. **The agent workload is exactly what removes that.** Under target
reuse, an execution that died before recording has

* no harness-recorded caller reference — it died first — and
* a target it may share with another execution,

so it is attributable by **neither**. Those are the executions every crash regime
in this paper is built on.

**Worse, the proof would have passed anyway.** On the frozen matrix targets are
still unique, so the fallback fires on every row and the caller-reference path is
never exercised. A byte-identical result would have been produced by code that
never ran the branch it was there to validate. **A vacuous proof is worse than no
proof**, and catching that is why the design changed.

### 2.4 THE DESIGN — a protocol-independent execution id in the ledger

> **This is the design that was built.** Summarised at the head of §2; stated
> in full here.

**The mock API records the harness's planned-execution identifier on every
applied mutation, and the analysis attributes effects by it.**

It is the only key that satisfies both constraints at once:

| constraint | `target` | `client_reference` | execution id |
|---|---|---|---|
| attributes an execution that died before recording anything | yes | **no** | **yes** |
| survives two executions sharing a resource | **no** | yes | **yes** |
| present for all seven systems | yes | **no** | **yes** |

It requires no cooperation from the system under test — the harness supplies it
on the call, exactly as it supplies the target today — so it keeps the property
`reconcile.py` was protecting while surviving the property the agent workload
removes.

**It must not enter the fingerprint.** `F(r)` is computed over the endpoint,
target and the endpoint's declared identity fields
(`experiments/mock_api/fingerprint.py`, Definition 1). If the execution id
entered it, every call would acquire a distinct identity, no two mutations would
ever share a fingerprint, and the duplicate metric would read zero everywhere.
The id is a recorded column, never an identity field.

### 2.5 The `LEDGER_SCHEMA_VERSION` bump, and why the frozen matrix is untouched

Adding a column to `applied_mutations` bumps `LEDGER_SCHEMA_VERSION`, which the
ledger states is *"a statement that previously collected result databases are not
comparable to new ones"*. That statement is about **collection**, and the
question here is about **analysis**: are the published numbers, which are derived
by re-reading those frozen databases, affected?

**They are not, and the reason is checkable rather than argued.** The analysis
never opens a frozen ledger through `GroundTruthLedger` — `analyze.py:199` says
so and gives the reason (*"that class is part of the apparatus under test's
environment"*). Its entire read surface on a frozen database is **one read-only
connection issuing one statement**:

```
SELECT target, COUNT(*) FROM applied_mutations GROUP BY target
```

Two consequences follow, and each is a proof obligation in §2.7 rather than an
assertion here:

1. **`LEDGER_SCHEMA_VERSION` is never consulted by the analysis.** It is read in
   `experiments/mock_api/ledger.py` and nowhere else; `analyze.py` contains no
   reference to `ledger_meta` or to a schema version. A bump is therefore
   invisible to every published number.
2. **The one statement names only `target`**, a column that exists unchanged in
   the frozen schema. A frozen database lacking the new column is read exactly as
   it is read today, because nothing in the statement mentions it.

The new column is consulted only where it exists. Frozen databases are read under
the old shape by a statement that predates the change, and are not migrated,
rewritten or re-derived.

### 2.6 Baselines carrying measurement metadata — a real threat, and §VIII must say so

Five of the seven systems are *defined* not to send a caller reference
(`experiments/baselines/contract.py`, `sends_client_reference=False`). Making
them send an execution id is a change to what a baseline transmits, and that is a
construct-validity threat to the baseline comparison. **It belongs in §VIII as a
stated threat, not in a design document where a reviewer will not find it.**

The precise claim, which §VIII should carry in these terms:

> The execution id is **harness instrumentation, not a protocol capability**. It
> is supplied by the measurement harness on every call for every system, exactly
> as the target resource already is; it is recorded by the provider and **never
> returned to the caller, never queryable by it, and never used by the provider
> to decide whether a mutation is a repeat**. No system under test can read it
> back, condition on it, or deduplicate with it.

That distinction is what separates it from `client_reference`, and the separation
is structural rather than stipulated: `client_reference` **is** queryable —
`ledger.applications_for_client_reference()` exists and `service.py:269` calls it
to serve read-backs under `CALLER_REFERENCE` keying. That accessor is what makes
a caller reference a *capability*. **The execution id gets no such accessor**, and
its absence is the thing to test.

**What remains a genuine threat, and should be conceded rather than argued away:**
the baselines now transmit a field they would not transmit in a real deployment.
It gives them no ability they lacked — the paper's premise is providers *without*
idempotency keys, and a write-only field the provider ignores for identity is not
one — but a reviewer is entitled to note that the baselines under the agent
workload are not byte-identical to the baselines elsewhere in the paper. The
honest position is that the field is inert by construction and that its inertness
is enforced by test.

### 2.7 REFUTED DESIGN 3 — the secondary repair was also a wrong design

> **Not implemented.** `duplicate_groups()` still groups on fingerprint
> alone, which is correct. Kept as the record of why.

**This section previously said `duplicate_groups()` should be partitioned on
`client_reference`.** It should not, and the reason is recorded here rather than
replaced, as with §2.0 and §2.3.

The argument was that under an agent workload a fingerprint group becomes
ambiguous between "one intent applied twice" and "two intents chose the same
mutation", so grouping should include the caller reference. Implementing it broke
`test_a_client_reference_is_never_an_input_to_duplicate_detection`, which exists
for a reason that defeats the proposal outright:

> Two applications of the same mutation carrying *different* client references
> are still one duplicate — otherwise a protocol could hide its duplicates simply
> by minting a fresh reference per attempt.

**The caller reference is protocol-generated.** AEP sends its own
`binding.request_fingerprint`. Partitioning the oracle's duplicate
classification on it would let the system under test decide how many duplicates
the oracle reports about it — the opposite of oracle independence, and a defect
the ledger's design already anticipated.

**The oracle must decide identity without trusting the caller at all.** That is
what Definition 3 is for, and it is why `duplicate_groups()` is left grouping on
fingerprint alone.

**The intent-versus-mutation distinction belongs to the analysis**, which
attributes by the harness-supplied `execution_id` — instrumentation the system
under test does not choose, cannot read back, and cannot vary to its advantage
(§2.4, §2.6). Two identifiers, two owners: the oracle owns *identity* and takes
nothing from the caller; the analysis owns *attribution* and takes it from the
harness. Collapsing them into one is what each of the three wrong designs in
this section did, in a different direction each time.

`duplicate_groups()` now carries this reasoning in its docstring, so it is not
re-derived by the next reader.

That partition is bounded by a structural fact. `sends_client_reference` is a
declared per-system capability in `experiments/baselines/contract.py`, and across
all seven systems it coincides **exactly** with `can_declare_ambiguity`:

| system | `can_declare_ambiguity` | `sends_client_reference` |
|---|---|---|
| `AEP_FULL` | True | True |
| `B3_INTENT_NO_BARRIER` | True | True |
| `B0_NAIVE_RETRY` | False | False |
| `B1_LEASE_ONLY` | False | False |
| `B2_CAS_ONLY` | False | False |
| `B4_DURABLE_WORKFLOW` | False | False |
| `B4B_DURABLE_WORKFLOW_AT_MOST_ONCE` | False | False |

**That coincidence is not luck.** Plan drift is defined as re-planning after a
declared ambiguity (§4.2), so it can only occur in a system that can declare one
— and the discriminator it needs exists in exactly those systems. Both follow
from having a pre-dispatch intent record the caller can name.

### 2.8 The proofs

None is asserted; each has a test. **§2.3 is the reason each is stated as
something to falsify rather than to confirm** — the proof that was nearly shipped
would have passed without exercising the code it existed to validate.

**Proof 1 — the frozen numbers do not move.** Re-running the analysis over the
frozen 432-run matrix produces **byte-identical** duplicate numbers before and
after the repair. **This proof is only available while the frozen data is the
only data**: once agent cells exist, a reader can no longer distinguish "the
repair changed nothing" from "the repair changed nothing on the cells that
predate it".

*And it must be shown non-vacuous.* On frozen databases the new column does not
exist, so byte-identity there demonstrates only that the fallback is intact. The
test must therefore be paired with a constructed fixture in which two executions
share a target, where old and new attribution **disagree** — proving the new path
is reached and does something. A test that only ever exercises the fallback is
the §2.3 mistake repeated.

**Proof 2 — `config_digest` is unaffected.** Every frozen run's recorded
`config_digest` is unchanged, because the execution id is supplied on the call
and recorded by the provider; it is not a `RunConfig` field
(`docs/31-transmission-event.md` §4).

**Proof 3 — the schema bump does not reach the analysis.** Two checkable claims
from §2.5: `analyze.py` contains no reference to `ledger_meta` or to a schema
version, and on a ledger *without* the column its read surface is a `PRAGMA
table_info` probe plus the unchanged `SELECT target, COUNT(*) FROM
applied_mutations GROUP BY target` — the new column is never named. Both are
assertable directly against the source, and both should be, because "we did not
change how frozen data is read" is exactly the kind of claim that rots silently.

*(The probe is what the earlier wording missed: attributing by execution id
requires asking whether the column exists, so the read surface is two statements
rather than one. The claim that matters — a frozen ledger is read exactly as
before — is unchanged.)*

**Proof 4 — the execution id is inert.** It never enters `F(r)`; the provider
exposes no accessor keyed on it, in contrast to
`ledger.applications_for_client_reference()`; and no system under test can read
it back. This is what §2.6 asks §VIII to claim, so it is what a test must pin.

### 2.9 The workload invariant

> **Invariant.** The planner may emit a tool call whose fingerprint equals one it
> has already emitted **only** in response to a step whose declared outcome was
> `PERMANENTLY_AMBIGUOUS`.

Under this invariant a repeated fingerprint can only arise where an ambiguity was
declared, so only in a system with `can_declare_ambiguity=True`, so only where a
caller reference is present and §2.4's primary path applies. For the other five
systems fingerprints and targets stay distinct exactly as they are today.

The invariant is checkable from the recorded plan and is asserted rather than
trusted.

### 2.10 What breaks if this lands late

* **Collected agent cells would be unanalysable.** The rows are recorded, but the
  attribution would be made by code that cannot tell the two cases apart, and
  re-running the analysis later is not equivalent to having collected under a
  checked invariant.
* **Proof 1 becomes impossible.** It is provable now because every frozen target
  carries one intent. Once agent cells are in the tree the comparison is against
  numbers already produced under the new rule.
* **The B4 duplicate claim silently changes population.** B4 duplicates at the
  highest rate in the study and that is a load-bearing comparison. Target-keyed
  attribution breaking for baselines (§2.2) is exactly what would corrupt it.

### 2.11 Acceptance

1. `applied_mutations` carries a harness-supplied execution id, and
   `LEDGER_SCHEMA_VERSION` is bumped (§2.4, §2.5).
2. The analysis attributes applied effects by that id, falling back to `target`
   for databases that predate the column.
3. The execution id is excluded from `F(r)` and from every endpoint's identity
   fields (§2.4).
4. No provider accessor is keyed on the execution id (§2.6).
5. `duplicate_groups()` partitions on `client_reference` (§2.7).
6. The §2.9 invariant is asserted in code, not assumed.
7. **Proof 1** — frozen duplicate numbers byte-identical — has a test, *and* a
   paired fixture test in which old and new attribution disagree, so Proof 1 is
   shown non-vacuous.
8. **Proof 2** — `config_digest` unchanged — has a test.
9. **Proof 3** — the analysis reads no schema version and issues one statement —
   has a test.
10. **Proof 4** — the execution id is inert — has a test.
11. **§VIII carries the baseline-fidelity threat** in the terms of §2.6. This is
    a manuscript obligation, not a code one, and the workstream is not complete
    without it.

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
2. Planner interface and the scripted planner (§3), with the §2.9 invariant
   asserted.
3. Pre-registration (§4.4), committed before any agent cell is collected.
4. Collection, then the local-model arm as a secondary.

**Nothing in this document is implemented.** No manuscript text depends on it,
and §VI-F does not exist yet.
