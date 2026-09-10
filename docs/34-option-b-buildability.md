# Option B: is docs/33 still buildable as designed?

**Read-only assessment, 2026-09-10.** No code, no paper edit, no collection. A
WS-5 collection was running on this host throughout; nothing in this pass
touched Docker, the test suite, or the working tree.

**This report makes no recommendation.** It states what is there and what it
would take.

---

## 1. What docs/33 specifies, and what was built

docs/33 splits into two workstreams, and only one of them was ever executed.

| | scope | doc | status |
|---|---|---|---|
| **WS-1a · Attribution** | the execution-id repair, four proofs, a §VIII threat statement | §2 | **built, verified, then reverted** |
| **WS-1b · The agent workload** | tools, planners, plan drift, collection | §§1, 3–5 | **design only; never implemented** |

### 1.1 The agent workload (§1) — design only

Three tools, 1:1 onto the three existing endpoints, chosen so the agent reuses
the paper's existing capability axis rather than adding a second one:
`charge_card` → `payments` (AUTHORITATIVE), `send_notification` →
`notifications` (POSITIVE_ONLY), `post_ledger_entry` → `ledger_postings`
(NO_READBACK). Every tool takes the same argument shape —
`{tool, target, action, amount_minor}` — because those are exactly the fields
already inside the oracle's fingerprint. That is the schema's load-bearing
property: the agent's whole action space sits inside `F(r)`, so no new identity
function is needed.

Two constraints are declared non-negotiable. **Replay:** a worker killed
mid-run and respawned must reconstruct the same plan, so every planner must be a
pure function of recorded inputs. **The planner never sees the oracle:** its
observation is the protocol's own declared result and nothing else, or plan
drift measures the oracle and the experiment is circular.

One modelling decision must be broken deliberately: `workload.py`'s *distinct
targets* rule. If each execution keeps its own resource, plan drift is
unobservable by construction — which is what makes §2 a prerequisite rather than
a detail.

### 1.2 The three planners (§3) — design only

One interface, `next_action(observation) -> ToolCall | Stop`, three
implementations: **scripted** (primary, every paper number, seeded RNG),
**local open-weights** (secondary, an existence proof, pinned weights and a
transcript), **hosted API** (optional, no number may come from it). The argument
for scripted-as-primary is reproducibility, not convenience, and docs/33 states
plainly what it costs: a seeded policy is not a language model, and the paper
would have to say "a planner that re-plans under ambiguity", not "an agent".

### 1.3 Plan drift (§4) — design only

> **Definition.** Let `s` be a step whose declared outcome is
> `PERMANENTLY_AMBIGUOUS`, with fingerprint `F(s)` and caller reference `c(s)`.
> The run drifts at `s` iff the planner later emits `s'` with `F(s') = F(s)` and
> `c(s') ≠ c(s)`.

Scored three ways, the third carrying the contrast: >1 ledger row with several
client references = **drift, applied**; planner emitted `s'` with no second row =
**drift, withheld**; >1 row with one client reference = the existing
`undetected_duplicate_applications`. The denominator is *ambiguous steps*, not
runs or executions.

### 1.4 What was built (§2) — and is now gone

WS-1a landed and was verified (`reports/phase-report-ws1a-2026-09-04.md`): a
harness-supplied execution id on `X-AEP-Execution-Id`, recorded in
`applied_mutations`, read by the analysis, with a fallback to `target` for
ledgers predating the column; a `LEDGER_SCHEMA_VERSION` bump to `ledger/2`; four
proofs; and a §VIII construct-validity concession. It was reverted six days
later.

---

## 2. What `74ea31f` and `241292e` removed

`241292e` (4 Sep) is the framing reversal itself — title, running head,
`CITATION.cff`, `arxiv-metadata.md`, the TSE cover letter, README, and the
SUPERSEDED banner on docs/33. It removed **no code**. It explicitly left "whether
to keep or revert WS-1a" open.

