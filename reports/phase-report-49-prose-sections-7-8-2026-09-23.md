# Phase 49 — §VII and §VIII rewritten

**No live calls.** `origin/main == HEAD` at `2803932` confirmed before any edit.
Three commits.

| | |
|---|---|
| §VII | em dashes **28 → 0** |
| §VIII | em dashes **25 → 0** |
| deferred items | both closed by the author's ruling; **nothing changed** |
| `claims-to-review.md` | **entry 3 added** |
| pages | main **24**, main-anon **24**, supplementary **7 / 7** |
| suite | **2593 passed, 34 skipped** |

**One incident is written up in §7 below: the anonymous gate destroyed
uncommitted §VIII edits.** It was caught, the work was re-applied, and the
hazard is now documented.

---

## 1. The two deferred items — closed, nothing changed

Recorded here as instructed, with no edit made.

**§VI's 25 bold paragraph leads stay as they are.** Each is a run-in lead or a
result stated against a reader's expectation. The density is §VI's own
convention for structuring a results section and it is not revisited.

**Emphasis is not restored on the B5 bounds.** Four marks in one paragraph is
heavy; if the four-item list is hard to follow, the fix is wording rather than
emphasis. `\emph{incomplete}` stays removed and the other three bounds stay
unmarked.

---

## 2. §VII — before and after

| metric | before | after |
|---|---|---|
| words | 3204 | 3182 |
| sentences | 116 | 124 |
| **em dashes** | **28** | **0** |
| em dashes per page | 6.55 | **0.0** |
| mean sentence length | 27.6 | 25.7 |
| sd | 14.3 | 13.2 |
| shortest / longest | 5 / 71 | 5 / 69 |
| corrective constructions | 21 | **21** |
| flagged vocabulary | 3 | **1** |
| `\emph` | 19 | 19 |
| `\textbf` | 3 | 3 |

**Invariants:** 51 citation keys, 5 `\cref` targets, 1 label, 4 numbers — all
identical to `HEAD`.

### No characterisation of cited work changed

Every em dash that set off an attribution became a colon, parentheses or a
sentence, and the attributed content is unchanged:

* **Chubby's sequencer** keeps all three parts (lock name, generation number
  that changes on every transition from free to held, acquisition mode) and the
  requirement that *the file server is expected to validate it*. The `\emph`
  on that requirement is preserved, moved with the clause.
* **`lock-delay`** keeps *"merely withholds a lock for a bounded period after an
  abnormal release"* and *"which that paper calls imperfect"*.
* **Rebello et al.** keeps *"none of five widely deployed applications"* and all
  five names, now parenthesised because the list has internal commas.
* **Spanner** keeps its qualification, now *"It is, however, built by an
  operator who controls every participant"*.
* **ExoFlow, Restate, DBOS, Beldi, Boki, Durable Functions** keep their
  characterisations and the direction of every contrast with AEP.

### Two flagged words removed, one kept

| word | decision |
|---|---|
| *Notably the draft mandates little beyond publication* | **removed** — the adverb asserted significance the sentence then demonstrates |
| *precisely the one that cannot* | **removed** → *exactly* |
| *no retry discipline on the caller's side* | **kept** — the ordinary noun, not the tic `docs/37` §6 flags |

**The three American spellings are untouched**, as instructed: `realized`
(l. 140), `formalizes` (l. 226), `characterizes` (l. 230). They belong to the
mechanical spelling pass.

---

## 3. §VIII — before and after

| metric | before | after |
|---|---|---|
| words | 3234 | 3213 |
| sentences | 118 | 120 |
| **em dashes** | **25** | **0** |
| em dashes per page | 5.80 | **0.0** |
| mean sentence length | 27.4 | 26.8 |
| sd | 14.2 | 13.7 |
| shortest / longest | 5 / 68 | 5 / 68 |
| corrective constructions | 33 | **33** |
| flagged vocabulary | 4 | **1** |
| `\emph` | 22 | 22 |
| `\textbf` | 4 | 4 |

**Invariants:** 18 `\cref` targets, 1 label, 1 citation key, 41 numbers, 24
provenance comment lines — all identical to `HEAD`.

### No limitation weakened

Every restructure was checked against the disclaimer it carries:

* **The layering paragraph** still declines both claims it declined — absolute
  fsync latency on real hardware, and that a real power cut cannot do worse.
  The two are now separated by a semicolon rather than interrupted by an aside.
* **The `drop_writes` emulation** still lists what it is faithful to and what it
  is not, with the faithfulness pair parenthesised.
* **The write-loss threat** still says *"this paper contains no evidence about
  storage that does not"* report its own failures.
* **The unrun arm** still says it *"was designed and not run"* with all three
  reasons.
* **The ablation's cost** still *"applies to the claim this paper most depends
  on"*.

**Appositions with internal commas became parentheses, not comma-wraps**, because
comma-wrapping a list inside a list is ambiguous: the `drop_writes` faithfulness
pair, the mock provider's realistic dimension, the controlled fault's landing
figures, and the voided run's three artifacts.

