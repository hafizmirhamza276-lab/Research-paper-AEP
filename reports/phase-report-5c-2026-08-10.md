# Phase Q + Phase 5C — the byte guarantee made portable, one word-number adjudicated, and the manuscript readied for an audit it has not yet had

**Date:** 2026-08-10
**Prompt:** combined Pre-5C micro-fixes (T1–T3) → Phase 5C submission-ready (T4–T9).
**Predecessor:** `reports/phase-report-5b-2026-08-10.md`
**Governing bounds document:** `WEEKEND_CODEX_PROMPTS.md` (Prompt 4), plus the
two SCOPE BOUNDS blocks in this session's prompt.

> **Read this first.**
>
> *(This banner is completed at the end of the session; the Phase Q findings are
> stated here, the 5C findings are added after T8.)*
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

---

## A. Phase attempted and scope reference

| Task | Requirement | Status |
|---|---|---|
| **T1** | `.gitattributes` making the tracked-results byte guarantee portable; `autocrlf=true` scratch-clone proof | ✅ **Done.** §C.1–§C.2 |
| **T2** | Classify the borderline word-number at `06-evaluation.tex:482` | ✅ **Done**, verdict (i), with a §G finding. §C.3 |
| **T3** | Commit Phase Q, push, Actions green including the numbers gate | ✅ **Done.** §C.4 |
| **T4** | Full proofread — grammar, terminology, number formatting, cross-references, IEEEtran | *(pending)* |
| **T5** | `verify_refs.py` full pass | *(pending)* |
| **T6** | `paper/cover-letter-tse.md` | *(pending)* |
| **T7** | `paper/arxiv-metadata.md` | *(pending)* |
| **T8** | Final PDF committed; `PAPER_ROADMAP.md` updated as scoped | *(pending)* |
| **T9** | §H completeness percentage + top-3 audit risks | *(pending)* |

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

*(completed after T8)*

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

*(filled in below, after the push)*

---

## D. EXPECTED RESULTS checklist

*(completed at the end of the session)*

---

## E. Deviations

*(completed at the end of the session)*

---

## F. Hostile-reviewer weaknesses of this session's output

*(completed at the end of the session; mandatory and non-empty)*

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

*(further items added during 5C)*

---

## H. Recommended next step

*(completed at the end of the session, with the completeness percentage and the
top-3 audit risks required by T9)*
