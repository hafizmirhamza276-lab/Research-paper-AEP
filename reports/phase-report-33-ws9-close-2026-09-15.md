# Phase 33 — WS-9 closed: the floor reached, M5 amended

## Asked / Done

Asked: unblock the migration at its cause, migrate the ~1 700 words, take the
other measured items, amend M5, close WS-9.

Done: the caption unblocked and watched failing before the fix, **three
migrations executed and committed green, 25 → 23 pages**, M5 amended with the
ruling and its evidence, WS-9 closed in `docs/26` §7.

The four §VI headline blocks and §VII's 1 498 words of positioning did not move.
Citations 371/0. No macro changed value.

---

## 1. The caption fix, and its failing-branch evidence

`generated/table-deployment-choice.tex` carried four `\cref`s into the main
text — `tab:outcomes`, `sec:eval-detection`, `tab:ablation`,
`sec:eval-prevention`. That is what pinned the table to the paper: a `\cref`
cannot cross documents, so moving the table made the supplementary build fail
with undefined references, and phase 30 reverted rather than commit it.

Fixed in the generator, by name:

> The detection claim of **the paper's outcome table** shows no observed
> difference in any cell, bounded by pooling the capability classes rather than
> per class, **as its detection subsection sets out** … and **the ablation
> table** shows it. What the barrier buys is the last column's second word, and
> **the prevention subsection** is what it is worth.

**Rule 13**, in `tests/test_deployment_caption_is_portable.py`, four tests. The
pre-fix caption is kept verbatim as a fixture and run through the current gate
(R17 — no older generator is executed):

```
pre-fix caption, table in the MAIN text          passes  <- why nobody noticed
pre-fix caption, table in the SUPPLEMENTARY      FAILS   <- what stopped phase 30
the real generated caption, in either document   passes
the generated caption contains no \cref at all   passes
```

The first is the point: the defect was invisible while the table sat where it
had always sat. The fourth reads the real artifact rather than a copy, so a
regeneration that reintroduced a `\cref` would fail it.

## 2. What migrated

| block | words | to | reference sites converted |
|---|---|---|---|
| `sec:eval-deployment` + `tab:deployment` | 908 | `supp:deployment` | 10 |
| `sec:eval-rq4` | 418 | `supp:rq4` | 3 |
| `sec:eval-provable` detail | ~170 | `supp:provable-detail` | 0 |

Each left a pointer that keeps the main text self-contained:

* **RQ3** restates both barrier costs with their intervals, so the cost claim
  stands without the deployment table.
* **RQ4** names the outcome classes as the ones `tab:outcomes` already counts.
* **The provably-empty cell** keeps its *result* in §VI — "the cell is empty in
  the world and unresolvable from the store" — and moves only the reasoning and
  the third-barrier trade.

**`fig:bycrashpoint` stayed in the paper.** It sits inside the provably-empty
block but is referenced from RQ1, which is one of the four protected blocks, and
a protected block must remain followable from the main text alone. Moving the
figure would have bought ~0.29 pages at the cost of that property.

## 3. Per-change page table

| # | change | words | main | supp |
|---|---|---|---|---|
| 1 | caption `\cref`s → by name | 0 | 25 | 5 |
| 2 | `sec:eval-deployment` migrated | −827 | **24** | **6** |
| 3 | `sec:eval-rq4` migrated | −362 | **23** | 6 |
| 4 | `sec:eval-provable` detail migrated | −67 | 23 | 6 |
| | **total** | **−1 256** | **25 → 23** | **5 → 6** |

Changes 1 and 4 delivered zero pages on their own and are reported as they
happened. Change 1 delivered none because it moves no text — it is what made
change 2 possible.

## 4. Integrity

**Macro multiset across both documents:** 320 uses / 197 distinct before,
**322 / 197 after**. Two macros gained a use and **none lost one**:

```
BarrierCostFifteen            5 -> 6
BarrierCostAlwaysFortyFive    2 -> 3
```

Both are the RQ3 pointer restating the barrier costs with their intervals, so
the claim survives the deployment table's departure. **No macro changed value
and no number left the paper** — which is the bound, stated precisely rather
than as "identical".

```
citations                371/0
check_paper_numbers      43 passed, 0 failed
cross-document checks    all three PASS at every committed point
generated/ hand-edited   none
```

## 5. M5 amended, WS-9 closed

`docs/26` M5 now carries the ruling:

> **The 16-page target is withdrawn on evidence.** Three passes measured the
> same exchange rate, ~950 words per page … Reaching 16 needs ~5 000 further
> words, and there is nowhere to take them from except §VI's four headline
> blocks (4 035 words) and §VII's positioning (1 498). **That is a scope
> decision — which results are main text — not a compression problem, and the
> author declined it.** A 16-page version of this work exists; it is a different
> paper. **The revised target is 23 pages.**

§7's length box is **amended, then ticked against the amended target**, with the
amendment stated in the box itself so nobody reads it as the original being met.
A second line closes WS-9: tone complete, compression complete, migration
complete to the floor.

## 6. Not done, and why

* **§IV's transition table (~400 w) and §III/§V tightening (~400 w)** were on
  phase 32's available list and were not reached. Together they are worth
  roughly 0.8 of a page, and the pass's remaining room went into the three
  migrations, which were worth more.
* **§VII's distinguishing prose (~600 w)** was explicitly not touched, as step 4
  allowed. Phase 32 protected the durability-acknowledgements and exactly-once
  blocks because they are what tell a reviewer the paper is not a restatement of
  known results, and that judgement stands.
* **22 pages, the bottom of the estimated range, was not reached.** 23 is where
  the measured items ran out. The estimate was 21–22 and the outcome is 23,
  which is the estimate being slightly optimistic rather than the work stopping
  early: item 4 above accounts for the difference almost exactly.

## 7. Raw outputs

```
pages                    main 25 -> 23    supplementary 5 -> 6
sections total           22 529 -> 21 288 words
check_paper_numbers.py   43 passed, 0 failed
validate_citations.py    OK: 371 citations, 0 invalid
new tests                tests/test_deployment_caption_is_portable.py, 4 passed
full suite               2 065 passed, 34 skipped, exit 0
builds                   supplementary, supplementary-anon, anon, main -- all exit 0
macro multiset           320/197 -> 322/197, two gained a use, none lost one
macros changed in value  0
protected and unmoved    §VI RQ1, detection, prevention, durability; §VII's
                         1 498 w of WS-8 positioning; fig:bycrashpoint
```
