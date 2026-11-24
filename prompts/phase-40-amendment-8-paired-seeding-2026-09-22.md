# Amendment 8 — paired seeding, so both arms meet the same conditions

**Amends `prompts/phase-40-agent-reachability.md`** §1 (the design) for the
**agent branch only**. Committed **before any further live call** and before
the code that implements it.

**Justified under amendment 6 §8 as the leak category**, which
`reports/phase-report-40-fault-symmetry-2026-09-22.md` named: the provider's
fault stream is seeded from a key whose first component is the system name, so
**arm identity determined the conditions the caller was tested under**. The
agent could not read the seed, but the experiment runs one fixed caller against
two systems and attributes the difference to the systems — and the systems were
handed different faults on different payments.

Amendment 6 §8 remains in force and is not reopened: further amendments still
require a **named** crash, leak or malformed path. This one names a leak.

---

## 1. The fault, restated precisely

`experiments/run_matrix.py:653-663` derives every run's seed from
`cell.key`, and `cell.key` (`:475-483`) begins with `self.system.value`.
Recomputing it reproduces every archived seed exactly; removing the system name
from the key changes it. That seed becomes both the provider's fault seed and
the workload seed, so the two arms have never faced the same faults **or**
handled the same payments.

## 2. The matrix is NOT affected, and its seeds stay as they are

**Per-cell seeds are correct for the matrix and remain correct.** There, each
cell is its own condition, collected 30 repetitions deep, and independent
per-cell seeds are precisely what makes the cells independent of one another.
A shared seed across cells would be the defect.

It becomes a validity problem only in phase 40's **paired, small-*n*,
binary-reachability** framing, which compares two cells directly, at one or two
runs each, rather than comparing distributions. The mechanism was right for the
job it was built for and is wrong for this one.

**So nothing in the matrix changes.** No collected run's `config_digest` moves,
`tests/test_scripted_plan_is_frozen.py` keeps recomputing the 51 collected runs
against what they recorded, and the scripted branch stays
character-for-character as it is. Pairing is reachable only on the
agent-interactive branch.

## 3. Why a shared seed alone would not have been enough

This is the part that decides the design, and it is a fact about the provider
rather than a preference.

### 3.1 The mutation fault stream is sequential

`MockLegacyAPI.__init__` holds one generator, `random.Random(config.seed)`, and
`draw_faults` consumes from it **three times per mutation**, unconditionally
and in a fixed order:

```python
server_error = self._random.random() < faults.server_error_probability
timeout      = self._random.random() < faults.timeout_probability
duplicate    = self._random.random() < faults.duplicate_response_probability
```

`draw_delay` consumes **nothing** under the pre-registered `CONSTANT`
distribution — deliberately, and the code says so: *"a run with delays disabled
must produce the same stream of fault decisions as one with delays enabled."*

**Read-backs consume nothing.** `draw_faults` and `draw_delay` are called from
exactly one place, `service.py:384-385`, inside the mutation route. The
read-back routes never touch the generator. That is worth stating because it
would otherwise be the obvious suspect, and it is not the problem.

### 3.2 The two arms send different numbers of mutations

From each run's ground-truth ledger and run log — the provider's own record of
requests that reached the fault draw:

| collection | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| stage 30 | 1 | 1 |
| stub a6 | **0** | **4** |
| stub rpc2, rep 0 | **0** | **4** |
| stub rpc2, rep 1 | **0** | **3** |

The counts differ because the arms differ in ways the protocol is *supposed* to
differ in: AEP's dispatch gate can withhold a dispatch that B0 sends
immediately, a crash can land before the request arrives on one arm and after
it on the other, and a re-dispatch the agent authorises reaches the provider on
both arms but produces a different number of records depending on what the
first attempt did.

### 3.3 Therefore a shared seed synchronises nothing past the first difference

At three draws per mutation, two arms sharing one seed stay aligned only while
they present the **same mutations in the same order**. After the first
divergence — one withheld dispatch, one extra retry, one crash landing on the
other side of the request — arm A's *n*-th mutation meets the fault drawn for
arm B's *m*-th, with *m ≠ n*, and every mutation after it is misaligned too.

**A shared seed would make the asymmetry harder to see without removing it.**
That is why §5 keys the fault to the request rather than to its position in a
sequence.

## 4. The workload is paired

On the agent branch, for the same repetition, **both arms receive an identical
workload**:

