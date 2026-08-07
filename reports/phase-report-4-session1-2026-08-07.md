# Phase 4 Session 1 — the matrix closeout and the manuscript

**Date:** 2026-08-07
**Roadmap section:** `PAPER_ROADMAP.md` §5 (Phase 4, the manuscript) and its
prompt block, preceded by the matrix closeout, under amendments **F0–F5**.
**Predecessor:** `reports/phase-report-2b-session3b-2026-08-07.md`

> **Read this first — four things, in the order they matter.**
>
> **1. The comparison is complete and the headline holds at four baselines.**
> B1 and B2 finished their `POSITIVE_ONLY_READBACK` and `NO_READBACK` cells, so
> Session 3B's §F3 ("the E3 comparison has one baseline, not four") is closed.
> B0, B1 and B2 duplicate at **0.77–0.83 on every endpoint capability** and
> declare nothing; AEP-full and B3 record **0.0000 undetected duplicates and
> 0.0000 lost effects in all three**, with declared ambiguity at
> 0.0000 / 0.3500 / 0.7222. The matrix is 326 runs, 2 720 executions, 91 cells.
> §C.6.
>
> **2. The paper exists, compiles, and every number in it is generated from a
> CSV.** 13 pages, IEEEtran, zero undefined references, zero `\todo` markers, 24
> bibliography entries each verified by DBLP lookup or DOI resolution.
> `scripts/check_paper_numbers.py` re-derives every table and fails on drift:
> 13 checks, all passing. §C.2.
>
> **3. Five defects were found, four of them in the measurement and reporting
> code, and not one was visible in any output.** A per-cell grouping that could
> silently average a crash-free cell with a hard-Redis-kill cell; a headline
> figure drawn from the table Session 3B had banned; a pooling formula that was
> an order-dependent running mean under a comment claiming otherwise; a
> bibliography that compiled completely blank while reporting no undefined
> citation; and a benchmark container that came up on the wrong durability
> policy twice. Every one was caught by a gate rather than by reading output.
> §C.3, §C.4, §C.5, §C.7.
>
> **4. The barrier's cost is now a curve, not a number.** The same crash-free
> cell against `appendfsync always` costs **63.4 ms** of barrier where
> `everysec` costs **2 004.9 ms** — a factor of 31 for one configuration line.
> §C.7.
>
> **One thing did not get done: the final push.** The credential helper wedged
> mid-session and `git push` now fails with `fatal: unable to get password from
> user`. Three commits are local-only and CI has not run on them. §E1.

---

## A. Phase attempted and roadmap section reference

`PAPER_ROADMAP.md` §5, under this session's amendments:

| Amendment | Requirement | Status |
|---|---|---|
| **F0(i)** | Standing rule 8 — commit/push Session 3B, green CI | ✅ **Done**, all three jobs green (§C.1) |
| **F0(ii)** | Let the remaining B1/B2/B3 cells finish | ✅ **Done**, 96/96 collected (§C.6) |
| **F0(iii)** | `appendfsync always` barrier-latency micro-benchmark | ✅ **Done**, and the config gate fired twice first (§C.7) |
| **F0(iv)** | Freeze results; `per-cell-metrics.csv` the only quotable source; archive with a per-cell manifest | ✅ **Done** (§C.3, §C.8) |
| **F1** | Claims match Session 3B exactly: dispatch withholding, **not** durability against process SIGKILL | ✅ (§C.9) |
| **F2** | The trilemma is the frame; per-capability table as anchor | ✅ (§C.9) |
| **F3** | Every number carries a pointer; timings only from suspend-gated runs; 28 ms and barrier cost separate; test counts never cited as assurance | ✅ (§C.2, §C.7) |
| **F4** | All sections drafted; `\todo` only where completion cells could move a value; IEEEtran; verified-real refs only | ✅, and zero `\todo` remain (§C.2, §C.5) |
| **F5** | Threats must include the six named items | ✅, plus three more a reviewer would raise first (§C.10) |
| **Rule 8** | Commit, push, green CI **before** the report | ⚠️ **committed, not pushed** — §E1 |

---

## B. Files created/modified

### New — the manuscript (`paper/`)

| File | What it is |
|---|---|
| `main.tex` | IEEEtran journal-mode. Its header states the numbers discipline and names the two permitted rate sources. |
| `sections/01-introduction.tex` | The trilemma as the frame; contributions C1–C4; explicit non-claims. |
| `sections/02-motivating.tex` | Four traces from the harness, cross-checked against the oracle; the trilemma table. |
| `sections/03-model.tex` | System, clocks, endpoint capability, failure model F1–F5, non-claims. Condensed from `docs/22-formal-model.md`. |
| `sections/04-protocol.tex` | Ordering, P1/P2/P3 with declared residuals, the ack→authorization chain, the state machine. |
| `sections/05-implementation.tex` | LOC, Lua scripts, composition modes, and an explicit refusal to cite test counts as protocol assurance. |
| `sections/06-evaluation.tex` | RQ1–RQ4. Every table `\input` from `generated/`. |
| `sections/07-related.tex` | Five strands plus a positioning table. |
| `sections/08-threats.tex` | Construct/internal/external, and where the protocol should *not* be used. |
| `sections/09-artifact.tex` | What is pinned, what reproduces, how the numbers regenerate. |
| `refs.bib` | 24 entries. Header records the two silent failures of §C.5. |
| `figures/state-machine.tex` | **Generated** from the implementation's transition set. |
| `generated/*.tex` | **Generated** tables and macros. Not hand-edited. |

