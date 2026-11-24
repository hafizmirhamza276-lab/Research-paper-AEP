---
name: redis-async-patterns
description: Implementation patterns for AEP's Redis layer — asyncio client config, Lua CAS write-path, distributed lock acquire/release/renew, and capped heartbeat lease.
---

# AEP Redis async patterns

These are the implementation patterns the AEP storage / lock / lease layer must follow. Treat them as canonical for design, code, and review.

## Client configuration

- A **single shared** `redis.asyncio.Redis(decode_responses=True)` client backed by a connection pool, created at startup and reused across the process.
- Do not create per-call clients. Do not toggle `decode_responses` per call.
- Lua scripts are loaded via `client.register_script(LUA_SRC)`; the returned callable uses `EVALSHA` semantics under the hood and falls back to `EVAL` on cache miss.

## Atomic CAS write-path

A single Lua script is the **only** way state is written. Pseudocode of its contract:

```
KEYS[1] = state_key
ARGV[1] = new_version (monotonic int, decoded by cjson)
ARGV[2] = new_payload_json
return:
   1  on successful write
  -1  on stale write   (incoming version <= stored version)
  -2  on corrupt-at-write (stored payload exists but cjson.decode fails)
```

- The Lua script uses `cjson.decode` on the stored payload; on decode failure it returns `-2` and does **not** overwrite.
- Python maps the return codes:
  - `1` → success.
  - `-1` → raise `StaleWriteError`.
  - `-2` → raise `StateCorruptionError`; the caller is responsible for quarantining the key.
- Raw `SET` against a state key is **forbidden**. Only the CAS Lua may write state.

## Distributed lock lifecycle

- **Acquire:** `SET lock_key token NX EX ttl`, where `token = secrets.token_hex(16)`. The token is an **ownership** token, not a fencing token.
- **Release:** a Lua script that reads the lock value and `DEL`s only if it matches the caller's token. A `0` return (token mismatch or already gone) MUST be logged as a warning — it indicates the lock may have expired underneath the caller.
- **Renew:** `PEXPIRE`-based renew, again token-checked via Lua. A `0` return means the token no longer holds the lock; the caller must treat itself as lock-less and fail-closed.

## Capped auto-renewing lease

- Heartbeat interval ≈ `ttl / 3`.
- Each successful renew extends the lock for another `ttl`.
- A **hard `max_total_lease`** ceiling caps how long the lease may be auto-renewed for any single acquisition.
- When the cap is hit:
  - The lease loop **stops renewing**.
  - The lock is allowed to expire naturally.
  - The caller is notified (raised exception or a sentinel return) so it can fail-closed.
- This is the Fail-Closed invariant in action: the system does not extend the lease indefinitely just because the worker is still running.

## TTL, durability, and quarantine

- State keys have a **48h TTL**.
- A stored payload that fails to parse is **quarantined** (e.g., renamed to a `quarantine:<key>` namespace with the raw bytes preserved) and `StateCorruptionError` is raised. The key is **not** silently rewritten.
- On the chosen self-hosted topology (AOF `appendfsync everysec` on fast SSD), the durability bound for crash loss is roughly **1–2 seconds** of writes. Reports and security findings must use this honest bound, not "zero loss."

## Honest topology note

This is a **single Redis instance**. NX-locks are not safe across Redis failover. Do not pretend otherwise. The honest claim is "detectable + fail-closed," supported by CAS fencing and capped leases.
