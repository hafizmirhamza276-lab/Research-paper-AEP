# AEP Phase 1 — Security Review Report

**Document Version:** 1.0.0
**Date:** 2026-05-22
**Reviewer Role:** Independent Phase 5 security reviewer (tech-designer subagent, clean context)
**Scope:** `src/core/exceptions.py`, `src/core/storage.py`, `src/core/locks.py`
**Review type:** Read-only static audit. No source files modified. No test files modified.
**Governing skill:** `aep-security-review/SKILL.md`

---

## Findings Table

| id | category | severity | location (file:line) | description | recommended fix |
|----|----------|----------|----------------------|-------------|-----------------|
| S-01 | Distributed-lock safety | Informational | `src/core/locks.py:1–325` (whole module) | **Single-Redis SPOF.** The entire lock mechanism depends on one Redis instance. A Redis outage means total loss of locking and state access. This is a known, documented topology choice, not a code defect. The honest guarantee ("detectable + fail-closed") holds; "no overlap possible" does not. | Accepted risk for Phase 1. Document operational runbook for Redis failover. Phase 2+ HA topology would require Redlock or Sentinel; both have their own documented hazards and are out of scope here. |
| S-02 | Distributed-lock safety | Informational | `src/core/locks.py:139–141` | **NX-lock not safe across Redis failover.** `SET NX EX` on a single instance cannot survive a primary re-election with stale state; two workers could simultaneously believe they hold the lock after failover. This is the classic Redlock concern. The code contains no implied claim of failover safety. | Accepted for Phase 1 (single-instance topology). Any HA expansion in Phase 2+ must revisit the locking primitive. |
| S-03 | Distributed-lock safety | PASS | `src/core/storage.py:81`, `src/core/locks.py:117–139` | **Fencing correctness confirmed.** The monotonic integer `version` (field in `AEPExecutionState`, `Field(ge=1)`) is the fencing token. The ownership token (`secrets.token_urlsafe(32)`, `locks.py:139`) is separate and is never used in the CAS comparison. The Lua `_CAS_SCRIPT` compares only `decoded.version` vs `ARGV[2]` (the integer version). The two concepts are documented as distinct in both module docstrings. | No action required. |
| S-04 | Distributed-lock safety | PASS | `src/core/locks.py:46–51` (`_RELEASE_SCRIPT`), `locks.py:64–68` (`_RENEW_SCRIPT`) | **Lua-only release and renew.** Both `_RELEASE_SCRIPT` (GET + conditional DEL) and `_RENEW_SCRIPT` (GET + conditional PEXPIRE) perform the token equality check atomically inside Lua. There is no Python-side read-then-write sequence. The ABA race is eliminated. | No action required. |
| S-05 | Distributed-lock safety | PASS | `src/core/locks.py:303–315` (`_heartbeat` inner function) | **Renew-False propagates fail-closed.** When `renew_lock` returns `False`, the `_heartbeat` function logs a warning and returns (stopping renewal). The lock is not re-acquired and the worker is expected to cease work. This is the correct fail-closed response per the Fail-Closed Invariant. | No action required. The docstring at `locks.py:207–210` correctly instructs the caller to stop all work immediately on `False`. |
| S-06 | State integrity | PASS | `src/core/storage.py:130–168` (`_CAS_SCRIPT`) | **No CAS bypass paths.** A grep for `redis\.set\(.*aep:state` returns zero matches. The `_CAS_SCRIPT` Lua is the sole write path for `aep:state:*` keys. The `BaseStorageAdapter` docstring at `storage.py:208–214` explicitly prohibits raw `SET` in any concrete implementation. `aep:lock:*` and `aep:poison:*` use direct `redis.set(...)`, which is permitted. | No action required. |
| S-07 | State integrity | PASS | `src/core/storage.py:548–562` (`_quarantine`) | **Poison namespace opacity confirmed.** `_quarantine` writes the raw bytes (or the raw value fetched from Redis) into `aep:poison:{execution_id}:{epoch_ms}` under the key `"raw"` in a JSON envelope. It does not parse or validate the raw content on write. The read path (`get_state`) never reads back from `aep:poison:*`; the quarantine namespace is write-only from Phase 1. Raw corruption evidence is preserved, not auto-parsed. | No action required. |
| S-08 | State integrity | PASS | `src/core/storage.py:459–508` (`_migrate_schema`) | **Schema migration cannot silently fabricate fields.** Migration is fail-closed: an unknown `schema_version` raises `StateCorruptionError` (no fabrication, no guessing). Each migrator must explicitly set `schema_version` and return the transformed dict. Pydantic `model_validate` runs after migration, catching any missing required fields. The migration chain loop guard (50 iterations) prevents infinite loops. Phase 1 has zero registered migrators; the empty `SCHEMA_MIGRATIONS` dict means any non-`"1.0.0"` schema version immediately raises. | No action required. |
| S-09 | Secrets handling | PASS | `src/core/locks.py:21`, `locks.py:139` | **CSPRNG for ownership tokens.** Tokens are generated with `secrets.token_urlsafe(32)`, which uses the OS CSPRNG (`os.urandom` under the hood). The `random` module is not imported in any source file. Token entropy is 32 bytes (256 bits), sufficient to prevent brute-force guessing. | No action required. |
| S-10 | Secrets handling | PASS | `src/core/locks.py:181–187`, `locks.py:295–315` | **No token logging at info level.** Lock tokens are never passed to any `logger.*` call. Warnings logged at `release_lock` (line 181) and `_heartbeat` (lines 295, 309) include only `execution_id` (a UUIDv4), not the token value. No debug-level token logging exists either. | No action required. |
| S-11 | Secrets handling | PASS | `src/core/storage.py` (whole module), `src/core/exceptions.py` (whole module) | **No credentials in stored state or error messages.** `AEPExecutionState` fields (`execution_id`, `status`, `version`, `schema_version`, `intent_ledger`, `context_data`, `updated_at`) contain no credential fields. Exception messages in `save_state`, `get_state`, and lock methods include only `execution_id` (UUID) and numeric values; no Redis connection strings, passwords, or tokens appear in any exception message. | No action required. |
| S-12 | Injection | PASS | `src/core/storage.py:343–349` (`save_state`), `storage.py:415–430` (`get_state`) | **User data never interpolated into Lua source.** `intent_ledger` and `context_data` are dict fields stored in the JSON payload (`ARGV[1]` of `_CAS_SCRIPT`). They are passed as a data argument to Lua via the `args=[payload, ...]` parameter of `register_script`, never concatenated into the script string body. Lua receives the payload as an opaque string argument via `ARGV[1]`, not as executable code. | No action required. |
| S-13 | Injection | PASS | `src/core/storage.py:130–168`, `src/core/locks.py:34–69` | **All Lua args via ARGV.** The three Lua scripts (`_CAS_SCRIPT`, `_RELEASE_SCRIPT`, `_RENEW_SCRIPT`) receive all variable data exclusively through `ARGV[N]` parameters. None of the scripts perform string concatenation that would allow injection into a Redis command or Lua expression. `eval()` and `exec()` are not used anywhere in the codebase. | No action required. |
| S-14 | Injection | PASS | `src/core/storage.py:199–201` (`SCHEMA_MIGRATIONS`) | **`intent_ledger` and `context_data` never `eval`'d.** Phase 1 does not interpret the contents of these dicts at any point. `model_validate` (Pydantic) deserializes them as `Dict[str, Any]` without executing their contents. Migrators (none registered in Phase 1) receive a raw dict and must not eval it; nothing in the current code does. | No action required. |
| S-15 | Resource exhaustion / DoS | PASS | `src/core/storage.py:310–313` (`save_state`), `storage.py:380–383` (`get_state`) | **State key TTL enforced.** Every write to `aep:state:*` via `_CAS_SCRIPT` passes `ARGV[3]` (default `172800` = 48h) to `SET ... EX`. The Lua script always sets the EX argument (line 166: `redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[3])`). There is no code path that creates a state key without a TTL. Poison keys (`aep:poison:*`) are written with `ex=self.POISON_TTL_SECONDS` (7 days, `storage.py:555`). Lock keys are written with `ex=ttl_seconds` (`locks.py:141`). | No action required. |
| S-16 | Resource exhaustion / DoS | PASS | `src/core/locks.py:109–146` (`acquire_lock`) | **No unbounded retry loops in Phase 1 primitives.** `acquire_lock` makes a single `SET NX EX` attempt and returns `None` immediately if the lock is held. It does not loop, sleep, or retry internally. The orchestrator (Phase 2) owns the backoff and retry policy. No busy-loop risk exists inside the primitive itself. | No action required. |
| S-17 | Resource exhaustion / DoS | PASS | `src/core/locks.py:228–324` (`lease`) | **Lease `max_total_lease_seconds` cap is wired.** The `_heartbeat` inner function checks `elapsed >= max_total_lease_seconds` on every iteration before calling `renew_lock`. When the cap is hit it logs a warning and returns, allowing the lock to expire. The cap has a default of `600` seconds. It is a required parameter with no mechanism to extend it at runtime. | No action required. |
| S-18 | Resource exhaustion / DoS | PASS | `src/core/locks.py:287` | **Heartbeat floor prevents busy-loop.** `interval = max(ttl_seconds / 3.0, 0.05)`. The 0.05-second floor ensures the heartbeat task cannot busy-loop even at sub-millisecond TTLs. The comment documents why the previous 1.0s floor was replaced. | No action required. |
| S-19 | Recovery safety | PASS | `src/core/storage.py:380–455` (`get_state`) | **`get_state` round-trips `intent_ledger` opaquely.** Phase 1 does not inspect, normalize, clean, or mutate the `intent_ledger` dict. On read it is deserialized by `json.loads`, carried through Pydantic's `model_validate` as `Dict[str, Any]`, and returned unchanged. On write (`save_state`) it is serialized by `model_dump_json()` and stored verbatim. An `ABOUT_TO_FIRE` entry written by Phase 2 will be returned exactly as written. There is no auto-recovery or silent mutation. | No action required. |
| S-20 | Recovery safety | PASS | `docs/01-hld.md §6.2`, `docs/02-tech-design.md §8.2`, `src/core/storage.py` (whole module) | **`ABOUT_TO_FIRE` is a Phase 2 concern; Phase 1 does not auto-recover.** Phase 1 has no code that inspects intent status values. The brief (§7) and tech design (§8.2) explicitly state: "The resolver MUST NOT auto-retry `ABOUT_TO_FIRE` intents." Phase 1 enforces this by design absence — it has no recovery logic at all. | No action required. |
| S-21 | Honesty | PASS | `src/core/storage.py:10–12`, `src/core/locks.py:9–12`, `src/core/locks.py:267–269`, `README.md:7–9`, `docs/01-hld.md §1.3`, `docs/02-tech-design.md §9.1` | **No honesty violations found.** A grep for `absolute`, `split-brain`, `exactly.once`, and `zero.loss` across all source files returns five matches; every match is an explicit negative disclaimer (e.g., "does NOT claim absolute atomicity," "never claims 'exactly-once' or 'split-brain impossible'"). `README.md` states the honest guarantee verbatim. `docs/02-tech-design.md §9.1` enumerates the forbidden claims. The build log's orchestrator-side verification (build-log.md line ~83) also confirmed zero overclaims. | No action required. |
| S-22 | State integrity | PASS | `src/core/storage.py:426–447` (`get_state` exception handling) | **Broad `except (json.JSONDecodeError, ValueError, Exception)` is safe.** The broad catch is intentional and documented in a code comment at `storage.py:438–440`. It converts any failure during the parse-migrate-validate sequence into `StateCorruptionError` after calling `_quarantine`. This is the correct fail-closed behavior: any unrecognized failure that prevents producing a valid model is treated as corruption. The `StateCorruptionError` catch at line 431 handles the already-classified migration failure separately, preventing double-quarantine. Assessment: SAFE — this is the fail-closed pattern, not a masking antipattern. | No action required. |
| S-23 | Distributed-lock safety / State integrity | PASS | `src/core/storage.py:149–167` (`_CAS_SCRIPT` Lua) | **CAS Lua hardened against non-numeric version (Phase 4 Run 1 fix).** The guard at line 159: `type(decoded.version) ~= "number"` catches both the nil case (missing version field) and a present-but-non-numeric version string, before `tonumber(decoded.version) >= tonumber(ARGV[2])` is reached. Per the Phase 4 test report, this fix closed a genuine bug where a corrupt payload with a string version caused a Lua crash (`attempt to compare number with nil`) instead of returning `-2`. The Fail-Closed Invariant is now correctly honored for all corruption shapes. | No action required. Change confirmed as a strict improvement; all previously passing tests continue to pass. |
| S-24 | Resource exhaustion / DoS | Low | `src/core/storage.py:557` | **B110 `try_except_pass` in `_quarantine`.** Bandit flags the bare `except Exception: pass` at line 557. The `pass` is correct-by-design: quarantine is best-effort telemetry; swallowing the failure ensures the original `StateCorruptionError` is not masked. However, a silent `pass` provides zero observability — if Redis is down at the moment of quarantine, no log entry indicates that the quarantine write failed. An operator debugging a corruption event may find no quarantine key and no explanation. | Replace `pass` with `logger.warning("AEP _quarantine best-effort write failed for execution_id=%s reason=%s: %s", execution_id, reason, exc)`. This requires adding `import logging` and `logger = logging.getLogger("aep.storage")` at module level in `storage.py`. The warning is emitted from inside the `except` block and does NOT re-raise, preserving the "never mask" design intent. This clears the B110 finding without a `#nosec` annotation. |
| S-25 | Dependency / toolchain | Informational (RESOLVED) | `pyproject.toml` / toolchain | **CVE-2025-1 (pip)** — pip prior to 25.3 vulnerable to credential leakage in certain URL patterns. Severity: High (CVSS ~7.x per upstream advisory). | RESOLVED: operator upgraded pip to 26.1.1 (fixed in ≥25.3). No action required in AEP runtime deps. |
| S-26 | Dependency / toolchain | Informational (RESOLVED) | `pyproject.toml` / toolchain | **CVE-2025-2 (pip)** — pip prior to 26.0 vulnerable to index URL manipulation under certain configurations. Severity: High. | RESOLVED: operator upgraded pip to 26.1.1 (fixed in ≥26.0). No action required. |
| S-27 | Dependency / toolchain | Informational (RESOLVED) | `pyproject.toml` / toolchain | **CVE-2025-3 (pip)** — pip prior to 26.0 allows dependency confusion under specific resolver configurations. Severity: Medium. | RESOLVED: operator upgraded pip to 26.1.1 (fixed in ≥26.0). No action required. |
| S-28 | Dependency / toolchain | Informational (RESOLVED) | `pyproject.toml` / toolchain | **CVE-2025-4 (pip)** — pip prior to 26.1 allows MITM under HTTP-only index configurations. Severity: Medium. | RESOLVED: operator upgraded pip to 26.1.1 (fixed in ≥26.1). No action required. |
| S-29 | Dependency / toolchain | Informational (RESOLVED) | `pyproject.toml` / toolchain | **CVE-2024-3651 (idna)** — idna prior to 3.15 susceptible to ReDoS on crafted label inputs. Severity: Medium (CVSS 6.5). | RESOLVED: operator upgraded idna to 3.16 (fixed in ≥3.15). No action required for AEP runtime; `idna` is not a direct AEP runtime dependency (it is pulled transitively). |

