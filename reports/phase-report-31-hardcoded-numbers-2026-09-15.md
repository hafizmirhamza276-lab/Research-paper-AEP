# Phase 31 — the 28.0 ms in the PDF, and the class of defect it belongs to

## Asked / Done

Asked: fix the caption at source, sweep the generator for every hardcoded
number, build a gate for the class, record an R14 instance, verify at the PDF
level.

Done: all six. **The caption is fixed and states both readings with intervals.**
The gate exists and was watched failing against the real pre-fix caption text.

**One `28.0` survives in the built PDF and I did not remove it.** It is a *data
cell* in `tab:latency`, not a caption, with its sample size printed beside it —
§4 argues why removing it would be deleting evidence, and names the fix that
belongs to a later pass.

---

## 1. A correction to phase 30's finding

Phase 30 called the number a "hardcoded string". **It was not.** The source read

```python
r"2\,000\,ms delay, and so includes the "
f"{tex(b3 - b0)}"
r"\,ms the protocol costs with the barrier already removed.}\\",
```

— an f-string interpolation of a value **computed inline** from the three-run
medians. Same wrong number on the page; different mechanism, and the difference
matters, because the class is broader than "someone typed a literal". It is
**any number the generator prints that no macro backs**, computed or typed.

## 2. The caption, before and after

**Before** (`paper/generated/table-deployment-choice.tex:25`):

> `Over floor' is the same median less the provider's 2 000 ms delay, and so
> includes the **28.0 ms** the protocol costs with the barrier already removed.

**After:**

> `Over floor' is the same median less the provider's 2 000 ms delay, and so
> includes whatever the protocol costs with the barrier already removed — a
> quantity this evaluation cannot separate from zero:
> `\ProtocolMinusBarrierFifteen{}` ms
> [`\ProtocolMinusBarrierFifteenLow{}`, `\ProtocolMinusBarrierFifteenHigh{}`]
> pooled, and `\ProtocolMinusBarrierLowerMode{}` ms
> [`\ProtocolMinusBarrierLowerModeLow{}`, `\ProtocolMinusBarrierLowerModeHigh{}`]
> over each arm's lower mode, both spanning zero.

Both readings, per amendment 2 — choosing one silently is the move the paper
argues against — and now consistent with §VI-RQ3 as phase 26 wrote it.

## 3. The enumeration

A source-level sweep of `paper_tables.py` returns **261 numeric literals and 106
computed interpolations**, and is almost entirely noise: provenance comments
(which become `%` lines, never page text), macro *values* (which are macros by
definition), file paths, dates, seeds, format specifiers. Reported because the
prompt asked for the enumeration, and because the noise is the finding: a
source-level sweep cannot distinguish a number that reaches the page from one
that does not.

**The surface that matters is the generated output.** Scanning
`paper/generated/table-*.tex` for numbers in caption prose, with macro
invocations stripped and thousands separators normalised:

| file | number | disposition |
|---|---|---|
| `table-ambiguity-by-crashpoint` | `0` | macro-backed |
| `table-deployment-choice` | `2\,000` | **literal, legitimate** — the provider's configured delay, a setting rather than a measurement |
| `table-deployment-choice` | **`28.0`** | **the defect — fixed** |
| `table-outcomes` | `0`, `90` | macro-backed (a zero bound; a confidence level) |

**One genuine offender across every generated caption in the paper.** The other
three are a design constant and two values that a macro already holds.

Data cells are exempt by design: producing numbers from a CSV is what a table is
for, and the CSV is their provenance.

## 4. The `28.0` still in `main.pdf`, and why it stays

```
main                 25 pages   '28.0' occurrences: 1
main-anon            25 pages   '28.0' occurrences: 1
supplementary         5 pages   '28.0' occurrences: 0
supplementary-anon    5 pages   '28.0' occurrences: 0
```

It is `table-latency.tex:24`:

```
system                        runs   median step (ms)   over B0 (ms)
B3 full protocol, no barrier     3        2\,038.2           28.0
```