### New — the tooling that keeps the paper honest

| File | Why |
|---|---|
| `scripts/paper_tables.py` | Generates every evaluation table and headline scalar from the frozen CSVs, emitting the filter and arithmetic behind each value as a comment. Never reads the banned pooled table. |
| `scripts/gen_state_machine.py` | Emits the state-machine figure from `LEGAL_INTENT_TRANSITIONS`; exits non-zero if the code has an edge the layout does not. |
| `scripts/check_paper_numbers.py` | Re-derives all of the above and fails on drift. Also greps `main.bbl` for empty entries and `main.blg` for parse errors. |
| `scripts/verify_refs.py` | DBLP lookup per entry; non-indexed sources listed for URL verification. |
| `scripts/freeze_results.py` | Per-cell manifest, `MANIFEST.csv`, `SHA256SUMS`. |
| `scripts/fsync_always_benchmark.sh`, `scripts/fsync_compare.py` | F0(iii). Second Redis, config verified on the live server before anything is measured. |
| `scripts/matrix_progress.py` | Remaining runs and wall time for a filtered invocation. |
| `redis/phase2-always.conf` | The durability config under test, beside the one it is compared against. |
| `experiments/tests/test_per_cell_regimes.py` | Pins §C.3 (5 tests). |
| `experiments/tests/test_figure_pooling.py` | Pins §C.4 (5 tests). |

### Modified

| File | Change |
|---|---|
| `experiments/analyze.py` | `regime` added to the per-cell grouping key and to `per-execution.csv`; `regime_label`; both figures re-pointed at `per_cell` within one named regime; figure 2's pooling corrected to a ratio of sums; the pooled-table warning now names the regime in the key. |
| `experiments/statistics.py` | `wilson_interval`, for figure error bars only, documented as not interchangeable with the CSV's cluster bootstrap. |
| `.gitignore` | LaTeX build products. |

---

## C. Raw command outputs

### C.1 F0(i) — standing rule 8, discharged

Session 3B ended without committing, which is itself a rule-8 violation by that
session; F0(i) is the remediation, and it is recorded rather than smoothed over.
30 files, 4 267 insertions.

```
$ git log --oneline -2
8446103 Phase 2B Session 3B: E1-E6 amendments, hard Redis kill, graded ambiguity
8c3663f Phase 2B Session 3: report, clock-suspension detection, tier-1 matrix results

=== CI run for 8446103 ===
run       31156350917
head_sha  84461031b0cb403872e3fa60a88576fab7e9cb55
status    completed
conclusion success

$ jobs
  success    Citation ranges (docs/22)
  success    WAITAOF durability (compose, phase2.conf)
  success    Suite (py3.13, Redis from compose)
```

Full output: `reports/raw/f0i-commit-and-ci.txt`.

### C.2 The manuscript, and the discipline it is written under

```
$ pdflatex main.tex; bibtex main; pdflatex main.tex; pdflatex main.tex
undefined(non-font): 0
pages: 13
todos: 0
```

The only remaining LaTeX warning is `Font shape T1/ptm/m/scit undefined` — a
small-caps-italic substitution, cosmetic.

**F3 is implemented as machinery, not as a habit.** Rather than write numbers
and annotate them, the tables and every headline scalar are *generated* from
the two permitted sources, each carrying its filter and arithmetic as a
comment. For example, from `paper/generated/numbers.tex`:

```latex
% per-cell-metrics.csv | system=AEP_FULL regime=(session-3) response_class=NO_READBACK
% metric=known_ambiguity_rate | sum(successes)/sum(total) = 130/180
\newcommand{\AepAmbNoReadback}{0.7222}
```

and from `paper/generated/table-latency.tex`:

```
% 'over B0' subtracts B0's median (2010.165771 ms), which is
% the no-protocol system on the same host and the same provider
% (configured delay 2000 ms; B0 sits above it by 10.2 ms, which is
% harness cost, not protocol cost).
```

The gate that enforces it:

```
$ uv run --frozen python scripts/check_paper_numbers.py
  PASS  per-cell-metrics.csv is keyed by regime
  PASS  paper_tables.py runs
  PASS  numbers.tex matches the CSVs
  PASS  table-ambiguity-by-crashpoint.tex matches the CSVs
  PASS  table-latency.tex matches the CSVs
  PASS  table-outcomes.tex matches the CSVs
  PASS  no generated table draws from the banned pooled table
  PASS  generated tables declare their sources
  PASS  state-machine figure matches the transition table
  PASS  bibliography has entries
  PASS  no empty bibliography entries
  PASS  bibtex reported no parse errors
  PASS  no undefined references or citations
  NOTE  0 \todoitem marker(s):
----------------------------------------------------------------------
13 passed, 0 failed
```

