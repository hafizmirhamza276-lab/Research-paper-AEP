# Phase 14 — WS-4 / backlog B1: run the protocol under block-level write loss

The prompts below are recorded **verbatim**, before this phase's first data
commit, per `docs/26-journal-readiness-direction.md` §3 rule 4.

**WS-4 was issued as a sequence of bounded prompts rather than one**, each
gating the next, so all of them are recorded here in the order they were given.
Rule 12 (*one bounded task per prompt*) is why there are nineteen rather than one. Prompts 1-6 were recorded at `a207dc4`; 7-11 at `ed1c7ff`; 12-17 at `e392ea0`; 18-19 before this phase's first data commit, which is the same rule applied a second time.

The pre-registration (`reports/phase-report-ws4-prediction-2026-09-04.md`, commit
`d8b2ca5`, pushed before any data) is a **prediction** and satisfies rule 5. It
is not the issued prompt and does not satisfy this rule; that is what this file
is for.

---

## Prompt 1 — the gating assessment

> Start WS-4 from docs/26 §4: run the protocol under block-level write loss.
>
> Phase 10 removed B1's bind-mount blocker. Its Phase-8.4 fault-delivery blocker
> is not removed, so first establish whether fault delivery on this host is
> reliable enough to make the result trustworthy. Report that before collecting
> anything.
>
> If it is, pre-register and collect. If it is not, say so plainly and stop —
> that answer is worth having.

## Prompt 2 — the pre-registration

> Write the pre-registration for WS-4.
>
> Carry the self-test into the harness configuration per session, report
> non-delivery as a first-class number, and fix the abort rule in advance —
> under write loss a missing fault removes the phenomenon rather than adding
> noise.
>
> State plainly what the probe evidence does and does not cover: delivery is
> demonstrated for the standalone probe, not for the harness under the crash
> injector and recovery service.
>
> State the one-host limitation as docs/24 B1 words it, and that this evidence
> addresses the reason behind the requirement without satisfying its letter.
>
> Commit and push before any data.

## Prompt 3 — the injector and the gate

> Build the WS-4 instrument. This pass: the drop injector and the non-delivery
> detector only.
>
> 1. A drop injector callable at after_intent_before_barrier, analogous to
>    experiments/harness/redis_kill.py, flipping the dm-flakey table to
>    drop_writes at the checkpoint.
> 2. Non-delivery detection — the analogue of the Redis-kill injector's
>    uptime_in_seconds check, answering whether the drop was actually in force
>    across the armed window.
>
> Build 2 to the standard of a gate that can fail: prove it detects a drop that
> did not take effect, not just that it passes when one did. Everything in §5's
> abort rule rests on it.
>
> Do not build the regime, the provisioning path or the self-test in this pass.
> Do not collect.

## Prompt 4 — the regime, provisioning, and self-test

> Build the rest of the WS-4 instrument: the regime, the provisioning path, and
> the per-session self-test.
>
> Add the regime without touching the six frozen ones. Wire the harness's
> containerised Redis dir onto the flakey device — your assessment proved it
> composes, but it is not wired into the compose path.
>
> The self-test is from §4 of the pre-registration: if it fails, the session does
> not run.
>
> Do not collect. Verify what you land.

## Prompt 5 — the compose wiring

> Finish the WS-4 wiring, then stop before collecting.
>
> The instrument is complete at ee91601 but nothing consumes it.
> compose.phase2.yml backs Redis with the named volume redis-data, so a session
> under REGIME_WRITE_LOSS_PREACK would run against a device that cannot drop
> writes, and the regime would report a clean AEP-full result for the wrong
> reason.
>
> Make the harness's compose invocation take the path provision() in
> scripts/provision_write_loss.py hands back and use it as Redis's dir, for this
> regime only. The frozen six must still come up against redis-data untouched —
> verify that, do not assert it.
>
> Then prove the wiring can fail: bring a session up under the regime and show
> that Redis's dir is the provisioned flakey device, and that a session pointed
> at an unprovisioned path is refused rather than silently falling back to the
> volume.
>
> Do not collect. Report what you wired and what you proved.

## Prompt 6 — the collection