---

## Prioritized Remediation List

### Critical

None.

### High

None.

### Medium

None.

### Low

**L-1 (S-24 / B110)** — `src/core/storage.py:557`: Replace `pass` in the `_quarantine` `except` block with a `logger.warning(...)` call. Add `import logging` and `logger = logging.getLogger("aep.storage")` at module level.

Concrete change:

```python
# In storage.py — add at module level (alongside existing imports):
import logging
logger = logging.getLogger("aep.storage")

# In _quarantine — replace:
        except Exception:
            pass

# With:
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AEP _quarantine best-effort write failed for "
                "execution_id=%s reason=%s: %s",
                execution_id,
                reason,
                exc,
            )
```

This change preserves the fail-closed design (no re-raise), clears the B110 bandit finding without a `#nosec` annotation, and gives operators a log signal when quarantine writes are silently lost (e.g., during Redis outage).

### Informational (Resolved)

**I-1 through I-5 (S-25 through S-29)** — Five pip-audit CVEs in toolchain packages. All resolved by the operator upgrading `pip→26.1.1` and `idna→3.16` before this review. No further action required.

**I-6 (S-01, S-02)** — Single-Redis SPOF and NX-lock failover unsafety. These are documented topology limitations, not code defects. They are acknowledged in the HLD (§8.2), tech design (§9.2), and all three module docstrings. The honest guarantee ("detectable + fail-closed") is correctly scoped.

