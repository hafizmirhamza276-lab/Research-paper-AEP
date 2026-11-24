"""The matrix refuses to collect beside a host-level fault injector.

This pins a failure that produced no error message and no visibly wrong
output. The write-loss probe of ``experiments/flakey_write_loss.py`` writes
``/proc/sys/vm/drop_caches``, which is kernel-wide; the matrix's Redis runs in
a container on the same kernel. Collected concurrently, several runs died with
``ConnectionError`` and the Redis instance restarted mid-batch. The runs that
*failed* are harmless -- they write no summary and the resumption logic
re-runs them. The runs that *completed* are the hazard: a coordinator blip
makes a re-executing baseline retry, a baseline that retries more produces
more duplicates, and that bias points toward the paper's own hypothesis. They
are indistinguishable from clean runs in every artifact the analysis reads.

So the check is a refusal rather than a warning, and it is tested in both
directions, because a refusal that cannot fire is the same as no refusal.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from experiments.run_matrix import (
    HOST_LEVEL_FAULT_INJECTORS,
    coordinator_run_id,
    host_level_fault_injector_running,
)


def test_a_quiet_host_reports_no_conflict() -> None:
    """The common case must not block collection."""
    assert host_level_fault_injector_running() is None


def test_the_probe_is_named_as_a_conflict() -> None:
    """If the module is renamed, this list has to be updated with it."""
    assert "experiments.flakey_write_loss" in HOST_LEVEL_FAULT_INJECTORS


def test_a_conflicting_process_is_detected(tmp_path: Path, monkeypatch) -> None:
    """A synthetic /proc with one offending cmdline must be caught."""
    fake_proc = tmp_path / "proc"
    for pid, cmdline in (
        ("1", "/sbin/init\0"),
        ("4242", "python\0-m\0experiments.flakey_write_loss\0--trials\030\0"),
        ("not-a-pid", "ignored\0"),
    ):
        entry = fake_proc / pid
        entry.mkdir(parents=True)
        (entry / "cmdline").write_bytes(cmdline.encode("utf-8"))

    monkeypatch.setattr(
        "experiments.run_matrix.Path",
        lambda value: fake_proc if value == "/proc" else Path(value),
    )
    assert host_level_fault_injector_running() == "experiments.flakey_write_loss"


def test_the_checker_never_reports_itself(tmp_path: Path, monkeypatch) -> None:
    """A run_matrix process whose own argv mentions the probe is not a conflict."""
    fake_proc = tmp_path / "proc"
    entry = fake_proc / str(os.getpid())
    entry.mkdir(parents=True)
    (entry / "cmdline").write_bytes(
        b"python\x00-m\x00experiments.flakey_write_loss\x00"
    )
    monkeypatch.setattr(
        "experiments.run_matrix.Path",
        lambda value: fake_proc if value == "/proc" else Path(value),
    )
    assert host_level_fault_injector_running() is None


def test_an_unreadable_process_entry_does_not_crash_the_check(
    tmp_path: Path, monkeypatch
) -> None:
    """A process that exits between listdir and read must not abort collection."""
    fake_proc = tmp_path / "proc"
    (fake_proc / "999").mkdir(parents=True)  # no cmdline file at all
    monkeypatch.setattr(
        "experiments.run_matrix.Path",
        lambda value: fake_proc if value == "/proc" else Path(value),
    )
    assert host_level_fault_injector_running() is None


def test_a_platform_without_proc_does_not_block_collection(
    tmp_path: Path, monkeypatch
) -> None:
    """The check is best-effort; it must not refuse what it cannot assess.

    This is also the path Windows takes, where the suite runs but the matrix
    does not, so a hard failure here would break the suite for no benefit.
    """
    monkeypatch.setattr(
        "experiments.run_matrix.Path",
        lambda value: (tmp_path / "absent") if value == "/proc" else Path(value),
    )
    assert host_level_fault_injector_running() is None


# ------------------------------------------------- the restart detector


class _FakeRedis:
    def __init__(self, run_id: str | None, *, raises: bool = False) -> None:
        self._run_id = run_id
        self._raises = raises

    async def info(self, _section: str) -> dict[str, str]:
        if self._raises:
            raise ConnectionError("Error 111 connecting to 127.0.0.1:6381")
        return {"run_id": self._run_id, "redis_version": "7.2.5"}

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_the_coordinators_identity_is_read_from_the_live_server(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "experiments.run_matrix.Redis",
        type("R", (), {"from_url": staticmethod(lambda *a, **k: _FakeRedis("abc123"))}),
    )
    assert await coordinator_run_id("redis://x/15") == "abc123"


@pytest.mark.asyncio
async def test_an_unreachable_coordinator_reads_as_unknown_not_as_clean(
    monkeypatch,
) -> None:
    """The distinction matters: `None` must not compare equal to a run_id.

    If an unreachable server returned a sentinel string, two unreachable
    readings would compare equal and a restart between them would be reported
    as no restart -- which is the exact failure this detector exists to catch.
    """
    monkeypatch.setattr(
        "experiments.run_matrix.Redis",
        type(
            "R",
            (),
            {"from_url": staticmethod(lambda *a, **k: _FakeRedis(None, raises=True))},
        ),
    )
    assert await coordinator_run_id("redis://x/15") is None