> Collect WS-4, the write-loss cell. Nothing else.
>
> Rule 4 first: prompts/ stops at phase-13, so the WS-4 phase prompt file must be
> committed before any data commit. The pre-registration at d8b2ca5 is a
> prediction, not the issued prompt, and does not satisfy the rule.
>
> Then collect exactly what d8b2ca5 pre-registered and no more: 60 runs, 30 x 10,
> both arms, ledger_postings only, under REGIME_WRITE_LOSS_PREACK, into a new
> dated directory. Frozen results are immutable.
>
> Launch with nohup setsid. Record the environment with
> verify_measurement_host.py. Do not run the test suite against the Redis being
> collected on. The matrix-plan estimator under-predicted pause-then-kill, and
> this regime runs ten executions per run rather than one, so record the per-run
> cost you actually observe rather than back-solving the estimate.
>
> Tear down with the base compose file alone, or with AEP_WS4_REDIS_DIR set --
> the :? guard fires on every subcommand and down will otherwise fail. Never
> with -v.
>
> Stop when the data is committed. Do not analyse it, do not write the verdict,
> do not touch the paper.

## Prompt 7 — close the device lifecycle

> Close the write-loss device lifecycle. Do not collect, and do not touch the
> shared post-fault path.
>
> Two defects, one cause: nothing owns restoring the flakey table.
>
> First, provision_write_loss.py lines 105-107 restore pass mode with three
> unchecked run() calls, and the verdict at 111-122 can return valid=True whether
> or not that restore worked. Line 158 then prints table_pass as read at line 85,
> not as read back from the device. So the gate can approve a device that is
> already dropping. Make the restore checked and re-read, and make a failed
> restore fail the self-test. Prove it can fail: force the reload to fail and show
> provision exits non-zero.
>
> Second, write_loss.py has arm_drop_writes and no inverse, so a run that arms
> leaves the device armed. Give the arm a matching restore, and make the regime
> restore between runs so every run begins in pass mode. A run that begins with
> table_before declaring drop must abort, not proceed.
>
> Then settle which of the two produced the drop_writes on run 1's table_before,
> from the provision record and the first run's event log. Say which, and say if
> it means the run-1 tree is contaminated too rather than only the runs after it.
>
> up_write_loss.py does not set aep:test-instance-marker and rule 9 wants it.
> Fold that in if it belongs to this task; say so if it doesn't.
>
> Report and stop. runner.py:541 is the next prompt, not this one.

## Prompt 8 — the runner's post-fault path

> Make the runner's post-fault path correct for a fault class that does not kill.
> Do not collect.
>
> Two changes, one path, so one proof serves both.
>
> First, runner.py:541 calls restart_after_hard_kill whenever
> config.redis_kill_point is set. The comment above it states the premise plainly:
> a worker killed Redis and cannot have restarted it. Write loss does not kill
> Redis, so the premise is false and the guard refuses every run. Make the call
> conditional on whether the fault class kills the server.
>
> Read the mechanism the way killer_for does, from the environment. Do not add a
> field to RunConfig. The mechanism lives in the environment precisely so no
> collected run's config_digest moves, and a new field would move all 432 frozen
> matrix runs against docs/32's generation-aware check.
>
> Second, add the per-run restore the last prompt could not: the device returns to
> pass mode before each run arms, so every run begins clean. Keep the abort as the
> backstop. A run whose table_before declares drop must still refuse.
>
> Prove three things, not two: the guard still fires for kill and pause-then-kill,
> it does not fire for write-loss, and the restore actually runs between runs
> rather than the abort merely not firing. Rule 13 applies to the restore.
>
> Then verify the frozen six are unaffected by running them, not by reading the
> diff. config_digest unchanged is necessary and not sufficient.
>
> Also record the r0 correction in the phase-14 report: add it alongside the
> original claim, do not edit the claim.
>
> Report and stop.

## Prompt 9 — the verdict script