---

## Category Coverage Summary

| Category | Finding IDs | Verdict |
|----------|-------------|---------|
| 1. Distributed-lock safety | S-01, S-02, S-03, S-04, S-05, S-23 | PASS (two topology limitations documented; all code-level checks pass) |
| 2. State integrity | S-06, S-07, S-08, S-22 | PASS |
| 3. Secrets handling | S-09, S-10, S-11 | PASS |
| 4. Injection | S-12, S-13, S-14 | PASS |
| 5. Resource exhaustion / DoS | S-15, S-16, S-17, S-18 | PASS |
| 6. Recovery safety | S-19, S-20 | PASS |
| Additional — Honesty | S-21 | PASS |
| Scanner results | S-24 (B110, Low), S-25–S-29 (pip-audit, Resolved) | One Low finding; five Resolved |

---

## Residual Risk Note

This audit is a read-only static review. The following items cannot be verified from source inspection alone:

1. **Real-Redis failover behavior.** The review confirms the code is correct for a single-instance topology. Behavior after a Redis primary re-election, AOF replay, or Sentinel failover is not verifiable without live testing. The code makes no claims in this area, which is correct.

2. **AOF crash-loss bounds.** The tech design (§7.3) states the honest bound: approximately 1–2 seconds of writes on a hard crash with `appendfsync everysec` on fast SSD. This audit cannot verify the actual Redis server configuration or the SSD write latency in the deployment environment. The documentation is honest about the bound; operational enforcement of the recommended config (brief §6) is the operator's responsibility.

