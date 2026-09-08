# WS-6 was not collected: there is no B5 collection path

**No data was collected, and none could be.** The stack was not brought up, no
image was pulled, and nothing was run against a provider. The two things that
were asked for *before* collection were done and committed first, in order:
prompt provenance (`d096f47`) and the Start-To-Close decision (`06d51b0`).

---

## The blocker

`analyse_b5_agreement.py` reads `b5-runs.jsonl`, one record per B5 run carrying
its system, crash point, response class, gate verdict, executions, and the
oracle-derived outcomes. **Nothing produces that file, and no path exists that
could.** Verified rather than assumed:

| check | result |
|---|---|
| `B5` / `TEMPORAL` in `experiments/baselines/contract.py` (`SystemId`) | **absent** |
| occurrences of `B5` in `experiments/run_matrix.py` | **0** |
| anything writing `b5-runs.jsonl` | only the reader and its test |
| `probe_open_questions.py`, first line | *"Not a collection. Nothing here writes a run directory"* |

The probe runs one workflow at a time and reports whether a crash point was
reached. It has no cell matrix, no run directories, no session root, and — the
substantive gap — **no oracle attribution**. `undetected_duplicate_applications`
and `lost_effect_executions` are not properties of a workflow result; they come
from reconciling the provider's ground-truth ledger against what the system
recorded, which is what `experiments/mock_api` plus `analyze.py` do for every
other arm and what nothing does for B5.

## This is my error, and I should name it precisely

My report for the previous prompt ended *"WS-6 is ready to collect."* That was
wrong. Every one of the five **pre-registered open questions** was genuinely
closed — digests, sandbox, both gates proven in both directions, all five crash
points demonstrated, retry-lands, the deadline — and I treated that as equivalent
to the instrument existing. It is not. The open questions were about *whether the
engine can be measured*; the instrument is *what does the measuring*.

The evidence was in front of me the whole time: I wrote the line "Not a
collection" at the top of the probe myself, four passes ago.

**It is the same shape as the four rule-inside-its-own-scope failures already
recorded** — R13 broken by its own proof script, R14 twice by this probe, R1 by
the probe's cleanup — and it is the fifth. The through-line `docs/25` R14 names
is that supporting work is held to a lower standard than the work it supports.
Here it was the *readiness claim* rather than a checker: a summary sentence
asserting a state of the world that one `grep` would have refuted, written at the
end of a pass where everything else had been verified.

## Why I did not build the runner in this pass and collect anyway

Three reasons, and the first is sufficient.

1. **A collection harness built in the same pass that runs it has no gate.** The
   two B5 gates exist because instrument failure was invisible twice, and both
   were proven able to fail before being trusted. A runner written and used
   inside one pass gets neither treatment, and its first output would be 360
   runs nobody could distinguish from correct.
2. **The oracle attribution is the hard part, and it is where the confound
   lives.** B4's rates come from the provider ledger via the shared reconciler.
   If B5's came from anywhere else — the workflow result, the engine's history —
   the two arms would be measuring different things, and an agreement or
   disagreement between them would be an artefact of the attribution rather than
   of the engines. That is the exact confound WS-6 exists to remove, and it is
   worth a pass of its own.
3. **The pre-registered stopping rule assumes a session that can be voided on
   run count.** With no run directories there is no run count to void on, and
   the instruction's own instruction — *"any decision to void the session must
   rest on those alone"* — has nothing to rest on.

## What collecting WS-6 actually needs

Stated concretely so the next pass is bounded, not open-ended:

1. **`SystemId.B5_TEMPORAL` and `B5B_TEMPORAL_AT_MOST_ONCE`** in
   `experiments/baselines/contract.py`, and the `ROADMAP_TO_BASELINE` entry in
   `experiments/baselines/crash_points.py` mapping `after_intent_before_barrier`
   to `None` so `run_matrix` records it `not_applicable` — the mechanism that
   already exists for B0/B1/B2 and that `B5_SEMANTICS.md` §2.3 depends on.
2. **A B5 regime** in `run_matrix.py`, alongside `REGIME_WRITE_LOSS_PREACK`,
   carrying 30 runs × 10 executions and the two arms. The frozen regimes are not
   modified.
3. **A B5 run driver** that, per run, provisions the mock provider with its own
   ledger, starts the supervisor, drives 10 executions, applies `gate.classify`,
   and writes a run directory plus one `b5-runs.jsonl` line.
4. **Oracle attribution for B5**, reusing the existing reconciler rather than a
   parallel one, so B5's `undetected_duplicate_applications` means exactly what
   B4's does.
5. **A gate proof for the driver**, both branches, before it is trusted — the
   standard the injector gate and the supervisor gate were each held to.

The Start-To-Close value is already fixed at **4000 ms** (`06d51b0`) and does not
need revisiting; it was the last free *parameter*, which is a different thing
from the last missing *component*.

## What was done in this pass

* **Rule 4 satisfied before anything else** (`d096f47`): WS-6's six prompts
  verbatim in `prompts/phase-15-b5-temporal.md`, including the collection prompt;
  the WS-4 tail added to phase-14 in condensed form with elisions marked and the
  reason given. The correction above is recorded there alongside the prompt whose
  premise it refutes, not silently applied.
* **The Start-To-Close choice fixed and committed before any run** (`06d51b0`),
  with the measurements, the rejection of 2500 ms *because* it was the value that
  produced a duplicate, and what conditioning on a timer B4 does not have costs
  the comparison.

Nothing else was touched. The paper is untouched, no stack was raised, no test
was run against anything, and `analyse_b5_agreement.py` was not run — there is
nothing for it to read.

## Status

| | |
|---|---|
| WS-6 collection | **NOT RUN** — no B5 collection path exists |
| Prompts (rule 4) | committed, `d096f47` |
| Start-To-Close | fixed at 4000 ms, committed, `06d51b0` |
| Pre-registration `1fecb1f` | unchanged |
| Frozen results | untouched |
| Paper | untouched |

**The correction stands on the record**: WS-6 was not ready to collect when I
said it was, and it is not ready now. It needs the five components above, and
each of the two that touch measurement needs a gate proven able to fail before
any of it is believed.
