# Response to the second external audit — 2026-09-25

**Audit under response:** `reports/external-audit-2-2026-09-25.md`, written
against `26d4d84`.
**This response was written at `26d4d84` with a clean tree.** Nothing was fixed
in this session. No live call was made. Every number below was recomputed from
tracked CSVs, the tracked JSONL, the `.tex` sources, `experiments/run_matrix.py`,
`formal/`, and a fresh `git clone` of this repository into a scratch directory.

**Verdict in one line.** The audit is substantially correct. Every load-bearing
claim I could check reproduces exactly, including all sixteen figures in its
§3.2 and §3.4 tables. Two of its findings are understated and one of its
characterisations is slightly too strong; both are detailed below. I found one
piece of corroborating evidence for B1 that the audit did not use, and it is
stronger than the evidence the audit does use.

**What I could not do in this environment.** No `java`, so I could not re-run
TLC; §2.5 is confirmed by mechanism from source, not by re-execution. No
`IEEEtran.cls`, so no PDF rebuild. The clone test ran on Windows, so three gates
fail there for the reasons the pack's own §3.3 records; I do not count those
against anyone.

---

## Summary table

| Audit finding | Verdict | Fix class |
|---|---|---|
| **B1** the undisclosed provider fault (the injection itself) | **VERIFIED**, on stronger evidence than the audit cites | (a) wording |
| **B1** §6.6's duplicates are background, not post-crash re-execution | **VERIFIED** — attribution **not supported** | (b) re-analysis |
| **B1** §6.2's engine comparison is background | **VERIFIED** | (b), or (c) for a real comparison |
| **B2** seven unscoped statements | **VERIFIED** (six clean, C4 **PARTLY**) | (a) wording |
| **B2** §6.4 contradicts §6.3.1's new paragraph | **VERIFIED** | (a) wording |
| **F1** figures predate the exclusion | **VERIFIED**, and understated | (b) re-analysis |
| **F2** supplementary's "five for B0–B2" | **VERIFIED** | (a) wording |
| **F6** B4 "duplicates at the highest rate in the study" | **VERIFIED** false under all three readings | (a) wording |
| **§2.5** the committed TLC config does not check the printed claim | **VERIFIED** by mechanism | (b) |
| **§8** nine audit-pack / audit-response claims | **8 VERIFIED, 1 PARTLY** | (a) wording |

---

## 1. B1 — the undisclosed provider fault

### 1.1 The injection: VERIFIED, on more evidence than the audit cites

**The configuration.** `experiments/run_matrix.py:1316-1324`:

```python
FAULTS = {
    "timeout_probability": 0.15,
    "server_error_probability": 0.05,
    "duplicate_response_probability": 0.0,
    "delay": {"distribution": "constant", "seconds": 2.0},
}
```

Its own docstring at `run_matrix.py:1310-1315` says it plainly: *"The fault
surface every matrix run shares. Not a matrix dimension."*

**It reaches every run through one unconditional code path.**
`run_matrix.py:1197` passes `fault_overrides=FAULTS` inside the single
`run_once(...)` call that every plan entry goes through. There is no regime
branch, no `p0` special case, no override. `grep -n FAULTS run_matrix.py`
returns exactly two lines: the definition and that call site. `p0`
(`REGIME_NO_CRASH`, `run_matrix.py:222-233`) sets `crash_probability=0.0` and
says nothing about faults.

**Introduced before the matrix existed.** `git log -S timeout_probability --
experiments/run_matrix.py` bottoms out at `9154d85`, 2026-08-06 10:15:54 +0500.
The matrix's first progress record is from the same collection window.

**Confirmed in the emitted configs, not only in the source.** The audit cites
two tracked `mock-api.yaml` files. I checked every one available:

| set | files | carrying `0.15` / `0.05` |
|---|---|---|
| tracked `mock-api.yaml` (`git ls-files`) | 249 | **249** |
| `experiments/results/matrix/*/` on disk | 84 | **84** |
| `experiments/results/abd-immediate-2026-09-24/*/` (phase 53) | 45 | **45** |
| `ws5-2026-09-10/t1-p0-everysec/*/` (a **crash-free** collection) | 15 sampled, all | **all** |

That last row is the direct answer to "including p0": a `crash_point: none`
run directory's own emitted provider config carries `timeout_probability: 0.15`
and `server_error_probability: 0.05`.

**The data proves it independently of any config file.** In the matrix's `p0`
cells, `crashed = 0` in all 210 executions, and yet:

| system | retried (`dispatch_attempts > 1`) | non-`APPLIED` outcomes |
|---|---|---|
| AEP_FULL | 0/30 | 3 `CONFIRMED_NOT_APPLIED` |
| B0_NAIVE_RETRY | **3/30** | 1 `UNVERIFIED_FAILURE` |
| B1_LEASE_ONLY | **8/30** | 1 `UNVERIFIED_FAILURE` |
| B2_CAS_ONLY | **7/30** | 0 |
| B3_INTENT_NO_BARRIER | 0/30 | 2 `CONFIRMED_NOT_APPLIED` |
| B4_DURABLE_WORKFLOW | **5/30** | 1 `UNVERIFIED_FAILURE` |
| B4B_…_AT_MOST_ONCE | 0/30 | 3 `UNVERIFIED_FAILURE` |

In a regime where *nothing is injected*, no worker is killed, and no request
fails, a retrying baseline retries zero times and every execution applies. These
do not.

**§6.1's sentence.** `paper/sections/06-evaluation.tex:57`:
> *"\textbf{crash-free} (\texttt{p0}): nothing is injected. The only regime RQ3
> may use"*

**No `.tex` file states either rate.** `grep` over `paper/main.tex`,
`paper/sections/*.tex`, `paper/supplementary.tex` and `paper/generated/*.tex`
for `0.15`, `timeout_probability`, `server_error`, and `probab` returns no
statement of either rate. The only `0.15` in the generated macros is
`\BfiveDup{0.1576}`, which is a result, not a setting.

**One correction to the audit, in the paper's favour.** The audit's B1 headline
says the paper *"never discloses"* the fault. `paper/sections/08-threats.tex:82-84`
does disclose the *existence* of the surface:
> *"The endpoint is a purpose-built service with a configurable delay, timeout
> and error distribution, and a transactionally written ground-truth ledger."*

That does not rescue §6.1 — "configurable" is not "on at 15%", and a threats
paragraph twenty pages later does not repair a false sentence in the setup. The
exact finding is: **the rates are stated nowhere, and §6.1 states the opposite
for `p0`.** I would not let the audit's stronger wording stand unqualified.

### 1.2 §6.6's attribution: NOT SUPPORTED

The audit's §3.2 table reproduces exactly. Recomputed here against
`ws5-2026-09-10/t1-p0-everysec` (crash-free, `crash_point: none`, n = 150 per
system):

| system | phase 53 (every execution SIGKILLed **before dispatch**) | crash-free | Fisher (2-sided) |
|---|---|---|---|
| B0 | 14/90 = 0.156 | 22/150 = 0.147 | **p = 0.85** |
| B1 | 13/90 = 0.144 | 27/150 = 0.180 | **p = 0.59** |
| B2 | 12/90 = 0.133 | 20/150 = 0.133 | **p = 1.00** |
| B4 | 16/90 = 0.178 | 24/150 = 0.160 | **p = 0.72** |

The matrix's own smaller `p0` cells agree (B0 3/30, B1 5/30, B2 5/30, B4 3/30;
pooled 16/120 = 0.133 against phase 53's 55/360 = 0.153, **p = 0.66**). Matching
on capability class as well — phase 53's `payments` cells only, against `p0`,
which is `payments` only — the agreement is if anything tighter
(14/120 = 0.117 against 16/120 = 0.133, **p = 0.85**).

**The mechanism, from the joint distribution.** The audit asserts that a
duplicate needs two dispatches. The data shows it, and shows that phase 53's
distribution is a scaled copy of the crash-free one:

| `dispatch_attempts`, `applied_effects` | phase 53 (n=360) | of which dups | crash-free `p0` (n=120) | of which dups |
|---|---|---|---|---|
| 1, 1 | 286 | 0 | 97 | 0 |
| 2, 1 | 17 | 0 | 5 | 0 |
| **2, 2** | 43 | **43** | 14 | **14** |
| 3, 1 | 2 | 0 | 2 | 0 |
| **3, 2** | 7 | **7** | 1 | **1** |
| **3, 3** | 5 | **5** | 1 | **1** |

Every duplicate in both columns has `dispatch_attempts ≥ 2` **within one
execution**. The killed first attempt sent nothing (0 of 450 executions record
an applied effect with no dispatch attempt). So both applications came from the
post-crash re-execution making a second call — and the only thing that makes a
re-execution call twice is an ambiguous first call, which is the injected 15%
timeout. The crash buys one re-execution; it does not buy the duplicate.

**Evidence the audit did not use, and it is inside the matrix the paper already
reports.** The `before_intent_write` cells are a crash *before anything is
written or sent* — structurally the same as phase 53's immediate kill, and
already in Table 7:

| system | `before_intent_write` (crashed regime) | crash-free `p0` | Fisher |
|---|---|---|---|
| B0 | 11/90 = 0.122 | 3/30 = 0.100 | p = 1.00 |
| B1 | 19/90 = 0.211 | 5/30 = 0.167 | p = 0.79 |
| B2 | 11/90 = 0.122 | 5/30 = 0.167 | p = 0.54 |
| B4 | 22/90 = 0.244 | 3/30 = 0.100 | p = 0.12 |
| **pooled** | **63/360 = 0.175** | **16/120 = 0.133** | **p = 0.32** |

Three independent cells — crash-free, crash-before-write, crash-before-dispatch
— all sit at the same floor, and that floor is the injected
`timeout_probability`. The cells where the request *was* on the wire sit at
0.92–1.00. The separation in the data is not crashed-versus-not; it is
**bytes-sent-versus-not**.

**Verdict.** §6.6's attribution is **not supported** for duplicates and lost
effects. It **is** supported for applied effects and dispatch attempts, exactly
as the audit says: `\AbdZeroDispatchApplied` = 0 of 450, and B4b's 0 applied
over 0 dispatches in 90 of 90, do establish the kill position. What the
collection cannot support is `06-evaluation.tex:894-899` —
*"the systems that re-execute do reach the provider … at \AbdDupRange{}
undetected duplicates per cell"* — read as a consequence of re-execution, or
*"That is the same separation \cref{sec:eval-detection} reports"*.

Two further defects in that paragraph, both confirmed:
- `06-evaluation.tex:898-899`: *"The systems that hold a pre-dispatch record …
  reach it at none."* B4 holds one — `06-evaluation.tex:432` says so
  (*"B4 has a durable record, acknowledged by the same barrier"*) and
  `02-motivating.tex:57` says so (*"its history is on disk before the call"*) —
  and duplicates at `\AbdBfourDupNoReadback{}` = 0.2000 in the same sentence.
- `06-evaluation.tex:880-881`: *"a system holding no durable record of the first
  attempt calls again."* B4 calls again because `Maximum Attempts > 1`, not
  because it lacks a record. B4b has the same record and does not.

**What survives.** Phase 53 still establishes the position, still reports a
refuted prediction honestly, and B4b's 0/90 is still the clean control. That is
a real subsection. It is not a duplicate-rate result.

### 1.3 §6.2's engine comparison: VERIFIED

Recomputed from `reports/raw/ws6-b5-s1-2026-09-08-attempt3/b5-runs.jsonl`
(118 `COMPLETED` runs; the other two are `VOID_WORKER_NEVER_READY`):

- B5 duplicate **executions** 93/590 = 0.1576, B5b lost 84/590 = 0.1424 — both
  match `\BfiveDup` and `\BfivebLost` exactly.
- Every record reads `worker deaths=1, respawns=1`; `start_to_close_ms` is 4000
  throughout. So at most 59 of 590 executions were ever crashed.
- B5's duplicate-executions-per-run distribution is `{0: 8, 1: 21, 2: 18, 3: 12}`.
  Summing the excess over one per run gives **42 of 93** duplicate executions
  that cannot be the killed one. For B5b, `{0: 10, 1: 28, 2: 9, 3: 10, 4: 2}`
  gives **35 of 84**. Both audit figures exact.
- Against the model's crash-free cells: B5 93/590 vs B4 24/150, **p = 1.00**;
  B5b 84/590 vs B4b 22/150, **p = 0.90**. Both audit figures exact.
- The engine cell's own tracked `mock-api.yaml` files (240 of the 249) carry the
  same `0.15` / `0.05`.

So `06-evaluation.tex:184-189` — *"At the same crash point, measured at the
intended instant … B4 duplicates at \AbdBfourDupAuth{} to
\AbdBfourDupNoReadback{} … against the engine's \BfiveDup{}"* — sets two
measurements of the same 15% timeout against each other. And
*"B4b … loses nothing at all against the engine's \BfivebLost{}"* compares a
cell where B4b never dispatched (0 dispatch attempts in 90 of 90) with a cell
where nine in ten executions ran to completion; B4b's own crash-free cell loses
at 22/150 = 0.147, which is **p = 0.90** against the engine.

### 1.4 What B1 does *not* damage — stated because the audit does not