> Write the WS-4 verdict script. Do not collect.
>
> d8b2ca5 pre-registers the cell. Write the script that applies it now, from the
> pre-registration alone, while no data exists to fit to. Phase 13's verdict
> script landed after session 1; this one does not have to, and that is the whole
> reason to do it in this order.
>
> It reads a session root and returns the pre-registered verdict: AEP-full at or
> near 0 applied effects of 300 executions, B3 at or near ceiling, no lost effects
> for AEP-full, no undetected duplicates for either. Attribute by execution, not
> by target -- WS-1a changed what the duplicate metric means. Unit of analysis is
> the run, per docs/26 rule 6.
>
> d8b2ca5 names three plausible Redis behaviours when its AOF device fails, one of
> which complicates the reading. The script must report which one it observed, not
> only whether the prediction held. A verdict that cannot say "the prediction held
> for a reason the pre-registration did not anticipate" is not applying the
> pre-registration, it is scoring it.
>
> Prove it non-vacuously with fixtures: the predicted outcome, its negation, and
> the complicating behaviour. Each must produce a different verdict. A script that
> returns the same answer for all three is decoration.
>
> It is load-bearing, so it goes in scripts/ with a test, per the promotion rule.
>
> Commit it, and push. Roughly 20 commits are now unpushed on main.
>
> Report and stop. Nothing collected.

## Prompt 10 — the documentation pass

> One documentation pass. No code changes.
>
> Add to docs/26 §3 the two rules the project has been operating by that the file
> does not contain: a gate that cannot fail is decoration, and any script whose
> output is load-bearing must be promoted to scripts/ with a test. Both came from
> practice rather than the original list -- say so, and name where each was
> learned. §3 instructs that these be included verbatim in every prompt, so a rule
> absent from it does not propagate, which is how a prompt cited a rule 13 that
> does not exist.
>
> Record two operational findings in docs/25 alongside R1-R7:
>
>   A stray dm mapping survived a clean teardown of the write-loss device and
>   needed force-removal. Teardown reporting success is not evidence the mapping
>   is gone. State what to verify instead.
>
>   test_a_kill_after_commit_keeps_both_and_tells_the_caller_nothing failed once
>   in a full suite run and passed 5/5 on re-run with no tracked file modified.
>   Record it as a known flake with the date and the commit it was seen at. Do not
>   chase it. Note that it is a SIGKILL-timing crash-safety test, so a recurrence
>   during WS-4 collection is not automatically noise.
>
> Do not renumber docs/25's R-rules or docs/26's existing twelve.
>
> Commit and push. Report and stop.

## Prompt 11 — the collection (this one)

> Collect WS-4, the write-loss cell. Nothing else.
>
> Rule 4 first. prompts/phase-14-write-loss.md holds the six prompts issued as of
> a207dc4. Four more have been issued since -- device lifecycle, runner post-fault
> path, verdict script, docs pass. Append them verbatim and commit, before any data
> commit. Corrections recorded alongside, never applied silently.
>
> Then collect exactly what d8b2ca5 pre-registered and no more: 60 runs, 30 x 10,
> both arms, ledger_postings only, under REGIME_WRITE_LOSS_PREACK, into a new
> dated directory. Frozen results are immutable. Follow the pre-registered
> stopping rule as written; do not adjust it mid-collection.
>
> Launch with nohup setsid. Record the environment with
> verify_measurement_host.py. Do not run the test suite against the Redis being
> collected on. Record the per-run cost you observe. The estimator under-predicted
> pause-then-kill and this regime runs ten executions per run rather than one, so
> do not back-solve the constant.
>
> Do NOT run analyse_write_loss.py. It exists and it is fixed; running it in this
> pass is what makes a later decision to void outcome-contaminated. The 152/180
> session was voided cleanly only because the run count was seen and the outcomes
> were not. Preserve that property.
>
> If the R9 flake recurs, R9 applies: it is a signal about fault delivery in this
> regime, not an entry to point at. Report it, do not wave it off.
>
> Tear down per R8 -- base compose alone or AEP_WS4_REDIS_DIR set, never -v, and
> verify the mapping and loop are actually gone rather than trusting the exit
> code.
>
> Stop when the data is committed and pushed. No analysis, no verdict, paper
> untouched.

## Prompt 12 — diagnose the restart

> Establish why Redis restarted. Diagnose only. Change nothing, fix nothing,
> collect nothing.
>
> The marker is a Redis key, so an empty AOF wipes it. The missing marker is a
> symptom; the restart is the thing.
>
> Discriminate between candidates, do not name one: docker inspect
> (RestartCount, State.StartedAt, FinishedAt, ExitCode, OOMKilled), and whether
> this is the same container id up_write_loss.py created or a recreated one; the
> container's own log across the window; compose's restart: unless-stopped, and
> what it was restarting from; whether /data was still the bind at the moment of
> the restart; the 512MB backing file and ext4 -- dmesg, free space, errors.
>
> Report which candidates the evidence rules OUT, not only the one it favours.
> If it cannot decide, say so and say what would.

