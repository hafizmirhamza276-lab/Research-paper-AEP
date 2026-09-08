# AEP Paper — Handoff and Resume Guide

**7 September 2026.** Supersedes `AEP_HANDOFF_2026-09-04.md`.

---

## 0. HOW TO USE THIS FILE

Read §1 and §2, then send one prompt from §4. One bounded task per prompt
(`docs/26` §3 rule 12); a defect found outside scope is recorded as a finding,
not fixed in passing.

**Every claim in §1 and §2 was verified against the tree while writing this
file** — commits resolved, rule counts read from the source documents, section
files grepped. Nothing was carried forward from the 09-04 file on trust. Where a
section *is* carried forward (§5, §7), it says so and says what was rechecked.

**Why that paragraph exists.** Three claims in the 09-04 file were wrong by the
time they were read, and each produced a defective prompt in this session:

| 09-04 claim | Reality | Consequence |
|---|---|---|
| §3 listed **14** standing rules | `docs/26` §3 had **12** | A prompt cited "rule 13", which did not exist in the source |
| §1 described **WS-1a as in progress and load-bearing** | `74ea31f` had reverted the Option-B parts | A prompt was built on a premise the tree contradicted |
| §4 presented the **A-vs-B decision as open** | Made *and executed* at `24c0a0b` | A prompt asked for a decision already taken |

All three were **restatements that drifted from their source.** The rule-count
drift is now closed — rules 13 and 14 were added to `docs/26` §3 this session, so
the source now has 14 — but the lesson is the structural one, and it is why §3
below points at the source documents instead of copying them.

