# Phase 26 — §VI-RQ3: the prose, over macros that now exist

## Asked / Done

Asked: retire 28.0 ms, make the `always` result the headline, put H4 in §VI,
correct `08-threats.tex:303`, empty `PENDING_MACROS`, rule 3 on every changed
claim, report the page delta.

Done: all of it. **`PENDING_MACROS` is empty. Every one of phase 25's 17 macros
is quoted.** The 15 three-run macros they supersede are no longer emitted at all.

One thing had to be decided that the prompt did not cover, and it is in §5: the
superseded macros became orphans the moment their prose was replaced, and the
gate fails on orphans.

---

## 1. Every claim, before and after

### The decomposition — `06-evaluation.tex:667`

**Before:** *"Everything the write-ahead protocol does apart from waiting for
`fsync` … costs `\ProtocolMinusBarrier{}` ms on a two-second call, or
`\ProtocolMinusBarrierPct{}`%. The two `WAITAOF` round trips cost
`\BarrierCost{}` ms between them, or `\BarrierCostEach{}` ms each."* — 28.0 ms
and 1 966.7 ms, both from three runs per arm.

**After:** the barrier is `\BarrierCostFifteen{}` ms
[`\BarrierCostFifteenLow{}`, `\BarrierCostFifteenHigh{}`] — 1 939.7
[1 855.8, 1 962.4]. The residual is `\ProtocolMinusBarrierFifteen{}` ms
[−122.6, 120.1] **pooled**, and `\ProtocolMinusBarrierLowerMode{}` ms
[−54.1, 47.5] **lower-mode**. Both intervals are in the same sentence as their
figure. Both readings appear, with the reason stated in the paper's own voice:

> We report both because they were both pre-registered and they disagree, and
> choosing between them after seeing them is the move this paper is arguing
> against.

And the claim is scoped once:

> **So the decomposition supports an ordering and not a partition.** … What
> cannot be said is what fraction of the protocol's cost is optional, because at
> this precision the non-barrier remainder is not distinguishable from nothing
> at all. An earlier draft of this paper quoted that remainder as a point figure
> of about thirty milliseconds; it rested on three runs per arm, and twelve more
> did not confirm it.

### The `always` policy point — `06-evaluation.tex:756`

**Before:** *"The barrier's cost falls from `\BarrierCost{}` ms to
`\BarrierCostAlways{}` ms"* — 1 966.7 → 15.0, a fall.

**After:** `\BarrierCostAlwaysFortyFive{}` ms
[`…Low{}`, `…High{}`] — **−9.2 [−27.2, 44.6]** over fifteen runs per arm,
followed by what it means:

> **That is the measurement this section turns on.** The barrier does not become
> cheap under `always`; it costs nothing, and the `\BarrierCostFifteen{}` ms it
> costs under `everysec` is therefore the price of the fsync boundary rather
> than of the barrier. … Nothing in the mechanism is expensive.

and why the sign is not a problem:

> The sign is not a puzzle to explain away. The two medians it separates are
> `\AepAlwaysFortyFiveMedian{}` ms with the barrier and
> `\BthreeAlwaysFortyFiveMedian{}` ms without it, on a two-second call; the gap
> between them is noise around a mechanism that is doing no waiting. This arm
> was pre-registered with the interval's exclusion of zero explicitly ruled out
> as an acceptance criterion …

### H4 — `06-evaluation.tex:186`, beside the rate it moves

New paragraph immediately after `\AepAmbPosOnly{}` is quoted:

> **The `pos-only` rate depends on how the read-back is keyed, and we did not
> expect it to** … We pre-registered an alternative keying … and predicted it
> would leave every headline rate inside a ±5 percentage-point margin. On
> `pos-only` it does not: declared ambiguity is `\KeyingAmbiguityCaller{}`%
> under the caller's reference and `\KeyingAmbiguityOracle{}`% under the
> fingerprint, a difference of `\KeyingAmbiguityDelta{}` percentage points …

with the consequence for generality, once:

