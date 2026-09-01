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
