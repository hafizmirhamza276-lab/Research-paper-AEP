# WS-6 — the real Temporal baseline: what it establishes, and what it does not

**8 September 2026.** Closing write-up for WS-6.

**Headline, stated at the width the evidence supports:** the production engine
was built and measured, it lands in the corner B4 and B4b assign it, and its
**rates are several times lower than theirs**. That says B4's rates are our
model's and not the product's. It does **not** say B4 was wrong, and it does not
require re-scoping any claim the paper makes — because the paper already scoped
B4 to the model, in two places, before this measurement existed.

---

## 1. The result

`analyse_b5_agreement.py`, unmodified, against `7fddd91`:

| Hypothesis | Class | B5 | frozen B4/B4b | Reading | Stage |
|---|---|---|---|---|---|
| H1 duplicates | AUTH | 0.1567 [0.1233, 0.1900] | 0.9333 [0.9000, 1.0000] | DISAGREES | 4 of 4 |
| H1 duplicates | NO_READBACK | 0.1586 [0.1241, 0.1931] | 0.9667 [0.9000, 1.0000] | DISAGREES | 4 of 4 |
| H2 lost effects | AUTH | 0.1433 [0.1067, 0.1833] | 0.9667 [0.9000, 1.0000] | DISAGREES | 4 of 4 |
| H2 lost effects | NO_READBACK | 0.1414 [0.1034, 0.1828] | 0.8667 [0.8000, 0.9000] | DISAGREES | 4 of 4 |

**H3 held.** No declared ambiguity in 118 non-void runs.

Pooled per arm, over 590 executions each: B5 (unlimited attempts) duplicated at
**0.1576** and lost **0.0000**; B5b (one attempt) lost at **0.1424** and
duplicated **0.0000**. At the same crash point and the same two capability
classes, B4 duplicates at **0.9500** and B4b loses at **0.9167**, over 60
executions each.

## 2. What the disagreement licenses

The script's pre-registered wording for this branch says *"B4 would then be an
artefact of our model rather than of event-sourced re-execution, and every B4
claim must be re-scoped."* That wording was written before any B5 data existed
and it assumes the paper claims more for B4 than it does. Checked against the
manuscript, it does not.

**Licensed:**

1. **B4's rates do not predict the engine's rates.** Roughly a factor of six at
   the one crash point both can be cut at.
2. **The corner assignment does transfer, exactly.** Unlimited attempts
   duplicates and loses *zero* effects; one attempt loses and duplicates *zero*.
   That is what `tab:related` predicts for the two retry policies, now observed
   on the product rather than on our instantiation of its documented defaults.
3. **H3 is confirmed on the engine itself.** The third corner of the trilemma is
   unreachable by the product, not merely by our model of it — the strongest
   positive result of WS-6, and the one that supports rather than qualifies the
   paper's argument.

**Not licensed:** any claim about the engine's throughput, latency, maturity or
correctness; any generalisation from one crash point to the engine's behaviour
at others; any reading of a B5 timing number as a recovery latency.

## 3. Four bounds, all four in the write-up

1. **The comparison is incomplete.** B5 has no `after_intent_before_barrier`
   position — the pre-dispatch record is written by the server inside one RPC,
   so no worker-side window exists between the write and its acknowledgement —
   while **B4 and B4b have frozen data there at all three capability classes**.
   Four cells read `NOT_TESTABLE_ABSENT_IN_B5`, resolved before any arithmetic.
   The summary is not a complete comparison and must not be read as one.
2. **Conditional on a 4000 ms Start-To-Close that B4 has no analogue for.** A
   different timeout is a different cell. No B5 timing number may be quoted as
   Temporal's recovery latency.
3. **The interval arithmetic is asymmetric.** B4's intervals rest on 3 runs
   against B5's 30, and three clusters put resampled means on multiples of
   1/30, which is why B4's widths are a round 0.1000. **The separation is in the
   point estimates — about 0.78 apart — not in the intervals failing to
   overlap**, and the write-up says so rather than leaning on the intervals.
4. **The dispatch-point window is sized by the server and by loopback**, not by
   the protocol, so its width is not like-for-like with B4's
   (`B5_SEMANTICS.md` §2.4).

## 4. What re-scoping B4 means concretely: almost nothing, and that is the finding

**The instruction was to quote what the paper says before deciding what to
change.** Quoted:

**§VII**, after introducing the two retry policies:

> Our B4 and B4b controls instantiate these two policies against the same
> non-cooperative endpoint. **They are semantic controls, not claims about those
> products' complete implementations.**

Its table rows are labelled **"Temporal-style, $\infty$ retries"** and
**"Temporal-style, 1 attempt"**, with qualitative outcome cells — *duplicate
effect*, *lost effect* — and no rates.

**§VIII**, in a paragraph already titled **"B4 is not Temporal"**:

> B4 shares exactly one mechanism with a production durable-execution engine
> [...] **the decision is our code. No claim about Temporal's throughput,
> latency, maturity or correctness as a product is made or supported anywhere in
> this paper**, and B4's latency in particular should not be read as any
> engine's recovery latency. B4 and B4b *bracket* the configuration space rather
> than survey it.

**§VI's** load-bearing use of B4 is structural, not rate-generalising: that a
durable record is necessary and not sufficient, that the record cannot contain
whether the provider applied the effect, and that one configuration line moves
the engine between two silent corners. None of that is a claim about the
product's rates.

**So no existing claim asserts that B4's rates characterise durable-execution
engines generally.** The re-scoping the script's wording demands was already
done, before the data existed. **Reporting that is the honest outcome; the
alternative would have been manufacturing a change to match a sentence written
in advance.**

### The one change made

§VIII gains a paragraph reporting the measurement, because *"no claim about the
product is supported"* was an assertion and is now demonstrated. It states the
two arms' rates and zeros, that neither declared ambiguity, that the direction
transfers and the magnitudes do not, and all four bounds above. **§VI and §VII
are unchanged.** Fourteen new macros, all generated by
`scripts/paper_tables.py --b5-session`, none hand-written.

## 5. Gates

`check_paper_numbers.py`: **23 passed, 0 failed**, including *every generated
number is used in the manuscript* — so all fourteen macros are load-bearing.
Both PDFs build clean; `main-anon.pdf` is 23 pages and passes its four
anonymity checks.

`check_generated_tables` now regenerates with `--b5-session` and **fails if the
session is absent**, matching that gate's own rule that a missing input is a
failure and not a silent skip. `paper_tables.py` emits the B5 macros only when
the session is supplied, because a macro computed from an absent source is worse
than a missing macro — the reader cannot tell the difference.

## 6. Recorded, not fixed

`analyse_b5_agreement.py`'s `run.get(metric_field, 0)` would silently compute
**H1 = 0.0000** from a missing field if the corrected script were run against
the 2026-09-08 session, whose records predate
`undetected_duplicate_executions`. Recorded in
`phase-report-ws6-prediction-corrected-2026-09-08.md` §6.1, beside the
prohibition on re-reading that session, because the two only make sense
together. Not fixed: the script has now read data, and changing it afterwards
is what the ordering exists to prevent.

## 7. Status

WS-6 is complete: the baseline was built, collected on the third attempt against
the corrected harness, read once, and written up. Two attempts remain against
the corrected cell and none is needed. The secondary sweep — four further crash
points on `NO_READBACK` — is registered in `1fecb1f` §3.1 and **not collected**;
`session.py` now arms those points correctly, and the crash-point binding is
proven, but no data exists for them.
