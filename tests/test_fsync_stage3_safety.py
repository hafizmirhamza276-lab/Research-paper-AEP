"""The fsync benchmark must append safely and validate before mutation."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fsync_always_benchmark.sh"


def _bash() -> str:
    return (
        shutil.which("bash")
        or r"C:\Program Files\Git\bin\bash.exe"
    )


def test_invalid_fsync_run_count_fails_before_results_or_docker(tmp_path: Path) -> None:
    sentinel = tmp_path / "existing" / "keep.bin"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"keep exactly")
    environment = os.environ.copy()
    environment.update(
        {
            "AEP_FSYNC_RUNS": "0",
            "AEP_FSYNC_RESULTS_ROOT": str(sentinel.parent),
            "AEP_STAGE3_PLAN_SHA256": "a" * 64,
            "AEP_GIT_SHA": "b" * 40,
        }
    )
    shell = _bash()
    if os.name == "nt" and Path(shell).name.lower() == "bash.exe" and "system32" in shell.lower():
        def wsl_path(path: Path) -> str:
            drive = path.drive.rstrip(":").lower()
            suffix = path.as_posix().split(":", 1)[1]
            return f"/mnt/{drive}{suffix}"

        command = " ".join(
            [
                "AEP_FSYNC_RUNS=0",
                f"AEP_FSYNC_RESULTS_ROOT={shlex.quote(wsl_path(sentinel.parent))}",
                f"AEP_STAGE3_PLAN_SHA256={'a' * 64}",
                f"AEP_GIT_SHA={'b' * 40}",
                "bash",
                shlex.quote(wsl_path(SCRIPT)),
            ]
        )
        invocation = [shell, "-lc", command]
    else:
        invocation = [shell, str(SCRIPT)]
    completed = subprocess.run(
        invocation,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 2
    assert "must be a positive integer" in completed.stderr
    assert sentinel.read_bytes() == b"keep exactly"


def test_fsync_script_has_no_destructive_clean_path() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "rm -rf" not in source
    assert '--runs-per-cell "${RUNS}"' in source
    assert "Stage 3 never deletes prior runs" in source


def test_fsync_configuration_and_disposable_instance_are_verified() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "CONFIG GET appendfsync" in source
    assert 'if [ "${ACTUAL}" != "always" ]' in source
    assert "GET aep:test-instance-marker" in source
    assert 'if [ "${MARKER}" = "1" ]' in source


def test_fsync_resume_uses_locked_interleaved_plan() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--resume" in source
    assert "--run-order interleaved" in source
    assert "--expected-appendfsync always" in source
    assert '--experiment-plan-sha256 "${PLAN_SHA256}"' in source
