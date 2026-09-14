# 25. Rules for collection tooling

Rules, not suggestions. Each exists because it was violated and the violation
cost something measurable. Scope: `experiments/harness/*.sh`, `scripts/*.sh`, and
any collection driver.

---

## R1. Never control processes by pattern. Use PIDs.

**Do not** use `pgrep -f`, `pkill -f`, or `ps | grep` on a pattern that could
appear in the command line of the process doing the matching.

**Do** capture `$!` at launch, write it to a PID file, and act on that. Where a
process must be waited on, wait on a **sentinel file written only on success**,
or on the target process itself (the Python process) rather than its wrapper.

**Why, from one day of Phase 8.4 — four instances, three distinct victims:**

| # | construct | what it did |
|---|---|---|
| 1 | `while pgrep -f "run_session.sh <slug>"` | matched its own command line; loop could never exit; the session chain stalled after a session that had already finished |
| 2 | two such watchers running together | each also matched the other, so neither could terminate even if (1) were fixed |
| 3 | `pkill -f "experiments.run_matrix"` for a status check | matched the checking shell; reported processes that were not running |
| 4 | `pkill -f "load_sampler.sh /tmp/ls2"` | killed the operator's own shell mid-command |

**Two of the four were the safety tooling itself** — the watcher that was meant
to detect a stalled session, and the cleanup for a test of the load sampler. A
pattern that is a substring of the matching command is not an edge case here; it
is the normal case, because these scripts name the things they operate on.

The failure is always silent and always in the unsafe direction: `pgrep` returns
a match, so "is it still running?" answers *yes* forever, and `pkill` finds a
target, so "stop that thing" stops the wrong thing.

### R1a. Second occurrence, 10 September, in the WS-7 model-checking sweep.

**R1 predates this by a month and was broken anyway, by the agent that had read
it.** Recording it because R12a's convention applies -- a second occurrence is
logged so a third is met as a pattern, not as a surprise -- and because the
first four instances were all in collection tooling, which made R1 easy to file
mentally as a collection rule. It is not. It is a rule about process control.

**What happened.** A TLC sweep was running in the background. To start a
corrected one, the old sweep was stopped with:

```sh
pkill -f tlc2.TLC; pkill -f run_tlc.sh
```

Both matched. Every `java ... tlc2.TLC` process died, and the report said so.
But `run_tlc.sh` is a **loop**: killing the `java` child it was waiting on did
not kill the loop, and `pkill -f run_tlc.sh` raced it. The wrapper survived and
walked on to the next configuration. Two sweeps then ran concurrently for about
twenty minutes.

**Both failure modes were silent, and both were in the unsafe direction.**

1. The two sweeps shared one log directory, and the second had begun with
   `rm -rf`. Logs from configurations the first sweep was still writing
   disappeared; one configuration reported `ERROR (see log)` for a log that no
   longer existed.
2. Worse, TLC writes its fingerprint and state files relative to the module
   directory unless told otherwise, so the two runs shared `formal/states/`.
   One deleted the other's files mid-run and it died with
   `java.io.IOException: ... AEP_0.tmp (No such file or directory)` --- an
   exception that looks nothing like a model-checking result and was, for a
   few minutes, mistaken for one.

**Neither was caught by noticing the kill had failed.** They were caught by the
*results* being wrong, which is the expensive way round and is exactly what R1
exists to prevent.

**Fixes applied.**

* Process control now collects PIDs first, prints them, then acts on each by
  PID --- so the count is visible before anything is signalled, and afterwards
  the process table is re-read and shown to be clear rather than assumed to be.
* `scripts/run_tlc.sh` passes `-metadir` per configuration, so two runs cannot
  share a state directory even when both are started deliberately. That is the
  robustness fix R1 could not have given: not controlling the processes better,
  but removing the shared resource they were fighting over.

**The general lesson, which R1 as written does not quite say.** `pkill -f` on a
*wrapper* is worse than on a leaf process, because killing the child a loop is
waiting on looks exactly like success while leaving the loop alive. If a script
iterates, the thing to kill is the script, by PID, captured at launch --- and
then to verify the iteration stopped, not that a signal was sent.

## R2. Validate every gate and every derived count against a known answer first.

Before a gate or a census is trusted on a case whose answer is unknown, run it on
one whose answer is already known and assert the result.

Known answers available in this repository:

- session 1 (`b2-paired-v2-s1-2026-08-28`): **0** non-landing kills, **30/30**
  runs and executions in each of four cells
- session 2 (`b2-paired-v2-s2-2026-08-28`): exactly **2** non-landing kills, at
  **rep0 and rep6**
- the frozen `analysis/redis-kill-ablation.csv` of any frozen root

This is the general remedy behind **B11**, and it is what actually caught every
instance of that finding. Failing-branch testing (R3) is necessary but does not
cover derived counts, which have no failing branch.

**It caught, in Phase 8.4:** a cell census that read `oracle_effect_executions`
(a count of executions that *applied an effect*) where `executions_planned` was
meant, which would have compared the applied column against runs; and a fault
census that reported **4** failures where there were **2**, at positions
`[3, 120, 26, 120]`, because it counted its own echoed output and parsed both
numbers out of `[3/120]`.

## R3. Test every gate on its failing branch, asserting the exit code.

A gate that has never once fired has not been shown to work; it has been shown to
be quiet. See **B11**: `${#ARRAY[@]:-0}` is invalid bash, raises
`bad substitution`, and under `if` reads as *false* rather than as an error — so
a fixtures-missing check ran through a real collection unable to halt anything,
while its passing path printed a reassuring `fixtures missing : none`.

## R4. A destructive gate needs a dry-run seam before R3 can be applied to it.

R3 is not dischargeable by pointing a destructive script at live state. Testing
`precondition.sh`'s failing branch — by renaming a fixture so it would be
classified as foreign — stopped the running session's Redis and destroyed a
collection at 8 runs (`reports/phase-report-8-4-session-2-aborted-2026-08-28.md`
§3a). Add the seam first, then test the branch.

## R5. Observation added mid-collection is disclosed in the artefact, not only in prose.

Additive observation may be added during a phase — it touches no registered gate
and changes no collection condition. But the resulting artefact must record its
own coverage limits, because prose gets summarised and artefacts get read
directly.

