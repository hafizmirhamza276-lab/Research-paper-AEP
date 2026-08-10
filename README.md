# Agent Execution Protocol (AEP)

The research artifact for *Declared Ambiguity: The Agent Execution Protocol
(AEP) for Autonomous Agents Calling Non-Idempotent Legacy APIs* — a protocol,
five baseline systems it is measured against, a fault-injection harness, the
frozen results of a 432-run evaluation, and the manuscript generated from them.

**Start at [`ARTIFACT.md`](ARTIFACT.md)** if you are here to check a number in
the paper. It maps every quantitative claim to the command that reproduces it.

```sh
make reproduce-figures   # the paper's tables, regenerated from the frozen CSVs and diffed
make reproduce-smoke     # one cell per system, end to end, under real SIGKILL
```

## The problem

An autonomous agent calls a legacy API that is non-idempotent, accepts no
idempotency key, and cannot be asked afterwards whether the mutation was
applied. The agent crashes around the call. Retrying risks a second real-world
effect nobody observes; not retrying risks an effect that exists and that no
record accounts for.

AEP's position is that this is a three-way trade rather than an engineering
defect, and that a system's obligation is to make the third corner reachable:
convert silent failure into **declared, durable, bounded ambiguity** an operator
can act on.

## Honest guarantee

> **Corruption and contention are detectable, and the system fails closed.**

This is the only guarantee this implementation delivers on a single Redis
instance. It does **not** claim absolute atomicity, split-brain impossibility,
exactly-once external calls, or HA/consensus. The full list of non-claims, each
with the reason it is out of scope, is in `docs/22-formal-model.md` §4.

## Three hard invariants

1. **Timeout Invariant** — `T_client <= T_lock - Buffer`, Buffer >= 15s.
2. **CAS Fencing Invariant** — state updates only via monotonic-integer CAS;
   never raw `SET`. The random lock token proves *ownership*; the monotonic
   integer is the fencing token.
3. **Fail-Closed Invariant** — on corruption, ambiguity, or a safety-cap hit:
   stop, fence, escalate. Never guess.

## What the evaluation found

Two claims the write-ahead pattern is usually sold as one, separated by
ablation:

* **Detection** — no undetected duplicate and no lost effect, with a residual of
  declared ambiguity set by what the endpoint can be asked — is produced by the
  durable pre-dispatch record **alone**. Removing the durability barrier and
  changing nothing else leaves every detection metric unchanged over 600
  executions per arm, against baselines that duplicate in 77–83% of crashed
  executions.
* **Prevention** is what the barrier contributes, and it is a different quantity
  against a different fault. Under a hard Redis kill placed between the intent
  write and its acknowledgement, the barrier withholds 18 real non-idempotent
  effects that the ablation commits.

The barrier's *durability* claim needs a fault that loses the page cache. A
process kill loses nothing — `appendfsync everysec` defers the `fsync(2)`, not
the `write(2)` — so it was tested by making the block device stop accepting
writes instead.

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
| `experiments/baselines/` | B0–B4b, and `B4_SEMANTICS.md` on what B4 shares with a real durable-execution engine |
| `experiments/harness/`, `experiments/run_matrix.py` | Fault injection, the six crash points, the matrix orchestrator |
| `experiments/analyze.py` | Runs → metrics, intervals, figures |
| `experiments/results/` | The frozen evaluation. Analysis products are tracked; raw run directories ship as an archive (see `ARTIFACT.md` §5) |
| `paper/` | The manuscript. `paper/generated/` is machine-written and must never be hand-edited |
| `scripts/` | The generators and the CI gates |
| `docs/22-formal-model.md` | System model, failure model, properties P1–P3, declared residual windows, non-claims |
| `reports/` | The session-by-session record, including what was wrong and when |

The package was named `src` before v0.2.0. Reports under `reports/` and
`docs/07`–`docs/21` cite the old paths deliberately: they record a tree that
existed at the time.

## Reproduce the verified run

Requires Docker and [uv](https://docs.astral.sh/uv/). Everything is pinned:
CPython 3.13.0 (`.python-version`), the dependency set (`uv.lock`), and the
Redis image by digest (`compose.phase2.yml`).

```sh
uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis
docker compose -f compose.phase2.yml up -d --wait

export REDIS_URL=redis://127.0.0.1:6381/15
export AEP_PHASE2_REDIS_INTEGRATION=1

# Assert the live Redis really provides phase2.conf semantics and WAITAOF.
uv run --frozen python scripts/verify_redis_semantics.py --url "$REDIS_URL"

uv run --frozen pytest -q -ra --strict-markers \
    --cov=aep_core --cov-report=term-missing --cov-fail-under=90
```

Expected: **1734 passed, 0 skipped**, coverage **91.18%** on `aep_core`.

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

The same guard stops the evaluation harness, which additionally kills processes
holding leases on the instance. `make reproduce-smoke` sets the marker on the
container it provisions and destroys, never on whatever `REDIS_URL` names.

## CI

`.github/workflows/ci.yml` runs the suite against real Redis 7.2 (never
fakeredis) and enforces five gates: zero skipped tests, zero xpassed tests,
≥ 90% coverage on `aep_core`, range-valid citations in
`docs/22-formal-model.md`, and — since the analysis products the paper is
computed from became tracked — the manuscript's numbers against the frozen CSVs.
Each gate is itself tested (`tests/test_ci_gates.py`,
`tests/test_citation_validator.py`, `tests/test_paper_tables.py`,
`tests/test_artifact_reproducibility.py`), because a gate that cannot fail is
decoration.

## License

MIT — see `LICENSE`. Citation metadata is in `CITATION.cff`.
