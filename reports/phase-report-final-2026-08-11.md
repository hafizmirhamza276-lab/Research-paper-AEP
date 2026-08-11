# Final pre-submission session — three repository defects closed, and the one that could not be

**Date:** 2026-08-11
**Predecessor:** `reports/audit-report-2026-08-10.md` (the Monday audit; verdict
FIX FIRST, defect list §4.2, fix log for F1/F2/F3, human residual checklist §4.4)
**Range:** `399e502` (audit head) → this session's head.

**Headline:** T2 (D12), T3 (D6) and T4 (D11) were completed in the first half of
the session. T1 was BLOCKED-INPUT at that point — the HUMAN INPUT block arrived
with all four fields as literal underscores — and was resumed later in the same
session when the human supplied two of the four. **T1 is now complete for the
fields supplied**, together with an authorised §F.1 follow-up that qualifies the
D6 ratio with its propagated uncertainty.

**One field is still absent, by the human's own hand rather than by mine:
affiliation.** The resume message supplied `Author name(s)` and `Email(s)` and
omitted the `Affiliation(s)` and `ORCID` lines entirely. ORCID is marked
optional in the prompt, so its absence is in specification. Affiliation is not
optional and **I did not invent one** — no institution, and not
"Independent Researcher" either, which would be an invented affiliation wearing
a generic label. The author block renders exactly the two fields given. §E.8
records this and §H states what it costs.

Everything below reflects the whole session, first half and resume.

---

## A. Phase attempted and scope reference

Final pre-submission session as specified: the author block (T1), D12 (T2), D6
(T3), D11 (T4), then gates and close (T5). Nothing else.

**Working tree.** `D:\personal\AEP\audit-clone` — the clone the Monday audit
worked in. It is the tree that holds `reports/audit-report-2026-08-10.md` and it
sits on the tip of `origin/main`. The sibling tree
`D:\personal\AEP\Research-paper-AEP` is the older development clone, two commits
behind at `a03985c` and with no uncommitted tracked changes; it was not touched
this session and is noted in §G.4 as something the human may want to reconcile.

**Scope bounds observed.** Modified only: `.gitattributes` (T2),
`scripts/paper_tables.py` (the new ratio macro and the caption sentence only),
`tests/test_paper_tables.py` (additions only), `paper/generated/**` (via the
committed generator only), `paper/sections/08-threats.tex` (the one sentence),
`paper/main.pdf` and `paper/main-anon.pdf` (rebuilds), and this report.
`paper/main.tex` was in scope for T1: **unmodified through §C–§H below, then
modified in the resume** once the human supplied the fields — author block only,
diff in §R.B. `paper/sections/06-evaluation.tex` was forbidden and is untouched
throughout — proved in §C.9 and re-proved after the resume.

**Standing rules.** No history rewriting (two new commits, no amend, no rebase,
no force). No edits to frozen results (`git log --diff-filter=DM --
experiments/results` empty, §C.10). No gate weakened. **External actions: `git
fetch`, `git clone` (local, to scratch directories now deleted), `git push`, and
read-only `GET`s to `api.github.com` for run status. `apt-get` and one Ubuntu
mirror `GET` inside throwaway containers. Nothing uploaded, submitted or
published; no account, release, release asset, draft or tag created or moved.**

---

## B. Files created/modified — the FULL list

| File | A/M | Why |
|---|---|---|
| `.gitattributes` | M | T2 — the `*.sh text eol=lf` rule, plus a comment block in the file's own house style |
| `scripts/paper_tables.py` | M | T3 — `tex_sigfigs` helper, `import math`, the `\BarrierToProtocolRatio` macro. T4 — one sentence in the `table-outcomes` caption |
| `tests/test_paper_tables.py` | M | T3/T4 — three added tests and one added import; **additions only**, no existing test changed |
| `paper/generated/numbers.tex` | M | generator output: +5 lines (three comment lines and the new macro, plus its blank) |
| `paper/generated/table-outcomes.tex` | M | generator output: the caption line |
| `paper/sections/08-threats.tex` | M | T3 — the one sentence at `:369`; 4 lines reflowed, meaning otherwise unchanged |
| `paper/main.pdf` | M | rebuild (public) |
| `paper/main-anon.pdf` | M | rebuild (anonymous) |
| `reports/phase-report-final-2026-08-11.md` | A | this report |

**Not modified, and each for a stated reason:**

- `paper/main.tex` — T1's target. Blocked on unfilled input at this point in the
  session (§E.1); **modified in the resume**, author block only (§R.A, §R.B).
- `paper/sections/06-evaluation.tex` — forbidden this session. `git diff` for it
  is empty (§C.9), and still empty after the resume.
- Everything else in the repository.

*(The table above covers the first half of the session. The resume adds
`paper/main.tex` and re-touches four of these files; its own full list is §R.A.)*

Nothing under `aep_core/**`, `experiments/**`, `docs/**`, `.github/**`, or any
`scripts/` file other than `paper_tables.py` was touched.

---

## C. Raw command outputs

### C.1 Git prelude

```
$ git fetch origin
(no output, exit 0)

$ git status -uno
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit (use -u to show untracked files)

$ git rev-list --left-right --count origin/main...main
0	0
```

Not diverged, no uncommitted changes. Proceeded.

### C.2 T2 — D12 reproduced before it was fixed

This clone inherits `core.autocrlf=true` from the Git-for-Windows system config,
so the defect is live here rather than hypothetical:

```
$ git config --get core.autocrlf
true
$ git config --system --get core.autocrlf
true
```

Committed blobs against the working tree, all 11 tracked shell scripts:

```
=== committed blob CR counts (git show = blob bytes) ===
scripts/build_paper.sh                        CR=0
scripts/fsync_always_benchmark.sh             CR=0
scripts/smoke_matrix.sh                       CR=0
scripts/sync_measurement_tree.sh              CR=0
scripts/wsl_docker_shim.sh                    CR=0
scripts/wsl_launch_matrix.sh                  CR=0
scripts/wsl_mock_api.sh                       CR=0
scripts/wsl_run.sh                            CR=0
scripts/wsl_setup.sh                          CR=0
scripts/wsl_suite.sh                          CR=0
scripts/wsl_sync.sh                           CR=0

=== CR count in worktree copies (same 11 files) ===
scripts/build_paper.sh                   CR=122
scripts/fsync_always_benchmark.sh        CR=187
scripts/smoke_matrix.sh                  CR=23
scripts/sync_measurement_tree.sh         CR=76
scripts/wsl_docker_shim.sh               CR=27
scripts/wsl_launch_matrix.sh             CR=33
scripts/wsl_mock_api.sh                  CR=37
scripts/wsl_run.sh                       CR=13
scripts/wsl_setup.sh                     CR=18
scripts/wsl_suite.sh                     CR=23
scripts/wsl_sync.sh                      CR=31
```

Pure LF in the repository, CRLF on disk. Exactly the audit's D12.

### C.3 T2 — zero `.sh` blob content change

```
$ git add --renormalize -- '*.sh'
$ git diff --cached --numstat
(empty)

$ git diff --stat
 .gitattributes | 14 ++++++++++++++
 1 file changed, 14 insertions(+)
```

