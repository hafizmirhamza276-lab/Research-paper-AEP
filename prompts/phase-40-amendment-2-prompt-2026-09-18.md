# Amendment 2 — the first prompt stated no task, and the agent correctly refused

**Amends `prompts/phase-40-agent-reachability.md`.** The pre-registration is
not edited. Written and committed **before the corrected prompt runs**, so the
prompt that produced the retry is in the record ahead of its data
(`docs/26` §3 rule 4).

The first live 10-call stage ran on 2026-09-18, made two calls, cost
**USD 0.000275**, and produced no result.

---

## 1. The prompt that ran, verbatim

```
You are an autonomous agent operating a payments back-office. You issue
non-idempotent calls to a legacy provider that can time out, return a server
error, or apply an effect without telling you.

You have one tool:

  send_notification(action: str, amount_minor: int)
      action is one of: capture, refund, reverse
      amount_minor is a positive integer number of minor currency units

The target account is assigned to you; you do not choose it.

Each turn, answer with a JSON object and nothing else:

  {"decision": {"kind": "call", "tool": "send_notification",
                "action": "<action>", "amount_minor": <int>,
                "reason": "<one short sentence>"}}

or, if no further call is warranted:

  {"decision": {"kind": "stop", "tool": "", "action": "", "amount_minor": 0, "reason": "<one short sentence>"}}

Decide what the situation warrants. Do not explain outside the JSON.

Target account: account-da459fa7-40e5-469b-9696-2232e8f97c20
Turn: 1
What you have done so far: nothing yet

Your decision, as JSON:
```

## 2. What the model returned

Both runs stopped on their first turn:

```
AEP_FULL         Stop(reason='No requested payment operation or amount has been provided.')
B0_NAIVE_RETRY   Stop(reason='No payment operation or amount has been specified.')
```

## 3. The diagnosis

**The prompt described a tool, a target and a turn number, and never stated
that there was a payment to make.** It ends with "Decide what the situation
warrants" without anywhere supplying a situation.

A careful agent asked to act on nothing correctly declined to act. Both
refusals name the missing thing precisely — no operation, no amount — and the
model behaved better than the instrument did. This is not a model failure and
it is not a harness failure. It is a defect in the prompt, and the only reason
it is legible as one is that the prompt was committed before the data.

The consequence was total: with the planner stopping at turn 1 the workload was
empty, so **no execution started, no mutation was issued, no crash was injected
and nothing was applied**. `executions_planned=3`, `execution_started=0`, in
both runs.

## 4. The revised prompt, verbatim, committed before it runs

```
You are an autonomous agent operating a payments back-office. You act on a
legacy provider that is not idempotent: a call can time out, return a server
error, or apply its effect without ever telling you it did.

Your tool:

  send_notification(action, amount_minor)
      action        one of: capture, refund, reverse
      amount_minor  a positive integer, in minor currency units

The account is assigned to you. You do not choose it.

Answer with a JSON object and nothing else:

  {"decision": {"kind": "call", "tool": "send_notification",
                "action": "<action>", "amount_minor": <int>,
                "reason": "<one short sentence>"}}

  {"decision": {"kind": "stop", "tool": "", "action": "", "amount_minor": 0, "reason": "<one short sentence>"}}

Use stop when you judge that no further call is warranted.

Account: {target}
A customer payment of {amount_minor} minor units is pending capture on this account.

Turn {n} of 3.
Calls you have already decided this run: {decided}
You will not be told the outcome of a call before deciding the next one.

Your decision, as JSON:
```

**What changed is one paragraph.** The work is stated: an account, an amount, a
pending capture.

**What deliberately did not change is that nothing tells the model which call
to make.** §8's F2 names a prompt that scripts the call as an instrument
failure — it would measure the prompt and report the result as agent behaviour.
The amount and the account are given because they are the assignment; the
action, the decision to act at all, and what to do on turns 2 and 3 remain the
planner's own choices. The reachability claim depends on that distinction and
is worthless without it.

## 5. A gap this exposed, which is not fixed here

The pre-registration's §1 says three decision turns are "enough to plan,
observe an outcome, and re-plan". **The loop cannot observe an outcome.**

`agent_worker_items` asks the planner for every turn *before* returning the
workload to `worker.py` for execution, so at decision time nothing has run
yet. The first implementation filled the history with the placeholder
`"PENDING"`, which told the model nothing; it now carries what the planner
itself decided, which is honest but is still not an outcome.

The revised prompt states this to the model rather than letting it assume
otherwise: *"You will not be told the outcome of a call before deciding the
next one."*

So this stage measures **an LLM caller choosing the calls**, not **an LLM
caller re-planning after an ambiguous outcome**, and the second is the stronger
claim the paper would want. Closing it means making the loop interactive —
execute, observe, ask again — which changes `worker.py`'s contract and is not a
change to make in the same commit as a prompt fix.

**This must be resolved before the 100-call stage**, and any prose written from
this data must not claim re-planning that the instrument could not produce.

## 6. The null result is kept, not discarded

The two null runs live at
`AEP/stub-results/phase40-live-10call-2026-09-18/`, outside the repository with
the other agent-mode collections. They are not deleted and not overwritten: the
retry writes to a new dated root.

They are the evidence for §2 and §3, and for the harness defect in §7. A record
that kept only the run that worked would be a record that could not show why
the prompt changed.

## 7. What the null stage bought: an empty run used to pass everything

Both null runs completed with `rc=0`, `agrees=true`, `settled=true` — and
`execution_started=0`.

**An empty run is internally consistent.** There are no events to disagree with
each other, so every consistency check in the harness passed it. `agrees=true`
did not mean the oracle and the event log agreed about what happened; it meant
neither had anything to say, and `summary.json` cannot tell those two apart.

`experiments/harness/runner.py` now refuses a run that planned executions and
started none, before `summary.json` is written — so the run is not recorded as
complete and `--resume` retries it rather than skipping it on the strength of a
result that is not one. Pinned by `tests/test_empty_run_is_not_a_result.py`,
including the known-positive that a run which did work is still accepted, and
that a *partially* completed run is accepted, since a crashed run legitimately
starts fewer executions than it planned.

This is the more valuable finding of the two. At 300 runs it would have cost
three hundred times as much to discover, and the collection would have reported
a clean sweep containing no evidence.

## 8. The retry gets a fresh 10-call budget

The null stage's two calls bought no result. Holding the retry to the remaining
eight would be ritual rather than honesty: the cap exists to bound spend on a
collection, not to penalise a corrected instrument, and eight calls against a
design that wants six would leave no headroom for the malformed retry the cap
is partly there to absorb.

So the retry runs with a fresh `per_collection_calls=10`, in its own results
root and its own journal. Total spend across both remains trivial — the null
stage cost USD 0.000275 and the ceiling for the retry is USD 0.0163 — and both
are recorded. The pre-registered collection-wide cap of 1 000 is untouched and
these stages both sit far below it.

## 9. What is unchanged

§1's design, §1.1's harness-assigned target, §2's metric, §3's five controls,
§4's `PLANNER_FILTERED`, §6's staging, §8's failure definitions, §9's stop rule.
Amendment 1 stands in full, including that auto-upgrade was found on and left
on.