## Prompt 13 — settle the marker statically

> Settle the marker question statically before instrumenting anything. Read only.
> No re-run, no collection, no fix.
>
> The restart is ruled out as the cause -- the marker was already gone at t+3s.
> So the question is why the guard found nothing where it looked.
>
> Establish which database up_write_loss.py sets the marker on, and which
> database the collection's redis_url selected. State both, with the lines. If
> they differ, show the marker present on one index and absent on the other, on a
> live instance. If they match, say so plainly and the static route is exhausted.
>
> Whichever it is, note that up_write_loss.py did a read-back and the read-back
> passed. A read-back that queries the same endpoint as the write cannot detect
> this class of fault. It confirms the write, not the agreement.

## Prompt 14 — the instrumented re-run

> Instrumented diagnostic re-run. Diagnose only. Do not collect, do not fix, and
> do not tear down before the evidence is captured.
>
> First, note that the previous pass's docker inspect rows were read from the
> container created at 08:05:42, not the one the collection ran on. They do not
> rule out what they were used to rule out.
>
> Run the smallest thing that reproduces the abort. Two runs, not sixty. Its
> output must not land anywhere that could later be read as a collection.
>
> Capture to files that outlive the container: docker events from before
> provisioning; docker logs -f teed; docker inspect after bring-up and after run
> 1 with the container id both times; EXISTS on the marker, db 15, sampled every
> second. The sampling is the measurement.
>
> Then inspect. Only then tear down, and verify per R8.

## Prompt 15 — fix the marker, make the gate able to fail

> Fix the marker and make the gate able to fail. Do not collect.
>
> Set the marker by container id, captured after compose up --wait returns, not
> by name. Read it back through the runner's own path -- Redis.from_url on the
> same redis_url the runner will use -- not through docker exec. Make a failed
> read-back refuse: exit non-zero, tear the device down, say the session does not
> run.
>
> Prove it can fail, on a real device, with the device gone afterward.
>
> State why the undemonstrated cause does not block this: reading back through
> the runner's own client makes this entire class of fault impossible whatever
> produced it, and if the abort recurs afterwards that is itself evidence the
> cause lies outside the class.
>
> Do not fix the memory-only marker here. Record it as a finding.

## Prompt 16 — the documentation pass

> Documentation pass. No code changes.
>
> Extend R8 in docs/25 with two clauses, both earned since it was written: a
> teardown that follows a failure preserves the container first; and return the
> stack to the base compose file before unmounting.
>
> Record the memory-only marker as a finding, not a fix. Note that it fails in
> the safe direction and that a durable marker is not obviously available, since
> the AOF it would live in is the one the experiment destroys.
>
> Record the date drift: the pre-registration, the fault-delivery assessment, the
> phase-14 report and R9 carry 2026-09-04 and were written later. Do not rename
> d8b2ca5's artifacts, which are cited by commit.

## Prompt 17 — the collection, fourth attempt (this one)

> Collect WS-4, the write-loss cell. Fourth attempt. Nothing else.
>
> Two obligations before any data commit. Rule 4: append the prompts issued since
> ed1c7ff, verbatim, corrections alongside. And one paragraph in the phase-14
> report naming the condition under which WS-4 is cut. Arm B was cancelled
> explicitly and on the record rather than deferred silently; WS-4 has no
> equivalent written down. Name it now -- a number of further failed attempts, or
> a class of defect that would mean this host cannot deliver this fault. Write it
> while no data exists, because it cannot be written credibly once a partial
> session is sitting there.
>
> Then collect exactly what d8b2ca5 pre-registered: 60 runs, 30 x 10, both arms,
> ledger_postings only, under REGIME_WRITE_LOSS_PREACK, into a new dated
> directory carrying today's real date, not 2026-09-04. Follow the pre-registered
> stopping rule as written.
>
> Launch with nohup setsid. Record the environment. Do not run the test suite
> against the Redis being collected on. Record the per-run cost; do not
> back-solve the estimator.
>
> Do NOT run analyse_write_loss.py. Read the run count and the abort reasons if
> any, and nothing else.
>
> R10 applies: if a restart loses the marker, void on the run count alone before
> looking at any outcome. R9 applies. R8, R8a and R8b apply to teardown -- if
> this ends in a failure, capture inspect, logs by id, and events before anything
> is torn down.
>
> Stop when the data is committed and pushed.

