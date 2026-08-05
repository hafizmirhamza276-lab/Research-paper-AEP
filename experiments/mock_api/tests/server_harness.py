"""Run MockLegacyAPI as a real OS process, so it can really be killed.

An in-process ``TestClient`` cannot be SIGKILLed and cannot lose a response to
a real socket timeout. The crash-safety claim in ``ledger.py`` is about a
process dying mid-transaction, so the tests that assert it need a process.

Not a test module: no ``test_`` prefix, nothing here is collected.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

#: True where a real SIGKILL exists. On Windows the equivalent is
#: TerminateProcess (``Popen.kill``), which likewise gives the target no
#: opportunity to run cleanup, flush buffers, or roll anything back --
#: the property these tests depend on. CI runs on ubuntu-24.04, so the
#: POSIX branch is the one that gates the artifact.
HAS_SIGKILL = hasattr(signal, "SIGKILL")


def free_port() -> int:
    """Ask the OS for a port, then release it. Racy in principle, fine here."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def write_config(path: Path, document: dict) -> Path:
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


class MockApiProcess:
    """A MockLegacyAPI running under uvicorn in its own process."""

    def __init__(self, config_path: Path, *, log_directory: Path) -> None:
        self.config_path = config_path
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._log_directory = log_directory
        self._stdout = (log_directory / "mock-api-stdout.log").open("wb")
        self._stderr = (log_directory / "mock-api-stderr.log").open("wb")
        self._process: subprocess.Popen | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self, *, timeout: float = 30.0) -> "MockApiProcess":
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "experiments.mock_api",
                "--config",
                str(self.config_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ],
            cwd=str(Path(__file__).resolve().parents[3]),
            stdout=self._stdout,
            stderr=self._stderr,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(
                    f"mock API exited during startup with code "
                    f"{self._process.returncode}\n{self.logs()}"
                )
            try:
                response = httpx.get(f"{self.base_url}/v1/health", timeout=0.5)
                if response.status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"mock API did not become healthy\n{self.logs()}")

    @property
    def pid(self) -> int:
        if self._process is None:
            raise RuntimeError("process was never started")
        return self._process.pid

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def sigkill(self) -> None:
        """Kill without any chance to clean up, and wait for the corpse."""
        if self._process is None or self._process.poll() is not None:
            return
        if HAS_SIGKILL:
            os.kill(self._process.pid, signal.SIGKILL)
        else:
            self._process.kill()
        self._process.wait(timeout=30)

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=30)
        self._stdout.close()
        self._stderr.close()

    # -- diagnostics -------------------------------------------------------

    def logs(self) -> str:
        parts = []
        for name in ("mock-api-stdout.log", "mock-api-stderr.log"):
            path = self._log_directory / name
            if path.is_file():
                parts.append(f"--- {name} ---\n{path.read_text(errors='replace')}")
        return "\n".join(parts)

    def __enter__(self) -> "MockApiProcess":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()


def wait_for_marker(path: Path, *, timeout: float = 20.0) -> bool:
    """Block until the service says it is inside the transaction."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.02)
    return False
