# Phase Q + Phase 5C — the byte guarantee made portable, one word-number adjudicated, and the manuscript readied for an audit it has not yet had

**Date:** 2026-08-10
**Prompt:** combined Pre-5C micro-fixes (T1–T3) → Phase 5C submission-ready (T4–T9).
**Predecessor:** `reports/phase-report-5b-2026-08-10.md`
**Governing bounds document:** `WEEKEND_CODEX_PROMPTS.md` (Prompt 4), plus the
two SCOPE BOUNDS blocks in this session's prompt.

> **Read this first — six things, in the order they matter.**
>
> **1. The CRLF hazard was real, and it was worse than predicted.** The prompt
> anticipated that a Windows clone with `core.autocrlf=true` "may rewrite their
> line endings at CHECKOUT". Measured on a scratch clone: **5 of the 13** tracked
> gate inputs are corrupted, and one of them is `SHA256SUMS` itself — so the
> verification manifest's own filenames gain a trailing CR and `sha256sum -c`
> fails to open **all 17** entries. Not one file could be checked. After
> `.gitattributes`: **0 of 13** corrupted, **7 OK**, identical to the Linux
> baseline in 5B §C.4. §C.2.
>
> **2. The eight CSVs were never at risk, and the reason is luck rather than
> design.** Python's `csv` writer already emits CRLF, so git's LF→CRLF smudge
> finds no lone LF to convert. The files that broke are exactly the pure-LF ones
> — `coverage.json`, the three `g2-flakey-write-loss*.json`, and `SHA256SUMS`.
> The 5B incident was the *write* path of the same mechanism; this is the read
> path, and it selects the complementary set of files. §C.1.
>
> **3. Line 482 is derived arithmetic, and adjudicating it surfaced a
> substantive defect that is NOT mine to fix.** The three numerals are
> configuration-derived, so T2's branch (i) applies and the line is unchanged.
> But the clause "is precisely what we measure" asserts agreement between a
> prediction of **1.0 s** and the paper's own generated `\BarrierCost{}` of
> **1 966.7 ms** — a factor of ~1.97. That is a claim defect, not a numeral
> defect, and both Phase Q ("change nothing") and 5C's substance freeze route it
> to §G untouched. **§G.1 — this is the item I would most want the audit to look
> at.** §C.3.
>
> **4. `verify_refs.py` exits 0 having verified nothing.** On this host every one
> of its 18 lookups failed on TLS and the script still returned success. Its exit
> code is therefore *not* evidence for the checklist item that names it. Run
> properly, the bibliography is sound — **25 of 25 entries verified, 0
> unverified** — but one entry's URL had rotted to a 404 and was repointed to a
> verified live page. §C.6, §G.3.
>
> **5. The terminology audit found a collision, not just an inconsistency.** The
> manuscript called the Redis instance "the coordinator" 9 times without ever
> defining it, while §3 used the same word for a *transaction* coordinator it
> says does not exist. "Redis" wins 67-to-9 and the losing term is now at zero.
> §C.5.1.
>
> **6. Three numbers I wrote into `arxiv-metadata.md` were wrong, including one
> that mattered.** My "short" abstract was 2 034 characters against arXiv's 1 920
> limit while labelled as fitting. Measured, cut to 1 862, and recorded — but the
> lesson is that the repository's numbers discipline stops at `paper/*.tex`, and
> both files this session added sit outside it. §C.7, §F.2.

---

## A. Phase attempted and scope reference

| Task | Requirement | Status |
|---|---|---|
| **T1** | `.gitattributes` making the tracked-results byte guarantee portable; `autocrlf=true` scratch-clone proof | ✅ **Done.** §C.1–§C.2 |
| **T2** | Classify the borderline word-number at `06-evaluation.tex:482` | ✅ **Done**, verdict (i), with a §G finding. §C.3 |
| **T3** | Commit Phase Q, push, Actions green including the numbers gate | ✅ **Done.** §C.4 |
| **T4** | Full proofread — grammar, terminology, number formatting, cross-references, IEEEtran | ✅ **Done**, with 3 findings. §C.5 |
| **T5** | `verify_refs.py` full pass | ✅ **Done**, and the tool's verdict could not be trusted as shipped. §C.6 |
| **T6** | `paper/cover-letter-tse.md` | ✅ **Done.** §C.7 |
| **T7** | `paper/arxiv-metadata.md` | ✅ **Done**, with a corrected length. §C.7 |
| **T8** | Final PDF committed; `PAPER_ROADMAP.md` updated as scoped | ✅ **Done.** §C.8 |
| **T9** | §H completeness percentage + top-3 audit risks | ✅ **Done.** §H |

**Phase Q bounds:** `.gitattributes` (new, repo root, only the rules named in
T1); `paper/sections/06-evaluation.tex` *only if* T2's verdict required a change
at line 482 (**it did not — the file is untouched in Phase Q**); this report.

**Phase 5C bounds:** `paper/**`; `PAPER_ROADMAP.md` (completed-phase markers and
CURRENT PHASE only); this report.

---

## B. Files created/modified — the FULL list

### Phase Q (commit `ef1460f`, and this report's Phase-Q sections)

| File | A/M | In bounds? |
|---|---|---|
| `.gitattributes` | A | ✅ one rule, `experiments/results/** -text`, exactly as named by T1 |
| `reports/phase-report-5c-2026-08-10.md` | A | ✅ explicitly permitted |

**2 files.** `paper/sections/06-evaluation.tex` was **not** modified in Phase Q:
T2's verdict is branch (i), whose instruction is "change nothing". No file
outside these two changed — `git status --porcelain` was empty before and after
the `.gitattributes` commit apart from the file itself.

### Phase 5C

| File | A/M | In bounds? | What changed |
|---|---|---|---|
| `paper/sections/01-introduction.tex` | M | ✅ `paper/**` | 2 terminology edits (C3, C4) |
| `paper/sections/03-model.tex` | M | ✅ | 1 terminology edit (caption of `tab:crashpoints`) |
| `paper/sections/05-implementation.tex` | M | ✅ | CI job count 3 → 4 (§E.2) |
| `paper/sections/06-evaluation.tex` | M | ✅ | 4 terminology edits, 2 added cross-references |
| `paper/sections/07-related.tex` | M | ✅ | 1 added cross-reference to `tab:related` |
| `paper/sections/08-threats.tex` | M | ✅ | 2 terminology edits |
| `paper/sections/09-artifact.tex` | M | ✅ | CI job list (§E.2) |
| `paper/refs.bib` | M | ✅ | 1 dead URL repointed to a verified live one (§C.6) |
| `paper/cover-letter-tse.md` | A | ✅ named by T6 | new |
| `paper/arxiv-metadata.md` | A | ✅ named by T7 | new |
| `paper/main.pdf` | A | ✅ named by T8 | the built PDF, force-added past `.gitignore:102` (§E.3) |
| `PAPER_ROADMAP.md` | M | ✅ named by the bounds | phase markers + CURRENT PHASE **only**; 31 insertions, 1 deletion (§C.8) |
| `reports/phase-report-5c-2026-08-10.md` | M | ✅ | the 5C sections of this report |

**13 files.** Every one is inside `paper/**`, `PAPER_ROADMAP.md`, or this report.
**No file under `aep_core/**`, `experiments/**`, `scripts/**`, `tests/**`,
`.github/**` or `docs/**` was modified in either phase** — the diff below is the
whole session:

