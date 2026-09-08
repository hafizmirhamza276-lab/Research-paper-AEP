# Phase 15 — WS-6, the B5 Temporal baseline

Prompts recorded per `docs/26` §3 rule 4: verbatim, before any data commit, with
corrections recorded alongside rather than silently applied.

**No B5 data exists at the time of writing.** Prompts 1–6 below produced design,
instrument and verdict-script work only; prompt 7 asked for collection and is
recorded here together with the reason collection did not happen.

---

## Prompt 1 — start WS-6

> Start WS-6 from docs/26 §4: run a real durable-execution engine as a baseline.
>
> Temporal server via docker compose, pinned image, a worker whose activity calls
> the mock provider, two configurations: maximumAttempts unlimited and = 1. Crash
> injection by SIGKILL of the worker at the same six crash points; document the
> mapping from Temporal's activity lifecycle to those points in B5_SEMANTICS.md.
>
> Pre-register: B5 reproduces B4's duplicate rates and B5b reproduces B4b's
> lost-effect rates within run-clustered intervals.
>
> Design and pre-register only in this pass. Do not collect yet.
>
> Constraints for this pass. Write documents and configuration; do not bring any
> stack up, do not pull images, and do not run the test suite. If a design
> question can only be settled by running something, record it as an open
> question for the collection pass rather than running it.
>
> The six crash points are the existing ones -- read them from the harness rather
> than restating them from memory, and say where you read them from. The mapping
> in B5_SEMANTICS.md is the load-bearing part of this pass: Temporal's activity
> lifecycle does not have six points, so state for each one whether the mapping
> is exact, approximate, or absent, and where it is approximate say what that
> costs the comparison. A mapping that claims six clean correspondences is the
> thing to be suspicious of.
>
> Follow B4_SEMANTICS.md's structure so the two baselines can be read side by
> side.
>
> Pre-register per docs/26 rule 5: hypothesis, run counts, unit of analysis,
> stopping rule, and the exact analysis to be run, committed before any data
> exists. WS-4's ordering is the precedent worth repeating -- the verdict script
> written before collection is why its REFUTED verdict was credible. Say in the
> pre-registration whether you intend to do the same here.
>
> Commit and push.

## Prompt 2 — close the five open questions

> Close WS-6's five open questions. Do not collect.
>
> 1fecb1f lists five that must close before any data commit. Close them with
> evidence, one pass, and stop.
>
> Pin the images. compose.temporal.yml carries tags, not digests. Resolve each to
> a sha256 digest and pin it, the same way compose.phase2.yml pins redis and
> toxiproxy. Record which tag resolved to which digest and when.
>
> Settle the Start-To-Close timeout. §5 says this decides whether H1 is testable
> at all, so it is the one that can invalidate the pre-registration rather than
> merely delay it. Establish it by measurement on the real stack, not by reading
> docs, and say what you measured. If it turns out H1 is not testable as
> pre-registered, stop and report -- do not adjust the hypothesis to fit what the
> engine does. Changing a pre-registration after touching the system is the
> failure d8b2ca5's ordering exists to prevent.
>
> Then the 120 s recovery deadline against that timeout, and whether point 6's
> race is observable on loopback.
>
> Last, the crash injector against an SDK worker. Prove the gate can fail: show
> the injector reaching the worker at a named point, and show that a worker it
> cannot reach refuses the run rather than proceeding. An injector only ever
> exercised where it works will approve one that does not -- that is the WS-4
> self-test lesson, and it cost four attempts there.
>
> Bring the stack up for this pass and tear it down after. No WS-4 collection is
> running, so the host is free, but R8, R8a, R8b and R12 apply: capture evidence
> before teardown if anything fails, release binds before unmounting, and check
> for orphaned listeners on the ports this stack uses.
>
> Report each question as closed with its evidence, or as still open with what
> blocks it. Do not collect, do not write analyse_b5_agreement.py in this pass.
>
> Commit and push.