Phase 8.4's `foreign-load-sample.json` records, in the file itself: that sampling
began 399 s after session 3's collection started; that **session 2 has no series
at all**, so the sessions are not uniformly instrumented; and that at 60 s
resolution a container living less than one interval is missed entirely, so an
empty foreign list is **weak evidence of quiet, not proof of it** — which matters
because both foreign containers this phase observed were removed within four
minutes.

## R6. The four 21 August roots carry a deny-DELETE guard. If a delete fails there, this is why.

**Applied 2026-09-01.** `experiments/results/b2-{,s1-,s2-,s3-}2026-08-21` each
carry an inheritable deny of `DELETE` for the current user:

```
AzureAD\HamzaKhan:(OI)(CI)(DENY)(DE)
```

**Why.** Those four roots hold 240 run directories that exist **nowhere else** —
the privileged custody survey of 1 September shows `/root/aep-phase8` holds
**zero** of them. They are gitignored, so `git status` prints nothing for them,
and `git clean -xdf` deletes them silently. They carry `\ReplicationPrevented*`,
the only session-clustered interval in the paper that excludes zero. See B31.

**`.gitignore` is deliberately NOT the remedy.** Tracking raw runs would put
uncheckpointed WALs under version control and break the archive discipline —
worse than the risk removed. **Do not "fix" a blocked delete by editing
`.gitignore`.**

**Removing and restoring it:**

```
powershell -ExecutionPolicy Bypass -File phase8-driver/apply_clean_guard.ps1 -Remove   # lift
powershell -ExecutionPolicy Bypass -File phase8-driver/apply_clean_guard.ps1           # re-apply
powershell -ExecutionPolicy Bypass -File phase8-driver/apply_clean_guard.ps1 -Show     # inspect
```

By hand, per root: `icacls "<root>" /remove:d "*<SID>" /T`.

**Symptom to recognise:** a delete inside those roots failing with `Invalid
argument` (git) or `Access is denied` (Explorer, `rm`). Reads, `tar`, and file
creation are unaffected and were verified so — the guard must not obstruct the
off-host copy it exists to bridge to.

**Verified on this tree, not only in test repositories.** `git clean -nxd` still
lists all 402 entries after the guard is applied, because an ACL changes git's
*ability* and not its *intent* — **so a dry run cannot verify this guard and must
not be used to.** Verification is `phase8-driver/probe_clean_guard.ps1`, which
creates its own throwaway directory inside a guarded root, confirms deletion is
refused, and removes it. The probe exists because the direct test — deleting a
run directory to see whether it is protected — destroys 60 irreplaceable runs if
the answer is no.

**It stops accident, not intent.** Anyone can drop the ACE. That is the intended
threat model: B31 is about a routine command run for an unrelated reason.

## R7. When you change what a claim asserts, find its restatements before you commit.

**Scope note.** This file is about collection tooling. R7 is about editing the
manuscript, which stretches that scope — recorded rather than glossed. It lives
here because it is a procedure that must be followed under pressure, which is
what this file is for.

**The rule.** An edit that changes what a claim *asserts* is not finished when
the sentence reads correctly. It is finished when **every other sentence stating
the same claim has been found and judged.**

### When it applies

**Applies** when an edit changes a claim's **strength** (*is* → *may be*),
**scope** (*weakest* → *narrowest*), **direction**, or **evidential basis**
(a withdrawn number, a control that was not one).

**Does not apply** to typography, citation fixes, a number changing under an
unchanged claim, or a genuinely new claim with no prior statement. **Not every
edit — only edits to what is asserted.**

### What is searched, and with what

**Do not use `phase8-driver/claim_sweep.py`.** It is the wrong instrument and
gives a plausible-looking wrong answer; see the decision recorded in B26.

```sh
grep -rn --include='*.tex' -iE "<TERM1>|<TERM2>" \
    paper/sections/ paper/main.tex paper/generated/
```

**Choose `<TERM>`s from the claim's CONTENT NOUNS** — the things the claim is
about (`host`, `docker`, `barrier`, `readback`) — **never from its strength
words** (*shows*, *establishes*, *may be*). A restatement is a restatement
because it is about the same thing; it will have been reworded, so the wording
is exactly what does not survive. Use `\b...\b` and allow the possessive:
`\bhost'?s?\b`.

**`paper/generated/` is in scope and is not optional.** B20 found **two of its
four** defects inside generated captions, and no grep over `sections/*.tex`
reaches them. `numbers.tex` will return `%` provenance comments — dismiss them
by reading, not by filtering. **Do not add `grep -v` to tidy the output:** an
unreported exclusion is precisely the defect that makes `claim_sweep.py`
unusable here.

**Expect tens of lines and read all of them.** For the host-dependence claim the
invocation returns **37**. That is the correct order of magnitude; a search
returning three has been over-narrowed.

### Search TWICE. The noun search alone is not sufficient, and this was measured

**A restatement that shares no content noun with the claim escapes the search
above.** This is not hypothetical. `06-evaluation.tex:462` states the same
proposition as `:393` and shares **not one noun** with it:

> `:393` — *"the effect size may be a property of this host's `docker` latency"*
> `:462` — *"`\UnwantedPrevented{}` … is one draw from a distribution"*

The first search returns `:393` and **not** `:462`.

**So run a second search over the macros that carry the claim's evidence:**

```sh
grep -rn --include='*.tex' "UnwantedPrevented\|KillLatency" \
    paper/sections/ paper/main.tex paper/generated/
```

**Take the union of both searches.** The macro search reaches what the noun
search cannot, because a restatement is *about the same quantity* even when it
reuses none of the same words — and the macro name is the one token a
quantitative restatement cannot paraphrase away.

**It also reaches the abstract.** `main.tex:172` carries `\UnwantedPrevented{}`
and contains the word *host* nowhere. **A noun-only search never looks at the
abstract**, which is where the paper's claims are stated most strongly and
where they were written when the evidence was strongest.

### Restatement versus a legitimate different claim

**A restatement** states the same proposition about the same subject, anywhere in
the document. Judge by proposition, not by wording or by section.

**Not a restatement**, and must not be "fixed" into agreement:

