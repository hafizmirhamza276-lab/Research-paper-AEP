# Phase 4B — the framing revision, the fault that was only ever named, and a hostile read

**Date:** 2026-08-07
**Roadmap section:** `PAPER_ROADMAP.md` §5 (Phase 4), under gates **G0–G4**.
**Predecessor:** `reports/phase-report-4-session1-2026-08-07.md`

> **Read this first — five things, in the order they matter.**
>
> **1. The 34 skipped tests are not a gate breach, and here is the proof rather
> than the assurance.** All 34 are guarded on `AEP_PHASE2_REDIS_INTEGRATION` /
> `REDIS_URL` (31 of them) or on a Redis that can prove `WAITAOF` support (3).
> Every one runs and passes in CI-Linux and in a locally-provisioned Windows
> tree. The green tip's gate step prints `OK: 1697 tests, 0 skipped`; fed the
> 34-skip JUnit, the same script exits 1. **Zero tests are skipped in both
> environments.** §C.1.
>
> **2. The paper's headline result now belongs to a different mechanism than
> the paper's headline mechanism.** Ablating the `WAITAOF` barrier changes
> nothing about detection over 600 executions per arm. Detection is produced by
> the durable pre-dispatch record and by a transition table with no edge back
> into the dispatching state. The barrier buys *prevention under coordinator
> loss*, which is a different quantity, on a different regime, with its own
> metric. Both are now stated that way, and the ablation is a finding in the
> abstract rather than a caveat in §8. §C.3.
>
> **3. The fault class the paper previously only named is now injected, and the
> barrier's durability claim survives it.** `dm-flakey` in `drop_writes` mode
> stops a block device accepting writes at a chosen instant. Over 90 trials in
> three replications, the `WAITAOF`-acknowledged record survived **90/90** and
> the unacknowledged one was destroyed **90/90** — against **0/10** lost under
> the process kill of the same probe. §C.2.
>
> **4. B4 and B4b complete the trilemma table, and the result is the cleanest
> statement in the paper.** B4 (durable log, vendor-default unlimited attempts)
> duplicates at 0.5889 and 0.5611. B4b (same engine, Maximum Attempts 1)
> records **zero** duplicates and loses the effect in 0.5056 and 0.5167
> instead. One configuration line moves the engine between two silent corners;
> neither reaches the third. §C.4.
>
> **5. Two batches of results were thrown away, both because of something I
> did.** The first B4/B4b collection ran while I was running the project's own
> integration suite against the same Redis — a suite that deletes the `aep:*`
> namespace and `docker restart`s the container by name. 29 runs discarded and
> re-collected on an idle host. Separately, one run in the clean batch failed
> the harness's reconciliation check and is reported **void** rather than
> silently replaced by its re-run. §E.1, §E.2.

---

## A. Gates attempted

| Gate | Requirement | Status |
|---|---|---|
| **G0** | Rule 8 start-check; enumerate the 34 skips, locate each, prove the CI gate has teeth; any test skipped in **both** environments is a breach to fix | ✅ **Done.** No breach. §C.1 |
| **G1** | Intent ledger carries detection; barrier carries **only** prevention, with its own metric and the fsync curve as a deployment choice incl. a barrier-less B3-mode; B3≡AEP-full moves to a stated finding near the abstract; `check_paper_numbers.py` covers the new numbers | ✅ **Done.** §C.3 |
| **G2** | Host-level write-loss fault in WSL2/Linux; one focused experiment; wire into §6 and the E1 fault-class statement | ✅ **Done.** §C.2 |
| **G3** | B4 and B4b on `POSITIVE_ONLY` and `NO_READBACK`, 30 reps each; trilemma table to full symmetry; figures from the fixed generators only | ✅ **Done.** §C.4 |
| **G4** | Hostile read of the **revised** draft: prevention framing, dm-flakey, author-written baselines, n=3 timing cells; list what remains undefended | ✅ **Done.** §F |
| **Rule 8** | Commit, push, green CI | ⚠️ **Partially.** Commits and green CI through `44a6d4d`; the last three commits are local because the credential helper wedged again. §E.5 |

---

## B. Files created/modified

### New