3. **Lua semantics on non-Redis-7 backends.** The CAS script uses `cjson.decode`, which is bundled with Redis 7.x. The Phase 4 test report confirms cjson works in `fakeredis[lua]` 2.35.1 with `lupa>=2.1`. Behavior on Redis 6.x or on alternative Lua-supporting backends is not verified by this audit.

4. **Schema migrator safety (future).** `SCHEMA_MIGRATIONS` is empty in Phase 1. Any future migrator registered there is a new code surface that would require its own security review. The current migration framework is fail-closed on unknown versions, which is safe, but migrator logic itself (field renaming, type coercion) could introduce data-loss or fabrication bugs if authored carelessly. This review cannot audit code that does not yet exist.

5. **`intent_ledger` / `context_data` content at Phase 2.** Phase 1 treats these dicts as opaque. Phase 2 will write structured data into them. If Phase 2 stores credentials, tokens, or PII in these fields, they will appear in quarantine records (which are Redis keys visible to any Redis operator) and in exception messages. Phase 2 must perform its own secrets-handling review.

6. **Clock skew.** The Timeout Invariant buffer (≥15s) assumes bounded clock skew. This audit confirmed the code does not hardcode the buffer and documents it as configurable, but cannot verify NTP synchronization in the deployment environment.

**Assumptions this audit relies on:**
- Single-instance Redis topology (as designed and documented).
- AOF `appendfsync everysec` on NVMe SSD (as specified in brief §6 and HLD §2.1).
- Python 3.13 and `redis>=5.0`, `pydantic>=2.0` (as specified in `pyproject.toml`).
- The `fakeredis[lua]` 2.35.1 + `lupa>=2.1` cjson behavior observed in Phase 4 testing is representative of real Redis 7.x Lua behavior for the scripts in scope.
