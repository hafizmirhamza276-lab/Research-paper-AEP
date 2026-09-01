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

### CLOSED 2026-09-01. Three lines, not two.

**The estimate was wrong in the direction that mattered.** The entry names
`:178` and `:179`. **The defect at `:172` is the load-bearing one and is not in
this entry.**

```python
:172  manifest_path.write_text(...)      ->  newline="\n"     # ADDED
:178  path.relative_to(root)             ->  .as_posix()
:179  SHA256SUMS write_text(...)         ->  newline="\n"
```

`MANIFEST.md` is **hashed into `SHA256SUMS`** at `:175`. Without `newline="\n"`
its bytes differ by platform, so **its content digest differs** — and no
path-spelling fix repairs that. `:178`/`:179` make the manifest well-*formed*;
`:172` is what makes it *reproducible*. A fix that stopped at two lines would
have produced a `SHA256SUMS` that verified on Windows and still disagreed,
digest for digest, with the one Linux produces from identical data.

**Deliberately not changed: `:95`, `MANIFEST.csv`.** `newline=""` plus the csv
module's `\r\n` lineterminator yields CRLF on **every** platform. Verified across
all eleven roots — CR count equals LF count exactly. It is already portable.

### The eleven existing roots need nothing, and that was checked before assuming

**All eleven committed `SHA256SUMS` are already correct**: 0 CR bytes, 0
backslashes, forward slashes throughout. `sha256sum -c` passes **16/16 from
Windows** on `b2-2026-08-21` today.

**The defect never reached a committed artifact.** Each of the four roots'
`SHA256SUMS` was committed exactly once, with no later repair commit — so the
bytes were LF from the moment they entered the repository. Only **future freezes
run from Windows** were ever at risk.

**One correction, and it is against this closure's own author rather than the
entry.** The plan for this fix said the entry "reads as though the repository
currently holds broken manifests." **That was overstated.** The paragraph
directly above has said since it was filed that the roots were re-frozen under
WSL and verify 16/16. The entry's *lead* foregrounds the failure output, which
is what invited the misreading, but the fact was recorded and I implied it was
not. **Nothing about the four roots is unresolved:** the Windows output was a
transient, corrected by re-freezing from WSL, and **never committed** —
established from `reports/phase-report-8-1-0-2026-08-27.md` §F.1 and from the
commit history, not inferred.

### Verified by a freeze on both platforms, not by reading the diff

`phase8-driver/verify_b5_freeze.sh`. A root is copied to scratch **outside every
results root and outside the repository**, frozen on Windows (3.11.9) and on WSL
(3.12.3), and compared byte for byte:

```
win == wsl        BYTE-IDENTICAL
win == committed  BYTE-IDENTICAL
wsl == committed  BYTE-IDENTICAL
format assertions on Windows output: CR=0 backslash=0
```

**Using the committed manifest as the expected value makes it real data rather
than a fixture**, and proves portability and non-regression in a single
comparison.

**The test discriminates, which was checked rather than assumed (R2).** The
pre-fix code from `HEAD`, run on the same data on Windows:

| | CR | backslash |
|---|---|---|
| **pre-fix** `SHA256SUMS` | **16** | **14** |
| **pre-fix** `MANIFEST.md` | **26** | 0 |
| fixed `SHA256SUMS` | 0 | 0 |
| fixed `MANIFEST.md` | 0 | 0 |

A test that passes before and after proves nothing. This one fails before.

**The harness itself failed first, and in the correct direction.** Its first run
reported `win != committed`. The cause was the harness: the original freeze used
`--label`, which I had omitted, so the regenerated manifest differed on its title
line alone. It now recovers the label from the committed `MANIFEST.md`. **A
verification check authorises "the fix is good" — the complacency side under B33
— so it must over-report failure.** It did.

**No existing `SHA256SUMS` was rewritten.** Every freeze ran on a copy in
scratch; the standing rule was not merely obeyed but structurally out of reach.
Afterwards: `git status` silent for `experiments/results`, the committed
`b2-2026-08-21` manifest unchanged, `sha256sum -c` 16/16.

### The regression test was DELIBERATELY NOT ADDED

**So that its absence is not read as an oversight.** The entry proposes freezing
a fixture tree and asserting no backslash and no `\r`. **There is no `tests/`
directory and no `test_*.py` anywhere in this repository.** Adding one is
materially more than this fix and was declined as scope.

**The two-platform verification above is the stronger check regardless**, and it
exists as a script rather than as a one-off: it compares against **real committed
data** rather than a fixture's expectations, so it cannot drift into agreeing
with a wrong implementation the way a self-authored fixture can. What is missing
is that **nothing runs it automatically** — it must be invoked by hand before a
freeze is trusted on a new platform. **That is the residual, and it is stated
rather than closed.**

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

### RESOLVED 2026-08-31 — the defect was pooling, it reached the point estimate, and the control was not one

**Closed.** Full working in
`reports/phase-report-8-B9-kill-latency-reanalysis-2026-08-31.md`; derivations
in `reports/raw/b9_kill_latency_by_session.py` and
`reports/raw/b9_drift_reconstruction.py`. No frozen root was opened and nothing
was re-collected. **This does not close as "recomputed, unchanged."**

**Correction 1 — the `+0.703` is from the wrong collection.** It is *not*
unreproducible: it reproduces exactly at **+0.7034** from
`b2-paired-s1-2026-08-28`'s tracked `per-execution.csv`, with position
reconstructed as `(cell, repetition)` in collection order. A stronger claim —
that the figure existed only outside the artefact — was asserted in this task's
plan and is **withdrawn in full**; the mechanism of that error is recorded in
§F.0f. What is wrong is narrower and still fatal to the paragraph above:
`b2-paired-s1` is a **superseded design in a different collection** from the
Phase 9 replication set (`b2ab570`) that this entry's claim is about. **The
drift was imported across collections before anyone measured the drift in the
data being argued about.**

**Correction 2 — the drift in this entry's own data is nothing like +0.703.**
Spearman(repetition, kill latency) for AEP-full: −0.211, −0.505, +0.045, −0.436
across `P9-B`, `s1`, `s2`, `s3`, and −0.125 on ext4. **Mixed in sign, moderate
in magnitude.** Drift is real and exchangeability over run labels does fail, so
the entry does not retire — but its stated evidence had to be replaced before
anything could be built on it.

**Correction 3 — it names the wrong test.** There is one family and it is
Mann-Whitney throughout (`paper_tables.py`, `_median_split`), not "a permutation
test over run labels" plus "the Mann-Whitney variants". The concern survives —
Mann-Whitney's null distribution *is* the permutation distribution of ranks —
but the entry misdescribes its own target.

**Correction 4 — the defect is between-session pooling, which this entry never
mentions.** `_median_split` filtered on `filesystem` and `system` only. The
drvfs stratum is **four sessions**, so it pooled 120 runs across four
host-timing states with no session term. Applied rates are 20, 12, 4 and 7 out
of 30 — 9C's over-dispersion — so pooling mixed between-session level
differences into a within-session contrast. Within-session position, which is
what this entry diagnoses and what both its proposed remedies target, is the
*weak* threat here: ρ(position, `applied`) is ≤ 0.19 in magnitude in every
session.

**Correction 5 — it reached the point estimate, not only the p.** The entry
says *"what cannot stand is the p-value as currently computed"*. That is wrong.
The four per-session median differences are **+70, −4, +282, +74** ms; the
pooled `\KillLatencyDiff` was **+201** ms, **larger than three of the four
sessions it was built from, with one of them of the opposite sign**. Pooling
weights runs, so `s2`'s +282 ms — measured on 4 applied runs against 26 —
dominated it. Session-clustered with the paper's own estimator: mean **+105.5**,
95% interval **[−90.8, +301.7]**, **half-width 1.86× the mean it brackets**.

**Correction 6 — the B3 negative control was not a negative control.**
`_median_split("drvfs", "B3_INTENT_NO_BARRIER")` was **the same pooled call on
the same four sessions**, so it could not stay evidential while the treatment
arm was retired. Recomputed at the session level: −28, +27, −31, −152 ms, mean
**−46.0**, interval **[−166.4, +74.3]**, **half-width 2.61× its mean**.

> **Pooling is what made it look like a control.** The pooled −14 ms at p = 0.63
> read as a clean null because pooling made it precise. At the correct unit the
> interval spans 240 ms and contains effects larger than the one it was
> supposed to be controlling for. **It never had the power to contradict the
> mechanism, so its failure to contradict it was never evidence for it** —
> whatever B3 had done, this comparison would have returned a null. Each
> session's difference rests on 2 non-applied runs out of 30.

**Correction 7 — the remedy this entry prescribes cannot work.** It assumes the
fix is a corrected p. At the session level with k = 4, a two-sided sign test is
**floored at 2·(1/2)⁴ = 0.125** — no outcome the design admits reaches 0.05. The
t route is not floored and returns p = 0.186. `"3 of 4 sessions positive"` is
that same floored test in counting form (two-sided p = 0.625) and is therefore
**not** used as directional support. The paper reports the four differences, the
mean and the interval, with no p and no tally.

