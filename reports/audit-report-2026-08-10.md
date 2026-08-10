# Independent adversarial audit — everything after the 4B handoff

**Auditor:** a different agent/model from the one that ran the 4B, 5A, 5B and 5C
sessions. Nothing in any prior report was taken as true; every claim reported
below was re-derived from a fresh clone.

**Audited range:** `e1e815d` (4B handoff) → `a03985c` (head), plus the 4B bounds
adjudication that the 5A report performs on the pre-handoff session.

**Method:** fresh `git clone` of
`https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git` into an empty
directory. Windows 11 host, Git 2.54, Python 3.11/3.13, `uv` 0.11.8, Docker
29.4.3, WSL2. No LaTeX on the host, so PDF-dependent checks were run either
against the committed PDF or inside a Linux container.

---

## 0. A precondition that failed, recorded as a finding

**The three prompt files the sessions actually ran under —
`COMBINED_PROMPT_P0_5A.md`, `COMBINED_PROMPT_PRE5B_5B.md`,
`COMBINED_PROMPT_PRE5C_5C.md` — were not available to this audit.** They are not
in the repository, not in the working directory, and not anywhere on the audit
host (searched `D:\personal` and the user profile to depth 4). They are not in
git history at any revision.

Per instruction I fell back to each report's §A declared scope, **and the
fallback is itself a finding (D9 below).** The consequence is precise and worth
stating plainly: for the bounds audit I can prove that *the file list each report
declares is exactly the file list git shows*, and that every changed file lies
inside the bounds *as each report states them* — but I cannot prove those stated
bounds are the bounds the human actually issued. A session that widened its own
declared bounds to match what it did would be invisible to this audit.

Two things partially offset it. `WEEKEND_CODEX_PROMPTS.md` **is** in the repo
(committed by 5A at `8db9084`) and I verified it is byte-identical to the human's
uploaded `CODEX_PROMPTS.md` (`git rev-parse 833bd91:CODEX_PROMPTS.md` and
`git rev-parse HEAD:WEEKEND_CODEX_PROMPTS.md` both return
`62c33844bf36ad2fbce79d267622f52cc4366337`). And the *planned* regime it contains
is materially narrower than what the sessions did, which is consistent with the
stated history that the combined prompts superseded it — but it cannot stand in
for them.

---

## 1. Bounds and rule-compliance audit

### 1.1 File lists, derived from git rather than read from §B

I derived each session's file list with `git diff --name-status` over the commit
range and compared it to the report's §B. **All three match exactly.**

| Session | Range | Files (git) | §B claims | Match |
|---|---|---|---|---|
| 5A | `07547df..eca6fcd` | 9 | 9 | ✅ exact |
| 5B (Phase P) | `eca6fcd..9975dc1` | **22** | "**21 files**" | ⚠️ all 22 listed; count wrong (**D1**) |
| 5B (Phase 5B) | `454a825` | 5 | 5 | ✅ exact |
| 5C | `c262f0f..a03985c` | 14 | 2 (Q) + 13 (5C), union 14 | ✅ exact |

Every changed file across the whole range falls inside the union of the declared
bounds: `paper/**`, `reports/**`, `docs/24-revision-backlog.md`,
`WEEKEND_CODEX_PROMPTS.md`, `experiments/results/**` (`git add` only),
`.github/workflows/ci.yml`, `.gitignore`, `.gitattributes`, `ARTIFACT.md`,
`Makefile`, `README.md`, `CHANGELOG.md`, `CITATION.cff`,
`scripts/paper_tables.py`, `tests/test_paper_tables.py`, `PAPER_ROADMAP.md`.

**No out-of-bounds file changed.** In particular `aep_core/**` is untouched
across the entire range — no implementation change could have moved a measured
number — and `scripts/` shows only `paper_tables.py`, so the pytest-gate script
`check_pytest_gates.py` was never edited.

### 1.2 The 4B bounds adjudication (verified, including the timeline finding)