**A file-location note.** `AEP_HANDOFF_2026-09-04.md` lives in the parent
directory `D:\personal\AEP\`, *outside* the repository, which is why it was never
tracked and never reviewable in a diff. This file is committed inside the repo,
next to `AEP-HANDOVER-2026-08-31.md`.

---

## 1. WHERE THINGS STAND

### The manuscript

**Title (executed at `24c0a0b`, Option A):** *Declared Ambiguity: Fail-Closed
Execution for Non-Idempotent Legacy APIs Without Idempotency Keys.*

Agents are motivating context, not the subject. Verified by grep: §I 2
occurrences, §II 2, §VII 5 (related work, where they belong), §VIII 2, and
**zero** in §III model, §IV protocol, §V implementation, §VI evaluation, §IX
artifact. Blocker **A1 is closed by retitling**, not by an agent experiment.

`check_paper_numbers.py`: **23 passed, 0 failed.** Both PDFs build clean.

### WS-4 — complete

This is the session's substantive work and the paper's newest result.

**The instrument.** `dm-flakey drop_writes` on a loop device carrying the
harness Redis's AOF, armed at the intent CAS. Mechanism selected by the
**environment**, never by `RunConfig`, so no collected run's `config_digest`
changes. Injector `experiments/harness/write_loss.py`; provisioning, bring-up
gate, per-session self-test, and post-fault restore all in `scripts/`.

**Five collection attempts. Four failed, and every failure found a real defect** —
none was bad luck:

| # | Outcome | Defect found |
|---|---|---|
| 1–3 | failed | missing marker; stale provider; a post-fault guard that could not accept a non-killing fault |
| 4 | voided on run count alone, before any outcome was read | **R10** — the test-instance marker lived only in RAM, so a restart aborted every remaining run |
| 5 | **60/60 collected** (`252e2d3`) | two launches aborted before any run directory existed; neither counted as an attempt |

**The pre-registration `d8b2ca5` was committed and pushed before any data
existed**, and `scripts/analyse_write_loss.py` was written before any data
existed and run **unmodified**. That ordering is the only reason a refutation
reported by the person who made the prediction is worth anything.

**The result.**

| arm | executions | applied | rate | lost | undetected dupes |
|---|---|---|---|---|---|
| `AEP_FULL` | 300 | 285 | 0.9500 | **0** | **0** |
| `B3_INTENT_NO_BARRIER` | 300 | 287 | 0.9567 | 0 | **0** |

**Verdict: REFUTED on the numbers, with `SILENT_APPEND_FAILURE` observed** — the
third of three Redis behaviours `d8b2ca5` enumerated in advance, and the one it
flagged as *"would complicate the reading"*.

### The finding, stated plainly

> **`WAITAOF` returned success 300 times out of 300 for durability
> acknowledgements requested *after* block-level write loss had already made the
> append impossible.**

300 false acknowledgements out of 300. `drop_writes` discards each write bio and
reports success, so the kernel sees no error, `fsync(2)` succeeds, and Redis has
no way to learn otherwise. The barrier withholds dispatch on a **failed or
absent** acknowledgement; it was handed a successful one and dispatched —
behaving exactly as specified on an input that was false.

**This cell is evidence about Redis, not about the protocol.** It does **not**
show the barrier fails to withhold under write loss: the condition the cell
exists to test was never reached. It does **not** show it works. It shows that
the protocol's guarantee is only as good as the acknowledgement it rests on, and
bounds that guarantee to storage which reports its own failures. One host, Redis
7.2.5, `appendfsync everysec`, claimed for no other.

Both pre-registered *exact* quantities held: `lost_effect_executions = 0` for
AEP-full, `undetected_duplicate_applications = 0` for both arms.

Written up in `reports/phase-report-14-write-loss-2026-09-07.md`; §VIII updated
at `561be06` (the old *"we have not done it"* sentence is gone).

### What the failures produced — none of it in any plan

Every one of these came out of a failure, not a roadmap:

- **`docs/25` R8a** — a teardown following a *failure* preserves the container first
- **`docs/25` R8b** — return the stack to the base compose file *before* unmounting
- **`docs/25` R10** — the write-loss marker lived only in RAM (closed by `a994023`)
- **`docs/25` R11** — the 2026-09-04 dates on several WS-4 artefacts are wrong; files deliberately *not* renamed, because `d8b2ca5` is cited by commit
- **`docs/25` R12** — orphaned provider processes on 8099 survive teardown
- **`docs/25` R12a** — unexplained post-collection container restarts, recorded and not chased
- **`docs/25` R13** — a scanner that cannot tell zero from one is worse than no scanner
- **`docs/26` §3 rule 13** — a gate that cannot fail is decoration
- **`docs/26` §3 rule 14** — a load-bearing script lives in `scripts/` with a test

### Also closed this session

- **The `/PTEX.FileName` leak in the anonymous build** (`309c4e5`). pdfTeX
  embedded absolute figure paths carrying the repository name, which resolves by
  search to the author's GitHub account — in neither the text layer nor DocInfo,
  so `pdftotext` and `pdfinfo` both missed it. Fixed with
  `\pdfsuppressptexinfo=-1` and `\pdfinfoomitdate=1`, scoped to the anonymous
  build. `check_paper_numbers.py` now gates the anonymous PDF on staleness,
  build paths, DocInfo and byline, and `scripts/prove_anonymous_gate.sh` shows
  all four checks failing on a deliberately reintroduced leak.
- **Both WS-4 findings** (`856d78a`). The per-run column read a key from the
  wrong file and printed thirty zeros under a total of 285; the regime label said
  `redis-kill-preack` for a write-loss cell. Both fixed, **the verdict re-derived
  unchanged**, and all five generated tables byte-identical.
- **The `numbers.tex` freeze question settled on evidence** (`8a6186a`): the
  Stage-2 freeze in the untracked `CLAUDE.md` is scoped to another branch in
  another working copy, and fourteen commits on `main` have staged `numbers.tex`
  since `c2fffa6`.

---

## 2. WHAT REMAINS

Verified against the tree, not carried over. WS-1b is gone from the table
entirely: Option A was executed, so there is no agent workload to build.

| Workstream | Status | Est. |
|---|---|---|
| WS-0 host | ✅ | — |
| WS-1 blocker A1 | ✅ **closed by Option A** (`24c0a0b`) | — |
| WS-1a attribution | ✅ **superseded** — Option-B parts reverted at `74ea31f`; correctness fixes kept | — |
| WS-3 prevention | ✅ | — |
| **WS-4 write-loss** | ✅ **complete** (`252e2d3`, `1d13868`, `561be06`, `856d78a`) | — |
| WS-2 archive | 🟡 DOI at submission | ~1 day |
| WS-5 stats power + remaining cells | ⬜ | 2–3 days |
| WS-6 real Temporal baseline | ⬜ | 3–5 days |
| WS-7 TLA+ model | ⬜ | 3–4 days |
| WS-8 related work 34 → 65+ refs | ⬜ | 2–3 days |
| WS-9 manuscript rewrite (21 → 16 pages, tone, AI disclosure) | ⬜ | 4–5 days |
| WS-10 audit + arXiv + submit | ⬜ | 2–3 days |

### Blocker status (`docs/26` §2)

- **A1** — **CLOSED.** Retitled at `24c0a0b`; agents are motivating context.
- **A2** — 80% closed. Archive built and verified; DOI deferred by decision.
- **A3** — **CLOSED** by Phase 13.
- **A4** (single host, WSL2) — **half closed** and will be written as a
  limitation. WS-4 sharpened this rather than closing it: fault delivery on this
  host is now *demonstrated reliable* for a full 60-run session, but the host
  still shows unexplained container lifecycle events (§7).

---

## 3. STANDING RULES

**Do not restate them here.** Restating them is exactly how the 09-04 file came
to list fourteen rules against a source that had twelve, and how a prompt came to
cite a rule that did not exist.

- **Project rules: `docs/26` §3.** Currently **14** rules, 1–14. Read them there.
- **Collection tooling rules: `docs/25`.** Currently **R1–R13**, including
  **R8a**, **R8b** and **R12a**. Read them there.

If a rule needs changing, change it in the source document in its own
documentation pass, and let this file keep pointing at it.

---

## 4. PROMPTS TO RESUME — copy one at a time

Carried forward from the 09-04 file's §5 **with prompts 1–4 deleted**: 1 and 2
(finish WS-1a, clean docs/33) are superseded by the Option-A revert, 3 was
gated on a decision already executed, and 4 (WS-4) is complete. The five below
were re-read against the tree; their premises still hold.

### Prompt 1 — WS-5, statistical power and the remaining cells

> Assess the statistical power of the existing cells and collect what is
> missing. Pre-register before collecting (`docs/26` §3 rule 5): hypotheses, run
> counts, unit of analysis (rule 6), stopping rule, and the exact analysis
> command, committed and pushed before any data exists. Report power as it comes
> out, including if it says the existing n is inadequate.

### Prompt 2 — WS-6, real Temporal baseline

> B4 shares one mechanism with Temporal and §VIII already says it is not
> Temporal. Build a real Temporal baseline, or state with evidence why it cannot
> be built on this host and make that the recorded answer. Do not weaken §VIII's
> existing sentence before there is a result to replace it with.

### Prompt 3 — WS-7, TLA+ model

> Model the protocol's safety property in TLA+ and check it. The model is
> evidence about the *specification*, not the implementation — say so where it
> is reported, and do not let it be read as verifying the code.

### Prompt 4 — WS-8, related work

> Expand related work from 34 to 65+ references. Every citation must resolve;
> `scripts/validate_citations.py` must pass. Do not pad — a reference that is
> not engaged with in the prose is not a reference.

### Prompt 5 — WS-9, the rewrite

> Cut the manuscript from 21 pages to 16. Tone per `docs/26` §3 rule 11: honest
> and precise, never apologetic; scope stated once, in limitations. Add the AI
> disclosure. Regenerate macros, never hand-edit `paper/generated/**`.

### Prompt 6 — WS-10, submission

> Final audit, arXiv, submit. §VIII's residual limitations must match what the
> evidence supports. The anonymous build is now gated by
> `check_paper_numbers.py` — but note §7: the **public** `main.pdf` still carries
> the absolute-path strings, which is correct today and must be re-decided if the
> public PDF is ever what gets submitted for review.

---

## 5. OPERATIONAL NOTES

Carried forward from the 09-04 file's §6. **Rechecked:** the credential,
lock-file, `nohup setsid`, sleep, test-suite-safety and corporate-laptop notes
all still hold; the "unpushed commits" note is superseded — see §6.

- **If a push hangs, retry once with a longer window before hunting anything.**
  Updated 8 September. A push of 981 objects timed out at 180 s, and the
  off-screen-credential diagnosis below did **not** apply: no
  `git-remote-https.exe`, no other git process, and no `.git/index.lock`. A
  plain retry at 540 s completed normally, and only 343 KiB actually
  transferred — so the stall was in the connection/auth phase, not the transfer,
  and nothing needed to be found or killed. Check for a stalled process and a
  lock file *after* a retry fails, not before.
- **Git credential dialog opens off-screen.** Cost 3h17m once, with a stalled
  `git-remote-https.exe` holding `.git/index.lock`. If git hangs *and a retry
  did not clear it*, look for a hidden account-selection window. The account is
  **`hafizmirhamza276-lab`**.
- **Never delete `.git/index.lock` while git processes are alive.** Kill them,
  confirm gone, verify the lock is 0 bytes, remove, then `git fsck`. This
  recurred this session; the lock was stale and no git process existed in either
  WSL or Windows, which is what made removal safe.
- **Long collections must be launched with `nohup setsid`**, `< /dev/null`.
- **Laptop must not sleep during collection**; never `wsl --shutdown`.
- **Never run the test suite against a Redis a matrix is collecting on.**
- **Never change any TLS, proxy, certificate, antivirus or git network setting.**
  Managed corporate laptop.
- **Per-run cost, write-loss regime: 61.4 s/run** (3687 s for 60 runs) against
  the pre-registration's untested 64.5 s estimate. No constant was edited.

### New this session

- **The WSL bridge strips `$` and mangles arguments, and it caught me three
  times in this session alone** — a `$D` that vanished so a `cp` wrote to `/`, a
  `$R` that turned `find $R` into a search of the working directory and reported
  a meaningless zero, and a `$P` that produced empty filenames in a leak count.
  The 09-04 file already recorded this and it still was not enough.
  **The rule is not "be careful": run anything whose result matters from a
  script file.** Inline `wsl -- bash -lc '...'` is for output you will read with
  your own eyes, never for a value a decision turns on.
- **Nested quoting through the bridge fails differently**: `bash -lc "... $(...)
  ..."` with inner double quotes produces a syntax error rather than a wrong
  answer. That one is safe because it is loud.
- **The checking-code pattern** (`856d78a` §3, and the report it points to).
  Three times this session a rule was broken *inside the fix for that rule*: a
  leak scanner that could not tell zero from one, whose replacement regex then
  reported every empty field as populated; a rule-13 proof that asserted on a
  re-run rather than on the output it had just shown; and a verification script
  that compared two greps with different patterns and reported a difference that
  did not exist. **What they share is that the checking code was held to a lower
  standard than the code it checked.** In all three cases the defect surfaced
  only because a result looked wrong against something already known by hand —
  never because the instrument caught it. Give the verification of a fix the
  same failing-branch proof the fix's own gate gets.
- **Void on the run count alone.** Attempt 4 was voided before any outcome was
  inspected. Keep doing this; it is what makes a void decision defensible.

---

## 6. UNCOMMITTED / UNTRACKED AT HANDOFF

**Everything is pushed. `origin/main..HEAD` is empty** — this supersedes the
09-04 file's "13–14 unpushed commits". 25 commits were made this session, ending
at `856d78a`.

Four files are untracked and were untracked before any of this work began. They
are **not ours to commit**, and one of them is actively misleading:

- `CLAUDE.md` — a Stage-3 protocol for a *different* working copy
  (`/root/aep-stage3`), saved into this repo root by accident. Its
  `numbers.tex` freeze does **not** apply here; see `8a6186a` and
  `reports/raw/ws4-freeze-and-anon-check-2026-09-07.md` §1.
- `main.bbl`, `phase8-driver/.build_keep.sh`
- `reports/raw/phase13-armA-s3-VOIDED-killed-at-152.txt`

`macro-scratch/` is **outside the repository** and is not committed. Anything
load-bearing has been promoted to `scripts/` (rule 14) — most recently
`prove_anonymous_gate.sh`. If you find a number quoted from a scratch script,
promote it.

---

## 7. OPEN QUESTIONS CARRIED FORWARD

Rechecked; all six from the 09-04 file are still open and none has been acted on.

- Four §VI paragraphs still span an UNDETERMINED `results_root` backing (all
  `b2-*-2026-08-21`, including the `\UnwantedPrevented` paragraph). Recorded in
  `docs/28`; no manuscript action taken.
- Four controlled acks in Arm A came in faster than *any* of the 143
  uncontrolled acks (three under 7.5 ms against a 29.3 ms minimum). n=4; not
  decidable from collected data.
- 2–3 runs per `NO_READBACK` cell did not apply, in **both** arms of the
  in-flight variant. Not a difference between arms, so it does not touch the
  tie, but unexplained.
- `issue_to_return_ns` times the injector call, not the death, so the in-situ
  landing is an upper bound. Only the "≥106 runs alive past 368 ms" figure is
  model-free.
- §VIII-A(e) still carries the `ClassPp` underpowered-comparison discussion from
  Phase 8.4/8.5. Arm A does not supersede it (different quantity), but it reads
  oddly next to the new material.
- `docs/30` §4 says the fsync mechanism "is not adopted without an explicit
  decision" — that decision now exists (Arm B cancelled) but the doc does not
  cross-reference it.

### New, from this session

- **What sent the SIGTERM in attempt 4?** Bounded, not solved
  (`reports/raw/ws4-sigterm-bound-2026-09-07.md`). An identical
  provision-and-bring-up cycle with observers running from before provisioning
  did **not** reproduce it, so it is not a deterministic consequence of
  bring-up. Origin unestablished. What removed it as a blocker was making the
  marker durable (`a994023`), not explaining it.
- **Post-collection container restarts.** `docs/25` R12a. Third occurrence of
  the same unexplained-lifecycle class. It did **not** touch the data — the
  newest file under the results root is `matrix-progress.jsonl`, written at the
  instant `run_matrix` returned 0, and `coordinator_restarted_unexpectedly` is
  `False` in all 60 rows. Deliberately not chased; recorded so a fourth
  occurrence is met as a pattern.
- **Two `VOID_WORKER_NEVER_READY` runs in the B5 primary session, unexplained.**
  Added 8 September, from `0c6bcf4`. Sequence positions 10 and 21, **both in the
  first cell** (`B5_TEMPORAL` / `ledger_postings`), both with an **empty
  `worker.err`** — so the worker left no traceback; it simply did not signal
  ready inside the spawn window, and `collect.py` retries once before voiding.
  **Attempt 1 produced none in its 39 runs**, under the same provider
  configuration, which is what makes it worth recording rather than shrugging
  at. The gate excluded both from every rate and reported them with counts, so
  no number rests on them, and 2/120 breaches no pre-registered rule.
  **Deliberately not chased** — recorded so a recurrence is met as a pattern,
  the same treatment `docs/25` R12a gives the container-lifecycle events.

- **`/PTEX.FileName` is still in the public `main.pdf`.** Absolute build paths
  carrying the repository name remain in `main.pdf` and are *not* a defect there
  — the public PDF is not anonymous. But it is a decision, not an accident, and
  it must be re-taken if the public PDF ever becomes the review artefact. The
  anonymous build is fixed and gated; the public one is deliberately untouched.