| File | What it is |
|---|---|
| `experiments/flakey_write_loss.py` | The G2 probe. Loop device → `dm-flakey` → ext4 → Redis 7.2.5 AOF. Self-tests the device before it will report a Redis trial. |
| `experiments/tests/test_flakey_write_loss.py` | 9 tests. Pin the drop table, the VOID rule and the rate arithmetic — none needs root, so none can skip. |
| `experiments/tests/test_fault_injector_isolation.py` | 8 tests. The refusal to collect beside a host-level fault injector, and the coordinator-restart detector. |
| `tests/test_paper_tables.py` | 15 tests. The number generator's arithmetic and formatting, in CI, where `check_paper_numbers.py` cannot go. |
| `scripts/build_paper.sh` | Builds the paper and treats LaTeX's two silent successes as failures. |
| `scripts/sync_measurement_tree.sh` | Keeps the Linux tree's *source* equal to the committed one without ever touching `experiments/results/`. |
| `paper/generated/table-ablation.tex` | The barrier ablation on the detection metrics. Generated. |
| `paper/generated/table-deployment-choice.tex` | Three measured configurations, one of them barrier-less. Generated. |
| `reports/raw/g0-skip-adjudication.txt` | The 34, enumerated, with the gate's negative control. |
| `reports/raw/g2-flakey-write-loss.txt` | The write-loss probe's full stdout and pooled analysis. |
| `experiments/results/voided/` | One run, and a README saying why it is not counted. |

### Modified

| File | Change |
|---|---|
| `paper/main.tex` | Abstract restructured around the detection/prevention split; equivalence claim moved from a p-value to a bound. |
| `paper/sections/01,02,03,04,05,06,07,08,09` | C3/C4 rewritten; §6.2 restructured into detection / prevention / durability; §6.3 into a deployment choice; three counting errors fixed; three new threats. |
| `scripts/paper_tables.py` | New tables and macros; LOC, coverage and p-values generated; Wilson bound for the zero-count equivalence claim. |
| `scripts/check_paper_numbers.py` | Regenerates the new tables; requires the always-mode and write-loss inputs; **new gate**: fails on any generated number the manuscript never uses. |
| `experiments/run_matrix.py` | Refuses to start beside a host-level fault injector; records the coordinator's `run_id` either side of every run. |
| `scripts/fsync_always_benchmark.sh` | System list, mock-API port and clean/append are now parameters, so the ablated arm can be collected under `always`. |
| `.github/workflows/ci.yml` | `MINIMUM_TESTS` 1590 → 1700 (1729 collected). |

---

## C. Raw command outputs

### C.1 G0 — the 34 skips, adjudicated

Full transcript: `reports/raw/g0-skip-adjudication.txt`.

**Rule 8 start-check.** Working tree clean, `HEAD == origin/main`, CI green on
the tip (`d4f5c1f`, run 31169005422, 3/3 jobs).

**Where the 34 come from.** All in seven files, all guarded:

```
$ pytest <the 7 guarded files> -q -ra          # no CI env vars
19 passed, 34 skipped in 0.71s

$ REDIS_URL=redis://127.0.0.1:6381/15 AEP_PHASE2_REDIS_INTEGRATION=1 \
  AEP_PHASE2_REDIS_CONTAINER=aep-phase2-redis72 pytest <same 7 files> -q -ra
53 passed in 61.17s
```

31 of the 34 are guarded on `AEP_PHASE2_REDIS_INTEGRATION` / `REDIS_URL`; the
other 3 (`test_b3_no_barrier.py`) on a Redis that can prove `WAITAOF` support,
which `fakeredis` cannot.

**Where each runs.** CI-Linux runs all of them — the job sets both variables at
job level. The gate step on the green tip:

```
OK: 1697 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed      # main job
OK: 4 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed         # WAITAOF job
```

**Does the gate still have teeth?** Fed the JUnit from the un-provisioned run:

```
$ python scripts/check_pytest_gates.py --junit <the 34-skip JUnit> ...
GATE FAILED: 34 test(s) were SKIPPED. In CI every precondition is provisioned,
so a skip is an unmet environment assumption, not a legitimate outcome.
exit=1
```

**Verdict: no breach.** No test is skipped in both environments; every one of
the 34 executes and passes in CI-Linux, and all 34 also pass on Windows once
the same preconditions are provisioned.

### C.2 G2 — the write-loss fault

`experiments/flakey_write_loss.py`. Same probe as
`experiments/redis_durability_window.py` — one `WAITAOF`-acknowledged key, one
not — with the fault swapped from `docker kill -s KILL` to a block device that
stops accepting writes.

**The device stack, and the two flags that decide whether it measures
anything.** `dmsetup suspend` calls `freeze_bdev()`, which syncs the
filesystem, and flushes outstanding I/O; either would push the unacknowledged
write out *before* the fault took effect and produce a confident null. The
reload runs `--nolockfs --noflush`.