The 5A report states, contrary to what its prompt asked it to write, that **3 of
13 files post-date the 18:15:53 upload of `833bd91`.** I re-derived this by
splitting the 4B commits at the boundary and taking the set difference. Files
first touched only after 18:15:53, excluding the report:

```
paper/figures/figure-1-undetected-vs-ambiguity.pdf
paper/figures/figure-2-duplicates-by-crash-point.pdf
paper/generated/table-outcomes.tex
```

**Exactly 3. The adjudication is correct**, and it was self-reported against the
session's own interest.

### 1.3 Rule 10 — no history rewriting

- **Force-push / rebase:** all four 4B hashes named in the 5A checklist
  (`fc2ed65`, `7ff034d`, `b4876ed`, `e1e815d`) resolve in the cloned history, and
  `07547df` is a true merge preserving `833bd91` as a second parent — i.e. the
  merge-not-rebase decision is visible in the DAG. Exactly one merge in range.
  *Limitation:* a fresh clone cannot disprove a force-push that rewrote and then
  restored identical hashes; the reflog is local to the pushing machine. What I
  can say is that no commit named in any report is missing.
- **Amended pushed commits:** author date == committer date on all 16 commits in
  range. An amend or rebase normally desynchronises them.
- **Deleted reports:** `git log --diff-filter=D -- 'reports/*'` over all history
  returns exactly one hit, `reports/_section_f_draft.md`, deleted in `c5592b9`
  (Phase 4 Session 1) — a scratch draft, **before** the audited range. No phase
  report was ever deleted.
- **Edited reports:** five report modifications exist. Three are pure appends
  (+43/-0, +67/-0, +91/-0). Two are not, and I read both diffs:
  - `0e80297` (+734/-20) removes only `*(pending)*` / `*(completed at the end of
    the session)*` placeholders and replaces them with content — normal
    in-session completion.
  - `e1e815d` (+24/-6) replaces a short "push blocked" paragraph with a longer,
    *more* self-incriminating one (six attempts over ninety minutes, a refused
    credential-inlining workaround). Not falsification.
- **Frozen results:** `git log --all --diff-filter=DM -- experiments/results`
  is **empty**. No tracked results file has ever been modified or deleted.

### 1.4 Frozen-results hashes, re-derived

`experiments/results/matrix/SHA256SUMS` lists 17 files; 13 files are tracked
under `experiments/results/`, of which **7 are covered by the manifest. All 7
verify.** The other 10 manifest entries are archive-layer files excluded by
`.gitignore:130,134`; ARTIFACT.md documents this explicitly and gives the
`grep -v "No such file"` invocation. So the mismatch is disclosed, not hidden —
but the naïve command still exits non-zero on a clone (**D3**).

**This clone is a stronger test of the CRLF fix than the sessions could run.**
My clone inherited `core.autocrlf=true` from the Git-for-Windows system config
(`D:/Git/etc/gitconfig`) — the exact condition that corrupted 5 of 13 files. A
byte-level census confirms the `.gitattributes -text` rule holds:

```
coverage.json                 CRLF=0     loneCR=0   loneLF=44     (pure LF)
g2-flakey-write-loss.json     CRLF=0     loneCR=0   loneLF=510    (pure LF)
g2-flakey-write-loss-rep2     CRLF=0     loneCR=0   loneLF=510    (pure LF)
g2-flakey-write-loss-rep3     CRLF=0     loneCR=0   loneLF=518    (pure LF)
SHA256SUMS                    CRLF=0     loneCR=0   loneLF=17     (pure LF)
per-cell-metrics.csv          CRLF=757   loneCR=0   loneLF=0      (native CRLF)
per-execution.csv             CRLF=3781  loneCR=0   loneLF=0      (native CRLF)
MANIFEST.csv                  CRLF=127   loneCR=0   loneLF=0      (native CRLF)
```

