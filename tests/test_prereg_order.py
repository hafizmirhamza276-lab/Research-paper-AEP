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


def record_blobs(repo, table):
    """Write the repo's own blob record, as --update-blobs would."""
    import json as _json
    blobs = {rel: {"first": audit.first_blob(rel, repo),
                   "current": audit.head_blob(rel, repo)}
             for rel in audit.prediction_paths(table)}
    out = repo / "reports" / "prereg-blobs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps({"blobs": blobs}), encoding="utf-8")


def test_prediction_before_data_passes(tmp_path, capsys):
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    table = {CELL: audit.Cell(PRED, None)}
    record_blobs(repo, table)
    code = audit.audit(repo, table)
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
    table = {CELL: audit.Cell(None, None, predates_rule=True)}
    record_blobs(repo, table)
    code = audit.audit(repo, table)
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


# --------------------------------------------------------------------------
# The content gap phase 37 named: the audit reads commit ORDER, never the
# prediction's CONTENT, so a file committed early and rewritten later passed.
# These exercise the comparison that closes it.
# --------------------------------------------------------------------------

import json  # noqa: E402


def blobs_file(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "prereg-blobs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_an_edited_prediction_is_detected(tmp_path, capsys):
    """Rule 13. The prediction is committed, then rewritten, then checked."""
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    table = {CELL: audit.Cell(PRED, None)}
    first = audit.first_blob(PRED, repo)

    # The rewrite, after the data landed.
    commit(repo, PRED, "x\nsomething added after the results\n",
           "2026-01-03T09:00:00")

    record = blobs_file(tmp_path, {"blobs": {PRED: {"first": first,
                                                    "current": first}}})
    problems = audit.check_blobs(repo, table, record)

    assert problems, "an edited pre-registration went undetected"
    assert any("EDITED" in p for p in problems), problems


def test_an_unexplained_first_current_divergence_is_flagged(tmp_path):
    """A record written from an already-edited history must not bless it.

    The two blobs differ, both match what git says, and nothing in EDITED
    explains why -- which is the shape that would otherwise absorb an edit
    simply by recording it.
    """
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    commit(repo, PRED, "x\nedited\n", "2026-01-03T09:00:00")
    table = {CELL: audit.Cell(PRED, None)}
    record = blobs_file(tmp_path, {"blobs": {PRED: {
        "first": audit.first_blob(PRED, repo),
        "current": audit.head_blob(PRED, repo),
    }}})

    problems = audit.check_blobs(repo, table, record)
    assert any("nobody has said why" in p for p in problems), problems


def test_a_classified_edit_passes_but_a_further_one_does_not(tmp_path):
    """An EDITED entry records a ruling; it does not open the door."""
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    commit(repo, PRED, "x\nedited once\n", "2026-01-03T09:00:00")
    table = {CELL: audit.Cell(PRED, None)}
    record = blobs_file(tmp_path, {"blobs": {PRED: {
        "first": audit.first_blob(PRED, repo),
        "current": audit.head_blob(PRED, repo),
        "edited": "examined and classified",
    }}})
    assert not audit.check_blobs(repo, table, record)

    commit(repo, PRED, "x\nedited twice\n", "2026-01-04T09:00:00")
    problems = audit.check_blobs(repo, table, record)
    assert any("EDITED" in p for p in problems), problems


def test_a_prediction_with_no_recorded_blob_fails(tmp_path):
    """Adding a pre-registration without recording it must not be silent."""
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    record = blobs_file(tmp_path, {"blobs": {}})
    problems = audit.check_blobs(repo, {CELL: audit.Cell(PRED, None)}, record)
    assert any("no recorded blob" in p for p in problems), problems


# --------------------------------------------------------------------------
# --update-blobs writes LF, on every platform.
#
# `Path.write_text` defaults to `newline=None`, which on Windows translates
# every "\n" it is given into "\r\n". The measurement host is Windows, so the
# first --update-blobs run there rewrote all 59 lines of prereg-blobs.json --
# a file whose entire purpose is to make a real change visible. The one-line
# addition it had been run for was buried in the churn, and two sessions hit
# it before it was pinned.
#
# TWO assertions, because one of them is a no-op half the time:
#   * the bytes carry no CRLF -- real on Windows, trivially true on Linux;
#   * the call passes newline="\n" -- fails on EVERY platform if the argument
#     is dropped, which is what makes this a guard rather than a local habit.
# --------------------------------------------------------------------------


def test_update_blobs_pins_the_line_ending_on_every_platform(
    tmp_path, monkeypatch, capsys
):
    repo = make_repo(tmp_path, [(PRED, "2026-01-01T09:00:00"),
                                (DATA, "2026-01-02T09:00:00")])
    target = tmp_path / "prereg-blobs.json"
    monkeypatch.setattr(audit, "BLOBS", target)

    seen: dict = {}
    original = Path.write_text

    def spy(self, data, *args, **kwargs):
        if self.name == "prereg-blobs.json":
            seen.clear()
            seen.update(kwargs)
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy)

    assert audit.write_blobs(repo, {CELL: audit.Cell(PRED, None)}) == 0
    capsys.readouterr()

    assert seen.get("newline") == "\n", (
        "write_blobs must pass newline='\n' to write_text. Without it "
        "Path.write_text uses os.linesep, and on Windows --update-blobs "
        "rewrites the whole record instead of the line it changed."
    )

    raw = target.read_bytes()
    assert b"\r\n" not in raw, (
        "prereg-blobs.json carries CRLF; it is a tracked record whose diffs "
        "are read by humans and must stay LF on every platform"
    )
    assert raw.endswith(b"\n")
    # And it is still the record it claims to be.
    assert json.loads(raw.decode("utf-8"))["blobs"][PRED]["first"]
