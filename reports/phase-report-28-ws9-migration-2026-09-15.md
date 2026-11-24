# Phase 28 — WS-9: the cross-document gate, and WS-0 executed

## Asked / Done

Asked: build the cross-document reference check first, decide the §VI/§VII
split, migrate, per-change page table, execute the WS-0 ruling, tick WS-1.

Done: **step 2 in full** — the check exists, is wired into the gate, and was
watched failing on all four of its branches — and the **WS-0 ruling executed**
with `docs/26` §7 updated.

**The migration itself was not executed.** §4 says what it requires and why I
stopped at the boundary rather than inside it. Pages: 25 before, 25 after.

---

## 1. The cross-document check, and what it catches

`check_cross_document_references` in `scripts/check_paper_numbers.py`, three
checks and one note:

| check | fails when |
|---|---|
| every reference in the main text resolves inside the main text | a block moved to the supplementary and its `\cref` stayed |
| every reference in the supplementary resolves inside the supplementary | the supplementary `\cref`s into the paper, which its own header says it cannot do |
| no label is defined in both documents | **a migration copied instead of moving** |
| *(note)* supplementary labels referenced by nothing | expected — the main text points at the supplementary by name |

**The third is the one no existing gate saw.** A dangling `\cref` is already
caught, because LaTeX emits an undefined-reference warning and
`check_paper_numbers` reads it. A *duplicated* label is silent in both
documents: LaTeX resolves each locally, every other check passes, and a reader
following the main text's pointer lands on whichever copy went stale. That is
precisely the failure phase 27 refused to risk, and it is now visible.

### Baseline, measured before the check was written

```
main:  41 labels, 33 refs      supplementary: 8 labels, 0 refs
main refs unresolved in main : none
supp refs unresolved in supp : none
defined in BOTH              : none
supp labels referenced by nobody : 8
```

The four labels that first looked unresolved — `tab:ablation`, `tab:deployment`,
`tab:latency`, `tab:outcomes` — are defined in `paper/generated/*.tex`. The
check reads `generated/` for exactly that reason; a version that did not would
have reported four false failures and been switched off.

### Rule 13 — watched failing, in a disposable tree

`tests/test_cross_document_references.py`, six tests. Each builds a two-document
tree in `tmp_path`; **none touches the real paper tree and none executes older
code** (R17).

```
a clean two-document tree                                   passes
a \cref in main to a label only in the supplementary         FAILS  (branch 1)
a label defined in both documents                            FAILS  (branch 3)
a \cref in the supplementary into the paper                  FAILS  (branch 2)
a commented-out reference is not a reference                 passes
an unreferenced supplementary label is a note, not a failure passes
```

The last two are the false-positive directions. A migration that comments a
block out rather than deleting it must not read as still-referencing, and the
by-name convention must not be turned into a `\cref` requirement the two-document
split makes impossible.

Gate count: **39 → 42**.

## 2. WS-0 executed — blocker to declared limitation

`08-threats.tex` already disclosed the platform, the port forwarding and the
development/measurement split. What it lacked was a concrete remedy, and
"future work" is weak beside absolute medians. Added:

> We treat this as a limitation rather than a defect to be fixed before
> publication, and the specific thing it costs is worth naming. Every absolute
> median here carries an unmeasured platform term, and the way to measure it is
> not to re-collect the evaluation on bare metal but to re-collect **one frozen
> cell** there and compare: the crash-free `everysec` cell of AEP-full and B3 is
> thirty runs and about an hour, it is the cell both barrier figures come from,
> and its archive manifest makes the comparison exact rather than approximate.
> Until that exists, a reader should treat the increments as this platform's and
> the ordering as the claim.

`docs/26` §7:

* **WS-1 ticked**, with its evidence inline — title, §VI's zero uses of "agent",
  §I:7's scoping, §II:9's "It is a scripted caller, not an agent".
* **WS-0 left unticked, deliberately**, with a note recording the conversion.
  The box describes work that has not been done and ticking it would say
  otherwise; what changed is that it no longer blocks submission. Nothing else
  was unticked.