## Prompt 3 — complete the probe

> Complete the WS-6 probe. One run to completion. Do not collect.
>
> Four things remain and they all come from the same probe dying early:
>
> The gate's both-branch proof, per rule 13. B5_INJECTOR_DISABLED=1 is
> implemented and wired but never executed. Run both branches: a run where the
> injector reaches the point and the gate is silent, and a run where it cannot
> reach and the run voids with a reason naming the injector, not the deadline.
> Until both have run, the gate is not proven and must not be described as
> closed.
>
> The two crash points after the provider call. Three of five are demonstrated;
> these two are not, and are not to be claimed until they are.
>
> The retry-lands measurement, which closes Q2 and decides whether H1 is
> testable. A timeout must clear ~2.06 s per the measured p50 2015.0 / p95
> 2024.2. If H1 proves untestable as pre-registered, stop and report -- do not
> adjust it.
>
> Q3 against the measured timeout, and Q4, whether point 6's race is observable
> on loopback. Leave B5_SEMANTICS.md at approximate unless the evidence
> downgrades it; if it becomes a second absent point, say what that costs the
> comparison.
>
> R14 now applies to this probe itself. Before running it, check that every
> readiness and sampling path in it can report the third outcome -- reached, not
> reached, and could not look or looked in the wrong place. The last two passes
> both died on checks that could only say "not ready". Fix them first, then run.
>
> R8, R8a, R8b, R12 apply to teardown: preserve evidence before tearing down,
> verify ports 7233/8233/8099 are free rather than asserting it.
>
> Report each item as closed with evidence or open with what blocks it. Commit
> and push.

## Prompt 4 — build the supervisor

> Build the B5 worker supervisor, then close Q5c. Do not collect.
>
> Q2b established that no B5 cell can measure a duplicate until B5 respawns its
> worker after SIGKILL. A duplicate is by definition what the second attempt
> does, and run_one leaves nothing to poll after the kill. B4's harness respawns;
> that is what makes its replay observable. Four rounds missed this.
>
> Build the supervisor. Read how B4's harness does it and follow that shape
> rather than inventing one, and say where you read it. The two harnesses
> producing duplicates by different mechanisms is exactly the confound this
> baseline exists to avoid.
>
> Prove it, per rule 13, and prove it in both directions: a run where the worker
> is killed and respawns and the retry lands, and a run where respawn is disabled
> and the run voids naming the supervisor rather than reporting
> PENDING_AT_DEADLINE. The second branch matters most -- a missing respawn
> currently looks identical to a legitimate result, which is the same shape as
> the injector gate you just built.
>
> Then redo Q2b with the supervisor in place. If H1 still proves untestable as
> pre-registered, stop and report. Do not adjust the hypothesis.
>
> Then close Q5c. AFTER_RESPONSE_BEFORE_RETURN sits at n=1 with
> provider_calls=0. Give it the n=8 treatment Q4 got. With 15% timeouts and 5%
> errors roughly one trial in five cannot reach it by construction, so n=1 tells
> you nothing either way. Claim it only if the trials demonstrate it.
>
> R12a: keep the observers running from before bring-up. The last run had no
> unexplained restart and was also the first you did not interfere with -- that
> is a correlation of one, not an explanation, and the four occurrences stand.
>
> R1, R8, R8a, R8b, R12, R14 apply. Verify teardown from a script file.
>
> Commit and push. If the push hangs, say so rather than reporting it pushed.

## Prompt 5 — write the verdict script

