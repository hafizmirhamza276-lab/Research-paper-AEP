# Stage 3 pre-run protocol — 2026-08-12

Status at freezing: **no Stage 3 scientific execution has started**. This
document fixes the hypotheses, estimands, matrix, ordering, seeds, and handling
rules before any outcome is observed. The hypothesis and analysis sections
below must not be edited after collection. Any later change belongs in the
dated amendment log at the end, with a reason and its effect on interpretation.

## Identity and frozen plan

- Git base: `c2fffa61961228de8466b12939ef1c578506e7ba` (`main`, equal to
  `origin/main` before Stage 3 edits).
- Collection-source manifest SHA-256:
  `989b87f38badfcbda8b8957bfa189b16f70d75fd40cf55ce6c4be1c321fd38f3`.
  This is the SHA-256 of the ordered `sha256sum` manifest for the eight
  collection and analysis source files named by the machine plan.
- Final machine-readable experiment plan:
  `reports/stage3-experiment-plan-2026-08-12.json`.
- Final machine-readable plan SHA-256:
  `b5e4a39fa83d30065b060960a6862eaf4fdc3d897df368aff7104cf8afdd7f9a`.
- Matrix version: `aep.matrix/1`; matrix seed: `20260812`.
- Each immutable `matrix-plan.json` contains the complete ordered run list,
  every run ID, and every integer seed. Its SHA-256 is in the final plan.
- Deterministic order: tier, then repetition, then SHA-256 of
  `matrix_seed|run-order|cell_key`. This interleaves systems and capabilities
  within every repetition and does not depend on outcomes.

## Frozen hypotheses and primary estimands

### B2: prevention across endpoint capability classes

The Redis process is killed at `after_intent_before_barrier`, with no worker
crash. The two systems are AEP-full and B3 intent-without-barrier. The two new
capability classes are authoritative read-back (`payments`) and positive-only
read-back (`notifications`), both under caller-reference keying.

The falsifiable prediction is:

1. endpoint capability may change the final declared-ambiguity classification;
2. endpoint capability must not retroactively change whether the provider
   received an effect; and
3. an applied-effect rate that materially changes only because read-back
   capability changed contradicts the stated prevention mechanism and will be
   reported as such.

The primary outcomes, separately for every system/capability cell, are unwanted
applied effects, dispatch withheld, declared ambiguity, undetected duplicates,
lost effects, barrier refusal/acknowledgement, Redis kill/restart timing, and
agreement with the independent ground-truth ledger. The primary estimands are
the cell-specific rates and the absolute AEP-full minus B3 differences. No
capability or fault regime will be pooled into a headline rate.

### B3: timing under Redis durability policy

The two systems are AEP-full and B3 intent-without-barrier in crash-free `p0`
payments cells, measured separately under `appendfsync everysec` and
`appendfsync always`. The primary estimand is:

> median AEP-full step latency minus median B3 step latency within the same
> `appendfsync` configuration.

The directional expectation is a positive barrier cost, but neither interval
is required to exclude zero. A zero, negative, or uncertain difference will be
retained. Run counts will not be increased in response to significance,
direction, interval width, or any other outcome.

## Design reconciliation and exact matrix

`docs/24-revision-backlog.md` described B2 as three runs of ten executions,
whereas the committed Redis-kill harness explains that one Redis kill defines
one independent infrastructure-fault exposure. The resolution fixed before
collection is **30 independent runs × 1 execution** per B2 system/capability
cell. This prevents later executions from sharing the Redis instance restarted
by an earlier execution. The locked plan tests this shape directly.

| Dataset | Regime / crash point | Systems | Capabilities | Redis policy | Cells | Runs/cell | Executions/run | Runs | Executions |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| `stage3-2026-08-12-b2` | `redis-kill-preack` / `after_intent_before_barrier` | AEP-full, B3 | authoritative, positive-only | AOF + everysec | 4 | 30 | 1 | 120 | 120 |
| `stage3-2026-08-12-b3-everysec` | `p0` / none | AEP-full, B3 | authoritative | AOF + everysec | 2 | 9 | 10 | 18 | 180 |
| `stage3-2026-08-12-b3-always` | `p0` / none | AEP-full, B3 | authoritative | AOF + always | 2 | 9 | 10 | 18 | 180 |