The state-machine figure is generated from the code's own edge set, so it
cannot disagree with the ten transitions the Lua script enforces:

```
% GENERATED by scripts/gen_state_machine.py -- do not edit.
% Edge set imported from aep_core.core.intents
% .LEGAL_INTENT_TRANSITIONS, so this figure cannot drift from
% the transition table the Lua script enforces.
% 10 edges, 6 states.
```

### C.3 A defect in the file the paper is told to quote

Session 3B §F2 banned `analysis/table-1.csv` because it pools three fault
regimes, and directed every reader to `per-cell-metrics.csv` instead. **That
remedy is only sound if the per-cell file does not have the same defect, and it
was one collected cell away from having it.**

`build_per_cell` grouped by `(system, crash_point, response_class,
readback_keying)` — no regime. Two of the five regimes report
`crash_point = "none"`, because no *worker* is killed in either:

* `p0` — crash-free, the only cells RQ3 may use;
* `redis-kill-preack` — Redis hard-killed and restarted mid-run.

They are told apart today only because `p0` happened to be collected against
`payments` and the Redis-kill cells against `NO_READBACK`. **`p0` on
`NO_READBACK` is in the 1 068-run plan.** Collect it, and a crash-free cell and
a hard-Redis-kill cell merge into one rate with nothing to say so.

```
$ pytest experiments/tests/test_per_cell_regimes.py -q   # pre-fix
5 failed in 0.19s
FAILED test_the_two_crash_free_regimes_do_not_merge_into_one_cell
FAILED test_session_threes_regime_is_labelled_rather_than_left_blank
FAILED test_regime_is_the_first_column_and_names_match_the_attributes
FAILED test_every_per_cell_row_carries_the_regime
FAILED test_the_per_execution_file_carries_the_regime_too

$ pytest experiments/tests/test_per_cell_regimes.py -q   # post-fix
5 passed in 0.04s
```

`regime` is now the first column of `per-cell-metrics.csv` and of
`per-execution.csv`, and Session 3's unnamed regime prints as `(session-3)`
rather than as an empty cell.

### C.4 Two figure-computation defects, neither visible in any output

**Figure 1 was drawn from the banned table.** `write_figures` took its bar
heights from `table_one` — the pooled table whose own warning says it is a
coverage summary and not a result. A banned table does not become quotable by
being drawn. Figure 1 is now pooled from `per_cell` inside one named regime,
and the regime is printed in the title so a reader cannot lose it.

**Figure 2 pooled response classes with a running mean:**

```python
current[row["crash_point"]] = (
    row["rate"] if previous is None else (previous + row["rate"]) / 2
)
```

under the comment `# Pool across response classes and keyings by weighting on
counts.` It does not weight on counts. It is order-dependent, and across three
response classes it weights the last-seen cell at 1/2, the one before at 1/4
and the first at 1/4.

```
$ pytest experiments/tests/test_figure_pooling.py -q   # post-fix
5 passed in 0.02s

The arithmetic the test pins, printed:
  cells (successes/total): [(1, 10), (0, 10), (30, 30)]
  correct pooled rate    : 31/50 = 0.6200
  old running mean       : 0.5250
  divergence             : 0.0950
```

Supporting change: `statistics.wilson_interval`, used **only** for figure error
bars. The CSVs keep their cluster bootstrap — executions inside a run are
correlated — but a figure that pools across cells has no cluster structure left
to resample, and a normal approximation puts bounds outside $[0,1]$ at the
exactly-zero rates three systems have. The docstring says the two are not
interchangeable and which to quote.

### C.5 Two silent failures in the citation apparatus

**A DOI written from memory did not exist.** `refs.bib`'s first draft carried
`10.1145/2181796.2229155` for Helland's *Idempotence Is Not a Medical
Condition*. Every DOI in the file was then resolved through `doi.org`:

```
DOI                                HTTP
---------------------------------- ----
10.1145/74850.74870                200
10.1145/38713.38742                200
10.1145/128765.128770              200
10.1145/319566.319567              200
10.1145/3149.214121                200
10.1145/226643.226647              200
10.1145/2160718.2160734            200
10.1145/3485510                    200
10.1145/3477132.3483541            200
10.1145/2181796.2187821            200
10.48550/arXiv.2403.16971          200
10.48550/arXiv.2603.20625          200
10.1145/2181796.2229155            404   <-- DOES NOT EXIST (written from memory)
```

