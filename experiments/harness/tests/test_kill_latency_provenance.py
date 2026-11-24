"""The host's fault-injector timing is recorded into every run.

Phase 10, addition 3. The field exists because Phase 9C's over-dispersion
finding was uninterpretable until Phase 8.1 recovered the per-run kill latencies
by hand from 300 event logs, and because the *host-level* distribution those
runs were drawn from was never recorded at all. Phase 10 then measured that
distribution moving by a factor of three when the container runtime changed
(961.8 ms median through the Docker Desktop shim, 317 ms through a native
daemon), which is the same order as the 194.1 ms separation Phase 8.1 attributed
to the race.

These tests pin the two properties that make the field worth having:

* it is present in ``collect()`` **whatever** the run's regime, including the
  regimes that perform no ``docker kill`` at all -- a field recorded only where
  it is exercised leaves exactly the gap it exists to close; and
* a missing or corrupt cache is *described* rather than raised, because a
  provenance probe that can abort a collection is a worse defect than the gap.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.harness import provenance


def test_a_missing_cache_is_described_rather_than_raised(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv(
        provenance.KILL_LATENCY_CACHE_VARIABLE, str(tmp_path / "absent.json")
    )
    record = provenance.docker_kill_latency()
    assert "error" in record
    assert record["cache"].endswith("absent.json")
    assert "runtimes" not in record


def test_a_corrupt_cache_is_described_rather_than_raised(
    tmp_path: Path, monkeypatch
) -> None:
    cache = tmp_path / "corrupt.json"
    cache.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv(provenance.KILL_LATENCY_CACHE_VARIABLE, str(cache))
    record = provenance.docker_kill_latency()
    assert "error" in record
    assert "JSONDecodeError" in record["error"]


def test_a_cache_with_no_summaries_is_an_error_not_a_silent_pass(
    tmp_path: Path, monkeypatch
) -> None:
    """An empty measurement must not read as "measured, and it was nothing"."""
    cache = tmp_path / "empty.json"
    cache.write_text(json.dumps({"measured_at_utc": "2026-09-02T00:00:00Z"}),
                     encoding="utf-8")
    monkeypatch.setenv(provenance.KILL_LATENCY_CACHE_VARIABLE, str(cache))
    record = provenance.docker_kill_latency()
    assert record["error"] == "the cache carries no runtime summaries"


def test_a_real_cache_is_summarised_with_its_target_mode(
    tmp_path: Path, monkeypatch
) -> None:
    """``target_mode`` is carried because it decides what the number means.

    A throwaway container isolates the runtime; only a measurement against the
    real compose container is comparable in absolute terms to the collected
    runs. A reader who cannot tell which one produced the number cannot use it.
    """
    cache = tmp_path / "kill.json"
    cache.write_text(
        json.dumps(
            {
                "measured_at_utc": "2026-09-02T10:00:00Z",
                "target": {
                    "mode": "pre-existing",
                    "comparable_to_collected_runs": True,
                },
                "summaries": {
                    "aep-native": {
                        "trials_counted": 100,
                        "min": 264.0,
                        "median": 317.0,
                        "p95": 361.0,
                        "max": 397.0,
                        "median_ci_low": 312.5,
                        "median_ci_high": 327.0,
                        "context": "aep-native",
                        "server_version": "29.4.3",
                        "ignored_extra_key": "not carried",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(provenance.KILL_LATENCY_CACHE_VARIABLE, str(cache))
    record = provenance.docker_kill_latency()

    assert "error" not in record
    assert record["measured_at_utc"] == "2026-09-02T10:00:00Z"
    assert record["target_mode"] == "pre-existing"
    assert record["comparable_to_collected_runs"] is True
    native = record["runtimes"]["aep-native"]
    assert native["median"] == 317.0
    assert native["trials_counted"] == 100
    assert native["context"] == "aep-native"
    assert "ignored_extra_key" not in native


def test_collect_carries_the_field_even_with_no_container(
    tmp_path: Path, monkeypatch
) -> None:
    """The regimes that never issue a ``docker kill`` must carry it too.

    ``session-3`` -- the regime Table 1 is built from, and the one Phase 10's
    replication re-collects -- performs no Redis kill: its fault is a worker
    ``SIGKILL`` the process sends to itself (``injector.py:81-82``), which has
    no cross-boundary landing latency. The *host* still has one, and whether
    two collections are comparable turns on whether the host was the same
    instrument.
    """
    monkeypatch.setenv(
        provenance.KILL_LATENCY_CACHE_VARIABLE, str(tmp_path / "absent.json")
    )
    record = provenance.collect(tmp_path, None)
    assert "docker_kill_latency" in record
    json.dumps(record)


def test_the_default_cache_path_is_inside_the_repository(monkeypatch) -> None:
    """No env var set: the probe must still name a determinate path.

    A probe whose location depended on the caller's working directory would
    record a different thing depending on where a collection was launched from,
    which is the class of defect this module was written to remove.
    """
    monkeypatch.delenv(provenance.KILL_LATENCY_CACHE_VARIABLE, raising=False)
    record = provenance.docker_kill_latency()
    assert record["cache"].endswith(provenance.KILL_LATENCY_CACHE)
    assert Path(record["cache"]).is_absolute()