`74ea31f` (4 Sep) closed that question by reverting. Its own inventory, verified
against the tree as it stands today:

| removed | present now? |
|---|---|
| `Transmitter.transmit()`'s `execution_id`, 5 implementations, 6 call sites | gone |
| `EXECUTION_ID_HEADER` and the provider plumbing in `mock_api/service.py` | gone — grep returns nothing |
| `applied_mutations.execution_id`, its threading, and the schema bump | gone; `LEDGER_SCHEMA_VERSION` reads `ledger/1` |
| `oracle_effects_by_execution`, `applied_effects_for`, `_has_execution_id`, `EXECUTION_ID_COLUMN` | gone; `analyze.py:199` is `oracle_effects_by_target`, `:213` is `GROUP BY target` |
| `tests/test_ws1a_attribution_proofs.py` (269 lines) | gone |
| four attribution tests in `test_plan_invariant.py` | gone |
| the §VIII baseline-fidelity concession | gone |

**Kept**, and still present: `plan_invariant.py` and its eight invariant tests;
`duplicate_groups()`'s docstring carrying the reasoning; docs/33's three refuted
designs; the reports.

### 2.1 What would have to come back, and how

**The code: restorable from history, cleanly.** Of the eight files `74ea31f`
touched, **six have had no commit since**: `mock_api/client.py`,
`mock_api/ledger.py`, `mock_api/service.py`, `baselines/common.py`,
`baselines/b4_durable_workflow.py`, `tests/test_plan_invariant.py`.
`experiments/analyze.py` is listed with one commit since (`adaf834`) but that
commit's diff for the path is **empty** — no content change to the attribution
region. So `git revert 74ea31f` would apply to the code essentially as written.

**The §VIII paragraph: has to be rewritten, not restored.**
`paper/sections/08-threats.tex` has had **five commits** since the revert —
WS-9 move 2 restructured the whole section into construct / internal / external
/ conclusion validity and cut it from 608 lines to 408, and WS-7 added to it
again. The removed concession was written for a section that no longer exists in
that shape. Restoring the diff would not apply, and should not: the paragraph
has to be re-authored into the construct-validity subsection.

**Two things `74ea31f` verified that are no longer true, and must be re-checked
before any restoration.** The revert asserted "1364 collected ledgers checked,
ZERO carry the column, so nothing is stranded." Since then WS-6 collected the B5
sessions and WS-5 is collecting ~600 runs as this is written. The ledger count
has grown, all of it under `ledger/1`. Re-introducing the column means the
`ledger/2` bump *and* the fallback-to-`target` reader, which was removed with
the column — and the fallback is now load-bearing for a materially larger frozen
corpus than it was on 4 September.

---

## 3. Does §4.2's limitation still stand?

**Yes, and it is now wider than docs/33 states.**

The restriction is not arbitrary: the two flags coincide exactly. Read from
`experiments/baselines/contract.py` as it stands:

| system | `can_declare_ambiguity` | `sends_client_reference` |
|---|---|---|
| B0, B1, B2 | False | False |
| B4, B4b | False | False |
| **B5, B5b** | **False** | **False** |
| B3 | True | True |
| AEP-full | True | True |

The two columns are identical for all nine systems. Drift needs both — an
ambiguous step to drift *from* (`can_declare_ambiguity`) and a caller reference
to tell a new intent from a retry (`sends_client_reference`) — so the metric is
defined exactly where both are True and nowhere else.

**What has changed since docs/33 is that the excluded set grew from five to
seven.** WS-6 added B5 and B5b, and both are False on both flags. docs/33 §5.2
says the paper "cannot say a durable workflow engine drifts more or less than
AEP-full"; with B5/B5b in the paper that sentence now also covers *the real
Temporal engine*, which is the comparison a reviewer is most likely to ask for.
Nothing since has narrowed the restriction, and WS-6 widened it.

---

## 4. Does the NO_READBACK prediction still hold?

