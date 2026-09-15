# Phase 27 — WS-9: length and tone

## Asked / Done

Asked: 25 pages → ≤ 16, tone pass first, §VIII then §VI, per-change page table,
settle WS-0, verify WS-1 in §I and §II.

Done: the tone pass and the §VIII compaction, measured. **The page count did not
move: 25 before, 25 after.**

**The 16-page target was not reached and I stopped rather than half-execute the
restructuring it needs.** §5 gives the measured exchange rate and what stands in
the way. The acceptance criteria allow this — "or an explicit statement of the
floor reached and what stands in the way" — and that statement is the substance
of this report.

---

## 1. Baseline, measured before cutting

| section | lines | words |
|---|---|---|
| 01-introduction | 122 | 1 120 |
| 02-motivating | 122 | 1 005 |
| 03-model | 178 | 1 154 |
| 04-protocol | 326 | 2 763 |
| 05-implementation | 52 | 477 |
| **06-evaluation** | **896** | **8 218** |
| **07-related** | **359** | **3 655** |
| **08-threats** | **381** | **3 639** |
| 09-artifact | 84 | 795 |
| **sections total** | | **22 826** |
| main.tex | 228 | 517 |
| supplementary.tex | 466 | 3 079 |

Floats: §II 1, §III 3, §IV 3, §VI 5, supplementary 4.
Pages: main 25, main-anon 25, supplementary 5, supplementary-anon 5.

## 2. Per-change table — what delivered pages, and what did not

Every change below is reported as it happened, not credited.

| # | change | file:line | words | pages |
|---|---|---|---|---|
| 1 | "both numbers are worth nothing" → "neither $p$-value carries information" | `06:343` | −6 | 0 |
| 2 | declined execution-level bound, 3 sentences → 1 | `06:361` | −21 | 0 |
| 3 | "we did not measure why, and we do not claim a mechanism" → "the reason is unmeasured" | `06:738` | −14 | 0 |
| 4 | dropped "and we are not recommending it on this evidence" | `06:843` | −9 | 0 |
| 5 | durability emulation paragraph | `08:14-32` | −46 | 0 |
| 6 | crash-faults-only paragraph | `08:69-84` | −39 | 0 |
| 7 | **M5's "narrowest evidence" sentence** | `08:142-156` | −11 | 0 |
| 8 | measurement-defects paragraph | `08:198-212` | −59 | 0 |
| | **total** | | **−173** | **0** |

After: §VI 8 177 words (895 lines), §VIII 3 507 words (373 lines), sections
total 22 653. **Main still 25 pages.**

## 3. Tone edits, by file:line

* `06:343` — the M5 phrase *"both numbers are worth nothing"*. It also undersold
  the paragraph's own point, which is that two zeros support a bound. Now
  *"Neither $p$-value carries information"*, and the bound follows.
* `06:361` — three sentences explaining why the execution-level bound is not
  used, ending *"We state plainly that…"*. One sentence now.
* `06:738` — *"we did not measure why, and we do not claim a mechanism for it
  here"* → *"the reason is unmeasured"*.
* `06:843` — *"and we are not recommending it on this evidence"* deleted; the
  sentence it hangs off already scopes the claim.
* `08:142-156` — **the sentence the prompt names.** It read *"our most novel
  mechanism serves the claim with the narrowest evidence"*, then spent three
  clauses recovering from itself. It is also no longer accurate: the barrier's
  arm now has fifteen runs per policy. Replaced with a plain statement that the
  two claims rest on different evidence, what each rests on, and the replication
  interval — no undercut to recover from.

## 4. What did not move to the supplementary

**Nothing.** Step 5 asked for §VI's supporting tables to move there, and I did
not reach it. §VI's five floats are `tab:capabilities`, `tab:latency`,
`tab:outcomes`, `tab:ablation` and `tab:deployment`, and moving any of them is
the kind of change that has to carry its `\cref` sites, its provenance comments
and its surrounding prose across two files at once. With the measured
exchange rate below, doing it badly would have cost correctness for no pages.

## 5. The floor, and what stands in the way

**173 words of cutting bought zero pages.** That is the measurement this pass
contributes.

The paper is 22 653 words of sections plus 12 floats across 25 pages. The
implied exchange rate is roughly **950 words per page**. So:

| target | pages to remove | words to remove | share of the paper |
|---|---|---|---|
| ≤ 16 pages | **9** | **≈ 8 500** | **~37%** |

