# AEP Multi-Agent Build Pipeline

This repository is scaffolded for a **multi-agent build pipeline** that constructs the **Agent Execution Protocol (AEP)** end-to-end: high-level design → technical design → implementation → adversarial testing → security review. The orchestrator runs the entire pipeline as a scored, gated, self-correcting loop on the main thread.

## Launching

```
claude --agent aep-orchestrator
```

Then, in the session, say:

> Build AEP per the aep-context skill, starting at Phase 1.

The canonical AEP specification lives at `.claude/skills/aep-context/references/brief.md` (copied from `AEP_IMPLEMENTATION_BRIEF.md`). Update that file if the spec changes — every agent reads it.

## Roles and pinned models

| Agent              | Role                                                             | Model ID                       |
|--------------------|------------------------------------------------------------------|--------------------------------|
| `aep-orchestrator` | Main-thread orchestrator (loop, scoring, retry, escalation, swap) | `claude-opus-4-7`              |
| `hld-designer`     | First-pass HLD + test-case enumeration (writer in Phase 4)        | `claude-haiku-4-5-20251001`    |
| `tech-designer`    | Technical design + default security reviewer (Phase 5)            | `claude-sonnet-4-6`            |
| `implementer`      | Implementation + default test runner (Phase 4)                    | `claude-sonnet-4-6`            |
| `opus-fixer`       | Two-strike escalation + swap-role worker (Phases 4 and 5)         | `claude-opus-4-7`              |

The orchestrator restricts which subagents it may spawn via its frontmatter `tools: Agent(hld-designer, tech-designer, implementer, opus-fixer)`.

## Phase state machine

```
Phase 1  HLD            -> hld-designer            -> score >=9 ? save docs/01-hld.md : retry
Phase 2  Tech Design    -> tech-designer           -> score >=9 ? save docs/02-tech-design.md : retry
Phase 3  Implementation -> implementer             -> score >=9 ? save docs/03-impl-report.md : retry
Phase 4  Testing        -> WRITE: hld-designer + RUN: implementer
                           score >=9 ? save docs/04-test-report.md : SWAP
                           SWAP -> WRITE: implementer + RUN: opus-fixer (writes docs/04-test-report.md)
Phase 5  Security       -> tech-designer
                           score >=9 ? save docs/05-security-report.md : SWAP
                           SWAP -> opus-fixer (writes docs/05-security-report.md)
```

## The ≥9 approval gate and two-strike escalation

- Every phase ends with the orchestrator scoring the subagent's report on five dimensions (Correctness, Completeness, Robustness, Clarity, Honesty), each 1–10, per the `aep-scoring-rubric` skill.
- A phase passes only if **every** dimension scores **≥9**.
- On reject: the orchestrator writes explicit feedback and re-delegates to the **same** agent.
- **Two-strike rule:** if the same agent fails the gate twice on the same unit of work, the orchestrator escalates to `opus-fixer` with all accumulated feedback.

## Role swaps (Phases 4 and 5)

- **Phase 4 (Testing):** default writer is `hld-designer`, default runner is `implementer`. On reject, the orchestrator swaps to writer = `implementer`, runner = `opus-fixer`, with `opus-fixer` producing a polished `docs/04-test-report.md`.
- **Phase 5 (Security):** default reviewer is `tech-designer` (independent from the implementer). On reject, the orchestrator swaps to `opus-fixer`, which produces `docs/05-security-report.md`.

Every delegation, score, reject, escalation, and swap is appended to `docs/build-log.md` with timestamps.

## Where reports land

- `docs/01-hld.md` — approved high-level design
- `docs/02-tech-design.md` — approved technical design
- `docs/03-impl-report.md` — implementation report (the actual source lives under `src/`)
- `docs/04-test-report.md` — adversarial test results
- `docs/05-security-report.md` — security review findings + remediation
- `docs/build-log.md` — append-only audit trail of every delegation, score, retry, swap, and escalation

## Platform caveats

- **Subagents cannot spawn subagents.** That is why the orchestrator runs on the **main thread**. All loop / score / retry / escalate / swap logic lives in its system prompt and is executed by it.
- **The ≥9 gate is rubric-based judgment, not a runtime certification.** It is the orchestrator's score against the rubric, not a guarantee enforced outside the LLM.
- **Honest guarantees only.** AEP runs against a **single self-hosted Redis instance**. The honest claim is *"corruption / contention is detectable and the system fails closed,"* not "absolute atomicity" or "split-brain impossible." This phrasing must appear consistently across designs, code, tests, and findings.
- **Cost discipline.** `opus-fixer` is reserved for the two-strike escalation path and the role-swap worker. The orchestrator should not escalate prematurely.

## Optional hardening (later)

Convert the ≥9 gate from rubric-based judgment into a real, deterministic gate by adding a `SubagentStop` hook that runs a scoring script and blocks progression on a sub-threshold result.