> Write analyse_b5_agreement.py, before any B5 data exists. Do not collect.
>
> 1fecb1f §5.1 registered this: the script, its thresholds, and its
> AGREES/DISAGREES rule committed before the first B5 run. Every open question is
> now closed, so this is the last thing standing between here and collection --
> and it must be written now, while there is nothing to fit it to. WS-4's REFUTED
> verdict was credible for exactly this reason.
>
> It applies the pre-registration and nothing else: H1 duplicates, H2 lost
> effects, H3 non-escalation, against B4 and B4b's frozen rates with
> run-clustered intervals. Read the frozen rates from where they live rather than
> restating them, and say where you read them from.
>
> Report the agreement AND the reasons, both. Do not collapse a cell to AGREES
> when the agreement rests on something the pre-registration flagged. In
> particular: PENDING_AT_DEADLINE above 20% makes a cell uninformative, and B5
> has no after_intent_before_barrier point at all, so any summary must say which
> cells are absent rather than showing a complete-looking table. WS-4's script
> could say "held, but for a reason the pre-registration flagged as
> complicating" -- this one needs the same capability.
>
> The void verdicts are instrument failures, not measurements. VOID_INJECTOR_*,
> VOID_SUPERVISOR_NEVER_RESPAWNED and VOID_WORKER_NEVER_READY must be excluded
> from rates and reported separately with counts. A void silently counted as "no
> duplicate" would make B5 look better than B4 for an instrument reason.
>
> Prove it non-vacuously with fixtures: agreement, disagreement, and a run set
> dominated by voids. Each must produce a different reading. Promote it to
> scripts/ with a test, per docs/26 rule 14.
>
> Three recorded items, decide each rather than carrying them: truncate
> worker.err per run, fix or remove the deaths counter since the printed number
> counts polls not deaths, and settle whether VOID_WORKER_NEVER_READY cold starts
> should be retried before collection rather than spent -- you raised that one
> yourself as avoidable power loss.
>
> Do not collect. Commit and push; if the push hangs, say so.

## Prompt 6 — collect (this one)

> Collect WS-6, the B5 Temporal baseline.
>
> Rule 4 first: append every prompt issued since the last prompts commit,
> verbatim, corrections recorded alongside, before any data commit.
>
> Then fix the Start-To-Close value and commit that choice BEFORE collecting,
> with the reasoning and the measurements that support it. It is the last free
> parameter in this cell, and a value chosen after seeing runs is a fitted
> parameter however well argued. 2500/4000/8000 ms all completed at 24-27 s; say
> which you pick and why, and what it costs the comparison with B4.
>
> Then collect exactly what 1fecb1f pre-registered: 120 runs primary, 240
> secondary, 30 x 10, both configurations, into a new dated directory. Frozen
> results are immutable. Follow the pre-registered stopping rule as written; do
> not adjust it mid-collection.
>
> Launch with nohup setsid. Record the environment with
> verify_measurement_host.py. Do not run the test suite against anything this
> collection is using.
>
> Do NOT run analyse_b5_agreement.py. Read the run count and the void counts and
> nothing else -- the void verdicts are instrument health, not outcome, so
> reading them keeps a void decision outcome-independent. Any decision to void
> the session must rest on those alone, as WS-4's did.
>
> If voids exceed what the instrument should produce, stop and report rather than
> collecting through it. Both gates exist to make instrument failure loud; a
> session that ignores them wastes the reason they were built.
>
> R1, R8, R8a, R8b, R12, R12a, R14 apply. Kill by PID only. Observers from before
> bring-up. Capture evidence before any teardown that follows a failure. Verify
> teardown from a script file.
>
> Stop when the data is committed and pushed. No analysis, no verdict, paper
> untouched. If the push hangs, say so rather than reporting it pushed.

## Prompt 7 — build the collection runner