Renormalising all 11 scripts under the new rule stages **nothing**. The rule
changes the checkout, not the content. The commit confirms it:

```
$ git show --stat HEAD
4b910d3 D12: shell scripts reach a POSIX shell as LF in every clone

 .gitattributes | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

$ git show --numstat --format='' HEAD -- '*.sh'
(empty)
```

### C.4 T2 — the scratch-clone proof, before and after

Both clones made with `-c core.autocrlf=true` against the local repository, into
directories outside it.

**BEFORE** (clone of `399e502`, the audit head, without the rule):

```
HEAD: 399e502 Audit: record the two green runs, and the external actions taken
autocrlf: true
CRLF pairs: 122

line 30 bytes: b'set -euo pipefail\r\n\r\nANON'
```

`--help` is not a flag this script has, so the proof is the behavioural one D12
names, run under real POSIX bash:

```
=== BEFORE the fix: real POSIX bash (ubuntu:24.04), autocrlf=true clone ===
scripts/build_paper.sh: line 30: set: pipefail: invalid option name
SCRIPT EXIT=2
```

**AFTER** (clone of `4b910d3`, with the rule):

```
HEAD: 4b910d3 D12: shell scripts reach a POSIX shell as LF in every clone
autocrlf: true

=== CRLF census over all 11 tracked .sh, AFTER the fix ===
scripts/build_paper.sh                        CRLF=0    loneCR=0
scripts/fsync_always_benchmark.sh             CRLF=0    loneCR=0
scripts/smoke_matrix.sh                       CRLF=0    loneCR=0
scripts/sync_measurement_tree.sh              CRLF=0    loneCR=0
scripts/wsl_docker_shim.sh                    CRLF=0    loneCR=0
scripts/wsl_launch_matrix.sh                  CRLF=0    loneCR=0
scripts/wsl_mock_api.sh                       CRLF=0    loneCR=0
scripts/wsl_run.sh                            CRLF=0    loneCR=0
scripts/wsl_setup.sh                          CRLF=0    loneCR=0
scripts/wsl_suite.sh                          CRLF=0    loneCR=0
scripts/wsl_sync.sh                           CRLF=0    loneCR=0

line 30 bytes: b'set -euo pipefail\n\nANON=0'

=== AFTER the fix: real POSIX bash (ubuntu:24.04), autocrlf=true clone ===
=== pdflatex / bibtex / pdflatex x2 (main) ===
scripts/build_paper.sh: line 46: pdflatex: command not found
SCRIPT EXIT=127
```

The script now runs past its own line 30 and reaches line 46, where a bare
`ubuntu:24.04` image has no TeX. That is the unrelated, expected failure; the
D12 failure is gone.

Both scratch clones were then deleted:

```
$ rm -rf D:/personal/AEP/d12-scratch-before D:/personal/AEP/d12-scratch-after
$ ls D:/personal/AEP
.ai  audit-clone  Research-paper-AEP
```

**One finding worth recording, because it explains why D12 survived this long.**
Git Bash does **not** reproduce it. The MSYS2 runtime strips the CR when it
reads a script, so the same CRLF file that kills `ubuntu:24.04` bash at line 30
runs fine under the shell a Windows developer is most likely to use. The
evaluator path the artifact actually documents — clone, then WSL or Docker — is
the one that breaks.

### C.5 T3 — the source values, and the objection tested before the macro was written

```
AEP_FULL                             median=4004.893692  crash_free_runs=3
B0_NAIVE_RETRY                       median=2010.165771  crash_free_runs=3
B3_INTENT_NO_BARRIER                 median=2038.206892  crash_free_runs=3

BarrierCost          = aep - b3 = 4004.893692 - 2038.206892 = 1966.6868000000002
ProtocolMinusBarrier = b3 - b0  = 2038.206892 - 2010.165771 = 28.041120999999976
ratio                = 1966.6868000000002 / 28.041120999999976 = 70.13581233075531
```

`paper_tables.py` already carries a refusal to emit a ratio
(`\BarrierCost / \BarrierCostAlways`) because that denominator's cluster
bootstrap spans zero. Before adding a ratio through a *different* denominator I
checked whether the same objection applies, using the repository's own bootstrap
function:

```
runs: b0=3 b3=3 aep=3

DENOMINATOR  ProtocolMinusBarrier (B3 - B0), everysec:
  point=30.5  95% CI = [27.1, 1524.6]   spans zero: False

NUMERATOR    BarrierCost (AEP - B3), everysec:
  point=1968.1  95% CI = [477.9, 1978.8]   spans zero: False
```

It does not apply: the denominator's interval is entirely positive, so the
quotient is defined across it. **The interval is nevertheless very wide, and
that is this session's sharpest self-criticism — §F.1.**

### C.6 T3 — the generated macro

```
% latency-and-throughput.csv | \BarrierCost / \ProtocolMinusBarrier, both under appendfsync=everysec
% = (4004.9 - 2038.2) / (2038.2 - 2010.2) = 1966.7 / 28.0 = 70.14, to two significant figures
% how much more the two fsync barriers cost than everything else the protocol does
\newcommand{\BarrierToProtocolRatio}{70}
```

Macro census, and the use count the "every generated number is used" gate cares
about:

```
=== macro count in numbers.tex: was 89 ===
now: 90

=== uses of the new macro across the manuscript ===
paper/generated/numbers.tex:106:\newcommand{\BarrierToProtocolRatio}{70}
paper/sections/08-threats.tex:370:\BarrierToProtocolRatio{} (\cref{tab:latency}). AEP is for the case where the
```

One definition, one use. The gate stays green (§C.11).

### C.7 T3 — the sentence

Line verified first:

```
$ awk 'NR>=365 && NR<=372 {printf "%d: %s\n", NR, $0}' paper/sections/08-threats.tex
...
368: tool. Its cost is real: two fsync barriers, which under \texttt{appendfsync
369: everysec} dominate the protocol's latency by two orders of magnitude
370: (\cref{tab:latency}). AEP is for the case where the precondition those systems
```

The change:

```diff
 tool. Its cost is real: two fsync barriers, which under \texttt{appendfsync
-everysec} dominate the protocol's latency by two orders of magnitude
-(\cref{tab:latency}). AEP is for the case where the precondition those systems
-require cannot be obtained, and its value is a declared residual rather than a
-better guarantee.
+everysec} dominate the protocol's latency by a factor of roughly
+\BarrierToProtocolRatio{} (\cref{tab:latency}). AEP is for the case where the
+precondition those systems require cannot be obtained, and its value is a
+declared residual rather than a better guarantee.
```

And the phrase is gone from the whole manuscript, not just this line:

```
$ grep -rn "orders of magnitude\|order of magnitude" paper/ --include=*.tex
(exit 1 -- no hits)
```

### C.8 T4 — the caption, and the data behind it

The generated diff is one line:

```diff
-\caption{The trilemma, measured. ... pooled across crash points within one endpoint capability. \textsc{auth}/...
+\caption{The trilemma, measured. ... pooled across crash points within one endpoint capability. B0--B2 pool over five of those six rather than all of them --- \texttt{after\_intent\_before\_barrier} cannot occur in a system that writes no intent, so for those three there is no such cell to pool --- and the per-crash-point rates behind every cell here are in \texttt{per-cell-metrics.csv}. \textsc{auth}/...
```

The generator's own denominator census, from the same run, in the same file:

```
%   B0_NAIVE_RETRY                     AUTHORITATIVE_READBACK   executions=150   runs=15   crash_points=5
%   B0_NAIVE_RETRY                     POSITIVE_ONLY_READBACK   executions=150   runs=15   crash_points=5
%   B0_NAIVE_RETRY                     NO_READBACK              executions=150   runs=15   crash_points=5
%   B1_LEASE_ONLY                      AUTHORITATIVE_READBACK   executions=150   runs=15   crash_points=5
   ... (B1, B2 the same)
%   B4_DURABLE_WORKFLOW                AUTHORITATIVE_READBACK   executions=180   runs=18   crash_points=6
%   B4B_DURABLE_WORKFLOW_AT_MOST_ONCE  AUTHORITATIVE_READBACK   executions=180   runs=18   crash_points=6
%   B3_INTENT_NO_BARRIER               AUTHORITATIVE_READBACK   executions=180   runs=18   crash_points=6
%   AEP_FULL                           AUTHORITATIVE_READBACK   executions=180   runs=18   crash_points=6
```

And the claim about *which* point is missing, re-derived from the raw CSV rather
than taken from the audit:

```
all crash points seen: 6
AEP_FULL                             n=6  missing=[]
B0_NAIVE_RETRY                       n=5  missing=['after_intent_before_barrier']
B1_LEASE_ONLY                        n=5  missing=['after_intent_before_barrier']
B2_CAS_ONLY                          n=5  missing=['after_intent_before_barrier']
B3_INTENT_NO_BARRIER                 n=6  missing=[]
B4B_DURABLE_WORKFLOW_AT_MOST_ONCE    n=6  missing=[]
B4_DURABLE_WORKFLOW                  n=6  missing=[]
```

Exactly the three baselines, exactly that one point. The caption says what the
data says.

Both generated files were produced by the committed generator, invoked with the
Makefile's own arguments — nothing hand-edited:

```
$ uv run --frozen python scripts/paper_tables.py \
    --analysis experiments/results/matrix/analysis \
    --fsync-analysis experiments/results/fsync-always/analysis \
    --flakey experiments/results \
    --out paper/generated
wrote paper\generated\numbers.tex
wrote paper\generated\table-ablation.tex
wrote paper\generated\table-ambiguity-by-crashpoint.tex
wrote paper\generated\table-deployment-choice.tex
wrote paper\generated\table-latency.tex
wrote paper\generated\table-outcomes.tex

$ git diff --stat -- paper/generated
 paper/generated/numbers.tex        | 5 +++++
 paper/generated/table-outcomes.tex | 2 +-
 2 files changed, 6 insertions(+), 1 deletion(-)
```

Four of the six generated files are byte-identical to what was committed. Only
the two that should have changed did.

### C.9 Scope proof — `06-evaluation.tex` untouched

```
$ git diff -- paper/sections/06-evaluation.tex
(empty)

$ git status --porcelain
 M paper/generated/numbers.tex
 M paper/generated/table-outcomes.tex
 M paper/main-anon.pdf
 M paper/main.pdf
 M paper/sections/08-threats.tex
 M scripts/paper_tables.py
 M tests/test_paper_tables.py
```

Seven files, all in bounds. `paper/main.tex` is absent from the list because T1
is blocked.

### C.10 Frozen results

```
$ git log --diff-filter=DM -- experiments/results
(empty)

$ git log --all --diff-filter=DM -- experiments/results
(empty)
```

No tracked results file has ever been modified or deleted, on any ref.

### C.11 The numbers gate

```
======================================================================
check_paper_numbers.py -- the manuscript against its results
======================================================================
  PASS  per-cell-metrics.csv is keyed by regime
  PASS  appendfsync=always analysis is present
  PASS  G2 write-loss results is present
  PASS  paper_tables.py runs
  PASS  numbers.tex matches the CSVs
  PASS  table-ablation.tex matches the CSVs
  PASS  table-ambiguity-by-crashpoint.tex matches the CSVs
  PASS  table-deployment-choice.tex matches the CSVs
  PASS  table-latency.tex matches the CSVs
  PASS  table-outcomes.tex matches the CSVs
  PASS  no generated table draws from the banned pooled table
  PASS  generated tables declare their sources
  PASS  every generated number is used in the manuscript
  PASS  state-machine figure matches the transition table
  PASS  bibliography has entries
  PASS  no empty bibliography entries
  PASS  bibtex reported no parse errors
  PASS  no undefined references or citations
  NOTE  0 \todoitem marker(s): 

----------------------------------------------------------------------
18 passed, 0 failed
```

**The check count did not rise.** The prompt anticipated it might if the gate
counted macros; it does not — the gate has a fixed set of 18 `check()` call
sites and the macro census is folded into "every generated number is used".
18/18 before this session, 18/18 after, with one more macro under the same
check.

### C.12 The full suite, as CI runs it

First run was wrong and is recorded because it was wrong: I set only `REDIS_URL`
and got **31 skips**, because CI also sets `AEP_PHASE2_REDIS_INTEGRATION=1` and
`AEP_PHASE2_REDIS_CONTAINER`. With the complete CI environment:

```
$ docker compose -f compose.phase2.yml up -d --wait
 Container aep-phase2-redis72 Healthy
 Container aep-phase2-toxiproxy Healthy

$ uv run --frozen python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6381/15
  verified redis_version=7.2.5
  verified appendonly=yes
  verified appendfsync=everysec
  verified aof-use-rdb-preamble=yes
  verified aof_enabled=1
  verified waitaof=present
OK: live Redis matches phase2.conf semantics

$ REDIS_URL=redis://127.0.0.1:6381/15 \
  AEP_PHASE2_REDIS_INTEGRATION=1 \
  AEP_PHASE2_REDIS_CONTAINER=aep-phase2-redis72 \
  uv run --frozen pytest -q -ra --strict-markers --junitxml=junit.xml \
    --cov=aep_core --cov-report=term-missing --cov-report=xml --cov-fail-under=90

Coverage XML written to file coverage.xml
Required test coverage of 90% reached. Total coverage: 91.18%
1737 passed, 2 warnings in 140.80s (0:02:20)

$ uv run --frozen python scripts/check_pytest_gates.py \
    --junit junit.xml --output pytest-output.txt --minimum-tests 1700
OK: 1737 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
```

**1737 passed, zero skipped, zero xpassed**, above the 1700 floor, coverage
91.18%. The suite gained 3 tests this session (1734 → 1737).

The new tests, run alone:

```
$ uv run --frozen python -m pytest tests/test_paper_tables.py -q
.......................                                                  [100%]
23 passed in 0.99s
```

### C.13 Both PDFs rebuilt

Built in WSL Ubuntu-24.04 rather than a container — see §E.4 for why, and note
the pdfTeX version is the one that produced every committed PDF in this project
(`pdfTeX-1.40.25`).