The real records are `10.1145/2160718.2160734` (CACM 55(5), now used) and
`10.1145/2181796.2187821` (ACM Queue). **A DOI is exactly the kind of thing
that looks verified because it is well-formed.** This is what F4 means by a
D4-level halt, and the resolution check is the only reason it did not become
one. Raw: `reports/raw/f4-doi-resolution.txt`.

**The bibliography compiled completely blank and nothing said so.** Provenance
comments were written *inside* each entry. BibTeX does not accept `%` comments
inside an entry:

```
Database file #1: refs.bib
You're missing a field name---line 32 of file refs.bib
 :   % [DBLP][DOI] Gray, Cheriton. SOSP 1989, pp. 202-210. DOI resolved 2026-08-07.
(Error may have been on previous line)
I'm skipping whatever remains of this entry
[... x24 ...]

$ grep -A3 "bibitem{gray1989leases}" main.bbl
\bibitem{gray1989leases}

\bibitem{redis-waitaof}
```

All 24 entries rendered empty. LaTeX reported **no undefined citations** — the
keys existed, the entries were empty — so the build was clean and the
bibliography was blank. A second bite of the same apple followed: BibTeX's
scanner treats an at-sign as an entry start *even on a comment line*, so the
header comment explaining the first failure silently swallowed the two entries
after it.

Both are now checked against the artifact rather than the log:
`check_paper_numbers.py` greps `main.bbl` for empty `\bibitem` blocks and
`main.blg` for parse errors. After the fix:

```
$ grep -c bibitem main.bbl
24
$ grep -A3 "bibitem{gray1989leases}" main.bbl
\bibitem{gray1989leases}
C.~G. Gray and D.~R. Cheriton, ``Leases: An efficient fault-tolerant mechanism
  for distributed file cache consistency,'' in \emph{Proceedings of the 12th
  ACM Symposium on Operating Systems Principles (SOSP)}, 1989, pp. 202--210.
```

All 24 entries were verified against DBLP's search API and/or `doi.org` before
being written. Raw sweep: `reports/raw/f4-citation-verification.txt`.

### C.6 F0(ii) — the matrix finished, and the comparison is now four baselines

```
$ python scripts/matrix_progress.py --results-root experiments/results/matrix \
      --max-tier 1 --system B1_LEASE_ONLY --system B2_CAS_ONLY --system B3_INTENT_NO_BARRIER
selected runs  96
collected      96
remaining      0
```

Final coverage:

```
  "cells": 91,
  "executions": 2720,
  "runs": 326,
  "regimes": ["(session-3)", "p0", "redis-kill-preack"],
  "response_classes": ["AUTHORITATIVE_READBACK", "NO_READBACK", "POSITIVE_ONLY_READBACK"],
  "all_runs_used_real_sigkill": true,
  "runs_with_usable_timing": 176,
```

**The anchor table, from `per-cell-metrics.csv`, crashed regime only** — this
is what the paper prints, and it is single-regime by construction:

```
                                undetected duplicate          lost effect        declared ambiguity
system                       auth   pos-only   none    auth  pos-only  none   auth  pos-only    none
B0 naive retry             0.8200   0.8000   0.7733  0.0133   0.0133 0.0067 0.0000   0.0000  0.0000
B1 lease-only              0.8133   0.8067   0.8267  0.0000   0.0067 0.0067 0.0000   0.0000  0.0000
B2 CAS-only                0.8067   0.7933   0.7800  0.0067   0.0067 0.0000 0.0000   0.0000  0.0000
B4 durable, inf attempts   0.9500      ---      ---  0.0000      ---    --- 0.0000      ---     ---
B3 intent, no barrier      0.0000   0.0000   0.0000  0.0000   0.0000 0.0000 0.0000   0.3667  0.7167
AEP-full                   0.0000   0.0000   0.0000  0.0000   0.0000 0.0000 0.0000   0.3500  0.7222
```

**Session 3B's §F3 is closed.** The claim "the baselines do not notice" is now
evidenced against three baselines on all three endpoint capabilities, at
$n = 150$ executions per cell, not against B0 alone.

**Two things this table says that the previous slice could not.** First, the
baselines' duplicate rate is essentially *flat* across endpoint capability
(0.77–0.83) — what the endpoint can be asked afterwards makes no difference to
a system that does not ask. Second, **B3's declared-ambiguity column is
indistinguishable from AEP-full's** (0.3667/0.7167 versus 0.3500/0.7222). The
barrier is not what buys declared ambiguity, and the paper says so in the
motivating table rather than leaving a reviewer to find it (§F1 below).

The decomposition by crash point, which is the more informative view:

```
AEP-full known ambiguity   auth   pos-only    none
before_intent_write        0/30      0/30    0/30
after_intent_before_barrier 0/30    30/30   30/30
after_barrier_before_dispatch 0/30  30/30   30/30
mid_dispatch               0/30      0/30   30/30
after_response_before_res. 0/30      1/30   30/30
after_resolution_before_bar. 0/30    2/30   10/30
```

