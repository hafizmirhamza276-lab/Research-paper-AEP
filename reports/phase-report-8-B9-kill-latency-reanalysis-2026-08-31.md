# B9 — the kill-latency re-analysis, and what it leaves standing

**B9 does not close as "recomputed, unchanged."** The entry's stated evidence is
from the wrong collection, the defect it names is not the large one, and the
quantity it says is safe — the point estimate — is the quantity most exposed.

Everything below is derived from tracked artefacts by two scripts committed
beside this report:

- `reports/raw/b9_drift_reconstruction.py` — run-position drift, from each
  paired root's `per-execution.csv`.
- `reports/raw/b9_kill_latency_by_session.py` — the kill-latency contrast at the
  session level, from `reports/raw/e1-kill-latency-by-run.csv` (committed
  `1191f1b`, 300 rows, applied counts matching the four roots frozen at
  `b2ab570` exactly).

**No frozen root was opened and no collection was re-run.** B9 is a re-analysis
obligation; the design cannot be fixed retroactively.

---

## Part 0 — B9's evidence

B9's "why it is at risk" paragraph rests on a Spearman of **+0.703** between run
position and kill latency, attributed to *"Phase 8.4 session 1"*.

### 0a. The figure is real. My plan said it was not, and that was wrong

The plan for this task asserted that `+0.703` could not be reproduced from
anything in the repository, and offered that as its strongest finding. **It
reproduces exactly: +0.7034**, from `b2-paired-s1-2026-08-28`'s tracked
`per-execution.csv`, with position reconstructed as `(cell, repetition)` under
that root's declared cell-major design. The cells have to be in **collection
order**, `NO_READBACK` before `AUTHORITATIVE_READBACK`; I had tried only
alphabetical orderings, which sort them the other way.

**The claim is withdrawn in full**, including the framing that made it
load-bearing — that this was a third instance of a figure existing only outside
the artefact. There is no third instance. The mechanism of the error is recorded
in **§F.0f**: an incomplete search and a genuine negative are indistinguishable
from inside the search, and this one failed in the direction that produced a
finding rather than a null.

The same construction reproduces five further committed figures exactly —
`+9.06` and `−1.81` ms/run (Theil–Sen), `−0.478`, `−0.112`, `−0.665` — which is
what licenses reading the corrected `−0.547` for s2 off it.

### 0b. It is from a different collection than the one B9 argues about — this stands

**B9's claim is about the Phase 9 replication set**, frozen at `b2ab570`:

| session in the latency CSV | frozen root | AEP-full applied |
|---|---|---|
| `P9-B` | `b2-2026-08-21` | 20/30 |
| `s1` | `b2-s1-2026-08-21` | 12/30 |
| `s2` | `b2-s2-2026-08-21` | 4/30 |
| `s3` | `b2-s3-2026-08-21` | 7/30 |
| `2026-08-07` (ext4) | inside `matrix` | 10/30 |

`+0.703` is a measurement of `b2-paired-s1-2026-08-28`, a **different
collection under a superseded design**. So B9 imported a drift figure from one
collection to argue about another, before checking the drift in the data it was
arguing about. **That is the correction, and it is narrower than "the number is
unreproducible."**

### 0c. The drift in B9's own data, which nobody had measured

Spearman(repetition index, `docker kill` latency), derived here. Repetition index
is a valid within-cell time order under either sort key, so this needs no
knowledge of the collection ordering:

| session | AEP-full | B3 |
|---|---|---|
| `P9-B` | **−0.211** | +0.174 |
| `s1` | **−0.505** | +0.285 |
| `s2` | **+0.045** | −0.398 |
| `s3` | **−0.436** | +0.022 |
| ext4 | −0.125 | +0.493 |

**Mixed in sign, moderate in magnitude, nothing resembling +0.703.** Drift is
real in this data and exchangeability over run labels is violated. B9 does not
retire.

### 0d. B9 names the wrong test

B9 says *"a permutation test over run labels"* and refers to *"the Mann-Whitney
variants"* as a separate family. **There is one family and it is Mann-Whitney
throughout** (`paper_tables.py`, `_median_split`). The exchangeability concern
survives the correction — Mann-Whitney's null distribution *is* the permutation
distribution of ranks — but the entry misdescribes its own target.

---

## Part 1 — the defect B9 does not name, and it is the larger one

`_median_split` filters on `filesystem` and `system` only. The drvfs stratum is
**four sessions**, so the macro pools 120 runs across them **with no session
term**. Those sessions have applied rates of 20, 12, 4 and 7 out of 30 — 9C's
over-dispersion — so pooling mixes between-session level differences into a
contrast that is meant to be within-session.

### The four sessions, individually

**These are the data.** No tally, no count of sessions on one side of zero, and
no derived summary stands in for them:

| session | applied / not | median difference |
|---|---|---|
| `P9-B` | 20 / 10 | **+70 ms** |
| `s1` | 12 / 18 | **−4 ms** |
| `s2` | 4 / 26 | **+282 ms** |
| `s3` | 7 / 23 | **+74 ms** |
| **pooled — what `\KillLatencyDiff` reports** | 43 / 77 | **+201 ms** |

**The pooled figure exceeds three of the four sessions it is built from, and one
session has the opposite sign.** `s2`'s +282 ms is measured on 4 applied runs
against 26; it dominates the pooled median because pooling weights runs, not
sessions.

### The session-clustered version, using the paper's own estimator

| | |
|---|---|
| mean of the four session differences | **+105.5 ms** |
| between-session sd | 123.4 |
| t(0.975, 3) = 3.182, half-width | **196.3** |
| **95% interval** | **[−90.8, +301.7] ms** |

> **The half-width is 1.86× the mean it brackets.** Per F.0's binding in its
> general form, that precision is stated wherever this quantity is stated. An
> interval this wide contains the observed effect, contains zero, and contains
> effects three times the observed one; it does not distinguish between them.

*(Computing the same quantities from the four differences rounded to whole
milliseconds gives sd 123.0 and [−90.2, +301.2]. The mean is identical and the
ratio is 1.86× either way; the emitted macros use the unrounded values.)*

### Why no p-value is reported with it

**Not because the p is inconvenient — because the design cannot produce an
informative one at this unit.**

- A **sign test at k = 4** has a two-sided minimum of `2·(1/2)⁴ = 0.125`. It is
  **floored above 0.05: no outcome this design can produce reaches
  significance.** This is the design-floor argument for the third time in this
  phase, and the first found rather than pointed out.
- **Its outcome in counting form is the same test.** "3 of 4 sessions positive"
  has `P(≥3 of 4) = 5/16 = 0.3125` under the null and a two-sided sign-test
  `p = 0.625`. Quoting the tally while declining the test would replace a
  useless p with an informal version of itself. **It is not used here.**
- The **t route at k = 4** is not floored, and returns `t(3) = 1.71,
  p = 0.186`.
- The pooled `4.0×10⁻⁹` is computed under exactly the pooling this section
  retires, and under an independence assumption the paper refuses in three other
  places.

The report is the four differences, the mean, and the interval with its
precision.

### 8.1 was internally inconsistent about this

`\ReplicationPreventedLow`/`High` = [6.1, 28.4] is emitted as *"session-
clustered, t(3) = 3.182, session as the unit"* — **on these same four
sessions, in the same phase** — while the kill-latency mechanism pools their
runs. One report, two units, same data. That is what makes this a defect rather
than a defensible choice.

### B9's own diagnosis, evaluated

B9 offers blocks-of-adjacent-runs or position-as-covariate. **Both target
within-session position, and the data says that is not where the problem is.**
Position must confound *both* latency and outcome to matter. It predicts latency
moderately (0c above), and **it predicts `applied` barely**:

| session | ρ(position, applied), AEP-full |
|---|---|
| `P9-B` | −0.098 |
| `s1` | +0.055 |
| `s2` | −0.057 |
| `s3` | +0.168 |
| ext4 | −0.188 |

**|ρ| ≤ 0.19 everywhere.** The confounding path B9 names is weak. The remedy
adopted is **the session as the stratum** — not a free parameter, the unit the
paper already uses for this quantity, and it removes the pooling that is the
actual defect.

**Block width is declined**, and the reason is on the record rather than
implied: it is a researcher degree of freedom. Had it been necessary the rule
would have been fixed before looking — width = the collection's repetition
stride — and any verdict that moved with the width would be reported as a
finding rather than resolved by choosing a width. None of that is needed once
the session is the block.

---

## Part 2 — the same construction, applied to every arm

The pooled construction is being retired for AEP-full. **The question is what
that does to the figures quoted in its support**, and it is answered from the
construction, not from what each one contributes.

### `\KillLatencyBthree*` — the B3 negative control: withdrawn, then recomputed

`_median_split("drvfs", "B3_INTENT_NO_BARRIER")` is **the same call, the same
four sessions, the same pooling.** It cannot be invalid in one arm and
evidential in the other. Its pooled −14 ms at p = 0.63 is withdrawn.

Recomputed at the session level:

| session | applied / not | median difference |
|---|---|---|
| `P9-B` | 28 / 2 | −28 ms |
| `s1` | 28 / 2 | +27 ms |
| `s2` | 28 / 2 | −31 ms |
| `s3` | 28 / 2 | −152 ms |
| **session-clustered mean** | | **−46.0 ms** |
| **95% interval** | | **[−166.4, +74.3] ms** |

> **The half-width is 2.61× the mean.**