**The self-test, which gates every run:**

```
before_the_cut_survived          True
after_the_cut_survived           False
after_the_cut_fsync_error        None      <- the loss is silent; fsync returned 0
valid                            True
```

**The environment, read back from the live system rather than assumed:**

```
mount_options    ext4 rw,relatime          <- no nobarrier
ext4_features    has_journal ... metadata_csum
appendfsync      everysec
redis_version    7.2.5                     <- the pinned build, streamed out of the pinned image
```

The probe refuses to measure under `appendfsync always` (there is no
unacknowledged write to lose) or a `nobarrier` mount (a surviving acknowledged
write would prove nothing).

**Result, 3 replications × 30 trials:**

```
POOLED n=90  void=0  acknowledged survived 90/90  unacknowledged lost 90/90
  Within G2:  Fisher exact, two-tailed p = 2.2e-53
  Across fault classes, same probe, same two keys:
    E1 docker kill -s KILL : 0/10 unacknowledged lost
    G2 dm-flakey           : 90/90 unacknowledged lost
    Fisher exact p = 5.8e-14
```

Exposure window 12.4–61.8 ms inside a 1000 ms fsync period that a preceding
`WAITAOF` has just reset — **deliberately the widest it can be**, exactly as
the process-kill probe did. So 90/90 is the loss rate for a worst-placed cut,
not for a uniformly-timed one. That is stated in §6.2.3 and §8.

**Wired into the paper:** §6.2.3 is a new subsection; the E1 fault-class
statement in §8 changed from *"the fault class was not injected"* to a
measurement plus a named residual (emulation ≠ power cut; lying write caches).

### C.3 G1 — the framing revision

**The ablation, as a finding.** `tab:ablation` is new and generated. Over 600
crashed executions per arm, B3 and AEP-full record identical zeros on
undetected duplicates and lost effects, and declared ambiguity differing by
two executions (p = 0.95).

**The equivalence claim does not rest on p = 1.00.** §F caught this: Fisher on
0/600 vs 0/600 has no power. The claim now rests on the one-sided 95% Wilson
limit for a zero numerator, **0.64%** — each rate, and the difference between
the systems, is below that, against baselines differing from both by 77–83%.

**The barrier's own metric.** The *unwanted-applied-effect rate*: effects put
on the wire while the durability of their own intent record could no longer be
confirmed. AEP-full 0.3333, B3 0.9333, p = 1.9e-06, 18 effects prevented.
Renamed from "applied an effect" because applying an effect is not by itself a
failure.

**The cost is a deployment choice with three measured points.**

```
configuration                median   over floor   barrier   prevents  claim
AEP-full, everysec           4004.9      2004.9    1966.7      yes     detection + prevention
AEP-full, always             2063.4        63.4      15.0      yes     detection + prevention
B3-mode,  everysec           2038.2        38.2       0.0      no      detection only
```

Collecting the barrier-less arm **under `always` as well** was necessary and is
new: the alternative was subtracting an `everysec` B3 median from an `always`
AEP median, which silently assumes the ablated protocol's own writes cost the
same under both policies. They nearly do (2038.2 vs 2048.4) — but "nearly" is a
measurement, and the factor of 131 would otherwise have rested on an
assumption.

**`check_paper_numbers.py` covers the new numbers**, and gained a gate that
found things immediately:

```
18 passed, 0 failed
```

The new gate — *every generated number is used in the manuscript* — fails on
any macro defined and never referenced. That is the drift a framing revision
produces, and LaTeX is silent about it (it catches only the opposite
direction). On first run it reported 39 orphans, including pre-existing ones,
and forced the generator to stop emitting numbers nobody quotes.

### C.4 G3 — B4 and B4b complete

72 runs, 2.92 h, **zero failures**, on an idle host.

```
$ redis-cli INFO server | grep run_id      # before the batch
run_id:7dc3a9c88586a5af131b3e982401083d6aea6de4
$ redis-cli INFO server | grep run_id      # after
run_id:7dc3a9c88586a5af131b3e982401083d6aea6de4   uptime 11127s
```

Byte-identical, so nothing restarted Redis underneath it — which the previous,
discarded batch could not say.

**The trilemma table, now symmetric where it matters** (crashed regime,
`per-cell-metrics.csv`):

