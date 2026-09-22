# Phase 44 — §II's ruling, and repository paths out of the rendered manuscript

**No live calls.** Three commits: the §II ruling, the path removal, the gate
check.

| | |
|---|---|
| §II ruling | *"By every signal the system exposes"* reverted |
| paths in rendered text | **23 → 0** |
| new gate | `scripts/check_no_repo_paths.py`, wired into all four builds |
| known-positives | **37 unit tests**, plus one end-to-end build failure |
| flagged | **nothing** — no claim lost its only support |
| pages | main **24**, main-anon **24**, supplementary **7**, supplementary-anon **7** |

---

## 1. §II's ruling

> **Before:** By every signal the system exposes, the execution is green.
>
> **After:** The execution is green.

*"Every signal"* is broader than the three the paragraph enumerates. Removing
the italics was what the punchline needed; the added clause was not.

---

## 2. Inventory, and the replacement chosen for each

**Taken from the rendered PDFs**, not from the `.tex`. Two of the twenty-three
were in `paper/generated/`, which nobody edits by hand, and a source-only scan
would have attributed them to the wrong file.

`%` comments are excluded throughout and are untouched. A comment is not in the
PDF, which is the reason this project puts sources in comments.

### 2.1 `main.pdf`

| # | file:line | occurrence | what it supported | replacement |
|---|---|---|---|---|
| 1 | `03-model.tex:4` | `docs/22-formal-model.md` | that §III condenses a formal model which cites enforcing code and is CI-checked | **(2) fact in a clause** — *"a formal model held in the artifact, which states every claim below with a citation to the enforcing code by file and line"* |
| 2 | `04-protocol.tex:217` | `aep_core/core/intents.py` | figure caption: where the state machine is generated from | **(2)** — *"generated from the transition table in the implementation"* |
| 3 | `05-implementation.tex:46` | `uv.lock` | that the environment is pinned | **(2)** — *"locked by a resolved dependency lockfile"* |
| 4 | `06-evaluation.tex:236` | `per-cell-metrics.csv` | where the wider cluster-aware intervals are | **(3) artifact pointer** — *"the artifact's per-cell metrics"* |
| 5–6 | `scripts/paper_tables.py:192,209` → `generated/table-outcomes.tex` caption | `per-cell-metrics.csv` ×2 | caption source attribution | **(3)** — same wording; **the generator was edited and the table regenerated** |
| 7 | `main.tex:213` | `.claude/agents/` | AI disclosure: where model identifiers are recorded | **(2)** — *"the per-assistant configuration files committed beside them"* |
| 8 | `main.tex:215` | `prompts/` | AI disclosure: where phase prompts are committed | **(2)** — *"committed in that repository"* |
| 9 | `main.tex:223` | `scripts/paper_tables.py` | which tool generates the numbers | **(3)** — *"the artifact's table generator"* |
| 10 | `main.tex:224` | `scripts/check_paper_numbers.py` | which tool re-derives them | **(3)** — *"its independent number check"* |
| 11 | `09-artifact.tex:20` | `MANIFEST.sha256` | per-file checksums in the archive | **(3)** — *"its own archive's checksum manifest"* |
| 12 | `09-artifact.tex:54` | `uv.lock` | the Python environment is locked | **(2)** — *"by a resolved dependency lockfile"* |
| 13 | `09-artifact.tex:66` | `MANIFEST.csv` | where the collected cells are keyed | **(3)** — *"the tracked per-cell manifest"* |
| 14 | `09-artifact.tex:72` | `scripts/paper_tables.py` | which tool generates the tables | **(3)** — *"the artifact's table generator"* |
| 15 | `09-artifact.tex:73` | `ARTIFACT.md` | where the tracked inputs are enumerated | **(3)** — *"the tracked inputs its documentation enumerates"* |
| 16 | `09-artifact.tex:77` | `scripts/build_paper.sh` | the command that builds and checks | **(3)** — *"The artifact's build script"* |
| 17 | `09-artifact.tex:81` | `scripts/check_paper_numbers.py` | the drift check | **(3)** — *"An independent number check"* |
| 18 | `09-artifact.tex:93` | `experiments/flakey_write_loss.py` | the probe excluded from the suite | **(2)** — *"the write-loss probe"* |
| 19 | `09-artifact.tex:105` | `scripts/gen_state_machine.py` | what generates the figure | **(2)** — *"a script that imports the transition set from the implementation"* |