This matches the 5B report's blob-level table line for line (44 / 510 / 510 /
518 / 17 / 757 / 127). **Register finding 2 is CONFIRMED RESOLVED, 5/13 → 0/13,
verified under the hostile configuration rather than asserted.**

### 1.5 Rule 9 — external actions

- `v1.0.0-rc1` is a **plain annotated tag** (`git cat-file -t` → `tag`) on
  `31664ca`. Its message ends "Nothing has been published, uploaded or submitted
  anywhere."
- `GET /repos/.../releases` returns **`[]`** — no GitHub release, therefore no
  release assets.
- No commit message or report asserts an upload. The only occurrences of
  "uploaded" in range refer to the human's own GitHub-web upload of
  `CODEX_PROMPTS.md`, and to explicit negations ("Nothing was uploaded to Zenodo,
  arXiv, any DOI minter, any package registry, or a GitHub release").
- `paper/cover-letter-tse.md` and `paper/arxiv-metadata.md` are in-repo drafts
  required by the 5C task list. I read the ban's "no drafts anywhere" as
  prohibiting drafts *created on external submission systems*, which is
  consistent with the human residual checklist retaining arXiv/TSE submission.
  Flagging the interpretation explicitly since it is a judgement call.

---

## 2. Claims audit — run, not read

### 2a. `reproduce-figures` — PASS, at a stricter standard than the target uses

`make` is unavailable on the host, so I executed the target's own commands. All
six generated files regenerate from the frozen CSVs and are **byte-identical**
to what is committed — verified with `cmp`, i.e. without the `tr -d '\r'`
normalisation the Makefile applies:

```
BYTE-IDENTICAL numbers.tex
BYTE-IDENTICAL table-ablation.tex
BYTE-IDENTICAL table-ambiguity-by-crashpoint.tex
BYTE-IDENTICAL table-deployment-choice.tex
BYTE-IDENTICAL table-latency.tex
BYTE-IDENTICAL table-outcomes.tex
```

`gen_state_machine.py --check` → `OK: paper/figures/state-machine.tex matches
aep_core.core.intents`, exit 0.

The two analysis figure PDFs **were not checked** — the tracked archive holds no
run directories, so the target's figure branch reports `SKIPPED`. That is
honestly printed by the Makefile and documented in ARTIFACT.md, but it remains a
real reproducibility gap (**D4**), and both files were modified in 5A.

### 2b. `check_paper_numbers.py` and the CI job — PASS

Run from the fresh clone: **14 substantive checks pass**, including all six
"matches the CSVs" checks, "no generated table draws from the banned pooled
table", "every generated number is used in the manuscript", and the
state-machine check. Two checks fail locally — `main.bbl` and `main.log` are
build byproducts absent without LaTeX. The script has **18 `check()` call
sites**, and the CI job installs TeX Live and runs `build_paper.sh` before
gating, which is why CI reports 18/18.

**CI on head `a03985c`: run
[31385351715](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31385351715),
conclusion `success`, 4/4 jobs**, including **"Numbers gate (manuscript vs frozen
CSVs)" — success.**

### 2c. `reproduce-smoke` — harness liveness confirmed, and both safety guards fire

I could not run `make reproduce-smoke` verbatim: the target shells out to
`docker compose`, and my clean Linux clone lived inside a container with no
Docker socket. I therefore performed the target's steps with the pieces split
across the two environments, and I state that plainly rather than claim the
target ran. On the host: `docker compose -f compose.phase2.yml up -d --wait`,
then `verify_redis_semantics.py` →

```
verified redis_version=7.2.5 / appendonly=yes / appendfsync=everysec
verified aof-use-rdb-preamble=yes / aof_enabled=1 / waitaof=present
OK: live Redis matches phase2.conf semantics
```

Then, in a `python:3.13-slim` container on the compose network, from a **genuinely
clean `git clone` at `a03985c`**, `uv sync --frozen` (41 packages) and the
target's collection and analysis steps:

```
system                                   undet.dup   lost effect   declared amb
-------------------------------------------------------------------------------
AEP_FULL                                       0/2           0/2            0/2
B0_NAIVE_RETRY                                 1/2           0/2            0/2
B1_LEASE_ONLY                                  1/2           0/2            0/2
B2_CAS_ONLY                                    2/2           0/2            0/2
B3_INTENT_NO_BARRIER                           0/2           0/2            0/2
B4B_DURABLE_WORKFLOW_AT_MOST_ONCE              0/2           2/2            0/2
B4_DURABLE_WORKFLOW                            2/2           0/2            0/2
```

Every system lands in its own corner of the trilemma, including B4b trading all
duplicates for 2/2 lost effects. Two executions per cell estimate nothing, as
the Makefile itself says; this is a liveness result.

**Both safety guards were exercised and both refused:**

1. On Windows: `REFUSED: amendment D2 requires every run in EVALUATION mode on
   Linux. This platform has no SIGKILL, so its crashes would be
   TerminateProcess` (exit 2). The harness will not manufacture data that looks
   like the paper's from a weaker fault.
2. On Linux with the marker deleted: `RunAborted: Redis at '…' does not advertise
   'aep:test-instance-marker' … it refuses to run against an instance that has
   not asserted it is disposable` (exit 1).

### 2d. Two trilemma cells traced end-to-end

**Cell 1 — B4 / AUTH / undetected duplicate (mandatory).** From the raw
`per-execution.csv` rows, filtered to `regime == '(session-3)'`:

```
executions=180  runs=18  crash_points=6   numerator=95   rate=0.5278
  after_barrier_before_dispatch      28/30      after_response_before_resolution  29/30
  after_intent_before_barrier         1/30      before_intent_write                7/30
  after_resolution_before_barrier     5/30      mid_dispatch                      25/30
```

`per-cell-metrics.csv` carries the same six rows (28/30, 1/30, …) summing to
**95/180 = 0.5278**; `table-outcomes.tex` prints `0.5278`; the PDF contains both
the table row and the prose *"it duplicates on AUTH as well, at 0.5278 over 180
executions"* and *"The full cell puts B4's AUTH duplicate rate at 0.5278, in line
with its other two classes"*. **Register finding 1 (0.9500 → 0.5278) is
CONFIRMED RESOLVED at every link in the chain.**

**Cell 2 — AEP-full / NONE / declared ambiguity.** Raw rows → **130/180 =
0.7222** → per-cell-metrics 130/180 → table `0.7222` → PDF prose *"AEP's
declared-ambiguity column is 0.0000 on AUTH, 0.3500 on POS-ONLY and 0.7222 on
NONE"*. Confirmed.

Incidental check while tracing: B0/B1/B2 have `crash_points=5` against 6 for the
intent-bearing systems. This is **not** a sampling defect — the missing point is
`after_intent_before_barrier`, which cannot exist for a system with no intent
write or barrier (360 rows = 4 systems × 3 classes × 30). It is, however,
nowhere stated in the table caption (**D11**).

### 2e. 4B §F.5 → 5A adjudication — complete, nothing vanished

All six items appear in the 5A table with verdicts and pointers.

| §F.5 item | Verdict | Independently verified |
|---|---|---|
| 1 write-loss probe never ran the protocol | (c) | `docs/24-revision-backlog.md` §B1, 51 lines, with design + blocking mechanism ✅ |
| 2 prevention result is one cell | (c) | §B2, 32 lines ✅ |
| 3 detection finding has no external referent | (b) | `08-threats.tex` — substantive paragraph present: *"supported by two systems we wrote, measured by a harness we wrote, against a provider we wrote"* ✅ |
| 4 barrier cost under `always` spans zero | (c) | §B3, 45 lines, incl. `file:line` proof the benchmark script cannot raise run count ✅ |
| 5 B4b has no AUTH cell, B4's is n=20 | (a) | Fixed: both cells now `executions=180 runs=18 crash_points=6`; `DASH CHECK: PASS` ✅ |
| 6 declared ambiguity not an operational outcome | (c) | §B4, 39 lines ✅ |