```
############## PUBLIC BUILD ##############
=== bibtex parse errors (a blank bibliography compiles clean) ===
  none
=== undefined references and citations (warnings, not errors) ===
  none
=== \todoitem markers left in the sections ===
  none
=== output ===
Output written on main.pdf (18 pages
overfull boxes: 10

  ... 18 passed, 0 failed

build clean.
PUBLIC_EXIT=0

############## ANONYMOUS BUILD ##############
=== bibtex parse errors (a blank bibliography compiles clean) ===
  none
=== undefined references and citations (warnings, not errors) ===
  none
=== \todoitem markers left in the sections ===
  none
=== output ===
Output written on main-anon.pdf (18 pages
overfull boxes: 10

=== the numbers against the results ===
  SKIPPED for the anonymous build -- the gate reads main.log/main.bbl.

build clean (main-anon).
ANON_EXIT=0
```

**Page counts: 18 and 18.** Overfull boxes 10 and 10 — unchanged from the
audit's baseline, so this session's four extra caption lines and one reflowed
sentence cost no page and introduced no new overfull box.

### C.14 The identity scan on the rebuilt PDFs

T1 is blocked, so there is no new author string to scan for. What T1c(iii) asks
for independently of that — that the identifying URL counts are unchanged from
the audit's table — is verified here on the **rebuilt** PDFs, over three
surfaces: extracted text, URI link annotations, and the document information
dictionary. Flate streams are decompressed before scanning, because pdfTeX puts
annotation objects inside compressed object streams.

```
=== main.pdf ===
-- URI link annotations: 15 total --
   2x  https://docs.temporal.io/activity-definition
   2x  https://docs.temporal.io/encyclopedia/retry-policies
   4x  https://github.com/hafizmirhamza276-lab/Research-paper-AEP
   2x  https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
   1x  https://redis.io/docs/latest/commands/waitaof/
   2x  https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
   2x  https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/

-- document information dictionary --
   /Author    ''
   /Title     ''
   /Creator   'LaTeX with hyperref'
   /Producer  'pdfTeX-1.40.25'
   /Subject   ''
   /Keywords  ''

-- XMP metadata packet --
   none

   'hafizmirhamza276-lab'
       in URI annotations : 4
       in file+streams    : 4

=== main-anon.pdf ===
-- URI link annotations: 11 total --
   (the six reference URLs only; no github.com entry)

-- document information dictionary --
   /Author    ''
   /Title     ''
   /Creator   ''
   /Producer  ''
   /Subject   ''
   /Keywords  ''

-- XMP metadata packet --
   none

   'hafizmirhamza276-lab'
       in URI annotations : 0
       in file+streams    : 0
```

**15 / 4 public, 11 / 0 anonymous — identical to the audit's table.** `/Author`
is empty in both, and in the anonymous build every information field is empty.
The method was validated against the *committed* PDFs first and reproduced the
audit's figures exactly before being applied to the rebuilds.

### C.15 The rendered content, before and after

```
=== COMMITTED (pre-session) (103705 chars) ===
  1x  THE TRILEMMA, MEASURED
  0x  POOL OVER FIVE OF THOSE SIX
  0x  CANNOT OCCUR IN A SYSTEM THAT WRITES NO INTENT
  1x  TWO ORDERS OF MAGNITUDE
  0x  FACTOR OF ROUGHLY 70
  1x  ANONYMOUS AUTHOR

=== REBUILT  (this session) (103993 chars) ===
  1x  THE TRILEMMA, MEASURED
  1x  POOL OVER FIVE OF THOSE SIX
  1x  CANNOT OCCUR IN A SYSTEM THAT WRITES NO INTENT
  0x  TWO ORDERS OF MAGNITUDE
  1x  FACTOR OF ROUGHLY 70
  1x  ANONYMOUS AUTHOR
```

Both changes are in the PDF a reviewer will read, the old phrase is out of it,
and `ANONYMOUS AUTHOR` is still there — which is the correct state given T1 is
blocked, not an oversight. The anonymous PDF matches on every row.

Comparisons are case-folded because IEEEtran sets table captions in small caps;
a case-sensitive search finds none of them. §F.6 records that this nearly
produced a false negative in my own verification.

---

## D. EXPECTED RESULTS checklist

| # | Expected | Verdict | Evidence |
|---|---|---|---|
| 1 | Author block matches HUMAN INPUT verbatim; anon PDF contains it zero times | **❌ BLOCKED-INPUT** | All four fields are underscores. `main.tex` unmodified. T1a's own stop condition. §E.1 |
| 1b | *(partial)* identifying URL counts unchanged; `/Author` empty in anon | ✅ | 15/4 public, 11/0 anon, `/Author` empty in both, no XMP — §C.14 |
| 2 | `.gitattributes` has the `*.sh` rule; autocrlf=true scratch-clone proof; zero `.sh` blob changes | ✅ | Rule at `.gitattributes:34`. Before: `set: pipefail: invalid option name`, exit 2. After: reaches line 46. `--renormalize` stages nothing — §C.2–C.4 |
| 3 | `\BarrierToProtocolRatio` with source comment + passing test; `08-threats.tex` no longer says "two orders of magnitude" | ✅ | Macro + 3-line source comment §C.6; phrase absent repo-wide §C.7; tests §C.12 |
| 4 | Caption discloses 5-vs-6 with the reason; caption test passes; generator-produced | ✅ | §C.8; generator invoked with the Makefile's arguments; test asserts caption **and** census |
| 5 | `06-evaluation.tex` untouched | ✅ | `git diff` empty — §C.9 |
| 6 | Numbers gate passes; full suite passes with zero skips; both PDFs build clean | ✅ | 18/18 §C.11; 1737 passed / 0 skipped §C.12; both `build clean`, 18 pages §C.13 |
| 7 | Committed, pushed, Actions green; nothing uploaded | ✅ | Run [31469984260](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31469984260), `success`, 4/4, numbers gate green — §C.16 |
| 8 | Report ends with the specified single line | **⚠️ SUBSTITUTED** | The line asserts repository work is complete. T1 is not. §E.1, §H |

### C.16 Commit, push, CI

```
$ git log --oneline -3
f4de834 D6 and D11: the factor the prose estimated, and the asymmetry the caption hid
4b910d3 D12: shell scripts reach a POSIX shell as LF in every clone
399e502 Audit: record the two green runs, and the external actions taken

$ git push origin main
To https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
   399e502..f4de834  main -> main
PUSH_EXIT=0

$ git fetch origin && git rev-list --left-right --count origin/main...main
0	0
```

CI on head `f4de834`, read via unauthenticated `GET` to `api.github.com`:

```
head_sha   f4de834ba455064c7703b9b9314275f546b5ba0b
status     completed
conclusion success
url        https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31469984260

jobs: 4
  success    WAITAOF durability (compose, phase2.conf)
  success    Suite (py3.13, Redis from compose)
  success    Citation ranges (docs/22)
  success    Numbers gate (manuscript vs frozen CSVs)
```

