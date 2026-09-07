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