### 2.2 `supplementary.pdf`

| # | file:line | occurrence | what it supported | replacement |
|---|---|---|---|---|
| 20 | `supplementary.tex:119` | `per-cell-metrics.csv` | caption: where the wider intervals are | **(3)** — *"the artifact's per-cell metrics"* |
| 21 | `supplementary.tex:235` | `redis-kill-ablation.csv` | caption source line | **(3)** — *"the artifact's Redis-kill ablation metrics"* |
| 22 | `supplementary.tex:300` | `experiments/results/matrix/MANIFEST.md` | per-cell run counts | **(3)** — *"the matrix manifest … that ship with the artifact"* |
| 23 | `supplementary.tex:301` | `analysis/coverage.json` | per-cell coverage | **(3)** — *"the coverage record"* |
| 24 | `supplementary.tex:679` | `results/voided/` | where the voided attempt ships | **(2)** — *"in a directory reserved for voided runs"* |

**(1) `\cref` to the supplementary was never the right answer.** Nothing being
cited by path had a supplementary section to point at; every one was an
attribution of where a file lives.

### 2.3 What was deliberately left

**Four vendor documentation URLs in the bibliography stay**, and the check
exempts them by URL context:
`https://redis.io/docs/latest/operate/`, `https://redis.io/docs/latest/commands/`,
`https://redis.io/docs/` and `https://cadenceworkflow.io/docs/concepts/workflows`.
These are citations. A test asserts they are still present, so the exemption
cannot be bought by deleting them.

**`\input{figures/state-machine}` and `\includegraphics{figures/…}` stay.** They
are build-time paths and never render.

### 2.4 The generative-AI disclosure — every element kept

Two paths left it; nothing else did. Still present: the model families, that use
was not confined to one part of the work, the six named areas it covered, the
author's direction and review, the reason identifiers are not listed, **the
commit trailers as the authoritative record**, the pre-registered phase prompts
from Phase 8 onward, **the Phases 1A–7 gap and the statement that the project's
audit records it rather than reconstructing it**, that no AI system is an
author, that every measurement was collected by the harness and is reproducible,
and that the author is solely responsible.

`.claude/agents/` → *"the per-assistant configuration files committed beside
them"*. `prompts/` → *"committed in that repository"*.

### 2.5 Nothing flagged

**No claim lost its only support.** Every occurrence was an attribution of where
a file lives, never the evidence for a statement. The statements themselves —
that the model is CI-checked, that the environment is pinned, that the figure is
generated from the implementation, that the numbers are re-derived — are all
still made, and all still supported by the same mechanisms.

### 2.6 §IX after the change

`docs/37`'s instruction allows §IX to describe structure by component name. It
now reads as a description of what the artifact contains rather than a file
listing, which is also how a TSE artifact section usually reads: *the artifact's
table generator*, *an independent number check*, *the artifact's build script*,
*the write-loss probe*, *a resolved dependency lockfile*, *the tracked per-cell
manifest*, *its own archive's checksum manifest*.

---

## 3. The gate check

### 3.1 `scripts/check_no_repo_paths.py`

Wired into `scripts/build_paper.sh` for **all four variants**, not only the main
non-anonymous one: a repository path is wrong in every build, and it is an
anonymity risk in exactly the two the numbers check skips. It runs on the staged
PDF **before promotion**, so a build that would ship one never replaces a clean
artifact.

**It reads the PDFs, not the LaTeX.** A `\texttt` reaches the page from a
caption, a footnote, a table cell and a generated file by four different routes,
and only the extracted text sees all of them at once. Two of the twenty-three
were in `paper/generated/`.

Patterns: a known repository directory followed by a slash; a bare filename with
a source-code extension; `MANIFEST.*`; `ARTIFACT.md`.

Exemptions, both tested: anything inside an `http(s)://` or `doi.org` run, and
prose that merely contains a slash or a dot.

### 3.2 Known-positives — 37 tests

