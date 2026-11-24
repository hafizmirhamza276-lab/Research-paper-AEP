# Phase 40 — amendment 5, the two instrument gaps, and the prepared re-run

**No live call was made.** Cumulative live spend is unchanged at
**USD 0.00154520**. The one collection run here is stub mode: 6 calls,
**USD 0.00**.

Closes the three items the stage-10 report left open, and records one defect
found while preparing the fourth.

---

## 1. Amendment 5 — the override, recorded as one

`prompts/phase-40-amendment-5-cost-criterion-2026-09-21.md`.

The author ruled that C4's two failures are a defect in the criterion rather
than a failure of the design, and overrode §9's stop rule on that basis. The
amendment states it as an **override**, not a clarification: it says plainly
that on §9's plain words the condition fired, who overrode it, and why.

**Nothing is retroactively passed.** The null stage and the retry stage each
stay `failed as written`. §9's counter for C4-as-written closes at two rather
than resetting, and any later summary of stage 10 carries both failures.

### 1.1 The replacement, and what its own known-positive did to it

C4′ has three limbs, implemented as `scripts/check_planner_cost.py` so the
criterion is run rather than read:

| limb | what it requires |
|---|---|
| **(a)** | every call ≤ §3's per-call ceiling (0.0016288 USD) **and** within the token bounds that ceiling is derived from |
| **(b)** | recorded USD reproducible by an **independent** recomputation from the transcripts, at a price whose URL and retrieval date are cited |
| **(c)** | every settle in `planner-cumulative.jsonl` ≤ 0 |

**The known-positive refuted the first draft of (a), which is the point of
having one.** The draft offered "a transcript entry with 4 000 prompt tokens"
as the fault (a) must catch. It does not catch it:

```
4 000 prompt tokens, small output   4000 × 0.20/10⁶ + 60 × 1.20/10⁶ = 0.000872
§3's per-call ceiling                                                = 0.0016288
```

**Output dominates the ceiling** — 0.0012288 of 0.0016288 is the output term —
so a prompt overrun alone does not breach the cost bound until about **8 144
tokens**, four times the cap it has already broken. A collection could run
every prompt at 3 000 tokens, pass a cost-only C4′(a) indefinitely, and §3's
model would be false throughout. So (a) gained the token bounds as a second
limb: the cost bound protects the wallet, the token bounds protect the model,
and they are not the same check.

That correction is in the amendment (`§4.1`), not applied quietly.

### 1.2 Why this matters more than it looks

`max_prompt_tokens = 2000` is **not enforced anywhere**.
`CallWrapper.attempt` uses it only to price the reservation
(`experiments/harness/planner.py:728-735`); the outbound request is bounded on
output and **not on input**. A prompt above 2 000 tokens is dispatched, billed
and recorded, and nothing before C4′(a) noticed. Amendment 4 put `last_outcome`
into every prompt, so growth is now the expected direction.

### 1.3 An honest limitation, recorded rather than left to be discovered

The reservation is priced at exactly `max_prompt × max_output`, which **is**
§3's per-call ceiling — the same number. So (c) fires at the same cost
threshold as (a)'s cost bound and never earlier, and a prompt overrun with a
small output breaches **neither** cost check. Only (a)'s token bound catches
that case. (c)'s distinct value is that it reads the **ledger** where (a) reads
the **transcript**, so the two also disagree if those records ever diverge —
which nothing else would notice. Pinned by
`test_limb_a_and_limb_c_share_a_threshold_and_that_is_recorded`.

### 1.4 The invoice check is open, not done

C4′(b) establishes that the repository is internally consistent and that its
price has a citable source. It does **not** establish that Azure charged that
price. Until the invoice or the cost-analysis blade is read, the paper may say
the cost was *computed* from vendor-reported token counts at a published rate,
and may not say it was *billed* at that rate.

### 1.5 C4′ run against real data

| collection | verdict |
|---|---|
| `phase40-live-10call-2026-09-18` (null) | **PASS**, 6 checks — with a `NOTE` that it carries no caps record |
| `phase40-live-10call-retry-2026-09-18` | **PASS**, 6 checks — same `NOTE` |
| `phase40-stub-interactive-2026-09-21` (new) | **PASS**, 7 checks — caps record present, so no `NOTE` |