```
$ git diff --cached --stat            # at the point of the 5C commit
 PAPER_ROADMAP.md                     |  32 ++++++-
 paper/arxiv-metadata.md              | 168 +++++++++++++++++++++++++++++++++++
 paper/cover-letter-tse.md            | 146 ++++++++++++++++++++++++++++++
 paper/main.pdf                       | Bin 0 -> 361203 bytes
 paper/refs.bib                       |  12 ++-
 paper/sections/01-introduction.tex   |   6 +-
 paper/sections/03-model.tex          |   2 +-
 paper/sections/05-implementation.tex |   7 +-
 paper/sections/06-evaluation.tex     |  19 ++--
 paper/sections/07-related.tex        |   2 +-
 paper/sections/08-threats.tex        |   4 +-
 paper/sections/09-artifact.tex       |   5 +-
 12 files changed, 378 insertions(+), 25 deletions(-)
```

The prose sections total **25 changed lines across 7 files** — the size a
proofread should be.

### Not in git

Two scratch clones under the system temp directory (`aepq-*` before the fix,
`aepq2-*` after it), both deleted in §C.2.

---

## C. Raw command outputs

### C.0 Git prelude

```
$ git fetch origin
EXIT=0

$ git status -uno
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit (use -u to show untracked files)

$ git rev-list --left-right --count origin/main...main
0	0
EXIT=0
```

Clean tree, zero divergence, no merge required.

### C.1 T1 — what was actually at risk, and why

The repository had no `.gitattributes` (`ls: cannot access '.gitattributes': No
such file or directory`; `git ls-files | grep -i gitattributes` empty). This
clone's `core.autocrlf` was `false` — set by hand in 5B §E.2 and recorded as the
open issue 5B §G.1. That local setting was the *only* thing making the committed
bytes correct.

Line-ending composition of the 13 tracked gate inputs, read from the blobs
rather than the working tree (`CR == LF` ⇒ every LF is preceded by CR ⇒ pure
CRLF, zero lone LF; `CR == 0` ⇒ pure LF):

```
file                                                       CR      LF
fsync-always/…/latency-and-throughput.csv                   3       3     CRLF
fsync-always/…/per-execution.csv                           61      61     CRLF
g2-flakey-write-loss-rep2.json                              0     510     LF
g2-flakey-write-loss-rep3.json                              0     518     LF
g2-flakey-write-loss.json                                   0     510     LF
matrix/MANIFEST.csv                                       127     127     CRLF
matrix/SHA256SUMS                                           0      17     LF
matrix/analysis/comparisons-vs-aep-full.csv                37      37     CRLF
matrix/analysis/coverage.json                               0      44     LF
matrix/analysis/latency-and-throughput.csv                  8       8     CRLF
matrix/analysis/per-cell-metrics.csv                      757     757     CRLF
matrix/analysis/per-execution.csv                        3781    3781     CRLF
matrix/analysis/redis-kill-ablation.csv                     3       3     CRLF
```

This predicts the failure set exactly. `core.autocrlf=true` converts **lone LF**
to CRLF at checkout; the eight CSVs have none (Python's `csv` writer already
terminates with CRLF), so they pass through untouched. The five pure-LF files —
`coverage.json`, the three flakey JSONs, and `SHA256SUMS` — are rewritten.

The eight CSVs are therefore safe **by accident, not by design**, and the
accident is the same one that caused the 5B write-path incident from the other
side.

### C.2 T1 — the scratch-clone proof, before and after

**Before the fix** — clone of `main` at `31664ca` with `core.autocrlf=true`:

```
$ SCRATCH=$(mktemp -d -t aepq-XXXXXX)      # /tmp/aepq-TegvPs
$ git -c core.autocrlf=true clone --quiet /d/personal/AEP/Research-paper-AEP repo
clone exit=0
$ git config --get core.autocrlf
true

$ cd experiments/results/matrix && sha256sum -c SHA256SUMS
sha256sum: 'MANIFEST.md'$'\r': No such file or directory
MANIFEST.md: FAILED open or read
sha256sum: 'MANIFEST.csv'$'\r': No such file or directory
MANIFEST.csv: FAILED open or read
sha256sum: 'analysis/comparisons-vs-aep-full.csv'$'\r': No such file or directory
analysis/comparisons-vs-aep-full.csv: FAILED open or read
… 17 identical stanzas …
sha256sum: WARNING: 17 listed files could not be read
EXIT=1
```

**OK-count before the fix: 0 of 17.** `SHA256SUMS` is itself a pure-LF file, so
it was CRLF'd too and every filename in it acquired a trailing CR. The manifest
cannot even name its own files.

Separating the manifest's own corruption from content corruption, by stripping
the CRs from a copy of the manifest and re-checking:

```
$ tr -d '\r' < experiments/results/matrix/SHA256SUMS > /tmp/sums_clean.txt
$ sha256sum -c /tmp/sums_clean.txt
  MANIFEST.csv: OK
  analysis/comparisons-vs-aep-full.csv: OK
  analysis/coverage.json: FAILED            <-- content genuinely corrupted
  analysis/latency-and-throughput.csv: OK
  analysis/per-cell-metrics.csv: OK
  analysis/per-execution.csv: OK
  analysis/redis-kill-ablation.csv: OK
  … 10 untracked-by-design entries: No such file or directory …
  sha256sum: WARNING: 1 computed checksum did NOT match
EXIT=1
```

And the same question asked of all 13 tracked inputs, each checked-out file
against its own blob:

```
$ for f in $(git ls-files experiments/results); do
    b=$(git cat-file blob "HEAD:$f" | sha256sum | cut -d' ' -f1)
    w=$(sha256sum "$f" | cut -d' ' -f1)
    [ "$b" = "$w" ] && echo "  intact    $f" || echo "  CORRUPTED $f"
  done
  intact    experiments/results/fsync-always/analysis/latency-and-throughput.csv
  intact    experiments/results/fsync-always/analysis/per-execution.csv
  CORRUPTED experiments/results/g2-flakey-write-loss-rep2.json
  CORRUPTED experiments/results/g2-flakey-write-loss-rep3.json
  CORRUPTED experiments/results/g2-flakey-write-loss.json
  intact    experiments/results/matrix/MANIFEST.csv
  CORRUPTED experiments/results/matrix/SHA256SUMS
  intact    experiments/results/matrix/analysis/comparisons-vs-aep-full.csv
  CORRUPTED experiments/results/matrix/analysis/coverage.json
  intact    experiments/results/matrix/analysis/latency-and-throughput.csv
  intact    experiments/results/matrix/analysis/per-cell-metrics.csv
  intact    experiments/results/matrix/analysis/per-execution.csv
  intact    experiments/results/matrix/analysis/redis-kill-ablation.csv
  ---
  corrupted at checkout: 5 of 13
```

**The fix.** `.gitattributes` at the repository root, one rule:

```
experiments/results/** -text
```

The rest of the file is a comment recording why, including the measured 5-of-13
figure, so the next reader does not have to rediscover it. The rule binds and
dirties nothing:

```
$ git status --porcelain
?? .gitattributes                       # only the new file itself

$ git check-attr text -- experiments/results/matrix/analysis/coverage.json \
                         experiments/results/matrix/SHA256SUMS \
                         experiments/results/matrix/analysis/per-cell-metrics.csv \
                         experiments/results/g2-flakey-write-loss.json
experiments/results/matrix/analysis/coverage.json: text: unset
experiments/results/matrix/SHA256SUMS: text: unset
experiments/results/matrix/analysis/per-cell-metrics.csv: text: unset
experiments/results/g2-flakey-write-loss.json: text: unset
```

`text: unset` is `-text`: no conversion on either path. No tracked file changed
content — the commit adds one file and modifies none.

**After the fix** — a second clone, same `core.autocrlf=true`, of the commit
carrying `.gitattributes`:

```
$ SCRATCH2=$(mktemp -d -t aepq2-XXXXXX)    # /tmp/aepq2-sQtb62
$ git -c core.autocrlf=true clone --quiet /d/personal/AEP/Research-paper-AEP repo
$ git config --get core.autocrlf
true
$ git ls-files .gitattributes
.gitattributes

$ cd experiments/results/matrix && sha256sum -c SHA256SUMS
MANIFEST.csv: OK
analysis/comparisons-vs-aep-full.csv: OK
analysis/coverage.json: OK
analysis/latency-and-throughput.csv: OK
analysis/per-cell-metrics.csv: OK
analysis/per-execution.csv: OK
analysis/redis-kill-ablation.csv: OK
sha256sum: MANIFEST.md: No such file or directory
… 10 untracked-by-design entries …
sha256sum: WARNING: 10 listed files could not be read
EXIT=1

$ sha256sum -c SHA256SUMS 2>/dev/null | grep -c ': OK$'
7
```

**OK-count after the fix: 7** — every tracked file that the manifest lists, with
**zero** content mismatches. This is bit-for-bit the Linux result recorded in 5B
§C.4, which is the point: the guarantee is now the same on both platforms.

The `WARNING: 10 listed files could not be read` and the resulting `EXIT=1` are
**not** a Phase-Q regression. They are the untracked-by-design analysis products
of 5B §C.2, and 5B §F.6 already records this as a known cost of T1(b)'s "EXACTLY
those files" instruction. The exit code is identical before and after on Linux.

All 13 tracked inputs, and the clone's own working tree:

```
$ … same blob-vs-worktree loop as above …
  intact    (all 13 lines)
  ---
  corrupted at checkout: 0 of 13

$ git status --porcelain
                                        # empty: no phantom CRLF modifications
```

Both scratch clones deleted:

```
$ rm -rf /tmp/aepq-TegvPs /tmp/aepq2-sQtb62
$ ls -d /tmp/aepq-TegvPs /tmp/aepq2-sQtb62
ls: cannot access '/tmp/aepq-TegvPs': No such file or directory
ls: cannot access '/tmp/aepq2-sQtb62': No such file or directory

$ git status --porcelain                # in the real repo
                                        # clean
```

### C.3 T2 — the verdict on `06-evaluation.tex:482`

**The sentence, with its antecedent** (`06-evaluation.tex:477-485`):

```
477  … The \BarrierCost{}\,ms buys the prevention
478  guarantee of \cref{sec:eval-prevention} and nothing else.
479
480  That figure is also a property of a \emph{configuration}, not of AEP. Under
481  \texttt{appendfsync everysec} a write must wait for the next scheduled fsync,
482  and those are one second apart; a mean wait of half a second per barrier, twice,
483  is precisely what we measure. …
```

**Verdict: (i) — derived arithmetic from a documented configuration constant.
The line is unchanged.**

The clause carries three quantities, and none is an observation:

| quantity | what it is | why it is not a measurement |
|---|---|---|
| "one second apart" | the `appendfsync everysec` fsync period | A configured constant of the server, set at `redis/phase2.conf:12` (`appendfsync everysec`) and read back from the live instance at run time (`06-evaluation.tex:427`, "the server's `appendfsync` was read back as `everysec`"). Its digit form is already classified **CONFIG** in 5B §C.6 — "the 1 000 ms `appendfsync everysec` period (a property of Redis, not of a run)". No run produced it; changing `phase2.conf` changes it. |
| "half a second" | period ÷ 2 | Textbook expected-value arithmetic on the constant above: an arrival uniformly distributed within a period of length *T* waits E = *T*/2 for the next tick. With *T* = 1 s that is 0.5 s. Derived on the page from a documented constant; no CSV column holds it. |
| "twice" | the barrier count per step | A structural count of the protocol, not an observation of a run. It is the same structural fact the generator itself relies on at `paper/generated/numbers.tex:96` — "half of `\BarrierCost` — the protocol runs exactly two barriers per step" — to derive `\BarrierCostEach`. |

Because branch (i) holds, branch (ii) does not apply: no generator macro is owed
for these three, and `paper_tables.py` needs no modification. T2's instruction
for branch (i) is "change nothing", and nothing was changed.

**COUNT-CONSTANT justification line, as T2 requires** — for the report's
COUNT-CONSTANT list, extending 5B §C.6's three entries:

> **`06-evaluation.tex:482`** — "one second apart; a mean wait of half a second
> per barrier, twice". The `everysec` fsync period is a configured constant
> (`redis/phase2.conf:12`), the half-second is that constant divided by two by
> the uniform-arrival expectation stated in the same sentence, and "twice" is the
> protocol's fixed barrier count per step (`numbers.tex:96`). All three describe
> the *configuration and shape* of the experiment, not its outcome; a reader can
> change each by editing a config file or the protocol, and none can drift while
> the frozen results stay fixed. Classified with the 17 CONFIG numerals of 5B
> §C.6 rather than with its 3 plan-size COUNT-CONSTANTs, which is the closer fit;
> recorded here under the heading T2 named.

**A note on the taxonomy, so the audit is not misled.** T2's branch (i) names
the "COUNT-CONSTANT list", but 5B §C.6 built two distinct categories — CONFIG
(17: "values the experiment or the system was configured *with*") and
COUNT-CONSTANT (3: "the size or cost of the experiment *plan*"). These three
numerals are CONFIG by that taxonomy, not COUNT-CONSTANT. I have filed the
justification under the heading T2 asked for and stated the discrepancy rather
than silently reclassifying either the numerals or the category.

**What adjudicating the line exposed, which is not a T2 outcome.** The clause
does not stop at deriving 0.5 s; it says that value "**is precisely what we
measure**". That is an assertion of numerical agreement between the derivation
and the paper's measured barrier cost, and the two do not agree:

```
predicted by the sentence   0.5 s per barrier x 2 barriers   = 1.0 s
measured, generated         \BarrierCostEach{} = 983.3 ms
                            \BarrierCost{}     = 1 966.7 ms   (= 4004.9 - 2038.2)
                                                                paper/generated/numbers.tex:87-97
ratio                       1 966.7 / 1 000                  = 1.97
```

The measured per-barrier cost, 983.3 ms, is approximately **one full** `everysec`
period, not half of one. The sentence's own arithmetic under-predicts the
sentence's own measurement by a factor of ~2, and the word "precisely" asserts
the opposite.