> Build the B5 collection runner. Do not collect.
>
> 1df2b16 names five components collection needs. Build them, and build the gate
> with them -- a harness built and used in the same pass gets no gate, and both
> existing B5 gates exist because instrument failure was invisible twice.
>
> The load-bearing constraint is oracle attribution.
> undetected_duplicate_applications and lost_effect_executions must come from the
> same reconciler that produced B4's, against the same provider ledger. If B5's
> rates came from anywhere else, agreement or disagreement would be an artefact
> of attribution rather than of the engines -- the confound WS-6 exists to
> remove. Read how B4 reconciles and use that path; do not write a B5-specific
> one. Say where you read it.
>
> Register B5 in contract.py's SystemId and in run_matrix.py the way the other
> systems are registered. Follow the existing shape rather than inventing one.
>
> Prove the runner writes what analyse_b5_agreement.py reads. That script is
> already committed and predates any data, so the runner must satisfy it, not the
> other way round. If the two disagree on format, change the runner. Changing the
> verdict script now is the one edit the ordering exists to prevent -- if it is
> genuinely wrong, stop and report rather than editing it.
>
> Prove the gate can fail, both directions, on the real stack: a run the
> reconciler can attribute, and a run where attribution is unavailable, which
> must void naming attribution rather than reporting a zero rate. A missing
> oracle currently looks like a clean result.
>
> Do not collect. The pre-registered stopping rule voids on run count, so a
> session started before the gate is proven has nothing for a void decision to
> rest on.
>
> Note in the report that this is the fifth instance of the R14 pattern, and that
> this one was a readiness claim rather than a check -- R14 covers instruments
> that cannot say "I looked in the wrong place"; a report asserting readiness
> without running the grep is the same defect in prose. Say whether R14 should be
> widened to cover it or whether that is a different rule.
>
> R1, R8, R8a, R8b, R12, R12a, R14 apply. Commit and push; if the push hangs, say
> so.

## Prompt 8 — prove the silent branch, then collect (this one)

> Prove the attribution gate's silent branch, then collect.
>
> Give each run its own ledger, as WS-4's runs had. The shared probe ledger is
> why branch A voided -- 129 rows from days of probe runs that the run's plan
> cannot explain. That was the gate working, and it named a requirement that was
> never written down.
>
> Re-run prove_attribution_gate.py and observe branch A silent. Both branches
> must be observed in one run of the proof, not one now and one from memory.
> Until branch A is silent, do not collect.
>
> Then collect. Rule 4 first: append the prompts issued since d096f47, verbatim.
>
> Collect exactly what 1fecb1f pre-registered at the 4000 ms Start-To-Close fixed
> in 06d51b0: 120 runs primary, 240 secondary, 30 x 10, both configurations, into
> a new dated directory. Frozen results are immutable. Follow the pre-registered
> stopping rule as written; do not adjust it mid-collection.
>
> Launch with nohup setsid. Record the environment with
> verify_measurement_host.py. Do not run the test suite against anything this
> collection uses.
>
> Do NOT run analyse_b5_agreement.py. Read the run count and the void counts and
> nothing else. The voids are instrument health, not outcome, so reading them
> keeps a void decision outcome-independent as WS-4's was. If voids exceed what
> the instrument should produce, stop and report rather than collecting through
> it.
>
> Two things to record while you are there.
>
> The regression in test_the_unit_of_analysis_is_the_run is a different failure
> from R14's five: the checker was not weak, it was the wrong checker. 856d78a
> ran check_paper_numbers.py and not the suite, so a fix was verified by a gate
> that could not see it. Record it as its own entry -- verify a change with the
> gate that covers what you changed -- rather than folding it into R14's
> widening.
>
> And record that CI did not install the b5 extra the suite now imports, so tests
> would have skipped rather than failed. A suite that skips what it cannot import
> reports green for work it never ran.
>
> R1, R8, R8a, R8b, R12, R12a, R14 apply. Stop when the data is committed and
> pushed. No analysis, no verdict, paper untouched. If the push hangs, say so.

---

## Prompt 9 — resume

> resume

## Prompt 10 — fix the crash point before attempt 2

