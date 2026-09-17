"""Exercise ``scripts/check_line_endings.py`` on the branches where it fails.

``docs/26`` §3 rule 13. This gate exists because three commits in one session
rewrote a CRLF file as LF and one of them shipped: ``b379809``'s real change was
44 insertions and 7 deletions, and it reads as 885/833. A gate that only ever
reports clean has been shown to be quiet, not to work, so every refusal below is
watched firing against a repository built for the purpose.

The fixtures are **real git repositories in tmp_path**, not the project's own.
Asserting against this repository's history would make the test pass or fail on
what someone commits next, and it would not run in a shallow clone.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_line_endings.py"


def load(repo: Path):
    """Load the gate with ROOT pointed at a throwaway repository."""
    spec = importlib.util.spec_from_file_location("check_line_endings", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_line_endings"] = module
    spec.loader.exec_module(module)
    module.ROOT = repo
    return module


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repository whose first commit holds one CRLF file and one LF file."""
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.invalid")
    git(r, "config", "user.name", "t")
    git(r, "config", "core.autocrlf", "false")
    (r / "windows.md").write_bytes(b"alpha\r\nbeta\r\ngamma\r\n")
    (r / "unix.md").write_bytes(b"alpha\nbeta\ngamma\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "first")
    return r


def run(module, **kwargs) -> int:
    return module.check(kwargs.pop("before", None), kwargs.pop("staged", False),
                        kwargs.pop("commit", None), kwargs.pop("allow", ()))


# --------------------------------------------------------------------------
# The refusals.
# --------------------------------------------------------------------------


def test_crlf_rewritten_as_lf_is_refused(repo, capsys):
    """The exact accident that shipped as b379809."""
    (repo / "windows.md").write_bytes(b"alpha\nbeta\nGAMMA\n")
    git(repo, "commit", "-q", "-am", "edit one word")
    module = load(repo)
    assert run(module, commit="HEAD") == 1
    out = capsys.readouterr().out
    assert "windows.md" in out
    assert "crlf" in out and "lf" in out


def test_lf_rewritten_as_crlf_is_refused(repo, capsys):
    """The same defect in the other direction, which the repair commit was."""
    (repo / "unix.md").write_bytes(b"alpha\r\nbeta\r\nGAMMA\r\n")
    git(repo, "commit", "-q", "-am", "edit one word")
    module = load(repo)
    assert run(module, commit="HEAD") == 1
    assert "unix.md" in capsys.readouterr().out


def test_a_content_edit_that_keeps_its_endings_passes(repo, capsys):
    (repo / "windows.md").write_bytes(b"alpha\r\nbeta\r\nGAMMA\r\ndelta\r\n")
    (repo / "unix.md").write_bytes(b"alpha\nbeta\nGAMMA\n")
    git(repo, "commit", "-q", "-am", "edit both, keep endings")
    module = load(repo)
    assert run(module, commit="HEAD") == 0
    assert "no file changed its dominant line ending" in capsys.readouterr().out


def test_a_named_flip_is_allowed(repo, capsys):
    """A deliberate normalisation passes only when named on the command line."""
    (repo / "windows.md").write_bytes(b"alpha\nbeta\ngamma\n")
    git(repo, "commit", "-q", "-am", "normalise deliberately")
    module = load(repo)
    assert run(module, commit="HEAD", allow=("windows.md",)) == 0
    assert "ALLOWED flip" in capsys.readouterr().out


def test_allowing_a_different_path_does_not_excuse_this_one(repo):
    (repo / "windows.md").write_bytes(b"alpha\nbeta\ngamma\n")
    git(repo, "commit", "-q", "-am", "normalise")
    module = load(repo)
    assert run(module, commit="HEAD", allow=("some/other/file.md",)) == 1


# --------------------------------------------------------------------------
# What it must not do.
# --------------------------------------------------------------------------


def test_a_new_file_is_not_a_flip(repo, capsys):
    """A file with no previous blob has nothing to have flipped from."""
    (repo / "new.md").write_bytes(b"alpha\r\nbeta\r\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add a CRLF file")
    module = load(repo)
    assert run(module, commit="HEAD") == 0


def test_a_deleted_file_is_not_a_flip(repo):
    git(repo, "rm", "-q", "windows.md")
    git(repo, "commit", "-q", "-m", "delete")
    module = load(repo)
    assert run(module, commit="HEAD") == 0


def test_binary_files_are_skipped(repo, capsys):
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02\r\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add binary")
    (repo / "blob.bin").write_bytes(b"\x00\x01\x03\n")
    git(repo, "commit", "-q", "-am", "change binary")
    module = load(repo)
    assert run(module, commit="HEAD") == 0
    assert "0 modified text file(s) compared" in capsys.readouterr().out


def test_a_single_line_file_with_no_terminator_is_not_a_flip(repo):
    """'none' on either side is not a direction, so it cannot flip."""
    (repo / "bare.md").write_bytes(b"no terminator")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add")
    (repo / "bare.md").write_bytes(b"still no terminator")
    git(repo, "commit", "-q", "-am", "edit")
    module = load(repo)
    assert run(module, commit="HEAD") == 0


def test_the_staged_path_sees_the_index_before_a_commit_exists(repo, capsys):
    """The pre-commit use: catch it before it is in the history at all."""
    (repo / "windows.md").write_bytes(b"alpha\nbeta\ngamma\n")
    git(repo, "add", "windows.md")
    module = load(repo)
    assert run(module, staged=True) == 1
    assert "the index" in capsys.readouterr().out


# --------------------------------------------------------------------------
# The profiler itself.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"a\r\nb\r\n", "crlf"),
        (b"a\nb\n", "lf"),
        (b"a\r\nb\n", "mixed"),
        (b"abc", "none"),
        (b"", "none"),
    ],
)
def test_profile_classifies(data, expected):
    module = load(ROOT)
    assert module.profile(data)[0] == expected


def test_evidence_paths_are_flagged_not_skipped(repo, capsys):
    """A flip under a results path is worse, and must still fail."""
    d = repo / "experiments" / "results"
    d.mkdir(parents=True)
    (d / "per-cell-metrics.csv").write_bytes(b"a,b\r\n1,2\r\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add frozen csv")
    (d / "per-cell-metrics.csv").write_bytes(b"a,b\n1,2\n")
    git(repo, "commit", "-q", "-am", "flip it")
    module = load(repo)
    assert run(module, commit="HEAD") == 1
    assert "tracked evidence" in capsys.readouterr().out
