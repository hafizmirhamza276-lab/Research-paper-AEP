# Revision backlog

Work that the Phase-5A adjudication (`reports/phase-report-5a-2026-08-10.md`)
resolved as **(c) DEFER**: named, designed, and not done. Each entry states the
experiment precisely enough that someone else could run it, and states what
blocked it here rather than leaving the reader to guess whether it was
difficulty or oversight.

Nothing in this file is a claim about results. These are designs.

---

## B1. Run the protocol — not two Redis keys — under host-level write loss

**Source:** hostile-pass item 1, `reports/phase-report-4b-2026-08-07.md` §F.5.
**Paper location of the admission:** `paper/sections/08-threats.tex:34-47`.

`experiments/flakey_write_loss.py` establishes the premise the barrier's
durability argument rests on — a `WAITAOF`-acknowledged key survives a device
that stops accepting writes (90/90) while an unacknowledged one does not
(90/90) — but it exercises two Redis keys, not AEP. No *protocol* outcome
(undetected duplicate, lost effect, declared ambiguity) has ever been measured
under write loss, so the durability half of the barrier's case is a premise
plus an argument rather than a system-level result.

**Design.** Provision the harness's Redis on the `dm-flakey` device instead of
beside it: loop device → `dm-flakey` (`drop_writes`) → ext4 → a Redis 7.2.5
whose `dir` is on that filesystem, with `appendonly yes` and `appendfsync
everysec` exactly as `redis/phase2.conf` sets them. Then run the existing
`redis-kill-preack`-shaped ablation with the fault swapped: for each of
AEP-full and B3, 30 runs × 10 executions on `NO_READBACK`, dropping writes at
the instant the intent CAS returns and before the barrier could acknowledge.
The measured quantity is the same unwanted-applied-effect rate already defined
in `scripts/paper_tables.py`, plus the undetected-duplicate and lost-effect
rates from `analyze.py`. The prediction that would be tested — and that the
paper currently only argues — is that AEP-full's `DurabilityAck` gate withholds
dispatch when the record it depends on was destroyed, and that B3, having no
such gate, proceeds. Budget ≈ 2.5 h for both arms plus device setup.