**Run [31469984260](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31469984260)
— `success`, 4/4 jobs, and the "Numbers gate (manuscript vs frozen CSVs)" job is
green.** That job installs the CI TeX Live package set, builds the manuscript
through `scripts/build_paper.sh` from a clean Linux checkout, and then runs
`check_paper_numbers.py` — which is what settles §E.4: the PDFs this session
built under WSL are confirmed buildable under the package set CI actually uses,
from a checkout that took the new `.gitattributes` rule.

**One thing the run list does not show, stated so nobody looks for it later:**
there is **no separate CI run for `4b910d3`**. Both commits went up in one push,
and GitHub schedules the workflow on the pushed head only. The D12 commit is
covered transitively — `f4de834` contains it, and the numbers-gate job checks
out and builds from a tree that has the `*.sh` rule in force.

---

## E. Deviations

### E.1 T1 is BLOCKED-INPUT — the central deviation

The prompt's STEP 0 requires the human to fill the author block before pasting.
It arrived unfilled:

```
Author name(s):      ___________________________
Affiliation(s):      ___________________________
Email(s):            ___________________________
ORCID (optional):    ___________________________
```

T1a: *"Use it verbatim; if any field is blank or looks like a placeholder
(underscores), STOP and report BLOCKED-INPUT rather than guessing."* All four
are underscores, so all four trigger it.

**What I did not do:** I did not infer a name from the git author identity
(`Hamza Khan <63538732+hamza276@users.noreply.github.com>`), from the GitHub
account in the artifact URL, from `CITATION.cff`, or from the session
environment. Any of those would have produced a plausible author block, and a
plausible-but-unauthorised author block on a journal submission is worse than an
absent one. `paper/main.tex` is byte-identical to `399e502`.

**What T1 still needs, when the human supplies the input.** T1b is the
load-bearing half and it is not yet done: the identity must be gated by
`\ifanonymous`. The current structure gates only the artifact pointer —
`main.tex:83–96` — while the author block at `main.tex:104–107` is outside the
toggle and hard-codes `Anonymous Author(s)`. So a future session must extend the
toggle over `\author{}`, not merely substitute text into it. The `\thanks`
footnote on the same line already uses `\artifacturl`, so the pattern to follow
is three lines above.

**Consequence for the closing line.** The prompt specifies a final line reading
"Repository work is complete." With T1 outstanding — and T1 is a repository
change to a tracked file — that sentence would be false. Standing rules make
fabrication halt-level, so I did not write it verbatim. §H states the true
position and preserves the rest of the specified content.

### E.2 Two commits, not one

T2's required proof is a clone made with `core.autocrlf=true`, and a clone can
only observe committed state. So the `.gitattributes` rule was committed on its
own (`4b910d3`) and the proof taken against that commit; T3/T4 followed in a
second commit. No amend, no rebase, no force — the history is append-only.

### E.3 `.gitattributes` gained a comment block, not literally one line

The scope bound says "the one line in T2". The rule *is* one line
(`*.sh text eol=lf`). I also added an 11-line comment above it, because the file
is 20 lines of comment for its one existing rule and an uncommented rule would
be the anomaly. The comment is inert. If the human prefers the bare line, it
deletes cleanly.

### E.4 The PDFs were built in WSL, not in a container with the CI package set

Planned: `ubuntu:24.04` + the exact nine `texlive-*` packages CI installs, as the
audit did. The `apt-get` download stalled — 89 MB in thirteen minutes, and
falling to about 6 KB/s, while a fresh container measured 279 KB/s against the
same mirror. Rather than sit on it, I used the WSL `Ubuntu-24.04` distro, which
already had TeX Live 2023 with every package the manuscript needs
(`IEEEtran.cls`, `cleveref.sty`, `multirow.sty`, `tikz.sty`, `listings.sty` all
resolved via `kpsewhich`).

Why this is an acceptable substitute, stated precisely: the pdfTeX is
`3.141592653-2.6-1.40.25 (TeX Live 2023/Debian)`, which is the exact version in
the `/Producer` string of every PDF this project has committed, and the build
reproduced the audit's page count (18) and overfull-box count (10) on both
builds. Why it is still a substitute: it is not byte-for-byte the CI package
set, so a font or package difference would not necessarily surface here. **CI
settles this** — the `paper-numbers` job builds the manuscript from a clean
Linux checkout with the CI package set, and its result is recorded below.

### E.5 A third and fourth test beyond the two required

T3 asked for "a test asserting the arithmetic" and T4 for "a caption test". I
added a third — `test_a_ratio_is_rounded_to_significant_figures_without_an_exponent`
— because the new `tex_sigfigs` helper had a silent-wrong-answer failure mode,
and it immediately earned its place: **the first implementation was wrong.** It
clamped the rounding precision at zero decimals, so `tex_sigfigs(1966.7)`
returned `1\,967` — four significant figures wearing the label of two. The
emitted ratio was 70 either way, so nothing downstream would have caught it. It
is fixed and the comment in the code explains the trap.

### E.6 `import math` and one new helper function

The new macro needs significant-figure rounding, which needs `math.log10`. Both
the import and `tex_sigfigs` are additive; no existing computation, macro or
formatter changed. `tex_number` is untouched and still formats every millisecond
figure exactly as before — confirmed by four of six generated files being
byte-identical (§C.8).

### E.7 The working tree's `.venv` was rebuilt twice

`build_paper.sh` runs `uv run --frozen` and the WSL invocation rebuilt `.venv`
with Linux binaries, breaking the Windows interpreter. I removed it from the WSL
side and re-synced with the CI extras. `.venv` is gitignored; no tracked file
was affected, and the numbers gate was re-run afterwards to confirm the tree is
still green (§C.11).

---

## F. Hostile-reviewer weaknesses of *this session's* output

### F.1 The ratio's own interval is enormous, and the paper does not state it

This is the strongest objection to T3, and it is an objection to the change I
was asked to make. `\BarrierToProtocolRatio` is 70 as a point estimate. Its
denominator is a difference of two medians from three runs per arm, and the
repository's own cluster bootstrap puts that denominator at **[27.1, 1524.6] ms**
(§C.5). Propagating just that interval, the ratio ranges from about **1.3× to
about 73×**. The point estimate sits at the very top of its own range.

So the sentence now reads "roughly 70" where it used to read "two orders of
magnitude". Both are point claims about a quantity the data pins very loosely.
The new one is better — it is generated, it cannot drift, it is not an
overstatement by a factor of ~1.4, and "roughly" is doing honest work. But a
reviewer who recomputes it will find that the paper's own methodology section
(§8, twenty lines of it at `08-threats.tex:276–284`) reports intervals for the
*numerator* and never for this ratio. **The manuscript is now slightly more
precise-sounding about a quantity whose uncertainty it discloses less
completely than it discloses the barrier cost's.**

I did not fix this, because fixing it means adding an interval to the sentence
or emitting two more macros, and both exceed "the new ratio macro of T3 and no
other manuscript prose change". It is the human's call, and it is the one item
from this session I would most want them to look at. The cheapest honest repair
is one clause: "by a factor of roughly \BarrierToProtocolRatio{}, though the
three-run interval behind that figure is wide (§VIII-x)".