| system | undet. dup POS-ONLY | NONE | lost POS-ONLY | NONE | declared ambiguity |
|---|---|---|---|---|---|
| B4 durable, ∞ attempts | 0.5889 | 0.5611 | 0.0000 | 0.0111 | 0.0000 |
| B4b durable, 1 attempt | 0.0000 | 0.0000 | 0.5056 | 0.5167 | 0.0000 |
| B3 intent, no barrier | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.3667 / 0.7167 |
| **AEP-full** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.3500 / 0.7222 |

n = 180 executions per cell. One configuration line moves the engine between
two silent corners; neither reaches the third.

**Matrix now:** 398 runs, 3 440 executions, 115 cells. Re-frozen with a fresh
`MANIFEST.csv` and `SHA256SUMS`; both figures regenerated by `analyze.py`'s
fixed generators.

**Remaining gap:** B4's `AUTH` cell is n=20 and B4b has none. §8 says so and
the table prints a dash rather than interpolating.

### C.5 The suite

```
$ REDIS_URL=... AEP_PHASE2_REDIS_INTEGRATION=1 pytest experiments/ tests/ -q -ra
1729 passed, 1 warning in 110.45s
```

Zero skipped. `MINIMUM_TESTS` raised 1590 → 1700.

---

## D. Gate compliance

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| G0 | Rule 8 start-check | ✅ | §C.1 |
| G0 | Enumerate the 34, locate each | ✅ | `reports/raw/g0-skip-adjudication.txt` |
| G0 | Prove the CI gate has teeth | ✅ | negative control, exit 1 |
| G0 | Fix any test skipped in both | ✅ **none exist** | 53/53 pass provisioned |
| G1 | Ledger carries detection | ✅ | `tab:ablation`, §6.2.1 |
| G1 | Barrier carries **only** prevention | ✅ | §6.2.2, own metric |
| G1 | Unwanted-applied-effect rate, 10/30 vs 28/30, p=1.9e-06 | ✅ | `tab:killablation` |
| G1 | fsync curve as deployment choice incl. barrier-less mode | ✅ | `tab:deployment`, 3 rows |
| G1 | B3≡AEP-full as a finding near the abstract | ✅ | abstract ¶2, C4 |
| G1 | `check_paper_numbers.py` covers the new numbers | ✅ | 18 checks |
| G2 | Host-level write-loss fault | ✅ | `dm-flakey drop_writes` |
| G2 | One focused experiment | ✅ | 90 trials, 3 replications |
| G2 | Wired into §6 and the E1 statement | ✅ | §6.2.3, §8 |
| G3 | B4/B4b on POS-ONLY and NO-READBACK, 30 reps | ✅ | 180 executions per cell |
| G3 | Trilemma table to full symmetry | ✅ | §C.4 |
| G3 | Figures from the fixed generators only | ✅ | `analyze.py write_figures` |
| G4 | Hostile read of the revised draft | ✅ | §F |
| Rule 8 | Commit | ✅ | 9 commits |
| Rule 8 | Push | ⚠️ | 6 of 9 pushed; §E.5 |
| Rule 8 | Green CI | ✅ on what is pushed | run 31173895841 and later |

---

## E. Deviations

**E.1 — I contaminated the first B4/B4b batch, and discarded it.** While
collecting, I ran the project's integration suite against the same Redis. That
suite deletes the `aep:*` namespace in the database the matrix is using, and
`tests/test_phase2_waitaof_integration.py` `docker restart`s the container by
name. Several runs died with `ConnectionError`; the server was replaced
mid-batch. Runs that *failed* are harmless (no summary, re-run on resume). Runs
that *completed* are the hazard: a coordinator blip makes a re-executing
baseline retry, more retries means more duplicates, and that bias points toward
our own hypothesis. **All 29 were discarded and re-collected on an idle host.**
None reached any number in the paper.

I first attributed this to the write-loss probe's `drop_caches`, which is also
kernel-wide and was also running. That attribution was wrong and the container
restart at 16:29 PKT matches the suite, not the probe. The paper says the
suite.

Two guards were added rather than a note: `run_matrix` refuses to start beside
a host-level fault injector, and it records the coordinator's `run_id` either
side of every run so a restart is visible in the results instead of inferred
from a log line.

