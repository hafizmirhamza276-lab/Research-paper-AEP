"""Regression coverage for failure-safe manuscript builds."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _usable_bash() -> str:
    # Windows exposes the WSL launcher as ``bash.exe`` on PATH.  Starting it
    # can take longer than this deliberately lightweight regression needs, so
    # prefer Git Bash when it is installed and fall back to PATH elsewhere.
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        completed = subprocess.run(
            [candidate, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode == 0:
            return candidate
    pytest.fail("a usable Bash is required to verify scripts/build_paper.sh")


@pytest.mark.parametrize(("argument", "job"), [(None, "main"), ("--anonymous", "main-anon")])
def test_missing_pdflatex_cannot_modify_an_existing_pdf(tmp_path, argument, job):
    paper = tmp_path / "paper"
    paper.mkdir()
    sentinels = {
        f"{job}.pdf": b"%PDF-1.4\nlast-known-good\n",
        f"{job}.log": b"last-known-good log\n",
        f"{job}.bbl": b"last-known-good bibliography\n",
        f"{job}.blg": b"last-known-good bibtex log\n",
    }
    for name, content in sentinels.items():
        (paper / name).write_bytes(content)

    command = [_usable_bash(), "scripts/build_paper.sh"]
    if argument:
        command.append(argument)
    environment = os.environ.copy()
    environment["AEP_PAPER_DIR"] = paper.as_posix()
    environment["AEP_PDFLATEX"] = "aep-deliberately-missing-pdflatex"

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 127
    assert "required paper-build command not found" in completed.stderr
    for name, content in sentinels.items():
        assert (paper / name).read_bytes() == content
