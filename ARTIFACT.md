# AEP artifact

The currently tracked artifact for *Declared Ambiguity: The Agent Execution
Protocol (AEP) for Autonomous Agents Calling Non-Idempotent Legacy APIs*: the
protocol implementation, baseline systems, fault-injection harness, derived
analysis products, and the manuscript generated from them. The raw run archive
and immutable DOI remain external blockers (§5).

This document is the map from **a claim in the paper** to **the command that
reproduces it**. If a number in the manuscript is not reachable from this file,
that is a defect; please open an issue.

---

## 1. What you can check, and what it costs

| | command | needs | time |
|---|---|---|---|
| The paper's tables and macros follow from the frozen CSVs | `make reproduce-figures` | Python 3.13, `uv` | ~1 min |
| The harness still runs, end to end, under real `SIGKILL` | `make reproduce-smoke` | + Docker | ~6 min |
| The implementation is correct on its own terms | `uv run --frozen pytest` | + Docker | ~2 min |
| The manuscript matches its results | `bash scripts/build_paper.sh` | + TeX Live | ~2 min |
| The full evaluation | see §6 | + ~25 h and a quiet host | ~25 h |

`make reproduce-figures` is the one that matters for the paper's numbers. It
regenerates every generated table and every macro from the frozen CSVs and
byte-compares them against what is committed. The same comparison runs in CI on
every push (the `Numbers gate` job).

---

## 2. Requirements

* **Linux, or Windows with WSL2.** The harness sends real `SIGKILL` to worker
  processes and `docker kill -s KILL` to the Redis container. It refuses to
  record a run in which the kill was simulated
  (`coverage.json: all_runs_used_real_sigkill`).
* **Docker**, for Redis. The image is pinned by digest, not tag:
  `redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44`
  (`compose.phase2.yml`). "Redis 7.2 with AOF" is load-bearing for every
  durability claim, and a tag can be re-pointed.
