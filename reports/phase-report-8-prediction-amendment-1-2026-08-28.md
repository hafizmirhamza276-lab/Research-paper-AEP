# Phase 8 · pre-registration, AMENDMENT 1 — run-level interleaving

**Committed and pushed before any session-2 run.** Amends
`reports/phase-report-8-prediction-2026-08-27.md` (commit `16abc99`). Everything
in that document not amended here stands unchanged.

**Disclosure, first and without qualification.** This amendment was written
**after I had seen session 1's outcome data** — AEP-full applied **25/30 under
AUTHORITATIVE_READBACK against 13/30 under NO_READBACK**. Those numbers are
published here, in the amendment that changes the design, precisely because I
saw them. Withholding them is the only thing that could make this decision look
like something other than what it is. They are also **the direction the confound
predicts**, and that is why the design changed.

---

## 1. What session 1 found

The pre-registered balance check failed. AEP-full's two arms differed by
**213.0 ms** in median kill latency (AUTH 1135.0, NO_READBACK 922.0) against a
threshold of **≤ 100 ms**; B3's differed by **1058.8 ms**.

It is not sampling noise. Kill latency **drifts monotonically within a session**
— Spearman(run position, latency) = **0.703** over 120 runs, block medians
829 → 1008 → 1114 → 1167 → 1070 → 1145 → 2162 → 2176 ms.

`build_plan` sorted runs by `(tier, cell_key, repetition)`, so each cell was
collected as one consecutive block and, the cell order being deterministic,
**NO_READBACK was always the earlier block and AUTH always the later one.**

## 2. Why this is a design change and not an adjustment

**Arm and drift are perfectly collinear.** This is the whole reason for the
amendment, and it is a stronger statement than "the imbalance is large":

- A *large* confound is a problem of precision. More sessions, or a covariate,
  can address it.
- A *collinear* confound is a problem of **identifiability**. Position within
  session is a deterministic function of arm. No number of sessions separates
  them, and the pre-registered covariate adjustment on `log(issue_to_return_ns)`
  cannot either, because there is no residual variation in arm at fixed position
  to identify the class effect from.

The pre-registration's contingency ("failing sessions are reported individually;
no session is dropped") was written for a **stochastic** imbalance that would
average out and could be adjusted for. The imbalance is **deterministic**. That
makes the registered fallback non-identifiable rather than merely strained.

**This is new information about the instrument, not about the result.** The
balance check was pre-registered, it operates on the covariate rather than the
outcome, and it is what fired. Discovering that a pre-registered check reveals a
non-identifiable design is the case for which pre-registering checks exists. It
would have been worse to run three more sessions knowing this.

## 3. The change

`experiments/run_matrix.py`, `build_plan`: the sort key becomes
`(tier, repetition, cell_key)`. Every cell's repetition *n* runs before any
cell's repetition *n+1*, so the two arms alternate run by run.

**Run-level alternation, not cell-level counterbalancing.** Counterbalancing
whole cells across sessions would not fix this: the drift is monotonic *within*
a session, so each arm would still be drawn from a different part of it, merely
in a different direction each time. Alternating run by run draws both arms from
the same distribution whatever shape the drift has.

**Identity- and seed-safe, verified.** `run_id` is `cell.slug`-`repetition` and
`cell_seed` digests `matrix_seed`, `MATRIX_VERSION`, `cell.key` and
`repetition`. None reads position. Confirmed: the interleaved plan produces the
same 120 `run_id`s and seeds, the same cell hashes (`8530cc0f`, `5e34a267`,
`99ac28be`, `6adaac10`), in a different sequence. Pinned by
`experiments/tests/test_run_ordering.py`.

## 4. The cause of the drift — reported, and not identified

Time-boxed investigation, per the amendment's instruction to report the cause
**or report that it could not be found**. It could not be found. What was ruled
out is worth more than the negative result:

- **Not resource accumulation.** This was the hypothesis that would have reached
  every multi-cell session this project has run, including the 432-run matrix.
  It is false here: **2 containers** total, **1** project volume, and only **4**
  Docker volumes created on the collection day out of 619 pre-existing. Nothing
  is created per run.
- **Not AOF growth.** Redis's AOF reached 32.4 MB during the session, but at
  rest afterwards, *at that same 32 MB*, kill latency measured **~826 ms** —
  the low end of the session's own range. (`redis/phase2.conf` sets no
  `auto-aof-rewrite-percentage`, so the default 64 MB threshold was never hit.)
- **Not `docker kill`/`start` churn alone.** 24 back-to-back kill/start cycles
  with no harness workload stayed **flat at 827–1155 ms** while load rose
  1.01 → 1.42. Churn does not reproduce it.