### Three flagged words changed, one kept

| word | decision |
|---|---|
| *the paper's most load-bearing empirical claim* | → *the claim this paper most depends on*. Plainer, same claim, same referent |
| *lock keys are deliberately not barriered* | → *by design*, matching the same change already made in §IV |
| *We stopped at four sessions deliberately rather than for want of machine time* | → *by choice*. **Replaced rather than deleted**: the contrast is the disclosure, and deleting the word would break the sentence |
| *silently inflating wall-clock durations* | **kept** — it describes the failure mode literally, and in a limitations section precision wins |

---

## 4. Correctives kept — 54, and the count is unchanged in both sections

### §VII, 21 — the contrast usually *is* the comparison with prior work

| construction | why it stays |
|---|---|
| *fencing protects the store, not an endpoint that never interprets the token* | the boundary B1 and B2 measure |
| *a timing heuristic, not a guarantee* | what Chubby's `lock-delay` is, and is not |
| *prior work, not AEP's novelty* | the concession about Olive |
| *semantic controls, not claims about those products' complete implementations* | the scope of B4 and B4b |
| *The axis is not feature coverage but what each assumes of the invoked step* | the organising claim of the subsection |
| *epistemic rather than engineering* | why exactly-once delivery is unobtainable |
| *the residual is not a weaker delivery guarantee but an unanswered question about an effect* | the distinction the whole paragraph exists for |
| *which is the problem rather than an oversight* | why no crash-consistency model exists to write litmus tests against |
| *an evaluation instrument rather than a claimed contribution* | the scope of the harness |
| *adjacent rather than a basis for ranking which work is "nearest"* | the ACRFence placement |
| *in that line rather than beside it* | where the durability result sits |
| + 10 more of the same kind | |

### §VIII, 33 — scope disclaimers almost without exception

`rather than` 21, `X, not Y` 10, `instead of` 1, `is not A, it is B` 1. A
limitations section states what a result is *not*, so the corrective form is
the content: *"an emulation… faithful where it matters and unfaithful in that
real power loss can tear a sector"*, *"a configuration change rather than a
fault"*, *"the fix is HA rather than anything local"*, *"reported as a bound
rather than as a test"*, *"for reasons of precision rather than of effect"*.

**Neither count moved, and that is the expected result**, not a failure to
edit.

---

## 5. Meaning-risk list — least sure first

### 5.1 The layering paragraph's two disclaimers — least sure

> **Before:** …a claim about absolute fsync latency on real hardware, which we
> do not make from this probe --- the barrier's cost comes from the deployment
> table in the supplementary material --- or a claim that a real power cut
> cannot do worse, which we explicitly do not make above.
>
> **After:** …a claim about absolute fsync latency on real hardware, which we do
> not make from this probe, **since** the barrier's cost comes from the
> deployment table in the supplementary material**;** or a claim that a real
> power cut cannot do worse, which we explicitly do not make above.

The original's aside interrupted an *either X or Y* structure. *"since"* makes
the aside a reason, and the semicolon holds the two alternatives apart. **Both
disclaimers survive intact**, but the sentence is long and the *"or"* now sits
across a semicolon, which is the construction I am least confident reads
cleanly.

### 5.2 "load-bearing" became "the claim this paper most depends on"

> **Before:** …it applies to the paper's most load-bearing empirical claim.
>
> **After:** …it applies to the claim this paper most depends on.

Same referent, same superlative, plainer word. Flagged because it is in a
limitation and any shift in a limitation matters.

### 5.3 The six named gaps re-punctuated

> **Before:** six named gaps --- five since closed and recorded there with what
> closing them changed, one still open: one run that did not complete.
>
> **After:** six named gaps: five since closed and recorded there with what
> closing them changed, **and** one still open, a run that did not complete.

The colon moved from the inner clause to the outer one. Counts and content
unchanged.

### 5.4 §VII's three framing questions lost their dashes

Each was `\textbf{Question?} --- answer`. The first now reads *"A mechanism may
need idempotence, an idempotency key, enrolment in a transaction, or a
compensating action, and one that needs any of these does not apply where none
can be obtained."* The four options and the consequence are unchanged; the
sentence is assembled rather than appended.

### 5.5 The B5 result sentence split

> **Before:** …one attempt lost and duplicated nothing --- each landing in the
> corner the supplementary comparison assigns it --- while the rates were
> several times below…
>
> **After:** …and one attempt lost and duplicated nothing, each landing in the
> corner the supplementary comparison assigns it. The rates were several times
> below…

The *"while"* contrast is carried by the paragraph's lead sentence, *"The
direction transferred and the magnitudes did not"*, which is two lines above.

---

## 6. Cut candidates — **none applied**

### §VII, 268 words

