"""Rule 13 for the attribution gate, on the real stack, in both directions.

A harness built and used in the same pass gets no gate. This is the gate: it
drives two real runs through :func:`collect.run_once` and asserts they read
differently.

* **Branch A** -- the ledger the run was collected against. The shared
  reconciler attributes every applied row to an execution, and the gate is
  silent.
* **Branch B** -- a ledger from a *different* run, so the applied rows belong to
  targets this run's workload plan does not contain. The join the numbers rest
  on does not hold, and the run must void naming **attribution**, not report a
  zero rate.

Branch B is the one that matters. A missing or mismatched oracle produces no
duplicates and no lost effects, which is arithmetically indistinguishable from a
clean run --- and would make B5 look better than B4 for the one reason that has
nothing to do with either engine.

Exit 0 means both branches were observed. Any other exit means the gate is
unproven and the runner must not be used to collect.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.baselines.b5_temporal import collect  # noqa: E402
from experiments.baselines.b5_temporal.gate import RunVerdict  # noqa: E402
from experiments.baselines.contract import SystemId  # noqa: E402
from experiments.harness.config import RunConfig  # noqa: E402
from experiments.mock_api.config import load_config  # noqa: E402

#: The ledger requires a real lower-case hex SHA-256 (ledger.py:200), so the
#: stray row carries one. It is still a row no plan of this run can explain,
#: which is the whole point of branch B.
_STRAY_DIGEST = "4f4c46a232d4b4548c5798c074b378e297a7d9b42013eb262504d7371a383b31"


def _config(run_id: str, results_root: Path) -> RunConfig:
    """A real RunConfig, field names read from experiments/harness/config.py:50.

    ``executions_per_worker`` with one worker gives the run's execution count;
    ``results_root`` plus ``run_id`` is what ``results_dir`` is derived from.
    """
    return RunConfig(
        run_id=run_id,
        seed=20260908,
        workers=1,
        executions_per_worker=2,
        endpoint="ledger_postings",
        mock_api_config_path="/var/tmp/b5-probe/mock-api.yaml",
        mock_api_base_url="http://127.0.0.1:8099",
        redis_url="redis://127.0.0.1:6381/15",
        results_root=str(results_root),
        system=SystemId.B5_TEMPORAL,
        crash_point="after_barrier_before_dispatch",
        crash_probability=1.0,
    )


async def main() -> int:
    out = Path("/var/tmp/b5-gate-proof")
    out.mkdir(parents=True, exist_ok=True)
    provider = "http://127.0.0.1:8099"
    TEMPLATE = Path("/var/tmp/b5-probe/mock-api.yaml")

    print("=== branch A: this run's OWN ledger (per-run provider) ===", flush=True)
    a_config = _config(f"gate-a-{uuid.uuid4().hex[:6]}", out / "A")
    a_dir = a_config.results_dir
    a_dir.mkdir(parents=True, exist_ok=True)
    # The requirement the gate itself surfaced: a ledger belonging to ONE run.
    # The previous attempt pointed branch A at the shared probe ledger, which
    # held 129 rows from days of earlier runs, and the gate correctly voided it.
    a_provider = collect.RunProvider(a_dir, template=TEMPLATE, port=8099)
    if not a_provider.start():
        print("  provider for branch A never became healthy", flush=True)
        return 4
    try:
        a = await collect.run_once(
            config=a_config, mock_api_config=load_config(a_provider.config_path),
            results_dir=a_dir, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
            provider_url=a_provider.url, deadline_s=90,
            ledger_path=a_provider.ledger_path,
        )
    finally:
        a_provider.stop()
    print(f"  verdict={a['verdict']}  attribution_usable={a['attribution_usable']}", flush=True)
    print(f"  {a['attribution_reason'][:170]}", flush=True)

    print("", flush=True)
    print("=== branch B: a ledger this run's plan cannot explain ===", flush=True)
    b_config = _config(f"gate-b-{uuid.uuid4().hex[:6]}", out / "B")
    b_dir = b_config.results_dir
    b_dir.mkdir(parents=True, exist_ok=True)
    b_provider = collect.RunProvider(b_dir, template=TEMPLATE, port=8099)
    if not b_provider.start():
        print("  provider for branch B never became healthy", flush=True)
        return 4
    stray = out / "stray-ledger.sqlite3"
    stray.unlink(missing_ok=True)
    from experiments.mock_api.ledger import GroundTruthLedger
    ledger = GroundTruthLedger(stray)
    ledger.initialise()
    try:
        ledger.record_applied_mutation(
            call_id="stray-call", endpoint="ledger_postings",
            target="target-from-another-run", fingerprint=_STRAY_DIGEST,
            payload_digest=_STRAY_DIGEST, client_reference="not-in-this-plan",
            response_class="NO_READBACK", delivery_index=1, applied_at_ms=1,
        )
    finally:
        ledger.close()
    try:
        b = await collect.run_once(
            config=b_config, mock_api_config=load_config(b_provider.config_path),
            results_dir=b_dir, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
            provider_url=b_provider.url, deadline_s=90, ledger_path=stray,
        )
    finally:
        b_provider.stop()
    print(f"  verdict={b['verdict']}  attribution_usable={b['attribution_usable']}", flush=True)
    print(f"  {b['attribution_reason'][:200]}", flush=True)

    print("\n=== rule 13 ===", flush=True)
    a_ok = a["verdict"] != RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE.value
    b_ok = b["verdict"] == RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE.value
    print(f"  branch A did not void on attribution : {a_ok}", flush=True)
    print(f"  branch B voided naming attribution   : {b_ok}", flush=True)
    satisfied = a_ok and b_ok
    print(f"  BOTH BRANCHES OBSERVED: {satisfied}", flush=True)
    return 0 if satisfied else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
