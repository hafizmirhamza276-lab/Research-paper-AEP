# WS-5 pre-registration — amendment 2: H2's hypothesis and H2's instrument disagree

**Amends** `reports/phase-report-ws5-prediction-2026-09-10.md` (`47d8a23`) and
`reports/phase-report-ws5-prediction-amendment-1-2026-09-10.md` (`684c5fb`).
**Both are left unedited** (rule 5). This records an ambiguity discovered on
contact with the data; it does not resolve one silently.

**Written after the data existed**, which is exactly why the resolution below is
the one that is *worse* for the paper. A pre-registration ambiguity settled in
the direction that helps is not a resolution, it is a fit.

---

## 1. The conflict

**H2, as pre-registered** (§2.2):

> B3's upper-mode fraction is a stable property of the arm, not of those three
> runs: at 15 runs it lies in [0.15, 0.40].

Measured at 15 runs: **0.20** — 30 of 150 executions, lower mode 2 055.8 ms
(n = 120), upper mode 5 048.3 ms (n = 30). **In band.**

**Amendment 1 §1, final paragraph, verbatim:**

> **If no arm is flagged at fifteen runs, the mixture reporting is omitted and
> the pooled median stands.** That outcome is H2 of the pre-registration being
> refuted, and it is reported as such rather than quietly dropped.

No arm was flagged. The `bimodal` predicate requires the largest gap to exceed
**half the sample's range**; at three runs it was 95%, at fifteen it is 40% —
not because the modes moved but because the larger sample contains far points
that inflate the *range* while the gap itself stays near 3 000 ms.

So the hypothesis says supported and the instrument says refuted.

## 2. Which governs, and why

> **Amendment 1 governs. H2 is REFUTED. The pooled median stands.**

Three reasons, none of which is "it gives the answer we prefer":

1. **Amendment 1 is the later and more specific instrument, and it was written
   for precisely this moment.** Its own stated purpose is that choosing a
   summary *"after seeing fifteen runs … would be a fitted choice: the shape of
   the new data would decide which summary flatters it."* Reading H2's prose
   over amendment 1's predicate, now that both answers are visible, is that
   fitted choice.
2. **The predicate is operational; the prose is not.** "Upper-mode fraction" is
   only defined once something has split the sample into modes. The splitter is
   `largest_gap_split`, and the same function that produces the fraction also
   produces the flag. Taking the fraction while discarding the flag uses half an
   instrument and calls it a measurement.
3. **Phase 17 ruled the other way and gave no reason that survives.** Its §4
   argued H2's text is "about the fraction". True, and beside the point: the
   text was operationalised, and the operationalisation was fixed first.

**Phase 17's verdict on H2 is therefore superseded.** Its report is not edited
(rule 5); this file is the correction, and the phase 18 report says so too.

## 3. What the resolution costs, priced

H1's second clause is *"the protocol-minus-barrier figure's interval half-width
falls below 100 ms."* Under the two readings, computed with the same estimator,
resample count and seed (cluster bootstrap over runs, 10 000, seed 20260806):

| quantity | pooled median (governing) | lower-mode median |
|---|---|---|
| barrier cost, AEP-full − B3 | 1 939.7 ms [1 855.8, 1 962.4], half-width **53.3** | 1 959.0 ms [1 914.2, 1 970.2], half-width **28.0** |
| protocol − barrier, B3 − B0 | 33.9 ms **[−122.6, +120.1]**, half-width **121.3** | 16.3 ms **[−54.1, +47.5]**, half-width **50.8** |

**H1 clause 1 holds under both.** The barrier's cost excludes zero either way.

**H1 clause 2 differs**: 121.3 ms fails the 100 ms target under the governing
reading; 50.8 ms passes it under the other. So **H1 is refuted under the
governing reading and would be supported under the alternative** — the
disagreement the prompt asked to be priced.

**The paper-relevant fact does not depend on the choice.** Protocol-minus-barrier
**spans zero under both readings**. Whatever H2's verdict, §VI-RQ3's 28.0 ms
figure is not resolvable from zero at fifteen runs per arm. The two readings
change H1's label; they do not change what the manuscript may claim.

## 4. A defect in amendment 1's predicate, recorded not fixed

`gap / range > 0.5` is **range-sensitive**: the same mixture fires at three runs
and not at fifteen, because the denominator grows with the sample while the
numerator does not. That is a bad predicate for a property that is supposed to be
*stable in the arm* — which is what H2 asserts.

A fraction-based predicate (*the smaller group holds between 10% and 40% of
observations, and the gap exceeds k times the within-mode spread*) would not have
this behaviour. **It is not adopted here.** Changing the predicate after seeing
which answer each version gives is the fitted choice this amendment exists to
refuse. It is recorded so that the *next* pre-registration, written before its
data, can choose better.

## 5. What would change this verdict

New data, not new reasoning. If a later collection at a larger *n* flags the arm
under the predicate as written, the mixture reporting applies and H1 should be
re-ruled under the lower-mode reading. Nothing in this file licenses re-ruling it
on the present data.
