# Phase 8 — B2. The issued prompt, verbatim.

**Why this file exists.** The Phase 6 audit's blind spot **S4.11 #1** is that the
prompts Phases 1A–7 ran under "do not exist in the repository, in git history, or
anywhere on this host", so every bounds check in two audits was made against each
report's *declared* scope rather than against what was actually asked. A session
that widened its own declared bounds to match what it did is invisible to that
instrument.

This is the first phase to record its prompt. It is **not** a retrospective fix:
see `PAPER_ROADMAP.md` § Prompt provenance for why the earlier phases cannot be
closed this way.

**Recorded before any Phase 8 data exists.** The planning session that produced
`reports/plan-phase-8-b2.md` ran read-only; the first thing the execution session
did was commit this file.

---

## Correction to the prompt, found by the plan it commissioned

The prompt below states, under *Hard bounds*:

> Read-only inspection commands (git log, grep, python to read CSVs, `--plan-only`)
> are fine and expected.

**`--plan-only` is not read-only.** `experiments/run_matrix.py:1182-1191` creates
`--results-root` and writes `matrix-plan.json` and `matrix-plan.txt` into it
*before* testing the flag:

```python
    root = Path(arguments.results_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "matrix-plan.json").write_text(...)
    (root / "matrix-plan.txt").write_text(rendered + "\n", ...)
    print(f"plan written to {root / 'matrix-plan.json'} and matrix-plan.txt")

    if arguments.plan_only:
        return 0
```

The planning session did not use it. It imported the module and called
`build_cells()` / `estimated_run_seconds()` directly, which writes nothing.

The correction is recorded here rather than silently applied, because the point
of a prompt record is to show what was asked — including where what was asked was
wrong. Carried as *Found but not fixed* #1 in the plan.

---

## The prompt as issued

> Phase 8 — PLANNING ONLY. Produce a plan. Change nothing.
>
> Hard bounds for this session:
> - Read-only. No edits, no commits, no new files except the plan document itself.
> - Do not run the matrix, do not start Redis, do not regenerate any table.
> - Read-only inspection commands (git log, grep, python to read CSVs, --plan-only)
>   are fine and expected.
> - If you find yourself wanting to fix something you noticed, write it in the plan
>   under "found but not fixed". Do not fix it.
>
> Context to read first:
> - `PAPER_ROADMAP.md` § CURRENT PHASE
> - `docs/24-revision-backlog.md` §B2
> - `reports/phase-report-6-audit-2026-08-21.md` §S4.10 and §S4.11
> - `reports/phase-report-7-fixes-2026-08-21.md`
> - `experiments/run_matrix.py`, `scripts/freeze_results.py`,
>   `scripts/paper_tables.py`, `experiments/analyze.py`
>
> The work being planned is B2: take the barrier's prevention claim from one
> capability class to three, then re-derive only what changes.
>
> Your plan must answer these, each with the evidence you used:
>
> 1. COVERAGE, FROM DATA NOT PROSE. Enumerate which (regime, endpoint, system)
>    cells already exist in `experiments/results`. Derive this from the frozen
>    result directories, not from what the backlog or the audit says. If the data
>    and the prose disagree about which capability classes were collected under
>    `redis-kill-preack`, say so explicitly and say which is wrong. This is the
>    first thing I will check.
>
> 2. REACHABILITY. For each cell that is missing, state exactly how it would be
>    invoked. If any of them cannot be reached with `run_matrix.py` as it stands
>    today, say so, quote the code that prevents it, and propose the minimal
>    change. Regime definitions are load-bearing for cells already collected — any
>    change to one must be shown not to alter the meaning of existing results.
>
> 3. PREDICTION. State the falsifiable prediction the backlog already specifies,
>    and where in the repo it will be recorded BEFORE the run. State what result
>    would contradict it and confirm that such a result gets reported as the
>    finding rather than explained away.
>
> 4. INTEGRITY. Describe the freeze-and-verify step concretely. The Phase P report
>    records that `core.autocrlf` silently corrupted 6 of 7 committed CSVs and that
>    only hashing the STAGED blob against SHA256SUMS caught it. Your plan must say
>    which artifact is hashed and at what point.
>
> 5. BLAST RADIUS. List every file the execution session would touch, and every
>    paper number that could move. Name the tables and the macros. If a number in
>    `paper/generated/numbers.tex` could change, say which.
>
> 6. COST AND STOP CONDITIONS. Wall-time estimate with its basis (`run_matrix.py`
>    has a fitted wall-time model — use it, and say if you think it is wrong).
>    State what would make you stop mid-run and come back rather than continue.
>
> 7. PHASE 8.0. Include as step 0: creating `prompts/` and committing this prompt
>    text there before the execution session runs, plus a short "Prompt provenance"
>    note in `PAPER_ROADMAP.md` recording that Phases 1A–7 have no such record and
>    that this is audit blind spot S4.11 #1, not retrospectively closeable.
>
> 8. WHAT THIS DOES NOT DO. Be explicit about the limitation that survives: three
>    capability classes on one host at one crash point is still one host at one
>    crash point.
>
> Output: a single plan document at `reports/plan-phase-8-b2.md`. Sequenced steps,
> each with its verification. Where you are uncertain, say "uncertain" and say what
> would resolve it — do not fill the gap with a confident guess. I am going to have
> this plan reviewed before anything runs.