> Fix session.py's crash point before attempt 2. Do not launch, do not collect.
>
> session.py:83 hardcodes crash_point=PRIMARY_CRASH_POINT in run_config(), and :151
> passes a hardcoded "ACTIVITY_ENTERED_BEFORE_CALL" to run_once(), which is the real
> injection point. resolve_for_system()'s return value is discarded.
>
> Harmless for the primary stage. For the secondary sweep, cells() yields four crash
> points and all 240 runs would inject the same fault while run_ids label them as
> four different ones. That is silently wrong data of exactly the class every gate
> in this workstream exists to prevent, and nothing downstream would catch it.
>
> Fix it so the injected point comes from the cell, through resolve_for_system().
>
> Prove it can fail, per rule 13: run one trial per crash point and show each
> records the point it was told to inject, and show that a mismatch between the
> labelled point and the injected one voids rather than proceeding. A run whose
> label and fault disagree must not be collectable.
>
> Then verify the four launch blockers are closed and stay closed: the runner
> committed, the launch detached with nohup setsid, the root-reuse guard refusing an
> existing root rather than appending, and the distro held open. Verify each by
> testing it, not by reading the change.
>
> Do not launch attempt 2. Report and stop.

## Prompt 11 — push, void, then collect (this one)

> Push, write the void record, then launch attempt 2.
>
> First push. 593ea64 and 4c4d9c3 are local. If it hangs, say so rather than
> reporting it pushed.
>
> Then write the void record for attempt 1, before launching. It has been decided
> but nothing on disk records it: 39/120 runs, stage-primary-finished.json absent,
> postgres and temporal stopped mid-collection. Record it as attempt 1 of 3 with
> two remaining, and record that it was also collected on uncommitted code, which
> disqualifies it under rule 5's ordering independently of the run count. Move the
> root aside as voided with a reason file; do not delete it.
>
> Record in it the two defects that would have made it worthless even had it
> finished: the hardcoded crash point, and crash_point carrying B5's vocabulary
> where analyse_b5_agreement keys on roadmap names, so every cell would have found
> no frozen counterpart. Those are why the void is not merely a lost session.
>
> Also record the .wslconfig correction: vmIdleTimeout=-1 is not honoured by WSL
> 2.7.3.0, the non-detached launch was the actual cause, and the comment in
> .wslconfig should not be trusted.
>
> Then launch attempt 2. Rule 4 first: append the prompts issued since d096f47,
> verbatim.
>
> Collect exactly what 1fecb1f pre-registered at the 4000 ms Start-To-Close fixed
> in 06d51b0: 120 runs primary, 30 x 10, both configurations, into a new dated
> directory. Frozen results are immutable. Follow the pre-registered stopping rule
> as written; do not adjust it mid-collection.
>
> Launch detached with nohup setsid, keepalive running. Record the environment with
> verify_measurement_host.py. Do not run the test suite against anything this
> collection uses.
>
> Do NOT run analyse_b5_agreement.py. Read the run count and the void counts and
> nothing else, so any void decision stays outcome-independent.
>
> Watch the attribution voids. Your proof trials showed VOID_ATTRIBUTION_UNAVAILABLE
> at the two earliest crash points with 2 executions, and you noted it may be an
> artefact of that configuration. The primary stage runs only
> after_barrier_before_dispatch, which attributed cleanly across all 39, so it
> should not appear -- if it does, stop and report rather than collecting through
> it.
>
> R1, R8, R8a, R8b, R12, R12a, R14 apply. Stop when the data is committed and
> pushed. No analysis, no verdict, paper untouched.

---

## Prompt 12 — read the WS-6 outcome

