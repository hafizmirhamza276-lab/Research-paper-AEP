# WS-1a — attribution: closing report

**2026-09-04.** The prerequisite that blocks WS-1b (the agent workload proper).
Design in `docs/33-agent-workload.md` §2; this is what was built and what it
cost.

---

## 1. The problem

The published duplicate metric attributes an applied effect to an execution **by
`target`**:

```
analyze.py  is_undetected_duplicate = applied_effects > 1 and outcome != DECLARED_AMBIGUOUS
            applied_effects         = effects[target]
            oracle_effects_by_target: SELECT target, COUNT(*) ... GROUP BY target
```

That is sound only because `target` is `account-{execution_id}` — it *encodes*
the execution. Measured on the frozen 432-run matrix: 4 782 applied rows, 1 401
targets carrying more than one row, and **zero** carrying rows from two distinct
intents.

An agent workload re-plans onto a used target, which removes the property. It
removes it for **all seven systems**, because unlike `client_reference` — NULL in
87.2% of rows — `target` is populated for every one.

## 2. What was built

* **A protocol-independent execution id**, supplied by the harness on every call
  for every system, carried by `X-AEP-Execution-Id`, recorded in
  `applied_mutations`. `LEDGER_SCHEMA_VERSION` → `/2`.
* **`Transmitter.transmit()` widened** to carry it — 5 implementations, 6 call
  sites. `mutate()` passes `binding.execution_id`; the four baselines pass their
  own `execute()` loop's id.
* **The analysis attributes by it** where the ledger carries it, falling back to
  `target` otherwise.
* **The §2.9 repeat invariant** as a checker over a recorded plan
  (`experiments/harness/plan_invariant.py`): a planner may repeat a fingerprint
  only in response to a step declared `PERMANENTLY_AMBIGUOUS`.
* **The §VIII baseline-fidelity threat**, stated in the manuscript.

## 3. Three wrong designs, and the framing that resolves them

Each was written down, implemented or attempted, and refuted by the code. All
three are recorded in `docs/33` §§2.0, 2.3, 2.7 rather than replaced.

| | the design | why it failed |
|---|---|---|
| **§2.0** | partition `duplicate_groups()` on `client_reference` | it does not produce any number in the manuscript. The metric comes from `oracle_effects_by_target`. The repair would have left the paper untouched while appearing to fix it. |
| **§2.3** | attribute by `client_reference`, falling back to `target` | it misses an execution that died before recording anything — the case every crash regime rests on. `reconcile.py:7-13` had already rejected it for that reason. **And its proof would have passed**: on frozen data targets are unique, the fallback fires on every row, and the new path is never exercised. |
| **§2.7** | partition `duplicate_groups()` on `client_reference` (again, for the oracle's own sake) | the caller reference is protocol-generated — AEP sends its own `binding.request_fingerprint` — so a protocol could hide its duplicates by minting a fresh reference per attempt. Refuted by an existing test written for exactly that. |

**Two identifiers, two owners.** The resolution is that identity and attribution
are different questions with different trust models:

> The **oracle** owns *identity* — "are these the same mutation?" — and must
> answer it **taking nothing from the caller**, because the caller is the system
> under measurement.
>
> The **analysis** owns *attribution* — "which execution caused this row?" — and
> may take it **from the harness**, because the harness is not under measurement.

All three wrong designs collapsed those two into one, in a different direction
each time. §2.0 asked the oracle a question the analysis owns. §2.3 asked the
analysis to use a key only the protocol can supply. §2.7 asked the oracle to
trust a value the protocol generates.

The execution id is admissible precisely because it is the harness's, not the
protocol's: the system under test cannot read it back, condition on it, or vary
it to its advantage.

## 4. The four proofs

`tests/test_ws1a_attribution_proofs.py`, 10 tests.

1. **Frozen numbers do not move — and the check is non-vacuous.** Byte-identity
   on pre-WS-1a data only shows the fallback is intact, since those databases
   have no column. It is paired with a fixture where two executions share one
   target and the attributions **disagree**: target reports 2 effects for each,
   execution reports 1. A third test shows the cost — under target attribution
   both executions read as undetected duplicates when neither is.
2. **`config_digest` unaffected.** `execution_id` is not a `RunConfig` field and
   does not appear in the digest body.
3. **The schema bump does not reach the analysis.** No `ledger_meta`, no
   `schema_version`, and the module owning `LEDGER_SCHEMA_VERSION` is never
   imported; a trace callback confirms the only `SELECT` against a column-less
   ledger is the original target query.
4. **The execution id is inert.** No ledger accessor is keyed on it — which is
   what makes `client_reference` a capability and this instrumentation — it is
   absent from the fingerprint module, and two applications of one mutation
   under different ids are still one duplicate group.

## 5. The one number that moved

**`\HarnessLoc`: 23 803 → 24 113** (93 → 94 files). The regenerated count of
Python lines under `experiments/`, reflecting the code this workstream added. It
is not a result; it is a number the generator recomputes precisely so it cannot
silently rot.

**No measured number moved.** No ledger in the tree carries the column, so the
analysis takes the target-attribution path everywhere it currently runs.

## 6. Verification

* Full suite: **1857 passed, 34 skipped**.
* `scripts/check_paper_numbers.py`: **19 passed, 0 failed**.
* Both PDFs rebuilt through `build_paper.sh`, which compiles in scratch and
  promotes only a clean build.

## 7. What is deliberately not done

* **`duplicate_groups()` is not partitioned** (§3, row three). Left grouping on
  fingerprint alone, with the reasoning in its docstring.
* **No agent code.** WS-1b is unblocked by this report but not started.
* The §2.9 invariant is implemented and tested but has **no caller yet** — the
  planner that will call it does not exist.

**WS-1a is complete. WS-1b is unblocked.**