### 2f. Ten sampled claims, checked against raw output — and re-derived where possible

I went past the instruction (does §C carry raw output?) and independently
recomputed the claim wherever the repository allowed it.

| # | Claim | Source | Result |
|---|---|---|---|
| 1 | B4/B4b AUTH cells at 180 executions, 18 runs, 6 crash points | 5A §C.4–5 | ✅ re-derived from CSV |
| 2 | `0.9500` → `0.5278` | 5A §C.5 | ✅ re-derived (95/180) |
| 3 | Trilemma table has no dash cells | 5A §C.4 | ✅ re-derived |
| 4 | 3 of 13 files post-date the boundary | 5A §C.2 | ✅ re-derived (exactly 3) |
| 5 | Line-ending census of the 13 tracked inputs | 5B §C.3 | ✅ matches my byte census line for line |
| 6 | 89 macros in `numbers.tex` | 5B §C.6 | ✅ `grep -c '\newcommand'` → 89 |
| 7 | Caption falsified by its own B3 row, reworded | 5B §C.8 | ✅ committed caption == quoted "After"; test-backed |
| 8 | `reproduce-smoke` from a clean clone | 5B §C.12 | ✅ independently reproduced (2c) |
| 9 | "coordinator" 9× → 0 | 5C §C.5.1 | ✅ 1 occurrence remains, and it is the legitimate *transaction* coordinator at `03-model.tex:153` — the colliding sense is at zero |
| 10 | 25/25 references verified; one rotted URL repointed | 5C §C.6 | ✅ 6 spot-checked exact; old URL **404**, new URL **200** |
| 11 | arXiv short abstract cut to 1 862 chars (limit 1 920) | 5C §C.7 | ✅ measured 1 861 (trailing-newline convention); well under limit |

Every sampled claim has raw output behind it in §C. **I found no claim without
supporting output, and no sampled claim that failed re-derivation.**

### 2g. CI gates — intact, and provably not weakened

- `ci.yml` across the entire audited range: **79 insertions, 0 deletions.** With
  zero deleted lines, no gate can have been weakened or removed; the only change
  was adding the `paper-numbers` job.
- `MINIMUM_TESTS` history: 1100 → 1350 → 1500 → 1590 → **1700**, last raised at
  `b2fc057` (Phase 4B, before the range). **Not touched in the audited range.**
- Redis pinned by digest, not tag:
  `redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44`.
- Zero-skip / zero-xpassed enforcement present via `scripts/check_pytest_gates.py`
  with `--minimum-tests "${MINIMUM_TESTS}"`; that script is untouched in range.

### 2h. Bibliography — 6 entries verified independently (≥5 required)

`verify_refs.py` is confirmed hollow: `main()` returns 0 unconditionally, a
failed lookup only prints `!! LOOKUP FAILED`, and the script is **not invoked by
CI, the Makefile, or `build_paper.sh`**. So the 25/25 claim rests on the human
comparison recorded in 5C §C.6, not on a gate. I therefore checked it myself
against authoritative APIs:

| Entry | Check | Result |
|---|---|---|
| `fischer1985impossibility` | Crossref `10.1145/3149.214121` | ✅ exact: Fischer/Lynch/Paterson, JACM 32(2), 374–382, 1985 |
| `zheng2026acrfence` | arXiv `2603.20625` | ✅ **real, not fabricated** — exact title and all four authors, 21 Mar 2026 |
| `jia2021boki` | Crossref `10.1145/3477132.3483541` | ✅ exact: Jia & Witchel, SOSP 2021, 691–707 |
| `helland2012idempotence` | Crossref `10.1145/2160718.2160734` | ✅ exact: Helland, CACM 55(5), 56–65, 2012 |
| `burckhardt2021durable` | Crossref `10.1145/3485510` | ✅ exact: all six authors, PACMPL 5(OOPSLA), 1–27 |
| `redis-locks` (the 5C repoint) | live fetch, both URLs | ✅ old path **HTTP 404**; new path **HTTP 200** carrying the Redlock content |

