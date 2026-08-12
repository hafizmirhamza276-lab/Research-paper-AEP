"""One run, end to end: its own provider, its own ground truth, its own log.

``runner.execute_run`` assumes a provider is already serving the configuration
named in its ``RunConfig``. That assumption is what made the D0(ii) entry gate
fail on its first attempt: six runs shared one provider, so each reconciled
against a ledger holding its predecessors' effects, and -- worse -- each drew
its faults from a generator its predecessors had already advanced, which makes
the seed in a run's own log stop describing that run (see
``experiments/mock_api/supervisor.py`` for the full account).

This module closes that hole by making the provider part of the run rather than
part of the environment. Every run gets:

* a rendered mock API configuration written into its own results directory, so
  the configuration a run was collected under is recoverable from the run;
* a ledger file of its own, so reconciliation sees only its own effects;
* a freshly seeded fault generator, so the fault stream is a function of the
  recorded seed alone;
* a provider process started and stopped by the run, so nothing outlives it.

The cost is one process start per run. That is the price of a reproducible
fault stream and it is not negotiable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from experiments.harness.config import RunConfig
from experiments.harness.runner import execute_run
from experiments.mock_api.supervisor import render_config, start_mock_api

#: Where a run's rendered provider configuration and ledger land, relative to
#: the run's own results directory. Both are inside it on purpose: a results
#: directory is meant to be readable on its own, months later, by someone who
#: has only the directory.
PROVIDER_CONFIG_NAME = "mock-api.yaml"
PROVIDER_LEDGER_NAME = "ground_truth.sqlite3"
PROVIDER_LOG_NAME = "mock-api.log"


async def run_once(
    *,
    run_config_overrides: Mapping[str, Any],
    template_path: Path | str,
    port: int,
    host: str = "127.0.0.1",
    fault_overrides: Mapping[str, Any] | None = None,
    provider_seed: int | None = None,
) -> dict[str, Any]:
    """Render a provider configuration, start it, run once, stop it.

    ``run_config_overrides`` must carry at least ``run_id``, ``seed``,
    ``results_root``, ``workers``, ``executions_per_worker``, ``endpoint`` and
    ``redis_url``; ``mock_api_config_path`` and ``mock_api_base_url`` are
    supplied here and must *not* be passed in, because a caller that named its
    own provider would defeat the isolation this module exists to provide.
    """
    overrides = dict(run_config_overrides)
    for reserved in ("mock_api_config_path", "mock_api_base_url"):
        if reserved in overrides:
            raise ValueError(
                f"{reserved} is owned by orchestrate.run_once; a run that names "
                "its own provider is not isolated from other runs"
            )

    results_dir = Path(overrides["results_root"]) / str(overrides["run_id"])
    if results_dir.is_dir() and any(results_dir.iterdir()):
        raise RuntimeError(
            f"refusing to overwrite existing run evidence at {results_dir}; "
            "archive the complete attempt under results/voided first"
        )
    results_dir.mkdir(parents=True, exist_ok=True)

    config_path = render_config(
        template_path,
        results_dir / PROVIDER_CONFIG_NAME,
        ledger_path=results_dir / PROVIDER_LEDGER_NAME,
        seed=provider_seed if provider_seed is not None else overrides.get("seed"),
        readback_keying=(
            str(overrides["readback_keying"].value)
            if hasattr(overrides.get("readback_keying"), "value")
            else overrides.get("readback_keying")
        ),
        fault_overrides=fault_overrides,
    )

    provider = start_mock_api(
        config_path,
        port=port,
        host=host,
        log_path=results_dir / PROVIDER_LOG_NAME,
    )
    try:
        config = RunConfig(
            **overrides,
            mock_api_config_path=str(config_path),
            mock_api_base_url=provider.base_url,
        )
        return await execute_run(config)
    finally:
        provider.stop()