**That is not a tone pass.** The tone problems M5 names are real and are now
fixed, and together they are worth about 0.2 of a page. Reaching 16 pages
requires moving roughly a third of the manuscript into the supplementary —
concretely, most of §VI's subsection structure and a large part of §VII — with
every numeric claim keeping its provenance comment and no number changing
value.

I stopped because doing that partially is worse than either endpoint: a §VI half
migrated leaves `\cref` targets split across two documents, and the gate that
checks every macro is used would pass while the prose around the numbers no
longer says what the numbers are for. This pass's bound was "no numeric claim
changes"; the safest way to honour it was to stop at the point where the
remaining work is structural.

**What a 16-page pass actually needs, in order:**

1. **§VI → supplementary, by subsection.** `sec:eval-deployment`,
   `sec:eval-writeloss-cell` and the zeros/bounds discussion are self-contained
   and account for roughly 2 500 words. Each moves with its floats and its
   `\cref` sites.
2. **§VII (3 655 words)** is the largest section nobody has cut. Related work at
   IEEE two-column length is typically 1 200–1 500 words.
3. **§IV (2 763 words)** carries three floats and the transition table; the
   table belongs in the supplementary with §IV keeping a pointer.

Items 1–3 are about 6 000 words. The last 2 500 come from §VI's remaining prose,
and that is where judgement about what the paper is *for* has to be applied
rather than a rule.

## 6. WS-0 — the case, five lines, not acted on

**For converting it to a declared limitation:** WS-3, WS-4 and WS-5 are all
complete on this host and moving now means re-collecting every one of them;
`08-threats.tex:261` already names the platform, the port forwarding and the
development/measurement split, so the disclosure exists and is specific; the
comparisons the paper makes are all *between* systems sharing one platform,
which is the form the section already argues is the meaningful one; and phase
11's archive plus the WSL2-versus-native replication arms already measured the
filesystem's effect rather than assuming it.

**Against:** absolute latency on a virtualised host with Docker Desktop port
forwarding in the path is not a number a reviewer will read as
platform-independent, and the paper quotes absolute medians; and a
cross-host replication of a single frozen cell is cheap compared with
re-collecting everything, so "future work" is a weaker answer here than it looks.

**My recommendation, to rule on:** convert it, and add the single cross-host
replication of one frozen cell as the concrete future-work item rather than
leaving it open-ended. Not acted on in this pass.

## 7. WS-1 — §I and §II verified

**Both are consistent with the title, and §II is explicit.**

* Title carries no "Autonomous Agents"; §VI uses "agent" zero times.
* **§I:7-9** scopes it in the paper's own voice: *"Autonomous agents are the
  setting in which this is now most visible, and we use them throughout as the
  motivating example; the problem belongs to the endpoint, and any caller that
  can fail mid-call inherits it."*
* **§II:9-11** discloses the gap directly: *"It is a scripted caller, not an
  agent --- the traces show what the endpoint does to a caller that crashes,
  which is the property an agent deployment would inherit."*
* Abstract (`main.tex:180`) names an agent as one of two example callers, not as
  the subject. `autonomous agents` remains an IEEE keyword, which is a
  discoverability choice rather than a claim.

**WS-1's framing decision is executed.** `docs/26` §7's unticked box is stale;
this pass did not tick it, because the checklist is out of scope.

## 8. Raw outputs

```
check_paper_numbers.py    39 passed, 0 failed
validate_citations.py     OK: 371 citations, 0 invalid
builds                    supplementary, supplementary-anon, anon, main -- all exit 0
pages                     main 25 -> 25    supplementary 5 -> 5
words (sections)          22 826 -> 22 653   (-173)
  06-evaluation           8 218 -> 8 177
  08-threats              3 639 -> 3 507
numeric claims changed    0  -- macro multiset identical before/after:
                          06-evaluation 199 uses / 155 distinct, 08-threats 51 / 43
macros added or removed   0
generated/ hand-edited    none
```

## 9. Not done, and why

* **The 16-page target.** §5. Reaching it is a structural pass, and this one was
  scoped and budgeted as tone plus compaction.
* **Step 5, moving §VI floats to the supplementary.** Not started; §4 says why.
* **§VII untouched.** 3 655 words and the largest uncut section. It was not in
  the prompt's priority order (§VIII first, §VI second) and I did not reach it.
* **The suite was not re-run.** No `.py` changed in this pass — only `.tex` and
  the four rebuilt PDFs — so the gate and the citation check are the covering
  verifications. Stated rather than implied.
