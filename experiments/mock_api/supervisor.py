"""Start one MockLegacyAPI per run, and give it its own ground truth.

Session 3's entry gate D0(ii) failed the first time it was run, and the reason
is recorded here because it is a methodological point, not a bug report.

Six crash points were run back to back against **one** long-lived provider
holding **one** SQLite ledger. Runs one to four agreed; runs five and six did
not, with ``oracle_unattributed_rows`` equal to 6 and 12 -- precisely the
cumulative effects of their predecessors. ``reconcile.py`` reads the whole
ledger, so every run after the first was being asked to account for effects
that belonged to a different run.

Sharing the provider is worse than that, though, and the second consequence is
the one that would have quietly damaged the paper. ``MockLegacyAPI`` seeds one
``random.Random(config.seed)`` per *process*, and every mutation draws three
fault decisions from it. Shared across runs, run *N*'s fault stream is a
function of how many requests runs *1..N-1* happened to make -- so the seed
recorded in run *N*'s log does not determine run *N*'s faults, and the run is
not reproducible from its own record. Nothing would have failed; the numbers
would simply not have meant what they said.

Hence this module. One provider process per run, one ledger per run, one
freshly seeded generator per run. A run's fault stream is then a function of
its seed alone, and its reconciliation sees only its own effects.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from experiments.mock_api.config import MockApiConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]

#: How long to wait for uvicorn to bind and serve before giving up.
DEFAULT_READY_TIMEOUT_SECONDS = 60.0


class MockApiStartupError(RuntimeError):
    """The provider did not come up, so no run may be collected against it."""


def render_config(
    template_path: Path | str,
    destination: Path | str,
    *,
    ledger_path: Path | str,
    seed: int | None = None,
    readback_keying: str | None = None,
    fault_overrides: Mapping[str, Any] | None = None,
) -> Path:
    """Write a run-specific configuration derived from a template.

    Overrides are applied to the *raw document* and the result is then loaded
    through ``load_config``, so the strict loader -- which refuses every
    unknown key -- validates what was written rather than what was intended.
    A template typo therefore fails here, once, instead of inside a provider
    process the runner has already started.
    """
    document = yaml.safe_load(Path(template_path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise MockApiStartupError("mock API template is not a mapping")

    document["ledger_path"] = str(ledger_path)
    if seed is not None:
        document["seed"] = int(seed)
    if readback_keying is not None:
        document["readback_keying"] = str(readback_keying)
    if fault_overrides:
        defaults = document.setdefault("defaults", {})
        faults = defaults.setdefault("faults", {})
        faults.update(dict(fault_overrides))

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(document, sort_keys=True), encoding="utf-8"
    )
    load_config(destination)  # validates, and refuses unknown keys
    return destination


@dataclass
class MockApiProcess:
    """A running provider, and the handle needed to stop it."""

    process: subprocess.Popen
    base_url: str
    config_path: Path
    config: MockApiConfig
    log_path: Path

    def stop(self, *, timeout: float = 15.0) -> int | None:
        """Terminate the provider and wait for its ledger to be closed.

        ``terminate`` rather than ``kill``: the ledger commits every applied
        mutation in its own transaction with ``synchronous=FULL``, so nothing
        is lost either way, but a graceful stop closes the SQLite connections
        and so does not leave ``-wal`` files for the analysis to interpret.
        """
        if self.process.poll() is not None:
            return self.process.returncode
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout)
        return self.process.returncode


def _probe(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def start_mock_api(
    config_path: Path | str,
    *,
    port: int,
    host: str = "127.0.0.1",
    log_path: Path | str,
    ready_timeout_seconds: float = DEFAULT_READY_TIMEOUT_SECONDS,
    python_executable: str | None = None,
) -> MockApiProcess:
    """Start one provider and return only once it is serving its own config.

    Readiness is ``GET /v1/config`` matching the digest of the configuration
    on disk -- not merely "the port accepts connections". A stale provider
    left listening on the same port from an earlier run answers the socket
    check and would silently collect the next run against the wrong fault
    surface and the wrong ledger.
    """
    config_path = Path(config_path)
    expected = load_config(config_path)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handle = log_path.open("wb")
    process = subprocess.Popen(
        [
            python_executable or sys.executable,
            "-m",
            "experiments.mock_api",
            "--config",
            str(config_path),
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        stdout=handle,
        stderr=subprocess.STDOUT,
    )

    base_url = f"http://{host}:{port}"
    deadline = time.monotonic() + ready_timeout_seconds
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                handle.close()
                raise MockApiStartupError(
                    f"provider exited with status {process.returncode} before "
                    f"serving; log:\n{log_path.read_text(errors='replace')[-4000:]}"
                )
            served = _probe(f"{base_url}/v1/config")
            if served is not None:
                if served.get("config_digest") != expected.config_digest:
                    process.terminate()
                    process.wait(timeout=10)
                    handle.close()
                    raise MockApiStartupError(
                        f"a provider is already serving {base_url} with digest "
                        f"{served.get('config_digest')!r}, but this run needs "
                        f"{expected.config_digest!r}. Refusing to collect a run "
                        "against a configuration it did not ask for."
                    )
                return MockApiProcess(
                    process=process,
                    base_url=base_url,
                    config_path=config_path,
                    config=expected,
                    log_path=log_path,
                )
            time.sleep(0.1)
    except BaseException:
        process.terminate()
        raise

    process.terminate()
    process.wait(timeout=10)
    handle.close()
    raise MockApiStartupError(
        f"provider did not serve {base_url} within {ready_timeout_seconds}s; "
        f"log:\n{log_path.read_text(errors='replace')[-4000:]}"
    )