B1 does **not** inflate RQ1's headline contrast. The background pushes the
pooled baseline rates **down**, not up: B0's pooled 275/360 = 0.764 contains
`before_intent_write` at 0.122; dropping that cell would give 264/270 = 0.978.
`\BaselineDupLow`/`\BaselineDupHigh` = 0.74/0.78 are therefore conservative with
respect to the fault surface, and the order-of-magnitude contrast against
AEP-full's and B3's zeros is untouched. The disclosure is still owed — a reader
cannot see this without being told the surface exists — but the headline
result is not at risk. B1's damage is confined to §6.1's sentence, C3's wording,
§6.6's attribution, and §6.2's engine comparison.

### 1.5 Fix classes

| item | fix | class |
|---|---|---|
| §6.1 `p0` "nothing is injected"; state the surface | rewrite the Faults paragraph to name `0.15` / `0.05` / the 2 s delay, and say it applies to every regime | **(a) wording** |
| C3's *"duplicate in most crashed executions"* | qualify | **(a) wording** |
| §6.6 re-attribution | recompute against `ws5 t1-p0-everysec` and the `before_intent_write` cells — all tracked | **(b) re-analysis** |
| §6.2 engine comparison | restate as engine-vs-crash-free with the background named, **or** drop | **(b) re-analysis** |
| a comparison that actually isolates crash recovery | a B5 cell at one kill per execution | **(c) new collection** |

---

## 2. B2 — the seven unscoped statements

**All seven located and quoted. Six are unambiguous; C4 is PARTLY.**

| # | location | text | verdict |
|---|---|---|---|
| 1 | `paper/main.tex:292-295`, abstract | *"\emph{Detection} … comes from the pre-dispatch record and a transition table that forbids re-entry into dispatch, not from the durability barrier."* | **unscoped** |
| 2 | `paper/sections/06-evaluation.tex:355`, §6.3.1 heading | *"Detection is the record's, not the barrier's"* | **unscoped** |
| 3 | `paper/sections/01-introduction.tex:118-119` and `:126-128`, C4 | *"…is what makes an outcome detectable, and it does so without the durability barrier"*; *"detection is nearly free, prevention is where the fsync cost lives, and an operator can buy the first without the second"* | **PARTLY** — see below |
| 4 | `paper/sections/02-motivating.tex:91-93`, Table 1 caption | *"B3 … reaches the same corner, so the barrier is not what buys declared ambiguity"* | **unscoped** |
| 5 | `paper/sections/06-evaluation.tex:795-799`, §6.4 | *"B3 is the system that already has that guarantee in full"*; *"The \BarrierCostFifteen{}\,ms buys the prevention guarantee … and nothing else."* | **unscoped** |
| 6 | `paper/sections/07-related.tex:339-341`, §7.3 | *"an ablation that assigns detection to the pre-dispatch record plus no re-entry, and prevention to the durability barrier"* | **unscoped** |
| 7 | `paper/supplementary.tex:592-593`, supp §7 | *"B3-mode … a supported configuration of the same implementation, licensed by the detection result in the paper's evaluation section"* | **unscoped** |

