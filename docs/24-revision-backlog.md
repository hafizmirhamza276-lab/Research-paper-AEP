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