> The two columns that carry the safety claim are unmoved … What moves is the
> residual, and the consequence is a limit on generality rather than on
> correctness. **The `pos-only` ambiguity rate is a property of the protocol
> *and* of how the recovering worker phrases its question** …

### `08-threats.tex:303` — the paragraph that prescribed more runs

**Before:** *"Every timing number rests on three runs, and one does not survive
its own interval … Closing this needs more crash-free **runs**, not more
executions per run."*

**After:** *"What fifteen runs per arm settled, and what they did not"* — the
barrier is pinned, the residual is not under either reading, and:

> That is a statement about resolution and not about the effect: a residual of a
> few tens of milliseconds on a two-second call is below what fifteen runs of
> this workload can separate from nothing, and more runs would narrow it rather
> than move it.

It also says what `\cref{tab:deployment}` now is, since the table's cells are
still the three-run ones: *"shown as the deployment points they were collected
to compare, not as the source of the costs quoted above."*

### `08-threats.tex:374` — the ratio

**Before:** a factor of roughly `\BarrierToProtocolRatio{}`, *"whose denominator
is pinned only to [27.1, 1 524.6] ms at three runs per arm"*.

**After:** no factor at all.

> A ratio whose denominator is not distinguishable from zero is not a
> measurement.

## 2. What the paper no longer says

* That the protocol costs **28.0 ms** apart from the barrier. It quotes an
  interval containing zero, twice, under both pre-registered readings.
* That the barrier's cost **falls to 15.0 ms** under `always`. It says the
  barrier costs nothing and the `everysec` figure is the fsync boundary.
* That the barrier dominates **by a factor of** anything.
* That every timing number rests on three runs.
* That closing the precision gap **needs more crash-free runs**.
* That the `pos-only` ambiguity rate is a property of the endpoint class alone.

## 3. `PENDING_MACROS` disposition — empty

All 17 entries deleted, because all 17 are now quoted:

| macros | where |
|---|---|
| `BarrierCostFifteen{,Low,High}` | §VI-RQ3 ×5, §VIII ×3 |
| `ProtocolMinusBarrierFifteen{,Low,High}` | §VI-RQ3, §VIII's ratio sentence |
| `ProtocolMinusBarrierLowerMode{,Low,High}` | §VI-RQ3, the both-readings sentence |
| `BarrierCostAlwaysFortyFive{,Low,High}` | §VI's `always` point, §VI's precision paragraph |
| `AepAlwaysFortyFiveMedian`, `BthreeAlwaysFortyFiveMedian` | §VI's "the sign is not a puzzle" sentence, §VI's both-policies premise |
| `KeyingAmbiguityOracle`, `Caller`, `Delta` | §VI's new H4 paragraph |

The mechanism stays in place with a comment saying why it is empty. Its two
checks — "every pending macro still exists", "no pending macro is already in
use" — both pass against an empty list, and the next pass that must stage a
macro gets them back.

## 4. Rule 3

Four new provenance comments, each naming the CSV and the estimator: the
fifteen-run barrier bootstrap, the two protocol-minus-barrier readings, the
45-run `always` cell (twice — the difference and the two medians), and H4's two
pooled cells with their `sum(successes)/sum(total)` construction.
`analysis/table-1.csv` is cited nowhere.

## 5. The decision the prompt did not cover

Replacing the prose orphaned **15 macros** — `\ProtocolMinusBarrier`,
`\BarrierCost`, `\BarrierCostAlways`, `\BarrierToProtocolRatio` and their
intervals and derivatives. `check_macros_are_used` fails on orphans, and the
three available moves were all wrong:

* leave them orphaned — the gate goes red;
* put them in `PENDING_MACROS` — that list means *"prose not written yet"* and
  asserts the macro is **not** in use. These will never be in use. It would
  break the mechanism phase 25 built in the same week;
* keep quoting them — the paper would carry two estimates of the same quantity
  from samples five times apart.

So they are **no longer emitted**: `SUPERSEDED_MACROS` in `paper_tables.py`,
with the reason attached, and the `macro()` helper returns early for any name in
it. `scripts/paper_tables.py` was not in this pass's listed scope; the change is
sixteen names and a two-line guard, and the alternative was a red gate. Recorded
here rather than done quietly.