| group | count | what must fire |
|---|---|---|
| repository paths | 9 | every real occurrence: `docs/22-formal-model.md`, `scripts/paper_tables.py`, `experiments/flakey_write_loss.py`, `aep_core/core/intents.py`, `.claude/agents/`, `prompts/`, `results/voided/`, `analysis/coverage.json`, `experiments/results/matrix/MANIFEST.md` |
| bare source filenames | 7 | `uv.lock`, `per-cell-metrics.csv`, `redis-kill-ablation.csv`, `ARTIFACT.md`, `MANIFEST.sha256`, `MANIFEST.csv`, `analyze.py` |
| every pattern fires | 1 | if a pattern stops matching anything it has stopped checking |
| generated-table caption | 1 | the two occurrences that were in `paper/generated/` |
| **exemptions that must NOT fire** | 14 | six vendor/archive URLs, seven prose-with-a-slash cases, one wrapped URL whose continuation looks like a bare path |
| committed state | 5 | all four builds clean, and the vendor URLs still present |

### 3.3 The end-to-end known-positive

Unit tests exercise the checker. This exercises the **wiring**. Restoring the
pre-fix `05-implementation.tex` from `HEAD`, which contained
`\texttt{uv.lock}`, and building `main`:

```
=== repository paths in the rendered text ===
  FAIL  main.pdf line 1058: source filename 'uv.lock'
        (uv.lock), the Redis image is pinned by digest, and
---- 1 occurrence(s) of a repository path in rendered text
     Replace with a \cref to the supplementary, a one-clause statement of the
     fact, or a generic artifact pointer.

DO NOT SUBMIT: 2 check(s) failed. Existing main.pdf preserved.
```

Exit 1, and the existing PDF was preserved. The tree was restored afterwards.

**Two earlier attempts at this failed for a reason worth recording.** Injecting
`scripts/paper_tables.py` as plain text broke the LaTeX run on the unescaped
underscore, so the build died before reaching the check; the real pre-fix source
was the correct fixture because it was valid LaTeX that had actually shipped.

### 3.4 One test was updated, and it did not weaken

`tests/test_paper_tables.py::test_the_outcomes_caption_discloses_the_crash_point_asymmetry`
asserted `"per-cell-metrics.csv" in caption`. Its purpose is that the caption
attributes its source. It now asserts the prose form is present, the filename is
absent, **and** that the `%` provenance census still carries the exact file. The
requirement did not weaken; its spelling changed.

---

## 4. The two metadata files

| file | hits | verdict |
|---|---|---|
| `paper/arxiv-metadata.md` | 19 in the file, **0 in the six pasted blocks** | **No change.** The nineteen are author instructions — *"run `python scripts/render_arxiv_abstract.py --write`"*, *"`docs/29` is the checklist"*, the `grep` command for re-counting figures. They tell the author what to do and are never pasted anywhere |
| `paper/cover-letter-tse.md` | 7, of which **1 in the letter body** | **Fixed.** `ARTIFACT.md` at L167 → *"A single artifact document at the repository root"*. The other six are in the provenance section below the rule marked *not part of the letter* |

---

## 5. Prose metrics, updated

Recorded in `docs/37` §13a rather than by editing §13, which is the pre-rewrite
baseline and should stay that way.

| file | words, §13 | words now | em (prose) |
|---|---|---|---|
| `01-introduction` | 1056 | 1065 | 0 |
| `02-motivating` | 731 | 728 | 0 |
| `03-model` | 638 | 652 | 0 |
| `04-protocol` | 2291 | 2291 | 28 |
| `05-implementation` | 440 | 444 | 4 |
| `06-evaluation` | 6389 | 6392 | 68 |
| `07-related` | 3204 | 3204 | 28 |
| `08-threats` | 3234 | 3234 | 25 |
| `09-artifact` | 816 | 825 | 8 |
| `main.tex` | 688 | 693 | 6 |
| `supplementary` | 4165 | 4175 | 38 |

Only §I, §II and §III were rewritten; the others moved only where a path was
removed. §IX gained 9 words because *"an independent number check"* is longer
than a filename.

---

## 6. Verification

| | |
|---|---|
| live calls | **none** |
| prose style | not touched beyond the wording around each replacement |
| spelling | British `-ise`, unchanged |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `prove_anonymous_gate.sh` | green |
| suite | **2593 passed, 34 skipped** |
