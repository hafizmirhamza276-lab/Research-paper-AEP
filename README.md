# Agent Execution Protocol (AEP)

AEP is a Python 3.13 + `redis.asyncio` execution protocol for autonomous
agents that call **non-idempotent legacy APIs**, running against a single
self-hosted Redis 7.2 instance with AOF.

## Honest guarantee

> **Corruption and contention are detectable, and the system fails closed.**

This is the only guarantee this implementation delivers on a single Redis
instance. It does **not** claim absolute atomicity, split-brain impossibility,
exactly-once external calls, or HA/consensus. The full list of non-claims, each
with the reason it is out of scope, is in `docs/22-formal-model.md` §4.

Instead of promising exactly-once, AEP makes ambiguity a first-class, durable,
detectable state: every external side effect is preceded by a
durably-acknowledged write-ahead intent, every state write is fenced by lock
ownership and exact expected-version CAS, and every unresolvable outcome halts
and escalates rather than guessing.

## Three hard invariants

1. **Timeout Invariant** — `T_client <= T_lock - Buffer`, Buffer >= 15s.
2. **CAS Fencing Invariant** — state updates only via monotonic-integer CAS;
   never raw `SET`. The random lock token proves *ownership*; the monotonic
   integer is the fencing token.
3. **Fail-Closed Invariant** — on corruption, ambiguity, or a safety-cap hit:
   stop, fence, escalate. Never guess.

## Layout

| Path | What it is |
|---|---|
| `aep_core/core/storage.py` | Atomic CAS state persistence via Lua, schema migration, quarantine on corruption |
| `aep_core/core/locks.py` | Distributed lease lock: acquire/release/renew plus a capped auto-renewing context manager |
| `aep_core/core/intents.py` | Write-ahead intent ledger and its transition table |
| `aep_core/core/durability.py` | WAITAOF barrier and the single-use dispatch authorization it mints |
| `aep_core/core/intent_workflow.py` | The runner: one external mutation per invocation, gated on the barrier ack |
| `aep_core/core/intent_recovery.py` | Crash-recovery resolver; classifies effects as CONFIRMED / REFUTED / PERMANENTLY_AMBIGUOUS |
| `aep_core/core/request_binding.py`, `request_vault.py` | Canonical request binding and the authenticated request vault |
| `docs/22-formal-model.md` | System model, failure model, properties P1–P3, declared residual windows, non-claims |
| `scripts/` | The CI gates (citations, pytest results, Redis semantics) |

The package was named `src` before v0.2.0. Reports under `reports/` and
`docs/07`–`docs/21` cite the old paths deliberately: they record a tree that
existed at the time.

## Reproduce the verified run

Requires Docker and [uv](https://docs.astral.sh/uv/). Everything is pinned:
CPython 3.13.0 (`.python-version`), the dependency set (`uv.lock`), and the
Redis image by digest (`compose.phase2.yml`).

```sh
uv sync --frozen --extra dev --extra cov
docker compose -f compose.phase2.yml up -d --wait

export REDIS_URL=redis://127.0.0.1:6381/15
export AEP_PHASE2_REDIS_INTEGRATION=1

# Assert the live Redis really provides phase2.conf semantics and WAITAOF.
uv run --frozen python scripts/verify_redis_semantics.py --url "$REDIS_URL"

uv run --frozen pytest -q -ra --strict-markers \
    --cov=aep_core --cov-report=term-missing --cov-fail-under=90
```

Expected: **1223 passed, 0 skipped**, coverage **90.31%** on `aep_core`.

Validate the formal model's citations:

```sh
uv run --frozen python scripts/validate_citations.py
```

Expected: **374 citations, 0 invalid**.

## Test-instance safety

Test cleanup is destructive. It never calls `FLUSHALL` — it `UNLINK`s only
`aep:*` keys — but namespace scoping alone is not a sufficient guard, because
`aep:*` is the namespace AEP uses *in production*. Cleanup therefore also
requires the instance to advertise `aep:test-instance-marker`, which is
auto-created only on an allowed, completely empty database. Mark a throwaway
instance explicitly with:

```sh
redis-cli -n 15 SET aep:test-instance-marker 1
```

## CI

`.github/workflows/ci.yml` runs the suite against real Redis 7.2 (never
fakeredis) and enforces four gates: zero skipped tests, zero xpassed tests,
≥ 90% coverage on `aep_core`, and range-valid citations in
`docs/22-formal-model.md`. Each gate is itself tested — see
`tests/test_ci_gates.py`, `tests/test_citation_validator.py`, and
`tests/test_artifact_reproducibility.py` — because a gate that cannot fail is
decoration.

## License

MIT — see `LICENSE`. Citation metadata is in `CITATION.cff`.
