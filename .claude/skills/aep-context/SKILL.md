---
name: aep-context
description: Canonical ground truth for the Agent Execution Protocol (AEP) — its purpose, topology (single self-hosted Redis), and the three hard invariants (Timeout, CAS fencing, Fail-Closed). Consult before any AEP design, coding, testing, or review task.
---

# AEP — Agent Execution Protocol

AEP is a protocol for safely coordinating autonomous agent execution against shared state on a **single self-hosted Redis instance**. It does not assume Redis HA / failover. Its safety claims must hold given that topology — meaning the real, honest guarantee is **"corruption / contention is detectable and the system fails closed,"** not "absolute atomicity across failover."

Use this skill as the canonical source of truth for what AEP is. For the full specification, **read `references/brief.md`** before doing any deep design, implementation, testing, or review work. Do this every time the orchestrator delegates a non-trivial unit of work to you.

## The three hard invariants

State each verbatim where relevant in your deliverables.

1. **Timeout Invariant**
   - `T_client <= T_lock - Buffer`, where `Buffer >= 15s`.
   - The client-side timeout for any operation under a lock must complete strictly before the lock TTL minus the safety buffer. The buffer covers clock skew, network jitter, and renewal latency.

2. **CAS Fencing Invariant**
   - State updates happen **only** via an atomic monotonic-integer compare-and-swap, **never** via raw `SET`.
   - Random tokens (e.g., the lock-ownership token from `secrets`) are **ownership** tokens — they prove *who* holds the lock. They are **NOT** fencing tokens. The fencing token is the monotonic integer.
   - A write with a non-increasing version is rejected as `StaleWriteError`. A write that finds the stored payload corrupt is rejected as `StateCorruptionError` with no overwrite.

3. **Fail-Closed Invariant**
   - On corruption, ambiguity, or a hit on a safety cap (e.g., the lease-cap ceiling): **stop, fence, escalate. Never guess.**
   - A corrupt payload is quarantined, not silently rewritten. An `ABOUT_TO_FIRE` intent is never auto-retried. A capped lease that hits its ceiling stops renewing and the lock is allowed to expire.

## Honest-guarantee rule

Never claim "absolute atomicity," "split-brain impossible," "exactly-once," or any equivalent on a **single Redis instance**. The honest guarantee is:

> **Corruption and contention are detectable, and the system fails closed.**

This rule binds every agent in the pipeline. Reports, designs, code comments, and security findings must use the honest phrasing.

## Full spec

See `references/brief.md` for the full AEP implementation brief — schemas, module contracts, Lua scripts, lock lifecycle, lease behavior, testing matrix, and rationale. Read it before any deep work.