* **Python 3.13.0**, pinned in `.python-version`, with
  [`uv`](https://docs.astral.sh/uv/). Every dependency is locked in `uv.lock`;
  all commands below use `--frozen`, so nothing resolves at run time.
* **GNU make**, for the two targets above.
* **TeX Live with IEEEtran**, only to rebuild the PDF. The exact package set CI
  installs is in `.github/workflows/ci.yml` under `Install TeX Live`.

The results in the paper were collected on Ubuntu inside WSL2 on Windows 11,
with Docker Desktop. Section 8 of the paper states what that costs in validity.

---

## 3. Claims to evidence

Every quantitative claim in the manuscript is a LaTeX macro defined in
`paper/generated/numbers.tex`, or a cell in a table under `paper/generated/`.
Nothing is typed by hand — that is enforced two ways: `check_paper_numbers.py`
fails if any generated file differs from a fresh regeneration, and the same
script fails if a generated macro is defined and never used.

**To check any claim in the paper:** find its macro in
`paper/generated/numbers.tex`. Every macro carries a comment naming the file,
the filter and the arithmetic that produced it. For example:

```tex
% per-cell-metrics.csv | system=B4_DURABLE_WORKFLOW regime=(session-3) response_class=AUTHORITATIVE_READBACK
% metric=undetected_duplicate_rate | sum(successes)/sum(total) = 95/180
\newcommand{\BfourDupAuth}{0.5278}
```

That comment is the whole provenance: the file, the three filter keys, and the
fraction. The generated `numbers.tex` currently defines 101 macros; the count
and values are regenerated together rather than maintained by hand.

| Source | What it supports |
|---|---|
| `experiments/results/matrix/analysis/per-cell-metrics.csv` | Every outcome rate: the trilemma table, AEP's three columns, B3's ambiguity, B4/B4b's two corners, the baseline range |
| `.../analysis/redis-kill-ablation.csv` | The prevention result — unwanted applied effects under a hard Redis kill, the canaries, Fisher's exact |
| `.../analysis/latency-and-throughput.csv` (both fsync policies) | Every latency and throughput figure, and the barrier-cost decomposition |
| regime-labelled `.../analysis/comparisons-vs-aep-full.csv` | Every system-vs-AEP-full comparison, the crashed-only ablation denominators, one-sided zero-event bound, and run-cluster ambiguity difference interval |
| `experiments/results/g2-flakey-write-loss*.json` | The block-level write-loss probe: the barrier's durability claim under the fault that can test it |
| `reports/raw/e1-durability-window.txt` | The process-kill probe: trials, window, and the `0/10` that showed the barrier does *not* protect against `SIGKILL` |
| `.../analysis/per-execution.csv` | Run-cluster intervals on the barrier's cost and the B3--AEP ambiguity difference |
| `.../analysis/coverage.json` | Runs, executions, cells collected, and the bootstrap resample count |
| derived, or counted from the source tree | Percentages, differences and the two lines-of-code figures; each carries its arithmetic in its comment |

All of these are **tracked in this repository** except the raw run directories
(§5). A clean clone can therefore regenerate every table and every macro with no
downloads:

```sh
make reproduce-figures
```

### The four headline claims

| Claim (paper §) | Macro / table | Evidence file | Command |
|---|---|---|---|
| AEP records **no** undetected duplicate and **no** lost effect under crashes, against baselines at 0.77–0.83 | `\AepDupAuth`, `\BaselineDupLow`, `\BaselineDupHigh`, `tab:outcomes` (§6.1) | `per-cell-metrics.csv` | `make reproduce-figures` |
| **Detection is produced by the pre-dispatch record plus no re-entry, not by the barrier**: the crashed-regime ablation shows no observed difference in duplicates or lost effects over 540 executions per arm; ambiguity has a separate run-cluster difference interval | `\BthreeVsAepDupCount`, `\BthreeVsAepN`, `\AblationZeroUpper`, `\BthreeVsAepAmbDiffLow`, `\BthreeVsAepAmbDiffHigh`, `tab:ablation` (§6.2) | `per-cell-metrics.csv`, regime-labelled `comparisons-vs-aep-full.csv` | `make reproduce-figures` |
| **Prevention is what the barrier buys**: under a hard Redis kill it withholds 18 real effects B3 commits | `\UnwantedPrevented`, `\AepUnwantedRate`, `\BthreeUnwantedRate`, `\UnwantedP` (§6.2) | `redis-kill-ablation.csv` | `make reproduce-figures` |
| The barrier's *durability* claim needs a fault that loses the page cache; a process kill loses nothing | `\ProcessKillUnackLost` (0/10), `\FlakeyAckSurvived` (90/90), `\FlakeyUnackLost` (90/90) (§6.2) | `reports/raw/e1-durability-window.txt`, `g2-flakey-write-loss*.json` | `make reproduce-figures` |

### Three worked spot-checks

1. **"B4 duplicates at 0.5278 on `auth`" (§6.1).** `\BfourDupAuth` in
   `paper/generated/numbers.tex` names `per-cell-metrics.csv`,
   `system=B4_DURABLE_WORKFLOW`, `regime=(session-3)`,
   `response_class=AUTHORITATIVE_READBACK`, `metric=undetected_duplicate_rate`,
   `95/180`. Check it directly:

   ```sh
   awk -F, '$1=="undetected_duplicate_rate" && $2=="(session-3)" \
     && $3=="B4_DURABLE_WORKFLOW" && $5=="AUTHORITATIVE_READBACK" \
     { s += $7; t += $8; print $4, $7"/"$8 } \
     END { print "pooled", s"/"t, s/t }' \
     experiments/results/matrix/analysis/per-cell-metrics.csv
   ```

   Six crash points, `95/180`, `0.5278`. The `regime` filter is not optional:
   without it the crash-free (`p0`) row joins in and the total becomes
   `98/210`. Pooling regimes is the mistake that got `analysis/table-1.csv`
   banned as a source.

2. **"18 real non-idempotent effects not committed" (§6.2).**
   `\UnwantedPrevented` is `B3 applied - AEP-full applied`:

   ```sh
   cat experiments/results/matrix/analysis/redis-kill-ablation.csv
   ```

   The `executions_with_an_applied_effect` column reads 28 for
   `B3_INTENT_NO_BARRIER` and 10 for `AEP_FULL`, over 30 executions each.

3. **"Not one unfsynced write was lost: 0/10" (§6.2).**

   ```sh
   grep "unacknowledged write lost" reports/raw/e1-durability-window.txt
   ```

   The per-trial lines above it give the window each kill landed in
   (`write->death`), which is where `\ProcessKillWindowMin` and
   `\ProcessKillWindowMax` come from.

---

## 4. Reproducing

### The paper's generated artifacts

```sh
make reproduce-figures
```

Regenerates `numbers.tex` and all five tables from the frozen CSVs into
`.scratch/reproduce/figures/`, byte-compares each against `paper/generated/`,
and checks `paper/figures/state-machine.tex` against the transition table in
`aep_core.core.intents`. Prints a verdict. Exits nonzero on any difference.

The two analysis figures (`figure-1`, `figure-2`) need the raw run directories,
which are not tracked (§5). The target says `SKIPPED` for them unless you point
it at an unpacked archive:

```sh
make reproduce-figures ARCHIVE=/path/to/unpacked/matrix
```

Those two are PDFs written by matplotlib, which stamps the wall-clock time into
every file it writes. The target normalises that timestamp and requires the rest
of the bytes to match exactly, so a plotted value that moved still fails.

### The harness, end to end

```sh
make reproduce-smoke
```

Provisions Redis from `compose.phase2.yml`, asserts the live server really
provides `phase2.conf` semantics and implements `WAITAOF`, marks the throwaway
instance disposable, collects one tier-1 cell for **each of the seven systems**
under real `SIGKILL`, analyses them, prints one row per system, and tears the
containers down. Fully unattended. Writes only under `.scratch/`.

This is a liveness check on the harness, not a replication. Two executions per
cell cannot estimate a rate — the paper's cells are 150–180 executions. What it
shows is that each system still lands in its own corner: AEP-full and B3 with
neither duplicates nor lost effects, B0/B1/B2/B4 duplicating, B4b losing the
effect instead.

### The test suite

```sh
uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis
docker compose -f compose.phase2.yml up -d --wait
export REDIS_URL=redis://127.0.0.1:6381/15 AEP_PHASE2_REDIS_INTEGRATION=1
uv run --frozen python scripts/verify_redis_semantics.py --url "$REDIS_URL"
uv run --frozen pytest -q -ra --strict-markers --cov=aep_core --cov-fail-under=90
docker compose -f compose.phase2.yml down -v
```

Expected: **1734 passed, 0 skipped**, coverage **91.18%** on `aep_core`. Redis
is never faked. Zero skips is a gate, not an observation
(`scripts/check_pytest_gates.py`).

### The manuscript

```sh
bash scripts/build_paper.sh
```

Builds the PDF and then runs the numbers gate. Fails on a blank bibliography and
on undefined references, both of which LaTeX itself reports as warnings while
exiting 0. Expected: **21 pages**, zero undefined references, zero `\todo`, and
`18 passed, 0 failed` from `check_paper_numbers.py`.

The tracked `paper/main.pdf` was promoted from a build meeting exactly that
expectation on 2026-09-01.

---

## 5. The frozen results

The evaluation is 432 runs / 3 780 executions / 126 cells. Two layers:

**Tracked in this repository** — the analysis products the paper's numbers are
computed from, at their frozen content:

```
experiments/results/matrix/analysis/{per-cell-metrics,per-execution,
    latency-and-throughput,redis-kill-ablation,comparisons-vs-aep-full}.csv
experiments/results/matrix/analysis/coverage.json
experiments/results/matrix/{MANIFEST.csv,SHA256SUMS}
experiments/results/fsync-always/analysis/{latency-and-throughput,per-execution}.csv
experiments/results/g2-flakey-write-loss*.json
```

These 13 files are exactly the inputs `scripts/check_paper_numbers.py` opens.
They are re-included by name at the tail of `.gitignore`; everything else under
`experiments/results/` stays ignored.

**Not yet published externally** — the raw run directories, each holding its run
config, ground-truth ledger, merged log and per-run summary, are the inputs to
`experiments/analyze.py`. They are not committed. **As of 2026-09-03 they are
assembled and verified but not uploaded: no DOI or archive URL exists yet.**

### The raw evidence archive (Phase 11, 2026-09-03)

Built by `scripts/build_raw_archive.py` and verified by
`scripts/verify_raw_archive.py`. Full account:
`reports/phase-report-11-rescue-2026-09-03.md`.

| | |
|---|---|
| collection roots | **20** |
| run directories | **1 458** |
| files | **26 300** |
| payload | **492 905 568 bytes** (`.tar` 520 396 800; `.tar.gz` **24 257 505**) |
| **`MANIFEST.sha256`** | **`87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7`** |
| `aep-raw-evidence.tar` | `3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94` |
| `aep-raw-evidence.tar.gz` | `fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353` |
| `ARCHIVE-METADATA.json` | `cf75e7232ad9a97ee989760ca05cda758c67d4da0245a7929ba12706f7a220e5` |

The manifest carries a SHA-256 for **every** file; the digest above is the digest
of the manifest itself. `ARCHIVE-METADATA.json` names each root's source path,
its filesystem at archive time, its run and file counts, and the tracked
`analysis/` directory it produced — and lists **every** raw run directory on the
build host that was *excluded*, with the reason, so no collection is silently
absent.

It contains the 432-run `matrix` evaluation, `fsync-always`, **`results/voided/`
with the excluded oracle-disagreement run and its `README.md`**, the four
`b2-*-2026-08-21` prevention replications, the six Phase-8.4 paired collections
including the two aborted ones, the four Phase-10 replication arms, and Phase
10's two voided wrong-runtime arms.

**Determinism.** Entries sorted by archive path; `uid`/`gid` zeroed,
`uname`/`gname` emptied, modes normalised, gzip member `mtime=0`. File mtimes are
preserved deliberately — they are evidence for
`docs/28-storage-backing-recovery.md`.

**Verified sufficient, not merely present.** The archive was extracted to a
scratch path, checked file-by-file against the manifest (26 300 verified, 0
problems), and `experiments/analyze.py` re-run over the *extraction* with each
root's own recorded bootstrap seed and resample count. Against every git-tracked
analysis file: **114 byte-identical, 8 identical after two declared
normalisations, 0 differing.** The eight normalised are accounted for by two
changes to `analyze.py` that postdate the freeze — the crash-always regime's
label (`(session-3)` → `crashed`) and two columns added to `per-execution.csv` —
and a row-level check confirms 0 differing keys and every shared column agreeing
on every row. A further 8 tracked files are written by the collection rather than
by `analyze.py`; all 8 are in the archive with digests matching the tracked
copies. `matrix/analysis/comparisons-vs-aep-full.csv` reproduces byte-identically
through its actual producer, `experiments/rebuild_comparisons.py`, as the
provenance note below requires.

**Nothing under any raw run directory was modified.** Every source file was
re-digested against the manifest after the build:
`python3 scripts/build_raw_archive.py --verify-sources-unchanged` → *"re-digested
26299 source files … UNCHANGED"*.

**Scanned before deposit.** `scripts/scan_archive_for_leakage.py` read all
26 300 files across twelve categories. **Zero** credentials, keys or tokens;
**zero** email addresses; **zero** account names; **zero** hardware identifiers;
**zero** environment dumps. What is present is the host's name (`KP248`, 9
files) and absolute filesystem paths (`/root/aep/…`, `/mnt/d/personal/AEP/…`).
Those are retained deliberately: 11 of the files carrying them are the evidence
`docs/28-storage-backing-recovery.md` §3.1 uses to determine the frozen
evaluation's collection path, and removing them would invalidate both digests.
Raw: `reports/raw/phase12-leakage-scan.{txt,json}`.