---

## Review round 1 — amendments to the plan's first draft

> APPROVED with amendments.
>
> Q1 (option 1) — three conditions on the paired design:
>
> A. Before any paired session runs, extend the harness to record per run:
>    docker version, docker daemon uptime/state, and the MEASURED kill latency
>    for the redis kill (arm-to-death wall time), into run-config.json or the
>    run record. 9C §6 names this as the provenance gap that "now matters most"
>    and A3 names docker kill latency as the driver. Running 5.2 h of paired
>    sessions without it reproduces the same uninterpretability at higher cost.
>    Declare this as a harness change; show it cannot alter counts.
>
> B. Pre-register k NOW, in the plan, with the expected paired precision, and
>    commit to not extending k after seeing results. If you believe k=4 may be
>    insufficient, either raise it now or pre-register an explicit stopping rule.
>    Adding sessions post hoc is optional stopping and would undercut the
>    pre-registration discipline this phase has otherwise kept.
>
> C. Sequence the paper fix BEFORE the new collection — see below.
>
> Q2 (option 1) — agreed, AUTH only, but record the reason as the regime's own
> comment in run_matrix.py ("Collecting the middle endpoint as well would cost 60
> runs to interpolate between them"), not "no code change". AUTH and NO_READBACK
> are the two extremes and therefore the sharpest test of the backlog's
> prediction; POS_ONLY interpolates.
>
> Defer POS_ONLY explicitly in the plan, and name the route: a NEW regime
> (e.g. redis-kill-preack-posonly), NOT an edit to REGIME_REDIS_KILL_PREACK.
> Extending the existing tuple changes the definition under which already-frozen
> cells were collected; a new regime leaves it byte-for-byte intact and makes the
> provenance visible in the cell identity hash.
>
> NEW STEP, ahead of the collection — Phase 8.1, the paper fix from data that
> already exists:
>
> The five sessions in 9C are 150 runs that currently live only in a report.
> \UnwantedPrevented is printed as 18; it ranges 8-24 across five identical
> sessions. That is a live defect in the manuscript today, independent of B2, and
> it sits on the barrier's only remaining claim.
>
> Plan a separate, small phase that:
>   - decides whether the 2026-08-07 cell and the four 2026-08-21 sessions are
>     poolable, from the recorded evidence (identical cell hash, seed, platform
>     fingerprint, pinned image, 40/44 config keys) — and states the four
>     differing keys and why they do or do not matter;
>   - replaces the point estimate with a session-clustered interval, session as
>     the unit, consistent with the run-cluster bootstrap the paper already uses
>     elsewhere; do NOT use the naive Wilson interval on pooled 150 — 9C §3 shows
>     it is four times too narrow;
>   - reports B3's flatness (28/30, range 0 across five sessions) explicitly in
>     the paper, because it is the control that keeps the mechanism claim intact
>     while the magnitude claim weakens;
>   - states in 08-threats.tex that the magnitude is session-variable and that the
>     direction held in 5/5;
>   - lists every macro and table that moves.
>
> Frame this as strengthening, not retreating: five independent replications of
> the headline cell with a clustered interval is more evidence than one cell with
> a point estimate, and reviewers at DSN/Middleware will read it that way.
>
> Still plan-only. Nothing runs, nothing is edited, until I approve the plan.

## Review round 2 — CHANGE 1 and CHANGE 2

> APPROVED with two changes. The plan is better than the amendments it was given
> — §0 in particular answers Amendment A more strongly than the amendment asked.
> Every citation I checked is exact, and Found-but-not-fixed #1 correctly
> identifies an error in the prompt: --plan-only is not read-only. Fix that in the
> prompt text you commit at 8.0, with a note that the correction came from this
> plan.
>
> CHANGE 1 — do not lock the estimand or k yet. New step 8.1.0, ahead of everything.
>
> §0's mechanism has a consequence the plan does not draw. In this regime AEP-full
> applies an effect only if WAITAOF returned before Redis died, so its applied
> count is counting how often the ack won a race whose width is the kill latency.
> UnwantedPrevented = 28 - (times the ack won) is therefore a property of the
> fault injector's timing distribution, not of the protocol. That is why it ranged
> 8-24 while B3 sat at range 0.
>
> The claim that does not depend on the race: AEP-full never dispatched without a
> durable acknowledgement; B3 dispatched regardless of durability. If that holds
> exactly across all 150 runs it is a deterministic fail-closed result, and it is
> stronger than any interval on a marginal rate.
>
> So, before 8.1 edits any prose and before 8.3 pre-registers anything:
>
>   a. Determine whether `applied => durable ack issued` is checkable from the
>      runs already on disk. Note that runner.py emits no per-execution barrier-ack
>      event (I checked the emit list), so it may not be. Say plainly whether it is.
>   b. If it is checkable: check it across all 150 runs and report exceptions. Zero
>      exceptions is the headline.
>   c. If it is not: 8.2 adds the ack event — smaller than surfacing
>      issue_to_return_ns — and the conditional form becomes available for the new
>      sessions.
>   d. Note the invariant is one-directional: ack does not imply applied, since the
>      kill can land after the ack and before dispatch. Do not overstate it as a
>      biconditional.
>
> Then re-decide, and say which you chose and why:
>   - whether 8.1's headline is the conditional invariant with the marginal rate
>     reported as a characterisation of the fault injector, or the clustered
>     interval as currently planned;
>   - what the primary estimand for 8.4 is, given that answer;
>   - and only then, k. The k=6 derivation is a power calculation for mean(d). If
>     the estimand changes, the calculation does not carry over. Re-derive it,
>     commit the new k in 8.3, and the no-extension rule applies to whatever k you
>     land on.
>
> If after this the answer is still mean(d) at k=6, that is a fine outcome — but
> it must be a decision taken with the mechanism in hand, not the default.
>
> CHANGE 2 — freeze the 240 Phase 9 runs in 8.0, not 8.1. Approved as in scope.
>
> §4 records that the evidence for 9C's central finding and for §0's mechanism
> exists on one Windows host and nowhere else. That is a data-loss risk, not a
> scope question. Move it ahead of everything: freeze and track the four b2-*
> roots' analysis products first, under the same staged-blob discipline as §4.
>
> In the same step, resolve Uncertain #3: list the WSL measurement tree at
> /root/aep and establish whether the 2026-08-07 kill runs' events.jsonl survive.
> If they are gone, §0's mechanism rests on four sessions and not five, and 8.1
> must be written knowing that rather than discovering it midway.
>
> Everything else stands as written — including k not being extended after the
> fact, the new-regime route for POS_ONLY, 8.1 before 8.4, the HALT conditions,
> and the refusal to re-run a contradicting result.
>
> Still no execution beyond 8.0 and 8.1.0. Report back after 8.1.0 with the
> estimand decision and the re-derived k before collecting anything.

## Review round 3 — AMENDMENT 1 and AMENDMENT 2, and the execution authorisation

> APPROVED for execution through 8.0 and 8.1.0 only, as the plan scopes it.
> Rev. 2 answers CHANGE 1 and CHANGE 2 properly, and §0.5 is a better answer than
> the question deserved — it establishes not just that the invariant is
> unavailable retroactively but exactly why, four independent ways.
>
> Two amendments, both due BEFORE 8.3, neither blocking 8.0 or 8.1.0. Fold them
> into the plan document you commit at 8.0.
>
> AMENDMENT 1 — the invariant must not set k.
>
> _checkpoint is awaited on the protocol path (intent_workflow.py:489-494), so
> dispatch => checkpoint-traversed holds by construction. Zero exceptions is
> therefore near-certain, and what the check primarily exercises is the harness's
> emission fidelity. The plan says this itself in §0.5's honesty caveat and in §8
> ("confirmatory, not exploratory") — but then makes it primary and derives k from
> its rule-of-three bound.
>
> Keep the invariant pre-registered, keep its HALT condition, and check it: after
> 8.2 it costs nothing and rides along on any collection. But:
>
>   - make 3.2 (the covariate-adjusted class effect) the phase's primary estimand
>     and its headline. That is the question B2 exists to answer;
>   - re-derive k from 3.2, with a stated minimum detectable class effect. Every
>     other quantity in this plan is derived — the wall-time model against observed
>     ratios, sd(d) from 9C's variance components, the rule-of-three table. 3.2
>     currently gets "adequately powered" with no derivation, and it is the
>     estimand that matters most;
>   - fold Uncertain #3 into that derivation: if AUTH's applied fraction differs
>     from NO_READBACK's 35.8%, it moves 3.2's power, not only the invariant bound;
>   - demote the invariant to a pre-registered integrity check with a HALT, and say
>     plainly in the report that it is confirmatory of code-enforced behaviour along
>     a single code path.
>
> If the re-derivation lands on k=4 anyway, that is fine — but it must be derived
> from the estimand that drives the phase.
>
> AMENDMENT 2 — bound the ack emit's timing effect; do not assert it away.
>
> RedisKillInjector.checkpoint() currently returns after two comparisons at this
> point (redis_kill.py:260-262 — the armed point in this regime is
> after_intent_before_barrier, not AFTER_DURABLE_...). Adding an emit puts a write
> on an awaited call, on the protocol path, at the exact boundary where the race
> §0 measured is decided.
>
> 8.2's verification — re-running analyze.py over an untouched Phase 9 root and
> diffing columns — tests analysis, not collection timing, and structurally cannot
> detect a perturbation of the race. Replace the assertion with:
>
>   a. a stated, bounded argument: measure the added cost at that boundary and
>      compare it against the 880-1216 ms kill-latency envelope. Microseconds
>      against a ~1 s race is negligible; say so with the number, not by assertion;
>   b. if the emit cannot be made non-blocking cheaply, prefer buffering it and
>      flushing after the execution completes, so nothing new is awaited inside
>      the race;
>   c. record the harness version in each results root, and state in 8.4's report
>      that Phase 9's roots and Phase 8's were collected under different harness
>      versions. The plan already keeps them in separate roots, which is right —
>      make the reason explicit so nobody later pools them without noticing.
>
> Everything else stands: k not extended once committed, POS_ONLY via a new regime,
> 8.1 before 8.4, the HALT conditions, the refusal to re-run a contradicting
> result, and the enforced-in-code caveat surviving into the report.
>
> Proceed with 8.0 now — the 240 runs on one host are the urgent item. Then write
> up 8.1.0 and stop. Report back with the re-derived k and the timing bound before
> 8.1 or 8.3.

---

## What the planning session was asked, in one line

Produce a plan for backlog B2 and change nothing. Three review rounds then
amended it: pair the design within sessions, defer POS_ONLY to a new regime, put
the paper fix before the new collection, rescue the untracked Phase 9 data first,
establish whether the fail-closed invariant is checkable retroactively, and
derive k from the estimand that actually drives the phase rather than from the
one that is easiest to bound.
