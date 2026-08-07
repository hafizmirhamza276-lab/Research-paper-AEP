"""The file the paper quotes must not pool two experiments into one rate.

Session 3B §F2 banned Table 1 as a source because it pools fault regimes: a
crash-free run and a run in which every execution was killed contribute to the
same rate, so the pooled number is a property of how many runs of each kind
happen to have been collected. The remedy was "quote ``per-cell-metrics.csv``".

That remedy is only sound if the per-cell file does not have the same defect,
and it nearly did. A regime is a *condition*, not a matrix dimension, so it is
not part of ``(system, crash_point, response_class, readback_keying)`` -- and
two of the five regimes report ``crash_point = "none"``:

* ``p0``                -- crash-free, the only cells RQ3 may use;
* ``redis-kill-preack`` -- no *worker* crash, but Redis is hard-killed and
                           restarted mid-run.

Nothing about those two belongs in one average. They are currently told apart
only because ``p0`` was collected against ``payments`` and the Redis-kill cells
against ``NO_READBACK`` -- an accident of collection order, not a property of
the key. ``p0`` on ``NO_READBACK`` is in the 1 068-run plan.

These tests fail if ``regime`` is ever dropped from the grouping again.
"""

from __future__ import annotations

from experiments.analyze import (
    PER_CELL_GROUP_ATTRIBUTES,
    PER_CELL_GROUP_COLUMNS,
    RunRecord,
    build_per_cell,
    build_executions_csv,
)


def _run(run_id: str, *, regime: str, redis_kill_point: str | None) -> RunRecord:
    """A run with no executions: the grouping is what is under test."""
    return RunRecord(
        run_id=run_id,
        system="AEP_FULL",
        crash_point="none",
        endpoint="notifications",
        response_class="NO_READBACK",
        readback_keying="CALLER_REFERENCE",
        seed=1,
        config_digest="d" * 8,
        has_sigkill=True,
        wall_seconds=1.0,
        regime=regime,
        crash_probability=0.0,
        redis_kill_point=redis_kill_point,
    )


def test_the_two_crash_free_regimes_do_not_merge_into_one_cell() -> None:
    """The collision the plan will produce, asserted before it produces it."""
    crash_free = _run("p0-r0", regime="p0", redis_kill_point=None)
    redis_killed = _run(
        "kill-r0",
        regime="redis-kill-preack",
        redis_kill_point="after_intent_before_barrier",
    )

    # Identical in every dimension the matrix has a name for.
    for attribute in ("system", "crash_point", "response_class", "readback_keying"):
        assert getattr(crash_free, attribute) == getattr(redis_killed, attribute)

    rows = build_per_cell([crash_free, redis_killed], resamples=10, seed=1)
    regimes = {row["regime"] for row in rows}
    assert regimes == {"p0", "redis-kill-preack"}, (
        "a crash-free cell and a hard-Redis-kill cell were averaged together"
    )


def test_session_threes_regime_is_labelled_rather_than_left_blank() -> None:
    """``""`` is the right key and the wrong column value."""
    rows = build_per_cell(
        [_run("s3-r0", regime="", redis_kill_point=None)], resamples=10, seed=1
    )
    assert {row["regime"] for row in rows} == {"(session-3)"}


def test_regime_is_the_first_column_and_names_match_the_attributes() -> None:
    """The two tuples are parallel; a rename of one must not silently pass."""
    assert PER_CELL_GROUP_COLUMNS[0] == "regime"
    assert PER_CELL_GROUP_ATTRIBUTES[0] == "regime_label"
    assert len(PER_CELL_GROUP_ATTRIBUTES) == len(PER_CELL_GROUP_COLUMNS)
    assert PER_CELL_GROUP_ATTRIBUTES[1:] == PER_CELL_GROUP_COLUMNS[1:]


def test_every_per_cell_row_carries_the_regime() -> None:
    rows = build_per_cell(
        [
            _run("s3-r0", regime="", redis_kill_point=None),
            _run("p0-r0", regime="p0", redis_kill_point=None),
        ],
        resamples=10,
        seed=1,
    )
    assert rows, "no rows produced"
    assert all(row.get("regime") for row in rows)


def test_the_per_execution_file_carries_the_regime_too() -> None:
    """A reader recomputing a rate from raw rows needs the same discriminator."""
    from experiments.analyze import ExecutionRecord

    run = _run("kill-r0", regime="redis-kill-preack", redis_kill_point="mid_dispatch")
    run.executions.append(
        ExecutionRecord(
            run_id=run.run_id,
            system=run.system,
            crash_point=run.crash_point,
            endpoint=run.endpoint,
            response_class=run.response_class,
            readback_keying=run.readback_keying,
            execution_id="e0",
            outcome_class="DECLARED_AMBIGUOUS",
            status="PERMANENTLY_AMBIGUOUS",
            applied_effects=0,
            crashed=False,
            dispatch_attempts=1,
        )
    )
    rows = build_executions_csv([run])
    assert [row["regime"] for row in rows] == ["redis-kill-preack"]