**On C4, the audit and the author's own plan disagree, and both are half right.**
`reports/b1-plan-2026-09-24.md` §1.2 lists C4 as *"YES — correctly scoped"*, on
the strength of its evidence clause: *"ablating the barrier produces no observed
difference **in the crashed-regime detection metrics**"*. That clause is
correctly scoped. The clause before it (*"and it does so without the durability
barrier"*) and the clause after it (*"an operator can buy the first without the
second"*) are unscoped general statements, and the second is a deployment
recommendation. The audit is right that C4 belongs on the list; the author is
right that C4 is not in the same state as the abstract.

**Also confirmed: the abstract contradicts itself within one paragraph.**
`main.tex:292-295` is unscoped; `main.tex:298-300` — *"Because detection does
not depend on the barrier for record-preserving faults"* — is one of the eight
rescoped sentences from `08590fb` and is correct. The unscoped sentence comes
first.

### §6.4 versus §6.3.1: VERIFIED contradiction

**§6.3.1's new paragraph**, `06-evaluation.tex:439-448`:
> *"\Cref{tab:modelchecking} carries the matched pair: with the barrier ablated
> and a restart that replays a shorter log, \emph{no lost effect} fails; with
> the barrier enabled under the same restart, only version monotonicity breaks
> and \emph{no lost effect} holds. So the model predicts that under a fault
> which destroys the record the barrier is what separates them, and that
> detection without it fails."*

**§6.4**, `06-evaluation.tex:798-799`:
> *"The \BarrierCostFifteen{}\,ms buys the prevention guarantee of
> \cref{sec:eval-prevention} and nothing else."*

The paper's own model says the barrier buys detection under record loss. "And
nothing else" therefore contradicts a paragraph nine hundred words earlier in
the same section. The companion sentence at `:795-797` — *"B3 is the system that
already has that guarantee in full"* — fails the same way: under a
record-destroying fault, §6.3.1 predicts B3 does not have it at all.

The matched pair is real. `formal/configs/aof-rewind.cfg` and
`formal/configs/b3-no-barrier-restart.cfg` differ in exactly one constant,
`BarrierEnabled` (`TRUE` vs `FALSE`); both set `SingleTimeline = FALSE`. So
§6.3.1's framing is sound. It is §6.4 that has to move.

**Fix class:** **(a) wording** for all seven, and for §6.4. No data is involved.

---

## 3. F1 — the figures

### Provenance: VERIFIED

```
paper/figures/figure-1-undetected-vs-ambiguity.pdf  ->  c2fffa6  2026-08-12 00:56:58 +0500
paper/figures/figure-2-duplicates-by-crash-point.pdf ->  c2fffa6  2026-08-12 00:56:58 +0500
18f44ac ("§6.1: disclose what was delivered at after_barrier_before_dispatch")   2026-09-24 10:01:46 +0500
```

Both figures are six weeks older than the disclosure and the exclusion.

### What they plot versus what the text says: VERIFIED, and understated

I rasterised both PDFs and read them.

**Supplementary Figure 1** (`supplementary.tex:111-121`, referenced from
`06-evaluation.tex:114-115` and `:266-271`) plots, in x-order
AEP, B0, B1, B2, B3, B4b, B4:

| bar | figure | pooled rate **with** the excluded cell | Table 7 (exclusion applied) |
|---|---|---|---|
| B0 | ≈0.80 | 359/450 = **0.7978** | 0.7417–0.7833 per class |
| B1 | ≈0.82 | 367/450 = **0.8156** | 0.7750–0.7833 |
| B2 | ≈0.79 | 357/450 = **0.7933** | 0.7417–0.7833 |
| B4 | ≈0.56 | 302/540 = **0.5593** | 0.4467–0.5067 |

The figure plots the pre-exclusion values exactly. Three text claims are false
against it:
- `06-evaluation.tex:114-115`: *"the supplementary material shows the **same
  executions** pooled to one bar pair per system"* — it shows **90 more per
  system**: 450 against Table 7's 360 for B0–B2, 540 against 450 for B4/B4b.
- `06-evaluation.tex:269-270`: *"The figure adds no number this section does not
  state"* — it adds four: 0.7978, 0.8156, 0.7933, 0.5593, none of which appears
  in the section.
- `06-evaluation.tex:267-268`: *"the three systems on the right have an empty
  left bar"* — the three rightmost are B3, B4b and **B4**, and B4's left bar is
  ≈0.56. (The audit ranks this Minor at §4 row 17; it is the same staleness.)

**Main Figure 2** (`06-evaluation.tex:314-322`) plots seven systems across all
six crash points, including a full `after barrier / before dispatch` group at
B0 ≈0.93, B1 ≈0.97, B2 ≈0.92, B4 ≈0.97 — the cell §6.1 says is *"excluded from
every pooled baseline rate in this section"*, plotted inside that section with
no qualifier.

**One finding beyond the audit's.** Figure 2's caption reads:
> *"The baselines' rate is not concentrated at one crash point: any interruption
> **after the request is on the wire** is enough, which is why a mechanism that
> acts only after the call cannot help."*

The figure's own `before intent write` group shows B0 0.122, B1 0.211, B2 0.122,
B4 0.244 — nonzero rates from an interruption *before* the request is on the
wire. The caption is contradicted by the figure it captions, and those bars are
the same fault-injection background as §1.2 above. Regenerating the figure will
not fix this sentence; it needs rewriting either way, and it is a second place
where the paper reads a timeout background as a crash effect.

**Fix class:** **(b) re-analysis.** Both figures are generated by
`experiments/analyze.py write_figures()` from `per-cell-metrics` /
`per-execution`, which are tracked; no new collection is needed. The exclusion
rule has to be taught to the generator, and the three text claims and Figure 2's
caption are **(a) wording** on top.

---

## 4. F2 and F6

### F2 — "five for B0–B2": VERIFIED

`paper/supplementary.tex:326-329`:
> *"Every other cell in the outcomes table spans all the crash points that apply
> to its system: six for the systems that run \texttt{aep\_core}'s workflow, and
> **five for B0--B2**, which have no window between writing a record and
> acknowledging it durable because they write no record."*

Against `paper/sections/06-evaluation.tex:36-38`:
> *"AEP-full and B3 pool six, B4 and B4b pool five, and **B0 to B2 pool four**"*

The data say four. n per capability class, crashed regime, exclusion applied:
B0 **120**, B1 **120**, B2 **120**; B4 **150**, B4b **150**; AEP-full and B3
180. 120 = 4 crash points × 30.

The same error is in `reports/audit-response-2026-09-23.md:148-149`
(*"leaves five crash points for B0–B2 and five for B4/B4b"* — the second half is
right, the first is not). The phase-53 pre-registration's §5.1 uses the same
"five crash points" phrasing about the pooled rates generally, which is correct
for B4/B4b and wrong for B0–B2.

Note that `supplementary.tex:311` — B4b *"over the five crash points they
pool"* — is **correct**. Only the B0–B2 half of line 327 is stale.

**Fix class: (a) wording**, in three files.

### F6 — B4 "duplicates at the highest rate in the study": VERIFIED false

`paper/sections/06-evaluation.tex:432-433`:
> *"B4 has a durable record, acknowledged by the same barrier, and duplicates at
> the highest rate in the study"*

All three of the audit's readings reproduce, and I add a fourth:

| reading | B4 | B0–B2 | B4 highest? |
|---|---|---|---|
| pooled per capability class, exclusion applied (Table 7) | 0.4467 / 0.5067 / 0.4800 | 0.7417–0.7833 | **no** |
| pooled per system, all six crash points | 302/540 = 0.5593 | 0.7933–0.8156 | **no** |
| maximum over crash points | 0.989 (`after_response_before_resolution`) | **1.000** (`after_resolution_before_barrier`, all three) | **no** |
| unweighted mean over B0's four pooled crash points | **0.575** | B0 **0.764** | **no** |

The only reading under which it is true is "highest among systems that hold a
durable pre-dispatch record" — where the other three (AEP-full, B3, B4b) are all
exactly zero, so the superlative carries no information. *"In the study"* defeats
that reading. The sentence was true only while the mis-delivered cell (B4 0.967
at `after_barrier_before_dispatch`) was in the pool, which is the audit's point
and is correct.

**Fix class: (a) wording.** The honest replacement is that B4 is the only
durable-record system in the study that duplicates at all.

---

## 5. §2.5 — does the committed TLC configuration check the claim §6.3.1 prints?

**VERIFIED by mechanism. I could not re-run TLC — no `java` in this environment —
so the audit's own run output is taken on its authority, and everything around
it is confirmed from source.**

**What the paper needs.** `06-evaluation.tex:442-445`: with the barrier
**enabled** under an AOF rewind, *"only version monotonicity breaks and
\emph{no lost effect} holds"*. That is a claim about `aof-rewind.cfg`.

**Why the committed run cannot establish it.**

1. `formal/configs/aof-rewind.cfg` lists `NoLostEffect` under `INVARIANTS` and
   `P1_VersionMonotone` under `PROPERTIES`, and declares
   `\* EXPECT: fail P1_VersionMonotone`.
2. `formal/AEP.tla:637`:
   `P1_VersionMonotone == [][store'.version >= store.version]_vars` — a **box
   action formula**, i.e. an action property, not a liveness property. TLC
   evaluates action properties **during** state generation and halts on the
   first violating step, exactly as it does for an invariant.
3. `scripts/run_tlc.sh` invokes
   `java -cp "$TLA_TOOLS" tlc2.TLC -config "$run_cfg" -metadir … -workers … -cleanup AEP.tla`.
   There is **no `-continue`**. The run therefore stops at the first
   counterexample.
4. The project already says so in its own comment. `04-protocol.tex:270-273`:
   *"Depths are used rather than state counts because **a failing run stops at
   its first counterexample**, so its state count reflects the search order and
   is not reproducible."*
5. `aof-rewind` stops at depth 4; `b3-no-barrier-restart`'s `NoLostEffect`
   counterexample is at depth 8. So the committed `aof-rewind` run halts before
   reaching the depth at which the paired failure lives, with states still on
   the queue — the audit reports *"30 distinct states found, 20 states left on
   queue"*, which is consistent with items 2–4 and which I could not reproduce
   without a JRE.

**The claim itself is true**, per the audit's derived invariants-only run
(52 940 distinct states, depth 28, no invariant violated). Nothing in the
repository checks it.

**Fix class: (b).** Commit an invariants-only variant of `aof-rewind.cfg` with
`\* EXPECT: pass` and run it. No new measurement; existing machinery on an
existing model. It is the cheapest fix in this entire response.

---

## 6. §8 — the audit-pack and audit-response claims

| # | pack claim | audit's finding | my verdict | evidence |
|---|---|---|---|---|
| 1 | Lines 5 and 16: the first audit found *"nine untrue claims in this file"* / *"the repository wins … in nine places"* | Untrue | **VERIFIED** | `external-audit-2026-09-23.md` §7 has **nine rows, two of them marked True** (*"§1.3 C3 'in any cell measured'"* and *"§5.2: no manuscript text mentions phase 40"*). At most seven |
| 2 | Line 77: *"the phrase is gone (`c8cedbc`)"* | Untrue in substance | **PARTLY** | `c8cedbc` is titled *"C4: drop 'reassigns our own headline result'"* and C4 no longer contains it, so the sentence is **literally true of C4**, which is what its paragraph is about. But *"because it reassigns our own headline claim"* survives verbatim at `06-evaluation.tex:423-424`, so the thing the first audit objected to is still in the paper. The audit's substance is right; "Untrue" overstates the wording |
| 3 | §8a line 719: *"Run 11 of the gates — Yes"* | Untrue | **VERIFIED** | Tested on a fresh `git clone` of `26d4d84`. `check_archive_covers_macros.py` → **exit 2**, *"archive part 2026-09-03: manifest not on disk"* (×3); `--selftest` → **exit 2**, *"no archive manifest is readable; cannot run"*. Cause is in the source: `check_archive_covers_macros.py:58-65` points `MANIFESTS` at `ROOT.parent / "aep-raw-archive*"`, **beside** the repository. `verify_published_archive.py --local` requires a DIR argument that a clone does not have. `check_paper_numbers.py` is not clean from a clone. Three of the eleven scripts in pack §3.1 cannot run |
| 4 | §8a line 752: *"A clone is missing no input that any generator, gate or test reads"* | Untrue | **VERIFIED** | Same evidence. A gate reads three manifests that are not in the clone |
| 5 | Header line 35, §3.1 line 262, §8.3 etc.: the coverage gate fails; phase 53 is in no archive part | Stale at HEAD; *"could not verify the rebuild either way"* | **VERIFIED, and I can close what the audit could not** | The pack rows are stale: line 35 still lists *"the archive-coverage failure (§3.1)"* as a submission blocker and line 262 still shows exit 1. I ran `check_archive_covers_macros.py` on this machine, where the manifests exist: **exit 0**, *"13 roots supply 156 macro attributions; 42 top-level names across 3 archive part(s) — every macro's evidence is obtainable: deposited, or tracked."* The part-3 rebuild in `26d4d84` is real |
| 6 | §8a lines 764–765: *"2 790 run directories / 44 794 files / 848 MB … in the three unpublished archive parts"* | Inaccurate | **VERIFIED** | `paper/sections/09-artifact.tex:41` states it outright: *"2 790 = 1 458 + 1 332; 44 794 = 26 300 + 18 494"* — **two** parts. `docs/29-archive-deposit.md:352` gives part 3 **729 run directories, 13 485 files**. Three-part totals are 3 519 and 58 279. The pack's own §3.1 row contradicts its §8a figure |
| 7 | §2.1 line 161: phase 53 *"is reported separately and pooled with nothing"* | True as stated, incomplete | **VERIFIED** | No rate pools the sessions — all eleven `\Abd*` provenance comments name only `abd-immediate-2026-09-24`. But §6.2 and §6.6 both draw cross-session contrasts as findings, under a rationale (*"A rate computed across two sessions…"*) that argues against doing so |
| 8 | `audit-response` line 77: *"all **84 tracked** `run-config.json` files under `experiments/results/matrix/`"* | Not verifiable from a clone | **VERIFIED** | `git ls-files 'experiments/results/matrix/*run-config.json'` → **0**. `.gitignore:153-157` ignores `experiments/results/matrix/*` except `MANIFEST.csv`, `SHA256SUMS` and `analysis/`. The underlying fact is true on this machine — 84 files exist, all 84 with `"crash_style": null` — but the word *"tracked"* is wrong and no auditor can check it |
| 9 | `audit-response` lines 148–149: dropping the cell *"leaves five crash points for B0–B2"* | Untrue | **VERIFIED** | Four. See F2 |

**Fix class for all nine: (a) wording**, in `reports/audit-pack.md` and
`reports/audit-response-2026-09-23.md`. Item 5 is a refresh, not a correction —
the pack describes a state that `26d4d84` ended.

**One caveat on item 3.** My clone test ran on Windows, where
`check_american_spelling.py` and `check_tla_transitions.py` also failed, for the
environmental reasons the pack's own §3.3 documents. I do not count those
against the claim. The three that fail *because it is a clone* —
`check_archive_covers_macros.py`, `verify_published_archive.py`,
`check_paper_numbers.py` — are the finding, and they reproduce. My
`check_paper_numbers.py` count differs from the audit's (35 passed / 5 failed
here against their 40 / 2), because a fresh checkout gives every file the same
mtime and the staleness checks misfire; the substance — not clean from a clone —
is the same in both environments.

