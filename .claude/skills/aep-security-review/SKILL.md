---
name: aep-security-review
description: Security & vulnerability checklist for AEP — lock safety, injection, secrets, DoS, data integrity, and recovery safety.
---

# AEP security review checklist

The security reviewer audits the AEP implementation against the categories below. Each finding is rated **Critical / High / Medium / Low**. The reviewer must be **independent** of the code author wherever possible (in the default pipeline, this is `tech-designer`; on swap, it is `opus-fixer`).

## Categories

### 1. Distributed-lock safety
- Single-instance Redis is a **SPOF**: outage of Redis means total loss of locking. Flag it.
- NX-locks are **not safe across Redis failover** (the classic Redlock concern). Flag any implied claim of failover safety.
- Verify fencing correctness: the monotonic integer — not the ownership token — is what protects writes.
- Verify that release / renew always token-check via Lua, never via a Python-side read-then-write.
- Verify that a renew failure flips the caller into fail-closed mode.

### 2. State integrity
- Look for **CAS bypass paths**: any code that writes a state key without going through the CAS Lua is a Critical finding.
- Poison / corrupt-payload handling: the system must quarantine, not overwrite. Verify the quarantine namespace is opaque (raw bytes preserved, no auto-parse on read).
- Verify that schema-version migration cannot silently fabricate fields.

### 3. Secrets handling
- No credentials in stored state, in logs, in URLs, in error messages, or in the build log.
- Ownership tokens come from `secrets.token_hex` (or equivalent CSPRNG), not `random`.
- No tokens logged at info level; only at debug level under explicit redaction.

### 4. Injection
- `intent_ledger` / `context_data` are untrusted input. Verify they are never `eval`'d, never interpolated into Lua source, never used to construct Redis commands as raw strings.
- Lua args must pass via `ARGV`, never concatenated into the script body.

### 5. Resource exhaustion / DoS
- TTL leaks: every key written must have a TTL (state 48h, locks ≤ ttl). Flag any code path that creates an unbounded key.
- Unbounded retry loops on lock acquisition: must have a max attempts and / or a deadline.
- Lease starvation: a worker that holds the lease forever blocks all others — the `max_total_lease` cap defends against this and must be wired.

### 6. Recovery safety
- `ABOUT_TO_FIRE` intents must NEVER be auto-retried. Verify the code path: on ambiguity, escalate, do not replay.
- Fail-closed is the default. Verify there is no "best effort" branch that proceeds on corruption.

## Output format

Findings table:

| id  | category | severity | location (file:line or component) | description | recommended fix |
|-----|----------|----------|-----------------------------------|-------------|------------------|

Followed by a **prioritized remediation list** ordered Critical → Low. Conclude with an honest **residual-risk note**: what the audit could not verify and what assumptions the audit relies on (single Redis topology, AOF `everysec`, etc.).
