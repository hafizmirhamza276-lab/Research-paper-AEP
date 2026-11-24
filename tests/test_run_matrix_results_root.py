"""``run_matrix`` must not default its results root. ``docs/25`` R16 instance 3.

The default was ``experiments/results/matrix`` -- the frozen 432-run root every
outcome rate in the paper is computed from. Two things made that worse than a
merely unfortunate default:

* ``--plan-only``, documented as the safe "print the schedule and exit" path,
  writes ``matrix-plan.json`` and ``matrix-plan.txt`` into the root *before* it
  returns. So the safe path wrote into published data.
* Phase 20 removed exactly this defect from the shell collection scripts and
  never reached this one, because that sweep only looked at shell scripts.

Every assertion here is on a refusal. ``docs/26`` §3 rule 13: a gate nobody has
watched fire has been shown to be quiet, not to work.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import run_matrix  # noqa: E402


FROZEN = ROOT / "experiments" / "results" / "matrix"


def test_no_results_root_is_refused_with_exit_2(capsys):
    """A caller who has not said where results go has not decided."""
    code = run_matrix.main(["--regime", "redis-kill-preack"])

    assert code == 2
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert "--results-root is required" in out


def test_plan_only_is_also_refused(capsys):
    """The documented "safe" path is the one that wrote into the frozen root."""
    code = run_matrix.main(["--plan-only"])

    assert code == 2
    assert "REFUSED" in capsys.readouterr().out


def test_an_explicitly_empty_results_root_is_refused(capsys):
    """``not arguments.results_root``, not ``is None``.

    An empty string is not a decision either -- the same distinction phase 19's
    run-count gate got wrong in the other direction with ``${VAR:-default}``.
    """
    code = run_matrix.main(["--results-root", "", "--plan-only"])

    assert code == 2
    assert "REFUSED" in capsys.readouterr().out


def test_the_module_exposes_no_default_results_root():
    """The constant's existence was the hazard, so it must be gone.

    A refusal in ``main`` alone would leave the old value importable and one
    ``default=`` away from returning.
    """
    assert not hasattr(run_matrix, "DEFAULT_RESULTS_ROOT")


def test_the_parser_carries_no_default_and_none_can_be_reintroduced():
    """The parser is built inside ``main``, so this reads the source.

    That is the weaker kind of check and the right one here: what a reviewer
    sees is the ``default=`` on the argument, and a refusal in ``main`` would
    still pass if someone put the old value back on the parser.
    """
    source = (ROOT / "experiments" / "run_matrix.py").read_text(encoding="utf-8")

    assert '"--results-root", default=None' in source
    assert "default=DEFAULT_RESULTS_ROOT" not in source
    assert 'DEFAULT_RESULTS_ROOT = "experiments/results/matrix"' not in source


def test_the_frozen_matrix_root_is_untouched_by_a_refused_invocation():
    """The point of the whole exercise.

    Records what is in the frozen root, runs every refused form, and checks
    nothing there moved. Skipped rather than faked if the root is absent.
    """
    if not FROZEN.is_dir():
        pytest.skip("the frozen matrix root is not in this checkout")

    before = {p.relative_to(FROZEN).as_posix(): p.stat().st_mtime_ns
              for p in FROZEN.rglob("*") if p.is_file()}

    for argv in ([], ["--plan-only"], ["--results-root", ""],
                 ["--regime", "redis-kill-preack"]):
        assert run_matrix.main(argv) == 2

    after = {p.relative_to(FROZEN).as_posix(): p.stat().st_mtime_ns
             for p in FROZEN.rglob("*") if p.is_file()}

    assert before == after, "a refused invocation modified the frozen root"