- **Not a leak in the collection distro.** Afterwards: no lingering
  Python/uvicorn processes, 70 total processes, 12.6 GB free.
- **It relaxes.** ~20 minutes after the session, kill latency was back to
  baseline. The drift is transient accumulation that dissipates on idle, and it
  requires the harness workload to appear.

**What it most likely is, stated as a hypothesis and not a finding.** The Docker
daemon runs in Docker Desktop's own WSL VM, not in the collection distro, so its
state is invisible from where the harness runs and **is not recorded** — the
same gap 9C §6 named when it concluded the missing provenance was daemon state.
Phase 8.2 added `docker_identity` and `container_state`; neither captures load
inside that VM.

**Interleaving is adopted regardless of cause**, because it protects against
drift whatever produces it.

## 5. Session 1's status: SUPERSEDED DESIGN

Not "dropped", and not a deviation.

**"No session is dropped" exists to prevent removing sessions on the basis of
their results.** Not pooling a session because *the design changed* is a
different act, and calling it a deviation collapses two unlike cases. Session 1
is retained, frozen, committed (`73381e6`) and published, including its outcome
numbers. It is not pooled into the k = 4 estimand set because it was collected
under a design that cannot identify the estimand — a property of the design,
established from the covariate, not a judgement about the numbers.

**Its outcome numbers, published:**

| system | class | runs | applied | declared ambiguous | canary |
|---|---|---|---|---|---|
| AEP-full | AUTH | 30 | **25** | 0 | 30/0 |
| AEP-full | NO_READBACK | 30 | **13** | 30 | 30/0 |
| B3 | AUTH | 30 | **30** | 0 | 30/0 |
| B3 | NO_READBACK | 30 | **28** | 29 | 30/0 |

The AEP-full class difference is +40 pp, in the direction the 213 ms imbalance
predicts, under a design in which the two cannot be told apart. **That is why
the design changed and it is not a result.** 8.6 states it in those terms.

Session 1's other results stand on their own and are not superseded, because
none depends on the arm comparison: the fail-closed invariant (0 exceptions),
Gate 1 (B3 acknowledged 30/30 in both cells), the unfalsifiability check
(AUTH declared ambiguity 0/30), and the integrity checks.

## 6. k, and the collection that follows

**k = 4 unchanged**, and **the no-extension commitment stands.** Session 1 is not
one of the four; the four are collected under the amended design. This is not an
extension of k — it is the same k under a design that can identify the estimand.

All of §5 of the pre-registration (the MDE tables, the [14.3, 18.1] pp baseline
transfer, the declared sd(d) assumption) carries unchanged: it depends on p₀ and
n, neither of which the ordering change touches.

**The tertiary ext4 replication (§6.1) also carries unchanged**, and session 1's
NO_READBACK arm is informative for it even though it is superseded for the arm
comparison, because it is a single-cell quantity that no ordering effect between
arms can distort: **prevented = 28 − 13 = 15**, inside the registered
[6.1, 28.4]. Reported as a fifth observation alongside the four, labelled as
coming from the superseded design.

## 7. The two pre-registration defects, fixed

**7.1 Wall-time stop condition.** Stated as "> 1.5× model (3213 s)". 3213 s is
1.5× the model for a **60-run** session; 8.4's sessions are **120 runs**, model
**4284 s**. Read literally the condition fires at 54 minutes, before any session
could finish even at model speed. **Corrected: the threshold is 1.5 × 4284 s =
6426 s.** Session 1 ran 4968 s = 1.16×, inside it.

**7.2 Gate 2's `dirty` expectation.** Registered as "`dirty: true` is EXPECTED",
because untracked `CLAUDE.md` makes it true in the authoring tree. The
collection host is a **fresh clone at the pre-registered commit with no
untracked files**, so `dirty` is **false**. **Corrected: `dirty` is not a gate
in either direction.** The gate is `commit` at or after `e67efd1`, plus a
session-start `git status --porcelain` that is either empty or shows only
`?? CLAUDE.md`; anything else halts the session.

## 8. Provenance

```
$ git rev-parse HEAD          (parent of this amendment's commit)
73381e6...

$ git status --porcelain
?? CLAUDE.md
```

Session 2 does not begin until this document's commit is on the remote and
verified there by inspection, on the same argument as the original: a design
amendment whose only timestamp is on the machine that then produces the data
proves nothing.

## 9. What this amendment does not change

The primary, both secondaries, the integrity check, the unfalsifiability check,
the HALT set, the missing-vs-false adjudication and both its gates, the
boundary-region verdicts, §9's uncomfortable-result statement, and §10's scope
limits. **All stand as written in `16abc99`.**