The rate is zero where the crash precedes the intent (nothing was promised) and
maximal where the crash precedes the dispatch (no effect can exist, and the
endpoint cannot say so). The protocol's errors run toward *claiming it might
have done something it did not*, never toward silence about something it did.

### C.7 F0(iii) — the barrier's cost as a function of durability config

**The gate fired twice before any number was produced, and both times it was
right to.** The benchmark reads `CONFIG GET appendfsync` back off the live
server and refuses to proceed unless it reads `always`:

```
$ redis-cli CONFIG GET appendfsync
appendfsync = everysec
$ redis-cli CONFIG GET appendonly
no

REFUSING TO MEASURE: appendfsync is 'everysec', not 'always'.
```

The container had come up on its compiled-in defaults because the bind mount
did not resolve. Two attempts failed this way — first from the WSL distro's
`/tmp`, then from `/mnt/d/...`. The cause:

```
$ docker inspect aep-phase2-redis72 --format '{{range .Mounts}}{{.Source}}{{end}}'
D:\personal\AEP\Research-paper-AEP\redis\phase2.conf
```

This Docker Desktop resolves bind-mount sources in the **Windows** filesystem;
`docker` inside WSL is a wrapper forwarding to `docker.exe`. A `/mnt/d` source
produced an *empty directory* at the mount point:

```
$ docker run --rm -v "/mnt/d/.../phase2-always.conf:/probe.conf:ro" alpine cat /probe.conf
cat: read error: Is a directory
```

**Without the gate this would have shipped a number labelled `always` measured
under `everysec`.** A third guard then fired — the Phase 2A disposable-instance
marker — which is also correct behaviour and is now set explicitly by the
script.

With all three satisfied, the identical cell (same system, endpoint, regime,
seeds, host, provider) under the two policies:

```
appendfsync     runs   exec   median ms     p95 ms   over 2000ms floor
everysec           3     30      4004.9     6892.9              2004.9
always             3     30      2063.4     5067.8                63.4

Two WAITAOF barriers cost 2004.9 ms under everysec and 63.4 ms under always.
Difference: 1941.5 ms.
```

**A factor of 31, for one line of configuration.** Under `everysec` an
acknowledgement waits for the next scheduled fsync, up to a second away, twice;
under `always` the fsync has already happened when the write returns.

**The caveat is stated in the paper with the number.** This measures *latency*,
not the throughput cost the Redis documentation warns about. Our workload — two
workers, a 2-second provider delay — is latency-bound and cannot exercise an
fsync-rate limit; throughput was in fact *higher* under `always` (0.42 vs 0.33
executions/s), which is a statement about this workload's shape and not about
Redis.

The separated numbers F3 asks for: the protocol minus the barrier is
**28.0 ms** (B3 − B0), and the barrier is **1 966.7 ms** under `everysec` and
≈25 ms under `always`.

### C.8 F0(iv) — the freeze

```
$ uv run --frozen python scripts/freeze_results.py --results-root experiments/results/matrix
wrote experiments/results/matrix/MANIFEST.md
wrote experiments/results/matrix/MANIFEST.csv
wrote experiments/results/matrix/SHA256SUMS  (17 files)

completed runs 326   executions 2720 (2450 crashed)   cells 91   incomplete dirs 2
  incomplete: analysis-interim
  incomplete: b4_durable_workflow-after_barrier_before_dispatch-payments-11d6b7e1-r2
```

The manifest agrees with the analysis **by construction**: `freeze_results.py`
loads each run through `experiments.analyze.load_run` rather than re-deriving
anything. Its first version did re-derive, and got three fields wrong —
`executions` is spelled `executions_planned`, `response_class` is not in the
run config at all (it is a property of the endpoint) — and reported **0
executions over 37 cells where the analysis saw 2 720 over 91**. A manifest
that disagrees with the analysis is a second, quieter set of numbers.

By regime:

| regime | cells | runs |
|---|---|---|
| `(session-3)` | 82 | 245 |
| `p0` | 7 | 21 |
| `redis-kill-preack` | 2 | 60 |

Archive: 4.8 MB, 6 731 entries, SQLite `-shm`/`-wal` sidecars excluded.

```
$ sha256sum aep-matrix-results-2026-08-07.tar.gz
84eed525309d98fca98bd76074ced79c06ba739e2c4022ac263c6a24bb831c46
```

Tracked copies of the manifest, the digests and the quotable CSV are in
`reports/raw/f0iv-*`.

### C.9 F1 and F2 — what the paper claims, checked against Session 3B