* the same **execution ids**,
* the same **targets**,
* the same **harness-assigned amounts**,
* the same **crash selection**.

`plan_workload` already derives each of these from named streams rather than a
sequential generator — `_stream(run_id, seed, purpose, worker, index)` — so the
change is to the *identity* those streams are keyed on, not to their structure.
On the agent branch that identity is a **pair identity**: the cell key with the
system component removed, and a seed derived from it. Off the agent branch it
is `(run_id, seed)` exactly as now.

§1.1 is untouched: the target remains harness-assigned and the planner still
chooses only tool, action and whether to act. Amendment 3's
`PLANNER_AMOUNT_MISMATCH` is untouched and now has more to bite on, because the
assigned amount is the same on both arms.

## 5. The fault is keyed to the request, not to the sequence

**Each mutation's fault outcome is a function of**

> **(paired seed, execution identity, dispatch ordinal for that execution)**

**and not of the global request sequence.**

* **Execution identity** is the request's own fingerprint — method, endpoint,
  action and amount — which §4's paired workload makes identical across arms
  for the same logical payment. It is derived from the request's content and
  from nothing the protocol mints, so no arm-specific value can enter it.
* **Dispatch ordinal** counts how many times *that* identity has already been
  seen in this run. The first dispatch of a payment is ordinal 0 on both arms
  whatever either arm did about other payments; a re-dispatch the agent
  authorises is ordinal 1 on whichever arm authorises it.

**The consequence is the property this amendment exists for: the same logical
request meets the same fault on both arms, whatever else either arm sends.**
An extra read-back, an extra retry, a withheld dispatch, a differently-timed
crash — none of them can shift the fault another payment will meet.

**Read-back routes draw from a separate stream.** They consume nothing from the
mutation stream today; this makes that structural rather than incidental, so a
future read-back that does need randomness cannot perturb the mutation faults
by existing.

## 6. The probabilities are unchanged

`server_error_probability: 0.05` and `timeout_probability: 0.15`, exactly as
pre-registered and exactly as every collection so far has run.
`duplicate_response_probability` stays at 0.0.

**Only the pairing changes.** The marginal distribution of faults is the same;
what changes is that the draw is reproducible per request instead of per
position, and therefore the same on both arms.

## 7. Stages 10 and 30 stay in the record as UNPAIRED

They are not re-run, not re-scored, and not deleted.

**Their instrument criteria stand.** C1 (every call has a transcript, token
counts and a cost), C2 (no filter blocks), C3 (no malformed calls), C4′ (the
cost bounds), and amendment 6 §9's clauses 2 and 3 are all **properties of the
instrument**, verified from the run directories, and none of them depends on
which faults the provider injected:

* C1 counts transcripts against journal reservations and checks arithmetic.
* C2 and C3 read the transcript's own outcome field.
* C4′ reads token counts and the ledger.
* Clause 2 counts calls about the crashed payment; clause 3 checks who was
  asked. Both are harness behaviour.

**That is the reasoning for §8's conclusion, and it is the reason stage 30 does
not need re-running.**

**No comparison between the arms is drawn from either stage.** Stage 30's
exploratory addendum §A.3 attempted one and has been withdrawn
(`dccb478`). Any later summary describes both stages as unpaired and draws no
cross-arm inference from them.

## 8. Stage 100 is the first paired stage

Stage 30's criteria are not re-run. Stage 100 runs under pairing, is the first
collection in which a cross-arm comparison is admissible at all, and is
assessed against §6's stage-100 criterion — both failure modes observed at
least once, cumulative spend under USD 1 — plus C1–C3 and C4′ as before.

Amendment 7 opened stage 100 by author override; this amendment changes the
conditions it will run under, not whether it may run.

## 9. What is unchanged

§1's two systems, crash point, capability class, regime, run count and turn
count; §1.1's harness-assigned target; §2's metric and its prohibition on
rates; §3's five controls and both USD figures; §4's `PLANNER_FILTERED`; §5's
transcript requirements; §6's C1–C3, C4′ and staging; §8's failure definitions;
§9's stop rule as amended by amendment 5.

Amendments 1–7 stand in full, **including amendment 6 §8's closure of
structural amendments**. This amendment is made under that clause rather than
around it: it names a leak, which §8 lists, and it changes the conditions the
caller is tested under rather than what the caller is asked or how the loop
behaves.