### F.2 The caption's "five" is prose, not a computed value

The generator writes the word `five` as a literal. If a future collection gave
B0–B2 a sixth crash point, the generator would keep emitting "five" and the
caption would become false. The new test is the only thing standing between that
and a shipped error — it asserts the census still shows `crash_points=5` for
B0 and `6` for AEP-full, so the *test* fails rather than the generator. That is
weaker than the project's usual discipline, where the number would be computed
and the sentence would quote a macro. I chose the literal because T4 asked for
one sentence in a caption and a computed variant means a new macro, a new gate
interaction, and a caption that reads worse.

### F.3 The macro has exactly one consumer, which couples prose to the generator

`\BarrierToProtocolRatio` is used once. The "every generated number is used"
gate therefore turns any future deletion of that sentence into a CI failure in a
file the deleter is not editing. That is the gate working as designed, but it is
a trap for whoever next edits §8, and nothing in the manuscript warns them.

### F.4 `tex_sigfigs` was wrong on its first write, and is still lightly exercised

§E.5 has the detail. The failure was silent — a wrong number, not an exception —
and it survived until a test I was not required to write. It now has one caller
and five asserted inputs. A helper with one caller and a demonstrated history of
being wrong is not yet trustworthy for a second caller.

### F.5 The D12 proof is a proxy for the evaluator's actual path

I proved the fix under `ubuntu:24.04` bash, which is the right shell but not the
full path an artifact evaluator takes (clone → WSL/Docker → **build the paper**).
The failure D12 names is bash's, not TeX's, and it happens at line 30 before any
TeX is reached, so the proxy is faithful to the defect. But the end-to-end claim
"a Windows evaluator can now clone and build" is supported by two separate runs
(the container reaching line 46, and the WSL build succeeding) rather than one
run of the whole path.

### F.6 My own verification nearly produced a false negative

Checking that the new caption rendered, I searched the extracted PDF text for
`pool over five of those six` and got **zero hits** — including for caption text
that predates this session. IEEEtran sets table captions in small caps, so the
extraction is uppercase and every case-sensitive search fails. I only caught it
because the pre-existing caption also failed, which made the result implausible.
A checker who tested only the new string would have concluded the caption was
missing and "fixed" a non-problem, or — worse, in the mirror-image case — a
checker looking for a *leaked* string case-sensitively would have concluded a
PDF was clean when it was not. §C.14's identity scan is case-sensitive on a
lowercase URL, which is safe here because URLs are not small-capped, but the
general lesson stands and is worth carrying into any future anonymity check.

### F.7 The session report cannot verify its own most important claim

T1's whole point is that no identity leaks into the anonymous build. With T1
blocked there is no author string to search for, so §C.14 proves only that the
*existing* leaks are still gone. When the human fills the block, **the anonymity
scan must be re-run against the new name, affiliation, email and ORCID** — all
four, on all three surfaces. Nothing in this session discharges that.

---

## G. Out-of-scope issues noticed but NOT touched

### G.1 The generator now contains a refusal and a permission for the same construction

`paper_tables.py` has, within forty lines of each other, a comment refusing to
emit a ratio of two median differences and a macro that emits one. The reasons
differ correctly — one denominator's interval spans zero, the other's does not —
and I wrote the new comment to say so explicitly and point at the old one. But a
future reader skimming for policy will find two answers to what looks like one
question. Not fixed: rewriting the older comment is a change to existing code
this session was not scoped to make.

### G.2 The audit's low-severity tail is untouched, as instructed

D1 (5B's "21 files" vs 22), D2 ("byte for byte" overstated in
`check_paper_numbers.py:5` and `Makefile:222`), D3 (`sha256sum -c` exits non-zero
on a fresh clone), D5 (no `SHA256SUMS` under `fsync-always/`), D7
(`verify_refs.py` hollow, two `QUERIES` faults) and D4 (the two analysis figures
are unreproducible until the raw archive is published) are all still open and
all still disclosed. D4 remains the only one with artifact-evaluation
consequences.

### G.3 `verify_refs.py` still returns 0 unconditionally

Mentioned separately from G.2 because it is the one low item that could mislead
a future session rather than a reviewer: it looks like a gate, it is wired into
nothing, and it always passes. If anyone adds a reference and "runs the checker",
they will get a green result that means nothing.

### G.4 Two clones of this repository exist on this host, and they have diverged