> Read the WS-6 outcome. Run analyse_b5_agreement.py against 0c6bcf4's session root.
>
> Report the reading AND the reasons, both. The script evaluates in a fixed order --
> absent point, then voids, then the pending bound, then interval overlap -- so
> report which stage each cell resolved at, not only its final reading. A cell
> reading AGREES after passing all four is a different fact from one that never
> reached the overlap test.
>
> Report per hypothesis: H1 duplicates, H2 lost effects, H3 non-escalation. H3 is
> absolute -- one declared ambiguity refutes it -- so say plainly whether any
> appeared.
>
> Say explicitly which cells are NOT_TESTABLE_ABSENT_IN_B5. B5 has no
> after_intent_before_barrier point, and that is where B4 has frozen data at all
> three response classes. The summary must not read as a complete comparison.
>
> The 2 VOID_WORKER_NEVER_READY are excluded from rates and reported with counts.
> Confirm the script did that rather than assuming it.
>
> Do not edit the script to fit what you see. If it errors, or the data has a shape
> it does not handle, report that as a finding and stop. Editing a verdict script
> after seeing data is what this ordering exists to prevent; any change it needs is
> a separate prompt with the reason recorded.
>
> Do not touch the paper. No macros, no prose, no §VI, no §VIII. This pass reads the
> result and nothing else.
>
> Then two small records. First, the push hang: the documented off-screen credential
> dialog did not apply, no stalled process and no index.lock, and a plain retry with
> a longer window cleared it. Update the handoff §5 note so the next reader tries a
> retry before hunting a dialog.
>
> Second, record the 2 VOID_WORKER_NEVER_READY as an open question -- both in the
> first cell, both with empty worker.err, none in attempt 1's 39 runs. Do not chase
> it.
>
> Commit and push. If the push hangs, retry once with a longer window before
> reporting it as a hang.

## Prompt 13 — establish why the intervals are zero-width

> Establish why three of four B5 intervals are zero-width. Do not touch the paper.
>
> The reading at 3e633d7 gives B5 rates of 0.4000 [0.4000, 0.4000] and 0.3000
> [0.3000, 0.3000] twice. A cluster bootstrap returns zero width only when every
> run produced an identical count. Confirm that directly from the run records: the
> per-run duplicate and lost-effect counts for each of the four cells, min, median,
> max and the distinct values observed.
>
> If every run is identical, establish whether that is a property of the engine or
> of the harness. Candidates to separate, not to choose between: the crash fires at
> a fixed point so the same executions are always in flight; the supervisor
> respawns once and the retry set is therefore fixed; the provider's 15% timeout
> and 5% error should introduce variation and apparently did not, which is itself
> worth checking against the run records.
>
> B4's frozen cells have wide intervals. Establish whether B4's per-run counts vary
> and B5's do not, or whether B4's width comes from having 3 runs where B5 has 30.
> Read both from the same place. That difference alone could explain the
> non-overlap without either engine behaving differently.
>
> Do not edit analyse_b5_agreement.py. If the estimator is doing something wrong
> with a degenerate cluster, that is a finding to report, not to fix in the pass
> that discovered it.
>
> Report what you find. If the determinism is real and explicable, say so and say
> what it means for reporting an interval at all. If it indicates the harness is
> constraining the outcome, that is a defect and the DISAGREES reading does not yet
> support a claim about B4.
>
> The agreement.txt/json artifacts in the session directory are fine as evidence of
> what was run -- keep them.
>
> Commit and push.

## Prompt 14 — repair the harness and re-register