**What remains before this section's availability claim becomes true — and it is
a manual step, not an automated one.** `docs/29-archive-deposit.md` is a
complete do-it-by-hand checklist for the Zenodo web interface: which files to
upload, their digests, every metadata field's exact value, what to check on the
sandbox record before publishing, and the post-upload verification. No API token
exists or is needed.

Two things are deliberately **pending** rather than done, and are recorded here
so their absence is visible:

| pending | why, and what closes it |
|---|---|
| **The DOI.** `paper/main.tex`'s `\archivedoi` reads `PENDING`, and §IX renders "prepared and verified but not yet deposited". | One line in one file, after the upload. Every other site derives from it; no section file contains a DOI string. |
| **A CI job verifying the published archive.** `scripts/verify_published_archive.py` exists and its local path is tested — 26 300 files checked, 122 tracked products compared, 0 differing — but it is **not wired into CI**. | With no DOI there is nothing to fetch, so the job could only pass without checking anything, and *a gate that cannot fail is decoration*. The job's YAML is written out in `docs/29-archive-deposit.md` §5, together with the deliberate-failure test it must be subjected to before it is trusted. |

Until then the repository supports regeneration from the tracked derived
products, and the from-raw rerun is reproducible on the build host and by anyone
holding the archive, but not yet by a reader who has only this repository.