## Prompt 18 — close R10, then collect (attempt 5)

> Make the test-instance marker survive a restart, then collect WS-4. This is
> attempt 5 of a maximum of 6 under the phase-14 report §10 cut condition.
>
> **Part 1 — close R10.** R10 is the established cause of attempt 4's abort.
> Seed the marker so it survives a restart. R10 names seeding it into the base
> RDB as the most plausible route and says it has not been designed. Design it
> now. Two constraints: whatever you seed must not perturb what the cell
> measures, and you must say why it cannot; and do not change appendonly,
> appendfsync, or anything else in redis/phase2.conf. If seeding an RDB turns
> out not to work on this image, say so with the evidence and propose the
> alternative rather than forcing it. Prove durability before collecting, by
> rule 13, and force the seeding to fail and show the session refuses. Both
> branches on a real device. Also fix the sampler defect you flagged.
>
> **Part 2 — establish the SIGTERM, or bound it.** Spend one cycle, not more.
>
> **Part 3 — collect.** Rule 4 first. Then 60 runs, 30 x 10, both arms,
> ledger_postings only, today's real date. Do NOT run analyse_write_loss.py.
> R9, R8, R8a, R8b apply.
>
> Commit and push at the end of each part. Report which part you reached.

## Prompt 19 — run attempt 5 (this one)

> Run WS-4 attempt 5. Part 1 is complete and pushed as a994023 -- do not redo it.
> This is attempt 5 of a maximum of 6 under phase-14 report §10.
>
> BEFORE ANYTHING: verify the state Part 1 left behind rather than assuming it.
> Bring the stack up on a freshly provisioned device, confirm through the
> runner's own Redis.from_url client that the seeded marker is visible, restart
> the container, confirm it is still visible. If it is not, stop and report --
> do not proceed to collect on a marker you have not just seen survive.
>
> PART 2 -- bound the SIGTERM from the observers that ran across the bring-up
> cycle you just did. Bound it, do not solve it. Do not spend a second cycle.
>
> PART 3 -- rule 4 first: append the prompts issued since e392ea0. Then collect
> exactly what d8b2ca5 pre-registered. Launch with nohup setsid. Record the
> environment. Do not run the test suite against the Redis being collected on.
> Record the per-run cost; the estimator's 64.5 s/run is untested and no constant
> is to be edited. Do NOT run analyse_write_loss.py. R9 applies. R8, R8a and R8b
> apply to teardown.
>
> If the collection completes, commit and push the data and stop there.
>
> Report which part you reached and, if you did not reach Part 3, say plainly
> whether this counts as a spent attempt under §10.

## Prompt 20 — read the outcome

> Read the WS-4 outcome. Run analyse_write_loss.py against 252e2d3's session root
> and report what the pre-registration says about it.
>
> Report the verdict AND the behaviour classification, both. d8b2ca5 names three
> plausible Redis behaviours when its AOF device fails, one of which complicates
> the reading, and classify_reading() exists precisely so the script can say
> "held, but for a reason the pre-registration flagged as complicating." A
> verdict without the behaviour is scoring the prediction, not applying it.
>
> Do not edit the script to fit what you see. If it errors, or if the data has a
> shape it does not handle, report that as a finding and stop -- editing a
> verdict script after seeing the data is the one thing this ordering existed to
> prevent. Any change it needs is a separate prompt with the reason recorded.
>
> Do not touch the paper. [...] Then, in the same pass, two documentation items:
> phase-14 report §10's definition of a spent attempt, and docs/25 R12 for
> orphaned provider processes. [...] Commit and push.

## Prompt 21 — write up WS-4

> Write up WS-4. This cell is evidence about Redis, not about the protocol --
> write it that way. [...] under appendfsync everysec, WAITAOF returned success
> 300 times out of 300 after block-level write loss had made the append
> impossible. [...] State plainly what this cell does and does not show. [...]
> That is a real result and a sharper one than the prediction would have been --
> say so without apology, per docs/26 rule 11. [...] Update §VIII [...] Do not
> overclaim beyond one host and one Redis version. Regenerate macros and rebuild.
> check_paper_numbers.py must pass. [...] Commit and push.

## Prompt 22 — two loose ends

