# Phase 10 — WS-0: Native Docker Engine inside WSL2, and re-baseline the measurement environment

## Read first (do not skip, do not summarise back to me)
- ../AEP_JOURNAL_READINESS_DIRECTION.md  (the external audit that directs this and all following phases; it sits one directory above the repo root)
- docs/24-revision-backlog.md  §B1 in full, especially "What blocked it here, exactly" and the Phase-8.2 addendum about redis_storage_backing
- compose.phase2.yml
- experiments/flakey_write_loss.py
- scripts/verify_redis_semantics.py
- paper/sections/08-threats.tex  §C(c) "Platform, and a development/measurement split" and §C(d) "Timing hygiene"
- PAPER_ROADMAP.md  (current phase section only)

## Context
Every number in the paper was collected on Ubuntu inside WSL2 with **Docker Desktop**, whose daemon resolves bind-mount sources in the Windows filesystem. docs/24-revision-backlog.md B1 records that this — not WSL2 itself — is what blocked running the protocol under block-level write loss: a dm-flakey device assembled inside WSL cannot be named as a bind source for a Docker Desktop container. But experiments/flakey_write_loss.py already ran 90 trials of dm-flakey successfully inside this same WSL2 kernel, so the device-mapper capability is present. The hypothesis this phase tests is therefore: **installing Docker Engine natively inside the WSL2 distribution, with Docker Desktop's integration disabled for that distribution, puts the loop device, the dm-flakey target, the ext4 filesystem and the Redis container in one namespace, and unblocks backlog item B1 without new hardware.**

This phase changes the measurement environment. It collects no new claim for the paper except one: a replication of an existing frozen cell under the new container runtime, which tells us whether the runtime change is a confound for everything collected later.

