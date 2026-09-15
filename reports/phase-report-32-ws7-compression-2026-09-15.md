# Phase 32 — §VII compression, and the floor stated with its arithmetic

## Asked / Done

Asked: measure §VII by subsection, compress surveys first, protect the WS-8
positioning, per-change page table, state the floor honestly.

Done: all of it. §VII is **3 655 → 3 420 words**, four survey passages
compressed, **54 citation keys unchanged and none dropped**, the WS-8 positioning
intact.

**Pages: 25 before, 25 after.** §6 gives the arithmetic for what is reachable
and what is not, and the answer is that **16 pages cannot be reached without
cutting evidence.**

---

## 1. §VII, measured before cutting

3 655 words in ten blocks. What each is doing for the paper decides whether it
compresses:

| block | words | cites | doing what |
|---|---|---|---|
| section intro | 217 | 0 | framing |
| Leases and fencing | 312 | 5 | survey + **distinguishing** (the Chubby fencing argument) |
| Logging, outboxes, compensation | 295 | 8 | **survey** |
| Idempotency-key contract | 338 | 3 | **WS-8 positioning — protected** |
| Why not two-phase commit | 247 | 3 | **WS-8 positioning — protected** |
| Locks with intent, durable-orchestration line | 913 | 14 | **WS-8 positioning — protected** |
| Agent execution reliability | 200 | 4 | **survey** |
| Durability acknowledgements | 256 | 5 | distinguishing |
| Exactly-once: state, delivery, effect | 350 | 5 | distinguishing |
| Fault-injection lineage | 409 | 7 | **survey** |

**1 498 words are WS-8 positioning and were not touched.** They are the
section's reason to exist: the durable-orchestration line, what an
idempotency-key contract requires of the *server*, and why not two-phase commit.
A reviewer checks those; compressing them would be deleting the argument to save
a quarter page.

## 2. What was compressed

| passage | before | after | citation keys |
|---|---|---|---|
| Fault-injection lineage | 409 | ~190 | 7 kept |
| Compensation (Gray / Korth / Sagas) | ~200 | ~120 | 5 kept |
| Agent execution reliability | ~185 | ~120 | 3 kept |
| Lease inventory | ~95 | ~55 | 4 kept |

Each collapses a list-of-systems into its claim. The fault-injection lineage
went from four methods each given its own clause to one sentence with four
citations and the one observation that matters — *a legacy endpoint publishes no
crash-consistency model to write litmus tests against, which is the problem
rather than an oversight.* The compensation passage kept every premise of its
argument and dropped the restatement of three formalisms a reader can look up.

**What was protected, beyond the three WS-8 blocks:** the Chubby fencing
argument in "Leases and fencing". Only its opening inventory was compressed. The
argument — that a fencing token protects a resource only if the resource checks
it, which makes fencing a property of the *resource*, and that Chubby itself
ships lock-delay as an imperfect fallback — is the closest prior art to this
paper's setting and is what B1 and B2 measure.

## 3. Per-change page table

| # | change | words | pages |
|---|---|---|---|
| 1 | fault-injection lineage | −219 | 0 |
| 2 | compensation survey | −80 | 0 |
| 3 | agent-work survey | −65 | 0 |
| 4 | lease inventory | −40 | 0 |
| | **total** | **−235** | **0** |

§VII 3 655 → 3 420 words; sections total 22 764 → 22 529. Main stayed at 25
pages throughout, which is consistent with phase 27's measured rate: 235 words
is about a quarter of a page.

## 4. Citations

```
before: 54 keys    after: 54 keys    dropped: none    added: none
validate_citations.py: OK: 371 citations, 0 invalid
```

Nothing left the bibliography. Four passages now cite in groups where they
previously cited in sequence, which is a typographic change and not a
bibliographic one.

## 5. Zero numeric claims changed

`07-related.tex` contains exactly one macro invocation, before and after,
identical. The compressions touched prose and citation grouping only.

## 6. The floor, with its arithmetic

This is the third pass to report a floor, and the three together now bound it
from evidence rather than estimate.

**Measured exchange rate** (phase 27, confirmed twice since): ~950 words per
page. 22 529 words of sections plus 12 floats across 25 pages.

**What cannot be cut:**

| protected | words | why |
|---|---|---|
| §VI's four headline blocks | 4 035 | RQ1, detection, prevention, durability — the evidence the paper exists to present |
| §VII's WS-8 positioning | 1 498 | the durable-orchestration line, the idempotency-key contract, why not 2PC |
| every numeric claim and its interval | — | bounds of every pass since phase 24 |

**What is still available, and what it is worth:**

| available | words | pages | status |
|---|---|---|---|
| §VI migration (`sec:eval-deployment`, `sec:eval-rq4`, `sec:eval-provable`) | ~1 700 | 1.8 | **blocked** — the deployment caption `\cref`s four main-text labels from inside `generated/`, phase 30 §2 |
| §VII distinguishing prose, tightened further | ~600 | 0.6 | available, with care |
| §IV's transition table to the supplementary | ~400 | 0.4 | available |
| §III, §V tightening | ~400 | 0.4 | available |
| **total** | **~3 100** | **~3.2** | |

**So the reachable floor is about 21–22 pages**, and reaching even that needs
the generator change phase 30 identified.

**The distance from there to 16 is ~5 000 words, and there is nowhere left to
take it from except the four headline blocks and the positioning.** That is not
a length problem this paper can solve by editing; it is a scope decision — which
results go in the main text and which become supplementary — and it belongs to
whoever decides what the paper claims, not to a compression pass.

The honest statement for `docs/26` M5: **16 pages is not reachable while §VI
presents four measured guarantees and §VII positions against durable-execution
engines.** A 16-page version exists, but it is a different paper.

## 7. Not done, and why

* **≤ 16 pages.** §6.
* **§VII's distinguishing blocks** — durability acknowledgements (256 w) and
  exactly-once (350 w) — were not compressed. They are the passages that tell a
  reviewer why the paper is not a restatement of known results, and ~600 words
  of them is worth more than 0.6 of a page. Available if the scope decision in
  §6 goes the other way.
* **§IV's transition table** was not moved. It is on the available list and was
  not reached.

## 8. Raw outputs

```
check_paper_numbers.py    43 passed, 0 failed
validate_citations.py     OK: 371 citations, 0 invalid
builds                    supplementary, supplementary-anon, anon, main -- all exit 0
pages                     main 25 -> 25    supplementary 5 -> 5
07-related.tex            3 655 -> 3 420 words   (359 -> 340 lines)
sections total            22 764 -> 22 529 words
citation keys in §VII     54 -> 54, none dropped
macro invocations in §VII 1 -> 1, identical
WS-8 positioning          3 of 3 passages present
.tex hand-edited          07-related.tex only
generated/ hand-edited    none
```