**E.2 — One run in the clean batch failed reconciliation and is reported
void.** A B4b cell classified all ten executions `CONFIRMED_APPLIED` against
two rows in the provider's ledger. Both siblings recorded ten; the provider
logged no error; its run-log held 3 lines against 11 for each sibling. Cause
undetermined. A re-run of the identical cell — same seed, same configuration —
agreed. It is **void** on the rule the durability probe already uses, ships in
`experiments/results/voided/` with the explanation beside it, and §6.4's
"zero reconciliation disagreements" became "exactly one".

**E.3 — I rewrote the harness under a live run before the guard existed.** The
ad-hoc sync that preceded `scripts/sync_measurement_tree.sh` rsynced
`experiments/` while the matrix was collecting. The live process had already
imported its modules, and the only changed file workers could have loaded was
`run_matrix.py`, which workers do not import. The batch's zero failures and
identical coordinator `run_id` are consistent with no effect. The guard now
refuses it outright.

**E.4 — G2 replications 1 and 2 predate the environment recording.** Only
replication 3 records the mount options and `appendfsync` read back from the
live system. The harness hardcodes both, and nothing changed on the host
between them, so the inference is sound — but it is an inference for 60 of the
90 trials and a measurement for 30.

**E.5 — Rule 8's push is incomplete.** Six commits are on `origin/main` with
green CI. The last three are committed locally and unpushed: the credential
helper wedged exactly as it did in Session 1 — `git ls-remote` works, `git
push` connects and then blocks indefinitely, and `GIT_TERMINAL_PROMPT=0` does
not make it fail fast. I declined to work around it by putting a token on the
command line. **The operator should run `git push` in a shell with a working
credential prompt.**

---

## F. The revised draft, read as a hostile TSE reviewer

Four attacks, as instructed, against the **revised** text.

### F.1 The new prevention framing

**"You have moved your headline result onto a mechanism whose evidence is one
cell."** The barrier's entire measured case is `redis-kill-preack`,
`NO_READBACK`, one crash point, 30 runs per arm, one host — with an effect size
the paper itself says is a function of that host's `docker kill` latency.
Detection, which has 600 executions per arm across three capability classes, is
now attributed to a durable write-ahead record, which is decades old.
**Status: conceded in §8**, including the consequence for novelty, which is
that the paper's most novel machinery (C2's token) serves its weakest evidence.

**"`p = 1.00` is not equivalence."** Fisher on 0/600 vs 0/600 has no power.
**Status: fixed.** The claim now rests on a 0.64% Wilson bound, and the
sentence "the barrier contributes nothing to detection" is now falsifiable —
it would be refuted by a barrier contributing more than 0.64 points.

**"B3-mode is a configuration you have shown to be worse, offered as a
choice."** **Status: defended.** The deployment table's last two columns say
exactly what B3-mode forfeits, and §6.2.2 quantifies it.

**"The unwanted-applied-effect rate is a metric you invented for a regime you
invented."** **Status: partially defended.** It is defined, generated from a
named CSV, and reported beside its denominator; but it is not a metric anyone
else uses, and the cell is not replicated on other capability classes.

### F.2 dm-flakey's result

**"Tautology: you fsynced one write and not the other, then destroyed
everything that was not fsynced."** **Status: defended.** The identical
construction under a process kill loses nothing (0/10). The construction alone
does not produce the result; the fault class does.

**"90/90 is a designed maximum."** **Status: conceded explicitly**, in §6.2.3
and §8: the window is phase-aligned to maximise exposure, so this is the loss
rate for a worst-placed cut and an upper bound on a uniformly-timed one.

**"WSL2 is five layers above hardware."** **Status: defended.** `dm-flakey`
*is* the boundary under test and everything below it is on the far side of that
boundary in both arms equally. What the layering would threaten — an absolute
fsync-latency claim — is not made from this probe.

**"You tested two Redis keys, not AEP."** **Status: conceded, and it is the
strongest of the four.** AEP-full and B3 were never run through the harness
under write loss, so no *protocol* outcome is attributed to it. The probe
establishes the premise, not the system-level consequence. Named in §8 as the
most worthwhile single extension; blocked because the harness's Redis is a
container whose bind mounts this Docker resolves in the Windows filesystem.

### F.3 Author-written baselines

**"Every system in the comparison was written by the people proposing the
winner."** **Status: disclosed, not eliminated** — as before. The artifact is
released partly so the baselines can be re-implemented.

**"B4 duplicates at 0.59 and you named it after a real product family."**
**Status: defended** by the "B4 is not Temporal" paragraph, whose scope is now
larger because B4's cells are larger. B4's re-execution policy is the vendor's
documented default and is cited as such; no claim about Temporal-the-product is
made.