**A note on the reference:** the prediction is in **§4.4**, not §3.4. §3.4 is the
config-digest constraint. Taking the prediction as meant:

> under `NO_READBACK` there may be *no difference at all* between the two arms.
> Both declare ambiguity, both hand the planner the same observation, and the
> planner is the same code.

**It holds, and the frozen data now supports its premise more strongly than when
it was written.** The premise is that the two arms hand the planner the same
observation. Measured: declared ambiguity under NO_READBACK is **0.7222** for
AEP-full and **0.7167** for B3 (`tab:outcomes`). §VI's ablation puts the
difference at **+0.37 pp** with a 90% run-clustered interval of
**[−1.11, +2.04] pp**. If the observation is the input to the planner and the
planner is the same code, identical inputs are expected to produce identical
drift.

**WS-4 bears on it, and strengthens the prediction's stated interpretation
rather than the prediction itself.** docs/33 says that if drift is identical
"that is a finding about where the protocol's value sits — in what reached the
provider, not in what the caller does next." WS-4 is direct evidence for exactly
that: under block-level write loss AEP-full withholds dispatch and B3 proceeds.
The two arms differ in what reaches the provider while handing the caller
observations that §VI cannot distinguish. That is the prediction's own reading,
now measured.

**WS-6 does not bear on it.** B5 and B5b never declare ambiguity in any run, so
they contribute no ambiguous step and cannot drift; the prediction is about
AEP-full versus B3 and WS-6 touches neither.

**One thing that does bear on it and is not in docs/33:** the write-loss and
Redis-kill regimes run `executions_per_run=1` (see §5.3 below), so the regime
where AEP-full and B3 differ most is a regime in which drift cannot be measured
at all.

---

## 5. What docs/33 assumes about the harness that is no longer true

docs/33 was written against the 4 September harness. Four changes since would
require redesign rather than restoration.

### 5.1 B5 and B5b have no planner seam — and docs/33 needs them to have one

docs/33's planner sits above the harness's own worker loop and assumes one such
loop. B5/B5b do not use it: they run activities inside a Temporal worker driven
by `experiments/baselines/b5_temporal/{collect,session,supervisor}.py`, added by
WS-6 on 8 September, four days after docs/33.

This matters even though §4.2 excludes B5/B5b from *drift*, because docs/33 §4.2
also says their "agent-workload cells contribute the existing three outcomes and
no drift figure" — so they still have to run the workload. That means
implementing the planner interface a second time, inside a Temporal activity,
or excluding B5/B5b from agent cells and saying so. Neither is costed in
docs/33, because neither existed.

### 5.2 The crash point is now bound per cell, and disagreement voids the run