### Verifying

`experiments/results/matrix/SHA256SUMS` currently digests the manifest and every
listed matrix output — 17 files. From a clone, only the tracked subset can be
checked. **The complete SHA-256 manifest that must cover every raw directory,
`results/voided/`, and all derived products now exists** — `MANIFEST.sha256`,
digest `87fa2d53…` above — but the resolver URL and archive checksum still cannot
be added here, because nothing has been uploaded.

The intended verification commands, once that archive exists, are:

```sh
cd experiments/results/matrix && sha256sum -c SHA256SUMS
```

From the current clone, only the 7 tracked files it covers can be checked; the other 10
report as missing, which is expected and is the difference between the two
layers above:

```sh
cd experiments/results/matrix && sha256sum -c SHA256SUMS 2>&1 | grep -v "No such file"
```

### Every run's configuration against its own digest — and what that proves

Each run records a `config_digest`: a SHA-256 over every field that could change
a number. `scripts/verify_published_archive.py` checks all of them as its last
step, and it can be run alone against an unpacked archive:

```sh
uv run --frozen --extra experiments --extra analysis python \
  scripts/audit_config_digests.py --root <unpacked>/matrix --require-runs 400
```

Expected: **`NONE UNEXPLAINED`**, over 432 configs.

**It is verified per schema generation, and this is not a workaround.** The
harness's `RunConfig` gained fields twice during the evaluation — amendment E1's
`redis_kill_*` and amendment E5's `suspend_disabled_declared` — and the digest
is computed over the field set in force when the run was collected. Verifying a
2026-08-06 run against today's field set therefore asks the wrong question and
gets the wrong answer. The audit reconstructs each historical field set from the
git history of `experiments/harness/config.py` and verifies each run against the
one in force at its collection. Three generations exist — 35 fields
(`2fefe5e`), 38 (`9154d85a`), 42 (`e67efd1`) — and **all 432 runs verify**, with
the 150 that today's field set cannot check reproduced exactly by generation
`9154d85a` and **none unexplained**. That is positive evidence that no
configuration was altered after collection, established across a schema the
project itself evolved. `docs/32-config-digest-verifiability.md` has the method
and the per-root breakdown.

