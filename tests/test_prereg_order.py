"""The rule-5 order audit, watched failing on every branch it can fail on.

``docs/26`` §3 rule 13. ``docs/25`` R17 governs how: **nothing here touches the
real history.** Each case builds a throwaway git repository in ``tmp_path`` with
commits in a chosen order and runs the current audit over it, so a violation is
constructed rather than hunted for.

That matters more than usual here. The audit's own subject is commit order, and
the one thing it must never do is repair history to make itself pass — so the
failing branch has to be demonstrated somewhere disposable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_prereg_order as audit  # noqa: E402


def run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


def commit(repo: Path, rel: str, body: str, when: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    run(repo, "add", rel)
    env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", rel, "--no-gpg-sign"],
        check=True, capture_output=True,
        env={**dict(__import__("os").environ), **env},
    )


def make_repo(tmp_path: Path, order: list[tuple[str, str]]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(repo, "init", "-q", "-b", "main")
    run(repo, "config", "user.email", "t@example.invalid")
    run(repo, "config", "user.name", "T")
    for rel, when in order:
        commit(repo, rel, "x\n", when)
    return repo


PRED = "reports/phase-report-x-prediction-2026-01-01.md"
DATA = "experiments/results/cell-2026-01-02/MANIFEST.md"
CELL = "experiments/results/cell-2026-01-02"


def test_prediction_before_data_passes(tmp_path, capsys):
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    code = audit.audit(repo, {CELL: audit.Cell(PRED, None)})
    capsys.readouterr()
    assert code == 0


def test_prediction_after_data_fails(tmp_path, capsys):
    """Rule 13: the violation the whole audit exists to catch."""
    repo = make_repo(tmp_path, [(DATA, "2026-01-01T09:00:00"),
                                (PRED, "2026-01-02T09:00:00")])
    code = audit.audit(repo, {CELL: audit.Cell(PRED, None)})
    out = capsys.readouterr().out
    assert code == 1
    assert "AFTER first data" in out


def test_a_collection_with_no_table_entry_fails(tmp_path, capsys):
    """The finding the audit is built to surface.

    Enumeration runs from the data, so a cell nobody pre-registered cannot hide
    by being absent from the prediction list.
    """
    repo = make_repo(tmp_path, [(DATA, "2026-01-02T09:00:00")])
    code = audit.audit(repo, {})
    out = capsys.readouterr().out
    assert code == 1
    assert "no entry in EXPECTED" in out


def test_a_prediction_missing_from_history_fails(tmp_path, capsys):
    """A path that names nothing must fail, not skip.

    This is not hypothetical: the first run of this audit against the real
    history failed exactly here, on a mistyped prompt filename.
    """
    repo = make_repo(tmp_path, [(DATA, "2026-01-02T09:00:00")])
    code = audit.audit(repo, {CELL: audit.Cell("reports/nope.md", None)})
    out = capsys.readouterr().out
    assert code == 1
    assert "not in the history" in out


def test_ancestry_is_checked_and_not_only_the_date(tmp_path, capsys):
    """Dates and ancestry disagree after a rewrite; both must hold.

    The prediction is committed on an unmerged branch, so its DATE precedes the
    data while it is not reachable from the data commit. A date-only check
    passes this; the audit must not.
    """
    repo = make_repo(tmp_path, [("seed.txt", "2026-01-01T08:00:00")])
    run(repo, "checkout", "-q", "-b", "side")
    commit(repo, PRED, "x\n", "2026-01-01T09:00:00")
    run(repo, "checkout", "-q", "main")
    commit(repo, DATA, "x\n", "2026-01-02T09:00:00")

    code = audit.audit(repo, {CELL: audit.Cell(PRED, None)})
    out = capsys.readouterr().out
    assert code == 1
    assert "not an ancestor" in out


def test_an_exempt_cell_is_reported_not_hidden(tmp_path, capsys):
    """A pre-rule cell is EXEMPT, and says so in the table.

    Exempt must be visible. A cell that silently vanished from the output would
    be the audit's own R14 instance.
    """
    repo = make_repo(tmp_path, [(DATA, "2026-01-02T09:00:00")])
    code = audit.audit(repo, {CELL: audit.Cell(None, None, predates_rule=True)})
    out = capsys.readouterr().out
    assert code == 0
    assert "EXEMPT" in out
    assert CELL in out


def test_the_domain_is_printed_every_run(tmp_path, capsys):
    """Ten R14 instances: a green check means green over what it can see."""
    repo = make_repo(tmp_path, [(DATA, "2026-01-02T09:00:00")])
    audit.audit(repo, {CELL: audit.Cell(None, None, predates_rule=True)})
    out = capsys.readouterr().out
    assert "DOES NOT" in out
    assert "COLLECTED" in out