`numbers.tex` is now **199 macros**: 214 minus the 15.

**One correction inside that change.** `\BarrierCostEach` was in the suppression
list and should not have been: `paper/supplementary.tex:202` quotes it, and
suppressing it broke both supplementary builds with an undefined macro. It was
caught by the build, not by the orphan check — the orphan check had correctly
*not* listed it. It is un-suppressed, and the fact that a three-run derived
figure survives in the supplementary while §VI quotes fifteen-run ones is
recorded in §7 as a follow-up, because `supplementary.tex` was out of scope.

## 6. Not done, and why

* **H2, H3 and H5 still have no macros and no prose.** Phase 25 §6 gave three
  separate reasons and they stand. H5's remains the only technical one.
* **`\cref{tab:deployment}`'s four medians are still the three-run cells.** The
  table is generated from `--fsync-analysis`, the August cell. §VIII now says so
  explicitly rather than leaving a reader to assume the table and the prose come
  from one sample. Repointing the table at the 45-run arm is a generator change
  and was not attempted.
* **The page count did not fall.** §8 asked for a pass that removes more than it
  adds; §VI grew by 59 lines net and §VIII shrank by 3. The additions are H4's
  paragraph, which did not exist, and both readings of a figure that previously
  had one. WS-9 is where length comes out.


## 10. Four tests failed, and that is rule 14 working

The suite came back **4 failed / 2045 passed** on the first run. All four
asserted properties of the macros this pass stopped emitting:

```
test_the_barrier_costs_are_within_policy_and_no_ratio_is_emitted
test_the_barrier_to_protocol_ratio_is_the_two_macros_divided
test_the_ratios_denominator_carries_its_own_interval
test_the_fifteen_run_macros_are_distinguishable_from_the_three_run_ones
```

The fourth is my own, from phase 25, asserting that `\BarrierCost` and
`\BarrierCostFifteen` both exist and differ.

Each was **rewritten to assert the new invariant, not deleted**: that the
superseded name is not emitted, and why. "This macro must not come back" is the
property worth keeping, and a deleted test keeps nothing. 44 passed after.

## 7. Raw outputs

```
check_paper_numbers.py     39 passed, 0 failed
validate_citations.py      OK: 371 citations, 0 invalid
full suite                 2049 passed, 34 skipped after the four rewrites below; the first run was 4 failed / 2045 passed
builds                     supplementary, supplementary-anon, anon, main -- all exit 0
macros                     214 -> 199  (15 superseded, no longer emitted)
PENDING_MACROS             empty
\ProtocolMinusBarrier{}    0 uses in .tex, 0 definitions
\BarrierCost{}             0 uses in .tex, 0 definitions
\BarrierCostAlways{}       0 uses in .tex, 0 definitions
\BarrierToProtocolRatio{}  0 uses in .tex, 0 definitions
net text                   06-evaluation.tex +108/-49, 08-threats.tex +21/-24
generated/ hand-edited     none
```

## 8. Page delta

| | pages |
|---|---|
| before | 25 |
| after | **25** |

No change. Stated rather than presented as neutral: the pass was asked to remove
more than it adds and did not.

## 9. Status lines, as asked

**WS-1 (framing).** **Done in the manuscript, stale in the checklist.** The
title is *"Declared Ambiguity: Fail-Closed Execution for Non-Idempotent Legacy
APIs Without Idempotency Keys"* — no "Autonomous Agents" — and §VI contains the
word "agent" **zero** times. `docs/26` §7's unticked WS-1 box appears to
describe a decision that has already been executed; the remaining question is
whether §I and §II match, which this pass did not read.

**WS-0 (native Linux host).** **Open, and unchanged.** `08-threats.tex:261`
still reads *"All measurements were collected on Ubuntu inside WSL2 on
Windows 11, with Docker Desktop port forwarding in the path"*. No native-host
measurement and no cross-host replication of a frozen cell exists; every
collection in this sequence, including the 45-run `always` arm, was taken on the
same WSL2 host.