This is a defect in a **claim**, not in a numeral's provenance, so it is out of
T2's scope in both directions — branch (i) says change nothing, and 5C's rules
say a substantive problem found while proofreading "goes in §G for the audit,
untouched". It is **§G.1**. Two things make it worth the auditor's attention:
the paper states the correct *bound* twenty lines later at `:501` ("An
acknowledgement must wait for the next scheduled fsync, up to a second"), so the
manuscript contains both a right and a wrong statement of the same mechanism;
and this is a survivor of 5B's two number sweeps, which looked for numerals
whose *provenance* was wrong rather than for prose whose *arithmetic* was.

The claim appears exactly once — `grep -rnE "half a second|one second|a second apart"`
over `paper/main.tex` and `paper/sections/*.tex` returns line 482 and nothing
else.

### C.4 T3 — Phase Q committed, pushed, Actions green

Two commits, pushed before any 5C edit was made:

```
$ git log --oneline -3
30f68e9 Phase Q T2: adjudicate the line-482 word-number, and start the 5C report
ef1460f Phase Q T1: make the frozen-results byte guarantee a property of the repo
c262f0f Phase 5B: record the tag, the final push and the two green runs

$ git push origin main
To https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
   c262f0f..30f68e9  main -> main
push exit=0
```

GitHub Actions on `30f68e9` — **all four jobs green, the numbers gate
included**:

```
$ curl -s .../actions/runs/31379777292        # status, conclusion
completed success

$ curl -s .../actions/runs/31379777292/jobs
WAITAOF durability (compose, phase2.conf)               completed    success
Numbers gate (manuscript vs frozen CSVs)                completed    success
Suite (py3.13, Redis from compose)                      completed    success
Citation ranges (docs/22)                               completed    success
```

**Run URL:** https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31379777292

Phase Q was green **before** the first 5C edit. From that point the Phase-Q
files were treated as read-only: `.gitattributes` is untouched by the 5C
commit, and `06-evaluation.tex:482` — the line Phase Q adjudicated — is not
among the lines 5C changed.

### C.5 T4 — the proofread

#### C.5.1 Terminology: one name per concept

Three concept families were audited by counting every variant across
`paper/main.tex` and `paper/sections/*.tex`, then reading each occurrence in
context. The audit found two genuine violations and one false alarm.

**Concept 1 — declared vs known ambiguity. Winner: "declared ambiguity".**

| term | before | after |
|---|---:|---:|
| `declared ambiguity` / `declared-ambiguity` | 24 | **25** |
| `known ambiguity` / `known-ambiguity` | **1** | **0** |

The single loser was `03-model.tex:119`, in the caption of
`tab:crashpoints`: *"why the known-ambiguity rate in \cref{sec:eval-rq1} varies
so sharply"*. It is a cross-reference into a section that never uses that name —
`06-evaluation.tex:115` and the generated caption of
`table-ambiguity-by-crashpoint.tex` both say *declared-ambiguity rate*. Changed
to match its own target.

*(The open and hyphenated forms are not two names: `declared ambiguity` is the
noun, `declared-ambiguity rate` the attributive. That is English, not
inconsistency, and both were left alone.)*

**Concept 2 — dispatch authority vs dispatch authorization. No change: these
are two concepts, not two names.**

```
$ grep -rn -iE "dispatch[ -]author[a-z]*" paper/main.tex paper/sections
01-introduction.tex:76:  of dispatch authority rather than a matter of call ordering: the fsync
05-implementation.tex:13: dispatch-authorization writer. Three further scripts implement the lock's
06-evaluation.tex:181:    the dispatch authorization, and the runner then performs preflight, mints the
06-evaluation.tex:233:    durability a checked precondition of dispatch authority (\cref{sec:p2}). B3 is
```

**Authority** is the *property* — both uses are "a checked precondition **of**
dispatch authority". **Authorization** is the *durable record that confers it* —
`01-introduction.tex:78` spells the relation out in the same sentence ("the
token is consumed to write a Redis-visible authorization"). The distinction
matches `docs/22-formal-model.md` (which uses both forms for the same two
referents) and the implementation, where the key is literally
`dispatch_authorization_key` (`aep_core/core/intent_workflow.py`). Merging them
would destroy a distinction the code makes. **Recorded as a deliberate
non-change so the audit can disagree with it explicitly rather than assume it
was missed.**

**Concept 3 — coordinator loss. Winner: "Redis". This was the real one.**

The manuscript used **"the coordinator"** in 9 places as a name for the Redis
instance, while never defining it — and §3 uses the same word for a *different*
concept:

```
03-model.tex:153:  Redis and a legacy provider share no transaction coordinator.
```

So a reader met "Redis and a legacy provider share no transaction coordinator"
in §3 and then, in §6, "the fault that exercises it is loss of the coordinator
itself" — which on the §3 reading describes losing a thing the paper had just
said does not exist. All 9 uses were confirmed to mean the Redis instance (at
`06-evaluation.tex:301` the very next sentence is "We hard-kill Redis at
\texttt{after\_intent\_before\_barrier}"; at `:565` the clause reads "a Redis on
the same host as the workers"), and `Redis` was already the established name at
**67 occurrences against 9**.

Replaced at `01-introduction.tex:83,101`; `06-evaluation.tex:301,370,559,565,569`;
`08-threats.tex:212,223`. Final state:

```
$ grep -rn -i "coordinator" paper/main.tex paper/sections
paper/sections/03-model.tex:153:  & Redis and a legacy provider share no transaction coordinator. The

count of lines mentioning coordinator: 1
of which are "transaction coordinator" (a different concept, kept): 1
```

**Zero occurrences of the losing term.** The one survivor is the 2PC sense,
disambiguated by its own modifier, and it is correct.

**Concept 4 — crash-point names. No change needed; already consistent.** All six
appear only under their canonical `snake_case` identifier inside `\texttt{}`,
with no competing prose paraphrase:

```
before\_intent\_write                      3
after\_intent\_before\_barrier             3
after\_barrier\_before\_dispatch           4
mid\_dispatch                              3
after\_response\_before\_resolution        3
after\_resolution\_before\_barrier         1
```

#### C.5.2 Cross-reference integrity, both directions

Checked mechanically over `main.tex`, `sections/*.tex`, `generated/*.tex` and
`figures/state-machine.tex`: 38 labels, 29 referenced keys.

**Before:** zero duplicate labels, zero dangling references — and **three floats
that the text never referred to**, which is the reverse direction and the one a
`\ref`-checker does not catch:

```
=== orphan labels -- defined but never referenced ===
  ORPHAN fig:bycrashpoint  ['paper/sections/06-evaluation.tex:209']
  ORPHAN fig:trade         ['paper/sections/06-evaluation.tex:150']
  ORPHAN tab:related       ['paper/sections/07-related.tex:96']
  ORPHAN sec:artifact, sec:eval-provable, sec:eval-rq2, sec:eval-setup,
         sec:introduction, sec:nonclaims        (section labels)
```

IEEE style requires every figure and table to be cited in the text. Three
references were added at content-matched anchors, not at arbitrary ones:

* `fig:trade` — at `06-evaluation.tex:67`, beside `\Cref{tab:outcomes} is the
  anchor result`, since the figure is those same executions pooled per system.
* `fig:bycrashpoint` — at the end of the "baselines duplicate in most crashed
  executions" paragraph, which is exactly what the figure decomposes by crash
  point.
* `tab:related` — at the end of "AEP declines to decide and says so", the
  sentence the table tabulates.

**After:** `=== float environments without a label === none`, and zero orphan
*floats*. The six remaining orphans are all `\section`/`\subsection` labels,
which is normal and was left alone.

#### C.5.3 Number formatting, in the generator's conventions

No violation found, and therefore **no `paper_tables.py` change was needed** —
T4's §G trigger did not fire on formatting.

| convention | conforming | violations |
|---|---:|---:|
| unit attachment `\,ms` | 26 | **0** (`[0-9] ms` with a plain space) |
| thousands separator `\,` | all | **0** bare 4-digit numerals |
| percent sign attached (`N\%`) | 3 | **0** detached |
| CI notation `[low, high]` | 4 | **0** other forms |

This is a consequence of Phase P rather than of this proofread: every DATA
numeral is a generated macro, so its formatting is the generator's by
construction. The four checks above test the hand-written CONFIG and METHOD
numerals that sit beside them.

#### C.5.4 IEEEtran compliance and page budget

`\documentclass[journal,10pt]{IEEEtran}`, `\IEEEtitleabstractindextext` wrapping
abstract and `IEEEkeywords`, `\IEEEdisplaynontitleabstractindextext`,
`\IEEEpeerreviewmaketitle`, `\markboth`, `\bibliographystyle{IEEEtran}` — the
journal-mode pattern is correct and complete. **18 pages**, inside the 14–18
the roadmap targets, with zero undefined references and zero `\todoitem`
markers (§C.8).

**Ten overfull boxes, now attributed.** 5B §G.6 recorded the count and that
"nobody has looked at which". They are all **tables**, never prose:

```
sections/02-motivating.tex          82.8pt   lines 94--108   (tab:trilemma)
sections/03-model.tex               34.9pt   line 128        (tab:crashpoints)
sections/03-model.tex               45.7pt   line 129        (tab:crashpoints)
sections/03-model.tex               61.9pt   line 131        (tab:crashpoints)
sections/03-model.tex               56.5pt   line 132        (tab:crashpoints)
sections/07-related.tex             57.0pt   lines 98--123   (tab:related)
generated/table-ambiguity-by-crashpoint.tex  22.8pt
generated/table-ambiguity-by-crashpoint.tex   9.5pt
generated/table-latency.tex                  13.1pt
generated/table-deployment-choice.tex        70.4pt
```

**Four of the ten are in `generated/*.tex`**, so fixing them means editing
`paper_tables.py` — which T4 names explicitly as a §G item rather than an edit.
The other six are hand-written table bodies whose column widths were chosen
deliberately. Re-typesetting six tables late, without a human seeing the
rendered result, and leaving the other four overfull anyway, is not a
proofreading change; **all ten go to §G.4 together** so the fix can be made
coherently. The count did not change during this session — 10 before my edits
and 10 after.

### C.6 T5 — reference verification, and why the tool's own verdict was not usable

**The script exits 0 when it has verified nothing.** Run first on Windows, every
single DBLP lookup failed and the exit code was still 0:

```
$ uv run --frozen python scripts/verify_refs.py
!! LOOKUP FAILED  Leases Efficient Fault-Tolerant Mechanism Distributed File Cache Consistency
   <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
    unable to get local issuer certificate (_ssl.c:1020)>
!! LOOKUP FAILED  Sagas Garcia-Molina Salem
   ... 18 of 18 identical ...
EXIT=0
```

Reporting that as "verify_refs.py passes" would have been literally true and
completely false. The environment lacks a CA bundle for Python's SSL context;
the failure is not the bibliography's. **This is §G.3.**

Re-run under WSL, which has working TLS (`DBLP reachable, HTTP 200`):

```
$ python3 scripts/verify_refs.py
### Leases Efficient Fault-Tolerant Mechanism ...   (1 hit(s))
  title:   Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency.
  authors: Cary G. Gray, David R. Cheriton
  venue:   SOSP year=1989 pp=202-210
  doi:     10.1145/74850.74870
... 11 queries resolved ...
!! LOOKUP FAILED  Durable functions semantics for stateful serverless
   HTTP Error 500: Internal Server Error
... 7 x HTTP 500 (DBLP rate-limiting the burst) ...
### In Search of an Understandable Consensus Algorithm Raft   (0 hit(s))
EXIT=0
```

Still not a clean verdict: 7 rate-limited, 1 zero-hit. So each entry was
verified directly rather than trusted to the sweep.

**All 11 DOIs in `refs.bib` resolved through doi.org, HTTP 200, every one:**

```
  HTTP 200  10.1145/74850.74870        Leases: an efficient fault-tolerant mechanism ... (pp. 202-210)
  HTTP 200  10.1145/38713.38742        Sagas (Garcia-Molina, Salem; pp. 249-259)
  HTTP 200  10.1145/128765.128770      ARIES: a transaction recovery method ...
  HTTP 200  10.1145/319566.319567      On optimistic methods for concurrency control
  HTTP 200  10.1145/3149.214121        Impossibility of distributed consensus with one faulty process
  HTTP 200  10.1145/226643.226647      Unreliable failure detectors for reliable distributed systems
  HTTP 200  10.1145/2160718.2160734    Idempotence is not a medical condition
  HTTP 200  10.1145/3485510            Durable functions: semantics for stateful serverless
  HTTP 200  10.1145/3477132.3483541    Boki: Stateful Serverless Computing with Shared Logs (pp. 691-707)
  HTTP 200  10.48550/arXiv.2403.16971  AIOS: LLM Agent Operating System
  HTTP 200  10.48550/arXiv.2603.20625  ACRFence: Preventing Semantic Rollback Attacks in Agent Checkpoint-Restore
```

The three whose first `title` field was a container title were re-fetched in
full and each carries the paper title, authors and pages that `refs.bib` claims.

**The four entries the sweep had not confirmed were queried individually, with
spacing, and all four match `refs.bib` exactly:**

```
In Search of an Understandable Consensus Algorithm   (1 hit)
  Diego Ongaro, John K. Ousterhout -- USENIX ATC 2014, pp. 305-319      = ongaro2014raft
ReAct: Synergizing Reasoning and Acting in Language Models   (2 hits)
  Yao, Zhao, Yu, Du, Shafran, Narasimhan, Cao -- ICLR 2023             = yao2023react
Toolformer: Language Models Can Teach Themselves to Use Tools   (2 hits)
  Schick, Dwivedi-Yu, Dessi, Raileanu, Lomeli, Hambro, ... -- NeurIPS 2023 = schick2023toolformer
Unreliable Failure Detectors for Reliable Distributed Systems   (1 hit)
  Chandra, Toueg -- J. ACM 43(2):225-267, 1996                         = chandra1996failuredetectors
```

The earlier zero-hit on Raft was an artifact of the stored query string, which
appends "Raft" — a word not in the paper's title.

**One entry failed, and it is a fix rather than a finding to defer.** The seven
URL-only sources were fetched live:

```
  HTTP 404    186619 bytes  https://redis.io/docs/latest/develop/use-cases/patterns/distributed-locks/
  HTTP 200     42382 bytes  https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
  HTTP 200    213367 bytes  https://redis.io/docs/latest/commands/waitaof/
  HTTP 200    136066 bytes  https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
  HTTP 200     85729 bytes  https://docs.temporal.io/encyclopedia/retry-policies
  HTTP 200     71893 bytes  https://docs.temporal.io/encyclopedia/detecting-activity-failures
  HTTP 200     93707 bytes  https://docs.temporal.io/activity-definition
```

`redis-locks` had rotted: Redis moved the page from `use-cases` to `clients`
with no redirect. The replacement was verified before it was written in, which
is what T5's rule requires:

```
  HTTP 200   Redlock/lock matches=45  https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
  HTTP 404   matches=0                https://redis.io/docs/latest/develop/use-cases/patterns/distributed-locks/
```

`refs.bib` now points at the 200 URL, with the access date moved to 2026-08-10
and a comment recording the rot. No entry was removed, and none is kept on
faith.

**Final bibliography state — 25 entries, 25 verified, 0 unverified:**

| class | n | how |
|---|---:|---|
| DOI-carrying | 11 | doi.org HTTP 200, record matched against the entry |
| No DOI, venue-verified | 7 | DBLP record matched (authors, venue, year, pages) |
| URL-only | 7 | live fetch, HTTP 200 (one repointed, §above) |
| **total** | **25** | **0 unverified** |

### C.7 T6, T7 — cover letter and arXiv metadata

`paper/cover-letter-tse.md`: venue fit (including why TPDS is the weaker fit),
the four contributions, an explicit non-claims paragraph, two volunteered
disclosures (the ablation is internal by construction; the barrier's durability
benefit cannot be exercised by any process-level fault), a no-prior-publication
statement that names the **planned** arXiv preprint, and artifact availability
pointing at `ARTIFACT.md` and tag `v1.0.0-rc1`.

`paper/arxiv-metadata.md`: final title, categories **cs.SE primary, cs.DC
secondary**, comments field, licence, and the abstract in plain text.

**Three numbers in it were wrong when first written, and were measured rather
than left as estimates.** I had written "~2 780 characters", "~1 870
characters", and "2 figures, 9 tables" from inspection. Measured:

```
full abstract   3105 chars   (I had written ~2 780)
short abstract  2034 chars   (I had written ~1 870 -- and arXiv's limit is 1 920,
                              so the "short" form did not actually fit)
tables 12, figures 3         (I had written 9 tables, 2 figures)
```

The short form was cut and re-measured to **1 862 characters**, 58 under the
limit, and the counts corrected to 3 figures / 12 tables. This is the same class
of defect the paper's own numbers gate exists to prevent, committed by me in a
file the gate does not cover — noted in §F.2.

### C.8 T8 — the final build, the PDF, and the roadmap

```
$ bash scripts/build_paper.sh                     # in WSL; no TeX Live on the Windows side
=== pdflatex / bibtex / pdflatex x2 ===
=== bibtex parse errors (a blank bibliography compiles clean) ===
  none
=== undefined references and citations (warnings, not errors) ===
  none
=== \todoitem markers left in the sections ===
  none
=== output ===
Output written on main.pdf (18 pages
overfull boxes: 10
=== the numbers against the results ===
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
build clean.
BUILD_EXIT=0
```

**18 pages, zero undefined references, zero `\todo`, and the numbers gate 18/18
after every edit this session** — which is the evidence the checklist asks for
that no number drifted during proofreading.

The PDF is gitignored (`.gitignore:102`, `paper/*.pdf`), so it was force-added.
`.gitignore` itself was **not** modified — it is out of 5C's bounds:

```
$ git add -f paper/main.pdf
$ git cat-file blob ":paper/main.pdf" | sha256sum
6f578c16474a0ea813e4102dbff749e29e0a935373a058a3b0b7615981184315  -
$ sha256sum paper/main.pdf
6f578c16474a0ea813e4102dbff749e29e0a935373a058a3b0b7615981184315  paper/main.pdf
$ git diff --cached --stat -- paper/main.pdf
 paper/main.pdf | Bin 0 -> 361203 bytes
```

Staged blob identical to disk, and git stores it as binary — no line-ending
path exists for it.

**`PAPER_ROADMAP.md`, exactly as scoped: 31 insertions, 1 deletion.** The
insertion is a `CURRENT PHASE: Monday audit` section plus a phase-status table
giving the report path that closed each phase; the deletion is the single stale
heading `## 3. CURRENT PHASE: Phase 2B ...`, which became
`## 3. Phase 2B — COMPLETE. ...`. Nothing else in the file changed — the full
diff is in §B's stat line and contains no other hunk.

### C.9 T8 — the final push and Actions on head

*(appended after the rest of the report, as in previous sessions)*

The 5C commit, and the push:

```
$ git log --oneline -3
0e80297 Phase 5C: the submission package, and three findings the proofread could not fix
30f68e9 Phase Q T2: adjudicate the line-482 word-number, and start the 5C report
ef1460f Phase Q T1: make the frozen-results byte guarantee a property of the repo

$ git push origin main
fatal: Cannot prompt because user interactivity has been disabled.
To https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
   30f68e9..0e80297  main -> main
push exit=0

$ git ls-remote origin main
0e80297883d903797174eeca672d622edb3dc2a7	refs/heads/main

$ git rev-list --left-right --count origin/main...main
0	0

$ git status --porcelain
                                        # clean
```

**An authentication detour worth recording, because I caused it and then
misdiagnosed it.** The first two push attempts hung (Git Credential Manager
opening an interactive dialog nobody answered). I then retried with
`GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never GIT_ASKPASS=echo`, which failed
hard:

```
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed for 'https://github.com/.../Research-paper-AEP.git/'
push exit=128
```

I read that as an expired credential and reported the push as blocked. It was
not: **`GIT_ASKPASS=echo` was my own doing**, and it makes git call `echo` as its
askpass helper, which returns an empty password — so git authenticated with
nothing and GitHub correctly rejected it. Dropping that one variable and keeping
the other two pushed successfully on the next attempt, exit 0. The `fatal:
Cannot prompt` line above is the same harmless GCM noise 5B recorded in its
§C.15: an interactive lookup GCM did not need, printed to stderr before the
cached credential succeeded. No credential was created, rotated or stored.

**GitHub Actions on `0e80297` — all four jobs green, the numbers gate
included:**

```
$ curl -s .../actions/runs/31384936846
completed success

$ curl -s .../actions/runs/31384936846/jobs
Suite (py3.13, Redis from compose)                      completed    success
Numbers gate (manuscript vs frozen CSVs)                completed    success
Citation ranges (docs/22)                               completed    success
WAITAOF durability (compose, phase2.conf)               completed    success
```

**Run URL:** https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31384936846

The numbers gate is green on a head that contains every proofreading edit, the
repointed bibliography entry, the committed PDF and the updated roadmap — which
is the checklist's "no number drifted during proofreading", verified by CI on the
final state rather than only locally.

**Rule 9, final discharge.** The only external interactions this session were
`git fetch`, `git push`, GitHub Actions running by itself, unauthenticated
`GET`s to `api.github.com` for run status, and the read-only `GET`s to
`doi.org`, `dblp.org`, `redis.io`, `docs.temporal.io` and
`martin.kleppmann.com` that T5 explicitly permits. **Nothing was submitted or
uploaded anywhere. No arXiv or journal account, draft or submission exists.** No
tag was created this session; `v1.0.0-rc1` remains where 5B left it, on
`31664ca`.

*(As in previous sessions, this section is appended in a follow-up commit, so the
run above is green on the head containing everything except these paragraphs.
That commit's own run is recorded by the same workflow and is the repository's
current head.)*

---

## D. EXPECTED RESULTS checklist

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Git prelude pasted; divergence merged if any | ✅ **DONE** | §C.0. `0	0` — no divergence, clean tree, no merge needed |
| 2 | `.gitattributes` exists; `autocrlf=true` scratch-clone hash check pasted, all tracked analysis files OK; scratch clone removed | ✅ **DONE** | §C.2. Before: **5 of 13 corrupted, 0 of 17 OK**. After: **0 of 13 corrupted, 7 OK**, clone tree clean. Both clones deleted, `ls` confirms |
| 3 | Line-482 verdict stated with reasoning; COUNT-CONSTANT justification **or** §G finding in the report | ✅ **DONE**, both | §C.3 gives verdict (i) with per-numeral reasoning and the justification line; the agreement defect it exposed is §G.1 |
| 4 | Phase Q pushed and green **before** any 5C edit; run URL | ✅ **DONE** | §C.4, run **31379777292**, 4/4 jobs green incl. the numbers gate. First 5C edit came after |
| 5 | `verify_refs.py` passes with raw output; zero unverified entries | ⚠️ **DONE, with the tool's verdict corrected** | §C.6. The script exits 0 having verified **nothing** on this host; run properly, **25 of 25** entries verified, **0 unverified**, one dead URL repointed to a verified live one. The script's own exit code is **not** the evidence — §G.3 |
| 6 | `check_paper_numbers.py` still passes after ALL edits (raw output) | ✅ **DONE** | §C.8. **18 passed, 0 failed**, in the same build that produced the committed PDF |
| 7 | Terminology audit result: which term won per concept, grep counts showing zero of the losers | ✅ **DONE** | §C.5.1. `declared ambiguity` (25 vs **0**); `Redis` over `coordinator` (**0** remaining, the 1 survivor is the 2PC sense); crash points already consistent; `dispatch authority`/`authorization` argued as two concepts, not merged |
| 8 | `cover-letter-tse.md` and `arxiv-metadata.md` exist and are complete | ✅ **DONE** | §C.7 |
| 9 | Final PDF committed; page count stated; zero undefined refs; zero `\todo` | ✅ **DONE** | §C.8. **18 pages**, 0 undefined, 0 `\todoitem`; blob hash matches disk |
| 10 | `PAPER_ROADMAP.md` updated exactly as scoped, nothing else changed | ✅ **DONE** | §C.8. 31 insertions (phase table + CURRENT PHASE), 1 deletion (the stale 2B heading). No other hunk |
| 11 | §H has the percentage + top-3 audit risks | ✅ **DONE** | §H |
| 12 | Nothing submitted/uploaded; §B lists only in-bounds files per phase; committed, pushed, Actions green on final head | ✅ **DONE** | §B (2 + 13 files, all in bounds); §E.5 discharges rule 9; §C.9 |

---

## E. Deviations

**E.1 — I committed `.gitattributes` locally before the scratch-clone proof, so
the proof could clone it.** T1 asks for the fix and then a clone-based
demonstration; a clone reads committed state, so the commit necessarily precedes
the proof. The push still happened in T3, after both. The before/after pair in
§C.2 is stronger evidence than an after-only run would have been, and it is why
the "5 of 13" figure exists at all.

**E.2 — I corrected the paper's CI job count from three to four, which is a
factual edit rather than a proofreading one.** `05-implementation.tex:49` said
"Continuous integration runs three jobs" and listed three; `09-artifact.tex:11`
listed the same three. The workflow has **four** —
`citations`, `test`, `waitaof-durability`, `paper-numbers` — since Phase P added
the numbers gate in the previous session:

```
$ grep -nE "^    name:" .github/workflows/ci.yml
64:    name: Citation ranges (docs/22)
87:    name: Suite (py${{ matrix.python-version }}, Redis from compose)
196:    name: WAITAOF durability (compose, phase2.conf)
290:    name: Numbers gate (manuscript vs frozen CSVs)
```

The sentence was verifiably false against a public file, and the paper was
*understating* its own artifact. I judged that shipping a knowingly false
sentence is the worse error, and that a count of CI jobs is not a "quantitative
claim" in 5C's sense — it is not a result, not a rate, and changes no framing.
**It is nonetheless the one edit this session that a strict reading of the
bounds could call substantive, so it is flagged here rather than buried; it is
two sentences and trivially revertible.**

**E.3 — I force-added `paper/main.pdf` past `.gitignore`.** T8 requires the PDF
committed; `.gitignore:102` ignores `paper/*.pdf`. `git add -f` puts the file in
the tree without editing `.gitignore`, which is out of bounds. The alternative —
amending `.gitignore` — would have been the actual violation.

**E.4 — I ran the build and the reference checks under WSL rather than on the
Windows tree.** There is no TeX Live on the Windows side, and Windows Python has
no CA bundle, so `verify_refs.py` failed every lookup there (§C.6). Both are
read-only uses of a second environment against the same working tree. Side
effect worth recording: `build_paper.sh` runs `uv sync`, which **deleted and
rebuilt `.venv` with Linux binaries**, so the Windows-side virtualenv is now
cross-platform. `.venv` is gitignored and no tracked file was touched
(`git status --porcelain` shows only the intended 5C files), but this is the
same hazard 5B recorded as its §E.8 and it will bite the next person who runs
`uv run` on the Windows side without re-syncing.

**E.5 — Rule 9 discharge.** External interactions this session: `git fetch`,
`git push`, GitHub Actions running by itself, unauthenticated `GET`s to
`api.github.com` for run status, and read-only `GET`s to `doi.org`, `dblp.org`,
`redis.io`, `docs.temporal.io` and `martin.kleppmann.com` for T5 — which the
prompt permits explicitly. **Nothing was uploaded, submitted or published. No
account, token or draft exists on arXiv, any journal system, Zenodo, any DOI
minter or any package registry.** `paper/arxiv-metadata.md` is a text file in
the repository and carries a banner saying so.

**E.6 — I wrote §C.9 after the push, as previous sessions have.** The run URL
for the final head cannot exist before the commit that contains the report.

---

## F. Hostile-reviewer weaknesses of *this session's* output

**F.1 — The terminology audit is three concept families deep and the manuscript
has more than three concepts.** I audited exactly what the prompt named, plus
crash-point names, and found two real violations. I did **not** enumerate the
manuscript's full vocabulary and check it for synonymy. "Exactly one name per
concept globally" is a claim about all concepts; what I can evidence is that it
holds for the four families I checked. The `coordinator` violation was found
because the prompt pointed at it — which is a fair summary of how much of this
audit was mine.

**F.2 — I introduced three wrong numbers into `arxiv-metadata.md` and caught
them only because I chose to measure.** I wrote character counts and float
counts from inspection; all three were wrong, and one was wrong in the way that
matters — my "short" abstract was 2 034 characters against arXiv's 1 920 limit,
so the artifact labelled "within the limit" was not. §C.7 records it. The
uncomfortable generalisation: the repository's numbers discipline covers
`paper/*.tex` and nothing else, so the two files this session added are exactly
the kind of unguarded surface where the previous sessions' defects lived. A
Monday auditor should re-measure both counts rather than trust the corrected
figures, for the same reason 5B §H asked for a second reader.

**F.3 — The line-482 finding is arithmetic I did, and the mechanism I offer for
it is a guess.** The factor-of-two gap between the sentence's derivation
(1.0 s) and `\BarrierCost{}` (1 966.7 ms) is solid — both quantities are on the
page. My explanation for *why* the measurement is a full period rather than half
of one — that `WAITAOF` must also observe the post-fsync offset propagate — is
**not measured, not cited, and not in the repository**. I have labelled it a
hypothesis in §G.1 and it must not be promoted to prose on my say-so. A reviewer
who reads §G.1 quickly could mistake the diagnosis for the explanation.

**F.4 — Three cross-references were added at anchors I chose.** `fig:trade`,
`fig:bycrashpoint` and `tab:related` were uncited; the fix is required by IEEE
style and by T4. But which sentence a figure is attached to is an editorial
judgement that shapes how a reader reads the figure, and I made three such
judgements without an author. The `fig:trade` anchor in particular asserts that
the figure is `tab:outcomes` "pooled to one bar pair per system", which I took
from the figure's own caption rather than from re-deriving it from the CSV.

**F.5 — I left ten overfull boxes in a submission-ready manuscript.** §C.5.4
diagnoses all ten, which is more than the previous session managed, and fixes
none. My reasoning — four are generator-owned and therefore §G by instruction,
and a partial fix leaves an incoherent state — is defensible, but the outcome is
that the PDF a reviewer opens has ten places where a table runs into the margin,
the worst by 82.8pt (~2.9 cm). "Submission-ready" is doing some work in that
sentence.

**F.6 — The bibliography is verified against DBLP and doi.org, which verifies
existence, not appropriateness.** Every entry resolves and every field matches.
Nothing in this session checked that the *right* paper is cited at the right
place, that the quoted vendor text still says what §2 and §7 claim it says, or
that a 2026 preprint (`zheng2026acrfence`) has not since been superseded by a
peer-reviewed version that should be cited instead. The URL fetches confirmed
HTTP 200 and page size; **I did not re-read the pages to confirm the quoted
sentences are still on them**, which is what `refs.bib`'s own `[URL]` protocol
requires and what the 404 shows can silently stop being true.

**F.7 — Phase Q's proof is strong and narrow.** The scratch clone demonstrates
that `-text` fixes checkout under `core.autocrlf=true` on this machine, with
this git version. It does not exercise `autocrlf=input`, a clone made before the
rule existed and then pulled forward, or a checkout on a filesystem that
normalises independently. The 5B incident was a *write*-path failure and this is
a *read*-path fix; I have not proved the write path is closed, only that
`-text` disables conversion in both directions by definition.

**F.9 — I reported the push as blocked on an expired credential when I had
broken it myself.** Detail in §C.9. I added `GIT_ASKPASS=echo` to a push
command, got `Invalid username or token`, and attributed it to GitHub-side
credential expiry — a confident diagnosis of an external cause for a failure my
own flag had produced. Removing the flag fixed it immediately. Nothing in the
repository was affected, but the episode is a live example of the failure mode
this whole report regime exists to catch: a plausible explanation, asserted
before the cheaper hypothesis ("what did I just change?") was tested. It is
recorded rather than quietly corrected because the earlier claim was already
made.

**F.8 — Every check in this report was written and run by me, in the same
session as the thing it checks.** Same structural criticism as 5B §F.8, and it
now compounds: the previous session's author checked their own numbers, and I
have checked their checking with instruments I also wrote (the cross-reference
walker, the overfull-box attributor, the macro extractor). None of it has been
run by anyone else.

---

## G. Out-of-scope issues noticed but NOT touched

**G.1 — `06-evaluation.tex:482-483` claims its derivation matches a measurement
that is twice as large.** Full working in §C.3. The sentence predicts a
1.0-second barrier bill from the `everysec` period and says that "is precisely
what we measure"; the paper's own generated `\BarrierCost{}` is 1 966.7 ms and
`\BarrierCostEach{}` is 983.3 ms. The measured per-barrier cost is about one
full fsync period, not half of one.

I have **not** edited it, on two independent grounds: T2's verdict is branch
(i), whose instruction is "change nothing"; and 5C forbids any change that
alters a quantitative claim. A plausible mechanism — that `WAITAOF` cannot
return until the post-fsync offset has been propagated and observed, costing
roughly one further period beyond the wait for the fsync itself — is offered as
a **hypothesis only**. I did not measure it, no file in the repository states
it, and it must not be written into the paper on my say-so. The honest minimal
repair is a wording change ("a mean wait of about one second per barrier,
twice"), but even that asserts a mechanism the repository has not evidenced; the
alternative is to drop the agreement claim and keep only the bound already
stated correctly at `:501`. **That choice belongs to the human.**

**G.2 — The manuscript is anonymised and simultaneously de-anonymised, and only
a human can resolve which.** The author block reads `Anonymous Author(s)`
(`main.tex:67`), while `main.tex:69` and `09-artifact.tex:6` both carry
`https://github.com/hafizmirhamza276-lab/Research-paper-AEP` — a URL naming a
personal account. If TSE review is double-anonymous, the artifact URL defeats
the anonymisation; if it is not, the `Anonymous Author(s)` block is simply
unfinished. I did **not** touch either: stripping the URL would break artifact
availability (which T6's cover letter is required to assert), and filling in the
author block is not mine to do. Compounding it, the planned arXiv preprint is
public by construction, so posting it first makes an anonymised submission moot.
`paper/arxiv-metadata.md`'s pre-submission checklist puts this decision first.

**G.3 — `verify_refs.py` cannot fail, and this session proved it.** The script
returned **exit 0 after every one of its 18 lookups failed** (§C.6). It also
returns 0 when DBLP rate-limits it, and 0 when a query gets zero hits. A gate
whose exit code is constant is not a gate — which is precisely the criticism
this repository levelled at its own test suite in `05-implementation.tex`. Two
smaller faults in the same file: `zheng2026acrfence` is cited in the paper
(`07-related.tex:129`) and has **no query at all** in `QUERIES`, so the sweep has
never checked it; and `QUERIES` still contains `"Notes on Data Base Operating
Systems Gray"`, for which no `refs.bib` entry exists. Editing the script is
forbidden in this phase and I did not.

**G.4 — Ten overfull boxes, four of them only fixable in the generator.** Full
attribution in §C.5.4. `tab:trilemma` (82.8pt), `tab:crashpoints` (4 rows, up to
61.9pt) and `tab:related` (57.0pt) are hand-written; `table-deployment-choice`
(70.4pt), `table-ambiguity-by-crashpoint` (×2) and `table-latency` are produced
by `paper_tables.py`, which T4 names as a §G item rather than an edit. They
should be fixed together — column widths and `\small`/`\footnotesize` choices
across all six tables — rather than piecemeal.

**G.5 — `experiments/results/fsync-always/` still has no `SHA256SUMS`.** 5B §G.4
raised it; unchanged and out of bounds here. Phase Q's `-text` rule now protects
those two tracked CSVs from conversion, but a manifest is what would prove they
are the frozen bytes. Note they are CRLF-terminated and so were never at risk
from the bug Phase Q fixed.

**G.6 — Two self-references read oddly.** `08-threats.tex:45` and `:109` say
"(\cref{sec:threats}, platform)" and "(\cref{sec:threats}, internal validity)"
from *inside* Section 8, so they render as "see Section 8" to a reader already
in Section 8. The subsections carry no labels, so a precise reference would mean
adding them. Cosmetic; not touched.

**G.7 — "two orders of magnitude" is 70×.** `08-threats.tex:369` says the
barriers "dominate the protocol's latency by two orders of magnitude"; the ratio
from the generated macros is $1\,966.7 / 28.0 = 70$. Rounding in log space
($10^{1.85}$) makes this defensible and I have not changed it, but it is the
kind of phrase a hostile reviewer converts into a question.

---

## H. Recommended next step

**Run the Monday audit as written, and give it §G.1 and §C.7 first.**

### Completeness: **96%**

One line of justification, as T9 asks: every gate the repository has now passes
on the committed head (numbers 18/18, suite 1734/0-skipped, citations, WAITAOF),
the bibliography is 25-for-25 verified, the submission package exists, and
**nothing that remains is evidence** — the shortfall is three unadjudicated
findings (§G.1 arithmetic, §G.2 anonymity, §G.4 typesetting) plus an audit that
has not happened, which is exactly the 96–97% the weekend plan predicted for
this point.

### Top 3 risks for the independent audit

**1. The line-482 agreement claim (§G.1) — the highest-value thing to check, and
the one I could not fix.** The manuscript says a derived 0.5 s-per-barrier wait
"is precisely what we measure" while its own generated `\BarrierCost{}` is
1 966.7 ms — a factor of 1.97. Two sessions of number sweeps did not find it
because both looked for numerals whose *provenance* was wrong, not for prose
whose *arithmetic* was. **The audit should assume there are more of these**: the
class is "sentence asserts a relationship between two correctly-generated
numbers, and the relationship is false", and no gate in this repository can see
it. Start by re-deriving every sentence in §6 that connects two macros with
"which is", "so that is", or "is precisely".

**2. Trust in `verify_refs.py`'s exit code (§G.3), and in reference checking
generally.** A reader of the checklist item "verify_refs.py passes" would
reasonably conclude the bibliography is verified. On this host the script exits
0 having verified nothing. I verified all 25 entries by other means and the
bibliography is genuinely sound — but the audit should re-run it *and check that
it actually resolved anything*, because the same false-pass is available to
anyone who runs it in CI or on a fresh machine. Related and unclosed: nothing
has re-read the six vendor pages to confirm the sentences `refs.bib` quotes are
still on them, and one of those URLs had already 404'd.

**3. Scope drift in two places I chose, and the anonymity decision I did not
(§E.2, §G.2, F.4).** The CI job-count correction (3→4) is the single edit that a
strict reading of "no substantive change" could reject; it is two sentences and
I have flagged it rather than hidden it. Three figure/table cross-references
were added at anchors I selected without an author. And the manuscript ships
both an `Anonymous Author(s)` block and a personal GitHub URL — a contradiction
that must be resolved before either arXiv or TSE, and which cannot be resolved
by any process that does not include the actual author.

### After the audit

If the verdict is SUBMIT, the ordered work is: resolve §G.2 (anonymity) → fix or
reword §G.1 → fix §G.4's ten overfull boxes in one pass across
`paper_tables.py` and the three hand-written tables → rebuild → re-measure the
arXiv abstract → then submit. If the verdict is FIX FIRST, §G.1 is the item that
should lead the list, because it is the only one that touches what the paper
claims rather than how it looks.

The highest-value *experiment* when host time is next available is unchanged
from 5A §H and 5B §H: backlog **§B2**, prevention on the other two capability
classes, ≈2 h, no code change. It is the weakest evidence under the paper's most
novel mechanism, and §C.5's proofread did not make it any stronger.