A criterion nothing has ever passed is as suspect as one nothing has ever
failed. Both halves are covered.

---

## 2. The two instrument gaps, closed

### 2.1 The transcript records when the call happened — `2b51703`

Schema `aep.agent.transcript/2` → `/3`. UTC, ISO-8601, milliseconds, explicit
`Z`: `2026-09-21T07:00:31.225Z`.

Millisecond rather than second resolution because two attempts on one step can
land inside a second on a retry. A test asserts it is genuinely UTC and not
local time formatted to look like it — a local stamp matches the same regex and
is still wrong.

It is a `default_factory`, not a parameter callers pass: the entry is built in
a `finally` block reached from four outcomes, so a required argument would be
supplied on the path someone tested and missed on the one they did not, which
is how the field came to be absent.

**Replay preserves the recorded stamp rather than restamping.** A respawned
worker reads the transcript instead of calling the model (§5), so the time
belongs to the original call, not to the lifetime that re-read it.

The two archived live collections stay `/2`. They cannot be stamped after the
fact and inventing a time for them would be worse than the gap they record.

### 2.2 The ceilings in force are recorded — `021c59a`

`planner-caps.json`, written into **both** the run directory and the collection
root — both, because the per-collection call cap and the USD ceiling are
collection-wide and no single run directory can answer what bounded the
collection.

**Outside the config digest, as `docs/31` §4 requires.**
`RunConfig._body()` folds every field into `config_digest`, so a cap recorded
there would change the digest of every run and make collections incomparable
across stages. A sibling file keeps both properties.
`test_no_cap_leaks_into_the_run_config_digest` asserts the second half against
`RunConfig`'s own field names, so a cap added there later fails here.

It records the values in force, the **pre-registered ceilings beside them**,
and which were tightened — so "`stage_caps` refuses to raise a cap" is
checkable from the archive rather than asserted. Plus the price, its source URL
and retrieval date, and the derived per-call ceiling that C4′ reads.

**Concurrency.** First writer wins on the collection file, via `O_EXCL` — the
same rule the cumulative journal uses, and for the same reason: last-writer-wins
is how the counter lost 598 of 800 increments. A later run whose caps differ
records `collection_caps_differ: true` on its own record rather than raising. A
mid-collection cap change is exactly what this file exists to make visible, and
aborting the run would destroy the evidence that it happened.

---

## 3. A defect found while preparing the command — `85de573`

Not found by a test. Found by reading the launcher in order to write §5's
command.

**`scripts/run_phase40_live.sh` exported `AEP_PLANNER_MODE=live` and never set
`AEP_PLANNER_LOOP`.** Run as it stood, the stage-10 re-run would have collected
the **planned** branch — at real cost, for the whole stage — which is the exact
shape amendment 4 replaced and amendment 5 §5 commissioned the re-run to get
away from. Nothing in the output would have said so afterwards.

Closed in two halves, because either alone leaves the hole open:

1. **The launcher refuses an unset loop**, with `:?` rather than a default —
   a default is what caused this. It accepts only `interactive` or `planned`
   and echoes the choice in the banner beside the caps. Verified: with
   `AEP_PLANNER_LOOP` unset it refuses before any network call.
2. **`planner-caps.json` records the mode and the loop.** This goes slightly
   beyond the letter of "record the caps", and is flagged as such: it is the
   same class of fact — environment only, deliberately outside `RunConfig` —
   and the justification for the entire re-run is that the loop changed. A
   collection that cannot say which loop produced it cannot be compared with
   one that ran the other.

**The first version of (2) broke an invariant, and the full suite caught it.**
It read `AEP_PLANNER_MODE` and `AEP_PLANNER_LOOP` directly inside
`planner.py`, which fails
`test_planner_budget.py::test_nothing_in_this_module_reads_the_environment`.
That test exists for a specific reason, stated in its own docstring: *"No key
can be picked up implicitly; stub mode needs no `.env`."* `planner.py` is the
module that enforces the caps and the one a key would otherwise reach, so it
reads nothing ambient at all.

