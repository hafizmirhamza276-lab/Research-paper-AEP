"""Exercise the guard that makes ``docs/25`` R16 a mechanism.

R16 -- "a test that inspects a destructive script must not execute it" -- was
written after a parametrised test executed ``fsync_always_benchmark.sh`` and its
default-on clean path deleted sixty executions of published data. A rule alone
does not stop the next one. ``scripts/results_root_guard.sh`` does, by
removing the two properties that made it possible: a compiled-in default results
root, and a delete that nothing had to consent to.

Every assertion here is on a *refusal*. ``docs/26`` §3 rule 13: a gate that has
never been watched firing has been shown to be quiet, not to work. These are
watched firing against the scripts as they stand, and against the pre-guard
versions they replace.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "results_root_guard.sh"
FSYNC = ROOT / "scripts" / "fsync_always_benchmark.sh"
MATRIX = ROOT / "scripts" / "wsl_launch_matrix.sh"

MARKER = ".aep-scratch-results-root"


def bash(snippet: str, cwd: Path | None = None, env: dict | None = None):
    """Run a bash snippet with the guard sourced."""
    script = f'set -uo pipefail\n. "{GUARD.as_posix()}"\n{snippet}\n'
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


# --------------------------------------------------------------------- 1
# No default root. An unset variable is a refusal, not a guess.
# --------------------------------------------------------------------- 1

def test_an_unset_results_root_is_refused_with_exit_2():
    result = bash("unset NOWHERE\naep_require_explicit_results_root NOWHERE")
    assert result.returncode == 2
    assert "REFUSING" in result.stderr
    assert "no default results root" in result.stderr


def test_an_explicitly_empty_results_root_is_also_refused():
    """``-z`` not ``-n``: an empty string is not a decision either.

    The phase 19 run-count gate had exactly this bug in reverse -- ``${VAR:-d}``
    silently accepted an empty value as the default.
    """
    result = bash('EMPTY=""\naep_require_explicit_results_root EMPTY')
    assert result.returncode == 2


def test_a_named_root_is_accepted():
    result = bash('R="/tmp/somewhere"\naep_require_explicit_results_root R')
    assert result.returncode == 0


# --------------------------------------------------------------------- 2
# A populated root is never written into.
# --------------------------------------------------------------------- 2

def test_a_populated_results_root_is_refused_with_exit_3(tmp_path):
    root = tmp_path / "already-collected"
    (root / "sys-a-r0").mkdir(parents=True)
    (root / "sys-a-r0" / "summary.json").write_text("{}", encoding="utf-8")

    result = bash(f'aep_refuse_nonempty_results_root "{root.as_posix()}"')
    assert result.returncode == 3
    assert "already exists and is not empty" in result.stderr


def test_an_absent_or_empty_root_is_accepted(tmp_path):
    absent = tmp_path / "not-yet"
    assert bash(f'aep_refuse_nonempty_results_root "{absent.as_posix()}"').returncode == 0

    empty = tmp_path / "empty"
    empty.mkdir()
    assert bash(f'aep_refuse_nonempty_results_root "{empty.as_posix()}"').returncode == 0


# --------------------------------------------------------------------- 3
# The delete requires consent. Rule 9's marker, moved to the filesystem.
# --------------------------------------------------------------------- 3

def test_deleting_a_results_root_without_the_marker_is_refused(tmp_path):
    """This is the assertion that would have refused phase 19."""
    root = tmp_path / "frozen-looking"
    (root / "aep_full-none-payments-r0").mkdir(parents=True)
    (root / "aep_full-none-payments-r0" / "summary.json").write_text(
        "{}", encoding="utf-8")

    result = bash(f'aep_guarded_rm_results "{root.as_posix()}"')

    assert result.returncode == 4
    assert "has not" in result.stderr and "disposable" in result.stderr
    assert root.is_dir(), "the guard must not delete an unmarked root"
    assert (root / "aep_full-none-payments-r0" / "summary.json").is_file()


def test_a_marked_scratch_root_may_be_deleted(tmp_path):
    root = tmp_path / "scratch"
    result = bash(
        f'aep_mark_results_root_scratch "{root.as_posix()}"\n'
        f'aep_guarded_rm_results "{root.as_posix()}"'
    )
    assert result.returncode == 0
    assert not root.exists()


def test_the_marker_cannot_be_satisfied_by_a_directory_of_that_name(tmp_path):
    """``-f``, not ``-e``. A directory named like the marker does not consent."""
    root = tmp_path / "sneaky"
    (root / MARKER).mkdir(parents=True)

    result = bash(f'aep_guarded_rm_results "{root.as_posix()}"')
    assert result.returncode == 4
    assert root.is_dir()


def test_deleting_root_or_the_empty_string_is_refused():
    assert bash('aep_guarded_rm_results ""').returncode == 4
    assert bash('aep_guarded_rm_results "/"').returncode == 4


def test_deleting_something_that_does_not_exist_is_a_no_op(tmp_path):
    assert bash(
        f'aep_guarded_rm_results "{(tmp_path / "gone").as_posix()}"').returncode == 0


# --------------------------------------------------------------------- 4
# The scripts themselves, invoked as a careless caller would invoke them.
# --------------------------------------------------------------------- 4

def test_fsync_benchmark_refuses_to_run_with_no_results_root(tmp_path):
    """The bare invocation its own usage header used to document.

    On 2026-09-14 this exact call deleted `experiments/results/fsync-always`.
    It must now exit 2 before reaching Docker, the config file, or anything
    that touches a filesystem path.
    """
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    result = subprocess.run(
        ["bash", str(FSYNC)],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert result.returncode == 2, result.stderr
    assert "AEP_FSYNC_RESULTS_ROOT is not set" in result.stderr


def test_fsync_benchmark_refuses_a_populated_results_root(tmp_path):
    """And it refuses before starting a container, not after."""
    root = tmp_path / "populated"
    (root / "run-r0").mkdir(parents=True)
    (root / "run-r0" / "summary.json").write_text("{}", encoding="utf-8")

    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "AEP_FSYNC_RESULTS_ROOT": root.as_posix(),
        "AEP_FSYNC_RUNS": "not-a-number",
    }
    result = subprocess.run(
        ["bash", str(FSYNC)],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    # The run-count gate fires first and is also a refusal; either way the
    # script must stop with a refusal and must not have touched the root.
    assert result.returncode in (2, 3), result.stderr
    assert (root / "run-r0" / "summary.json").is_file()


def test_the_matrix_launcher_refuses_to_default_to_the_frozen_root(tmp_path):
    """`RESULTS_ROOT` defaulted to the frozen 432-run `matrix` root.

    Second instance of the R16 shape. A bare invocation aimed a resumable
    collection at the directory every outcome rate in the paper comes from.
    """
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "AEP_LINUX_TREE": str(tmp_path)}
    result = subprocess.run(
        ["bash", str(MATRIX)],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert result.returncode == 2, result.stderr
    assert "RESULTS_ROOT is not set" in result.stderr


# --------------------------------------------------------------------- 5
# No collection script may reacquire a default or an unguarded delete.
# --------------------------------------------------------------------- 5

COLLECTION_SCRIPTS = [
    ROOT / "scripts" / "fsync_always_benchmark.sh",
    ROOT / "scripts" / "wsl_launch_matrix.sh",
    ROOT / "scripts" / "launch_ws5_collection.sh",
]


@pytest.mark.parametrize("script", COLLECTION_SCRIPTS, ids=lambda p: p.name)
def test_no_collection_script_recursively_deletes_a_results_path(script):
    """A source assertion, and deliberately a source assertion.

    R16's own lesson is that *executing* a collection script to test it is how
    the data was lost. So this check reads the text. It is the weaker kind of
    check and it is the right kind here.
    """
    text = script.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "rm -rf" in stripped:
            assert "aep_guarded_rm_results" in stripped, (
                f"{script.name}: unguarded recursive delete: {stripped}"
            )


def test_the_guard_is_tracked_by_git():
    """The near-miss this file exists to prevent recurring.

    The guard was first written to `scripts/lib/`, which `.gitignore:14`
    ignores via a broad `lib/` rule. Committed there it would have been
    absent from every clone, both collection scripts would have died at
    their `source` line, and every test above would have failed in CI -- a
    load-bearing file invisible to the one tool everyone checks.
    """
    result = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", str(GUARD)],
        capture_output=True,
    )
    # check-ignore exits 1 when the path is NOT ignored, which is what we want.
    assert result.returncode == 1, (
        f"{GUARD} is gitignored; it would be absent from every clone"
    )