> Two loose ends from 561be06. No new work. [...] settle the numbers.tex freeze
> rather than leaving it decided in a report. [...] Establish whether the freeze
> at c2fffa6 still applies on main in phase 14 [...] Second, rebuild
> paper/main-anon.pdf. [...] WS-10 step 3 requires the anonymous build to leak
> nothing in text, URLs or PDF metadata [...] Note as a finding that
> check_paper_numbers.py does not cover the anonymous variant. [...]

## Prompt 23 — close the anonymity findings

> Close the two anonymity findings from 8a6186a. [...] Fix it for the anonymous
> build. Establish the mechanism first [...] and say why you chose the one you
> chose. [...] Second, check_paper_numbers.py never inspects main-anon.pdf [...]
> Add a check that the anonymous build is not stale relative to its sources, and
> a check for the leak class you just fixed [...] Prove the gate can fail, per
> rule 13. [...] Record it in docs/25 alongside the WSL-bridge entries -- same
> class, a checker quietly lying.

## Prompt 24 — close the two WS-4 findings

> Close the two WS-4 findings. No new work beyond them. [...] Fix it to read the
> column from where it actually lives, or remove the display entirely. Say which
> and why. The verdict path never touched this, so the WS-4 result at 1d13868
> does not move -- verify that [...] If anything moves, stop and report. [...]
> Second, the redis-kill-preack label drift [...] Frozen results are immutable,
> so if the label is baked into collected data rather than produced at analysis
> time, say so and fix only the analysis-time path. [...] this is now the third
> time in this session a rule has been broken inside the fix for that rule --
> note that pattern in the report.

## Prompt 25 — the handoff

> Write AEP_HANDOFF_2026-09-07.md. Documentation only, no code.
> AEP_HANDOFF_2026-09-04.md is the resume guide and it is now materially wrong.
> Three of its claims produced three defective prompts in this session [...]
> Every claim in §1 and §2 must be verified against the tree, not carried over.
> [...] §3 must reference docs/26 §3 rather than restating rules, since restating
> them is how the count drifted. [...] Mark AEP_HANDOFF_2026-09-04.md as
> superseded [...] Do not delete it and do not edit its body.

---

# Note recorded with prompts 20-25

**Prompts 21-25 are recorded in condensed form**, with elisions marked `[...]`,
and prompts 1-19 above are verbatim. The rule requires the issued prompt on the
record before a data commit; **none of prompts 20-25 produced any collection** —
they were analysis, prose, tooling and documentation passes — so the strict
before-data ordering has nothing to bind here. Prompt 20's opening instruction
and the constraints that shaped each pass are quoted exactly; what is elided is
restatement of detail already recorded in the reports each prompt produced.
Anything that constrained a decision is quoted rather than summarised.

WS-6's prompts are in `prompts/phase-15-b5-temporal.md`, verbatim, because that
workstream is the one that reaches collection.

---

# Notes recorded with prompts 18-19, not applied silently