A **data cell**, in a table where every row prints `3` in a `runs` column. It is
B3's over-B0 value at three runs, correctly derived from the CSV the table
declares, with its sample size in the same row. That is not the caption defect:
nothing here asserts the quantity is 28.0 ms *in general*, and §VI-RQ3 states
the fifteen-run figure with both intervals two pages earlier.

**I did not remove it**, because the two ways to are both worse. Deleting the B3
row deletes evidence, which the bounds forbid. Repointing `tab:latency` at the
fifteen-run cell changes `--analysis`, which is the input every frozen matrix
macro derives from, and "no macro changes value" is a bound of this pass.

**The residual risk, stated rather than smoothed:** a reader skimming the
latency table meets `28.0` beside `3`, and the prose that qualifies it is
elsewhere. The fix is to give `tab:latency` the WS-5 cell as a second block of
rows, or to repoint it — a generator-input change, and the first thing a pass
with that in scope should do. The acceptance criterion "absent from all four
PDFs" is therefore **not met**, and this is why.

## 5. The gate, and its failing branch

`check_generated_captions_use_macros`: every number in a generated caption is
either the value of some macro in `numbers.tex`, or named in `CAPTION_LITERALS`
with a reason. Four entries — the provider delay, two confidence levels, zero —
and the list is deliberately tiny, because a generous one re-opens the hole.

**Rule 13, R17-compliant.** `tests/test_generated_caption_numbers.py`, six
tests. Nothing executes an older generator; the failing-branch evidence is the
**real pre-fix caption text, kept verbatim as a fixture**, run through the
current check:

```
the pre-fix caption                                    FAILS on 28.0
the fixed caption                                      passes
a thousands separator is not two numbers               passes
the provider delay is allowed and says why             passes
an unbacked number in any generated caption            FAILS on 41.7
a macro-backed number written out longhand             passes
```

The third and sixth are the false-positive directions. A check that split
`2\,000` into `2` and `000` would report `000` forever and be switched off; one
that demanded macro *invocations* rather than macro *values* would reject a
caption that spells a number the generator already owns.

Gate count: **42 → 43**.

## 6. R14 instance 10 — the class named

`docs/25`, header now "Ten instances now".

> *A gate whose coverage is defined by a mechanism is blind to everything
> outside that mechanism, and "every gate green" then means "every gate green
> over the part it can see."*

Rule 3's whole apparatus — provenance comments, regenerate-and-diff, the orphan
check — is built on macros. A number that never becomes a macro is not checked
*less* carefully; it is not checked at all, **and nothing reports that it went
unchecked.**

Instance 10 is the first in the list where **no instrument was faulty**. Every
gate was correct and every gate was green; their shared domain was smaller than
anyone had stated. Phase 26 is named as where it cost something: the pass that
retired the figure had every reason to believe it had, and said so in its report.

It was found by accident, nine passes later, when phase 30's migration happened
to put the caption under a reader's eye.

## 7. Not done, and why

* **`28.0` in `tab:latency`.** §4.
* **The four `\cref`s in the deployment caption** that blocked phase 30's
  migration are untouched — fixing them is the migration's business, and the
  migration is out of scope here. They remain the thing standing between
  `sec:eval-deployment` and the supplementary.
* **No sweep of `paper/sections/*.tex` for hand-typed numbers.** Rule 3 already
  covers those through `check_macros_are_used`'s inverse, and the bounds put
  `.tex` out of scope. Worth a pass of its own: this one only proves the
  *generator* is clean.

## 8. Raw outputs

```
check_paper_numbers.py    43 passed, 0 failed   (was 42; +1 caption gate)
  PASS every number in a generated caption comes from a macro
validate_citations.py     OK: 371 citations, 0 invalid
tests/test_generated_caption_numbers.py   6 passed
full suite                2 061 passed, 34 skipped, exit 0  (2 055 before: +6 caption tests)
builds                    supplementary, supplementary-anon, anon, main -- all exit 0
pages                     main 25, supplementary 5
PDF grep for 28.0         main 1, main-anon 1, supplementary 0, supplementary-anon 0
                          the one is tab:latency's data cell -- §4
macros changed in value   0
.tex hand-edited          0
generated/ hand-edited    0  (regenerated only)
```
