# Agent Execution Protocol (AEP) — Phase 1

AEP is a Python 3.13 + `redis.asyncio` persistence and concurrency layer for
autonomous agents on a single self-hosted Redis instance.

## Honest Guarantee

> **Corruption and contention are detectable, and the system fails closed.**

This is the only guarantee this implementation delivers on a single Redis
instance. It does not claim absolute atomicity, split-brain impossibility,
or exactly-once external calls.

## What is in Phase 1

- `src/core/exceptions.py` — five exception classes for distinct failure routing.
- `src/core/storage.py` — atomic CAS state persistence via Lua, schema migration,
  quarantine on corruption.
- `src/core/locks.py` — distributed lease lock with acquire/release/renew and a
  capped auto-renewing context manager.

## Install

```sh
pip install -e ".[dev]"
```

Requires Python 3.13+ and a running Redis 7.x instance.

## Run tests

```sh
pytest -q --tb=short
```

Tests that exercise the CAS Lua script (`cjson`) require a real Redis instance
(Docker recommended). `fakeredis` may be used for lock and non-Lua tests; verify
`cjson` support before relying on it for CAS scenarios.

## Three hard invariants

1. **Timeout Invariant** — `T_client <= T_lock - Buffer`, Buffer >= 15s.
2. **CAS Fencing Invariant** — state updates only via monotonic-integer CAS; never raw SET.
3. **Fail-Closed Invariant** — on corruption, ambiguity, or safety-cap hit: stop, fence, escalate.