- **A prediction from design, marked as such.** `08-threats.tex:103` — *"the
  effect size should be a function of the host's kill-latency distribution ---
  but our measurement of that reason does not establish it."* That is the
  protocol's logic offered as a reason and explicitly withheld as evidence.
- **A design claim** rather than a measured one. `06-evaluation.tex:466` —
  *"what is structural is that the race exists for AEP-full at all and cannot
  exist for B3."*
- **A claim about a different quantity** that happens to share vocabulary.

**The distinction that matters:** does the sentence *assert* the claim, or
*attribute* it (to design, to prediction, to a source it names as insufficient)?
Only assertions have to move together.

### What to do when one is found

1. **Do not batch it.** Fix it in the same commit as the edit that created the
   mismatch. B9 unit 3 rewrote `08-threats.tex:96` and left `:385` contradicting
   it **289 lines away in the same file**, which is B26.
2. **Judge each site on its own passage.** A site may legitimately stay stronger
   or weaker if its paragraph is doing different work — but that must be a
   decision, not an oversight.
3. **Verify from the built PDF, not the source** (F.0i). Macros are separate
   tokens in source and one sentence when rendered; a quantity mismatch across a
   comparison is visible only rendered.
4. **If the search returns a site you did not know about, say so in the commit
   message.** That is the rule working, and it is the only evidence anyone gets
   that it ran.

---

## R8. A teardown that reports success is not evidence the device is gone.

`scripts/provision_write_loss.py teardown` printed `torn down` and exited 0
while the mapping was still present:

```
dmsetup ls   -> aep-ws4-flakey	(254:0)
losetup -a   -> /dev/loop0: [2096]:224042 (/var/tmp/aep-ws4/backing.img (deleted))
```

The backing file had been unlinked, so the path was gone and the *directory*
looked clean, while the kernel still held the mapping over a deleted file. The
teardown's own `dmsetup remove` had been a no-op because the mapping still had a
holder at the moment it ran, and nothing checked afterwards.

**Verify the device, not the teardown's exit code.** After any teardown of a
device-mapper target, assert all three:

```sh
dmsetup ls   | grep -c '<name>'   # 0
losetup -a   | grep -ci '<name>'  # 0
dmsetup info '<name>' 2>/dev/null | grep State   # absent; if present, see below
```

The third matters independently: a mapping left in `State: SUSPENDED` blocks
every I/O against it, so the next `mount` **hangs** rather than failing. That was
observed in this project — a proof script hung instead of erroring — and it is
why `write_loss._reload_table` resumes in a `finally`. A hang is worse than a
crash: the collection makes no progress and reports nothing.

A stray mapping is not merely untidy. The next session provisions a device with
the same name, and `dmsetup create` against an existing name fails — or worse,
succeeds against a different backing file than the record names.

### R8a. A teardown that follows a *failure* preserves the container first.

R8 as first written does not distinguish teardown-after-success from
teardown-after-failure. The second has an evidence obligation the first does not.

On **2026-09-04** a write-loss collection aborted on all 60 runs and the device
was torn down immediately afterwards — correctly, by R8 as it then stood. The
teardown ran `docker compose up` on the base file, which **recreated the
container**, and the only log that would have shown Redis's state at the moment
of the abort went with it. Two subsequent diagnostic passes could not recover it;
one of them read `RestartCount`, `OOMKilled` and `ExitCode` off the *replacement*
container and drew conclusions the rows did not support.

**Before tearing down after a failure, capture what the teardown will destroy:**

```sh
docker inspect "<container>"            > inspect-at-failure.json
docker logs    "<container>"            > logs-at-failure.log   # by ID, not name
docker events --since <window-start>    > events-at-failure.log
```

Then tear down and verify per R8. The device is reproducible; the container's log
is not.

### R8b. Return the stack to the base compose file *before* unmounting.

A container holding `/data` bound into the device's mount keeps that mount busy.
`umount` fails, `dmsetup remove` fails, and — because neither return code is
checked by default — **the teardown reports success over a device that is still
there**. That is R8's own failure mode, produced by ordering rather than by
neglect.

The order that works:

1. `docker compose -f compose.phase2.yml up -d --wait` — base file **alone**,
   never `-v`. This re-points `/data` at the named volume and releases the bind.
2. unmount, `dmsetup remove`, `losetup -d`.
3. verify per R8.

Found in `cf12884`'s own `teardown_on_refusal` — new code, written by the author
of R8, in the same session R8 was written. The read-back proof caught it: the
function printed `torn down` while `dmsetup ls` still listed the mapping. R8
tells you to check; R8b tells you why the check will otherwise fail.

## R9. Known flake: `test_a_kill_after_commit_keeps_both_and_tells_the_caller_nothing`

**Observed once, 2026-09-04**, in the full-suite run immediately preceding commit
`9ae9a73` (tree at `4d0fc84` plus two new untracked files). Result that run:
`1 failed, 1899 passed, 34 skipped`. Re-run immediately afterwards: **5/5
passed**. No tracked file was modified in that change — the surface was two new
files, neither touching the mock API — so it was not caused by the work in
progress.

**Do not chase it.** It is recorded so that a second sighting is recognised as a
second sighting rather than investigated from scratch.

**But it is not automatically noise.** It lives in
`experiments/mock_api/tests/test_service_crash_safety.py` and asserts what
survives a `SIGKILL` delivered *after* the ledger commit — a timing-sensitive
crash-safety property, exercised by the same mechanism WS-4 collection uses.
A recurrence **during or around a WS-4 collection** should be treated as a
signal about the collection's fault delivery, not dismissed by pointing at this
entry. The zero-skip gate (`scripts/check_pytest_gates.py`) makes any failure
loud, which is the desired behaviour; this entry does not license suppressing
it.

---

### R9a. Second known flake: `test_the_barrier_is_validated_once_not_per_resolution`