**Correction 8 — the block-width remedy is declined, on the record.** Block
width is a researcher degree of freedom. Had it been necessary the rule would
have been fixed before looking (width = the collection's repetition stride) and
any verdict that moved with the width would have been reported as a finding
rather than resolved by choosing a width. None of it is needed once the session
is the block — which is not a free parameter but **the unit `paper_tables.py`
already uses for `\ReplicationPrevented*` and `\ClassPp*` on these same four
sessions, in the same file**. That inconsistency, one report using two units on
one dataset, is what makes this a defect rather than a defensible choice.

**Correction 9 — the asymmetry note is right and is kept.** Interleaving from
session 2 onward does protect new data. That paragraph survives intact.

**What was withdrawn beyond what this entry named.** 8.5's finding that
`log(issue_to_return_ns)` is not degenerate was being used as independent
support for the mechanism. It is not: non-degeneracy establishes that the
covariate has variation to adjust on, and says nothing about whether latency
predicts `applied`.

**What the mechanism now rests on.** One session — ext4, `2026-08-07`, 30 runs
— at **+88 ms, p = 0.03**, with its own single-session control at +26 ms,
p = 0.53. It is retained because it is a single session and therefore pools
nothing; its costs are that k = 1, it carries no between-session variance
component, and **it is the one figure this entry's own exchangeability concern
actually reaches**. Beside it, four replication sessions that are directionally
consistent at a precision that does not resolve the question. **That is very
little, and it is the result.** The mechanism is not refuted and it is not
established.

**Changed:** `\KillLatency{,Bthree}{Diff,P,N}` withdrawn and replaced by
`\KillLatency{,Bthree}{PerSession,Mean,HalfWidth,PrecisionRatio,Low,High}` plus
`\KillLatencySessions` and `\KillLatencySignFloor`, session declared in the
`macro()` provenance and the emission fail-closed on "exactly four whole
sessions". `\KillLatencyOrig*` and `\KillLatencyBthreeOrig*` unchanged.
`06-evaluation.tex` and `08-threats.tex` rewritten. Nothing in `main.tex`.
Commits `49cf2a3`, `ebc7d1f`, `c7dc005`.

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

### RESOLVED 2026-08-31 — and the filing above was wrong in three ways

**Closed.** What was fixed, and what the analysis found that this entry did not.

**Correction 1 — it was four unbounded restatements, not one.** An F.0b lexicon
sweep (*indistinguishab | equivalen | no difference | no effect | unaffected |
identical to | the same as | shows no*) over every section, `main.tex` and every
generated file found:

| | location | wording | in the original filing? |
|---|---|---|---|
| 1 | `06-evaluation.tex:623-624` | "every rate in that table, on every capability class, statistically indistinguishable from AEP-full's" | yes |
| 2 | `generated/table-outcomes.tex:11` — **caption** | "That the two are indistinguishable here is this paper's ablation result" | **no** |
| 3 | `generated/table-deployment-choice.tex:25` — **caption** | "shows no observed difference **down the whole table**" | **no** |
| 4 | `07-related.tex:66-68` | "Their crashed-regime detection outcomes are statistically indistinguishable" | **no** |

Two are generated captions, so they live in `paper_tables.py` and cannot be
fixed in `.tex`. **Fixing only site 1 would have closed this entry while leaving
the defect in the paper three times over.**

**Correction 2 — three axes of over-generalisation, not two.** Sites 1–4
generalised from two metrics to every rate, and from pooled to per class. **They
also inherited a third defect from the careful paragraph itself.**

**Correction 3 — and it is the important one: the careful version was also
unsound.** This entry framed the defect as *careful version versus careless
version*. That framing was wrong. `\AblationZeroUpper` put `n = 540` in a Wilson
denominator when the data are **54 runs of 10 executions** — the same
execution-level independence `table-ablation.tex:6` disclaims for the Fisher
values, undisclosed here, and reaching the abstract. The abstract carried it
**five lines from a "stratified run-cluster" interval**, two units of analysis in
one paragraph with nothing marking the switch.

### The four bound values

| construction | bound |
|---|---|
| execution-level, pooled, 0/540 @95% — **as the paper had it** | 0.50% |
| **run-level, pooled, 0/54 @95% — as the paper now has it** | **4.77%** |
| run-level, per class, 0/18 @95% | 13.07% |
| **run-level, per class, 6 simultaneous bounds at joint 90%** | **20.10%** |

"On every capability class", honestly scoped and honestly clustered, is **20.1
pp — forty times the number that was quoted.** A 20-point band is not a detection
guarantee.

### What was done

- The bound is reported at the **run** unit, with the execution-level figure
  beside it and what it assumes. `\AblationZeroUpper` was **removed**, not
  redefined, so any unmigrated site fails to compile.
- The prose states explicitly that the unit was **not chosen for the result**:
  the baselines it is contrasted against are `\BaselineDupLowPct`–%
  `\BaselineDupHighPct`\%, so the contrast is unaffected either way.
- All four sites narrowed to the pooled scope, **including both generated
  captions**, which now say that the per-class cells the anchor table is
  organised by are not separately bounded.
- **20.1 pp is stated in the paper**, not only here, so the per-class claim is
  visibly declined rather than silently dropped.

### Two things found and deliberately not fixed

1. **`paper_tables.py:1341`**, a code comment: *"including the p-values that say
   the two systems are indistinguishable."* Not reader-visible, so no F.0b
   violation — but it is the same misconception living in the generator, beside
   the macros whose own provenance says the Fisher values are descriptive only.
   **Phase 12.**
2. **Two sentences the sweep surfaced that are correctly *not* violations.**
   Recorded so a future sweep does not re-litigate them. `06-evaluation.tex:63`
   ("long enough to suspend is indistinguishable from one that cannot") and
   `08-threats.tex:242` ("They are also indistinguishable from clean runs in
   every artifact the analysis reads"). **Both are observability claims, not
   failures to reject** — neither reports a test. The second is in fact the
   opposite of the defect B20 names: it states that two populations *cannot be
   told apart in the data*, and uses that to justify discarding and re-collecting
   rather than to claim they are the same.

**Item 4 of the original filing stands and is unfixed.** Nothing enforces
consistency between a careful statement and a later restatement. All four sites
were found by a manual sweep; F.0b's lexicon check still does not exist.

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
`pydantic` (~~B6's territory,~~ an environment gap).

> **STRUCK 2026-09-01. `pydantic` was never B6's territory.** **B6** is that
> local TeX Live typesets 24 of 29 `\bibitem` entries. **This failure** was the
> *"state-machine figure matches the transition table"* check, which imports
> `aep_core.core.intents` and needed `pydantic>=2.0` **and** `redis>=5.0`. Two
> unrelated environment gaps, and the name was carried between them without
> being derived. **Both are now resolved: `pydantic`+`redis` installed (18
> passed, 0 failed), and B6 remains open.**

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
   **[2026-09-01: the refusal is over — 18 passed, 0 failed. The PDF is
   promotable and unpromoted. The tracking question is untouched and still
   open.]**

---

### SHAPE ESTABLISHED 2026-09-01. Not closed. Larger than this entry states.

**Nothing was installed, promoted, or edited under `paper/`.**

#### The `pydantic` failure is NOT B6, and two documents say it is

This entry calls it *"B6's territory"*; `ARTIFACT.md:231` calls it *"backlog
B6"*. **Both are wrong.**

- **B6** is that local TeX Live (2023/Debian, WSL) typesets **24 of 29**
  `\bibitem` entries, so nine citations render undefined and **CI is the only
  place the bibliography is correct.** Its fixes are pinning the TeX
  distribution or making "built by CI" a checked precondition.
- **The failure actually blocking promotion** is the check *"state-machine
  figure matches the transition table"*. `scripts/gen_state_machine.py:30`
  imports `aep_core.core.intents`, which imports `pydantic`, which is not
  installed.

**They are unrelated environment gaps.** `pydantic>=2.0` is a **declared**
dependency (`pyproject.toml:18`) that is simply absent — from Windows 3.11.9
**and** WSL 3.12.3.

#### The failing check has no bearing on the manuscript

It regenerates a figure from `aep_core` source and compares it to the transition
table. **It says nothing about the paper's prose, numbers, or typesetting.**
Notably, *"no undefined references or citations"* currently **passes**.

**But installing `pydantic` is not established to make the gate green.** It makes
the check **run**. Whether the regenerated figure then *matches* is unknown and
cannot be known without installing. **"One `pip install` from promotable" is the
optimistic reading and is not derived.**

#### The stale artifacts corrupt the gate in the OPPOSITE direction too — new

`check_paper_numbers.py:291-297`: `--build-dir` **defaults to `--paper`**. So a
direct `python scripts/check_paper_numbers.py` reads `paper/main.log` and
`paper/main.bbl`, both dated **10 August**.

| key cited by `07-related.tex` today | in 10 Aug `main.log` | in `refs.bib` |
|---|---|---|
| `richardson-transactional-outbox` | **0** | 1 |
| `jena2025idempotencykey` | **0** | 1 |
| `setty2016olive` | **0** | 1 |

> **The direct invocation's *"no undefined references or citations: PASS"* is
> vacuous.** It is computed from a log written before those citations existed.
> **The `17 passed, 1 failed` baseline this project has quoted as a control
> throughout Phase 8 and 9 is partly computed from three-week-old artifacts.**

`build_paper.sh:147-148` **does** pass `--build-dir "$BUILD_DIR_REL"`, so the
gate inside a build reads scratch correctly. **The same two files therefore break
both paths in opposite directions: the build fails spuriously (this entry), and
the direct invocation passes vacuously (this amendment).**

#### Item 3 is half-done and this entry does not know it

`main.aux` and `main.bbl` **are already gitignored** — `.gitignore:97-98`. What
is missing is the removal-or-refusal half. **Deleting them is not a tracked-file
change and loses nothing**; both are regenerable build products.

#### The mechanism is LIVE, tested rather than assumed

`phase8-driver/probe_texinputs.sh`, under the exact `TEXINPUTS` of
`build_paper.sh:79`:

```
main.bbl (no local copy)      -> paper/main.bbl
main.bbl (local copy present) -> paper/main.bbl
PAPER WINS -- the stale .bbl shadows the fresh one
```

**Even with a scratch-local `main.bbl` present, resolution goes to `paper/`.**

~~**Residual, stated:** this is `kpsewhich` … **The definitive test is a build,
which was not run.**~~ **RESIDUAL CLOSED 2026-09-01 by a real build.**

`phase8-driver/build_probe.sh` runs the actual `scripts/build_paper.sh` with
`AEP_PAPER_DIR` pointed at a **copy**, so a clean build cannot promote into the
tracked tree. Two runs, differing only in whether a stale `main.bbl` is present
in the copy's `paper/`:

| copy's `paper/` | result |
|---|---|
| stale artifacts removed | **17 passed, 1 failed** — the only failure is the state-machine check |
| stale `main.bbl` planted | **16 passed, 2 failed** — adds *"no undefined references or citations"* |

> **B21's mechanism is confirmed against a real `pdflatex` run, not a path
> lookup.** A stale `main.bbl` in `paper/` breaks a build that is otherwise
> clean.

**And the clean run's citation PASS is genuine**, because the gate read the
freshly staged log — unlike the direct invocation's, below.

**A defect in my own probe, reported rather than quietly dropped.** The script
also tried to answer *which* `main.bbl` `pdflatex` opened, by grepping the newest
`main.log` under `.scratch/`. It printed `(./main.bbl` for **both** runs. That
output is **invalid**: `build_paper.sh` removes its scratch directory on exit, so
the newest surviving log was a leftover from **31 August 16:35** — three days
old. **A probe written for a task about stale artifacts read a stale artifact and
reported it as current.** The bbl-identity question is therefore **still open**;
the build-level result above does not depend on it. B21's item 2 — assert the
`.bbl` identity from `\openin`/`\openout` — remains the right fix and is
unimplemented.

#### `ARTIFACT.md`'s marker is itself stale

It is dated *"as of 2026-08-31"* and enumerates what the tracked PDF lacks as of
then. **Six wording edits landed on 1 September** (`08-threats` ×3,
`06-evaluation` ×2, `main.tex` ×1) and are not in its list. The marker is honest
about the PDF and **out of date about its own contents.**

#### Verdict

~~**blocked on … whether `pydantic` is installed** — one declared dependency~~
**AMENDED 2026-09-01: `pydantic` was not the blocker, it was the first of
several.**

### STEP 2, 2026-09-01: the real baseline, and why "one `pip install`" was wrong

**`pydantic` 2.13.5 was installed into Windows Python 3.11.9.** The check then
failed on the **next** import:

```
aep_core/core/intents.py:20  from pydantic import ...        # now satisfied
aep_core/core/intents.py:21  from redis.asyncio import Redis # ModuleNotFoundError
```

> **The state-machine check imports the production module `aep_core.core.intents`,
> so it requires the APPLICATION's runtime dependency set — `redis>=5.0`,
> `pydantic>=2.0`, `cryptography>=46.0` — not a documentation toolchain.**
> Satisfying one import reveals the next. **"One `pip install` from promotable"
> is false**, and nothing further was installed.

#### `import redis` succeeds while redis-py is absent — an over-reporting check

```
>>> import redis          # succeeds
>>> redis.__file__        # None
>>> redis.__path__        # ['D:\...\Research-paper-AEP\redis']
$ pip show redis          # Package(s) not found: redis
```

**The repository has a `redis/` directory at its root holding Redis *config*
files** (`phase2.conf`, `phase2-always.conf`, `toxiproxy.json`). Run from the
repo root, Python resolves `redis` to that directory as a **namespace package**.
It shadows nothing — a real `redis` package would win — but **any check that
uses `import redis` as a proxy for "redis-py is installed" gets a false
positive.** B33's class: an availability check that over-reports.

#### The true baselines, both paths

| path | result | is it meaningful? |
|---|---|---|
| **`build_paper.sh`** (WSL, clean copy) | **17 passed, 1 failed** | **Yes.** Gate reads freshly staged artifacts; the citation PASS is genuine |
| **direct `python scripts/check_paper_numbers.py`** | **14 passed, 2 failed** | **No.** Fails *"main.bbl exists"*, and its citation PASS still reads the 10 August `main.log` |

> **RECORDED SO IT IS NOT CITED AGAIN: the `17 passed, 1 failed` figure quoted
> from DIRECT invocations in earlier reports was partly vacuous.** Its
> bibliography and citation checks were computed from 10 August artifacts. **The
> same numeral is correct for a real build and wrong for a direct run**, which is
> precisely why it went unquestioned for two phases.
>
> **The direct invocation is not a baseline at all.** `--build-dir` "defaults to
> `--paper` for direct and legacy invocations", and `paper/` only holds
> bibliography artifacts if a previous build promoted them there. **It reports on
> whenever that build happened to be.**

#### The state-machine question — ANSWERED 2026-09-01, and it passes

~~Whether the figure matches the transition table remains unknown.~~

```
PASS  state-machine figure matches the transition table
PASS  no undefined references or citations
18 passed, 0 failed
build clean (main); verified artifacts promoted atomically.
```

> **The figure matches the transition table.** Stated precisely, because the two
> statements are not the same: **the check has now run and passed. It is not
> true that it has always passed** — before 1 September it had never completed
> on this host, so the agreement between `figures/state-machine.tex` and the
> transition table was **unverified, not verified-and-fine.** This is the first
> observation of it.

**The dependency chain was two packages, not the three or four that would have
made it a finding:**

| # | package | demanded by |
|---|---|---|
| 1 | `pydantic>=2.0` | `aep_core/core/intents.py:20` — the import that failed all along |
| 2 | `redis>=5.0` | `aep_core/core/intents.py:21`, revealed only once (1) was satisfied |

`cryptography>=46.0` is declared but **was never demanded and was not
installed.** Nothing speculative was added.

**`sudo` was authorised for this and went unused.** `pip` was bootstrapped into
WSL's user site via `get-pip.py` (`phase8-driver/wsl_bootstrap_pip.sh`), and both
packages installed with `--user`. The credential exposure was not added to.

#### The real baseline, final

| path | result |
|---|---|
| **`build_paper.sh` (WSL, clean)** | **18 passed, 0 failed** |
| direct invocation | not a baseline — see above |

**The build produces a 21-page PDF, 374 600 bytes.** The tracked
`paper/main.pdf` is 19 pages, 356 309 bytes, from 21 August.

> **`paper/main.pdf` is now promotable.** It was not promoted: this build ran
> with `AEP_PAPER_DIR` pointed at a copy, and the tracked PDF is byte-identical
> to what it was. Promotion awaits the operator.

#### Three further environment findings, none acted on

1. **WSL cannot install `pydantic` at all.** No `pip`, no `ensurepip`, no
   `pipx` — only `python3 -m venv` without a pip to bootstrap. The routes are
   `sudo apt install python3-pip` or `python3-pydantic`, and **`sudo` is
   prohibited by the standing instruction from the custody task.** The authorised
   install could therefore be completed in **one** environment, not both.
2. **`.venv/` is a stump** — a dangling `lib64 -> lib` symlink and `pyvenv.cfg`,
   no interpreter. `uv run --frozen python` on Windows fails trying to remove it.
   Since `build_paper.sh` prefers `uv`, **the Windows build path is broken
   independently of any dependency.**
3. **`build_paper.sh` cannot run on Windows at all** — no `pdflatex`/`bibtex` on
   PATH, so it exits 127. **WSL is the only build path**, and there the runner is
   system `python3`, which is the one that cannot have `pydantic` installed.

~~**Stopped here.** Steps 3 and 4 … were not started.~~ **Completed
2026-09-01.**

### STATUS 2026-09-01: B21 STAYS OPEN. Three of its four prescriptions are undone

The operator's four steps are discharged — stale artifacts deleted, baseline
re-established, misattribution struck in both places, `ARTIFACT.md`'s marker
removed after promotion. **That is not the same as this entry being closed**, and
closing it here would be closing on a technicality.

**Measured against this entry's own "What is needed":**

| # | prescription | status |
|---|---|---|
| 1 | **Do not put `paper/` on `TEXINPUTS` wholesale** | **OPEN.** `build_paper.sh:79` is unchanged. The recursive search path still exposes `paper/` for every file the run needs |
| 2 | **Assert the `.bbl` identity** after `bibtex` | **OPEN.** Nothing checks that the `.bbl` pdflatex read is the one bibtex wrote. Still the fix for the silent case — a stale `.bbl` with *outdated* rather than *missing* entries produces no warning at all |
| 3 | **Fail loudly on stale artifacts in `paper/`** | ~~HALF DONE, and the wrong half~~ **DONE 2026-09-01 — see below** |
| 4 | **Decide whether `paper/main.pdf` should be tracked at all** | **OPEN.** The PDF was promoted, which resolves the *staleness* but not the *question*. It is still the one tracked build product |

**Item 3 deserves the sharpest statement.** This task deleted three files by
hand, and a single successful build recreates two of them. **The state that made
the gate lie is not prevented; it was merely cleared once.** The mechanism —
refuse, or clear before every build — is unbuilt.

**What this task did settle**, and it is not nothing: the mechanism is confirmed
against a real build rather than a path lookup; the `pydantic`/B6 misattribution
is struck in both documents; the state-machine check has run for the first time
and passes; and the directly-invoked baseline is recorded as never having been a
baseline. ~~Items 1, 2 and 4 remain, and item 3 remains in the form that
matters.~~ **Items 1, 2 and 4 remain. Item 3 is done.**

### ITEM 3 CLOSED 2026-09-01 — a refusal, not a removal

**The entry offered two remedies and both are about the files.** *"`.gitignore`
them and remove them before each build, or refuse to build while they are
present."* **Neither is the fix, and saying so is the substantive part of this
closure.**

Promotion writing `main.log`/`main.bbl`/`main.blg` into `paper/` is **correct** —
CI depends on it and `ARTIFACT.md` documents it. **The defect was never that the
files exist. It is that a later reader could not tell whether they corresponded
to the current sources.** So the fix is provenance, not removal: a build records
the SHA-256 of every source it read, and the gate refuses to use artifacts it
cannot match against that record.

**The rule is "produced from THESE sources", not "newer than the sources".** Age
was rejected: `git checkout` resets source mtimes, so an mtime rule reports stale
after every branch switch and gets learned around — and **this project already
recorded that sync clients normalise mtimes**, so depending on them here would
mean ignoring its own finding. The comparison is an exact hash set: no threshold,
no clock, the orphan gate's construction.

**"Not produced by this build" was also rejected, because it breaks CI.**
`.github/workflows/ci.yml:334` runs the gate a second time with no
`--build-dir`, deliberately — see B40. A flag-provenance rule would fail a step
that is correct and load-bearing.

| file | change |
|---|---|
| `scripts/paper_provenance.py` | **new.** Writer and reader in one module, for `freeze_results.py`'s stated reason — two implementations of *"which files are sources"* would drift, and the drift would fail open |
| `scripts/build_paper.sh` | hashes sources **before** compiling, stages the stamp, promotes it with the artifacts and **before** the PDF. A failed build leaves the previous stamp untouched |
| `scripts/check_paper_numbers.py` | verifies only when `build_dir` resolves to `--paper`; an explicit `--build-dir` is the build checking its own staged output |

**Every ambiguity resolves to STALE** — stamp missing, unreadable, malformed,
wrong version, empty; any source unreadable; anything added, removed or changed.
**There is no path to "fresh" that does not require a complete, readable,
exactly-matching set** (B33: this check authorises *"the numbers are current"*,
so it must over-report staleness).

**Skips are reported, not silent** — `SKIP 2 checks not run` — per B29a.

**Verified by discrimination**, per B34 and B5
(`phase8-driver/test_b21_item3.sh`): the new code passes a fresh build and fails
all five constructed stale states; **the pre-change code passes all six.** That
last line is what proves the new check is doing the work rather than something
else failing.

#### The stamp lives in the directory whose files caused the problem

**Named here so nobody later "cleans it up" as an instance of the very problem it
solves.** `paper/.build-provenance.json` is a new untracked build product, in
`paper/`, gitignored alongside `*.aux`/`*.bbl`/`*.blg`/`*.log`.

> **The distinction that makes it acceptable: the old artifacts were SILENT when
> wrong. The stamp FAILS THE GATE when wrong.**

They are the same kind of file and the opposite kind of risk. **Deleting the
stamp does not restore the old behaviour** — it makes the gate refuse until the
next build, which is the safe direction. There is no state in which removing it
makes the gate more permissive.

#### Transitional state, so it is not read as a regression

`paper/` has no stamp yet, so a bare gate run reports **`14 passed, 1 failed`**
and names the reason. **It clears on the next build.** `paper/` was deliberately
not rebuilt to create one: that would re-promote a byte-different PDF for no
reason. **No artifact was deleted** — deletion is what item 3 replaces.

---

## B22. The write-loss probe tests matched pairs as independent samples, and the code says so itself

**Filed against Phase 12. Found by the unit-of-analysis sweep
(`reports/phase-report-8-unit-of-analysis-sweep-2026-08-31.md`), not by the
sweep's own framing** — the sweep was looking for unit errors, and this sits
above the unit question entirely.

**The defect.** `scripts/paper_tables.py` computed `\FlakeyBarrierP` as
`fisher_exact_two_tailed(0, 90, 90, 0)`. **Fisher's exact test assumes two
independent samples. These are ninety matched pairs.**
`experiments/flakey_write_loss.py:345-348`, `one_trial`:

> """One matched pair of writes, one write-loss event, one read-back."""

The acknowledged and un-acknowledged records are written **in the same trial**
and exposed to **the same write-loss event**. The two rows of the 2×2 are not
two samples; they are two measurements on one unit.

**The code contradicted its own documentation.** The docstring says *"matched
pair"*. The emitted provenance said *"acknowledged vs un-acknowledged loss over
the **same** 90 trials"*. Both name the pairing, and the test discards it.

**It is independent of the unit question and invalidates the construction at
every unit.** Whether the trial, the replication or anything else is the
independent unit, an unpaired test on paired data is the wrong test. A paired
analysis at the trial level (exact binomial on 90 concordant pairs) gives
`1.6e-27`; at the replication level a sign test on 3 gives a floor of `0.25`.
**Neither number was ever quoted, because the p-values are now withdrawn
entirely** — see the sweep report for the four options and the elimination.

**Why this is filed rather than fixed.** The manuscript no longer quotes either
p-value, so nothing in the paper depends on this. What remains is a defect in
the generator: `fisher_exact_two_tailed` is still imported and used elsewhere,
and nothing prevents the next paired comparison from reaching for it. **What is
needed is a guard or a paired-test helper, not a recomputation.**

**Same class as B11 and F.0a:** every artefact involved states the correct fact
and no mechanism connects the statement to the computation.

---

## B23. `\BaselineDupMaxP` is execution-level, and is wrong by 157 orders of magnitude

**Filed against Phase 12.** Found by the unit-of-analysis sweep.

**State this first, so nobody misreads the size: the conclusion is safe under
either unit.** This is a wrong *value*, not a changed *result*.

| unit | comparison | value |
|---|---|---|
| execution — **as quoted at `06-evaluation.tex:93`** | 357/450 vs 0/540 | `5.4e-182` |
| **run** | **42/45 runs with ≥1 duplicate vs 0/54** | **`8.7e-25`** |

The sentence reads *"the weakest of the three comparisons against AEP-full is
significant at $p = \BaselineDupMaxP{}$ by Fisher's exact test."* **It is
significant at both.** The baselines duplicate in 77–83% of crashed executions
and AEP-full in none; no plausible unit changes that.

**The defect is that the value is computed on executions treated as independent
when they are ten to a run**, and that `comparisons-vs-aep-full.csv` records
this — its `fisher_unit` column reads `execution (cluster-unadjusted)` — while
the macro's provenance does not carry it and the sentence does not state it.
**The paper disclaims exactly this assumption in three other places**
(`paper_tables.py:1894-1897`, `table-ablation.tex:6`, `06-evaluation.tex:300`)
and B20 removed it from the ablation bound for the same reason.

**Not fixed here** because it is a different quantity from B20's and needs its
own decision: recompute at the run level, or keep the execution-level value and
declare the unit. **Both are defensible; picking one is not this sweep's call.**

---

## B24. `\UnwantedP`'s unit is correct and declared thirty lines away

**Filed against Phase 12.** Found by the unit-of-analysis sweep.

**Nothing is wrong with the number.** `\UnwantedP` is Fisher exact two-tailed on
`[[10, 20], [28, 2]]` — 30 runs per arm, and `06-evaluation.tex:348` states
*"One execution per run, \AepKillRuns{} runs per system"*. **The run is the unit
and the run is what was used.**

**What is wrong is that nothing carries that with the number.** The macro's
provenance names the contingency table and not the unit. The declaration exists
only in a prose sentence about thirty lines from the first quotation, and the
macro is quoted in **three** places including the abstract (`main.tex:171`,
`06-evaluation.tex:379`, `08-threats.tex:73`).

**This is `\ClassPpLow`'s situation exactly: correct today for a reason nothing
enforces** (F.0c). If the probe were ever changed to run more than one execution
per run, the macro would still resolve, `check_paper_numbers.py` would still
pass, every sentence would still read fluently, and the p-value would silently
become an execution-level number quoted as a run-level one. **Nothing degrades
when the assumption stops holding.**

**The fix is declaration, not recomputation** — and it is the thing B25 would
enforce.

---

## B25. A unit-declaration check: designed, not built — and it would not have caught B20

**Filed against Phase 12.** Designed by the unit-of-analysis sweep.

**The design.** Every macro whose provenance matches an inferential pattern
(interval, bound, CI, bootstrap, Wilson, Fisher, quantile, half-width, margin)
must contain an explicit unit token — execution, run, run cluster, session,
cell, stratum, trial. `paper_tables.py` refuses to emit otherwise.

**Fail-closed by construction, per F.0d: a new quantity with no declared unit
fails until declared.** The default state of new work is failure, which is the
property that separates the orphan gate from every check in this backlog that
looks live and cannot act.

**It must handle sibling inheritance.** `\BarrierCostHigh`'s provenance reads
*"the 97.5th percentile of **the same** bootstrap"*, inheriting its unit from
`\BarrierCostLow`. A naive implementation flags it and three others, and a check
that cries wolf on a quarter of its population will be silenced.

**Keep this sentence: it would not have caught B20.** `\AblationZeroUpper`'s
provenance read *"one-sided Wilson 95% upper bound on 0/540, percentage"*. **It
declared its unit. The unit was wrong.** A declaration check passes it.

**What it would have caught: all four findings of the sweep** — B22, B23, B24
and the withdrawn `\FlakeyVsProcessKillP`. **What it cannot do is decide whether
a declared unit is the right one.** That is the judgement B20 needed, and no
check can make it. What the declaration buys is that the judgement becomes
visible and reviewable, which is all a check can honestly offer.

**Recorded so the check is not oversold later.** Declaration is mechanical;
correctness is not.

---

## B26. Four sentences assert the race mechanism as established; B9 withdrew the evidence

**Filed 2026-09-01 by the pre-Phase-10 assessment
(`reports/phase-report-9-claims-assessment-2026-09-01.md`, amended by unit 2).
File, do not fix.**

B9 withdrew the pooled kill-latency `p`, showed the point estimate was a pooling
artefact, and showed B3 was never a negative control for it. What remains of the
race mechanism is **one unreplicated session at +88 ms, `p` = 0.03**, and a
four-session interval of **[−91, +302] ms containing zero**. B9 corrected the two
sites it was scoped to. **Four others assert the mechanism as fact and were not
looked for.**

| site | wording | verdict |
|---|---|---|
| `06-evaluation.tex:393` | "the effect size is a property of this host's `docker` latency" | **defensible.** One of *"two honest qualifications"* — offered as a reason to distrust the number. Asserting a limitation on thin evidence is conservative |
| `06-evaluation.tex:463` | "it is where one host's kill-latency distribution **happened to place a race**", chained by *"therefore"* to the paragraph above, which now concludes the opposite | **exposed** |
| `08-threats.tex:85` | "an effect size we **can now show** is host-dependent rather than merely suspect it is" | **exposed.** Written when `p` = 4.0×10⁻⁹ existed |
| `08-threats.tex:385` | "its effect size **is a function of** that host's `docker kill` latency. It is the whole of the barrier's measured case" | **exposed.** Directly contradicts `08-threats.tex:96`, 289 lines earlier in the same file |

**The mechanism of the defect is the point.** `06-evaluation.tex:393` states a
caution. The two threats-section sites restate it as a finding, because neither
passage is *about* how well evidenced it is. **A self-imposed limitation was
converted into an asserted result by restatement** — F.0b's mechanism running in
the direction nobody watches.

**And I introduced the contradiction.** B9 unit 3 rewrote `08-threats.tex:96` and
did not look 289 lines down for its restatement. **The fix for the previous
instance of F.0b's restatement problem created the next instance of it.**

**Needed:** the standing adversarial pass must cover *restatements of* an edited
claim, not only the edited claim. A search for the claim's other sites is
mechanical ~~(`claim_sweep.py` finds all four)~~ and was not run.

> **The struck parenthetical is false, and it contradicted B29a on the same
> page.** `claim_sweep.py` returns **two of five** sites for this claim. B29a
> already recorded that it returned two of four; this entry kept asserting the
> opposite, and the two were filed the same day. **A backlog can hold a
> contradiction as easily as a manuscript can** — which is B26's own subject,
> appearing in B26's own text.

**Not in scope:** the sentence following `06-evaluation.tex:463` — *"what is
structural is that the race exists for AEP-full at all and cannot exist for
B3"* — is a design claim and is sound.

---

### CLOSED 2026-09-01 by R7, which was tested before it was trusted

**The procedure is `docs/25-collection-tooling-rules.md` R7.** The instrument
question was settled from source first, because giving a fail-open tool formal
standing is worse than having no tool.

**`claim_sweep.py` has three silent exclusions, not the one B29a records:**
macro-bearing sentences (`:129`), sentences with no lexicon hit (`:131`), and
`numbers.tex` plus structural lines (`:70`, `:59`). Probed against the five sites
of this claim, it returns **two**:

| site | outcome |
|---|---|
| `06-evaluation` *"property of this host's"* | **excluded — no lexicon hit** |
| `06-evaluation` *"one draw from a distribution"* | excluded — macro |
| `08-threats` *"host-dependence we"* | returned |
| `08-threats` *"should be a function of"* | returned |
| `08-threats` *"may be a function of that"* | excluded — macro |

**One miss is the lexicon filter, and that decides the instrument question.**
Fixing the reporting announces a skipped count without finding the sites. Adding
`--all` removes the macro filter and *still* misses `06-evaluation`, whose
sentence contains none of the forty lexicon terms. Removing both filters leaves
"print every sentence" — **full-text search with extra steps and a lexicon to
keep wrong.** It is the wrong instrument; R7 specifies `grep`. **B29 and B29a
remain open and unfixed.**

**R7 was tested against this claim, and the test changed the rule.** As first
written it searched content nouns only and passed the four current sites. But
`06-evaluation.tex:462` restates `:393` while sharing **not one noun** with it —
*"one draw from a distribution"* against *"a property of this host's `docker`
latency"* — so the noun search misses it. It happens to be harmless here, because
Edit C left that site no longer asserting host-dependence; **it is right by luck
of a rewrite, not by the procedure being sound.**

R7 now requires **two searches and their union**: content nouns, then the macros
carrying the claim's evidence. That reaches `:462` **and `main.tex:172`** — which
carries `\UnwantedPrevented{}` and the word *host* nowhere, so **a noun-only
search never looks at the abstract**, where claims are stated most strongly and
were written when the evidence was strongest.

**Both sites were added to the fixture rather than dropped.** Dropping the one
the rule missed would have been adjusting the fixture until the rule passed.
`phase8-driver/test_r7_fixture.sh`: **6 sites, PASS.**

**What this does not close.** R7 is a procedure a person runs, not a gate. Nothing
enforces it, and its own weakness is now on record: **a restatement sharing
neither a content noun nor a macro with the claim escapes both searches.** No
such site is known in this manuscript; the limit is stated rather than assumed
absent.

**Also corrected: this entry's own site list was incomplete.** `08-threats.tex:103`
states the claim and B26 never listed it. It is correctly hedged — *"but our
measurement of that reason does not establish it"* — so it needs no edit, and R7
records it as the worked example of **a prediction from design, which is not a
restatement to be brought into line.**

---

## B27. The prevention claim is carried in three places by one session's Fisher, and only one carries the replication

**Filed 2026-09-01 by the argument assessment
(`reports/phase-report-9-argument-assessment-2026-09-01.md` §3b, recharacterised
by unit 2 §A2). File, do not fix.**

`\UnwantedP` = 1.9 × 10⁻⁶ is a Fisher on 10/30 against 28/30, **one execution
per run, within one session.** It appears three times:

| site | what follows |
|---|---|
| `main.tex` — abstract | nothing. Three scope qualifiers, no indication the quantity was replicated |
| `08-threats.tex:73` — **bold** | nothing |
| `06-evaluation.tex` | **the replication, immediately** — five measurements, range 4–20, mean 17.2, session-clustered interval **[6.1, 28.4]** |

**A reader of the abstract or of the threats section receives one session's
`p` and never learns the quantity was measured four more times.**

**What this is not, tested and rejected in unit 2 §A2.** It is **not** an F.0b
violation — F.0b binds a failure to reject reported as indistinguishability, and
this is a rejection. It is **not** a unit-of-analysis error of the B20/B9 class —
a within-session run-level Fisher is a legitimate unit for the narrower
question, and the paper declines it nowhere. **B24 separately covers whether the
unit is declared.**

**What it is:** a **representativeness gap**. A quantity measured five times is
represented by one of its five in both places a reader forms an impression.
Every existing check passes all three sites, because the number is correct at
all three. **F.0b's mechanism needs only a restatement; it does not need a
withdrawal.**

---

## B28. The threats section's self-criticism attaches to the wrong half, and under-claims

**Filed 2026-09-01 by the argument assessment (§3a, reference class corrected by
unit 2 §A3). File, do not fix.**

`08-threats.tex:83-88` says the barrier — the paper's most novel contribution —
*"serves the claim with the **weakest** evidence."*

**On scope that is correct and must not be softened:** one capability class, one
crash point, one host, and all four replications are the same cell.

**On strength within that scope it is now wrong in the paper's own disfavour.**
The manuscript carries session-clustered intervals for **three distinct
quantities** (four macro pairs; the kill-latency pair is one contrast measured
on two arms):

| quantity | interval | zero |
|---|---|---|
| **effects prevented** | **[6.1, 28.4]** | **excluded** |
| capability-class effect | [−21.4, +46.4] pp | contains |
| kill-latency contrast (both arms) | [−91, +302] / [−166, +74] ms | contains |

**The prevention result is the only one that excludes zero.** It is the
best-replicated inferential claim in the paper, and the sentence calling its
evidence the weakest sits in the same paragraph as B26's *"can now show"*.
**Under-claim and over-claim, adjacent, in the paragraph written to be hard on
the paper.**

**Needed:** nothing that softens the scope criticism. What is missing is that
within that scope the effect replicated four times with an interval excluding
zero, and that the weakly evidenced thing is the *explanation*, not the result.

---

## B29. `claim_sweep.py` exists and is not wired to anything

**Filed 2026-09-01. File, do not fix.**

`phase8-driver/claim_sweep.py` implements the lexicon check **F.0b recorded as
unimplemented**, widened from equivalence vocabulary to strength vocabulary, over
all nine sections, `main.tex` and the six generated captions. It found B26, B27
and B28, none of which any existing check can reach: **137 of 756 sentences carry
evidential force and cite no macro**, and every one of them is invisible to
`check_paper_numbers.py`, to the orphan gate, and to LaTeX.

**It is not in `check_paper_numbers.py` and it is not in any build.** It is a
tool that was run once, by hand, by the person who wrote it — which is precisely
the property F.0e records as the reason the first design-floor argument was
never filed.

**It also cannot be made a gate as written**, and that should be recorded rather
than discovered later: it flags sentences for **judgement**, not violations. 137
hits with no verdict is a list, not a check. A gate would need either a
tolerated-set file that the 137 are enrolled in — so that a *new* evidential
sentence with no macro is what fails — or nothing at all.

**Needed:** decide between wiring it as a diff-scoped advisory (new or changed
evidential sentences only) and deleting it. **Leaving it in the tree unwired is
the worst of the three**, because its existence reads as coverage.

### B29a. It is fail-open, and this is the sharper defect

**Amended 2026-09-01, the same day, after using it.** The entry above says the
tool is unwired. **The tool is also wrong in the F.0d sense, and that matters
more.**

Asked to find every restatement of the race-mechanism claim, `claim_sweep.py`
**returned two of the four sites and exited 0.** The four are
`06-evaluation.tex:393`, `06-evaluation.tex:463`, `08-threats.tex:85` and
`08-threats.tex:385`. It returned the two that carry no macro. **The two it
missed carry `\UnwantedPrevented` and `\AepKillRuns`.**

**It excludes macro-bearing sentences by design** — that exclusion is the whole
point, since those are the sentences the other checks already reach — **and it
says nothing about having done so.** Its output is a list of hits and an exit
code of 0, which is exactly what a complete answer looks like.

> **"Here is everything" and "here is everything except the class I skip" render
> identically.** That is F.0d's fail-open class, in a tool built during the phase
> that named it, by the person who named it.

The full answer came from a plain full-text search run afterwards. **The tool was
used for the one job its design forbids, and its output gave no sign of that.**

**The fail-closed form, recorded and deliberately not built:**

1. **Report the exclusion.** Print the count of sentences skipped for carrying a
   macro, beside the count returned. A caller then sees the answer is partial —
   `137 returned, 619 skipped as macro-bearing` — rather than inferring
   completeness from a clean exit.
2. **Refuse the wrong question.** A `--all` mode that scans both populations, so
   "find every site stating X" has a correct invocation instead of only a
   plausible-looking wrong one.

**Do not build either.** Recorded so that whoever decides B29's fate decides it
knowing the tool is not merely unwired but silently partial, and so that the
count of fail-open checks in this repository includes the one written to detect
them.

---

## B30. The mechanism counterfactual is the last flatly-asserted mechanism claim in the paper

**Filed 2026-09-01, immediately after the six wording changes of `f5ac276`.
File, do not fix — this needs a decision about what the mechanism paragraph
should claim, which is a task and not a clause.**

`06-evaluation.tex:393-395`, as it now reads:

> "Second, and for the same reason, *the effect size **may be** a property of
> this host's `docker` latency*. **A faster kill pushes AEP-full toward 0 and
> widens the gap; a slower one narrows it.** The *direction* is structural — B3
> cannot be protected by a barrier it does not wait for — but the magnitude
> should not be read as a constant of the protocol."

**The first sentence was hedged by edit F. The second was left alone, by
instruction, and it is a flat counterfactual.** *"A faster kill pushes AEP-full
toward 0"* asserts the direction and the responsiveness of the effect to kill
latency as fact.

**After `f5ac276` it is the only flatly-worded mechanism statement left in the
manuscript.** The other four sites now read *may be*, *suspect and have not
established*, *which our measurement does not establish*, or state the measured
variation instead.

### What supports it, and what does not

| | |
|---|---|
| **Design argument** | AEP-full dispatches only if `WAITAOF` returns before Redis dies. That a slower kill gives `WAITAOF` more time to win is **a property of the protocol**, and it is sound |
| **Empirical argument** | one unreplicated session at +88 ms, `p` = 0.03; a four-session interval of [−91, +302] ms containing zero |

**The sentence is doing both jobs and the paper no longer distinguishes them.**
Read as design, it is correct and needs no evidence. Read as measurement — which
its placement invites, sitting inside a *"two honest qualifications"* passage
that is entirely about what the data show — it asserts a responsiveness the data
do not resolve.

### Why this is a task and not a clause

The three available positions are different papers:

1. **Keep it as an explicit design claim**, marked as such, and say the
   magnitude of the response is unmeasured. Requires deciding what the paragraph
   is *for* once its measurement half is gone.
2. **Hedge it** like the other five sites. Cheap, and leaves a qualification
   paragraph that hedges a claim the protocol's own logic guarantees — weaker
   than the truth.
3. **Cut it** and let *"the direction is structural"*, two sentences later, carry
   the whole point. That sentence is already sound and already there.

**Option 3 is probably right and is not obviously right**, which is why this is
filed rather than done. Choosing it means deciding that the counterfactual adds
nothing the structural sentence does not already say — a judgement about the
paragraph, not a repair to a sentence.

**Related:** B26 (the four assertion sites, three now corrected), and §F.0i on
why the sixth site was found only after the other five landed.

---

## B31. The only copy of 240 manuscript-quoted runs is gitignored, and `git clean -xdf` destroys it silently

**Filed 2026-09-01. File, do not fix. This is the sharpest custody finding in the
phase, and it is ranked above the general durability exposure rather than folded
into it.**

### The exposure

`experiments/results/b2-2026-08-21`, `b2-s1-`, `b2-s2-` and `b2-s3-2026-08-21`
hold **60 run directories each — 240 runs.** The privileged survey of
1 September establishes that `/root/aep-phase8` holds **0** runs for all four.
**The Windows working clone is the only copy that exists, on any machine.**

`.gitignore:165-215` un-ignores each root and then re-ignores its contents
(`experiments/results/b2-2026-08-21/*`) with an allow-list of **eight** files per
root: `MANIFEST.csv`, `SHA256SUMS`, and six analysis CSVs.

```
$ git status --porcelain experiments/results/
$                       # nothing. 240 run directories, zero lines of output.
```

> **The sole copy of 240 runs sits inside a git working tree, ignored, where
> `git clean -xdf` deletes it with no confirmation — and no safety net in git
> reports their existence beforehand.**

`git clean -n` would list them. But `-n` is not the flag anyone reaches for when
the intent is "drop build artefacts", and `git status` — the command actually
used to decide a tree is safe to clean — prints **nothing**.

### Why these 240 runs and not some other 240

They carry **`\ReplicationPrevented*`**: the replication of the prevention result
across four sessions. **The only session-clustered interval in this paper that
excludes zero**, quoted in the abstract, in `06-evaluation.tex`, and twice in
`08-threats.tex`, where it is what makes *"narrowest is not weakest"* true.

This phase withdrew the kill-latency pooled *p*, showed its point estimate to be
a pooling artefact, and showed B3 was never a negative control. **What is left
carrying the prevention claim's replication is these 240 runs** — and they are
the least protected evidence in the project.

### THE POLICY IS CORRECT. THE EXPOSURE IS ITS CONSEQUENCE, NOT A DEFECT IN IT

**Recorded emphatically, because the obvious "fix" is the harmful one.**

Raw run directories **are not source** and must not be committed. The repo policy
is explicit, the trees are ~12 M each, and B5's freeze/archive discipline exists
precisely so raw evidence travels as manifested archives rather than as git
objects. The allow-list — un-ignore the root, re-ignore its contents, readmit the
manifest and the analysis CSVs — is **exactly right**, and is what lets
`check_paper_numbers.py` run in CI at all.

> **Nobody should "fix" this by loosening `.gitignore`.** Tracking the runs would
> discharge a durability exposure by breaking the archive discipline, inflate the
> repository by an order of magnitude, and put uncheckpointed WAL files under
> version control. **That is a worse outcome than the risk it removes.**

The finding is not that the ignore rules are wrong. It is that **"correct policy"
and "invisible to every safety net git offers" are the same configuration here**,
and nothing currently records that they coincide.

### The remedy is custody, not git

An off-root archive of these four collections removes the exposure completely and
leaves `.gitignore` untouched. They are **48 M uncompressed, ≈ 2.4 M at the
measured ≈ 21:1**. See `reports/phase-report-9-offhost-options-2026-09-01.md`.
**No option there has been authorised or acted on, and this entry does not
authorise one.**

**Until then** the operational rule is one line, and belongs wherever
contributors are told how to clean the tree: **never run `git clean -xdf` in this
repository.** Use `git clean -nxd` and read it first.

> ### GUARD APPLIED 2026-09-01 — AND HOW TO REMOVE IT
>
> An inheritable deny of `DELETE` is now set on all four roots for the current
> user (B31a establishes why this form and not the obvious one). **`.gitignore`
> is untouched.**
>
> ```
> AzureAD\HamzaKhan:(OI)(CI)(DENY)(DE)     # on all four b2-*-2026-08-21
> ```
>
> **REVERSAL — recorded here so nobody has to rediscover it:**
>
> ```
> powershell -ExecutionPolicy Bypass -File phase8-driver/apply_clean_guard.ps1 -Remove
> ```
>
> or by hand, per root:
>
> ```
> icacls "<root>" /remove:d "*<SID>" /T
> ```
>
> Inspect with `-Show`. **If a legitimate operation fails inside these roots with
> `Invalid argument` or `Access is denied` on a delete, this guard is why** —
> remove it, do the work, re-apply. Do not work around it by loosening
> `.gitignore`.

### Rank

Above the general durability finding because it differs in **kind**. General
durability is *"one machine failure ends the ability to re-derive."* This is
**one routine command, run for an unrelated reason, with no warning from the tool
that issues it, destroying evidence that exists nowhere else.** The general
exposure needs a hardware event. This one needs a habit.

**Related:** custody inventory §5c–§5e (derivation), B5 (freeze portability),
B27 and B28 (the claims these runs carry).

### B31a. A mechanism exists, and it is not a git mechanism

**Amended 2026-09-01. Established by test, not by reading documentation.** The
entry above offers *"use `git clean -nxd` and read it"*, which is a **discipline,
not a mechanism** — and this phase has established four times that a discipline
held only by its author fails. Four candidates were tested in scratch
repositories outside this tree. **Three fail. One works.**

#### Candidate 1 — `git clean`'s nested-repository skip: WORKS, but not usably

`git clean` refuses to delete a directory that is itself a git repository unless
`-f` is given twice. **Verified, including inside an ignored tree:**

```
$ git clean -xdf
Removing experiments/results/b2-x/marked_run/     <- .git was an empty dir
Removing experiments/results/b2-x/plain_run/
                                                  <- nested_run/ SURVIVED
```

**Two things this test established that reading the manual would not.** An
**empty `.git` directory is not enough** — `marked_run/` had one and was deleted;
the protection requires a genuine repository. And the protection **does** survive
`-x`, which was not obvious, since `-x` otherwise makes ignored content fully
eligible.

**Rejected anyway.** `git clean` removes the run directories *individually* —
the roots themselves hold tracked files (`SHA256SUMS`, `MANIFEST.csv`) and are
never removed. So protection would require **240 nested repositories, one per run
directory.** That is elaborate, it puts a `.git` inside every frozen run
directory, and it invalidates the directory contents against any future manifest.

#### Candidate 2 — a `pre-clean` hook: DOES NOT EXIST

`git help hooks` contains **zero** occurrences of the string "clean". Git has no
`pre-clean` hook and no hook that fires on `git clean` at all. **There is nothing
to write.** Recorded so nobody looks again.

#### Candidate 3 — `skip-worktree` / `core.excludesFile`: NOT APPLICABLE

`skip-worktree` is a bit on **index entries** and applies only to **tracked**
files. The run directories are untracked, so there is no index entry to set it
on.

`core.excludesFile` is another way to express *ignore*, and the run directories
are **already ignored** — which is precisely why `-x` reaches them. **No
ignore-based mechanism can help here, because `-x` exists to override exactly
that.** Any approach in this family is a category error.

#### Candidate 4 — filesystem permissions: **WORKS. This is the mechanism.**

**The obvious form fails and the test is why it was worth running.** A deny of
`DC` (delete-child) on the root **does not work** — `git clean -xdf` deleted the
run directories anyway, because deleting a child requires `DELETE` on the child
*or* `DELETE_CHILD` on the parent, and the children still granted `DELETE` by
inheritance.

The **inheritable deny of `DELETE` itself** works:

```
icacls <root> /deny "*<SID>:(OI)(CI)(DE)"

$ git clean -xdf
warning: failed to remove res/run_a/x.sqlite3: Invalid argument
warning: failed to remove res/run_b/x.sqlite3: Invalid argument
after: run_a  run_b  SHA256SUMS          <- both survived, contents intact
```

**Four commands, one per root. `.gitignore` is not touched.** The archive policy
stays exactly as it is: no raw run enters the index, no WAL is versioned, the
allow-list is unchanged.

**Verified not to break what must keep working:** reads succeed, and `tar`
archives the protected directories normally — so **this does not obstruct the
copy it is meant to bridge to.** Creating new files inside the root also still
succeeds.

**Costs, stated rather than discovered later.**

- It **also blocks legitimate deletion** inside those roots. For collections that
  are *declared frozen and carry a `SHA256SUMS`*, that is arguably the semantics
  they should always have had — **it makes an existing declaration enforceable
  rather than adding a new constraint.** Reversible with `icacls /remove:d`.
- A tool that rewrites a file by **delete-then-rename** rather than truncating
  will fail inside these roots. Not observed, but not excluded.
- **It is a Windows ACL.** It protects the four 21 August roots, which is exactly
  the scope of B31, and it does **nothing** for the `/root` trees — which do not
  need it, since they are not inside a git working tree.
- **It stops accident, not intent.** Anyone can remove the ACE. That is the
  correct threat model: B31 is about a routine command run for an unrelated
  reason, not about deliberate deletion.

#### Verdict

> **A mechanism exists that keeps the policy intact: an inheritable deny-`DELETE`
> ACE on each of the four 21 August roots. It is four commands, it touches no git
> configuration, and it defeats `git clean -xdf` under test.**

**Not applied.** This entry establishes that the mechanism exists and what it
costs; applying it is a change to the working tree and is a separate decision.
The discipline in B31 remains the answer until then, **and is now known to be a
fallback rather than the only option.**

**Method note.** All four candidates were **tested in throwaway repositories
outside this tree**, never in it, and the scratch directories were removed. Three
of the four behaved differently from what their documentation implied — the empty
`.git` that did not protect, the `DC` deny that did not block, and the
nested-repo skip that *did* survive `-x`. **Reading the documentation would have
produced the wrong answer in all three cases**, which is the entry's transferable
result.

---

## B32. `custody_survey.sh` over-counts run directories, in the reassuring direction

**Filed 2026-09-01. File, do not fix. Fail-closed form recorded below, not
built.**

The 1 September privileged survey reported:

```
matrix     runs= 433  db= 432 wal= 432 shm= 432 [OK]  262M
```

**433 run directories against 432 ledgers — and the triple check said `OK`.**

### The defect

`detail()` counts run directories as

```sh
runs=$(find "$root" -mindepth 1 -maxdepth 1 -type d \
         ! -name analysis ! -name voided | wc -l)
```

— an exclusion **by name, of two names**. Any other non-run directory inside a
root is counted as a run. The extra one here is `matrix/analysis-interim/`, a
derived-products directory dated 7 August holding an earlier `per-execution.csv`,
`table-1.csv` and two figure PDFs; `phase8-driver/matrix_ledger_gap.sh`
identifies it. **`matrix` is exactly 432**, which is the number the manuscript
uses.

The `[OK]` is not a second opinion. It compares `db`, `wal` and `shm` **to each
other**. Three counts that agree can all disagree with the run count without the
check noticing, because **nothing compares the ledger count to the run count.**

### The direction is the finding

> **It reports MORE evidence than exists.** For a tool whose only job is to
> establish whether the evidence still exists, that is **the worst available
> direction of error.**

An under-count provokes investigation. An over-count is consistent with
everything being fine, and is what a reader of a custody report hopes to see. A
root that had **lost a run and gained a stray directory** would read as intact:
`runs=432, db=432`, clean `[OK]`.

This is F.0d's fail-open class **in the same tool, on a second axis.** The
rewrite of 1 September fixed the permission axis — `ABSENT` versus `UNREADABLE`,
after the first version reported a tree holding 432 runs as holding nothing — and
left this one. **Fixing one fail-open path in a tool is not evidence that the
tool fails closed.** That is the transferable lesson, and the reason this is
filed separately rather than as an amendment to the custody report.

It is also the **third instrument in this phase to fail open**: `claim_sweep.py`
(B29a), `custody_survey.sh` twice, and `history_check.sh` (custody report §5f) —
the last of which failed open **one function below its own header comment
forbidding it.**

### The fail-closed form, recorded and not built

**Do not compare two counts. Compare two name-sets, and report the difference by
name.** For each root: the set of subdirectories, and the set of subdirectories
containing a `*.sqlite3`. Emit the symmetric difference. Anything in the first
and not the second is either a stray directory or a lost ledger, and the tool
**cannot tell which** — so it names it and exits non-zero rather than folding it
into a total.

This is the same construction as the **orphan gate**, and as the `fsync-always`
determination in custody report §5b — which is why that determination is
trustworthy while `runs=433` was not: **two independently produced sets, exact
equality, no threshold.** A count of 6 there would have been satisfied by six
unrelated directories, exactly as `runs=433` was satisfied by a directory that is
not a run.

**Not built**, per this phase's file-do-not-fix discipline, and because the one
number it would have corrected is already corrected by hand.

**Related:** F.0d (fail-open class), F.0c, B29a, and custody inventory §5e.

---

## B33. A credential search that over-reports, and the general form the backlog has been missing

**Filed 2026-09-01. File, do not fix.** No remediation is proposed here and none
has been performed; **rotation is deferred by the operator's decision.**

### The instance

Asked whether a `sudo` password had reached anything durable, I searched the
Claude Code session transcripts for a password-shaped token with
`grep -cE "hamza[0-9]{3}"`. It reported hits in **sixteen** transcript files.

**Fourteen were false positives.** The git remote is
`hafizmirhamza276-lab`, so **every transcript containing the repository URL
matched** — `hamza276`. The narrowed pattern finds the credential in **two**
files.

> **Acting on the count of sixteen would have meant rewriting fourteen files of
> project record to remove a string that was never in them.**

Those transcripts are the durable record of this work: the derivations, the
retractions, the corrections that this backlog cites. Redacting fourteen of them
to remove a phantom would have destroyed audit trail to fix nothing.

### Why this one is new, and why it belongs at the same rank as the others

**Every fail-open case filed so far errs toward reassurance.** `pgrep` matching
nothing (R1). `claim_sweep.py` returning two of four and exiting 0 (B29a).
`custody_survey.sh` printing `ABSENT` for a denied tree, and later over-counting
runs (B32). The search in F.0f that could not distinguish *"does not reproduce"*
from *"I did not try that ordering"*. Each of them makes a situation look
**resolved**.

**This one errs toward alarm, and it is exactly as dangerous**, because of what
its output would have authorised. A cautious-looking result is not a safe result.
**An over-reporting credential search justifies a destructive action.**

### THE GENERAL FORM

> **A check's error direction must be evaluated against what its result
> AUTHORISES, not against whether the error looks cautious.**
>
> - **A check whose output triggers DELETION, redaction, or rollback must
>   UNDER-report.** A false positive destroys something real.
> - **A check whose output triggers COMPLACENCY — "the evidence is intact", "the
>   claim is supported", "the process is gone" — must OVER-report.** A false
>   negative leaves something broken while asserting it is fine.
>
> **Same principle, opposite directions.** Which one applies is determined by the
> **consequence of the output**, never by the tool's subject matter and never by
> which direction feels more careful.

This is why "fail-closed" alone is an incomplete instruction, and why F.0d needs
this amendment rather than another instance. **"Fail closed" is a shorthand for
"fail toward the answer that does not authorise an irreversible act"** — and for
a search that licenses deletion, that direction is *fewer hits*, not more.

The custody tools and the claim tools in this backlog all sit on the
complacency side, which is why every prior entry points the same way. **Nothing
in the record before this said the direction was contingent.** It reads as though
over-reporting were always the safe error, and for the next tool built here that
would be wrong.

### Companion instance: `history_check.sh`, and the tightest case yet

The same session produced the opposite error in the same task.
`phase8-driver/history_check.sh` was written to answer *"did the password reach
any shell history file?"* Its first version:

```sh
if [ ! -e "$f" ]; then
    echo "  ABSENT: $f"
    return
fi
```

`[ ! -e "$f" ]` is **true for a path whose parent is `0700`.** Run unprivileged
it reported `ABSENT: /root/.bash_history` — the fail-open, complacency-side
error, in a credential check, in the same script whose header block reads:

> *"the whole point of a fail-closed survey is not to assert an absence it has
> not checked."*

**The violation is one function below the sentence forbidding it, in the same
file, written in the same sitting.**

This is the **fourth recorded instance** of the author-is-weakest-enforcer
pattern — after the B9 unit-3 tally-as-support defect written one commit after
committing to remove that exact pattern, `custody_survey.sh`'s original
fail-open, and `claim_sweep.py` (B29a). **It is the tightest of the four, and the
only one where the prohibition already existed in the same file when the
violation was written.** The other three violated a rule stated elsewhere or
stated later; this one violated a rule the author had just typed, inches away.

**Both errors, in one task, in opposite directions.** That is the argument for
the general form above: the author of a tool cannot reliably reason about its
error direction from the tool's subject, because the subject was identical in
both cases and the correct direction was not.

**Related:** F.0d (fail-open class — **amended by this entry, not merely
instanced**), F.0c, B29a, B32, R1, and custody inventory §5f.

---

## B34. Documentation is a claim about behaviour, and a claim is not an observation

**Filed 2026-09-01. Ranked with the F.0d family**, because it is the same
structural failure — **a source that appears to answer the question, answering a
different one** — with the source being a manual rather than a check.

### The evidence: three of four candidates behaved differently from their documentation

While establishing a mechanism for B31, four candidates were tested in throwaway
repositories. **Three contradicted what reading the documentation would have
predicted, in both directions.**

| # | what the docs support believing | what the test showed |
|---|---|---|
| 1 | `git clean` skips a directory containing `.git` | **An empty `.git` is not enough.** `marked_run/` had one and was deleted. The check validates a *repository*, not a *directory name* |
| 2 | The nested-repo skip is an *untracked*-directory protection, so `-x` would defeat it | **It survives `-x`.** A genuine nested repo inside an ignored tree **survived `git clean -xdf`** |
| 3 | Denying `DC` (delete-child) on a directory prevents deleting its children | **It does not.** Deletion needs `DELETE` on the child *or* `DELETE_CHILD` on the parent; the children still granted `DELETE` by inheritance, and `git clean -xdf` removed them |

**Two of the three would have caused a wrong decision, in opposite directions.**
(1) and (3) would have produced a guard **believed to work and not working** —
the worst possible outcome for a guard, since it converts a known risk into an
unknown one. (2) would have caused a **usable mechanism to be discarded**
unexamined.

**And the fourth was verified rather than assumed too**, which is why it is the
one that shipped.

### THE GENERAL FORM

> **Documentation is a claim about behaviour. A claim is not an observation.**
>
> A manual describes what the authors intended, at some version, under
> assumptions it does not enumerate. It is **evidence about behaviour, not
> behaviour** — the same relationship a paper's prose has to its data, which is
> the distinction this entire backlog exists to police.

The project already refuses to let a claim stand on its author's account of it:
F.0 requires the precision beside the result, B29a rejects a tool's silence as
evidence of completeness, and the standing adversarial pass exists because **the
author of a rule is its weakest enforcer.** A tool's manual is exactly that —
**its author's account of its behaviour** — and it has been getting an exemption
no other claim in this project gets.

### The standing method: throwaway verification outside the tree

> **Any mechanism this project relies on is verified by test in a throwaway
> location outside the working tree, before it is relied upon. Not just git's —
> any of them.**

Four properties made it cheap enough to be non-negotiable here:

1. **Outside the tree.** Scratch repositories under `/tmp` and a scratch
   directory on `D:`, all removed afterwards. No test touched a results root.
2. **The destructive operation is run for real**, not in dry-run. `git clean -xdn`
   listed `nested_run/` as removable; **`git clean -xdf` did not remove it.**
   **The dry run was wrong**, which is itself a fourth documentation-versus-
   behaviour gap, and it is the one that would have been trusted most.
3. **The blast radius is engineered to be nil.** When the guard had to be
   verified on the real tree, the probe created **its own directory** rather
   than testing against a run directory — because the direct test destroys 60
   irreplaceable runs if the answer is no. **Never test a guard by risking the
   thing it guards.**
4. **The check is chosen for what it can distinguish**, per B33. `git clean -nxd`
   still lists all 402 entries with the guard active, because an ACL changes
   git's *ability* and not its *intent*. It cannot tell guarded from unguarded,
   so it is fail-open for this question and was not used as the verification.

### What this does not license

**It is not an argument for testing everything.** It applies to **mechanisms
relied upon** — things whose failure is silent and whose correctness is assumed
between the moment of adoption and the moment of loss. A guard, a gate, a
freeze, a manifest. Not every library call.

The distinguishing property is the one from B33: **what does believing this
authorise?** A documentation claim that authorises "we are now protected" must be
observed, because nothing downstream will ever check it again.

**Related:** F.0d and B33 (error direction), B29a, B31a (the four tests), R2
(validate a gate against a known answer first — **this is R2 applied to
third-party mechanisms rather than to our own**), and R6.

---

## B35. Should a root declared frozen be enforceably frozen?

**Filed against Phase 12. A question, not a defect. Do not act on it.**

The B31 guard denies `DELETE` inside four result roots. **That semantics —
deletion refused inside a root that carries a `SHA256SUMS` and a `MANIFEST.csv`
and is described everywhere in this project as *frozen* — is arguably what those
roots should have had from the moment they were frozen.**

Today "frozen" is a **declaration**: a manifest is written, the prose says the
root is closed, and nothing in the filesystem distinguishes a frozen root from a
live one. The guard makes it a **property** for four roots, and it does so as a
side effect of an unrelated exposure — `git clean`. **The four roots that now
have it are the four that happened to be single-copy and gitignored, not the four
that most needed enforcement.** That distribution is an accident.

### What the question actually is

**Not** "should we apply the ACL everywhere" — that is the cheap answer and it is
probably wrong. The real question is what *frozen* is supposed to mean:

1. **A declaration**, as now: freezing is a claim, and a manifest is how the
   claim is checked after the fact. Cheap, uniform, and **detects** violation
   rather than preventing it.
2. **A property**: freezing sets permissions, and a violation fails at the point
   of attempt. Prevents rather than detects — but it is **per-platform** (an
   NTFS ACL does nothing for the `/root` trees on ext4), it must be lifted for
   legitimate regeneration, and **a freeze that is routinely lifted is a freeze
   in name only.**
3. **Both, with the manifest as the authority** and permissions as an advisory
   guard whose absence is not treated as evidence of anything.

### Why it is a Phase 12 question and not a task

Choosing (2) or (3) means deciding what happens when regeneration must write into
a frozen root — which happens, and which `regen_into_repo.sh` exists because of.
It also means deciding whether `freeze_results.py` acquires a platform-specific
step, and whether a root without the guard is thereby *not frozen* or merely
*unenforced*. **That last one is the trap**: if the guard's presence becomes
evidence of frozen-ness, its absence becomes evidence of the opposite, and
**absence-as-evidence is exactly the fail-open shape this backlog keeps filing**
(B29a, B32, B33).

**Do not resolve this by extending the guard.** The guard is scoped to B31's
threat model — a routine `git clean` in a git working tree — and the `/root`
trees are not in one.

**Related:** B31, B31a, R6, B5 (freeze portability), and B15 (what `SHA256SUMS`
does and does not cover — it names **zero** run directories, which is why the
declaration is weaker than it reads).

---

## B36. B33's class in investigation rather than in tooling, four days after B33 was filed

**Filed 2026-09-01. The near-miss is the entry; nothing is broken.**

### What happened

Opening B5, the first question was which committed manifests carry CRLF. The
check was:

```sh
CR=$(grep -c $'\r' "$f")
```

It reported **CRLF on every line of all eleven `SHA256SUMS`**, and on all eleven
`MANIFEST.md`. **Every one of those results was false.** The shell consumed the
`$'\r'`, `grep` received an effectively empty pattern, and an empty pattern
matches every line. The count printed was the line count.

The truth, read at byte level: **0 CR bytes in all eleven files.**

### What it would have authorised

**A plan opening with "all eleven committed manifests are corrupt."**

From there the natural next step is repair, and repair of a `SHA256SUMS` means
**rewriting a frozen manifest** — which the project's oldest standing rule
forbids outright, and which would have destroyed the integrity record for
eleven roots to fix a defect that does not exist. The eleven roots verify today;
`sha256sum -c` returns **16/16 OK** on `b2-2026-08-21` from Windows.

> **An over-reporting check, authorising a destructive action, against frozen
> artefacts.** That is **B33's general form**, arrived at independently, four
> days after B33 stated it.

### The new part: it was not in a tool

B33's instances are all **tools** — `pgrep`, `claim_sweep.py`,
`custody_survey.sh`, `history_check.sh`, the transcript search. Each was written,
committed, and could be reviewed. **This one was an ad-hoc shell command typed
mid-investigation and never committed anywhere.**

That is worse in the way that matters: **a tool's defect is discoverable by
reading the tool. An investigative command's defect is discoverable only by
doubting its output.** There is nothing to review. It runs once, produces a
number, and the number becomes a premise.

### How it was caught, which is the reusable part

Not by suspicion, and not by re-running it. **By looking at the bytes:**

```
$ head -4 experiments/results/matrix/SHA256SUMS | cat -A
...  MANIFEST.md$
...  analysis/comparisons-vs-aep-full.csv$
```

`$` at end of line and no `^M` — LF, and forward slashes. **The tool's count and
the file's bytes disagreed, and the bytes won.** The confirmation was then run
through a second, independent instrument (`open(f,'rb').read().count(b'\r')`),
which agreed with the bytes and not with `grep`.

### THE TRANSFERABLE RULE

> **`check-what-it-authorises` applies to investigation as much as to tooling.**
>
> **A result that would justify touching frozen artefacts must be confirmed at
> the byte level before it is believed.** Not re-run — *confirmed by a different
> instrument*, because re-running a wrong command reproduces the wrong answer
> with increased confidence.

The asymmetry that makes this cheap: **confirming costs one command; acting on a
false positive costs the artefact.** There is no symmetric case for skipping it.

**Corollary, from B5's harness the same day:** the verification script's *first*
run also reported a failure that was not real — a missing `--label`, not a
portability defect. **That one was correct behaviour**, because a verification
check authorises "the fix is good" and must therefore over-report failure. **Two
false alarms in one task, one a defect and one a feature, distinguished only by
what the output would have authorised.** That distinction is the whole content
of B33 and it earned its keep here.

**Related:** B33 (**this is its class; the entry generalises from tooling to
investigation**), B32, B34 (documentation is a claim — here, *a tool's output* is
a claim), R2, and B5.

---

## B37. `import redis` succeeds while redis-py is absent, because the repo has a `redis/` config directory

**Filed 2026-09-01. B33's class. File, do not fix.**

Run from the repository root, with redis-py **not installed**:

```python
>>> import redis          # succeeds
>>> redis.__file__        # None
>>> redis.__path__        # ['D:\...\Research-paper-AEP\redis']
$ pip show redis          # Package(s) not found: redis
```

`redis/` at the repository root holds **Redis configuration** —
`phase2.conf`, `phase2-always.conf`, `toxiproxy.json`. It has no `__init__.py`,
so Python resolves it as a **namespace package** and `import redis` succeeds
against a directory of `.conf` files.

**It shadows nothing.** A real `redis` distribution wins, because the import
system prefers a regular package over a namespace portion. **The defect is
entirely in the negative direction: `import redis` cannot be used to establish
that redis-py is present**, and it fails in the reassuring direction — the
availability check says *yes* when the answer is *no*.

This was live during B21: `import redis` succeeded, `from redis.asyncio import
Redis` did not, and the two together are confusing precisely because the first
looks like proof the second should work.

### The part worth recording

> **This is invisible from the checking code's own source.** A reviewer reading
> `import redis` sees a correct availability test. **Whether it is correct
> depends on the repository's directory layout** — on a sibling directory with a
> colliding name, created for an unrelated reason, by someone not thinking about
> imports.
>
> **The check and the thing that breaks it are in different files, and nothing
> links them.** No amount of reading the check reveals the defect; only running
> it in this tree does.

That makes it a **stronger** instance than B33's others, all of which are
diagnosable by reading the tool. It is the same shape as B21 itself — a build
that reads state from a directory it claims not to compile in — and the same
shape as `TEXINPUTS` recursion: **a namespace made larger than intended, silently
capturing a name.**

**Fail-closed form, not built:** test for the attribute you need
(`importlib.util.find_spec("redis.asyncio")`, or check `redis.__file__ is not
None`), never for the bare package name. **Better: do not use `import X` as a
proxy for "X is installed" at all** — ask the package database.

**Not fixed**, and renaming `redis/` is **not** proposed: it is referenced by
collection tooling and by the pinned-image setup, and the rename would be a
larger change than the defect. Recorded so the next person who sees `import
redis` succeed does not conclude redis-py is available.

**Related:** B33 (error direction), B32, B34, B21.

---

## B38. `paper/main.log` is the third stale artifact, and it is why the direct gate invocation still lies

**Filed 2026-09-01. Companion to B21's `main.aux`/`main.bbl`. File, do not fix.**

B21 step 1 deleted `paper/main.aux` and `paper/main.bbl`, both dated 10 August.
**`paper/main.log`, 45 077 bytes, same date, was not named and remains.**

**It is the one that matters most for the gate's honesty.**
`check_paper_numbers.py:257` reads `build_dir / "main.log"`, and `--build-dir`
defaults to `--paper`. So a direct invocation still evaluates *"no undefined
references or citations"* against a **10 August** log — which predates the three
`\cite` keys `07-related.tex` now uses, and therefore **passes by knowing nothing
about them.**

With `main.bbl` deleted the direct run now fails *"main.bbl exists"* and so
**announces** its incompleteness. **`main.log` alone would not have done that**:
it would have gone on silently producing a green bibliography verdict from
three-week-old evidence. **Deleting two of three artifacts made the remaining
defect louder by accident, not by design.**

### Is deleting it safe? Yes — established, not assumed

| consumer | reads | verdict |
|---|---|---|
| `check_paper_numbers.py:257` | `build_dir/main.log` | reads it, and **should not** — the value is exactly the harm |
| `build_paper.sh:120,135,136,139` | `${JOB}.log` **in the scratch directory** | unaffected; never reads `paper/main.log` |
| `build_paper.sh:163,166` | **writes** it | regenerates and promotes it on every clean build |

**It is gitignored** (`.gitignore:97` covers `paper/*.aux`; the `.log` pattern
sits alongside), **untracked, and regenerated by any successful build.** Nothing
depends on the stale copy; the only thing that reads it is the check it
misleads.

**Not deleted here**, because the instruction named two files and this is a
third. **Recommendation, for a decision rather than an action: delete it, and
prefer B21's item 3 — refuse to build, or refuse to check, while untracked
build products are present in `paper/`.** Deleting all three by hand is a habit;
the refusal is a mechanism, and this project has spent the phase establishing
the difference.

**Related:** B21 (items 1 and 3), B33, and the amendment recording that the
directly-invoked `17 passed, 1 failed` baseline was partly vacuous.

### CLOSED 2026-09-01 — deleted, and the file deleted was not the stale one

**`paper/main.log` is gone.** One nuance worth recording, because it changes what
the deletion accomplished: **by the time it was deleted it was fresh, not stale.**
Promotion ran first, and `build_paper.sh:163,166` rewrites `paper/main.log` on
every clean build, so the 10 August file (45 077 bytes) had already been replaced
by a 1 September one (45 458 bytes).

**So this deletion did not remove stale evidence — it removed the *mechanism* by
which evidence goes stale unnoticed.** A fresh log makes the direct invocation
*correct today* and silently wrong the moment any source changes. Deleting it
makes the direct path fail loudly and permanently instead:

```
FAIL  main.log exists
```

**That is the intended end state, not a regression.** The direct invocation was
never a valid gate — `--build-dir` defaults to `--paper`, so it reports on
whenever the last promotion happened to be. It now says so out loud.

**Verified after deletion:** `build_paper.sh` unaffected at **18 passed, 0
failed** (it reads its scratch log); direct invocation **17 passed, 1 failed**
under WSL, the single failure being `main.log exists`.

---

## B39. A partial fix surfaced a defect a complete one would have concealed

**Filed 2026-09-01. An observation, not a defect. It argues against the usual
instinct, which is why it is recorded rather than left as a nice coincidence.**

### What happened

Three stale artifacts sat in `paper/`, all dated 10 August: `main.aux`,
`main.bbl`, `main.log`. B21 named all three. **Two were deleted and one was
not**, because the instruction named two.

That accident is what exposed the third.

| what was deleted | what the direct gate invocation did |
|---|---|
| **none** | `17 passed, 1 failed` — bibliography and citation checks **silently** computed from a three-week-old log. Looked healthy |
| **`main.aux` + `main.bbl`** | `14 passed, 2 failed` — **`FAIL main.bbl exists`**. The gate announced that it had nothing current to check against |
| **all three** | would have been `FAIL main.bbl exists` **and** `FAIL main.log exists` — correct, but the `main.log` failure arrives folded into a batch, indistinguishable from the `.bbl` one |

**The middle row is the informative one.** Removing `main.bbl` forced the checker
to *speak*, and what it then said — *"missing `paper/main.bbl`; run bibtex
first"* — is what made it obvious that `main.log` was being read from the same
directory under the same defaulting rule. **With all three gone, that inference
still lands, but nothing distinguishes which artifact taught it.** With none
gone, nothing is learned at all.

### The general form

> **Fix one thing at a time and watch what changes.** A partial fix leaves the
> system in a state neither the before nor the after would produce, and that
> state is often the most diagnostic one available — the remaining defect is
> forced to act alone, against a background that has just moved.
>
> **A complete fix removes the defect and the evidence of it together.** The
> system goes green and nothing is learned about *why* it was red, or which of
> the several things changed was load-bearing.

This is the same reasoning as the design floor and as B9's session-clustering:
**a change that moves several variables at once cannot attribute the result.**
Applied to repair rather than to measurement, it says: **repair one variable,
observe, then the next.**

### Where it does and does not apply

**Applies** when the defects are independent and the system reports its own
state — a checker, a gate, a build. The partial state is observable and cheap.

**Does not apply** when a partial fix leaves the system in an *unsafe* state
rather than merely an informative one, or when the defects interact so that
fixing one masks the other. **Nothing here argues for shipping partial fixes.**
It argues for **passing through** partial states deliberately and reading them,
rather than batching every repair into one commit and learning nothing from the
transition.

**Counter-note, so this is not read as tidier than it was:** this was **not
planned**. The instruction named two files; the third was omitted for an
unrelated reason. **The lesson is real and the method was an accident**, and
saying so is the difference between a finding and a story told afterwards.

**Related:** B38 (the instance), B21, B33, and F.0d — where the same structure
appears as *"a failed check that passes when it does nothing"*.

---

## B40. A check whose validity depends on what ran before it, in a different file

**Filed 2026-09-01. A category this backlog did not have.**

`.github/workflows/ci.yml:329-334`:

```yaml
- name: Build the manuscript
  run: bash scripts/build_paper.sh

- name: Gate -- the manuscript's numbers against the frozen CSVs
  # build_paper.sh ends by running this too. It is repeated as its own
  # step so the verdict is a named, separately-reported result rather
  # than the tail of a build log -- and so that a later edit to the
  # build script cannot quietly remove the check.
  run: uv run --frozen python scripts/check_paper_numbers.py
```

**The second step was added as a safeguard, and its comment says so.** The
reasoning is sound: if the check only ever ran inside `build_paper.sh`, someone
editing that script could remove it and nothing would notice.

**But it takes no `--build-dir`**, so until 2026-09-01 it read whatever sat in
`paper/`. In CI that is fresh — the build promoted seconds earlier. **Anywhere
else it is whatever the last promotion left**, which is how a `17 passed, 1
failed` computed from three-week-old artifacts was quoted as a control through
two phases.

### Why this is not B37 or B38

| | |
|---|---|
| **B37** (`import redis`) | wrong **everywhere**, for a reason invisible in the check's own file |
| **B38** (`main.log`) | a **stale input** — the same check, given older data |
| **B40** | **correct in isolation, correct in CI, wrong everywhere else** — and which one you get is decided by *what ran before it* |

> **The command is identical in all three cases. Only its predecessor differs.**

Read on its own, the step is right. Read in the CI file, it is right. **Its
validity is a property of the sequence, and neither file states the dependency.**
The safeguard comment explains why the step exists and says nothing about what
must precede it — so the one fact a reader needs to judge it is in neither place.

### The general form

> **A check can be correct as written and still be worthless, if its correctness
> depends on state established by a caller that does not know it is establishing
> it.** Reviewing the check tells you nothing. Reviewing the caller tells you
> nothing. **The defect exists only in the composition**, and nothing in this
> project reviews compositions.

This is the shape B21 itself has — a build that reads state from a directory it
claims not to compile in — and the shape `TEXINPUTS` recursion has. **It is a
recurring structure, not three coincidences: a dependency that is real,
load-bearing, and written down nowhere.**

### Was the safeguard vacuous?

**Not entirely, and the distinction matters.** It genuinely protected against
*"someone deletes the check from `build_paper.sh`"* — that was its stated
purpose, and it would still have caught it.

**What it did not do is what its name implies.** *"Gate — the manuscript's
numbers against the frozen CSVs"* reads as an independent verification. It was
a re-run of a check whose inputs the preceding step had just written, so it
could not disagree with that step about the bibliography. **It duplicated a
verdict rather than confirming it.**

### Status

**Resolved for this instance by B21 item 3**, which makes the second step verify
provenance and therefore genuinely independent of ordering: it now passes only
if the artifacts match the sources, whoever produced them and whenever.

**Not resolved as a class.** Nothing detects the next check whose validity is
carried by its caller. **No fix is proposed** — a general mechanism for this is
not obviously cheaper than the defect, and inventing one here would be building
on a sample of three.

**Related:** B21 (item 3 resolves the instance), B37, B38, B33, and R6 — where
`git clean -nxd` is recorded as unable to verify a guard **for the same reason
in reverse**: the command is correct, and what it can tell you depends on state
it does not control.
