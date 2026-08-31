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

`scripts/freeze_results.py:176-178`:

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