| # | candidate | words | restates | against cutting |
|---|---|---|---|---|
| 1 | The Stripe and Adyen contract details | 96 | nothing | They are the evidence that the same header name carries different guarantees, which is the paragraph's claim |
| 2 | *"Why not two-phase commit"*'s second paragraph on Spanner | 76 | nothing | It forestalls *"but Spanner does it"*, which a reviewer will raise |
| 3 | The workflow-management-systems sentence | 44 | **§VII's own compensation paragraph** already places sagas | It is the historical bridge; without it the durable-execution line starts in 2016 |
| 4 | *"Fault-injection lineage"*'s FATE / LDFI / Elle comparisons | 52 | nothing | Each names a specific method this work is not, which is what a related-work section is for |

### §VIII, 301 words

| # | candidate | words | restates | against cutting |
|---|---|---|---|---|
| 5 | The kill-latency attribution's interval detail | 88 | **§VI-C.2** gives the same figures | §VIII's use is different: §VI reports the attempt, §VIII reports that it failed at this precision |
| 6 | *"B4 is our model of a durable-execution engine, and the real one"* | 84 | **§VI-B.1**'s B5 paragraph | §VI states the result, §VIII states the threat it leaves. Removing it would leave the threat unstated |
| 7 | The voided-run description | 71 | **the supplementary's RQ4 section** carries the incident in full | §VIII's two sentences are what make the oracle-independence claim checkable rather than asserted |
| 8 | *"Concurrency coverage is narrow"* | 58 | nothing | A reviewer will ask what concurrency was exercised; this answers it |

**Total 569 words.** My view: **none should be cut.** 5, 6 and 7 are each the
threat-side counterpart of a result stated in §VI, and a limitations section
that omits them would be weaker in exactly the way §VIII exists to prevent.

---

## 7. An incident: the anonymous gate destroyed uncommitted §VIII edits

**Caught, recovered, and now documented.** Reported in full because it will
recur otherwise.

### What happened

`scripts/prove_anonymous_gate.sh` proves its four anonymity checks can fail by
inducing each failure and restoring. **Its staleness fixture is
`paper/sections/08-threats.tex`**: it appends to that file to make the
anonymous build stale, then restores with

```sh
git checkout -- paper/sections/08-threats.tex     # lines 33 and 82
```

I ran the gate with §VIII rewritten but **not yet committed**. The `git
checkout` reverted the file, and the first gate run exited *"tree not
restored"* because its own backup of `main-anon.pdf` predated my rebuild.

### How it was caught

`git status` after the gate showed `07-related.tex` modified and
`08-threats.tex` **absent from the list**, which is impossible if both had been
edited. Re-running the em-dash count confirmed §VIII was back at 25.

### Recovery

The rewrite is script-applied, so re-running it reproduced the file exactly;
the invariant check then confirmed 18 `\cref`, 1 label, 1 cite, 41 numbers and
24 provenance comments identical to `HEAD`.

### The rule this establishes

**Commit `paper/sections/08-threats.tex` before running
`prove_anonymous_gate.sh`, or run the gate first.** In every earlier session
§VIII happened to be committed when the gate ran, which is why this never bit
before. For this session §VII was committed with §VIII stashed, then §VIII was
committed, and only then was the gate run — which passed and left the tree
clean.

**No work was lost and nothing was silently changed.** Both files are committed
in the state the builds and checks were run against.

---

## 8. `claims-to-review.md` — entry 3 added

**`voided/` still renders in §VIII, after the same path was removed from the
supplementary.**

`08-threats.tex` renders *"in the published archive under `\texttt{voided/}`"*.
The supplementary said `\texttt{results/voided/}` until the path-removal pass
on 2026-09-22, which replaced it with prose.

`check_no_repo_paths.py` did not catch it: its pattern requires a known
repository directory before the slash, `results` is in that list and `voided`
is not. **The check is behaving as written.** Whether it *should* fire turns on
whether `voided/` names a location in the published archive that a reader needs
in order to follow the pointer, which a prose pass cannot decide. Three options
are set out in the entry, including whether the checker should gain an
allow-list so the distinction is enforced rather than accidental.

Entries 1 and 3 are **open**; entry 2 remains **RESOLVED**.

---

## 9. Where the manuscript stands

| file | em dashes | passed |
|---|---|---|
| `01-introduction` … `06-evaluation` | **0** | yes |
| `07-related` | **0** | **yes, this session** |
| `08-threats` | **0** | **yes, this session** |
| `09-artifact` | 8 | no |
| `main.tex` | 6 | no |
| `supplementary` | 38 (42 raw) | no |

**§I–§VIII are done.** What remains is §IX, `main.tex`'s front matter, and the
supplementary.

---

## 10. Verification

| | |
|---|---|
| live calls | **none** |
| `origin/main == HEAD` before starting | confirmed at `2803932` |
| spelling | British `-ise` untouched, including §VII's three slips |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `prove_anonymous_gate.sh` | **green, tree restored clean** (run after both commits) |
| full suite | **2593 passed, 34 skipped** |
| cut candidates applied | **none** |