**And this is the finding, not a formality.** The pooled −14 ms looked like a
clean null because pooling made it precise. At the correct unit the control's
interval spans 240 ms and contains effects larger than the one it is supposed to
be controlling for. **It is not a negative control; it is an uninformative one.**
It never had the precision to contradict the mechanism, so its failure to
contradict it is not evidence. Every B3 session has 28 of 30 applied, so each
session's difference rests on 2 non-applied runs.

### `\KillLatencyOrig*` and `\KillLatencyBthreeOrig*` — the ext4 cell: retained

`_median_split("ext4", ...)` selects **one session**, `2026-08-07`, 30 runs per
system. There is no between-session pooling in it, so the defect retired above
does not reach it. It is a within-session contrast at the unit it was collected
at.

| | difference | p |
|---|---|---|
| AEP-full, ext4, n = 30 | **+88 ms** | **0.03** |
| B3, ext4, n = 30 | **+26 ms** | 0.53 |

**Retained, and by construction rather than by preference** — the test is
whether the figure pools across sessions, and this one does not. Two costs are
stated with it:

1. **k = 1.** It is a single session, unreplicated, on the original filesystem
   stratum. Its p is a legitimate within-session test and carries no
   between-session variance component at all.
2. **It is the one figure B9's own stated concern actually reaches.** Within-
   session position drift is exactly the threat to a within-session Mann-Whitney.
   For this cell ρ(position, latency) = −0.125 and ρ(position, applied) = −0.188,
   so the confounding path is weak — but weak is the honest word, not absent.

### `log(issue_to_return_ns)` non-degeneracy — not support, and I had it wrong

The plan listed 8.5's finding that the covariate is not degenerate as
independent support for the mechanism. **It is not.** Non-degeneracy establishes
that the covariate *has variation to adjust on*; it says nothing about whether
latency predicts `applied`. Withdrawn as support.

---

## Part 3 — what remains of the mechanism's claim

The claim is *"the unwanted-applied-effect rate is a race outcome rather than a
protocol constant."* Applying one construction consistently to every arm, what
supports it is:

- **One session** — ext4, `2026-08-07`, 30 runs — at **+88 ms, p = 0.03**, with
  its own single-session control at **+26 ms, p = 0.53**.
- **Four replication sessions** whose differences are **+70, −4, +282, +74 ms**,
  mean **+105.5**, 95% interval **[−90.8, +301.7]**, half-width **1.86× the
  mean** — consistent with the direction and unable to establish it.

**That is very little, and it is the result.** The mechanism is not refuted: the
direction agrees across five sessions of two collections, and the replication
set's interval comfortably contains the ext4 point estimate. But the four-session
replication, analysed at the unit it was collected at, **cannot confirm it**, and
the negative control that appeared to strengthen it turns out never to have had
the precision to weaken it.

**What the paper can say** is that a single session shows the association, that
a four-session replication is directionally consistent at a precision that does
not resolve it, and that the design's session-level floor of 0.125 means no
replication of this size could have resolved it. **What it cannot say** is that
the association is established, or that a clean negative control rules out a
host artefact.

**If the session-clustered interval had excluded zero I would report that with
equal prominence.** It does not.

---

## Part 4 — what this changes

| macro | now |
|---|---|
| `\KillLatencyDiff`, `\KillLatencyP`, `\KillLatencyN` | **withdrawn**, replaced by session-clustered macros |
| `\KillLatencyBthreeDiff`, `\KillLatencyBthreeP`, `\KillLatencyBthreeN` | **withdrawn**, replaced by session-clustered macros |
| `\KillLatencyOrigDiff`, `\KillLatencyOrigP`, `\KillLatencyOrigN` | **retained unchanged** |
| `\KillLatencyBthreeOrigDiff`, `\KillLatencyBthreeOrigP`, `\KillLatencyBthreeOrigN` | **retained unchanged** |

Sites: `paper/sections/06-evaluation.tex` and `paper/sections/08-threats.tex`.
**Nothing in `main.tex`.**

Retirement follows B20's pattern: **remove the withdrawn macros rather than
redefining them**, so the orphan gate and LaTeX enforce completeness from both
sides, and add-migrate-remove lands in **one commit** because those two checks
make any other ordering non-building.

The new emission **declares its unit in the `macro()` provenance** rather than
in the prose, per F.0d, and **refuses to emit** if the four sessions are not
recoverable from the CSV — the same fail-closed guard as
`\AblationZeroUpperPerClass` and `\FlakeyPerRep*`.

---

## What was not done

- **No re-collection**, and no opening of any frozen root.
- **No block-width parameter**, for the reason in Part 1.
- **No fitting of the 8.5 estimand** and nothing touched in the `\Class*` work.
- **B10 and B22–B25 stay unfixed**, including inside `paper_tables.py`.