> Repair the B5 harness and re-register, before collecting. Do not collect.
>
> Two defects sit between the DISAGREES reading and any claim about B4. Fix both,
> and pre-register the corrected cell, because the repair changes what the
> collection measures.
>
> First, the seed. RunProvider.start() rewrites ledger_path and nothing else, so
> all 120 runs shared seed 20260908 and the fault stream was identical.
> supervisor.py's render_config already takes a seed, and its docstring exists
> because Session 3's D0(ii) gate caught this. Use it: one freshly seeded provider
> per run, derived from the run's own seed so it is reproducible.
>
> Prove the repair, per rule 13, and prove it on the fault stream rather than on
> the outcome: show that the per-run fault-decision signatures from
> ground_truth.run.jsonl now differ across runs, and show that a run given the same
> seed reproduces its signature exactly. A seed that varies but does not reach the
> provider would look identical to what you just found.
>
> Second, H1's units. analyse_b5_agreement.py:371 compares B5's duplicate
> applications against B4's per-execution indicator. The reconciler already
> computes undetected_duplicate_executions and it is in all 120 summary.json, so
> write it into the session record and compare like with like. State in the report
> that H2 was already units-consistent and needed no change.
>
> This is a change to the verdict script after data exists, which is the one edit
> the ordering exists to prevent -- so do it explicitly and on the record. Record
> what the script said before, what it says after, and that the correction was
> identified from a units mismatch in the code rather than from the result being
> unwelcome. Do not run it against the new data in this pass.
>
> Then re-register. Attempt 2's data stays as a complete honest record of a harness
> that was too deterministic -- do not delete or amend it. The corrected cell is a
> new pre-registration: hypotheses unchanged, run counts, unit of analysis, stopping
> rule, and the statement that per-run fault streams now vary. Commit it before any
> attempt 3 run exists.
>
> Two of three attempts remain. Say in the pre-registration whether the repair
> resets that budget or spends from it, and why. Attempt 2 was not wasted, but it
> also did not measure the cell.
>
> R1, R8, R8a, R8b, R12, R12a, R14 apply. Commit and push.

## Prompt 15 — collect attempt 3 (this one)

> Launch WS-6 attempt 3 against the corrected cell.
>
> Rule 4 first: append the prompts issued since the last prompts commit, verbatim,
> corrections recorded alongside, before any data commit.
>
> Collect exactly what the corrected re-registration specifies: 120 runs, 30 x 10,
> both configurations, 4000 ms Start-To-Close, into a new dated directory. Frozen
> results are immutable. Follow the stopping rule as written; do not adjust it
> mid-collection.
>
> Launch detached with nohup setsid, keepalive held. Record the environment with
> verify_measurement_host.py. Do not run the test suite against anything this
> collection uses.
>
> Do NOT run analyse_b5_agreement.py. Read the run count and the void counts only,
> so any void decision stays outcome-independent.
>
> Two stop conditions beyond the pre-registered one.
>
> If VOID_ATTRIBUTION_UNAVAILABLE appears, stop and report. It appeared in no run
> of attempt 2, so its presence would mean something changed.
>
> And read the provider_seed field across runs as the collection proceeds. It is
> configuration the runner echoes back, not an outcome, so reading it is
> outcome-independent. If the seeds are not distinct across runs, stop immediately
> -- that is the defect this attempt exists to repair, and collecting through it
> would spend an attempt reproducing attempt 2.
>
> Do not read per-run duplicate or lost-effect counts. Those are outcomes, and the
> identical-runs check belongs to the analysis pass, not to you during collection.
>
> The 2 VOID_WORKER_NEVER_READY from attempt 2 are an open question in handoff §7.
> If they recur, record the count and the positions; do not chase them.
>
> R1, R8, R8a, R8b, R12, R12a, R14 apply. Stop when the data is committed and
> pushed. No analysis, no verdict, paper untouched. If the push hangs, retry once
> with a longer window before reporting it as a hang.

---

# Corrections recorded alongside, not applied silently

**Prompt 5's premise, and my own report, were wrong about readiness.** Prompt 5
said *"every open question is now closed, so this is the last thing standing
between here and collection"*, and my report for that prompt closed with
*"WS-6 is ready to collect."* **Both were false, and the error is mine**: the
five pre-registered open questions were closed, but no B5 collection path exists.
There is no `B5` in `experiments/baselines/contract.py`'s `SystemId`, zero
occurrences of `B5` in `run_matrix.py`, and nothing anywhere that writes the
`b5-runs.jsonl` that `analyse_b5_agreement.py` reads. `probe_open_questions.py`
says so in its own first line — *"Not a collection. Nothing here writes a run
directory"* — and I wrote that line. I conflated *the open questions are closed*
with *the instrument exists*.

