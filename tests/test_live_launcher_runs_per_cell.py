"""The launcher takes a runs-per-cell argument, and the default still means 1.

**The default is the load-bearing half.** Stages 10 and 30 were launched
without the argument, and their reports quote the shape it produced -- two
runs, one per system. If adding the argument changed what those commands mean,
the reports would describe a collection the launcher can no longer reproduce.

The script needs a key to get past its own preconditions, so these read it as
source and exercise only the argument handling, which fails before anything is
loaded.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_phase40_live.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")


# -- the default ------------------------------------------------------------

def test_the_default_is_one():
    """Absent, the argument means what every stage so far ran with."""
    assert 'RUNS_PER_CELL="${2-1}"' in SOURCE


def test_an_empty_argument_does_not_silently_become_one():
    """${2-1}, not ${2:-1}. Found by the parametrised refusal test below.

    `run_phase40_live.sh "$ROOT" "$RUNS"` with RUNS unset is the shape an
    operator actually writes. With ${2:-1} that silently collects one run per
    cell instead of refusing, which is a collection that is not the one they
    asked for.
    """
    assert 'RUNS_PER_CELL="${2:-1}"' not in SOURCE


def test_the_matrix_call_uses_the_variable_not_a_literal():
    assert '--runs-per-cell "$RUNS_PER_CELL"' in SOURCE
    assert "--runs-per-cell 1 " not in SOURCE, (
        "a literal 1 would ignore the argument"
    )


def test_the_rest_of_the_collection_shape_is_unchanged():
    """Only runs-per-cell becomes an argument. Nothing else moves."""
    assert "--executions-per-run 3" in SOURCE
    assert "--workers 1" in SOURCE
    assert "--system AEP_FULL --system B0_NAIVE_RETRY" in SOURCE
    assert "--crash-point mid_dispatch --endpoint notifications" in SOURCE
    assert "--keying CALLER_REFERENCE --max-tier 1" in SOURCE


def test_the_banner_states_the_run_count():
    """An operator reading the log can see how many runs were asked for."""
    assert "runs/cell" in SOURCE
    assert "RUNS_PER_CELL * 2" in SOURCE


def test_the_usage_line_documents_it_as_optional():
    assert "<results-root> [runs-per-cell]" in SOURCE


# -- it refuses what it cannot use -----------------------------------------

def run_with(argument: str) -> str:
    """Invoke the launcher far enough to hit the argument check.

    The results root does not exist, so the script would go on to the env file
    and the caps; the argument check sits before any of that and before any
    network access, which is the point.
    """
    completed = subprocess.run(
        ["bash", str(SCRIPT), "/tmp/aep-nonexistent-root", argument],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "AEP_PLANNER_LOOP": "interactive",
             "AEP_PLANNER_PER_RUN_CALLS": "20",
             "AEP_PLANNER_PER_COLLECTION_CALLS": "30",
             "AEP_PLANNER_PER_COLLECTION_USD": "0.06"},
    )
    return (completed.stdout + completed.stderr)


@pytest.mark.parametrize("bad", ["0", "abc", "-1", "2.5", ""])
def test_a_value_it_cannot_use_is_refused(bad):
    output = run_with(bad)
    assert "REFUSING" in output, output
    assert "runs-per-cell" in output, output


def test_the_refusal_happens_before_the_env_file_is_read():
    """A bad argument must not get as far as loading a key."""
    output = run_with("abc")
    assert "REFUSING" in output
    # The env-file failure has its own wording; seeing it would mean the
    # argument check ran too late.
    assert "no /" not in output, output


@pytest.mark.parametrize("good", ["1", "2", "3", "10"])
def test_a_usable_value_passes_the_argument_check(good):
    """It gets past the argument check and stops on a later precondition."""
    output = run_with(good)
    assert "runs-per-cell must" not in output, output


# -- the derivation this exists for ----------------------------------------

def test_the_worst_case_for_the_derived_stage_100_shape_fits_its_budget():
    """Amendment 6 §7 caps a run at 20 calls; stage 100's budget is 100.

    Four runs -- two per system -- is the largest even count whose worst case
    cannot breach the stage's own collection cap. Six would give 120, and a
    collection cap that fires mid-run voids that run, which is the evidence
    stage 100 needs.
    """
    per_run_cap = 20
    stage_budget = 100

    assert 2 * 2 * per_run_cap == 80 <= stage_budget
    assert 3 * 2 * per_run_cap == 120 > stage_budget


def test_the_per_run_cap_the_derivation_uses_is_the_one_in_the_code():
    """So the arithmetic above cannot drift away from what runs."""
    from experiments.harness.agent_loop import MAX_DECISIONS_PER_EXECUTION

    derived = (3 * MAX_DECISIONS_PER_EXECUTION + 4) * 2 * 1
    assert derived == 20
