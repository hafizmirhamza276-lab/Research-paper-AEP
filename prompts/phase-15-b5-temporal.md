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