**"Your central *new* finding is an ablation of your own system against
itself, so it has no external referent at all."** **Status: undefended, and
correct.** An ablation is internal by construction and that is the right
instrument for attributing a mechanism. But nothing outside this artifact
corroborates that a write-ahead record without an fsync barrier is sufficient
for detection, and a reviewer who distrusts the harness distrusts the finding
entirely.

### F.4 n = 3 timing cells

**"Four medians, three runs each, carry the barrier cost and the factor of
131."** **Status: conceded in §8**, with what it does and does not support:
direction and rough magnitude, not a distribution, which is also why the
argument is made on medians rather than the p95 column.

**"You report no uncertainty on the barrier cost or the ratio at all."**
**Status: closed, and it cost the paper a claim.** A cluster bootstrap over
runs (10 000 resamples, seeded; the unit of independence is the run, not the
execution) now accompanies both barrier figures:

```
appendfsync   barrier (ms)   95% CI
everysec          1966.7     [ 477.9, 1978.8]
always              15.0     [-1474.6,   22.7]
```

Under `everysec` the cost is comfortably positive and pinned only to within a
factor of four. **Under `always` it is not separable from zero at this sample
size.** The "factor of 131" that survived four earlier drafts of this session
is therefore not supported by these data and has been **removed from the
paper, and the macro that produced it deleted from the generator** — with a
test asserting it is not emitted, because generating it is what let it into
the prose the first time. The claim is now directional: hundreds to ≈2 000 ms
under `everysec`, and *nothing demonstrable* under `always`.

The cause is three clusters, which admit only ten distinct bootstrap
multisets, against an `always` cell with a heavy upper tail (p95 5 067.8 ms
against a 2 063.4 ms median). Closing it needs more crash-free **runs**, not
more executions per run.

### F.5 What remains undefended, in priority order

1. **The write-loss probe never ran the protocol.** Needs the harness's Redis
   on the flakey device; blocked by Docker Desktop's bind-mount resolution.
   §F.2. Now the largest hole.
2. **The prevention result is one cell.** `NO_READBACK` only, one crash point,
   one host. The other two capability classes are in the plan, uncollected.
3. **The detection finding has no external referent.** Structural to ablation;
   only independent re-implementation fixes it.
4. **The barrier's cost under `always` is unmeasured in effect**, not merely
   imprecise — its interval spans zero. Three more crash-free runs per arm
   would probably settle it and were not collected this session.
5. **B4b has no `AUTH` cell and B4's is n=20.** Table prints a dash.
6. **Declared ambiguity is still not evaluated as an operational outcome.** No
   operator study; unchanged from Session 1 and still the largest gap between
   what the paper measures and what it argues.

---

## G. What I would do next, in order

1. **More crash-free runs**, six to ten per arm per policy rather than three.
   Roughly 40 minutes, and it is what would let the paper say anything at all
   about the barrier's cost under `always`.
2. Collect the Redis-kill ablation on `AUTHORITATIVE_READBACK` and
   `POSITIVE_ONLY_READBACK` — roughly 2 h — so prevention stops resting on one
   cell.
3. Get the harness's Redis onto the flakey device (native `redis-server` in
   WSL rather than the Docker container) and re-run AEP-full vs B3 under write
   loss. This is the one that would turn §6.2.3 from a premise into a result.
4. B4b `AUTH` and B4 `AUTH` to n=180.

---

## H. Honest summary

The framing revision is done and it cost the paper something: the mechanism
the paper is architecturally proudest of turns out to be optional for the
result the paper is empirically strongest on. That is a better paper and a
weaker novelty claim, and §8 now says both.

The fault class that Session 1 named and did not inject is injected, and the
barrier's durability claim survives it cleanly — but on a probe that tests
`WAITAOF` rather than AEP, which is the single largest thing this session did
not finish.

The hostile pass was worth more than the strengthening. It removed a number:
the "factor of 31 for one configuration line" that Session 1 reported, which
this session first recomputed as 131 on a properly matched ablation and then
deleted outright when a cluster bootstrap showed the denominator's interval
spans zero. A headline figure that survived two sessions and four drafts of
this one did not survive being asked for an error bar.

Two batches of data were destroyed by my own carelessness with a shared
machine, and both are recorded rather than smoothed over. The guards that
would have prevented them are now in the runner and tested.

Rule 8 is not fully discharged: three commits are local because the credential
helper wedged, and I would rather report that than put a token on a command
line to make the table green.
