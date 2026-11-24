# WS-5 pre-registration — amendment 4: the class sweep stays at four sessions, and WS-5 closes

**Amends** `reports/phase-report-ws5-prediction-2026-09-10.md` (`47d8a23`) and
amendments 1 (`684c5fb`), 2 (`05458ea`) and 3. **All four stay unedited**
(rule 5).

**Ruling, made after phase 22 and before any further collection: the
capability-class sweep remains at four sessions, and WS-5 is closed to further
collection.**

---

## 1. What six sessions would have bought, and why it is not needed

Amendment 1 §2 already fixed the class-sweep result as **a bound, not a test**:

> Six is the minimum at which the paired sign test can reject at all … **The
> result is reported as a bound, not as a test.** Six sessions gives 80% power
> only against effects far larger than the ±5 pp margin; reaching that margin
> needs ~143 sessions … The claim made will therefore be an interval and an
> explicit statement of what it could not have detected.

Once the claim is a bound, the 2/2ⁿ floor is **not load-bearing**. It matters
only if a p-value is going to be quoted, and amendment 1 already ruled that one
will not be. Moving the floor from 0.125 to 0.03125 would change no sentence the
paper is entitled to write.

**§VIII's claim is in fact stronger at four.** The sentence is that this design
*could not have found* an effect — at n = 4 that is a theorem about the design
(no effect size whatever produces p ≤ 0.05), and it is stated in §1.4 of the
pre-registration in exactly those terms. A six-session tree of mixed design
would replace a clean impossibility result with a messier one.

## 2. Why six was not reachable without re-collecting

Phase 22 launched sessions 5 and 6 and stopped them at 19 of 60 runs.

The four existing sessions are **cell-major**: 30 `AEP_FULL`, then 30 `B3`.
Run-level **interleaving** was introduced in `5b601d0`, 2026-08-28 12:02:54,
*"Phase 8 pre-registration amendment 1: interleave at run level, because arm and
drift are collinear"*. Its comment in `run_matrix.py` is explicit that the
cell-major arrangement makes arm and drift *perfectly collinear* — **a
non-identifiable confound that no number of sessions separates**.

The four class-sweep sessions are dated 21 August. They pre-date that commit by
a week and were never re-collected.

So the two options were:

* add interleaved sessions to cell-major ones — two designs inside one paired
  sign test; or
* revert `5b601d0` for this collection — deliberately reintroduce a known
  non-identifiable confound so that new data resembles old data.

**Neither is acceptable, and the third option is this amendment.** The project's
own precedent points the same way: on 28 August the identical defect was met by
re-collecting the whole comparison as `b2-paired-v2-*` and retaining the v1
session unpooled. Re-collecting the class sweep as a v2 is the only route to six
comparable sessions, costs about six hours, and buys a floor the reported claim
does not use.

## 3. What is ruled

1. **The capability-class sweep stands at four sessions**, reported as a bound
   with its floor of 0.125 stated, exactly as amendment 1 §2 prescribes.
2. **The four sessions' cell-major design is disclosed**, not merely known. It
   is recorded in the collection record beside the data itself (§4 below), so
   the analysis pass and any reviewer meets it without reading a phase report.
3. **WS-5 is closed to further collection.** No further sessions, arms or cells
   will be collected for this workstream.

## 4. Where the discontinuity is recorded

`COLLECTION-NOTE.md`, tracked, in each of the four session roots:

```
experiments/results/b2-2026-08-21/COLLECTION-NOTE.md
experiments/results/b2-s1-2026-08-21/COLLECTION-NOTE.md
experiments/results/b2-s2-2026-08-21/COLLECTION-NOTE.md
experiments/results/b2-s3-2026-08-21/COLLECTION-NOTE.md
```

Beside the data, not in a report, and un-ignored so it survives a fresh clone.

## 5. What this does not change

* Amendments 1–3 are unedited. Amendment 1 §2's "two sessions are added to the
  existing four" is **superseded by this amendment**, not rewritten.
* The `always` arm (phase 21, 45 runs) and the tier-1/tier-2 collections stand.
* **This amendment is about the class sweep only.** It says nothing about
  whether §VIII's wording should change; that is manuscript work and no `.tex`
  was touched in the pass that wrote this.
* The four sessions themselves are untouched — 60 run directories each,
  verified after the ruling.