The 2026-dated entry was the one most worth attacking and it survived. 5C's two
self-reported sub-faults in `verify_refs.py` also reproduce: `zheng2026acrfence`
has **no** entry in `QUERIES`, and `QUERIES` still contains `"Notes on Data Base
Operating Systems Gray"` for which **no** `refs.bib` entry exists (**D7**).

---

## 3. Manuscript read, as a hostile TSE reviewer

**Detection-vs-prevention framing: clean.** The abstract separates them
explicitly ("Our central result separates two claims that the write-ahead
pattern is usually sold as one"), attributes detection to the durable
pre-dispatch record alone, and confines prevention to the hard-Redis-kill fault
with its own metric. §6.2.2's opening — *"If detection does not need the barrier,
what does the barrier do?"* — states the ablation's logic without overreaching.
The prevention subsection names its own scope in its own text (one execution per
run, `\AepKillRuns{}` runs, `NO-READBACK`), and §8 carries the single-cell
limitation.

**The B3-equivalence finding is honestly placed.** It is in the abstract, not
buried; it is stated as a bound rather than as proof of equality (*"bounding each
rate and the difference between them below `\AblationZeroUpper{}`%"*), which is
the correct repair of the earlier `p = 1.00` error. The corrected caption is
committed and matches: *"AEP-full and B3 — the same protocol with and without the
durability barrier — are the only systems that record any declared ambiguity …
That the two are indistinguishable here is this paper's ablation result, not an
accident of this table."* The prose reports it against the paper's own interest
(*"declared ambiguity differs by 2 executions in 600"*).

**The abstract is entirely macro-driven.** Every quantity in it is a
`numbers.tex` macro; there are no hand-typed data numerals left in it. That is
the numbers-discipline result made visible in the highest-risk paragraph.

**Claims still ahead of their evidence.** Setting §G.1 aside as pre-authorised, I
found one: `08-threats.tex:369` says the barriers *"dominate the protocol's
latency by two orders of magnitude"*, while the generated macros give
`\BarrierCost` / `\ProtocolMinusBarrier` = 1 966.7 / 28.0 = **70×**. Defensible
in log space, and already self-reported at 5C §G.7, but it is a phrase a reviewer
converts into a question (**D6**). I found nothing else overclaiming.

**Did 5C stay within polish?** Yes. 25 changed prose lines across 7 files, all
terminology, cross-references and one CI job count. No framing moved.

**The voided run's eight word-measurements: acceptable, with one caveat.** The
passage names the cell, enumerates the disagreement (ten classified against two
in the ledger, eight disagreements; siblings at ten; three log lines against
eleven), states *"We could not determine the cause"*, applies the durability
probe's own void rule, explains why both alternatives are worse ("counting it
would let a broken ground truth set a baseline's rate; discarding it quietly and
keeping the re-run would be re-running until the number looks right"), and ships
the voided attempt in the artifact. This is the right level of forensic detail
and I would not cut it. The caveat: these are hand-typed data numerals outside
the gate's reach, because voided runs are excluded from the CSVs by construction,
so nothing can drift-check them (**D8**, low).

**Identity leaks — is finding 8 the only one of its kind?** I swept the sources,
the built PDF's text, its `DocumentInfo`, and its link annotations. **The answer
is: two source locations, and nothing else.**

- `main.tex:69` (`\thanks`) and `09-artifact.tex:6` — both
  `\url{https://github.com/hafizmirhamza276-lab/Research-paper-AEP}`.
- **No acknowledgements section**, no author names, no email, no ORCID, no
  funding note. Every `acknowledg*` hit in the sweep is the technical sense
  ("durably acknowledged write").
- **PDF metadata is already clean:** `/Author` empty, `/Title` empty,
  `/Creator: LaTeX with hyperref`, `/Producer: pdfTeX-1.40.25`. No XMP.
- **But the PDF carries 4 URI link annotations** with the identifying URL (2 on
  p1, 2 on p17). An anonymous build must clear those too, not just the visible
  text — removing the `\url{}` in source does so.

---

## 4. Verdict

### 4.1 Completeness

**95%.**

Justification. The evidentiary core is sound and I could not break it: two
trilemma cells re-derive exactly from raw execution rows through to the PDF; all
six generated artifacts regenerate byte-identically; the CI gates are provably
un-weakened (0 deleted lines in `ci.yml`); the frozen bytes verify under the
hostile line-ending configuration; the harness refuses to run in two distinct
unsafe conditions; the bibliography survives spot-checking including its most
attackable entry; and every sampled claim has raw output and re-derives. The
reports disclose against their own interest repeatedly — the 5A checklist marks
item 5 **⚠️ PARTIAL — cannot be committed** rather than claiming success, and the
4B bounds finding contradicts what the prompt asked the session to write.

The missing 5% is: two confirmed open defects that must be fixed before
submission (one of them a hard blocker), one artifact-reproducibility gap that
needs the raw archive published, and a tail of low-severity items. Nothing found
threatens a measured result.

### 4.2 Defect list

Severity: **BLOCKER** = must fix before submission · **MEDIUM** = fix or disclose
before the artifact is evaluated · **LOW** = cosmetic or already disclosed.

| # | Severity | Defect | Status |
|---|---|---|---|
| **D-A** | **BLOCKER** | Anonymity conflict: `Anonymous Author(s)` shipped alongside an identifying GitHub URL at `main.tex:69` and `09-artifact.tex:6`, plus 4 URI annotations in the PDF. Register finding 8 / 5C §G.2. | **OPEN → F2** |
| **D-B** | **MEDIUM** | `06-evaluation.tex:482–483` claims a predicted half-second-per-barrier wait "is precisely what we measure", while `\BarrierCostEach{}` = 983.3 ms — a factor of 1.97. The paper states the bound *correctly* 20 lines later (":501", "up to a second away, and the protocol waits twice"), so it contradicts itself. Register finding 7 / 5C §G.1. | **OPEN → F1** |
| **D4** | MEDIUM | The two analysis figure PDFs cannot be regenerated or verified from the tracked repo; `reproduce-figures` reports `SKIPPED`. Both were modified in 5A. Disclosed in ARTIFACT.md and by the target itself. | Needs raw archive published |
| **D3** | LOW-MED | `cd experiments/results/matrix && sha256sum -c SHA256SUMS` exits **non-zero** on a fresh clone (10 of 17 entries absent). Documented with a workaround in ARTIFACT.md, but an evaluator running the obvious command sees 10 × `FAILED`. | Disclosed |
| **D6** | LOW | `08-threats.tex:369` "two orders of magnitude" is measured 70×. Self-reported at 5C §G.7. | Quantitative — human decision |
| **D9** | LOW | The three combined prompt files were unavailable, so bounds were audited against each report's *declared* scope rather than the issued prompt. A session that widened its own declared bounds would be invisible here. | Structural |
| **D1** | LOW | 5B §B states "**21 files**" for Phase P; git shows **22**. All 22 are listed in the table — an arithmetic slip, nothing undisclosed. Counting errors are a recurring failure mode in this project (cf. 4B "three counting errors"). | Report-only |
| **D2** | LOW | `check_paper_numbers.py:5` says it compares "byte for byte" and `Makefile:222` prints the verdict "byte-identical", but both normalise newlines (`read_text()` universal newlines; `tr -d '\r'`). The claim is stronger than the check. Not present in the manuscript. | Internal docs |
| **D7** | LOW | `verify_refs.py`: `zheng2026acrfence` has no `QUERIES` entry (never swept); `QUERIES` contains a Gray entry with no `refs.bib` counterpart. Plus the hollow exit code (register finding 6). Self-reported at 5C §G.3. | Disclosed |
| **D5** | LOW | `experiments/results/fsync-always/` has no `SHA256SUMS`. Self-reported at 5C §G.5. | Disclosed |
| **D8** | LOW | The voided run's ~8 hand-typed word-numerals are data numerals no gate can check (voided runs are excluded from the CSVs by construction). | Accepted as forensic detail |
| **D11** | LOW | `tab:outcomes` does not state that B0–B2 are pooled over 5 crash points against 6 for the intent-bearing systems. Semantically justified, but undisclosed in the caption. | New |
| **D10** | LOW | No independent cryptographic anchor ties the committed frozen bytes to the Phase-4 measurement session — results were untracked until 5B. Mitigated: 5A discloses the re-freeze, and its stated 3 780 executions matches the committed CSV exactly. | Structural |

**Register items confirmed:** 1 ✅ resolved · 2 ✅ resolved (verified under
`autocrlf=true`) · 3 ✅ resolved · 4 ✅ resolved · 5 ✅ resolved · 6 ✅ accurately
recorded, hollow gate confirmed, 25/25 spot-checked 6/6 · 7 ✅ open, confirmed ·
8 ✅ open, confirmed, and it **is** the only leak of its kind · 9 ✅ decision
recorded, not reverted · 10 ✅ both self-corrections present as claimed.

### 4.3 Verdict: **FIX FIRST**

Two confirmed open defects stand between this repository and submission, one of
them a hard blocker. Submission is irreversible and a desk reject on an
anonymity violation costs far more than the hours these fixes take.

Ordered fix list:

1. **F1** — rewrite `06-evaluation.tex:482–483` to claim only what the data
   supports (pre-authorised).
2. **F2** — add an `\ifanonymous` toggle; produce both PDFs (pre-authorised).
3. **F3** — record the human's decision on register finding 9 (record only).

Nothing in my own defect list qualifies for Part 2: D4/D3/D5/D7/D1/D2 fall
outside the `paper/**` scope, and D6/D11 would change or add a quantitative
claim, which the substance freeze forbids. They are referred to the human below.

### 4.4 HUMAN RESIDUAL CHECKLIST — steps only the human can do

**I must not and did not perform any of these.**

1. **Decide the anonymity policy first.** Confirm whether TSE review is
   double-anonymous for this submission. Everything else about the artifact
   pointer follows from that answer, and it interacts with (2).
2. **Decide the arXiv-vs-TSE ordering.** A public arXiv preprint makes an
   anonymised TSE submission moot. This decision precedes any upload.
3. **arXiv:** create/log into the account, upload, choose licence, confirm the
   cs.SE primary / cs.DC secondary categories in `paper/arxiv-metadata.md`.
4. **TSE:** the ScholarOne submission itself, author block, affiliations, the
   cover letter in `paper/cover-letter-tse.md`.
5. **Publish the raw results archive** (the run directories) and point `ARCHIVE`
   at it, so the two analysis figures become reproducible (**D4**) — and, if
   anonymous review applies, host an **anonymised artifact mirror** and use that
   URL.
6. **Fill in the author block** in `main.tex` for the non-anonymous build.
7. **Decide D6** ("two orders of magnitude" vs the measured 70×) and **D11**
   (whether `tab:outcomes` should state the 5-vs-6 crash-point difference) —
   both are quantitative-claim changes outside this audit's fix mandate.
8. **Confirm venue policy** on preprints, artifact badging, and whether the
   `v1.0.0-rc1` tag should become a release with a DOI.

---

*Part 1 complete. Verdict is FIX FIRST, so Part 2 proceeds under its stated
scope bounds; the fix log is appended below.*