`593ea64` ("the injected crash point comes from the cell, and disagreement
voids") plus `experiments/baselines/crash_points.py`'s explicit partial mapping
(`ROADMAP_TO_BASELINE`, with `None` meaning *this system has no such moment* and
the cell recorded `not_applicable`) changed the relationship between a cell and
where a crash lands.

Under the fixed workload the crash point and the execution index are both known
before the run starts. **Under a planner they are not:** which *step* a
cell's crash point falls on depends on what the planner chose, and the planner's
choice depends on prior outcomes. docs/33 §1.4 assumes a sequence but never
addresses how a per-cell crash point binds to a planner-determined step, nor
what "disagreement voids" means when the step sequence is itself an outcome.
This is the largest genuinely new design problem, and it is not a restoration.

### 5.3 Three regimes cannot host the workload at all

`redis-kill-preack`, `redis-kill-inflight` and `write-loss-preack` all set
`executions_per_run=1`. docs/33 §1.4 is explicit that such regimes "cannot
exercise re-planning at all, because there is no 'after' in which to re-plan."

docs/33 states the constraint but does not draw the consequence, which is worth
stating plainly: **the agent workload is confined to the crash regimes
(`session-3`, `p0`, `p30`) and cannot reach the infrastructure-fault regimes** —
including the write-loss regime that carries WS-4's result and the Redis-kill
regimes that carry the prevention result. Whatever plan drift measures, it
measures it where AEP-full and B3 are hardest to tell apart.

### 5.4 Two seeded generators whose consumption order the planner now controls

The provider is seeded (`MockLegacyApi._random = random.Random(config.seed)`),
and `run_matrix.cell_seed()` derives each run's seed from
`(matrix_seed, MATRIX_VERSION, cell.key, repetition)` — derived rather than
drawn, so the plan can state every seed before collecting.

docs/33 §3.3 discharges replay for the *planner's* RNG only. It does not address
that the provider's generator is consumed in an order the planner now
determines: a different tool sequence draws from the provider in a different
order. For the scripted planner this still replays, because the planner's
decisions are themselves a pure function of the seed. For the transcript-based
model-backed arm it is a new requirement — replay must reconstruct the planner's
decisions *before* the provider is consulted, in order, or the provider diverges
even though the transcript matches.

### 5.5 What has not changed

Two load-bearing assumptions survive intact. `workload.py` still derives
everything from `(run_id, seed, worker_index, execution_index)` with nothing
drawn from a global generator, so §3.3's scripted-planner discipline is
unchanged. And §3.4's config-digest constraint still holds exactly as written:
`RunConfig._body()` iterates every dataclass field into `config_digest`, so
planner selection must go in the `environment` block. That constraint is
*more* binding now than in September, because every run WS-6 and WS-5 have
added is digested under the current field set.

---

## 6. What it would cost now

docs/33 estimated 2–3 weeks when the harness was simpler. The harness metric the
manuscript reports has gone from **23,946** lines at the revert to **27,098**
today — 13% growth, all of it in B5, the supervisor, the write-loss injector and
the WS-5 instruments.

Costed against what is actually there:

| item | restore or rewrite | notes |
|---|---|---|
| WS-1a code (execution id, header, column, analysis path, proofs) | **restore** | `git revert 74ea31f` applies; 6 of 8 files untouched since, the 7th has an empty diff |
| the `ledger/2` bump and the fallback reader | restore, then **re-verify** | the "zero stranded ledgers" check must be re-run against a corpus grown by WS-6 and WS-5 |
| §VIII construct-validity paragraph | **rewrite** | the section was restructured by WS-9 move 2; the old diff will not apply and should not |
| planner interface + scripted planner | **new** | as designed in §3; the only part docs/33's estimate covers accurately |
| planner seam for B5/B5b | **new, undesigned** | Temporal activity, not the harness worker loop; or an exclusion that must be justified |
| crash-point binding under a planner-determined step sequence | **new, undesigned** | §5.2; the substantive open design problem |
| provider-seed replay ordering | **new, small** | §5.4; matters only for the model-backed arm |
| pre-registration (§4.4) | **new** | per rule 5, before any agent cell |
| collection | **new** | agent cells across 3 regimes × 3 capability classes × systems |
| local open-weights arm | **new, optional** | docs/33 already flags the cross-hardware determinism caveat |

Two things push the honest figure above docs/33's 2–3 weeks, and neither is
absorbable by working faster. §5.2 is a design problem with no worked answer in
docs/33 — the interaction between a per-cell crash point that voids on
disagreement and a step sequence that is itself an experimental outcome. And
§5.1 is a second implementation of the planner interface against a runtime
(Temporal) that did not exist when the interface was specified.

Everything else is either a clean revert or work docs/33 already costed. The
2–3 week figure was for the second category only.

---

## 7. Status of what this report read

Read-only. `docs/33`, `docs/26`, the two commits and their diffs,
`experiments/baselines/contract.py`, `experiments/analyze.py`,
`experiments/harness/workload.py`, `experiments/run_matrix.py`,
`experiments/baselines/crash_points.py`, `experiments/mock_api/ledger.py`,
`paper/generated/{numbers.tex,table-outcomes.tex}`, and `git log`. No process
was started or stopped; the WS-5 collection was left alone.
