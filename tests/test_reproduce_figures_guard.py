"""Exercise the ``reproduce-figures`` analysis-figure guard, as a clone hits it.

The guard in ``Makefile`` decides whether the two analysis figures can be
regenerated: it counts run directories under ``RUNS`` and compares that count
with the archive's own ``MANIFEST.md``. It has three outcomes -- regenerate,
skip because the tree is partial, skip because there are no runs at all -- and
the third is the one every evaluator meets, because a clone carries the analysis
products and never the raw runs.

That third branch was unreachable. ``.SHELLFLAGS`` is ``-eu -o pipefail``
(Makefile:34) and the manifest was read as ``sed ... 2>/dev/null | head -1``:
with no manifest ``sed`` exits 2, ``pipefail`` promotes it, ``-e`` aborts the
recipe, and ``make`` reports ``Error 2`` before the skip message. The target
failed in precisely the situation it had a paragraph of prose explaining how to
handle. Found by running it in a clean clone (phase 39).

``docs/26`` §3 rule 13: the branch is exercised here, and the pre-fix form is
exercised beside it, so the test is watched failing against the defect and not
only passing against the fix.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

# The pre-fix line, kept verbatim so the regression test is against the real
# thing and not a paraphrase of it.
PRE_FIX = (
    'want=$$(sed -n "s/^- completed runs: '
    r"\*\*\([0-9]\+\)\*\*.*/\1/p"
    '" "$(RUNS)/MANIFEST.md" 2>/dev/null | head -1)'
)


def extract_guard() -> str:
    """Lift the guard's recipe lines out of the Makefile, verbatim."""
    lines = MAKEFILE.read_text(encoding="utf-8").split("\n")
    start = next(
        i for i, ln in enumerate(lines) if ln.strip().startswith("have=$$(find")
    )
    out, seen_else = [], False
    for ln in lines[start:]:
        out.append(ln)
        if ln.strip() == "else":
            seen_else = True
        elif seen_else and ln.strip() == "fi":
            break
    else:  # pragma: no cover - would mean the recipe was restructured
        pytest.fail("could not find the end of the analysis-figure guard")
    return "\n".join(out)


def run_guard(body: str, archive: Path, figroot: Path):
    """Expand the make variables and run the guard the way make runs it."""
    script = (
        body.replace("$(RUNS)", archive.as_posix())
        .replace("$(FIG_ROOT)", figroot.as_posix())
        .replace("$(UV)", "uv")
    )
    script = "\n".join(ln[1:] if ln.startswith("\t") else ln for ln in script.split("\n"))
    script = script.replace("$$", "$")
    # failed= is set earlier in the recipe; -u would otherwise reject the
    # reference in the branch that is not taken.
    return subprocess.run(
        ["bash", "-eu", "-o", "pipefail", "-c", "failed=0\n" + script],
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def archive(tmp_path: Path) -> Path:
    d = tmp_path / "archive"
    (d / "analysis").mkdir(parents=True)
    (d / "analysis" / "outcomes.csv").write_text("cell,n\n", encoding="utf-8")
    return d


def test_clean_clone_is_the_no_runs_branch(archive: Path, tmp_path: Path) -> None:
    """Analysis products, no run directories, no manifest -- what a clone has."""
    r = run_guard(extract_guard(), archive, tmp_path / "fig")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SKIPPED" in r.stdout
    assert "no run directories" in r.stdout


def test_the_skip_message_says_how_to_get_the_figures(
    archive: Path, tmp_path: Path
) -> None:
    """A skip that does not say what would un-skip it is a dead end."""
    r = run_guard(extract_guard(), archive, tmp_path / "fig")
    assert "RUNS=" in r.stdout


def test_partial_tree_skips_rather_than_reporting_a_moved_value(
    archive: Path, tmp_path: Path
) -> None:
    """84 of 432 is a rescued snapshot, not a disagreement about the data."""
    for i in range(3):
        (archive / f"t1-b0-p0-r{i}").mkdir()
    (archive / "MANIFEST.md").write_text(
        "# archive\n\n- completed runs: **432**\n", encoding="utf-8"
    )
    r = run_guard(extract_guard(), archive, tmp_path / "fig")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "holds 3 run directories" in r.stdout
    assert "records 432" in r.stdout


def test_missing_manifest_does_not_abort_the_recipe(
    archive: Path, tmp_path: Path
) -> None:
    """The pre-fix form, run against the same clean-clone tree, exits 2.

    This is the defect, executed. If this ever stops exiting non-zero the
    Makefile has been changed in a way that makes the test above vacuous.
    """
    body = extract_guard()
    assert PRE_FIX not in body, "the pre-fix manifest read is back in the Makefile"

    lines = body.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "want=")
    end = next(i for i, ln in enumerate(lines[start:], start) if ln.strip() == "fi")
    broken = lines[:start] + ["\t" + PRE_FIX] + lines[end + 1 :]

    r = run_guard("\n".join(broken), archive, tmp_path / "fig")
    assert r.returncode == 2, (
        "the pre-fix form no longer reproduces the abort; "
        f"exit={r.returncode}\n{r.stdout}{r.stderr}"
    )
    assert "SKIPPED" not in r.stdout, "it aborted before printing anything"


def test_guard_is_still_where_the_test_thinks_it_is() -> None:
    """R14: a test that cannot find its subject must say so, not pass."""
    body = extract_guard()
    assert 'if [[ -f "$(RUNS)/MANIFEST.md" ]]; then' in body
    assert body.strip().endswith("fi")
    assert "elif" in body and "else" in body