---

## 7. Which fixes interact

**B1 is upstream of §6.6 and §6.2, and it decides what they can claim at all.**

1. **B1 → §6.6.** Re-attributing the duplicates removes §6.6's duplicate-rate
   finding entirely. What is left is the position result, which is real:
   0 of 450 applied-without-dispatch, and B4b at 0/90. But `\AbdDupRange`,
   `\AbdBzeroDupNoReadback` and `\AbdBfourDupNoReadback` can no longer be
   presented as consequences of re-execution, and the claim that the cell shows
   *"the same separation \cref{sec:eval-detection} reports"* goes with them — the
   same separation appears in the crash-free cells, where there is nothing to
   recover from. Do not fix §6.6's wording before deciding this; the wording
   follows the attribution.
2. **B1 → §6.2 → F5.** The *"magnitudes are closer"* sentence
   (`06-evaluation.tex:181`) was added on the strength of phase 53's B4 rates.
   If those are background, the sentence is comparing two timeout backgrounds
   and has to change or go. It cannot be changed in isolation, because the same
   comparison is also stated at `06-evaluation.tex:212` (*"differ by roughly
   0.8"*), `07-related.tex:208` (*"several times below"*) and
   `08-threats.tex:119` (*"the magnitude does not"*). One decision, four
   locations.
3. **F1 → F6 → F2.** All three are consequences of the same exclusion. F6's
   sentence was true only pre-exclusion; F2 is the pre-exclusion count; the
   figures are the pre-exclusion data. Regenerating the figures and recounting
   the crash points should be one pass, and F6's sentence checked against the
   regenerated Table 7.
4. **B2 §6.4 ↔ §6.3.1.** Fixing *"and nothing else"* means stating what §6.3.1
   already predicts — that the barrier is what preserves detection under record
   loss, untested. That is the same scope clause B2 wants in the other six
   places, so do all seven in one pass with one agreed form of words.
5. **B1 → F1's Figure 2 caption.** *"Any interruption after the request is on the
   wire is enough"* is the same misreading as §6.6's, in a caption. Fix it with
   the §6.6 re-attribution, not with the figure regeneration.
6. **§2.5 → B2.** The invariants-only config is what makes §6.3.1's paragraph —
   the paragraph that B2's §6.4 fix has to defer to — actually checked by the
   build. Cheap, and it strengthens the scope argument everywhere else.

**Nothing in this response requires new collection**, with one exception: a
B4-versus-engine comparison matched on exposure as well as position would need a
B5 cell at one kill per execution, which is a new phase. Every other fix is
wording over data already on disk, or re-analysis of tracked CSVs. Phase 54
remains the collection that would give C4's detection half empirical content,
which is the audit's §2.2 point and is outside this response's scope.

---

## 8. Where I would not sign the audit as written

Three places, none of them load-bearing:

1. **B1's "never discloses."** `08-threats.tex:82-84` discloses the existence of
   a *"configurable delay, timeout and error distribution."* The exact and
   sufficient finding is that the **rates** appear nowhere and that §6.1 asserts
   the opposite for `p0`.
2. **§8 item 2, "Untrue in substance."** `c8cedbc` did remove the phrase from
   C4, which is what the pack's sentence is about. The survival at
   `06-evaluation.tex:423-424` is the real finding and it stands; the verdict
   label is harsher than the wording deserves.
3. **B2's count of C4.** C4's evidence clause is correctly scoped, as
   `reports/b1-plan-2026-09-24.md` §1.2 says. Its lead clause and its deployment
   conclusion are not. C4 belongs on the list, but not in the same state as the
   abstract.

Set against that: the audit **understates** F1 (the caption of Figure 2 is
wrong on its own data, not merely stale) and **understates** B1 (the
`before_intent_write` cells already in Table 7 corroborate the re-attribution
from inside the matrix the paper reports, without leaving the crashed regime).
Its §3.2 and §3.4 arithmetic is exact in all sixteen figures I recomputed.