**Prompt 6's collection therefore did not happen**, and the reason is recorded in
`reports/phase-report-ws6-not-collected-2026-09-08.md` rather than worked around.
The Start-To-Close decision it asked for was still made and committed first, as
instructed, because it is the last free parameter and fixing it before any run is
the point.

---

**Prompt 10 said "through `resolve_for_system()`". It was not done that way, and
the deviation is recorded here rather than applied silently.**

`resolve_for_system` is lossy for B5. It maps **both**
`after_barrier_before_dispatch` and `mid_dispatch` onto the single
`BEFORE_REQUEST_TRANSMISSION`, distinguishing them only by deferred delivery.
Driving the injector from it would have collapsed two of the four secondary
crash points into one — the same defect the prompt was written to remove, one
level further down.

What was built instead: `resolve_for_system` still decides **whether the cell
exists** (it is the cross-system contract, and what `RunConfig` validates
against), and `worker.resolve_b5_point` — B5's own registered mapping, which has
five distinct positions — supplies **the point that is armed**. Both must agree.
A test pins the lossiness, so if the shared resolver ever stops being lossy that
test fails rather than the guard quietly becoming redundant.

**A second defect was found while doing it, and is not in the prompt.** The run
record wrote B5's vocabulary into `crash_point`, but `analyse_b5_agreement.py`
keys the frozen B4 comparison on roadmap names. All 39 runs of the voided
attempt 1 say `"ACTIVITY_ENTERED_BEFORE_CALL"`. The two vocabularies are
disjoint, so **every cell, primary included, would have found no frozen
counterpart** — a failure the prompt's "harmless for the primary stage" did not
anticipate, because it was a second defect in the same family rather than the
one being fixed.

**Prompt 11's premise about the cause was carried from my own earlier report and
was wrong.** I had told the human the distro's idle shutdown killed attempt 1.
Measurement says WSL keeps the VM up while anything is running: the non-detached
driver died with its launching client first, and the distro idled out ~20 s
later. `.wslconfig`'s `vmIdleTimeout=-1` is not honoured by WSL 2.7.3.0 at all.
The prompt asked for exactly this correction to be recorded, which is why it is
here and in `reports/phase-report-ws6-attempt1-voided-2026-09-08.md` §4.

---

**Prompt 12 asked for "two small records" and got three artefacts.** I also
saved the analysis output (`agreement.txt`, `agreement.json`) into the session
directory and re-digested `SHA256SUMS` over it, treating that as evidence of what
was run rather than as a new document, and flagged it in the report as a third
artefact so it could be objected to. Prompt 13 accepted it explicitly — *"The
agreement.txt/json artifacts in the session directory are fine as evidence of
what was run -- keep them."* Recorded because the acceptance is what makes it not
a silent widening of scope.

**Prompt 14's rule-13 proof failed on its first run, for its own reasons.** The
prompt asked for the repair to be proven on the fault stream rather than the
outcome, and warned that *"a seed that varies but does not reach the provider
would look identical to what you just found."* The proof's branch B — the same
seed must reproduce its stream exactly — failed, and the defect was in the proof,
not the repair: its signature digested client-observed HTTP statuses, which
depend on whether the test client's socket timeout fires before the provider's
simulated timeout returns 504. The provider's own decisions were byte-identical
across the two runs. Before rewriting the signature I checked that a
provider-only signature still separated the five seeds, so the rewrite was not
assumed to work. Recorded in `prove_provider_seeding.py`'s docstring and in
`reports/phase-report-ws6-prediction-corrected-2026-09-08.md` §2.1.

**Prompt 10's `resolve_for_system()` deviation, above, is the pattern these
share:** each time the prompt named a mechanism and the mechanism turned out to
be the wrong one for a reason only visible on contact with the code. In all three
cases the deviation is recorded here rather than folded into a diff, because a
prompt whose instruction was not followed is a prompt whose record would
otherwise be false.
