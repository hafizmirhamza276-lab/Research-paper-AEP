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