The fix is not to relax the test. `agent_loop` already resolves both values
from the environment, so `planner_record()` lives there and the values are
**passed down** to be recorded. `planner.py` now records what it is given and
reads nothing; an unstated branch records `null` rather than guessing
`"planned"`, because a direct construction genuinely did not state it. Three
tests hold the split: one that `agent_loop` resolves the environment, one that
`planner.py` still contains neither `os.environ` nor either variable name, and
one that an unstated branch is recorded as unstated.

The stub-interactive collection in §4 was re-run against the corrected code, so
the evidence below comes from what is committed.

---

## 4. The stub-interactive run — evidence, at zero cost

`AEP/stub-results/phase40-stub-interactive-2026-09-21/`, run end to end against
Docker and Redis under WSL2, **with the caps proposed in §5** rather than the
defaults, so the configuration that would run live was exercised for free
first.

### 4.1 The new evidence is present

| | |
|---|---|
| transcript entries | 6 |
| carrying an ISO-8601 UTC timestamp | **6 of 6** |
| schema version | `aep.agent.transcript/3` |
| example | `2026-09-21T07:00:31.225Z` |
| the 2026-09-18 run, for contrast | **0 stamped**, schema `/2` |
| caps record in the collection root | **yes** |
| caps record in each run directory | **yes, 2 of 2** |
| `collection_caps_differ` | `false` on both |
| the 2026-09-18 run, for contrast | **no caps record at all** |

The caps record reads:

```
in_force               per_run_calls 28, per_collection_calls 10,
                       per_collection_usd 0.05, max_prompt_tokens 2000,
                       max_output_tokens 1024
preregistered_ceiling  36, 1000, 20.0, 2000, 1024
tightened              per_collection_calls, per_collection_usd, per_run_calls
per_call_ceiling_usd   0.0016288
price_source           azure.microsoft.com/…/openai-service/, retrieved 2026-09-17
planner                mode=stub, loop=interactive
```

`per_collection_usd` reads 0.05 here rather than §5's proposed 0.02: the stub
run was launched before that figure was tightened, and it is left as it was
rather than re-run to make a report table tidier. Nothing in the run depends on
it — the collection cost USD 0.00.

### 4.2 The results match the previous run

Compared field by field across `summary.json`, `events.jsonl` counts,
transcript call counts and outcomes, and the void flag:

| | 2026-09-18 | 2026-09-21 |
|---|---|---|
| `AEP_FULL` crashes / declared ambiguities | 3 / 3 | **3 / 3** |
| `B0_NAIVE_RETRY` crashes / undetected duplicates | 3 / 1 | **3 / 1** |
| `agrees` both runs | true | **true** |
| cumulative | 6 calls, 2 runs, USD 0.00, 0 voided | **identical** |

**Identical on every compared field.** The two changes add records; they change
no behaviour.

---

## 5. The stage-10 re-run, prepared and NOT run

### 5.1 The caps, derived

**`AEP_PLANNER_PER_RUN_CALLS=28`** — amendment 4 §4, `(T + L) × A × W`:

| term | value | source |
|---|---|---|
| `T` turns | 3 | §1 |
| `A` attempts per decision | 2 | one call, one malformed retry — what `_ask` does |
| `L` lifetimes | 4 | `REEXECUTE_CRASHED` re-executes without re-crashing, so lifetimes ≈ executions + 1 |
| `W` workers | 2 | the collected default |

`(3 + 4) × 2 × 2 = 28`.

**A note on `W`.** The launcher runs `--workers 1`, so the same formula gives
`(3 + 4) × 2 × 1 = 14` for this collection's actual shape. **28 is not raised
to fit** — it is amendment 4's pre-registered value, and at one worker it is
simply not the binding constraint. It is carried unchanged rather than
re-derived downward, because lowering it here and restoring it later is how a
cap quietly becomes a knob.

**`AEP_PLANNER_PER_COLLECTION_CALLS=10`** — the stage is the 10-call stage.
The stub-interactive run made exactly **6** calls in this shape, so 10 leaves
four calls of headroom for a malformed retry. If the planner needs more than
that, the cap fires and the run voids, and the stage is reported as such.

