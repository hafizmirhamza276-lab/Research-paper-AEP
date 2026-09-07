# Phase 14 — WS-4 / backlog B1: run the protocol under block-level write loss

The prompts below are recorded **verbatim**, before this phase's first data
commit, per `docs/26-journal-readiness-direction.md` §3 rule 4.

**WS-4 was issued as a sequence of bounded prompts rather than one**, each
gating the next, so all of them are recorded here in the order they were given.
Rule 12 (*one bounded task per prompt*) is why there are six.

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
