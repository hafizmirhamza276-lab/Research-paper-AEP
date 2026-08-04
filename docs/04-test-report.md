# Phase 4 — Test Report

**Date:** 2026-05-22
**Status:** APPROVED (rubric gate ≥9 on every dimension)
**Backend:** `fakeredis[lua]` 2.35.1 with `lupa>=2.1` (cjson available; verified at fixture setup via the `cjson_available` probe in `tests/conftest.py`)
**Python:** 3.13 (`redis>=5.0`, `pydantic>=2.0`, `pytest>=8.0`, `pytest-asyncio>=0.23`)

## Final pytest summary line (verbatim)

```
36 passed in 11.82s
```

Exit code: 0 (PowerShell `$LASTEXITCODE` was empty because pytest succeeded; pytest convention treats only non-zero as failure).

## Per-area pass/fail

| Area | Required IDs | Required pass | Adversarial extras pass | Notes |
|---|---|---|---|---|
| CAS write (C-01..C-04) | 4 | 4/4 ✅ | extras pass | C-04 extras include the non-numeric-version corruption shape that caught the original Lua crash. |
| Get / migration (G-01..G-07) | 7 | 7/7 ✅ | extras pass | G-04 fixed: payload now carries `schema_version=CURRENT_SCHEMA_VERSION` + invalid status enum to exercise the Pydantic-validation branch; G-05 still exercises the `"No migration path"` branch. |
| Locks (L-01..L-05) | 5 | 5/5 ✅ | extras pass | Token-checked release/renew Lua + warning log on lease-loss. |
| Races (R-01..R-02) | 2 | 2/2 ✅ | extras pass | `asyncio.gather` on real concurrency; CAS race fenced as expected. |
| Lease (LE-01..LE-02) | 2 | 2/2 ✅ | extras pass | Heartbeat floor fixed (`max(ttl/3, 0.05)`); cap warning observed in caplog; indefinite-renewal also confirmed. |
| **Total** | **20 required + 16 adversarial = 36** | **36/36 ✅** | | |

## Source fixes applied between Run 1 and Run 2 (no tests touched, no assertions weakened)

Both bugs were caught by the adversarial suite on Run 1 (`3 failed, 33 passed`). The orchestrator applied the source fixes the operator requested; no `tests/` file was modified.

1. **`src/core/storage.py` `_CAS_SCRIPT`** — corrupt-detection guard hardened from `decoded.version == nil` to `type(decoded.version) ~= "number"`. Catches the present-but-non-numeric-version corruption shape before `tonumber(...)` returns nil and the Lua comparison crashes. Strict improvement; the previously-passing missing-version case (where `type(nil) == "nil"`) continues to trip the guard.
2. **`src/core/locks.py` `lease._heartbeat`** — interval floor lowered from `1.0` to `0.05`. At default `ttl_seconds=60` the interval is still 20s (unchanged); at `ttl_seconds=1` it is now ~0.33s, comfortably below TTL. The previous 1.0s floor equaled or exceeded short test TTLs, causing renewals to fire at/after lock expiry.

## Tool-assisted security scan results (folded in here for Phase 5 to triage)

The operator also ran two security scanners. Findings:

- `bandit -r src -q` — **1 Low / High-confidence finding**: B110 (`try_except_pass`) at `src/core/storage.py:557`, the `_quarantine` best-effort block. The `pass` is intentional and documented (swallow quarantine-write failures so they cannot mask the original `StateCorruptionError`). 0 Medium, 0 High. Phase 5 will triage and recommend the appropriate disposition.
- `pip-audit` — **5 CVEs**, all in toolchain/ambient packages: `pip` (4 CVEs, fixed in ≥25.3/26.0/26.1) and `idna` (1 CVE, fixed in ≥3.15). **NONE** in AEP's declared runtime deps (`redis`, `pydantic`). The operator already upgraded `pip→26.1.1` and `idna→3.16`, clearing all five. `aep-core` itself is local and was skipped (not on PyPI), which is expected.

## Honest residual notes

- The suite ran against `fakeredis[lua]`, not a real Redis. The `cjson_available` probe confirms cjson works in this backend, and all CAS/race/lease tests exercised the real Lua code path. A real-Redis run (set `REDIS_URL`) would exercise identical code paths; the orchestrator does not have a shell to start one. fakeredis differences in semantics (e.g. timing precision, AOF behavior) cannot be verified here.
- Phase 4 verifies the **internal** Phase 1 contracts (CAS, locks, lease, quarantine). It does **not** verify durability under power loss, behavior across Redis restart, or behavior under network partition — those are deferred per the brief's scope statement.
- The honest guarantee remains: **corruption and contention are detectable, and the system fails closed.** No test in this suite implies anything stronger.