## Bounds
- In scope: scripts/ (new provisioning + verification scripts), docs/ (new files only), reports/ (new files), prompts/ (this prompt), .github/workflows/ci.yml (only if a new environment assertion is needed), PAPER_ROADMAP.md (status rows only)
- Out of scope, do not touch: experiments/results/** (frozen), paper/generated/** , paper/sections/** , aep_core/** , any existing test
- Do not modify compose.phase2.yml's pinned image digest or any pinned version. If the native engine cannot pull the pinned digest, stop and report it rather than substituting a tag.
- If you find a defect outside this scope, record it under "Findings outside scope" in the report and do not fix it.

## Steps
1. Commit this prompt verbatim as prompts/phase-10-wsl2-native-docker.md before anything else. Also copy ../AEP_JOURNAL_READINESS_DIRECTION.md into docs/26-journal-readiness-direction.md and commit it, so the repository is self-contained about what is directing the remaining work.

2. Record the CURRENT environment before changing anything, into reports/phase-report-10-env-before.md: `docker version`, `docker context ls`, `docker info | grep -i 'root dir\|storage driver\|server version'`, `docker inspect aep-phase2-redis72` (mount sources verbatim), `uname -a`, `cat /etc/os-release`, `df -T` for the repo and for /var/lib/docker, `dmsetup targets`, `lsmod | grep -i 'dm_\|loop'`, and the WSL kernel version. This is the record the paper's platform threat currently describes; it must be preserved before it is replaced.

3. Verify the device-mapper premise independently of Docker: run experiments/flakey_write_loss.py's self-test path only (the loop device + dm-flakey pass/drop tables + the fsync-before/fsync-after file check), and confirm it still passes on this kernel. Report the raw output. If dm-flakey is unavailable, stop here and report — the rest of the phase depends on it.

4. Write scripts/provision_wsl2_native_docker.sh, idempotent and non-interactive, which:
   - installs Docker Engine from Docker's apt repository inside the WSL2 distro at a pinned version (record the exact version installed),
   - configures the daemon to start without systemd if systemd is unavailable in this distro, and documents which path was taken,
   - does NOT uninstall Docker Desktop, but selects the native engine explicitly via a docker context (e.g. `docker context create aep-native --docker host=unix:///var/run/docker.sock` and `docker context use aep-native`), so the change is reversible and auditable,
   - verifies afterwards that `docker context inspect` names the unix socket and that a container bind-mounting a WSL-local path sees the file (write a canary file, mount it, cat it inside the container, assert content).
   Run it. Record all output.

5. Write scripts/verify_measurement_host.py which asserts and prints, as machine-readable JSON: docker context and daemon socket, docker server version, whether the daemon resolves WSL-local bind sources (the canary test from step 4), the pinned Redis image digest as actually resolved locally, `dmsetup targets` containing flakey, the filesystem type and mount options backing the repo and backing Docker's data root, whether the host can suspend, and the wall-vs-monotonic clock check the E5 gate already uses. Every later phase will call this and embed its output in its report.

6. Bring the stack up on the native engine and prove semantics are unchanged:
   - `docker compose -f compose.phase2.yml up -d --wait`
   - `uv run --frozen python scripts/verify_redis_semantics.py --url "$REDIS_URL"`
   - confirm `docker inspect aep-phase2-redis72` now reports Linux mount sources, and record `redis_storage_backing` (volume path, filesystem type) — this is the field Phase 8.2 requires later phases to compare against.

7. Run the full gate set and record raw output for each:
   - `uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis`
   - `uv run --frozen pytest -q -ra --strict-markers --cov=aep_core --cov-report=term-missing --cov-fail-under=90`  (expect 1734 passed, 0 skipped, ~91.18%)
   - `uv run --frozen python scripts/validate_citations.py`  (expect 371 citations, 0 invalid)
   - `make reproduce-figures`
   - `make reproduce-smoke`

8. Runtime-confound replication. Pre-register it first: commit reports/phase-report-10-prediction-<today>.md stating the cell to be re-collected (choose one already-frozen cell that is cheap and central — propose AEP-full x NO_READBACK x crashed regime, and justify your choice if you pick another), the number of runs (match the frozen cell's run count exactly), the unit of analysis (the run), the analysis command, and the prediction: rates agree with the frozen cell within a run-clustered 95% interval. Commit that file BEFORE collecting. Then collect into a NEW dated results directory — never into an existing one — and analyse.

9. Write docs/27-measurement-host.md: the host as it now stands, how to reproduce it from scratch, which numbers in the paper predate the change, and the runtime-confound result from step 8.

10. Update PAPER_ROADMAP.md's phase table with a Phase 10 row and its report path. Change nothing else in that file.

## Acceptance criteria (all must be true, and each must be evidenced by raw output in the report)
- `docker context` in use is the native WSL2 engine, and a container can bind-mount a WSL-local path (canary proven).
- The pinned Redis image digest resolves identically under the native engine.
- dm-flakey self-test passes on this kernel under the native engine.
- Full suite passes with 0 skipped, 0 xpassed, coverage >= 90%; citations valid; reproduce-figures byte-identical; reproduce-smoke completes.
- scripts/verify_measurement_host.py exists and its JSON output is embedded in the report.
- The replication cell was pre-registered in a commit that predates its first data commit (state both commit hashes and timestamps in the report).
- The replication either agrees with the frozen cell, or disagrees — either result is acceptable and must be reported as it came out. Do not tune anything to make it agree.
- experiments/results/** from previous collections is byte-unchanged (`git status` proves it).

## Report
Write reports/phase-report-10-wsl2-native-docker-<today>.md with these sections, in this order:
Asked / Done / Environment before / Environment after (JSON from step 5) / Gate outputs (raw) / Replication: pre-registration commit, data commit, result, interval / What this unblocks (state explicitly whether backlog B1 is now runnable, and if not, exactly what still blocks it) / Not done and why / Findings outside scope.

In chat, reply with no more than 5 lines pointing to the report and stating, in one sentence, whether B1 is now unblocked.

---
---

# Corrections and additions issued with the prompt

Recorded here rather than folded silently into the prompt above, per
`docs/26-journal-readiness-direction.md` §3 rule 4: *"Corrections to the prompt are recorded
alongside it, never silently applied."* The prompt above is verbatim as issued. Everything
below was issued by the operator after the plan was presented and before any work began.

## A. Four decisions taken at plan approval

**A1 — Results root: collect BOTH arms.** The survey established that the frozen `matrix`
cell was collected in the WSL-native tree on ext4 (`/root/aep`), while the Phase-8
replications ran through `/mnt/d` on drvfs/9p, and Phase 8.1 measured a 40× cost difference
on event-log appends. Collecting only one arm would confound the filesystem with the
container runtime. Therefore:

> Collect the cell twice — once into `/root/aep-phase10/...` on WSL-local ext4, once into a
> drvfs path under `/mnt/d` — so filesystem and container runtime are separated rather than
> confounded. The ext4 arm is the primary runtime-confound test against the frozen cell; the
> drvfs arm is the filesystem sensitivity arm. Pre-register BOTH arms in the same prediction
> file before either is collected, and state the prediction for each separately. Copy both
> dated results dirs into `experiments/results/` for the commit, and record in each dir's
> metadata the actual collection path and filesystem type, so the provenance difference
> between collection path and committed path is explicit rather than inferred.

**A2 — Commits: commit on `main` AND push, before any data exists.**

> The prompt file commit and the pre-registration commit must each be PUSHED before any data
> exists, not merely committed. Record the push time alongside the commit hash in the report.
> The point is an external witness to ordering, which a local timestamp cannot supply.

**A3 — Engine version: match Docker Desktop's server version.**

> If that exact version is not available in Docker's noble apt repo, take the nearest
> available, record both versions and the delta explicitly, and state the delta as a
> limitation of the runtime-confound test in the report — do not treat it as a footnote.

**A4 — Added in scope: storage backing across existing collections (establish only).**

> You have found something the paper does not currently account for. The frozen `matrix` cell
> was collected on WSL-local ext4 at `/root/aep`, while the Phase-8 replications ran through
> `/mnt/d` on drvfs/9p, and Phase 8.1 measured a 40x cost difference on event-log appends.
> That is a storage-backing difference between two sets of runs the paper compares, and it is
> exactly the class of defect `docs/24-revision-backlog.md` B1's Phase-8.2 addendum says must
> be stated rather than assumed comparable.
>
> Do this and nothing more with it:
> - Add a section to the Phase 10 report titled "Storage backing across existing collections".
>   In it, enumerate every tracked results directory under `experiments/results/` and state,
>   for each, the collection path and filesystem where it can be determined from recorded
>   metadata, and mark it UNDETERMINED where it cannot. Do not infer from filenames.
> - State plainly which comparisons currently made in `paper/sections/06-evaluation.tex` span
>   a storage-backing difference, citing file:line for each. Determine this; do not estimate it.
> - Do NOT edit the manuscript, do not re-analyse any frozen cell, and do not attempt to
>   correct anything. This phase establishes the fact only. What to do about it is the next
>   phase's decision, and I will make it from your report.

## B. Three additions issued at plan approval

**ADDITION 1 — Measure docker kill landing latency on both runtimes.** *"This is the largest
omission in the plan."*

> Phase 8.1 established that whether AEP-full dispatches is decided by whether WAITAOF
> returns before the kill lands, that runs which applied an effect had +194.1 ms higher kill
> latency (permutation p = 0.00005), and that the paper's `\UnwantedPrevented{}` is therefore
> partly a property of the fault injector's timing distribution. The paper records 419-992 ms
> for docker kill on this host. That figure was measured through the Docker Desktop shim,
> which cds to /mnt/d and execs docker.exe across the WSL/Windows boundary. A native
> unix-socket daemon will almost certainly have a different distribution, and every prevention
> number collected after this phase inherits it.
>
> So: before the replication collection, measure it directly on both runtimes.
> - 100 timed `docker kill -s KILL` operations against a throwaway container from the pinned
>   Redis image, per runtime: (a) through the Docker Desktop shim, (b) through the native
>   `aep-native` context. Same container spec, same measurement code, interleaved if practical.
> - Reuse whatever the harness already uses to time kills so the number is comparable to the
>   419-992 ms in the paper; if the harness's timing is embedded in the run path rather than
>   callable, write `scripts/measure_kill_latency.py` and state explicitly how it differs from
>   the harness's instrumentation.
> - Report both distributions: n, min, median, p95, max, and the interval. Compare against the
>   419-992 ms range the paper quotes, and state whether the native runtime's distribution is
>   faster, slower, or tighter.
> - Add the result to the phase report under its own heading "Fault delivery latency, both
>   runtimes", and add the native-runtime distribution to `verify_measurement_host.py`'s JSON
>   as a recorded environment field (measured once and cached, not re-measured on every call).
>
> Do NOT re-analyse or adjust any existing paper number from this. Establish the distribution
> only. What it implies for Table IX is the next phase's decision.

**ADDITION 2 — Give the replication a falsifiable criterion and enough power to have one.**

> As written, the primary prediction is that rates fall inside a frozen run-clustered interval
> of [0.0, 0.6]. Almost any outcome satisfies that, so the test cannot fail and therefore
> establishes nothing. Fix it in the pre-registration, before collecting:
>
> - Keep the 18-run matched arms exactly as planned (they are the like-for-like comparison,
>   and their shape must match the frozen cell).
> - Add, per arm, a powered secondary collection on the single informative cell only —
>   `after_resolution_before_barrier` — at 15 runs x 10 executions rather than 3. At ~40 s/run
>   that is ~10 minutes per arm.
> - Pre-register the criterion on that cell in the form of a difference, not a containment:
>   report ext4-arm rate minus frozen rate with a run-clustered 95% interval, and state in
>   advance the margin at which you would call the runtime a confound. Choose the margin
>   yourself, justify it in the prediction file, and state plainly that it is a stipulation
>   rather than something derived — the same discipline Section VI-C1 applies to its
>   equivalence margin.
> - State in advance what half-width would make the comparison uninformative, so that an
>   inconclusive result is reported as inconclusive rather than as agreement. Phase 9C's
>   failure was exactly this shape.
> - Same for the ext4-versus-drvfs comparison.

**ADDITION 3 — Record kill latency per run in the replication collection.**

> If the harness does not already write the docker kill landing latency into each run's
> records for this regime, add it now, before collecting. Every run from this phase onward
> must carry it. This is the field whose absence made Phase 9C's over-dispersion
> uninterpretable until Phase 8.1 went looking for it retrospectively, and it is the field
> WS-3's controlled-fault design will be built on.

**Stop-and-report conditions: unchanged, plus —**

> if kill latency cannot be measured on the Docker Desktop shim because the engine will not
> start, report that and proceed with the native measurement alone, stating the comparison as
> unavailable rather than estimating it.