Planned core total: 8 cells, 156 independent runs, and 480 executions. The
plan model estimates 5,850 seconds (1.63 hours) of run time; setup, validation,
analysis, and the slower `always` arm make 2–3 wall-clock hours a conservative
operator estimate. Raw outputs are expected to remain below 250 MiB, but at
least 2 GiB of stable free host storage is required before collection so that
Docker, WSL, Redis AOF, logs, voided attempts, and analysis cannot exhaust the
host volume.

The Stage 2 three-run timing aggregates remain frozen. Their raw directories
are absent, so Stage 3 will not pretend to append six raw runs to them or merge
them with new raw evidence. The pre-result resolution is a fresh, independently
versioned nine-run dataset for each arm/configuration. The old aggregate remains
descriptive historical evidence only.

## Inclusion, failure, retry, and void rules

- A run is included only when its ID, seed, system, capability, regime,
  execution count, dataset version, plan digest, Git SHA, Redis image/version,
  and effective durability match the locked plan and run configuration.
- The disposable marker, `appendonly=yes`, expected `appendfsync`, AOF enabled,
  Redis version, and coordinator run ID are checked before and after each run.
- A normal run requires an unchanged coordinator run ID. A Redis-kill run
  requires a changed run ID and a verified restarted coordinator.
- The merged event log and independent SQLite ground-truth ledger must
  reconcile. A scientifically unfavorable but internally valid result remains
  included.
- Infrastructure-invalid conditions include an incomplete run, malformed raw
  record, configuration or plan mismatch, missing marker, unexpected restart,
  missing expected restart, ledger disagreement, host suspension, storage
  exhaustion, provider start failure, or loss of the required Redis policy.
- A partial or invalid attempt is moved byte-for-byte beneath the versioned
  root's `voided/` directory. A sibling JSON reason records its original run
  ID, fixed seed, reason code, timestamp, and recursive raw-directory SHA-256.
  It is excluded from scientific estimates but included in void accounting.
- A retry uses the same preassigned run ID and seed and occurs only after the
  invalid attempt is preserved. No favorable-seed replacement or silent rerun
  is permitted. A resume skips an already complete valid run and never cleans
  the result root.
- No completed or voided evidence may be deleted, edited, or overwritten.
  Results are never reconstructed from aggregate CSVs.

## Frozen analysis methods

- Runs, not executions, are the independent clusters.
- Rates show raw numerator and denominator and a 95% run-cluster bootstrap
  interval. Absolute AEP-full minus B3 differences use a run-cluster bootstrap.
- B3 median differences and their 95% intervals resample whole runs within
  system and durability configuration; executions are never the resampling
  unit for the primary timing uncertainty.
- Fisher exact tests, where emitted, are labelled descriptive execution-level
  tests because executions remain clustered by run.
- Redis-kill, `p0`, `p30`, every-execution-crashed, and any future block-loss
  data remain distinct. Capability classes and Redis policies remain distinct.
- Stage 1's ±5 percentage-point ambiguity-equivalence margin is retained as a
  historical analysis margin and is not called preregistered.
- B2 and B3 are confirmatory relative to this protocol. Any secondary cells are
  exploratory unless a dated prediction is appended before those cells start.
  Contradictory and tying results are not suppressed.

## Secondary questions fixed before their possible execution

Secondary work starts only after valid B2 and B3 closure.

- `redis-kill-inflight`: asks whether the two arms tie when Redis dies after
  transmission. A tie is the existing prediction and is evidence, not a reason
  to rerun or discard the cell.
- `p30`: asks only how crash-free-step latency/overhead behaves at an
  intermediate 30% crash rate. It will not be mixed with `p0` or the
  every-execution-crashed regime.