> **What this check proves, and what it does not.** It proves that each run's
> recorded configuration is the one its digest was computed over, under the
> field set in force at collection time — so a field altered afterwards is
> caught, and so is a digest that matches no generation. **It is a tamper check,
> not a correctness check.** It says nothing about whether the configuration was
> the right one, whether the fault it names was actually delivered, or whether
> the run measured what it intended to. Those are the jobs of the fault-delivery
> census, the run-level oracle reconciliation and the per-cell counts in
> `MANIFEST.csv` respectively. In the same way `scripts/validate_citations.py`
> proves citation ranges are valid and not that the semantics are right, this
> proves the configuration is unaltered and not that it was correct.

Both of the check's failure modes were demonstrated rather than asserted, on
copies, against the real corpus: a stored digest matching no generation, and a
configuration whose contents were altered while its digest was left untouched.
Both are caught; the check also refuses to pass when it examined nothing.

### Provenance: one derived artifact was regenerated after the first freeze

`analysis/comparisons-vs-aep-full.csv` is the **only** tracked results file that
has been modified since the results were first committed, and its `SHA256SUMS`
line was rewritten in the same commit. It is recorded here because a reader who
compares this manifest against `reports/audit-report-2026-08-10.md` — which
verified that no tracked results file had ever been modified — would otherwise
find a discrepancy with no explanation.

