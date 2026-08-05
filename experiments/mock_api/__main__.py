"""Run MockLegacyAPI standalone.

    python -m experiments.mock_api --config experiments/mock_api/config.example.yaml

The configuration is loaded and fully validated before the socket is bound, so
a run never starts against a document the service only partly understood.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from experiments.mock_api.service import MockLegacyAPI, create_app

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.example.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MockLegacyAPI.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--log-level", default="warning")
    arguments = parser.parse_args(argv)

    api = MockLegacyAPI.from_config_path(arguments.config)
    api.start()
    print(
        f"MockLegacyAPI config_digest={api.config.config_digest} "
        f"ledger={api.config.ledger_path} run_log={api.run_log_path}",
        flush=True,
    )
    try:
        uvicorn.run(
            create_app(api),
            host=arguments.host,
            port=arguments.port,
            log_level=arguments.log_level,
        )
    finally:
        api.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