- `ORACLE_FINGERPRINT`: asks whether alternative read-back keying changes
  detection/classification. It is not evidence that keying retroactively
  changes prevention.

No secondary cell is scheduled while the core infrastructure blockers below
remain, and the full 1,068-run matrix will not be collected cosmetically.

## Environment and safety preflight

Observed 2026-08-12, Asia/Karachi:

- Host: Windows 11 Pro 10.0.26200, Docker Desktop 4.46.0 using its Linux engine,
  and Ubuntu 24.04.4 under WSL2 kernel 5.15.167.4. This is not native Linux.
- CPU/RAM: Intel i5-8365U, 4 cores / 8 logical CPUs, 12.69 GB host RAM; WSL saw
  8 CPUs and 6.12 GB RAM.
- Workspace storage: NTFS exposed to WSL as `v9fs`. Host C: was repeatedly at
  100% usage, with readings from about 24 MiB to 453 MiB free and no second
  fixed data volume. This fails the fixed 2 GiB collection requirement.
- Load: preflight samples showed 92.2–99.8% total CPU and 1.46–1.61 GiB
  available host memory. Timing collection requires a new quiet-load check.
- Power: Windows Balanced scheme; AC and DC sleep-after are both zero;
  hibernation is disabled and AC hibernate-after is zero. Therefore
  `AEP_HARNESS_SUSPEND_DISABLED=1` is truthful for a mains-powered run and was
  set only for plan generation. It was not globally present before that.
- Python: Windows project environment Python 3.12; WSL system Python 3.12.3.
  `uv` and the locked project dependencies are absent in WSL, so the Linux
  environment cannot yet be synchronized. `uv.lock` SHA-256 is
  `03f03adfffccadf027e39df199cfecd4acaae610692d3458bb04326f6bc9b447`.
- Docker: client/engine 28.4.0; Compose 2.39.2. A read-only `docker system df`
  audit fails because overlay snapshot 1841 is missing. The engine must be
  repaired and re-audited before a planned kill/restart loop can be trusted.
- Redis: pinned `redis:7.2.5-alpine` digest
  `sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44`,
  version 7.2.5, `appendonly=yes`, `appendfsync=everysec`, port 6381, DB 15.
  The Docker-restarted instance initially lacked the marker and had DB size
  zero. Its Compose labels, pinned image, command, loopback port, and empty DB
  identified the dedicated AEP instance; `SET ... NX` installed only
  `aep:test-instance-marker`, then `GET` returned `1` and DB size returned `1`.
  No cleanup, restart, kill, flush, unrestricted key scan, or data deletion was
  performed.
- Toolchain: Poppler 24.02.0 and pdfTeX 1.40.25 (TeX Live 2023) in WSL.
- Competing interactive services included VS Code, browsers, Codex, and Claude.
  They must be quiesced or recorded before timing collection.

Preflight verdict: **BLOCKED before collection** by critically insufficient
host storage, an inconsistent Docker overlay audit, and an unsynchronized WSL
locked environment. These are environment-gated blockers, not failed or null
scientific results. No run directory or void attempt exists yet.

## Historical raw-evidence and privileged-study status

The original 432 raw run directories and the referenced historical
`results/voided/` evidence are not present in the Git checkout or in the
searched Desktop, Documents, and Downloads locations. Only tracked aggregates
and manifests are available. Therefore combined raw reanalysis, complete DOI
archive closure, and clean-room raw reproduction are blocked unless the
original archive is supplied or the complete dataset is recollected into a new
root. No raw data will be synthesized from those aggregates.

B1 block-write-loss is deferred: the host is WSL2 plus Docker Desktop, not a
disposable native-Linux block-device namespace, bind mounts resolve through
Windows, and the user has not given the separately required privileged
host-level approval. No loop device, `dmsetup`, `sudo`, or write-loss injection
was attempted. B4's human-operator study is outside this stage and will not be
attempted.

## Dated amendments after freezing

None. Append amendments here; do not rewrite the hypotheses or analysis rules
above.