| | |
|---|---|
| **What** | `experiments/results/matrix/analysis/comparisons-vs-aep-full.csv` |
| **When** | `b9617e4`, *"Close Stage 1 scientific integrity and novelty issues"* |
| **Why** | The file pooled three fault regimes — `crashed`, `p0` and `redis-kill-preack` — into one set of comparison rows, which the manuscript's own reporting rule (§VI-A) forbids. It was regenerated regime-labelled. |
| **By** | `experiments/rebuild_comparisons.py`, committed in the same commit together with `experiments/tests/test_regime_comparisons.py` |
| **Old digest** | `c2a4cd3df667bb0878cf76b57cc7d13ef41a82a266a3893f4867dfd554c76a9a` |
| **New digest** | `a5310f3abf3cecfe6b82ac58591f4ed6f548bad244c30687cc85e95bc423ee12` |

**No measured data changed.** The inputs that regeneration reads —
`analysis/per-cell-metrics.csv` and `analysis/per-execution.csv` — have exactly
one commit and one blob each across the project's entire history and are
byte-identical at every revision. The regeneration is reproducible from the
tracked tree alone:

```sh
python -m experiments.rebuild_comparisons \
  --analysis experiments/results/matrix/analysis \
  --output /tmp/check.csv
cmp /tmp/check.csv experiments/results/matrix/analysis/comparisons-vs-aep-full.csv
sha256sum /tmp/check.csv          # == the new digest above
```

What the correction did to the manuscript is recorded in
`reports/phase-report-6-audit-2026-08-21.md` §S3.1: of 89 generated macros, 84
were unchanged, and of the five that moved, none moved in the paper's favour —
the headline Fisher p-value became 25.7× weaker.

The pending archive must include `MANIFEST.md`, listing the run count for every
cell keyed the way the paper quotes it — `(regime, system, crash point, response
class, read-back keying)`. The regime is part of the key deliberately: pooling
regimes is what disqualified `analysis/table-1.csv` as a source, and
`check_paper_numbers.py` fails if any generated file draws from it.

---

## 6. Collecting the evaluation from scratch

The full plan is 1 068 runs at roughly 25 h on one machine. The 432 that were
collected were chosen to answer the research questions rather than to fill the
grid; §8 of the paper names every gap.

```sh
uv run --frozen python -m experiments.run_matrix --plan-only   # inspect first
uv run --frozen python -m experiments.run_matrix --resume      # collect
uv run --frozen python -m experiments.analyze --results-root experiments/results/matrix
```

Two things worth knowing before starting. The harness **refuses to run** if a
host-level fault injector is already running, and it refuses to touch a Redis
that has not advertised `aep:test-instance-marker`, because it kills processes
holding leases and deletes keys. And absolute timing is dropped from any run on
a host that has not declared suspend disabled — the E5 gate — so a laptop that
sleeps mid-run contributes counts but no latency.

---

## 7. Layout

| Path | What it is |
|---|---|
| `aep_core/` | The protocol: intents, durability barrier, locks, CAS storage, recovery |
| `experiments/harness/`, `experiments/run_matrix.py` | Fault injection, the crash points, the matrix orchestrator |
| `experiments/baselines/` | B0–B4b, and `B4_SEMANTICS.md` on what B4 does and does not share with a real durable-execution engine |
| `experiments/mock_api/` | The non-idempotent provider, with the three reconciliation capabilities |
| `experiments/analyze.py` | Runs → metrics, intervals, figures |
| `scripts/paper_tables.py` | Metrics → the manuscript's tables and macros |
| `scripts/check_paper_numbers.py` | The gate: the manuscript against its results |
| `paper/` | The manuscript; `paper/generated/` is machine-written |
| `docs/22-formal-model.md` | System model, failure model, properties P1–P3, and the non-claims |
| `reports/` | The session-by-session record, including what was wrong and when |

---

## 8. Licence and citation

MIT (`LICENSE`). Citation metadata is in `CITATION.cff`. No new immutable
submission release or tag has been created for this revision; that is a human
release blocker, not a state this document assumes.