**F1.** §6.2 of the paper is split in two, deliberately. §6.2.1 is titled *A
negative result that narrows our own claim* and states that a process kill
cannot lose an unfsynced AOF write (0/10 in the probe, 30/30 and 30/30 canaries
in the cells), that the barrier's durability benefit is therefore
**unobservable under any process-level fault**, and that the fault class it
holds against is host power loss, kernel panic or VM destruction — which was
not injected. §6.2.2 gives the benefit that *is* measured: 10/30 versus 28/30
applied, Fisher $p = 1.9\times10^{-6}$, with both qualifications Session 3B
required (the 10/30 is a race created by kill latency, and the effect size is a
property of this host's `docker` latency, not a constant of the protocol).

The words "the barrier keeps the record across a crash" appear nowhere.

**F2.** The trilemma is the frame in three places: §1.2 defines it as the
paper's central move, §2 instantiates it per baseline as
\cref{tab:trilemma} — **including B3, added after the closeout data showed B3
declares ambiguity at the same rate as AEP-full**, so the table does not imply
the barrier buys it — and §6.1's anchor table is per endpoint capability and
single-regime. B4 and B4b are presented with `B4_SEMANTICS.md`'s Temporal
citations and an explicit statement of what B4b models.

**Known-ambiguity numbers are quoted per endpoint capability, never pooled.**
The pooled `AEP_FULL` figure of 0.3717 that `analyze.py` prints appears nowhere
in the manuscript.

### C.10 F5 — threats to validity

All six required items are present: single-node and single trust domain; mock
API realism; the Windows-development/Linux-measurement split; the E1 fault-class
limitation (given its own leading paragraph, since it is the sharpest); B4's
modelling scope with a 13-row knob table cited; and the resume-defect class,
stated with the safeguard (`discard_stale_shards`, what it deletes and what it
deliberately does not).

Three more were added because a reviewer would raise them first: declared
ambiguity is not evaluated as an operational outcome (no operator study); the
motivating traces come from our own harness and are not field evidence; and one
author implemented every system under comparison.

### C.11 The suite

Run on an idle machine — Session 3B §F9 warns the suite must not compete with a
matrix, and the matrix had finished.

```
$ uv run --frozen python -m pytest experiments/ -q
407 passed, 25 skipped, 1 warning in 15.92s

$ REDIS_URL=redis://127.0.0.1:6381/15 uv run --frozen python -m pytest tests/ -q
1256 passed, 9 skipped in 18.61s
```

**A correction to Session 3B §F8.** It recorded
`test_cleanup_spans_more_keys_than_one_scan_batch` as failing *on Windows* and
concluded "the Linux suite with real Redis is the one the artifact rests on".
The OS is not the variable. It fails wherever `fakeredis` is the backend and
passes wherever real Redis is, on either platform:

```
$ pytest tests/test_conftest_safety.py -q          # no REDIS_URL -> fakeredis
1 failed, 20 passed in 0.12s

$ REDIS_URL=... pytest tests/test_conftest_safety.py -q   # real Redis
21 passed in 0.30s
```

The conclusion §F8 drew was right; its reason was wrong, and the corrected
reason is more useful, because it says exactly which invocations are
trustworthy.

---

## D. Requirement checklist

| # | Requirement | Status | Evidence |
|---|---|---|---|
| F0(i) | Commit/push Session 3B | ✅ | 8446103 pushed; §C.1 |
| F0(i) | Green CI | ✅ | run 31156350917, 3/3 jobs; §C.1 |
| F0(ii) | Remaining B1/B2/B3 cells finish | ✅ | 96/96; §C.6 |
| F0(iii) | `appendfsync always`, one config, crash-free, AEP-full only | ✅ | §C.7 |
| F0(iii) | Barrier cost stated as a function of durability config | ✅ | 2 004.9 ms vs 63.4 ms; §C.7 |
| F0(iv) | `analyze.py` final pass | ✅ | §C.6, `reports/raw/f0iv-final-analysis.txt` |
| F0(iv) | `per-cell-metrics.csv` the only quotable source | ✅ **and made safe to be one** | §C.3 |
| F0(iv) | Table-1-pooled banned | ✅ enforced by a check | §C.2 |
| F0(iv) | Archive with a manifest of run counts per cell | ✅ | §C.8 |
| F1 | Barrier claim = dispatch withholding, not durability | ✅ | §C.9 |
| F1 | Name the fault class it holds against and the one where it is unobservable | ✅ | §C.9 |
| F1 | Cite the E1 probe | ✅ | §6.2.1 cites 0/10 and the canaries |
| F1 | Known-ambiguity per capability, never pooled | ✅ | §C.9 |
| F2 | Trilemma frames intro and evaluation | ✅ | §C.9 |
| F2 | Per-capability table as anchor | ✅ | `tab:outcomes`; §C.6 |
| F2 | B4/B4b with Temporal citation and what B4b models | ✅ | §2.4, §7 |
| F3 | Every number points to its CSV cell | ✅ generated, not annotated | §C.2 |
| F3 | Absolute timings only from suspend-gated runs | ✅ | E5 gate; 176 of 326 runs usable |
| F3 | 28 ms and barrier cost reported separately | ✅ | §C.7 |
| F3 | Test counts never cited as protocol assurance | ✅ | §5 says so explicitly |
| F4 | ALL sections drafted including evaluation | ✅ | 9 sections, 13 pages |
| F4 | `\todo` only where completion cells could move a value | ✅ | 3 during drafting, **0 at freeze** |
| F4 | IEEEtran TSE format | ✅ | compiles |
| F4 | Every citation verified to exist | ✅ | 24/24; one fabrication caught | 
| F5 | Six named threats | ✅ + 3 more | §C.10 |
| Rule 8 | Commit all work | ✅ | 3 commits |
| Rule 8 | Push, confirm CI green **before** the report | ❌ **BLOCKED** | §E1 |

---

## E. Deviations from the amendments

**E1. Rule 8's push is not done, and this report was written anyway.** Two
pushes succeeded this session (`8446103`, `6cd6815`). The third hangs: the
credential helper wedged, and after it was killed, push fails outright.

```
$ git -c credential.helper= push
fatal: unable to get password from user

$ git ls-remote origin main     # reads still work
6cd6815cc3437ccac27c9d6ab46205fd0cb726fa        refs/heads/main
```

Three commits are local-only — `f3808d4`, `118731c`, and the commit carrying
this report. **CI has not run on any of them.** Rule 8 says a session whose
work is not pushed is not complete, and by that standard this session is not
complete. Writing the report before the push is the deviation; the alternative
was to withhold the report entirely, which would have lost the findings without
making the push succeed. The one command needed is in §H.

**E2. The `appendfsync always` benchmark measures latency, not throughput.**
F0(iii) asked for "one config, crash-free, AEP-full only", which is what was
run. That shape cannot exercise the cost `always` is actually known for. The
paper states this beside the number rather than letting the 31× read as an
unqualified recommendation.

**E3. The suite's `tests/` half needed `REDIS_URL` set to be meaningful**, and
the first run this session omitted it and produced a failure that is a
`fakeredis` artifact. Both invocations are recorded in §C.11 rather than only
the passing one.

**E4. Two figure defects and one grouping defect were fixed in `analyze.py`
during a session whose scope was the manuscript.** They were found by trying to
use the outputs, and leaving a known-wrong figure generator in the artifact
while writing a paper about measurement discipline was not defensible. Each is
pinned by tests.

---

## F. The draft read as a hostile TSE reviewer

What follows is the review I would write if I wanted to reject this paper.
Ordered by how much damage each objection does.

### F1. "Your headline result does not need your headline mechanism."

The strongest attack, and the closeout data made it stronger. AEP-full and B3
are now measured as **indistinguishable on every RQ1 cell**: zero undetected
duplicates, zero lost effects, and declared ambiguity within 0.006 of each
other (0.3500 vs 0.3667, 0.7222 vs 0.7167). B3 is AEP-full with the durability
barrier removed. So the paper's central claim is delivered entirely by the
write-ahead intent, the fenced CAS and the recovery classifier — and **not at
all** by the ack→authorization→preflight chain that is its most novel design
work.

The paper's answer is §6.2: the barrier's contribution appears only under
infrastructure faults, where it is large. That is a real answer. A reviewer is
still entitled to say: *then the contribution is a write-ahead intent ledger
with fail-closed classification, which is architecturally unsurprising, plus
one dispatch gate evidenced by a single 60-run experiment on a single fault.*

The draft now includes B3 in the trilemma table precisely so this is visible
rather than discovered. That is honest but it is not a defence.

**Severity: high. Not fixable by writing.**

### F2. "Your comparison is against baselines you wrote, on a mock you wrote."

Every system in the anchor table is the authors' code; the oracle is the
authors' service. `B4_SEMANTICS.md` defends B4's re-execution policy against
Temporal's documentation — more than most papers do — but it defends *one*
modelling decision. Nothing defends B0's retry predicate, B1's lease
parameters, or the provider's 15% timeout rate, each of which moves the rates.

The threats section now names this. Naming is not answering. One measurement
against a real Temporal worker on the same mock provider would convert the
strongest fairness objection into a data point.

**Severity: high. Addressable.**

### F3. "n=3 for every timing number, one endpoint, one virtualised host."

Three crash-free runs per system; one endpoint for all of RQ3; WSL2 with Docker
Desktop port forwarding in the latency path. The paper is candid about all of
it, and candour does not widen an interval. The `p0` cells cost ~45 s each — the
timing story could be made ten times stronger in under an hour, and was not.

**Severity: medium. Cheap to fix.**

### F4. "You measure that AEP declares ambiguity. You never show that declaring
helps."

The normative core — a declared incident beats an undiscovered one — is
asserted. There is no operator study, no resolution data, no evidence the
declared-ambiguity queue stays bounded. At 0.72 on a `NO_READBACK` endpoint a
reviewer can fairly ask whether the system is usable at that rate. §6.1 now
owns the cost explicitly and threats records the gap, which is the right move
and does not close it.

**Severity: medium-high, and higher at a software-engineering venue than it
would be at a systems one.**

### F5. "Your motivating study is not a study."

§2 replays four traces from the authors' own harness. The roadmap asked for
exactly that, so the section does what was specified — but there is no evidence
about how often real deployments meet non-idempotent endpoints without
idempotency keys. The premise of the whole paper rests on argument. A survey of
a dozen real enterprise APIs' idempotency support would close it cheaply and
would strengthen the introduction more than anything else available.

**Severity: medium.**

### F6. "You prove the barrier is unnecessary for every fault you injected, and
keep it anyway at 98% of your latency."

§6.2.1 establishes that `appendonly yes` alone survives every injected fault,
and §6.3 measures the barrier at 1 966.7 ms of a 2 038 ms protocol. The
justification is a dispatch-gate benefit plus an argument about host-level
faults that were not injected. The `appendfsync always` comparison helps — it
shows the cost is a configuration choice — but it supplies no missing fault.

**Severity: medium. It is the predecessor report's open question G1, still
open.**

### F7. Smaller things a reviewer would list without comment

1. **Thirteen pages is short for TSE**; signals a thin evaluation to a skimmer.
2. **RQ4 reports almost nothing.** Recovery latency is withheld because the E5
   gate leaves too few gated crashed runs. Correct call; leaves a research
   question with no numbers. Either collect gated crashed runs or fold RQ4 into
   RQ1.
3. **B4 and B4b are `auth`-only at n=20 and n=30** while every other system has
   three capabilities at n=150–180. The three-way trilemma argument is
   confirmed in shape and is not powered.
4. **The Wilson interval in the figures differs from the bootstrap in the
   CSVs.** Documented in code, not in the paper.
5. **No page-limit discipline yet** — no author bios, no anonymisation
   decision, placeholder author block.

### F8. What I would not attack

- Every number traces to a CSV cell and a script fails the build on drift.
- The negative result is stated by the authors before a reviewer could find it,
  with the mechanism explained and the claim narrowed.
- The non-claims table and declared residual windows are unusually complete,
  and the residuals are probe-confirmed rather than asserted.
- Regimes are never pooled, and the paper explains why the pooled table its own
  tool emits is not quotable.
- §6.1.2 pre-empts the best technical question in the paper (why the
  provably-empty crash point is not resolved) with a mechanism and a price.
- The bibliography is verified by resolution, and the one fabricated DOI that
  entered the file was caught by that check.

---

## G. Open questions needing a human/architect decision

1. **Can the paper obtain a host-level fault?** Unchanged from Session 3B §G1
   and now the single largest determinant of how F1 and F6 above land. Options
   in increasing cost: `virsh destroy` on a local VM; a cloud instance
   force-stopped; `dm-flakey` with `drop_writes` under the AOF directory; or
   keeping the narrowed claim. **Recommendation: `dm-flakey` is a day of work
   and would convert the paper's weakest claim into a measured one.**

2. **Should a real Temporal worker be run?** F2 above. It is the cheapest
   available answer to the fairness objection and it would either confirm B4 or
   invalidate it — both are publishable, and finding out before a reviewer does
   is strictly better.

3. **Is the contribution the protocol or the composition?** F1 above forces a
   framing decision that only an author can make. If the honest answer is "the
   fail-closed composition, of which the barrier is one part", the paper should
   say that in §1 rather than positioning the ack chain as the novelty.

4. **How much more matrix is worth collecting?** 742 of 1 068 runs are
   unstarted. The ones that change a claim are: B4/B4b on all three
   capabilities (~144 runs, closes F7.3), more `p0` runs (~minutes each, closes
   F3), and `redis-kill-inflight` (~60 runs, records a predicted tie). The
   remaining ~500 are the `ORACLE_FINGERPRINT` sensitivity variant and change
   nothing the paper claims.

5. **Venue and anonymisation.** The draft carries a placeholder author block.
   TSE is not double-blind; a workshop version would be.

---

## H. Recommended next phase and its prerequisites

**Prerequisite, before anything else: push.** Three commits are local-only and
unverified by CI.

```
git push        # re-authenticate when the credential helper prompts
```

Then confirm all three CI jobs are green on the final commit. Until that is
done the session is incomplete by rule 8, and the report above should be read
as provisional in exactly that respect.

**Next, in value order:**

1. **Decide G1 (host-level fault), and if yes, run it.** It is the difference
   between a measured claim and an argued one, and it is the first thing a
   Redis-literate reviewer will ask about.
2. **Run a real Temporal worker against the mock provider.** One cell, three
   endpoints. Closes the fairness objection that currently has no answer.
3. **Collect B4/B4b on all three capabilities** (~144 runs, ~7 h). Turns the
   trilemma table's third row from a shape into data.
4. **Ten more `p0` runs per system** (~30 min). Turns every timing number from
   n=3 into something defensible.
5. **Then polish for submission**: author block, page budget, a related-work
   comparison table (drafted), and a final `check_paper_numbers.py` run.

**Deliberately not recommended:** finishing the matrix. The
`ORACLE_FINGERPRINT` tier is ~500 runs and ~11 h and changes no claim in the
paper.