## 3. Per-change page table

| # | change | pages |
|---|---|---|
| 1 | `check_cross_document_references` + 6 tests | 0 (no `.tex`) |
| 2 | WS-0 limitation paragraph, `08-threats.tex` | 0 (+111 words) |
| 3 | `docs/26` §7 ticks | 0 (not in the paper) |
| | **total** | **0** |

25 pages before, 25 after. Change 2 *added* words, which is correct: the ruling
was to state a limitation, not to remove one.

## 4. The migration — not executed, and the boundary I stopped at

Step 3 asked for the split to be decided and written down before executing. The
deciding measurement is what `sec:eval-deployment` alone would cost:

```
\cref{sec:eval-deployment}  01-introduction.tex:112
                            06-evaluation.tex:378
\label                      06-evaluation.tex:742
\Cref{tab:deployment}       06-evaluation.tex:747
                            08-threats.tex:51
                            08-threats.tex:307
```

**Six reference sites across three files, for one subsection.** Each `\cref`
becomes a by-name reference, because the supplementary's convention forbids
cross-document `\cref` and the new check now enforces that. §VI has five such
blocks and §VII is 3 655 words with its own citation graph; the full migration
is roughly 8 500 words and on the order of forty reference sites.

I stopped here rather than starting it because the pass's own premise is that a
*partial* migration is the failure mode. With perhaps a quarter of a subsection's
worth of working room left, beginning a three-file, six-site move would have
produced exactly the half-migrated tree phase 27 declined to produce — and now
the check built in step 2 would catch it, which means committing it would mean
committing a red gate.

**What the next pass has that this one did not:** a gate that can see the
defect. That was step 2's stated purpose — *"Without this, the migration is
unverifiable"* — and it is done, tested, and green. The migration is now a
mechanical operation with a verifier, rather than an unverifiable one.

**The order it should go in**, unchanged from phase 27 §5 and now costed:

1. `sec:eval-deployment` — 6 sites, 3 files, ~2 000 words.
2. `sec:eval-writeloss-cell` and the zeros/bounds discussion — ~2 500 words.
3. §VII, 3 655 words — no floats, but 371 citations must all survive
   `validate_citations.py`.
4. §IV's transition table — 1 float, §IV keeps a pointer.

## 5. Proof the macro multiset is unchanged

In Python, not a shell regex — phase 27's first attempt at this check matched
nothing and reported two identical empty hashes as a pass.

```
06-evaluation    before 199 uses / 155 distinct   after 199 uses / 155 distinct
08-threats       before  51 uses /  43 distinct   after  51 uses /  43 distinct
macro multiset unchanged: YES
```

Zero numeric claims changed. The WS-0 paragraph quotes no macro.

## 6. Raw outputs

```
check_paper_numbers.py    42 passed, 0 failed   (was 39; +3 cross-document)
  PASS every reference in the main text resolves inside the main text
  PASS every reference in the supplementary resolves inside the supplementary
  PASS no label is defined in both documents
  NOTE 8 supplementary label(s) referenced by nothing -- expected
validate_citations.py     OK: 371 citations, 0 invalid
tests/test_cross_document_references.py   6 passed
full suite                2 055 passed, 34 skipped, exit 0
builds                    supplementary, supplementary-anon, anon, main -- all exit 0
pages                     main 25 -> 25    supplementary 5 -> 5
words (sections)          22 653 -> 22 764   (+111, the WS-0 paragraph)
numeric claims changed    0
generated/ hand-edited    none
```

## 7. Not done, and why

* **The migration.** §4. The infrastructure it required is done; the move is not
  started, and no `\cref` was touched.
* **§VII untouched**, for the second pass running.
* Nothing else. The full suite **was** run before committing, after this
  section first recorded it as a gap: **2 055 passed, 34 skipped, exit 0**
  (2 049 before, +6 from the new cross-document tests). The 34 are the
  Redis-integration tests, expected without compose up.