**`AEP_PLANNER_PER_COLLECTION_USD=0.02`** — chosen to sit **above** the maximum
the call cap permits (`10 × 0.0016288 = 0.016288`), so the call cap always
binds first and the USD ceiling is a genuine backstop rather than the primary
control. Checked against the ordering in `attempt()`: the USD test is
`state["usd"] >= cap` evaluated before reserving, so after ten reservations
`usd = 0.016288 < 0.02` and the eleventh call is stopped by the call cap.

### 5.2 Maximum spend

| | per call | × 10 calls |
|---|---|---|
| at the current price ($0.20 / $1.20 per 1M) | 0.0016288 | **USD 0.016288** |
| at the stale price ($1.00 / $6.00 per 1M) | 0.008144 | **USD 0.081440** |

**Expected**, from the stub run's 6 calls and the retry stage's observed token
sizes (prompts 349–356 before `last_outcome`, outputs 79–249):
≈ 400 prompt + 120 output per call → `≈ 0.000224 × 6` ≈ **USD 0.0013**.

Cumulative afterwards: **≈ USD 0.0028 expected**, **≤ USD 0.0178 worst case**.
Against §9's USD 10 stop threshold and §3's USD 20 ceiling.

### 5.3 The command

Prerequisites, all verified today: both containers healthy under WSL2's native
Docker (`aep-phase2-redis72`, `aep-phase2-toxiproxy`), `aep:test-instance-marker`
set in DB 15, port 8099 free, `.env` present at `D:\personal\AEP\.env`
(outside every git work tree) with `AZURE_OPENAI_API_VERSION=2025-04-01-preview`.

```bash
wsl -d Ubuntu-24.04 -u root -e bash -c '
export PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /mnt/d/personal/AEP/Research-paper-AEP

export AEP_HARNESS_SUSPEND_DISABLED=1
export AEP_PLANNER_LOOP=interactive
export AEP_PLANNER_PER_RUN_CALLS=28
export AEP_PLANNER_PER_COLLECTION_CALLS=10
export AEP_PLANNER_PER_COLLECTION_USD=0.02

bash scripts/run_phase40_live.sh \
    /mnt/d/personal/AEP/stub-results/phase40-live-10call-interactive-2026-09-21
'
```

From Git Bash this needs `MSYS_NO_PATHCONV=1` in front of `wsl`, or the
`/mnt/...` arguments are rewritten into Windows paths before `wsl` sees them.

The results root **must not exist or must be empty** — the launcher refuses
otherwise, so that a re-run cannot resume onto a journal already holding
another stage's reservations.

### 5.4 What it would be assessed against

C1, C2, C3 and **C4′** — a **new** stage-10 attempt under amendment 5 §5, not
a continuation of either earlier collection. C4′'s §9 counter starts at zero,
and two failures of C4′ arm §9 on its plain words, with no second override.

Afterwards:

```bash
python scripts/check_planner_cost.py <results-root>
```

**This command has not been run. No cap is raised by this report and no call
is authorised by it.**

---

## 6. Verification

| | |
|---|---|
| full suite | **2 383 passed, 34 skipped** |
| `tests/test_scripted_plan_is_frozen.py` | **59 passed** — the scripted branch is untouched |
| `tests/test_last_outcome_is_arm_neutral.py` | **9 passed** — the new fields are written to disk, not into `last_outcome` |
| `tests/test_interactive_loop.py` | 14 passed |
| `tests/test_planner_cost_criterion.py` | 14 passed (8 injected faults) |
| `tests/test_transcript_timestamp.py` | 8 passed |
| `tests/test_planner_caps_recorded.py` | 19 passed |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **none**; spend unchanged at USD 0.00154520 |

### 6.1 Two environment notes

**The WSL distro and the venv had to be rebuilt** at the start of the previous
session, and there are **two Docker daemons** on this host: Docker Desktop's
and WSL2's native engine. The project's stack belongs in the WSL one
(`docs/27-measurement-host.md`, phase 10). A stack started under Docker Desktop
held port 6382 and blocked toxiproxy under WSL; it was removed. The unit suite
does not need either — it uses `fakeredis` — but the harness does.

**`.env` is still mode 777**, holding an 84-character key. The launcher notes
it and proceeds. Unchanged from the last two reports.