**Observed once, 8 September 2026**, in the full-suite run immediately preceding
commit `14148c6` (WS-8's final reference pass). Result that run: `2 failed, 1968
passed` --- the other failure was `test_verify_refs.py`'s pinned route counts,
which was real and is the subject of R15. Re-run **in isolation: passed**;
re-run as part of the full suite after the counts were corrected: **1970 passed,
0 failed**.

**Do not chase it.** Recorded so a second sighting is recognised as a second
sighting.

It lives in `tests/test_recovery_durability_barrier.py` and asserts that the
durability barrier is validated once rather than once per resolution. The change
in flight touched `paper/refs.bib`, `paper/sections/07-related.tex`,
`tests/test_verify_refs.py` and `.github/workflows/ci.yml` --- nothing in
`aep_core` and nothing in the barrier path --- so it was not caused by the work
in progress.

**This is not obviously the same phenomenon as R9's.** R9's flake is
`SIGKILL`-timing in the mock API's crash-safety suite; this one is barrier
validation counting in the recovery path. They share only that both are
timing-adjacent assertions that failed once under a full-suite run and passed
alone. Recording them adjacently is a filing convenience, **not a claim that
they have a common cause**, and a future investigation should not assume one.

---

### R9b. RESOLVED — a test-side defect, and the test's name pointed at the wrong thing

**Investigated and fixed 9 September 2026.** The entry below is the original
sighting, kept unedited; this section is what the investigation found. The short
version: **the code was right and the test was wrong**, and the failure had
nothing to do with the property the test is named after.

**The rate.** 25 isolated runs: **9 failed, 16 passed — 36%.** Three runs said
"not deterministic"; twenty-five said how often.

**What actually failed.** Not the mutation counts. Every failure was raised
before the assertions were reached:

```
7 x  WriteAheadWorkflowError: durability barrier did not acknowledge the
     preceding write
2 x  WriteAheadWorkflowError: durability barrier failed: DurabilityBarrierError
```

**The mechanism.** The test's own `_policy()` set `durability_timeout_ms=2_000`,
copied from the harness default. `WAITAOF` against a shared Redis running
`appendfsync everysec` can legitimately exceed two seconds under load, and when
it does **the barrier refuses to dispatch**. That is the fail-closed behaviour
§VI exists to describe, working correctly. The test asserted three successful
executions while silently depending on an unstated assumption about barrier
latency on whatever host ran it.

So the earlier characterisation in this entry --- that the property the WS-4 and
WS-6 oracles rest on might be nondeterministic --- **was wrong, and it was wrong
because the test's name was taken as a description of its failure.** A test
called `..._exactly_one_applied_mutation` failing does not mean applied
mutations were miscounted. The counting assertions never ran.

**Reachable in a collection? Yes, and it has fired --- but nowhere the paper
reads.** Established by reading the event logs rather than by argument, because
the worker records a failed execution as an `execution_failed` event carrying
its `failure_class`:

| tree | `WriteAheadWorkflowError` events |
|---|---|
| `experiments/results/matrix` (the frozen source the paper reads) | **0** |
| WS-4 write-loss session (`reports/raw/ws4-writeloss-s1-2026-09-07`) | **0**, against 600 `execution_resolved` |
| WS-6 B5 attempt 3 | **0** --- B5 never touches this barrier; its only `aep_core` mentions are docstring prose saying it deliberately does not import it |
| `phase10-replication-{drvfs,ext4}[-arbb30]-2026-09-02` | **40** |

**The paper's numbers are unaffected.** WS-4's 60 runs and WS-6's 120 runs are
clean, verified by count and not by inference. The mechanism fails **loudly**:
`worker.py` emits `execution_failed` with the class and sets
`UNEXPECTED_FAILURE_EXIT`, so it cannot silently shift a rate.

**The Phase 10 roots: settled, 9 September, and the answer is that nothing needs
re-deriving.** The four replication roots do contain 40 such events, and
`scripts/phase10_replication_analysis.py` reads those roots, so the question was
whether it excludes them, counts them as ordinary executions, or carries them in
a denominator they do not belong in. Read rather than assumed:

* The script has **no notion of `execution_failed` at all.** It reads
  `analysis/per-execution.csv` and counts every selected row, so it does not
  exclude them.
* It does not need to. The 12 distinct failed `execution_id`s appear as **26
  rows across the four roots, and every one carries a terminal outcome class** —
  8 `CONFIRMED_APPLIED`, 7 `CONFIRMED_NOT_APPLIED`, 6 `DECLARED_AMBIGUOUS`, and
  the rest terminal likewise. **None is `NO_RECORD` or `UNVERIFIED_FAILURE`.**
* On `recovery_success_rate` they score **26 of 26** in the numerator. On
  `known_ambiguity_rate` 6 of 26 score, which is simply the rate's definition —
  every execution is in that denominator whether or not it declared.

**So they are counted as ordinary executions, and they are ordinary
executions.** `execution_failed` records that the *initial dispatch attempt*
raised because the barrier refused; recovery then settled the intent, which is
the protocol behaving as designed. A refused dispatch that recovery resolves is
not a missing execution.

**And no paper number derives from that analysis.**
`phase10-replication-analysis.json` is read only by its own script and its own
prediction report; no macro in `paper/generated/numbers.tex` and no manuscript
prose reads it. There is nothing to re-derive.

**Scope of that claim, stated rather than implied:** what was verified is that
*these* 12 failed executions settled to terminal outcomes. It was not shown, and
is not claimed, that every possible barrier refusal settles. No collected result
was modified and no verdict script was re-run.

**The fix, and why it is not tuning-to-pass.** `durability_timeout_ms` in that
test file's `_policy()` raised from 2\,000 to 30\,000. It is local to the file
and changes no collection semantics --- a collection keeps 2\,000 deliberately,
because there a slow barrier is a *measured outcome* and must not be tuned away.
The test's subject is applied-mutation accounting, and barrier latency was never
part of that subject. A genuinely broken barrier still raises and still fails the
test; only the "the host was busy" path is removed.

**Proof the fix works:** the same 25-run protocol, after the change ---
**0 failed, 25 passed.** 9/25 to 0/25.

---

### R9b (original sighting, kept unedited): `test_one_execution_produces_exactly_one_applied_mutation`

**Observed 9 September 2026**, in the full-suite run during WS-9's first task
(`1 failed, 1969 passed`). Unlike R9 and R9a, **it did not pass on re-run in
isolation**: three consecutive isolated runs of that single test gave
**pass, fail, pass**. Running the whole file gave `6 passed, 1 error`, the error
being a separate teardown failure in
`test_the_runner_carries_no_test_authorisation`.

**Not caused by the work in flight.** The change under test touched
`scripts/build_paper.sh`, `scripts/check_paper_numbers.py`,
`scripts/paper_provenance.py` and the new `paper/supplementary.tex`. None is
imported by `experiments/mock_api/tests/`, and none touches `paper/`-unrelated
state. The same test passed in several full-suite runs earlier the same day.

**Why this one is a different class from R9 and R9a.** Both of those passed the
moment they were re-run alone, which is what made "flake, do not chase"
defensible: the failure needed the full suite's concurrency to appear. This one
reproduces **without** the suite around it, roughly one run in three on this
host under load. A test that fails alone is not a scheduling artefact; it is
either a real nondeterminism in the mock provider's dispatch accounting or a
test that under-specifies what it is asserting.

**Still not chased in this pass**, because `docs/26` §3 rule 12 puts a defect
found outside a task's scope in the record rather than in the diff. But it is
recorded with a **stronger recommendation than R9 or R9a**: this one should be
investigated before it is relied on, because
`test_one_execution_produces_exactly_one_applied_mutation` asserts the
one-execution-one-effect property that the WS-4 and WS-6 oracles are built on.
If that accounting is genuinely nondeterministic, it is a question about the
instrument and not only about the test.

**Do not fold it into R9's entry.** R9 is `SIGKILL` timing, R9a is barrier
validation, this is dispatch accounting, and the only property all three share
is the word "flake".

---

### R9c. The four "flakes" are one environment sensitivity, and three are unfixed

**Consolidated 9 September 2026, after R9b.** Three consecutive full-suite runs
each failed exactly one barrier-adjacent test, a different one each time:

| run | test | file |
|---|---|---|
| 1 | `test_one_execution_produces_exactly_one_applied_mutation` | `experiments/mock_api/tests/test_evaluation_dispatch.py` |
| 2 | `test_cas_and_waitaof_are_ordered_on_the_same_pinned_connection` | `tests/test_phase2_waitaof_integration.py` |
| 3 | `test_recovery_resolves_an_orphan_with_the_production_barrier` | `tests/test_recovery_durability_barrier.py` |

R9a's sighting, `test_the_barrier_is_validated_once_not_per_resolution`, is in
that third file too. **All four sit in tests that set
`durability_timeout_ms=2_000`**, and each passes in isolation --- R9b being the
exception severe enough to reproduce alone, at 36%.

**The evidence for treating them as one phenomenon**, rather than four flakes
filed adjacently:

* four for four on the shared constant;
* the only one investigated failed with a **barrier-timeout error**, not with
  the assertion its name describes;
* raising **only that one's** timeout took it from 9/25 to **0/25**, and it has
  not recurred since;
* the other three continue to appear, one per full-suite run, in the three runs
  after that fix.

The mechanism is the same one R9b established: `WAITAOF` against a shared Redis
on `appendfsync everysec` exceeds two seconds under full-suite load, and the
barrier does what it is designed to do --- refuses. **This is load, not
nondeterminism, and not a protocol defect.**

**Three are deliberately NOT fixed.** The one-line change that fixed R9b would
very probably fix them, and applying it to tests that have not been *shown* to
fail for that reason is tuning on a resemblance. R9b is precisely the warning:
its original entry assumed the failure matched the test's name and was wrong.

**What would settle them**, cheaply, for whoever takes it: run each 25 times
**under concurrent load** rather than in isolation --- isolation is the
condition under which they pass, so isolated repetition cannot answer the
question. If a run reproduces a barrier-timeout error, the fix is the same
one-line change with the same reasoning, and these entries collapse into R9b.

**Until then the zero-skip gate keeps them loud**, which is correct: an
intermittent failure that everyone recognises is better than a suppressed one
nobody sees.

---

## R10. Finding: on the write-loss regime the test-instance marker lives only in RAM.

**A finding, not a fix.** Recorded so it is not rediscovered as a surprise.

`aep:test-instance-marker` is the key rule 9 requires an instance to advertise
before the harness will run destructive cleanup against it. Under
`write-loss-preack` the instance is brought up on a **freshly provisioned
dm-flakey device whose AOF is empty**, so a marker set after provisioning exists
in memory and nowhere else. **Any restart during a collection loses it, and every
remaining run aborts.**

The six frozen regimes never meet this. Their Redis loads the `redis-data`
volume's AOF, which already carries the marker from an earlier set, so it
survives restarts without anyone having arranged for it to.

**It fails in the safe direction.** A lost marker makes runs *abort*, not
proceed: the harness refuses rather than running destructive cleanup against an
instance that has not asserted it is disposable. The cost is a wasted collection,
not a contaminated one.

**A durable marker is not obviously available here**, which is why this is a
finding rather than a fix. The AOF the marker would have to live in is the same
AOF the experiment exists to destroy — the fault *is* writes not reaching that
device. Seeding it into the base RDB before the collection starts is the most
plausible route and has not been designed, let alone tested.

`cf12884` narrowed the adjacent problem — the marker is now set by container id
and read back through the runner's own client, so a marker the *consumer* cannot
see stops the session. That closes the write/consumer gap. It does **not** make
the marker durable.

## R11. The 2026-09-04 dates on several WS-4 artefacts are wrong.

These files carry `2026-09-04` in their names or bodies and were written later:

* `reports/phase-report-ws4-prediction-2026-09-04.md` (the pre-registration, `d8b2ca5`)
* `reports/raw/ws4-fault-delivery-assessment.md`
* `reports/phase-report-14-write-loss-blocked-2026-09-04.md`
* **R9 above**, whose "Observed once, 2026-09-04" is subject to the same drift

The date was carried forward from Phase 13 and the host clock was not checked
until a directory had to be named, at which point it read **2026-09-07**.

**Git's timestamps and commit order are correct and authoritative.** Nothing
about what was done, or in what order, is in question — only the strings.

**The files are deliberately not renamed.** `d8b2ca5` is cited by commit in the
pre-registration, in `scripts/analyse_write_loss.py`, in the phase-14 prompt file
and in several reports; renaming the artefact a pre-registration lives in is a
worse defect than a wrong date, because a pre-registration's value is that it can
be shown unchanged. Read the dates in those four artefacts as approximate and the
commit history as exact.

## R12. A provider process orphaned on port 8099 survives teardown and fails the next session.

**Observed twice**, both times after a teardown that reported success.

* **Attempt 3.** A `kill -9` of the run left `experiments.mock_api` still
  listening. The next launch failed on the digest gate.
* **Attempt 5, first collecting launch.** A provider from attempt 4's run
  `b3_...-r23` was still on `127.0.0.1:8099`, twenty minutes after that
  collection ended. **All 60 runs failed**, in five seconds:

  > `MockApiStartupError: a provider is already serving http://127.0.0.1:8099
  > with digest 'b6ccbf3c...', but this run needs '80b14f45...'. Refusing to
  > collect a run against a configuration it did not ask for.`

**This is a teardown gap, not a gate failure.** The gate did exactly what it is
for: it refused, loudly, per run, naming both digests, rather than collecting 60
runs against a configuration they did not ask for. Had it not existed, attempt 5
would have produced a full-looking session measured against the wrong mock API.
Nothing about the gate should change.

What was missing is that **nothing owned the listening process**. R8 verifies the
device is gone. R8a preserves the container after a failure. R8b returns the
stack to the base compose file before unmounting. All three are about the device
and the container; a provider is neither, and it outlives both.

**The rule.** A teardown is not complete until the port is verified free:

```bash
ss -lptn 'sport = :8099' | grep -q LISTEN && { <kill the pid, then re-check> }
```

Verify, do not assert (R8's standard applies unchanged): re-read the port after
killing, and refuse to collect if it is still held. Attempt 5's launcher does
this as a pre-flight check and exits rather than collecting into a gate storm.

### R12a. Unexplained container restarts, third occurrence, not chased

At attempt 5's teardown both containers read `Up 14 seconds`: **something
restarted them after the collection had ended.** This is the third occurrence of
the class `reports/raw/ws4-sigterm-bound-2026-09-07.md` bounds — attempt 4's
SIGTERM, the non-recurrence in the Part 2 observation cycle, and now this.

**It did not touch the data.** The newest file anywhere under the results root is
`matrix-progress.jsonl`, written at the instant `run_matrix` returned 0; nothing
was written afterwards. Independently, `coordinator_restarted_unexpectedly` is
`False` in all 60 rows and the 2 s marker sampler recorded a single container id
throughout.

**Deliberately not chased.** The origin is unestablished and stays that way. What
removed it as a blocker was making the marker durable (`a994023`), so a restart
no longer destroys it — not an explanation. Recorded here so a fourth occurrence
is recognised as a pattern rather than met fresh.

## R13. A leak scanner that cannot distinguish zero from one is worse than no scanner.

**Observed 2026-09-07**, twice in one pass, in the anonymity checks themselves.

**First, a false negative shape.** The needle loop was

```bash
C=$(grep -c -- "$N" anon.txt || echo 0)
```

`grep -c` prints `0` **and exits 1** when there are no matches, so `|| echo 0`
appends a *second* line. `C` becomes the two-line string `"0\n0"`, every
`[ "$C" != "0" ]` is true, and **every clean needle rendered as a hit**. The
first run reported `HIT Hamza (0 0)`, `HIT github (0 0)`, and so on for sixteen
needles.

That run happened to be noisy rather than dangerous, because the direction was
false-positive. The same construction one refactor away — `[ "$C" = "0" ]` for
"clean" — reports **clean for everything**, and an anonymity scan that always
says clean is exactly the artefact you would ship a deanonymised PDF behind.

**Second, a false positive, in the replacement.** The DocInfo check used

```python
re.search(rb"/" + key + rb"\s*\((.+?)\)", raw, re.S)
```

pdfTeX writes the empty keys adjacently — `/Author()/Title()/Subject()` — so a
dot-matching group opening inside `/Author()` runs past its own `)` and closes
on `/Title()`'s, capturing `")/Title("`. **Every empty key was reported as
populated.** It was caught only because it failed on a PDF that had already been
verified clean by hand ten minutes earlier; on a first-ever run it would have
been read as a real leak and "fixed" in the PDF. The repair is `[^)]+`, which
cannot cross the delimiter.

**The rule.** Any scanner whose output is *"nothing found"* must be shown to say
something else on a case that contains the thing. This is **R3** applied to
searches rather than gates, and **R2** applied to counts: run it against a known
positive before trusting a negative.

For the anonymity checks specifically that proof is
`scripts/prove_anonymous_gate.sh`, which rebuilds the manuscript *without*
`\pdfsuppressptexinfo`, `\pdfinfoomitdate` and `\ANONYMOUS`, shows all three
content checks fail on it (naming `/PTEX.FileName`, `Creator, Producer,
CreationDate/ModDate`, and the real byline), modifies a source to show the
staleness check fail, then restores and re-runs to `23 passed, 0 failed`.

**Same class as R1.** There the failure was `pgrep`/`pkill` matching their own
command line, so *"is it still running?"* answered yes forever. Here it is a
scanner miscounting its own matches. Both are tools reporting confidently about
something they never actually measured, and in both the report is what gets
believed.

## R14. Hold the checking code to the standard of the code it checks.

**Eight instances now.** It has stopped being an observation and become the most
reliable defect generator in this project, so it is a rule. Instance 6 is in
R14a below; instances 7 and 8 are at the end of this list. Seven is the first to
have been caught from outside the project rather than by a number looking wrong.
Eight is the first in which the blank output would have been read as a
**pre-registered hypothesis being refuted**, which is the most expensive form
this defect has taken.

The shape is always the same: the instrument is written quickly *because it is
"just" a check*, and then it becomes the thing every other conclusion is believed
on. In every instance below the defect surfaced only because a result looked
wrong against something already known by hand — **never** because the instrument
caught it.

### The instances

1. **The anonymity scan** (`docs/25` R13, `309c4e5`). `C=$(grep -c … || echo 0)`
   made every clean needle read as a hit, because `grep -c` prints `0` *and*
   exits 1. Noisy in that direction; one refactor from a scan that reports clean
   for everything.
2. **The DocInfo regex, written to replace it.** `(.+?)` with `re.S` ran past its
   own `)` onto the next key's, reporting every empty field as populated. Caught
   only because it failed on a PDF verified clean by hand ten minutes earlier.
3. **The rule-13 proof** (`309c4e5`). `prove_anonymous_gate.sh` asserted by
   *re-running* the checker rather than on the output it had just printed — so it
   asserted about a run it had not shown. The R13 shape, inside the proof written
   to justify R13.
4. **The WS-4 verification script** (`856d78a` §3). Compared two greps with
   *different patterns* and reported a difference that did not exist, inside the
   check that the fix had produced no false result.
5. **The WS-6 probe** (`a54940a`, and again the pass after it). Its readiness
   check could say *"not ready"* but never *"I am asking the wrong question"*: it
   polled `/healthz`, which does not exist, reported `000`, and the probe
   **proceeded anyway**. Then its latency sampler counted any non-5xx as a
   healthy sample, so 30 consecutive `422 unidentifiable-envelope` refusals
   returned in under 2 ms were recorded as a provider p50 of 8.6 ms — against a
   provider configured with a **2 s** delay. The measurement was not merely
   imprecise; it was of the rejection path.

7. **The `docs/35` grep, 10 September.** `docs/35` §0.2 ran
   `grep write-loss experiments/results/*/analysis/per-cell-metrics.csv`, got
   nothing, and wrote that the `write-loss-preack` regime *"is implemented and
   has never been collected."* It had been collected on 7 September and lives
   under `reports/raw/`, 60 runs, 258 files tracked in git. The grep was correct
   about the tree it searched; it could report *found* and *not found* and had
   no way to report **I looked in the wrong place**.

   **Two things make this the worst instance so far.** It is in a document whose
   own §0.1, two paragraphs earlier, accuses its predecessor of exactly this —
   *"inference from a grep window presented as a fact about a file"* — so the
   rule was not merely unapplied but stated and then broken in the same pass.
   And it was load-bearing: §5 built the argument for a four-to-seven-week
   workstream on that cell being uncollected, when the cell had already been
   measured and showed the arms 0.67 pp apart. Caught by an external audit, not
   by the instrument, which is instance 1's shape again.

   *The cheap guard it did not have:* a search whose negative result is
   load-bearing must be run against a **known positive** first (R2), or be
   widened until it finds something and then narrowed. `git ls-files | grep`
   would have found it; so would searching the repository rather than one
   subtree.

8. **`power_analysis.py`'s empty section, 14 September, and mine.** Phase 17
   ran the mixture instrument as pre-registered,
   `power_analysis.py --section degeneracy`. That view rebuilt the report
   without the `mixtures` key, so section A2 printed its heading with **nothing
   under it** — and `print_report` emitted every heading unconditionally, so an
   uncomputed section and an empty result rendered identically.

   **What made it dangerous is what the blank meant.** Amendment 1 of the WS-5
   pre-registration fixes the decision rule as *"If no arm is flagged at fifteen
   runs, the mixture reporting is omitted and the pooled median stands. That
   outcome is H2 of the pre-registration being refuted."* A blank A2 is exactly
   what "no arm was flagged" looks like. The instrument was one glance away from
   reporting a pre-registered hypothesis refuted because a dictionary key was
   missing.

   Caught only because the fifteen-run B3 arm visibly has two modes — 120
   executions near 2 056 ms and 30 near 5 048 ms — so a blank A2 contradicted
   something already known by hand. That is instance 1's shape again, and the
   fourth time in this list that the instrument was not what noticed.

   *Fixed twice, because one fix was too narrow.* The key now travels with the
   degeneracy view; and **every** section, in every view, now prints which kind
   of empty it is — `not computed in this view` or `computed: no arm has a
   splittable sample`. Rule 13 is discharged against the pre-fix module at
   `5ff3dc2`, which renders A2 as a heading followed directly by section B.

### The rule

A checking instrument must be able to report **three** outcomes, not two:

* the thing is there,
* the thing is not there,
* **I could not look, or I looked in the wrong place.**

An instrument that can only express the first two will express the second when
the third is true, and the second is usually the answer that lets work proceed.

Concretely, and each of these comes from one of the instances above (the list runs 1-5, 7 and 8; 6 is R14a):

* **Never let `not found` and `could not ask` render the same.** Verify the probe
  against a **known positive** before trusting any negative (R2 applied to
  searches).
* **Assert on the output you showed**, not on a fresh invocation of the same
  command (instance 3).
* **Compare like with like** — if two extracts are to be diffed, build them with
  the same expression (instance 4).
* **A section that computed nothing must not render like a section that found
  nothing** (instance 8). Print which kind of empty it is, or exit non-zero. The
  same applies to a gate whose inputs are incomplete: `make reproduce-figures`
  tested the *presence* of run directories and so ran over 84 of 432, reporting
  the shortfall as a moved value. It now tests the count against the archive's
  own manifest and skips with both numbers named.
* **Check the success shape, not the absence of an error shape.** `< 500` is not
  success; `2xx` is (instance 5).
* **A readiness check must fail closed and say which** — `paper_provenance`
  already states this for artefacts: *"I could not read it" and "it is unchanged"
  must never render the same*. It applies to every probe.

### R14a. A test's name describes what it asserts, not why it failed.

**Added 9 September 2026, from R9b.** The sixth instance, and the first in which
the object held to too low a standard was a **report** rather than an
instrument.

`test_one_execution_produces_exactly_one_applied_mutation` failed. It was
recorded — by me, in this file — as possible nondeterminism in the property the
WS-4 and WS-6 oracles rest on, because that is what the name says the test
asserts. **The test never reached its assertions.** It raised in setup, on a
durability-barrier timeout, and the mutation counts were never evaluated at all.
The name described the intended subject; the failure was somewhere else
entirely.

The cost was not just a wrong entry. **A whole prompt was written on that
premise** — investigate a possible nondeterminism in the oracles' foundation —
and the investigation's first real finding was that the premise was false. The
error propagated from a record into a plan before anything checked it.

> **Read the failure, not the name.** A failing test tells you its name and its
> traceback. Only one of those is evidence about what went wrong, and the cheap
> step that settles it — capture the actual error before characterising the
> failure — takes one run.

This is R14's demand pointed at prose: a report is also an artefact, it also has
a way of being wrong, and nothing in R3, R13 or R14 compels anyone to check that
a summary matches the thing it summarises. R14's own widening anticipated this —
*"a readiness check must fail closed and say which"*, and *"I could not read it"
and "it is unchanged" must never render the same* — but it was stated about
probes. It applies to sentences.

### Relation to the existing rules

**R3** requires a gate be exercised on its failing branch; **R13** says a gate
that cannot fail is decoration. R14 is the same demand pointed one level up: the
*checker* is also code, it also has a failing branch, and nothing in R3 or R13
compels anyone to exercise it. These five instances are what that gap produced.
**R14a** points it one level up again, at the report describing the checker.

---

## R15. Verify a change with the gate that covers what you changed.

**Two occurrences, both the same shape: a fix was verified by a gate that could
not see what the fix touched.** This is not R14. R14 is about an instrument that
cannot report the third outcome --- a checker too weak to fail. R15 is about
running the wrong instrument at all. The gate in both cases was sound; it was
simply pointed somewhere else.

**Occurrence 1 --- `856d78a`, 6 September.** The commit closed two WS-4 findings
and was verified by running `check_paper_numbers.py`. That gate reads the
manuscript against the analysis CSVs. The change also touched harness code, and
it regressed `test_the_unit_of_analysis_is_the_run` in
`tests/test_write_loss_verdict.py` --- a test the paper gate does not run and
cannot run. The regression was found later, not by the verification performed at
the time.

**Occurrence 2 --- WS-8, 8 September.** Five reference passes each ran
`check_paper_numbers.py`, `verify_refs.py --offline` and `validate_citations.py`,
all of which passed every time. None ran the suite. `tests/test_verify_refs.py`
pins the bibliography's route counts precisely so that a new entry must be routed
deliberately, and it went red on the **first** WS-8 commit and stayed red for
**four commits** before the full suite was run again. The gate worked exactly as
designed and nobody was looking at it.

### The rule

> **Verify a change with the gate that covers what you changed, and run the full
> suite before any commit that touches tracked code or tests. Paper gates do not
> substitute.**

The paper gates answer a narrow question --- does the manuscript still match its
results --- and they answer it well. They say nothing about whether the
repository's own tests still pass. A commit that edits `refs.bib`, a script, or
a test file has changed something no paper gate reads.

### Why this is worth its own entry

The two occurrences are eight days apart, in different workstreams, by the same
route: a plausible, relevant, *passing* gate was mistaken for sufficient
verification. Neither was caught by review; both were caught later by running the
thing that should have been run first. That is a habit failure rather than a
tooling failure, which is why the rule is stated as a running discipline and not
as a new check.

### Is anything enforcing it? No.

Nothing in the repository prevents a commit whose tests were never run. Two
mechanisms would catch this class, and neither is built in this pass:

* **A pre-commit hook** running the suite when the staged set touches
  `tests/`, `scripts/`, `experiments/` or `aep_core/`. It would catch both
  occurrences at the moment they happened, which is the right moment. The cost
  is the suite's wall-clock: **8m31s** measured on 8 September. That is too long
  to sit in front of on every commit, and a hook that slow is a hook people
  disable or bypass with `--no-verify` --- which converts a habit failure into a
  habit failure with a false sense of coverage. A *targeted* variant --- run only
  the test files that import what changed --- would be fast enough, but choosing
  those files correctly is itself the checking code R14 warns about, and getting
  it wrong reproduces exactly this bug one level down.
* **A CI step**, which already exists: the suite runs on every push, so both
  occurrences *would* have been caught in CI. What CI cannot do is catch them
  **before** the commit, and both of these sat in pushed commits --- four of them
  in the WS-8 case --- which is the gap. CI turns this from an undetected defect
  into a late-detected one; it does not remove it.

**Recommendation: no hook here, at least not yet.** The honest fix is the rule
above plus reading CI results after pushing, which was the step actually skipped.
If a third occurrence appears, the targeted pre-commit hook becomes worth its
cost and its own R14 treatment --- and a third occurrence is the trigger, in the
same sense R12a records a third unexplained restart so a fourth is met as a
pattern.

---

## R16. A test that inspects a destructive script must not execute it.

**Do not** let a parametrised test invoke a collection script whose results
root is a compiled-in default. **Do** make the root an input and point the
test at a sacrificial directory, or assert against the source text.

**Why, from 14 September, phase 19 --- and the victim was published data.**

`scripts/fsync_always_benchmark.sh` had `CLEAN` defaulting to `1` and a
recursive delete of the hardcoded `experiments/results/fsync-always`. Ruling
on the preserved stage 3 safety test required R13 --- run the test against the
old code first and watch it fail. Three of its four properties are source
inspections and are inert. The fourth is a run-count gate, it is parametrised,
and **it runs the script**. On the old script there was no gate to stop at, so
every invocation fell into the delete and then into a real collection. They
raced: one invocation's `rm -rf` removed the run directory another was writing
into, and that is preserved as a `FileNotFoundError` traceback in the
quarantined `matrix-progress.jsonl`.

Sixty executions across six raw run directories, behind three published
macros, gone. Not recoverable: they were gitignored, uncommitted, unmanifested.

**The compounding part is the gitignore.** That root un-ignores its two
derived CSVs and ignores everything else. So `git status` reported *two*
deleted files and could not report the *sixty* that mattered more --- and
those two came back from git, which is exactly what makes the loss look
survivable at a glance. **A tree whose valuable half is invisible to
`git status` needs a manifest, and this one had none** --- a fact recorded in
the same pass's report, hours before the deletion, as an observation rather
than an action.

**R13 and this rule pull against each other, and R13 still wins.** Exercising
the failing branch is what made the ruling worth anything: it is what surfaced
the default-on delete at all. The defect is not that the old code was run. It
is that it was run *in the repository*, against its own default root, instead
of in a copy. Before running the old version of anything destructive, ask what
its defaults point at --- and if the answer is a path under
`experiments/results/`, run it somewhere else.

Account: `reports/incident-fsync-always-raw-destroyed-2026-09-14.md`.

### Relation to the existing rules

* **Rule 2** (docs/26: frozen results are immutable) is the rule that was
  broken. R16 is about the mechanism that broke it.
* **R4** already says a destructive gate needs a dry-run seam before R3 can be
  applied to it. R16 is R4 read in the other direction: the seam is needed
  before the *test* can be applied to it either.
* **R15** is what caught it, and only just. `check_paper_numbers.py` failed
  with a `FileNotFoundError` on a path the pass had no reason to think it had
  touched. Nothing else in the pass would have.