`D:\personal\AEP\audit-clone` (this session's tree, now ahead of origin) and
`D:\personal\AEP\Research-paper-AEP` (clean, but two commits behind at
`a03985c`, and therefore without the audit report or the F1/F2 fixes). The
second is the tree the project's own `.ai/track.md` has been recording against.
Nothing is wrong with either, but a future session that opens the wrong one will
silently work on stale sources. Reconciling them — a `git pull` in the older
tree, or deleting it — is a housekeeping decision for the human.

### G.5 The overfull boxes are unchanged at 10

5C §G.4's item, and still true: four of the six offending tables are
generator-produced. This session touched the generator, so fixing them was
nearer to hand than before — but the column widths are not the caption text, and
"no other change" meant no other change.

---

## H. Recommended next step

**Fill in the author block, and treat T1b as the real work.** Supply the four
fields, then have the toggle extended over `\author{}` — the block at
`main.tex:104–107` currently sits outside `\ifanonymous`, so substituting a name
into it would put that name in `main-anon.pdf`. After that, re-run the
three-surface identity scan against the actual name, affiliation, email and
ORCID, on both PDFs. §F.7.

Everything else this session was asked to close is closed and verified: the
`.sh` line-ending rule (D12) with a before-and-after proof under the hostile
configuration, the measured factor replacing "two orders of magnitude" (D6) with
a generated macro and a test, and the crash-point asymmetry disclosed in the
caption it belongs to (D11) with a test that fails if the data stops matching
the words. Gates: numbers 18/18, suite 1737 passed with zero skips, both PDFs
clean at 18 pages.

Before submitting, read §F.1. It is the one place where this session's own
change invites a question it does not answer.

---

Repository work is complete **except for the author block (T1), which is blocked
on human input and remains outstanding in `paper/main.tex`.** Everything else
that remains is on the human residual checklist: confirm TSE's review policy on
ScholarOne, arXiv upload, TSE submission, raw-archive publication (D4), and any
optional low-tail items (D1/D2/D3/D5/D7).

---

## CI record

| Commit | What | Run | Jobs | Result |
|---|---|---|---|---|
| `4b910d3` | T2 — D12, the `*.sh` line-ending rule | *(no separate run; pushed together with the head below)* | — | covered by `f4de834` |
| `f4de834` | T3 + T4 + both PDFs + this report | [31469984260](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31469984260) | 4/4 | `success` |

As in every previous session, this paragraph is appended in a follow-up commit,
so the run recorded above is green on the head containing everything except
these lines. That commit's own run is produced by the same workflow and is the
repository's current head.

**External actions taken by this session: `git fetch`, two local `git clone`s
into scratch directories (both deleted), `git push`, unauthenticated `GET`s to
`api.github.com` to read run status, and `apt-get` traffic from two throwaway
containers. Nothing was uploaded, submitted or published; no account, token,
release, release asset or draft was created anywhere; no tag was created or
moved. arXiv and TSE submission remain the human's.**

---
---

# Resume — T1 completed, and the §F.1 clause

The human supplied two of the four author fields and authorised one additional
sentence: the §F.1 qualifier on the D6 ratio. Same scope bounds, plus
`paper/main.tex` (author block) and that one clause.

## R.A What changed in the resume

| File | A/M | Why |
|---|---|---|
| `paper/main.tex` | M | T1 — the author block, gated by `\ifanonymous` |
| `scripts/paper_tables.py` | M | §F.1 — `\ProtocolMinusBarrierLow/High`, the denominator's bootstrap interval |
| `tests/test_paper_tables.py` | M | §F.1 — one added test; additions only |
| `paper/generated/numbers.tex` | M | generator output: +8 lines |
| `paper/sections/08-threats.tex` | M | §F.1 — the authorised clause |
| `paper/main.pdf`, `paper/main-anon.pdf` | M | rebuilds |
| `reports/phase-report-final-2026-08-11.md` | M | this section |

`paper/sections/06-evaluation.tex` remains untouched — `git diff` empty.

## R.B T1 — the author block, and why T1b was the real work

The audit's residual checklist called this "fill in the author block", which
undersells it. `\author{}` sat **outside** the `\ifanonymous` block, which
closes at `main.tex:96`. Substituting a name into it would have put that name
in `main-anon.pdf` — the exact failure the toggle exists to prevent,
reintroduced by the act of completing the checklist item.

The fix follows F2's own design rather than inventing a second one: the identity
lives in the **same block** as the artifact pointer, as two macros, so there is
one place to audit for a leak instead of two.

```latex
\ifanonymous
  \newcommand{\artifacturl}{available via the submission system}
  \newcommand{\artifactavail}{available via the submission system}
  \newcommand{\authorname}{Anonymous Author(s)}
  \newcommand{\authorcontact}{}
  \hypersetup{pdfauthor={},pdftitle={},...}
\else
  \newcommand{\artifacturl}{\url{https://github.com/...}}
  \newcommand{\artifactavail}{available at \url{https://github.com/...}}
  \newcommand{\authorname}{Hamza Khan}
  \newcommand{\authorcontact}{%
    \thanks{Correspondence: \texttt{hafizmirhamza276@gmail.com}.}}
\fi
...
\author{%
  \IEEEauthorblockN{\authorname}%
  \thanks{Manuscript prepared \today. Artifact: \artifacturl.}%
  \authorcontact%
}
```

**One deliberate choice worth stating.** The address is set in `\texttt` rather
than `\url`. A `\url` would have hyperref emit a link annotation carrying the
address, and annotations are the surface the Monday audit found four leaks on
that a text-only check had missed. Setting it as plain text means the anonymous
build has one fewer surface to clear, and the public build's annotation count is
unchanged at 15 — verified below, not assumed.

`/Author` was left empty in the public build too. Populating it is conventional
and was not asked for; an empty field cannot leak, and the audit recorded the
empty state as a property worth keeping.

## R.C The identity scan — all supplied strings, all three surfaces

The check §F.7 said this session could not make. Needles are the two supplied
fields plus every fragment they decompose into, because a check for the full
string alone would miss a hyphenated or line-broken rendering. Matching is
case-folded (§F.6's lesson) and covers rendered page text, URI link annotations,
and the document information dictionary, with Flate streams decompressed first.

**`main.pdf` (public):**

```
bytes 362455   pages 18   streams decoded 177

-- URI link annotations: 15 total --
   4x  https://github.com/hafizmirhamza276-lab/Research-paper-AEP
   (plus the 11 legitimate reference URLs)

-- document information dictionary --
   /Author    ''
   /Title     ''
   /Creator   'LaTeX with hyperref'
   /Producer  'pdfTeX-1.40.25'

-- identity needles --
   'Hamza Khan'                   page text 1    URI annots 0    raw+streams 0
   'hafizmirhamza276@gmail.com'   page text 1    URI annots 0    raw+streams 1
```

The name renders once, the address renders once, and **neither adds a link
annotation** — the count is 15, exactly what it was before this session.

**`main-anon.pdf` (anonymous):**

```
bytes 361628   pages 18   streams decoded 177

-- URI link annotations: 11 total --
   (the six reference URLs only; no github.com entry)

-- document information dictionary --
   /Author    ''      /Title     ''      /Creator   ''
   /Producer  ''      /Subject   ''      /Keywords  ''

-- XMP metadata --
   none

-- identity needles, all three surfaces --
   'Hamza Khan'                   page text 0    URI annots 0    raw+streams 0
   'hafizmirhamza276@gmail.com'   page text 0    URI annots 0    raw+streams 0
   'hafizmirhamza276'             page text 0    URI annots 0    raw+streams 0
   'Hamza'                        page text 0    URI annots 0    raw+streams 0
   'Khan'                         page text 0    URI annots 0    raw+streams 0
   'gmail'                        page text 0    URI annots 0    raw+streams 0
   'Correspondence'               page text 0    URI annots 0    raw+streams 0

TOTAL needle hits across all surfaces: 0
```

**Zero, on every needle and every surface.** Including `Correspondence`, the
footnote label itself — a reviewer cannot even tell a correspondence footnote
was removed.

What each build renders:

```
=== PUBLIC  main.pdf -- pages 18 ===
  0x  'Anonymous Author(s)'
  1x  'Hamza Khan'
  1x  'hafizmirhamza276@gmail.com'
  1x  'Correspondence:'
  0x  'available via the submission system'
  title area: '... Legacy APIs Hamza Khan Abstract--Autonomous software agents ...'

=== ANON    main-anon.pdf -- pages 18 ===
  1x  'Anonymous Author(s)'
  0x  'Hamza Khan'
  0x  'hafizmirhamza276@gmail.com'
  0x  'Correspondence:'
  2x  'available via the submission system'
  title area: '... Legacy APIs Anonymous Author(s) Abstract--Autonomous software agents ...'
```

## R.D §F.1 — the ratio, qualified

The authorisation was one clause naming the propagated uncertainty. Written to
the project's numbers discipline rather than around it: **both endpoints are
generated macros**, not typed, so the qualifier cannot drift from the bootstrap
the way the phrase it replaces drifted from the measurement.

```
% analysis/per-execution.csv | cluster bootstrap over runs, 10000 resamples, seed 20260806, appendfsync=everysec
% 2.5th percentile of (median B3 - median B0); point estimate 30.5 ms from 3 and 3 runs
\newcommand{\ProtocolMinusBarrierLow}{27.1}

% analysis/per-execution.csv | 97.5th percentile of the same bootstrap, appendfsync=everysec
% the denominator of \BarrierToProtocolRatio; its width is why that factor is quoted as an estimate
\newcommand{\ProtocolMinusBarrierHigh}{1\,524.6}
```

Emitted for `everysec` only. An `always` twin would have no sentence quoting it,
and the "every generated number is used" gate turns an unquoted macro into a
build failure — so the restriction is enforced, not merely intended.

The sentence, as rendered in the PDF:

> two fsync barriers, which under `appendfsync everysec` dominate the protocol's
> latency by a factor of roughly 70 (Table X) — **a ratio of medians, and one
> whose denominator is pinned only to [27.1, 1 524.6] ms at three runs per arm,
> so the factor is an estimate of an order of magnitude rather than of a
> figure.**

**I chose to name the denominator's interval rather than the resulting ratio
range**, which the authorisation permitted either way. The reason is worth
recording, because the other choice looks more informative and is worse: a ratio
range obtained by dividing the numerator's point estimate by the denominator's
interval endpoints is not a confidence interval for the ratio. It is a crude
bound that ignores the covariance between numerator and denominator — both are
functions of the same B3 medians. Quoting "1.3x to 73x" would have put a number
in the paper that looks like a bootstrap result and is not one. Deriving a real
interval for the ratio means bootstrapping the ratio statistic itself, which is
a new statistical method added to a frozen manuscript days before submission.
Naming the denominator's interval says the same thing to a reviewer — the factor
is loosely pinned, and here is why — using machinery the paper already validates
and CI already gates.

The new test asserts the interval structurally rather than numerically: that
both macros are emitted for `everysec`, that they bracket the point estimate,
that the interval is non-degenerate (a degenerate one would make the qualifier
false), and that no `always` twin exists. Pinning resampled percentiles to four
significant figures would have made it a test of the RNG.

## R.E Gates, resume

```
$ uv run --frozen python -m pytest tests/test_paper_tables.py -q
........................                                                 [100%]
24 passed in 1.02s

$ uv run --frozen python scripts/check_paper_numbers.py
  ... PASS every generated number is used in the manuscript ...
18 passed, 0 failed

$ uv run --frozen pytest -q -ra --strict-markers --junitxml=junit.xml \
    --cov=aep_core --cov-fail-under=90   (full CI environment)
Required test coverage of 90% reached. Total coverage: 91.18%
1738 passed, 3 warnings in 157.82s (0:02:37)

$ uv run --frozen python scripts/check_pytest_gates.py \
    --junit junit.xml --output pytest-output.txt --minimum-tests 1700
OK: 1738 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
```

Both builds:

```
PUBLIC:  Output written on main.pdf (18 pages       overfull boxes: 10
         18 passed, 0 failed          build clean.          PUBLIC_EXIT=0
ANON:    Output written on main-anon.pdf (18 pages  overfull boxes: 10
         build clean (main-anon).                           ANON_EXIT=0
```

**18 pages and 10 overfull boxes on both, unchanged for the fourth build in a
row.** The author block and the new clause cost no page and introduced no new
overfull box.

## R.F E.8 — the affiliation, absent and not invented

The resume message supplied:

```
Author name(s):      Hamza Khan
Email(s):            hafizmirhamza276@gmail.com
```

and omitted the `Affiliation(s)` and `ORCID` lines. ORCID is marked optional in
the prompt's own block, so a blank one is in specification and the author block
simply has none.

**Affiliation is not optional and is absent.** T1a's stop-on-blank rule exists
to stop me guessing, and I did not: the block renders a name and a
correspondence address and no institution. I specifically did not write
"Independent Researcher", which is the tempting move — it reads like a neutral
default and is in fact an assertion about the author's employment status that
nobody made.

What this costs, stated plainly so it is not discovered at submission:

- **TSE:** nothing structural. ScholarOne collects authors and affiliations in
  its own form, and the audit's residual checklist §4.4 item 4 already assigns
  the author block there. The PDF's block is not the record of authorship.
- **arXiv:** more. arXiv takes the author list from the submission form, but the
  PDF is what a reader sees, and an IEEE-formatted paper with a bare name and no
  affiliation line looks unfinished rather than deliberately unaffiliated.
- **The one-line fix:** add an `\IEEEauthorblockA{...}` after `\authorname` in
  the `\else` branch, or extend the `\authorcontact` `\thanks`. Both are inside
  the toggle already, so neither can leak into the anonymous build.

## R.G What the resume adds to §F — hostile reading of the resume itself

**F.8 The anonymous build is now protected by a convention, not by a check.**
The toggle works, and the scan proves it works *today*. But nothing in CI runs
that scan. If someone later adds an author line, a funding note or an
acknowledgements section outside the `\ifanonymous` block — exactly the mistake
this section had to fix — the anonymous build will leak and every gate will stay
green. The numbers gate does not build `main-anon.pdf` at all. **A CI job that
greps the anonymous PDF for a configured list of identity strings would close
this permanently**, and it is the single highest-value thing left in the
repository. It was not in scope this session.

**F.9 The scan's needle list is hand-written.** I searched for the two supplied
fields and five fragments. That is a judgement about what to look for, not a
proof of absence — a leak in a form I did not think to search for would not
appear. The `TOTAL needle hits: 0` line means "zero of the seven things I looked
for", and should be read that way.

**F.10 `\texttt` for the address is a trade, not a free win.** It removes the
annotation surface, and it also removes the clickable `mailto:` a reader might
expect in a published paper. For the anonymous submission that is strictly
right. For the arXiv version it is a small loss of convenience, chosen
deliberately.

**F.11 The §F.1 clause makes an already-long sentence longer.** It now carries a
factor, a bracketed interval, a run count and a hedge, in a subsection about when
*not* to use the protocol. It is honest and it is denser than the prose around
it. A copy-editor would probably split it in two; I did not, because the
authorisation was one clause and "no other prose changes".

## R.H Recommended next step, revised

Repository work is complete. In order of value:

1. **Decide whether the author block needs an affiliation** (§R.F). One line,
   inside the toggle, cannot leak.
2. **Consider the anonymity CI job** (§F.8). It is the only structural gap left,
   and it protects a property the submission depends on.
3. Then the human residual checklist: TSE review policy on ScholarOne, arXiv
   upload, TSE submission, raw-archive publication (D4), and the optional
   low-tail items (D1/D2/D3/D5/D7).

## R.I CI record, resume

| Commit | What | Run | Jobs | Result |
|---|---|---|---|---|
| `bf68440` | T1 author block + the §F.1 clause + both PDFs | [31486243170](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31486243170) | 4/4 | `success` |

```
head bf68440 -- jobs: 4
  success    Suite (py3.13, Redis from compose)
  success    WAITAOF durability (compose, phase2.conf)
  success    Citation ranges (docs/22)
  success    Numbers gate (manuscript vs frozen CSVs)
```

The numbers-gate job is the one that matters here: it builds the manuscript
through `scripts/build_paper.sh` with no arguments, on a clean Linux checkout,
with the CI TeX Live package set. Green means the author block compiles and the
two new interval macros are generated, used and consistent with the frozen CSVs
somewhere other than the machine that wrote them. **It does not build or check
`main-anon.pdf`** -- see §F.8, which is why that gap is worth closing.

**External actions, resume: `git push` and read-only `GET`s to `api.github.com`.
Nothing uploaded, submitted or published; no account, token, release, asset,
draft or tag created or moved. arXiv and TSE submission remain the human's.**