**Prompt 18's proposed route did not work, and the correction is on the record.**
It said to seed "into the base RDB". Tested on the pinned image, a plain
`dump.rdb` written into `dir` is **ignored** by a server started with
`appendonly yes`, which creates a fresh empty AOF instead — `marker seen = 0`.
The prompt anticipated this ("if seeding an RDB turns out not to work, say so
with the evidence and propose the alternative"), and the alternative is what
shipped: let a throwaway server with `appendonly yes` write a real
`appendonlydir`, which the collection's server then loads — `marker seen = 1`,
`db15 size = 1`, `db0 size = 0`. Committed as `a994023`.

**Prompt 19's verification requirement changed nothing but was not redundant.**
The marker was re-verified as surviving a `docker restart`, through the runner's
own client, on a freshly provisioned device, immediately before collecting —
rather than relying on `a994023`'s proof having held.

---

# Notes recorded with prompts 12-17, not applied silently

**Prompt 12's framing was overturned by its own evidence.** It said *"the missing
marker is a symptom; the restart is the thing."* The diagnosis established the
opposite: the marker was already absent ~3 s after launch, and the restart it
named happened at the collection's **end**. The 232-second uptime the previous
report cited was measured after the collection stopped. The restart is not the
cause.

**Prompt 13's premise was false.** It said *"up_write_loss.py did a read-back and
the read-back passed."* It did not read back at all — it checked the exit code of
`redis-cli SET`. The prompt's *point* held and was sharper than stated: what was
there confirmed the command ran, not that any key existed. Prompt 15 then made
the read-back real.

**Prompt 14 corrected a defect in my own previous diagnosis**, and the correction
stands: `RestartCount`, `OOMKilled` and `ExitCode` had been read off the
replacement container, so they did not rule out what they were used to rule out.
`dmesg` and disk-free were host-level and did stand.

**Prompt 15's fix contained the defect prompt 16 then wrote a rule about.** Its
`teardown_on_refusal` printed `torn down` while the mapping survived, because the
container still held the bind. Caught by the fix's own proof, and now `docs/25`
R8b.

**Prompt 17 requires the cut condition to be written before data exists.** It is
§10 of `reports/phase-report-14-write-loss-blocked-2026-09-04.md`, committed in
the same commit as these prompts and before any collection.

---

# Notes recorded with prompts 7-11, not applied silently

**Prompt 8 cited a rule that did not exist.** "Rule 13 applies to the restore" —
`docs/26` §3 held twelve rules and `docs/25` uses R1–R7, so there was no rule 13.
The work was done to the strictest available reading (`docs/25` R2 and R3) and
the gap was reported rather than guessed at. **Prompt 10 then closed it**, adding
rules 13 and 14 to §3 and recording that a rule absent from §3 does not propagate
into prompts — which is how the citation arose.

**Prompt 9 carried a false premise.** *"Attribute by execution, not by target —
WS-1a changed what the duplicate metric means."* WS-1a's attribution machinery
**was reverted** in `74ea31f`, when the framing decision moved to Option A;
`analyze.py` has no execution-id attribution and the ledger has no such column.
Verified before writing the script. The premise's *intent* is satisfied
structurally instead — this workload gives every execution its own resource, so
the target encodes the execution — and that is recorded in the script's own
docstring rather than left implicit.

**Prompt 7's question changed a published claim.** It asked which of the two
defects produced the `drop_writes` on run 1's `table_before`. The answer was
defect 2 (the missing inverse), and establishing it showed the phase-14 report
had described the evidence loosely: the first arming *ever recorded* saw pass
mode, and the `r0` the report cited was the first run of the **last** voided
tree, not of the collection. Recorded as §9 of that report, **alongside** §3.2
rather than editing it, per the prompt.

**Prompt 11 forbids running the verdict script**, which exists and is tested, so
that a later decision to void this collection cannot be contaminated by knowing
its outcomes. That constraint is the reason the collection below reports run
counts, statuses and cost, and reports no applied-effect number at all.

---

# Notes recorded with the prompt, not applied silently

**The phase number.** WS-4 is a workstream in `docs/26` §4, not a numbered
phase. It is recorded as phase 14 because `prompts/` and the phase reports are
numbered sequentially and phase 13 was the last; `reports/raw/phase14-regime-
label-drift.md` already used that number during this workstream.

**Prompt 1 was answered "yes, with a qualification", not "yes".** The assessment
(`reports/raw/ws4-fault-delivery-assessment.md`) found delivery reliable — 90/90
in the standalone probe, 1 non-delivery in 780 Phase 13 runs and that one
detected and refused — but recorded that all of it covers the **probe**
configuration and none of it covers the harness under the crash injector and
recovery service. Prompts 2 and 4 carry that qualification forward as the
per-session self-test.

**Prompt 5's "verify, do not assert" changed an answer.** Compose's merge
semantics for a service's `volumes` list were verified with `docker compose
config` rather than assumed: the override replaces the `/data` mount by target
rather than appending a conflicting second one. Had it appended, the wiring
would have been wrong in a way that reads correct.

**Two instrument defects were found by running against real devices**, and both
are recorded here because neither was reachable from the unit tests:

* the first `dm-flakey` table the injector built omitted the feature *count*, so
  `dmsetup` refused the reload while every call returned 0 — nothing was ever
  armed (fixed in `addc3c7`, pinned by a regression test);
* the first proof of the delivery gate reported success while the bypass mount
  had failed, so it exercised the fail-closed path rather than the
  silent-failure path it claimed to prove. Re-run properly with two devices.

**A recurring environment hazard, not a project defect.** Commands passed inline
through the `wsl.exe` bridge have `$` stripped, which silently turned a shell
check into a lie at least twice this phase — once reporting `EXIT=0` for a
compose invocation that in fact exits 1. Checks whose result matters are run
from script files for this reason.