**What blocked it here, exactly.** Not difficulty — a resolution failure in the
container runtime. This Docker daemon resolves bind-mount *sources* in the
Windows filesystem, not in the WSL distro's: `docker inspect
aep-phase2-redis72` reports its config mount as
`src=D:\personal\AEP\Research-paper-AEP\redis\phase2.conf`, a Windows path,
even though the harness driving it runs inside WSL. A `dm-flakey` device
assembled inside WSL exists only at a WSL path, so it cannot be named as a
bind source for the container; mounting `/mnt/d/...` produces an empty
destination, which is the daemon's way of reporting that it could not resolve
the source (`scripts/fsync_always_benchmark.sh:44-54` records the same failure
from the other direction). The alternative — a native `redis-server` in the
distro, on the flakey filesystem, with no Docker in the path — is not available
either: `which redis-server` in Ubuntu-24.04 returns nothing, so it would have
to be installed, and the installed build would not be the digest-pinned
`redis:7.2.5-alpine@sha256:6aaf3f5e...` that every other number in the paper
was collected against. Both routes therefore require a change to the host or to
a pinned artifact, which Phase 5A's bounds forbid.

**Cheapest unblocking step.** A Linux host with a native Docker daemon (not
Docker Desktop's Windows-resolving proxy), where the loop device, the
filesystem and the container all live in one namespace. This is the single
most worthwhile extension to the evaluation, and the paper says so.

**Required of this phase when it runs (added by Phase 8.2): verify
`redis_storage_backing` differs from the frozen runs, and state it in the
report.** Not optional, and not merely recorded — *read*.

Every number currently in the paper was collected with Redis's `/data` on a
**named Docker volume** (`compose.phase2.yml:12`, `redis-data:/data`), i.e. on
Docker's own storage, and `docker inspect` confirms it:
`type=volume, source=/var/lib/docker/volumes/aep-phase2_redis-data/_data`.
B1's whole design is to **bind-mount that directory onto a `dm-flakey`
device**, so B1's numbers will be the first collected with the AOF on a
different storage stack from every number they will be compared against.

That is the same shape of defect Phase 8.1 caught and Phase 9C missed: a
property that can move a measured quantity, that nobody chose to hold fixed,
and that no field recorded. It is worse here, because in B1 the storage *is*
the fault under test — a difference in the backing is not a confound to be
controlled away but the thing being manipulated, and it must be stated rather
than assumed comparable.

`experiments/harness/provenance.py` now detects the backing at run
construction and writes it into `run-config.json` under `environment`. B1 is
therefore required to: (i) read the field from both its own runs and the
frozen ones, (ii) confirm they differ and say how, and (iii) not report any
AEP-versus-frozen comparison of absolute barrier latency without that
statement. Detected, never declared — nobody declared drvfs either.

**Required of this phase when it runs (added by Phase 8.4): the second host is
now required for *reliability*, not only for the bind-mount.** B1 has always
needed a Linux VM because `dm-flakey` under a bind-mount is not reachable from
Docker Desktop's VM. Phase 8.4 adds an independent reason, and it is the
stronger one.

**Fault delivery itself is degrading on this host.** The harness raises
`FaultInjectionError: the hard kill did not land` when Redis reports an
`uptime_in_seconds` showing it is the same server process the run started with,
so no infrastructure fault was injected. The counts:

| collection | runs | kills that did not land |
|---|---|---|
| Phase 9, four sessions | 240 | **0** |
| Phase 8.4 session 1 | 120 | **0** |
| Phase 8.4 session 2 | 120 | **2, both in the first 26** |

**Zero to two is a change in kind, not in degree.** Across 360 prior runs the
kill had never once failed to land. This is the same host degradation already
visible in two other places — the within-session drift, whose *sign* reverses
between sessions, and the kill-latency envelope — and fault delivery is now a
third independent surface showing it.

**Why this bears on B1 specifically, and harder than on Phase 8.** In Phase 8
the kill is a *side condition*: a run whose fault did not land is discarded
(amendment 4) and the estimand is measured on the runs where it did. In B1 the
fault **is the measurement**. Write loss under `dm-flakey` is the quantity being
studied, not the condition under which some other quantity is studied. An
instrument that intermittently fails to deliver the fault does not cost B1
precision — it silently removes the phenomenon while leaving runs that look
successful.

So the second host is not merely a convenience for reaching `dm-flakey`, and
not merely a way to sample a second timing distribution. **It is required for
B1's fault delivery to be trustworthy at all**, and B1 must additionally report
its own non-delivery count as a first-class number rather than as a footnote.

---

## B2. Replicate the prevention result beyond one cell

**Source:** hostile-pass item 2, §F.5.
**Paper location of the admission:** `paper/sections/08-threats.tex:325-335`.

The barrier's entire measured case is one cell: `redis-kill-preack`,
`NO_READBACK`, one crash point, 30 runs per arm, one host — with an effect size
the paper itself attributes partly to that host's `docker kill` latency. The
detection result has 540 crashed-regime executions per arm across three capability classes;
the prevention result, which is the barrier's only remaining claim after the
ablation, has one.

**Design.** Collect the same `redis-kill-preack` ablation on the two
uncollected capability classes: AEP-full and B3, on `AUTHORITATIVE_READBACK`
and `POSITIVE_ONLY_READBACK`, 3 runs × 10 executions per crash point at the
`after_intent_before_barrier` crash point where the kill is placed, i.e. four
new cells at n=30 per system per class. The regime already exists in
`experiments/run_matrix.py` (`--regime redis-kill-preack`), so this needs no
code change — only host time on an idle machine. The paper's stated
expectation is falsifiable and should be recorded before the run: the
capability class should move the *declared-ambiguity* column and leave the
*applied-effect* column alone, because whether an effect reached the provider
is not something a read-back can change after the fact. A result in which the
applied-effect column moves with capability class would contradict the
mechanism as described and would be the finding. Budget ≈ 2 h.

**Why deferred.** Phase 5A's experiment budget was 2.5 h and was spent in full
on the G3-gap AUTH cells (hostile-pass item 5), which the same prompt
prioritised. This is the next experiment to run, ahead of everything else in
this file except B1.

---

## B3. More crash-free runs, so the barrier's cost under `always` has an interval that means something

**Source:** hostile-pass item 4, §F.5.
**Paper location of the admission:** `paper/sections/08-threats.tex:268-292`.

The cluster bootstrap over runs reports the barrier's cost under `appendfsync
always` as a point estimate whose 95% interval spans zero. The paper says so
and has removed the ratio claim that did not survive it. The limitation is the
sample: three clusters admit only ten distinct bootstrap multisets, against an
`always` cell with a heavy upper tail (p95 5 067.8 ms against a 2 063.4 ms
median). The fix is more crash-free **runs**, not more executions per run.

**Design.** Raise the crash-free `p0` cell for both arms — AEP-full and
B3-mode — from 3 runs to 9 runs of 10 executions under `appendfsync always`,
and correspondingly under `everysec` so the comparison stays matched, then
regenerate `cluster_bootstrap_median_difference` through
`scripts/paper_tables.py` unchanged. Nine clusters admit enough distinct
multisets that the interval stops being an artifact of the resampling
granularity. The claim to re-evaluate afterwards is the one the paper now
makes directionally: hundreds to ≈2 000 ms under `everysec`, and nothing
demonstrable under `always`. Budget ≈ 1 h for the additional runs.

**What blocked it here, exactly.** `scripts/fsync_always_benchmark.sh` cannot
produce additional runs with its existing parameters, and Phase 5A forbids
editing it. Line 166-173 invokes `experiments.run_matrix` without
`--runs-per-cell`, so the cell inherits the harness default of 3
(`experiments/run_matrix.py:1104`). Line 172 passes `--resume`, and resumption
is per-run: `already_collected()` (`experiments/run_matrix.py:868-882`) skips
any run whose `summary.json` parses, so a second invocation with
`AEP_FSYNC_CLEAN=0` collects **zero** new runs. The only other setting,
`AEP_FSYNC_CLEAN=1` (the default, acting at line 156-157), `rm -rf`s the
results root and recollects the *same three seeds* — destroying existing runs
to reproduce them, which Phase 5A also forbids. The three exposed variables
(`AEP_FSYNC_SYSTEMS`, `AEP_FSYNC_MOCK_PORT`, `AEP_FSYNC_CLEAN`) do not reach
`--runs-per-cell`. Raising the count therefore requires either editing the
script or bypassing it, and the script exists to enforce the `CONFIG GET
appendfsync` gate (lines 131-135) that makes the measurement trustworthy, so
bypassing it is worse than deferring.

**Cheapest unblocking step.** One line in `scripts/fsync_always_benchmark.sh`:
expose `AEP_FSYNC_RUNS` and pass it through as `--runs-per-cell`. That is a
one-token change to a script that is READ-ONLY under the weekend prompt regime
and would be entirely routine outside it.

---

## B4. Evaluate declared ambiguity as an operational outcome

**Source:** hostile-pass item 6, §F.5.
**Paper location of the admission:** `paper/sections/08-threats.tex:141-151`.

This is the largest gap between what the paper measures and what it argues, and
it is unchanged since Session 1. The paper measures how often AEP declares
ambiguity and shows it never substitutes a silent failure for it. It does not
show that declaring is *better in practice*. The argument that a declared
incident beats an undiscovered one is a normative claim about failure handling,
and the paper marks it as such rather than evidencing it.

**Design.** An operator study, which is a different instrument from everything
else in this evaluation and should be reported as such. Recruit 12–16
practitioners who operate production integrations (not the authors, and not
people who have seen the protocol). Each receives the same incident queue,
replayed from real harness output: a mixed set of executions terminating in
`PERMANENTLY_AMBIGUOUS` from AEP-full, alongside a control condition drawn from
a baseline in which the same underlying faults produced silent duplicates or
lost effects discoverable only by reconciling the provider's ledger by hand.
Within-subject, order counter-balanced. The measured outcomes are the four the
threats section already names as unmeasured: what fraction of declared
ambiguities the operator resolves, time-to-resolution, resolution *accuracy*
against the oracle ledger the harness already writes, and whether the queue
stays bounded under a fixed arrival rate. The comparison that matters is
accuracy and time on the AEP condition versus the baseline condition, not
subjective preference. Pre-register the analysis; the honest null is that
declared ambiguity costs operator time without improving final-state accuracy,
and the study should be able to return it.

**A prerequisite the artifact does not have.** `paper/sections/08-threats.tex:149-151`
records that reaching the terminal state pauses the execution and alerts
nobody — there is no escalation mechanism. A study of how operators handle a
queue needs the queue to exist, so building a minimal escalation surface is
part of this work rather than a precondition met elsewhere.

**Why deferred.** A human-subjects study is out of scope for any prompt in
`WEEKEND_CODEX_PROMPTS.md` and cannot be run by an agent in a weekend. It is
recorded here so that the gap is tracked as work rather than absorbed as a
permanent caveat.

---

## B5. `freeze_results.py` cannot produce a verifiable manifest on Windows

**Deadline: before Phase 10.** Not deferred indefinitely like B1–B4 — this one
has a date, because `SHA256SUMS` is the artifact's integrity mechanism for
exactly the reviewers `ARTIFACT.md` is written for.

**Source:** Phase 8.1, `reports/phase-report-8-1-0-2026-08-27.md` §F.1.

`scripts/freeze_results.py` writes the manifest with two platform-dependent
constructs, at lines 178–179:

```python
    sums = [f"{sha256(path)}  {path.relative_to(root)}" for path in digested]
    (root / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
```

`Path.relative_to` renders `analysis\per-execution.csv` on Windows, and
`write_text` translates `\n` to `\r\n`. The result is a `SHA256SUMS` whose every
entry names a file that does not exist under that spelling and carries a
trailing `\r`. Observed when freezing the four Phase 9 roots from Windows:

```
sha256sum: 'analysis\table-1.csv'$'\r': No such file or directory
sha256sum: WARNING: 16 listed files could not be read
```

exit 1, on all four roots. The committed convention — set by
`experiments/results/matrix/SHA256SUMS` — is forward slashes and LF.

**Why this is not the same defect Phase Q fixed.** `.gitattributes` marks
`experiments/results/** -text`, which pins the bytes on *checkout* so a clone
cannot corrupt a manifest it received. It says nothing about *generation*: a
manifest produced on Windows is already wrong before git sees it, and `-text`
then faithfully preserves the wrongness.

**The fix, two lines.** `path.relative_to(root).as_posix()`, and
`newline="\n"` on the `write_text` call. `reports/raw/extract_kill_latency.py`
already does the equivalent for its own output and says why in a comment.

**A test that would have caught it.** Freeze a small fixture tree and assert the
manifest contains no backslash and no `\r`. Cheap, and it fails today on Windows
and passes on Linux, which is the whole point.

**Worked around, not fixed, in Phase 8.0**: the four roots were frozen under WSL
instead, after which all four verify 16/16 OK. That work-around is invisible to
anyone who later runs the script on Windows and trusts its exit code, which is
why this is tracked rather than left as a note.

---

## B6. The submission PDF cannot be built on the author's machine

**Deadline: before Phase 14 (the submission package).** Dated for the same
reason B5 is: the failure surfaces at the worst possible moment if it is left.

**Source:** Phase 8.1, `reports/phase-report-8-1-0-2026-08-27.md` §F.6.

The author's local TeX Live (2023/Debian, in WSL) typesets **24 of the 29**
`\bibitem` entries `bibtex` correctly produces. The last entries never receive a
`\bibcite`, so nine citations render as undefined and
`scripts/check_paper_numbers.py` fails its `no undefined references or
citations` check on a pristine tree. CI, which installs its own TeX Live, is
green on the same commits — so **CI is currently the only place the
bibliography is correct**, and the PDF a local build produces is not the PDF the
paper claims to be.

That is tolerable while CI is the arbiter and nothing is being submitted. It
stops being tolerable at submission, for a specific reason: **arXiv does not
accept a PDF, it accepts a source tarball and builds it itself.** A submission
prepared from a locally-verified tree would surface this as a broken
bibliography inside arXiv's build, after the deadline-shaped commitment has been
made, with the author's only local reproduction being the broken one.

**Two acceptable fixes; the phase picks one.**

1. **Pin the TeX distribution** the way the Redis image is pinned — a container
   or a `tlmgr` manifest — so a local build and a CI build are the same build.
   Consistent with how every other dependency in this artifact is handled, and
   it makes the failure impossible rather than detected.
2. **Make "built by CI, not locally" an explicit, checked precondition** of the
   submission package: `ARTIFACT.md` and the submission checklist state that the
   tarball is assembled from a CI-produced artifact, and the packaging step
   refuses to run against a locally-built PDF.

(1) is better. (2) is acceptable if (1) proves expensive, but only if it is
*enforced* — a note saying "build in CI" is not a precondition, and this
project's own history has an audit finding (S4-D) about exactly that class of
unenforced assumption.

**Diagnostic detail, so the next reader does not repeat it.** `bibtex` is not at
fault: its log reports `You've used 29 entries` and all 29 keys appear as
`\bibitem` in `main.bbl`. The truncation happens during typesetting, and only
`\bibcite` lines 1-24 reach `main.aux`. Phase 8.1 checked the obvious
alternatives and none of them explain it: the keys are all present in
`refs.bib`, a manual three-pass build reproduces it, and building on ext4
instead of drvfs makes no difference (29 bibitems either way).

---

## B9. 8.1's kill-latency test assumes exchangeability, and the runs are not exchangeable

**Due before Phase 10 (the DOI).** The number this concerns is already in the
manuscript, so this is due before the artifact is minted, not after.

**The claim at risk.** `06-evaluation.tex` reports that across the replication
set the runs which applied an effect had a median `docker kill` latency
`\KillLatencyDiff{}`\,ms longer than those that did not, at
$p = \KillLatencyP{}$, and uses it to argue the unwanted-applied-effect rate is
a race outcome rather than a protocol constant. Phase 8.1 computed that with a
permutation test over run labels, and the committed stratified figures
(`\KillLatencyOrigP{}`, and the Mann-Whitney variants) share the same
assumption.

**Why it is at risk.** A permutation test assumes the observations are
*exchangeable* under the null: that relabelling them is as likely as the labels
observed. Phase 8.4 session 1 measured that kill latency **drifts monotonically
within a session** — Spearman(run position, latency) $= 0.703$ over 120 runs,
with block medians rising 829 → 1008 → 1114 → 1167 → 1070 → 1145 → 2162 →
2176\,ms. Under drift, runs adjacent in time are correlated, exchangeability
fails, and the permutation distribution is too narrow: **the p-value is
optimistic**, possibly by a lot.

**This does not make the mechanism wrong, and the report must not overcorrect.**
Drift is plausibly the *source* of the latency variation the test exploits, and
latency is the measured driver of the applied rate. The direction and the
mechanism can survive intact. What cannot stand is the p-value as currently
computed, because it was computed under an assumption now known to be false.

**What closing it requires — check, do not assume:**

1. Recompute conditioning on run index: either permute **within blocks** of
   adjacent runs, or include position as a covariate and test the latency
   coefficient given position.
2. Report whether kill latency still predicts the applied effect **once position
   is accounted for**. If it does, the manuscript keeps the claim with a
   corrected p-value and a sentence naming the dependence. If it does not, the
   mechanism paragraph in `06-evaluation.tex` and the corresponding passage in
   `08-threats.tex` are wrong as written and must be rewritten.
3. Re-derive every affected macro through `scripts/paper_tables.py`, since
   `\KillLatencyP{}` and its stratified siblings are generated, not typed.

**Note the asymmetry with Phase 8.4.** From session 2 onward, collection is
run-level interleaved (`experiments/run_matrix.py`, `build_plan`'s sort key), so
new data is protected against exactly this. The frozen replication set that 8.1
analysed is not, and cannot be — it is already collected. B9 is therefore a
re-analysis obligation, not a re-collection one.

---

## B10. `paper_tables.py` writes incomplete output and exits 0 when under-invoked

**Due before Phase 12.** Found in Phase 8.4 while regenerating `numbers.tex`
after a code change.

**What happens.** `scripts/paper_tables.py` takes `--analysis`,
`--fsync-analysis` and `--flakey`. Invoked with only `--analysis`, it writes a
`numbers.tex` that is **65 lines shorter**, silently missing whole macro
families — the `fsync-always` block (`\BarrierCostAlways`, `\AepAlwaysMedian`,
`\AepAlwaysPninetyfive`, `\AepThroughputAlways`, `\BthreeAlwaysMedian`,
`\AepThroughputEverysec`) and the write-loss block (`\FlakeyReplications`,
`\FlakeyN`, `\FlakeyAckSurvived`, `\FlakeyUnackLost`) — and **exits 0**. The
canonical invocation is in the `Makefile` `reproduce-figures` target; nothing
requires it.

**Severity, stated accurately rather than inflated.** This is
**late detection, not silent corruption.** The macros are cited in
`06-evaluation.tex` and `08-threats.tex`, so a truncated `numbers.tex` fails the
LaTeX build on undefined control sequences, and CI builds the paper. The
committed form would have been caught. In Phase 8.4 it was caught earlier still,
by reading the diff before staging.

**Why it is nonetheless worth fixing, and where it bites.** The dangerous shape
is regeneration **from a clean clone**, which is exactly what Phase 10 (artifact
and DOI) and Phase 14 (submission package) do. In that setting the reviewer's
reproduction path is "run the generator", and a generator that produces a
plausible-looking, quietly-smaller artifact and reports success is a bad
instrument even when a downstream gate eventually catches it. It also fails in
the direction that looks like success, which is the property audit finding S4-D
is about.

**Two acceptable fixes; the phase picks one.**

1. **Refuse to write.** If any input root is absent, exit non-zero naming the
   missing one. Simplest, and makes the failure impossible rather than detected.
2. **Carry a manifest of macro families.** The script declares which families it
   emits and which input each requires, and fails when a family that exists in
   the committed `numbers.tex` would be absent from the regenerated one. Slower
   to build, but it also catches the reverse case — a family silently *added* —
   and it degrades gracefully when a root is legitimately unavailable.

(1) is sufficient for the failure observed. (2) is worth the extra work only if
Phase 10 wants the generator to be self-checking against the committed artifact.

**Related.** `scripts/check_paper_numbers.py` did catch the mismatch between the
truncated `numbers.tex` and the CSVs, so the gate works. B10 is about the
generator, not the gate.

## B11. A gate that looks live and is not: shell conditions are never tested on their failing branch

**Filed against Phase 12.** Found by accident during Phase 8.4, while breaking
something else — which is itself the point. Nothing in the repository would have
reported this gate as broken.

**The defect.** `precondition.sh`'s fixtures-missing gate was written as:

```sh
if [ "${#MISSING[@]:-0}" -gt 0 ]; then
    echo "PRECONDITION FAILED: compose fixtures absent: ${MISSING[*]}"
    exit 2
fi
```

`${#ARRAY[@]:-0}` is not valid bash. It raises `bad substitution`, the `[` test
never runs, and **under `if` a command that fails to execute reads as *false*
rather than as an error**. The gate therefore could not have halted anything, in
either direction, and it ran in that state for a real collection. Its passing
path printed a reassuring `fixtures missing : none` throughout, because that
line uses `${MISSING[*]:-none}`, which is valid.

**Why the class matters more than the instance.** The instance is a one-line
fix. The class is *a gate that looks live and is not*, and this repository has it
three times now:

- **Audit finding S4-D** — an assumption stated and never enforced.
- **B10** — `paper_tables.py` writes incomplete output and **exits 0**, failing
  in the direction that looks like success.
- **B11** — a stop condition whose failing branch is unreachable.

All three share a shape: the passing path is exercised constantly and looks
healthy, while the failing path is never executed even once, so the gate's only
job is the only thing never tested.

**The requirement, in two parts.** Failing-branch testing is necessary and it is
not sufficient — the third instance below is not a gate at all and has no failing
branch, yet it is the same defect.

1. **Every shell gate must be tested on its failing branch**, not only its
   passing one, asserting the exit code. A gate that has never once fired has
   not been shown to work; it has been shown to be quiet.
2. **Every gate and every derived count must be validated against a case whose
   answer is already known, before it is trusted on a case whose answer is
   not.** This is the general remedy, and it is what actually caught all three
   instances. It is cheap here because known answers exist: session 1 has 0
   non-landing kills and 30/30 runs per cell, session 2 has exactly 2 at rep0
   and rep6. Any census or gate that cannot reproduce those has not earned the
   right to report a number nobody can check.

**Carry the caution from how this one was tested.** The failing branch of
`precondition.sh` was exercised by renaming the fixture so it would be classified
as foreign — against the live Docker daemon, during a collection, which stopped
the running session's Redis and destroyed it (see
`reports/phase-report-8-4-session-2-aborted-2026-08-28.md` §3a). **A destructive
gate needs a dry-run mode before its failing branch can be tested safely.** The
requirement above is not dischargeable by pointing the existing scripts at the
real daemon; Phase 12 must add the seam first.

**Scope.** `experiments/harness/*.sh`, `scripts/*.sh`, and the Phase 8 collection
driver. The Python gates (`check_paper_numbers.py`, `check_pytest_gates.py`,
`freeze_results.py`) are in scope for the same audit, but Python raises on a
malformed expression rather than silently reading false, so the specific failure
mode is shell-only; what carries over is the "never tested on its failing branch"
audit, not the substitution defect.

### B11, second instance: a watcher that always reads true

Found in Phase 8.4 one session after the first instance, and it belongs to the
same entry because it is the same defect with the sign flipped.

The session-2 watcher was:

```sh
while pgrep -f "run_session.sh b2-paired-v2-s2-2026-08-28"; do sleep 60; done
```

**The pattern is a substring of the watcher's own command line**, so `pgrep -f`
matched the watcher itself. The condition could never become false, the loop
could never exit, and the chain could never advance past a session that had in
fact finished. Two watchers were running, which made it strictly worse: each
also matched the other, so neither could terminate even if the first problem
were fixed.

**Why it is the same class as `${#ARRAY[@]:-0}`.** That expression always read
*false*; this predicate always read *true*. Both look live. Neither can ever
act. And both would have been caught by the requirement this entry already
states, because in both cases the branch that was never exercised is the one the
construct exists for — a loop's exit path is its failing branch, and a watcher
whose exit path never runs is untested in precisely the way B11 names.

Confirmed empirically rather than by reading: `pgrep -f "run_session.sh
b2-paired-v2-s3-2026-08-28"` returns a match when no such session exists,
because the `pgrep` command line contains the string it searches for.

**The rule.** Do not wait on a `pgrep` pattern that appears in the waiting
command. Wait on a child PID, on a sentinel file written only on success, or on
`pgrep` restricted to the target process (the Python process, not the wrapper).
Phase 8.4's chain runner uses the sentinel, runs each session in the foreground
and reads its exit code directly, so there is one observer and no pattern
matching at all.

**A third member of the general family, from the same session.** The first
`FaultInjectionError` census counted its own echoed output — it wrote the
matching lines into the log it then grepped, reporting 4 failures where there
were 2 — and extracted positions as `[3, 120, 26, 120]` because `grep -oE
'[0-9]+'` over `[3/120]` yields both numbers. Not a gate, so not B11 proper, but
the same root cause: a derived number that was never checked against a known
answer. It was fixed by reading `matrix-progress.jsonl` instead and validating
against session 2's known 2 and session 1's known 0. **The generalised
requirement: every derived count in the collection tooling must be validated
against a session whose answer is already known.**

## B12. Nothing samples foreign VM load *during* a session

**Filed against Phase 12, and it is the residue of the gap 9C §6 named.**

Phase 8.4 added a per-session container precondition, and it works: session 3's
precondition caught two foreign `postgres:16-alpine` containers
(`komserv-pg-race-*`) running in the Docker Desktop VM, recorded them by name,
and stopped them before collection. That is a real improvement over
`container_state` in `run-config.json`, which covers the AEP Redis container
only.

**But the precondition is a snapshot at t=0, and the load that mattered arrived
after t=0.** Session 2's own `container-precondition.json` recorded
`foreign_running_before: []`, correctly — the VM was clean when it started. The
foreign containers appeared during the session, and were only seen because
session 3's precondition ran 43 minutes after session 2 finished and caught them
still up. See
`reports/phase-report-8-4-foreign-load-during-session-2-2026-08-28.md`.

So the current instrumentation can establish "the VM was clean when this session
began" and cannot establish "the VM was clean while this session ran". For a
phase whose entire estimand turns on `docker kill` latency — a quantity on the
critical path of the VM's own scheduling — that is the wrong boundary.

**What is needed.** A sampler that records the VM's container set periodically
during collection, not only at its edges, and writes the series into the run
root. Cheap: `docker ps` at, say, 30 s intervals, appended to a JSONL beside
`matrix-progress.jsonl`. That makes foreign load a per-run covariate rather than
a per-session precondition, and it is the only way a later reader can ask
whether a specific anomalous run coincided with competing load.

**Why it is worth doing rather than noting.** Three surfaces of host degradation
now have no run-level explanatory variable: the drift whose sign reverses
between sessions, the kill-latency envelope, and — new in session 2 — kills that
do not land at all. Each is currently attributable only to "the host", which is
not falsifiable. A sampled container series would make at least the competing-load
hypothesis testable rather than merely plausible.

**Ephemerality makes it urgent.** Both foreign containers observed in Phase 8.4
were **removed within four minutes** of being stopped; `docker inspect` returned
`no such object`. Evidence about VM load does not persist. If it is not sampled
while it exists, it is not recoverable afterwards — which is exactly what
happened to session 2's exact start times.

**Fourth instance, recorded because it happened while writing the fix.** Testing
the load sampler, `pkill -f "load_sampler.sh /tmp/ls2"` killed the operator's own
shell — the pattern was a substring of that shell's command line. Same defect,
same session, third distinct victim. The pattern-matching family of process
control is not safely usable in this codebase; use PIDs.

### 12a. Nothing detects or records a gap *inside* the sampled series either

**Added 2026-08-31, when the sampler was stopped.** The same boundary problem as
B12 itself, one level in: the precondition cannot see load arriving after t=0,
and the sampler cannot see its own absence.

Stopping `load_sampler.sh` produced a before/after snapshot of its JSONL, and the
series turns out **not** to be continuous. Across
`2026-08-28T16:55:15` – `2026-08-31T12:10:52`, 1414 samples, there are two
multi-hour holes:

| gap | from | to |
|---|---|---|
| **36 h** | 2026-08-29T22:12:29 | 2026-08-31T10:10:44 |
| **7.6 h** | 2026-08-29T12:38:16 | 2026-08-29T20:15:19 |

The cause is WSL VM suspension — a `while true` loop with a `sleep` cannot skip
36 hours while running. On resume it continues against a clock that has jumped.

**Nothing anywhere records this.** `slice_load.py` counts the samples falling
inside a window and emits `samples` plus a `coverage_note`, but that note
describes only the gap *before* sampling began. A window containing a suspension
would report a lower sample count and say nothing about why — and a sparse or
empty `foreign_running_seen` would then read as "the VM was quiet" when the only
supportable reading is **"the VM was not observed"**. That is the exact inversion
`interpretation_limit` exists to prevent, defeated by a mechanism it does not
model.

This is **R5** satisfied for the leading gap and unsatisfied for interior ones,
and it is the same shape as **B13b**: an artefact that does not declare the
boundary of what it actually covers.

**Sessions 3 and 4 are unaffected, checked rather than assumed.** Both windows
fall on 28 August, roughly seventeen hours before the earlier gap begins. Outside
the two gaps above, the largest interval between consecutive samples anywhere in
the file is **73 s**, and that one occurs on 31 August. Sampling inside both
windows is regular at its 60 s interval: 72 samples for session 3, 76 for
session 4. **No suspension occurred during any collection window.**

**Needed, and cheap:** the slicer already holds every sample's timestamp, so it
can report the largest interior gap in the window beside the sample count, and
say so explicitly whenever that gap exceeds the sampling interval. Pairs with
B13c — the interval must be read from the sampler rather than hardcoded, or the
comparison that decides "is this a gap?" uses the wrong threshold.

**A methodological note that generalises past this item.** `ps` reported the
sampler as `STARTED 30 Aug 12:20` with `ELAPSED 23:50:39`, which would suggest it
was not the process launched on 28 August. It was: the PID never changed and the
JSONL's first record is `16:55:15` on 28 August, seconds after the recorded
launch. Elapsed and start time derive from boot time, and **boot time is not
stable across VM suspension on this host**. In a suspendable VM an append-only
file is a more reliable account of a process's history than the process table is.
Anywhere the collection tooling reads a duration or an age from a boot-derived
clock, that reading is suspect on this host and must be checked rather than
assumed sound. That check was carried out — see **B17**.

See `reports/phase-report-8-4-sampler-stopped-2026-08-31.md`.

## B13. `slice_load.py` writes into frozen roots, and its output depends on when it ran

**Filed against Phase 12. Three defects in one 137-line script, found together.**

**13a is an instance of B16, not the whole of it.** Two other writes landed
inside frozen roots in the same phase from unrelated causes — a deliberate
repair and a stale-cwd `mkdir` — and neither involves this script. Fixing
`slice_load.py` does not fix the class. 13b and 13c are defects in this script
alone and belong here rather than under B16.

### 13a. It writes into a frozen root with no guard

`slice_load.py:123-127` writes `foreign-load-sample.json` to both the run root
and `analysis/`, checking only that the parent directory exists. It does not look
for `SHA256SUMS`, and it does not care that the file it is about to overwrite is
already named there.

Re-running it on sessions 3 and 4 after they were frozen broke both freezes:
`sha256sum -c` went from 18 OK / 0 FAILED to **17 OK / 1 FAILED** in each. The
artefact was recovered by reproducing the original input rather than by
re-freezing, so no digest was rewritten — but recovery worked only because the
sampler's JSONL is append-only and had not rotated. Had it rotated, a hashed
artefact would have been permanently unrecoverable, and the only remaining option
would have been to re-freeze, which destroys the property that the digests were
produced at collection time.

**Needed:** refuse to write when `SHA256SUMS` exists in the target root and
already names the target path, and a `--dry-run` seam so the refusal branch can
be tested without a live frozen root (**R4**).

### 13b. With no `complete at` line, the slice is unbounded and its contents depend on when it ran

`slice_load.py:80`:

```python
if t1 and t > t1:
    continue
```

When `t1` is `None` there is **no upper bound at all**. The loop keeps every
sample from `t0` to end-of-file. So an unbounded slice's contents are set by the
wall-clock moment the script executed, not by the session's boundary — and the
artefact does not say so. `window_end` is serialised as `null` and no field
distinguishes "the session ended here" from "we stopped reading here".

This is the normal path, not an edge case. `finish_session.sh` runs the slice
*during* the freeze, before the session log has been written its final
`complete at` line, so `t1` is `None` every time. Both frozen artefacts carry
`"window_end": null`. They are left that way deliberately: that is what the
freeze attests, and bounding them now would be editing evidence to make it tidier.

**It was harmless only by timing.** Session 3's last sample is at `18:07:09` and
the sampler's default interval is 60 s (`load_sampler.sh:33`), so
`finish_session.sh` had about sixty seconds to compute the slice before the next
sample landed. Session 4 started at `18:07:19` — **four seconds** after session 3
completed. Had the chain been a minute slower, session 3's foreign-load record
would have silently absorbed session 4's window, and nothing anywhere would have
flagged it: no gate reads this file, the record count would still have looked
plausible, and `sha256sum -c` would have passed on whatever was written.

**Needed:** bound the slice explicitly at compute time when the log gives no end,
and record in the artefact which bound was used and why.

### 13c. The interval is hardcoded and can disagree with the sampler

`slice_load.py:98` emits `"interval_seconds": 60` as a literal. The sampler takes
the interval as a positional argument — `load_sampler.sh:33`,
`INTERVAL="${2:-60}"` — so 60 is only a default. A sampler started at any other
interval produces an artefact that misreports its own resolution.

That number is not decorative. The artefact's `interpretation_limit` field uses
it to state how long a container must live to be visible, which is the entire
basis for reading an empty `foreign_running_seen` as weak evidence rather than
proof. A wrong interval makes that bound wrong in an unfalsifiable direction.

**Needed:** the sampler records its interval in the JSONL header or in each
record, and the slicer reads it rather than asserting it.

## B14. `finish_session.sh` counts its own output, and it is the second file to do so

**Filed against Phase 12. The mechanism is already recorded once; this is the
point of the entry.**

`finish_session.sh`'s inline fault count greps the session log for `FAILED` and
then echoes the matching lines back into that same log through `tee`. Every
later invocation therefore counts its own prior output. Session 2's log read
**4** when it was first run and **8** when read again later. The true value is
**2**, at repetitions 0 and 6.

`fault_census.py` is correct: it reads `matrix-progress.jsonl`, the harness's
structured record, and was validated against session 1's known 0 and session 2's
known 2 before being trusted. Every fault figure in the Phase 8.4 reporting comes
from it, not from the shell count.

**This is the identical mechanism to the census defect already recorded under
B11 — a derived count that reads its own echoed output — now in a second file.**
The first instance also parsed `[3/120]` as two separate numbers and reported
failures at positions `[3, 120, 26, 120]`. Fixing one file did not fix the class,
because the class is *deriving a count by grepping a stream the deriving process
also writes to*. Both instances were caught only by **R2**: validating against a
session whose answer was already known. Neither has a failing branch, so **R3**
could not have caught either.

**Needed:** no count in the collection tooling is derived from a log that the
counting process writes to. `matrix-progress.jsonl` is append-only and structured
and is the answer in both cases. The shell count should be deleted rather than
repaired, because a correct grep over a self-appended log is still one `tee` away
from being wrong again.

## B15. `SHA256SUMS` attests 1% of a root, and the gate record is in the other 99%

**Filed against Phase 12. Confirmed from source and across all 11 result roots on
the collection host.**

`scripts/freeze_results.py:175-177`:

```python
digested = [manifest_path, csv_path]
if analysis.is_dir():
    digested += sorted(p for p in analysis.glob("*") if p.is_file())
```

`analysis.glob("*")` is non-recursive and file-filtered. The digest set is
`MANIFEST.md`, `MANIFEST.csv` and `analysis/*` — and nothing else. No run
directory, no ledger, no log, no top-level file. Every root on the host holds
15–18 entries with **0 sqlite entries and 0 run-directory entries**, including
`matrix`, the frozen 432-run tree the manuscript rests on.

**Derived for sessions 3 and 4, which are typical:**

| | count |
|---|---|
| entries in `SHA256SUMS` | 18 |
| files anywhere in the root | **1827** |
| **attested fraction** | **1.0%** |
| run directories, wholly unattested | 120 |
| `ground_truth.sqlite3` / `-wal` / `-shm`, wholly unattested | 120 / 120 / 120 |

### The part that is worse than "the raw evidence is unattested"

Five files sit at each root's **top level**, outside `analysis/` and therefore
outside the digest entirely:

`cell-census-bundle.json`, `gates.json`, `matrix-plan.json`, `matrix-plan.txt`,
**`matrix-progress.jsonl`**.

Two of those decide whether a session is admissible at all:

- **`gates.json`** holds the HALT gate outputs — undetected duplicates, lost
  effects, the `executions ≠ runs × 1` resume double-count signature, duplicate
  `(system, response_class)`, canary survival.
- **`matrix-progress.jsonl`** is the authoritative source for the fault census
  (**R2**, and B14 above), which is what amendment 4's exclusion criterion and
  its ceiling of 3 are evaluated against.

**So the two files that determine admissibility are outside the digest.** Anyone
could alter either one after the freeze — flip a HALT result, remove a
`FaultInjectionError` record so a session no longer approaches the ceiling — and
`sha256sum -c` would still report every entry OK. The check that a reader runs to
establish that a session was not tampered with does not cover the records that
say whether the session passed.

Stated at its true strength: there is no evidence anything was altered, and
nothing here suggests it was. The defect is that the verification offers no way
to rule it out while appearing to.

### Not an overclaim about the documentation

`ARTIFACT.md:248-254` is already honest about scope. It says `SHA256SUMS`
"currently digests the manifest and every listed matrix output — 17 files", that
"from a clone, only the tracked subset can be checked", and that the external
archive's manifest "must cover every raw directory, `results/voided/`, and all
derived products". None of that is wrong, and this entry does not claim
otherwise.

**The gap is between that paragraph and what a reader does.** B5 calls
`SHA256SUMS` "the artifact's integrity mechanism". The command in the repository
is `sha256sum -c SHA256SUMS`, it exits 0, and nothing in its output states what
it did not check. The honesty lives in a document; the misleading pass lives in
the tool. Additionally, nothing produces or enforces the complete manifest
`ARTIFACT.md` requires — there is no archive script anywhere in `scripts/`, and
`Makefile:38`'s `ARCHIVE ?=` is an input path, not a build target.

**Needed, in order of cost:** a refusal banner in `SHA256SUMS` itself naming what
it does not cover; then a `SHA256SUMS.evidence`-style manifest over run
directories and top-level files, produced at freeze time by the same script. The
off-host archive written for sessions 3 and 4 in Phase 8.4 demonstrates the
latter is cheap — a full 1827-entry manifest per root, ledger triples intact and
no WAL checkpointed, took seconds.

### The raw trees are not consistent across copies, and nothing detects a partial

Because `SHA256SUMS` names **zero** run directories, a copy holding a *subset* of
a root's runs verifies exactly as well as a complete one. There is no entry for
the missing runs to fail against. This is not hypothetical — the copies already
disagree.

**`matrix` exists twice on this machine, at two different sizes:**

| copy | run directories | ledgers |
|---|---|---|
| `/root/aep/experiments/results/matrix` | **432** | 432 |
| `Research-paper-AEP/experiments/results/matrix` | **84** | 84 |

The second is a **19.4% snapshot** taken from this project, sitting untracked on
disk in the working clone. `git status` does not show it and `git ls-files`
returns 8 tracked paths for that root, none of them a run directory — so it is
invisible to git and unattested by the manifest, while occupying the exact path a
reader or a script would look in.

**And the split runs both ways**, so neither tree is "the complete one":

| root | in `/root/aep-phase8` | in the working clone |
|---|---|---|
| `b2-2026-08-21` | 0 runs | **60** |
| `b2-s1/s2/s3-2026-08-21` | 0 runs each | **60 each** |
| Phase 8.4 `s1`–`s4` | **120 each** | 0 runs each |

The 21 August roots' raw runs are on the Windows side only; Phase 8.4's are on
the WSL side only; `matrix` is complete in a third location. **No single tree on
this machine holds all of the project's raw evidence.**

**Independent confirmation of survey (a) on the 84.** They were surveyed
separately, by the same read-only method: **84 of 84 are exactly 4096-byte bare
pages** — the 0.34 MB aggregate is 84 × 4096 exactly — and **84 of 84 have a
non-empty `-wal`**, totalling 41.82 MB. Sampled runs show 4,096 B of database
against 74,192 B of WAL; WAL sizes vary by run and reach the hundreds of
kilobytes. Across the working clone's 331 ledgers: 331 bare, 331 non-empty WALs,
1.36 MB of database against 66.84 MB of WAL. 662 `-wal`/`-shm` files stamped
before and after, **0 changed**.

**The consequence for Phase 10 is the one that matters.** Whoever assembles the
archive must choose a copy, and **nothing in the repository tells them which is
complete or checks the choice afterwards**. Building from the working clone would
publish **84 of 432 runs, 19.4%**, under a DOI — and `sha256sum -c` would return
exit 0 on that archive, because the manifest names 17 derived files and no runs
at all. A silently truncated archive is indistinguishable from a complete one by
every check the project currently has.

This is the same defect as the rest of B15 — the digest's scope does not reach
the evidence — but it is the form with the worst outcome, because the failure is
not a corrupted file that fails a check. It is a *missing 80%* that passes one.

### B15a. Three artefacts exist twice, hashed in one place and not the other

Recorded inside B15 rather than as its own item, because it is the same defect —
a scope boundary that does not follow the content — in its sharpest form, and
because fixing B15 without fixing this would make it worse: an evidence manifest
would then attest *both* copies with no rule saying which one wins.

`container-precondition.json`, `fault-injection-census.json` and
`foreign-load-sample.json` each exist at both the root and under `analysis/`.
`slice_load.py:123-127` writes both copies; the census and precondition writers
do the same.

**The `analysis/` copy is authoritative.** It is the one `SHA256SUMS` names, the
one `publish_from_sums.sh` copies into the tracked clone, the one committed, and
the only one a reader outside the collection host will ever see. The top-level
copy is a convenience for operators on the host.

**Nothing checks that they agree, and they can diverge silently.** Any tool that
writes only one copy — or writes both and fails between them — leaves two
different answers to the same question inside one frozen root, with the
unattested one sitting at the more obvious path. A reader on the collection host
who opens the root-level file gets an answer that `sha256sum -c` never checked
and that no policy declares subordinate.

**Needed:** write one copy, under `analysis/`, and if the top-level convenience
copy is kept, make it a symlink or have the freeze assert the two are identical
before hashing.

## B16. A frozen root is an ordinary writable directory: the freeze produces a digest and no enforcement

**Filed against Phase 12. This is the parent item; B13a is one instance of it.**

The later number is not a mistake and the item is not renumbered — B13, B14 and
B15 are already cited by commit messages and by
`reports/phase-report-8-4-stray-writes-into-a-frozen-root-2026-08-31.md`, and
renumbering would break those citations to make an ordering look tidier.

### The claim

**Freezing a results root produces a manifest of digests and nothing else.**
`freeze_results.py` writes `SHA256SUMS` and exits. It sets no permissions, takes
no lock, leaves no marker any tool consults, and installs nothing that could
refuse a later write. Afterwards the root is an ordinary directory with ordinary
write permissions, and every process on the host may modify it freely.

So there is **no prevention**. And there is **no detection either**, in the sense
that matters: `sha256sum -c` does not run by itself. It reports a modification
only if a person remembers to invoke it, on the right root, before drawing a
conclusion from that root.

### Three writes landed inside frozen roots in Phase 8.4, from three unrelated causes

| # | write | cause | class |
|---|---|---|---|
| 1 | `slice_load.py` overwrote `analysis/foreign-load-sample.json` in s3 and s4 | a tool run post-freeze with no guard (**B13a**) | automated |
| 2 | the recovered artefact was copied back into both roots | a deliberate repair, digest verified against the recorded entry first | intentional |
| 3 | `.ai/` and `phase8-driver/` were created inside s3's root | a relative `mkdir` and a hook write, both resolved against a stale shell cwd | accidental |

**The common factor is not `slice_load.py`.** One was a script, one was a
considered human action, one was an accident of shell state. No guard that
addresses any single cause addresses the other two. What they share is only that
the target was writable and nothing objected.

That is why this is the parent and B13a is the instance: fixing `slice_load.py`
to refuse post-freeze writes removes cause 1 and leaves 2 and 3 untouched.

### The sharper half: additions are invisible, not merely unreported

Instance 3 is worse than instances 1 and 2, and in a way that is easy to miss.

`sha256sum -c` iterates the entries a manifest names. A file the manifest does
**not** name has no entry, so there is nothing to check and nothing to fail. The
root held three files that did not exist at freeze time and reported
**18 OK / 0 FAILED** throughout.

**A passing `sha256sum -c` is not a statement that a root is unchanged. It is a
statement that the named files are unchanged.** For modifications the check is
sound but manual; for additions it is structurally blind. Since B15 establishes
that the digest names 1.0% of a real root, the blind region is essentially the
whole root.

### What is needed

In increasing order of cost, and the first is nearly free:

1. **Make the freeze checkable for additions.** Record the complete file *set* at
   freeze time, not only digests of a subset, so a verifier can report "3 files
   present that were not here at freeze" as well as "0 digests failed". This
   closes the structural blindness without changing any permission.
2. **Leave a marker the tooling consults.** A `FROZEN` sentinel in the root that
   every collection script checks and refuses to write past, with a `--dry-run`
   seam so the refusal branch is testable (**R4**) and a documented override for
   verified repairs like instance 2 — which should be *recorded*, not prevented.
3. **Make the root read-only after freezing.** Effective against instance 3 and
   against careless tools, and the only one of the three that acts rather than
   reports. It complicates legitimate repair, which is why it is listed last
   rather than first.

**Do not read this as an integrity claim about Phase 8.** All four sessions
verify 18 OK / 0 FAILED, the one broken artefact was recovered by reproducing
bytes that hash to the recorded digest, and the strays were enumerated and
removed. Nothing was silently altered. The defect is that none of that was
guaranteed by the freeze — it was established afterwards, by hand, because
someone went looking.

## B17. Amendment 4's exclusion criterion compares a wall-clock uptime against a suspension-blind threshold

**Filed against Phase 12. A finding against amendment 4, recorded in the backlog
because the amendment is closed and is not being reopened.**

Prompted by B12a: `ps` misreported the sampler's own age because boot-derived
clocks are not stable across VM suspension on this host. Amendment 4's exclusion
criterion is the Redis server's uptime, so it was checked rather than assumed
sound.

### What the criterion actually is

`experiments/harness/faults.py:207` reads the figure from the server itself:

```python
uptime = int(server.get("uptime_in_seconds", 10**9))
```

`faults.py:221` decides with it:

```python
was_killed=uptime <= max(30, int(time.monotonic() - started) + 10),
```

and `faults.py:231-236` raises `FaultInjectionError` when `was_killed` is false.

**Two different clocks meet on line 221.**

| term | clock | advances while the VM is suspended? |
|---|---|---|
| `uptime` | Redis's own, via `INFO server` | **yes** (see caveat below) |
| `time.monotonic() - started` | Python's `CLOCK_MONOTONIC` | **no** — by definition |

`CLOCK_MONOTONIC` on Linux excludes time the system was suspended;
`CLOCK_BOOTTIME` is the variant that includes it. So the **threshold** is
suspension-blind while the **quantity being thresholded** is not.

**Caveat, stated because it is not verifiable from this repository.** Redis's
source is not vendored here — `redis/` holds only `phase2.conf`,
`phase2-always.conf` and `toxiproxy.json`. Standard Redis derives
`uptime_in_seconds` from its start timestamp against current time, both
wall-clock, which would include suspended time. That is the assumption above and
it should be confirmed against Redis's source before any fix is designed.

### The failure mode, and its direction — spurious EXCLUSIONS

The direction matters more than the mechanism, because it determines which of
amendment 4's two provisions is exposed.

**The chain, stated explicitly.** Suppose the VM suspends between `started`
(`faults.py:197`) and the `INFO` read (`faults.py:206`) — a window of roughly one
to two seconds.

1. Suspension **advances the wall clock**, so Redis's `uptime_in_seconds`
   **inflates** by the whole duration of the suspension.
2. Suspension **does not advance `CLOCK_MONOTONIC`**, so
   `int(time.monotonic() - started) + 10` does not move. The threshold stays
   **static** at its floor of 30.
3. An inflated uptime against a static threshold makes `uptime <= max(30, ...)`
   false, so **`was_killed` evaluates `False`**.
4. `faults.py:231-236` therefore raises `FaultInjectionError: the hard kill did
   not land` — **on a run whose kill did land.**

**A landed kill is recorded as a non-landing one. The risk is spurious
EXCLUSIONS, not spurious inclusions.**

**And it lands directly on amendment 4's ceiling.** The registered rule is that
more than 3 non-landing kills in a session marks a sick instrument. Every
spurious exclusion consumes one of those three. A single suspension striking
that one-to-two-second window in four separate runs would trip the ceiling and
condemn a session whose instrument was working perfectly — and the session would
be reported as degraded on the strength of a clock artefact, with the refills
themselves also being unnecessary.

**It could have tripped the ceiling falsely. It did not.** The sampler's gaps —
the only suspensions on record — are **29–31 August**, and **both session
windows are 28 August**. No collection window contains a suspension, so no
exclusion in Phase 8.4 can have arisen this way. See the check below.

**Exposure is bounded by the `max(30, ...)` floor.** A restart takes one to two
seconds, so the monotonic term is dominated by the constant 30 in normal
operation and only matters if a restart exceeds twenty seconds. The defect is
real; it is not on a hot path.

### It did not fire in Phase 8.4, and this is checkable rather than assumed

1. **The two observed incidents are not clock artefacts.** Both non-landing kills
   in session 2 reported `uptime_in_seconds` of **42** and **37**. A suspension
   artefact would report hours, not tens of seconds. These are genuine
   same-process detections, exactly as amendment 4 intends.
2. **No suspension occurred during any collection window.** The load sampler's
   two multi-hour gaps (B12a) fall on 29–31 August; every session window is on
   28 August. Both Phase 8.4 session windows sample regularly at 60 s throughout.

**So no Phase 8.4 exclusion decision is affected, and none of the four sessions'
numbers change.**

### Adjacent, and it closes rather than opens a question

The estimand's covariate is measured with the same family of clock —
`redis_kill.py:298` and `:305` compute
`issue_to_return_ns = time.monotonic_ns() - armed_at`.

**This one is correct, and deliberately so.** For timing a short interval,
`CLOCK_MONOTONIC` is the right instrument precisely because it is immune to
wall-clock adjustments such as NTP steps, which would otherwise corrupt a
sub-second measurement. Suspension would cause an under-count, and no suspension
occurred during collection. **The covariate is sound; recorded here so the
question is not reopened later.**

### What is needed

Compare like with like: threshold the Redis-reported uptime against a wall-clock
elapsed measurement, or read `CLOCK_BOOTTIME` rather than `CLOCK_MONOTONIC` for
this one comparison, and confirm Redis's own derivation against its source
first. **Do not amend amendment 4** — it is closed, its criterion was applied
correctly to the data that exists, and this is a defect in the implementation of
the check rather than in the registered rule.

## B18. Shell substitution silently rewrote the tooling's own inputs, including a commit message

**Filed against Phase 12. B11's class, in the layer that records what was done.**

B11 is "a gate that looks live and cannot act". This is its sibling: **a command
that looks like it ran and did something else**. Both were found the same way —
by checking output against a known answer (**R2**) rather than by any exit code,
because in every instance below the exit code was **0**.

### First, a correction to how this was reported

An earlier account of this said inline commit messages were eaten "twice, and the
first was silent". Both halves were wrong, and checking rather than recalling is
what established it. Every commit message from this session was re-read:

- **Commit-message corruption happened exactly once**, in the commit that became
  `1fe3f72`. The other three inline commits contain **zero** backticks and are
  intact.
- **That one was not silent.** `bash` printed `command substitution: line 1:
  syntax error` to stderr. What it did do is exit **0**, create the commit, and
  report success — so the error was *visible but non-fatal*, which is a different
  and more dangerous thing than silent.

The genuinely silent instances were elsewhere, and there were more of them.

### What happened

Two distinct substrates, one mechanism.

**1. The commit message.** `git commit -m "…"` with a message containing
backticked code — `` `if analysis.is_dir():` `` — had those spans executed as
command substitutions by the invoking shell. Their output, empty, replaced the
code in the message. The committed text read *"Line 176 is the  in the middle of
the quote, not the  at its head"*: a sentence whose subject and object had been
deleted, in a commit whose entire purpose was to correct a wrong citation.
Amended from a file.

**2. Command arguments through `wsl … bash -c '…'`.** Repeatedly, `$VAR`
references inside the quoted script were expanded by the *outer* shell before
reaching the guest, arriving empty. These were the silent ones, and one produced
data rather than an error:

| attempt | what it printed | why it was wrong |
|---|---|---|
| per-root file counts | four roots each reporting **8165 files, 902 subdirectories, 18 run dirs** | `$r` was empty, so every iteration measured the *parent* directory. Four identical rows of a real number for the wrong object. |
| directories lacking a ledger | ~330 lines of `NO LEDGER:` with an empty name | `${d%/}` expanded to nothing; every directory "failed" |

**The first of those is the dangerous one.** It is not a crash and not an obvious
mangling — it is a plausible table of plausible numbers, and 8165 *is* the true
file count of something. Had it not been checked against an independent
measurement, it would have entered a report as four roots' contents.

### Why this belongs in the backlog rather than in a habit

The failure is structural, not careless. **Every layer between the intent and the
execution is a shell**, and each strips one level of quoting: Git Bash on
Windows, then `wsl.exe`'s argument marshalling, then the guest's `bash -c`, then
in some cases a `python3 -c` inside that. Backticks, `$`, `!` and `{}` are all
active in at least one of them. Writing a correct multi-level escape is possible
and is not reliably repeatable, which is exactly the property that makes a
convention fail under time pressure.

It also compounds R1: `pkill -f` was unsafe because a *pattern* matched more than
intended; this is unsafe because a *quoted string* means less than intended.
Both are cases of the shell reinterpreting something the author treated as inert
data.

### Mitigation, already adopted

1. **Never pass a commit message inline.** Write it to a file and use
   `git commit -F <file>`, or a quoted heredoc (`<<'MSG'`), which disables
   substitution. Every commit after `1fe3f72` in this session used one of these.
2. **Never pass a multi-line or variable-bearing script through `bash -c`.**
   Write the script to a file and invoke the file with arguments. Every survey in
   this task was rewritten this way after the second failure, and none failed
   afterwards.
3. **A script that reports per-item results must print the item's identity from
   inside the loop**, so an empty variable is visible as an empty label rather
   than as a plausible repeated row. The `8165` table would have been obvious
   immediately under this rule.

### What is needed beyond the habit

The mitigations are conventions, and **R3's lesson is that a convention nobody
can fail is better than one nobody should fail**. Worth having: a small wrapper
for host-to-guest invocation that takes a script path and an argument list and
makes the inline form unavailable, so the unsafe construction cannot be reached
rather than merely being discouraged.

## B19. The §3.2 half-width column assumed zero between-session variance, and said so nowhere

**Filed against Phase 12. Same class as Amendment 3's 0.02 threshold: a number
that governed a design decision, with no derivation on the record.**

### What the number did

`reports/plan-phase-8-b2.md` §6 tabulates a "§3.2 half-width (pp)" for k = 2…6
and argues the phase's sample size from it:

> **k = 4 is also the point where the two analyses become commensurable** —
> 3.1's MDE (17.3 pp) and 3.2's half-width (19.6 pp) agree, so the robustness
> check can actually corroborate the primary. At k = 3 they diverge badly
> (20.0 vs 30.6), which would make 3.2 decorative.

**That column selected k = 4.** The MDE column beside it has a full derivation, a
stated baseline (`p₀ = 53/150`), and a six-point sensitivity table across AUTH's
plausible range. The half-width column has **no derivation anywhere in the
document** — it appears in the table and in the sentence above, and nowhere else.

### What it actually was, recovered by reproduction

A session-as-unit half-width is `t(k−1)·sd/√k`, so the column implies an assumed
sd. Taking the **binomial sampling sd of a single session's paired difference**,
with the two arms treated as independent:

`sd = 100·√(2·p₀·(1−p₀)/30) = 12.342 pp` where `p₀ = 53/150`

| k | t(k−1) | reproduced | plan | difference |
|---|---|---|---|---|
| 2 | 12.706 | 110.89 | 110.8 | +0.09 |
| 3 | 4.303 | 30.66 | 30.6 | +0.06 |
| 4 | 3.182 | 19.64 | **19.6** | +0.04 |
| 5 | 2.776 | 15.32 | 15.3 | +0.02 |
| 6 | 2.571 | 12.95 | 12.9 | +0.05 |

**All five rows reproduce to within 0.1 pp.** Five independent matches identify
the assumption uniquely; it is not a coincidence of rounding.

**It was not taken from Phase 8.1's replication set.** That set's per-session
prevented counts are 8, 16, 21, 24 with sd 6.99 counts — a different quantity,
and one that would have given a different column.

### The assumption it embeds, which is the actual defect

**A binomial sd for a session-level contrast contains no between-session variance
component at all.** The column therefore assumed the four sessions would differ
from one another only by binomial sampling noise — that they are exchangeable
draws with no session-level variance.

**That contradicts the design's own premise.** The phase blocks on session
*because sessions differ*; §3.2 uses session as the unit and forbids the pooled
Wilson interval *because* pooling understates the spread; and plan §3.4 registers
per-session reporting because sessions are expected to disagree.

**Where the reasoning slipped.** The plan justifies the *MDE* column explicitly:

> the design blocks on session and adjusts for kill latency, which is what
> brings the residual variance back to roughly binomial — 9C measured
> over-dispersion **5.37** for unblocked pooling, so the binomial calculation
> below is valid only because of the blocking.

That justification is sound **for the quantity it was written about**. Blocking
cleans the *within-session* contrast. It cannot make the *between-session spread
of those contrasts* binomial — that spread is what blocking exists to
acknowledge. **The justification was carried across to a column it does not
cover**, and because the column had no derivation of its own, nothing marked the
transfer.

### What actually happened

| | |
|---|---|
| assumed sd | 12.342 pp |
| **observed sd across the four sessions** | **21.322 pp** |
| ratio | 1.728 |
| **implied over-dispersion** | **2.99** |

9C measured over-dispersion **5.37** unblocked. The blocking moved it from 5.37
to about **3.0** — it worked, and it did not reach the **1.0** the half-width
column assumed. **The design's own instrument for reducing over-dispersion was
credited with removing it entirely.**

### The benchmark is contaminated the same way, so the "agreement" was one omission counted twice

**The MDE column has the identical defect**, which changes how the whole thing
must be stated.

Plan §6 line 385: *"Baseline `p₀ = 53/150 = 0.3533` … **Per-arm n = 30k**. MDE at
80% power, α = 0.05 two-sided"*. Pooled binomial across **all k sessions**, with
no between-session component either. Reproduced with
`100·(z₀.₉₇₅ + z₀.₈₀)·√(2p₀(1−p₀)/30k)`:

| k | n/arm | reproduced | plan | difference |
|---|---|---|---|---|
| 2 | 60 | 24.45 | 24.4 | +0.05 |
| 3 | 90 | 19.96 | 20.0 | −0.04 |
| 4 | 120 | **17.29** | **17.3** | −0.01 |
| 5 | 150 | 15.46 | 15.5 | −0.04 |
| 6 | 180 | 14.12 | 14.1 | +0.02 |

**5 of 5 rows.** So the commensurability argument — *"3.1's MDE (17.3 pp) and
3.2's half-width (19.6 pp) agree, so the robustness check can actually
corroborate the primary"* — has the missing assumption on **both sides**. The two
numbers did not meet because two independent calculations converged. **They met
because they omitted the same thing.**

**And the MDE rests on precisely the pooling this project refuses for its own
inference.** `scripts/paper_tables.py:1894-1897`, in the code that produces
`[6.1, 28.4]`:

> Session as the unit, not the execution. **Pooling the 120 executions would
> treat them as independent draws when they share a session's host-timing
> state**; session 3B's no-pooling rule and the run-cluster bootstrap used
> elsewhere in this file are the same argument.

Pooling 30k runs per arm across sessions is that operation exactly. The
registered power calculation is built on an assumption the project rejects, in
writing, in the generator that produces the manuscript's own interval.

**Therefore the precision miss must not be stated as "the phase missed its
registered 17.3 pp".** That framing treats the benchmark as sound. The accurate
statement is:

> **Between-session variance was absent from both sides of the design's power
> argument.** The MDE and the half-width it was matched against were computed as
> though sessions differ only by binomial noise, and the phase then observed
> sessions that do not.

### The sensitivity analysis could not have detected the error it existed to catch

**This is the transferable lesson, and it is a bigger finding than the number.**

Plan §6 lines 409–416 tests robustness — but varies **`p₀` only**:

| AUTH applied fraction | 0.05 | 0.10 | 0.20 | 0.358 | 0.50 | 0.65 |
|---|---|---|---|---|---|---|
| MDE (pp) | 13.4 | 14.4 | 15.9 | **17.3** | 17.7 | 17.3 |

and concludes:

> The MDE is bounded in [13.4, 17.7] pp across the entire plausible range, so the
> design's power does not depend on guessing AUTH's rate correctly. **This is the
> one input that could have invalidated the calculation, and it does not.**

**The variance assumption is held fixed across every column of that table.** The
sweep varies the parameter the design was *not* sensitive to and never touches
the one that broke it. The closing sentence — "this is the one input that could
have invalidated the calculation" — is asserted, and it is wrong: the input that
invalidated the calculation was the one not varied.

**So the design was robust to the parameter that did not matter, and the
robustness check is why nobody looked further.** A sensitivity analysis that
sweeps the wrong axis is worse than none, because it converts an unexamined
assumption into a checked one.

**This is the class recorded four times in handover finding 5 and generalised in
R2 — a check that looks live and structurally cannot detect what it names — now
appearing in the *design* rather than in a script.** B11 and R3 cover gates in
code. Nothing in the project covers a *power calculation* whose sensitivity sweep
omits its own dominant term.

### Consequence, and what it does not license

The realised §3.2 half-width is **33.9 pp against 19.6 projected**. The
commensurability argument that selected k = 4 does not survive: at the realised
spread, k = 4 delivers worse precision than the plan's own k = 3 row, which it
called "decorative".

**This does not reopen the verdict and must not be used to.** k = 4 is committed,
the plan states "if realised precision is worse, it is reported worse", and
extending k after seeing results is optional stopping. The registered rule was
applied exactly as written.

### What k the realised spread implies — descriptive, post hoc, not a power claim

**This is not a target the phase should have hit.** The between-session sd was
not knowable before collection; the phase existed partly to measure it. It is
recorded because a reviewer will ask it immediately and because Phase 12 planning
needs a figure grounded in observation rather than in binomial noise.

At the **realised** sd of 21.32 pp, half-width `t(k−1)·sd/√k`:

| k | half-width (pp) | ≤ 17.3? |
|---|---|---|
| 4 | **33.92** | no |
| 5 | 26.47 | no |
| 6 | 22.38 | no |
| 7 | 19.72 | no |
| 8 | 17.83 | no |
| **9** | **16.39** | **YES** |
| 10 | 15.25 | YES |
| 12 | 13.55 | YES |

**Reaching a 17.3 pp half-width at the observed spread needs k ≈ 9** — roughly
11 hours of collection at the phase's measured 35.7 s/run, against the 4.8 h
budgeted.

Stated as arithmetic on an observed quantity. It does not license reopening k = 4,
which is committed and closed.

### What is needed

1. **Any future k derivation must state the assumed between-session variance
   component explicitly, and cite where it came from.** A projection built on a
   within-session or pooled sd is a projection that assumes the answer.
2. **A sensitivity analysis must sweep the variance assumption, not only the
   rate.** §6's sweep varied `p₀` across its whole plausible range and never
   moved the term that dominated. Sweeping the wrong axis converted an unexamined
   assumption into an apparently checked one.
3. **Use the realised figure.** The four v2 sessions give an observed
   between-session sd of 21.3 pp on this contrast, and an over-dispersion of 2.99
   against binomial *after* blocking. Any successor design should plan against
   those, not against 1.0.
4. **Audit every other power or precision number in the phase set the same way.**
   This one was found by reproducing a table row by row. Nothing systematic
   checks that a tabulated projection has a derivation attached, and both columns
   here did not.
5. **Extend R2's rule from derived counts to design projections.** R2 requires a
   derived count be validated against a known answer. A power projection has no
   known answer in advance — but it can be reproduced from its stated inputs, and
   a projection that cannot be reproduced from inputs the document states is a
   projection with no provenance. Both columns here were reproducible only by
   guessing the omitted assumption.

---

## B20. The paper holds a careful version and a careless version of one equivalence claim, and ships both

**SUBMISSION-BLOCKING. Not Phase 12 routine.** This is not a defect in the
analysis pipeline or in a design projection; it is a defect in the manuscript as
it currently stands, and a reviewer reaches it by reading two sentences in one
document. It is older than anything Phase 8.5 produced.

### The three locations, verbatim

**(1) The careless version — `paper/sections/06-evaluation.tex:618-621`**, in
`\paragraph{B3-mode: the barrier removed entirely}`:

> it delivers the entire detection guarantee of \cref{tab:outcomes} --- every
> rate in that table, on every capability class, statistically indistinguishable
> from AEP-full's.

**(2) The careful version — `paper/sections/06-evaluation.tex:283-301`**, the
paragraph headed *A word on what the zeros can and cannot support*:

> both numbers are worth nothing: a test between two zero counts has no power,
> and failing to distinguish them is not evidence that they are the same. What
> two zeros do support is a *bound*. The one-sided 95% Wilson upper confidence
> bound on a zero numerator over \BthreeVsAepN{} executions is
> \AblationZeroUpper{}%. […] This finite-sample bound is the support for "no
> observed difference" in the two zero-event metrics; the corresponding Fisher
> values are not evidence of equivalence.

**(3) The generator's own caption — `paper/generated/table-ablation.tex:6`:**

> The p-values are execution-level Fisher tests over all capability classes;
> they do not account for run clustering and **are not used as equivalence
> evidence**.

The same disclaimer appears a third time at `06-evaluation.tex:280-281`: "The
execution-level Fisher value ($p = \BthreeVsAepAmbP{}$) is not used as
equivalence evidence."

**The abstract's bounded counterpart — `paper/main.tex:157-160`:**

> both record $\BthreeVsAepDupCount{}$ undetected duplicates and
> $\BthreeVsAepLostCount{}$ lost effects. The individual one-sided 95% Wilson
> upper bound for either zero-event rate is \AblationZeroUpper{}%.

The abstract makes the narrower claim **and carries its bound**. Line 621 makes
the wider claim and carries nothing.

### What line 621 drops

Every qualification the source paragraphs insist on:

1. **The bound.** `\AblationZeroUpper{}` = 0.50 pp, and under simultaneous
   statement Bonferroni gives joint coverage of at least 90%, not 95%. Line 621
   states no bound and no coverage.
2. **That the ambiguity margin is stipulated and post hoc.** Line 270-272 says
   the $\pm\BthreeVsAepAmbMargin{}$ pp margin "was not preregistered, and we
   state it as a stipulation rather than derive it."
3. **That the interval is 90%, stratified and cluster-aware** —
   \BthreeVsAepAmbClusters{} clusters over \BthreeVsAepAmbStrata{} strata — and
   that line 277-280 calls it "a sensitivity analysis, not a strong general
   equivalence result".
4. **That "no observed difference" was the licensed phrasing.** Line 257-258 uses
   exactly that wording. Line 621 upgrades it to "statistically
   indistinguishable", which is the phrasing line 288 disclaims by name:
   "failing to distinguish them is not evidence that they are the same."

### And what it adds that no source supports

**"on every capability class."** There is no per-class equivalence test anywhere
in the paper. §`sec:eval-detection` reports per-class declared-ambiguity rates
*descriptively* ("the two systems track each other",
`06-evaluation.tex:262-265`), and every interval it computes is **pooled** across
classes. The only per-class statistics in the build are the Fisher values, and
all three locations above say those are not equivalence evidence. So line 621's
per-class claim rests on the one quantity the manuscript twice refuses to rest it
on.

### Why this is blocking rather than routine

Two disclaim the use the third makes, inside one compiled document. A reviewer
does not need the data, the artifact, or any Phase 8 material to find it — they
need §6.4's zeros paragraph and §6.7's B3-mode paragraph, both in
`06-evaluation.tex`. The careless version is also the one placed in the
deployment-recommendation paragraph, where it does argumentative work: it is what
licenses "B3-mode gives the paper's headline result for \ProtocolMinusBarrier{}
ms" at `06-evaluation.tex:633`.

### What is needed — and what was deliberately not done now

**Not fixed in Phase 8.** Line 621 is a different quantity from Phase 8.5's
estimand (B3 vs AEP-full on `tab:outcomes` detection metrics in the crashed
regime, versus the capability-class contrast on the applied-effect column in the
redis-kill regime). It needs its own analysis, and rewriting it now — with the
data in view and no pre-registration governing it — is exactly the move this
phase has spent itself avoiding. The `paper/` lift covering Sites 1 and 2 does
not reach it.

1. **Decide what line 621 is entitled to claim,** per metric and per class,
   before rewording it. The answer is probably "no observed difference, bounded
   at \AblationZeroUpper{} pp pooled, with no per-class test" — but that is a
   determination, not an edit.
2. **Drop "on every capability class" unless a per-class analysis is run.** It is
   currently an unsupported generalisation of a pooled result.
3. **Make the binding structural.** See the principle recorded in
   `reports/phase-report-8-6-section-F-2026-08-31.md` §F.0b: this is the second
   instance in this manuscript of *failure to reject reported as
   indistinguishability*, and §F.0 caught only the first because it was written
   around one named estimand.
4. **Nothing enforces consistency between a careful statement and a later
   restatement of it.** `scripts/check_paper_numbers.py` verifies that every
   *number* matches its source. It cannot see that a sentence carrying no number
   has overstated a sentence that carried one. Same class as B11 and B15: a
   check that looks live and structurally cannot detect what this needs.

---

## B21. The paper build compiles in a scratch directory and then reads three-week-old state back in

**Filed against Phase 12.** Found while rebuilding for the Site 1/Site 2 edits,
because it produced a `DO NOT SUBMIT` that pointed at the wrong cause.

### What happened

`scripts/build_paper.sh` opens by stating its own design goal:

> Compilation happens in a scratch directory. Bibliography, reference, PDF, and
> paper-number checks all run against those staged artifacts; only a clean build
> is promoted into `paper/`.

It then sets, at line 79:

```bash
export TEXINPUTS="${PAPER}//:${TEXINPUTS:-}"
```

The `//` makes kpathsea search `paper/` **recursively, for every file the run
needs** — not only for `sections/`, `generated/` and `figures/`, which is the
stated intent, but also for `main.aux` and `main.bbl`. Both exist in `paper/`,
both are **untracked**, and on this host both are dated **10 August** — three
weeks before this build.

`bibtex` writes a fresh `main.bbl` into the scratch directory. pdflatex then
finds the stale one and uses it. That `.bbl` predates three `\cite` keys
`07-related.tex` now uses, so the build reported:

```
FAIL  no undefined references or citations
      Citation `richardson-transactional-outbox' on page 14 undefined
      Citation `jena2025idempotencykey' on page 14 undefined
      Citation `setty2016olive' on page 14 undefined on input line 44.
```

All three keys are present in `refs.bib`. Nothing was wrong with the manuscript.

### Why it is worth filing rather than shrugging at

**The isolation the script advertises is defeated by its own search path.** The
scratch directory is real and the promotion discipline is real, but the compile
is not isolated: it reads back exactly the kind of stale state the scratch
directory exists to avoid. Same class as B11 and B15 — the mechanism is present,
the name is accurate about intent, and it does not do what a reader assumes.

**It misattributes.** The failure names the citation keys and the citing file.
It gives no indication that the cause is an artifact in a directory the build
claims not to compile in. Time to diagnose here: substantial, and the first
control I ran was itself wrong (below).

**It is silent when it succeeds.** A stale `main.bbl` that merely has *outdated
entries*, rather than missing ones, produces no warning at all. Nothing checks
that the `.bbl` pdflatex read is the `.bbl` bibtex just wrote. The current
failure is loud only because the drift happened to be a missing key.

### A methodological note, because the obvious control was wrong

The natural check — "did HEAD build clean?" — was run as:

```bash
git archive HEAD paper | tar -x -C /tmp/headpaper
AEP_PAPER_DIR=/tmp/headpaper/paper bash scripts/build_paper.sh
```

It passed, which appeared to prove the edits caused the failure. **It proved
nothing of the kind.** `git archive` emits tracked files only, so the exported
tree had no `main.aux` and no `main.bbl` — the control silently removed the
variable under test. The comparison was between *edited sources with stale
artifacts* and *HEAD sources with no artifacts*, differing in two things at once.

Re-run symmetrically (`phase8-driver/build_clean_copy.sh`: copy `paper/`, delete
the untracked artifacts, build), the edited tree gives **17 passed, 1 failed** —
identical to the control, with the one failure being the pre-existing missing
`pydantic` (B6's territory, an environment gap).

**`git archive HEAD <path>` is not a snapshot of a working directory.** Any
future "was it like this before my change?" check that uses it must first
establish that the behaviour under test does not depend on untracked files.

### What is needed

1. **Do not put `paper/` on `TEXINPUTS` wholesale.** Expose `sections/`,
   `generated/` and `figures/` explicitly, or copy the inputs into the scratch
   directory. Nothing needs `paper/main.aux` on the search path.
2. **Assert the `.bbl` identity.** After `bibtex`, confirm the `.bbl` pdflatex
   resolved is the scratch one — `\openin`/`\openout` lines are in `main.log`
   and are greppable.
3. **Fail loudly on stale artifacts in `paper/`.** If `main.aux`/`main.bbl` are
   untracked build products, either `.gitignore` them and remove them before
   each build, or refuse to build while they are present.
4. **Decide whether `paper/main.pdf` should be tracked at all.** It is the one
   tracked build product, and it is now stale relative to the sources, because
   the build legitimately refuses to promote while the `pydantic` check fails.
