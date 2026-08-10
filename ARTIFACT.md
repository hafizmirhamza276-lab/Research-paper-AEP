# AEP artifact

Everything behind *Declared Ambiguity: The Agent Execution Protocol (AEP) for
Autonomous Agents Calling Non-Idempotent Legacy APIs*: the protocol
implementation, the five baseline systems it is measured against, the fault
injection harness, the frozen results, and the manuscript that is generated
from them.

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
fraction. The 89 macros draw on eight files and nothing else.

| Source | Macros | What it supports |
|---|---:|---|
| `experiments/results/matrix/analysis/per-cell-metrics.csv` | 31 | Every outcome rate: the trilemma table, AEP's three columns, B3's ambiguity, B4/B4b's two corners, the baseline range |
| `.../analysis/redis-kill-ablation.csv` | 11 | The prevention result — unwanted applied effects under a hard Redis kill, the canaries, Fisher's exact |
| `.../analysis/latency-and-throughput.csv` (both fsync policies) | 11 | Every latency and throughput figure, and the barrier-cost decomposition |
| `.../analysis/comparisons-vs-aep-full.csv` | 8 | Every system-vs-AEP-full p-value, the ablation's zero counts and its per-arm n |
| `experiments/results/g2-flakey-write-loss*.json` | 7 | The block-level write-loss probe: the barrier's durability claim under the fault that can test it |
| `reports/raw/e1-durability-window.txt` | 5 | The process-kill probe: trials, window, and the `0/10` that showed the barrier does *not* protect against `SIGKILL` |
| `.../analysis/per-execution.csv` | 4 | The cluster-bootstrap intervals on the barrier's cost |
| `.../analysis/coverage.json` | 4 | Runs, executions, cells collected, and the bootstrap resample count |
| derived, or counted from the source tree | 8 | Percentages, differences and the two lines-of-code figures; each carries its arithmetic in its comment |

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
| **Detection is produced by the durable record, not by the barrier**: removing the barrier changes nothing detection measures over 600 executions per arm | `\BthreeVsAepDupCount`, `\BthreeVsAepN`, `\AblationZeroUpper`, `tab:ablation` (§6.2) | `per-cell-metrics.csv`, `comparisons-vs-aep-full.csv` | `make reproduce-figures` |
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
exiting 0. Expected: 18 pages, zero undefined references, zero `\todo`, and
`18 passed, 0 failed` from `check_paper_numbers.py`.

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

**Published as an archive** — the 432 raw run directories, each holding its
run config, its ground-truth ledger, its merged log and its per-run summary.
These are the inputs to `experiments/analyze.py`. They are not committed: they
are ~1 GB of evidence that no gate reads directly, and a repository is the wrong
container for them.

### Verifying

`experiments/results/matrix/SHA256SUMS` digests the manifest and every analysis
output — 17 files. From an unpacked archive:

```sh
cd experiments/results/matrix && sha256sum -c SHA256SUMS
```

From a clone, only the 7 tracked files it covers can be checked; the other 10
report as missing, which is expected and is the difference between the two
layers above:

```sh
cd experiments/results/matrix && sha256sum -c SHA256SUMS 2>&1 | grep -v "No such file"
```

`MANIFEST.md` (in the archive) lists the run count for every cell, keyed the way
the paper quotes them — `(regime, system, crash point, response class,
read-back keying)`. The regime is part of the key deliberately: pooling regimes
is what disqualified `analysis/table-1.csv` as a source, and
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

MIT (`LICENSE`). Citation metadata in `CITATION.cff`. The tag `v1.0.0-rc1`
marks the state of the artifact at submission.
