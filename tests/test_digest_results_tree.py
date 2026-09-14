"""Exercise ``scripts/digest_results_tree.py`` on the branches where it fails.

``docs/26`` §3 rule 13. This tool exists because `SHA256SUMS` was believed to
cover something it did not, so a tool that *also* quietly covered less than
claimed would repeat the defect one level down. Every way it can fail to detect
a change is exercised here against a tree built for the purpose.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "digest_results_tree.py"


def load():
    spec = importlib.util.spec_from_file_location("digest_results_tree", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["digest_results_tree"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dt():
    return load()


@pytest.fixture
def tree(tmp_path):
    """Two run directories and an analysis directory, as a step root looks."""
    root = tmp_path / "step"
    for name in ("sys-a-r0", "sys-a-r1"):
        run = root / name
        run.mkdir(parents=True)
        (run / "summary.json").write_text('{"agrees": true}\n', encoding="utf-8")
        (run / "events.jsonl").write_text('{"event":"x"}\n', encoding="utf-8")
        (run / "ground_truth.sqlite3").write_bytes(b"SQLite format 3\x00payload")
        # Volatile side files: present, and deliberately not covered.
        (run / "ground_truth.sqlite3-wal").write_bytes(b"wal-one")
        (run / "ground_truth.sqlite3-shm").write_bytes(b"shm-one")
    analysis = root / "analysis"
    analysis.mkdir()
    (analysis / "per-cell-metrics.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    return root


# --------------------------------------------------------------------------
# What it covers.
# --------------------------------------------------------------------------


def test_write_then_check_passes_on_an_untouched_tree(dt, tree, capsys):
    dt.write(tree)
    assert dt.check(tree) == 0
    assert "0 missing, 0 added, 0 changed" in capsys.readouterr().out


def test_the_digest_file_states_its_temporal_limitation(dt, tree):
    out = dt.write(tree)
    text = out.read_text(encoding="utf-8")
    assert "does NOT" in text and "retroactively bind" in text
    assert "tree digest:" in text
    assert "phase 17" in text


def test_it_is_verifiable_by_sha256sum_itself(dt, tree):
    """The format must be the standard one, comments and all.

    A bespoke format would mean the only thing that can check the artifact is
    the thing that wrote it, which is the shape R14 warns about.
    """
    out = dt.write(tree)
    lines = [l for l in out.read_text(encoding="utf-8").splitlines()
             if l and not l.startswith("#")]
    assert lines, "no checkable lines"
    for line in lines:
        digest, _, rel = line.partition("  ")
        assert len(digest) == 64 and rel


# --------------------------------------------------------------------------
# The branches where it must fail.
# --------------------------------------------------------------------------


def test_a_changed_file_is_detected(dt, tree, capsys):
    dt.write(tree)
    (tree / "sys-a-r0" / "summary.json").write_text(
        '{"agrees": false}\n', encoding="utf-8")
    assert dt.check(tree) == 1
    out = capsys.readouterr().out
    assert "CHANGED" in out and "summary.json" in out


def test_a_changed_ledger_is_detected(dt, tree, capsys):
    """The ground-truth ledger is the file a result would be forged in."""
    dt.write(tree)
    (tree / "sys-a-r1" / "ground_truth.sqlite3").write_bytes(b"SQLite format 3\x00EDITED")
    assert dt.check(tree) == 1
    assert "CHANGED" in capsys.readouterr().out


def test_a_deleted_file_is_detected(dt, tree, capsys):
    dt.write(tree)
    (tree / "sys-a-r0" / "events.jsonl").unlink()
    assert dt.check(tree) == 1
    assert "MISSING" in capsys.readouterr().out


def test_an_added_file_is_detected(dt, tree, capsys):
    dt.write(tree)
    (tree / "sys-a-r1" / "smuggled.jsonl").write_text("{}\n", encoding="utf-8")
    assert dt.check(tree) == 1
    assert "ADDED" in capsys.readouterr().out


def test_a_whole_run_directory_removed_is_detected(dt, tree, capsys):
    import shutil
    dt.write(tree)
    shutil.rmtree(tree / "sys-a-r1")
    assert dt.check(tree) == 1
    assert "MISSING" in capsys.readouterr().out


def test_the_tree_digest_changes_when_any_run_changes(dt, tree):
    _l, _p, before = dt.digest_tree(tree)
    (tree / "sys-a-r0" / "summary.json").write_text('{"agrees": 0}\n', encoding="utf-8")
    _l, _p, after = dt.digest_tree(tree)
    assert before != after


def test_check_on_a_tree_with_no_digest_file_fails(dt, tree, capsys):
    """Absent must not read as clean."""
    assert dt.check(tree) == 1
    assert "does not exist" in capsys.readouterr().out


# --------------------------------------------------------------------------
# The documented exclusion, asserted rather than trusted.
# --------------------------------------------------------------------------


def test_sqlite_side_files_are_excluded_and_touching_them_does_not_fail(dt, tree):
    """Documented exclusion: -wal and -shm are rewritten by any open.

    Asserted because a docstring claim nobody checks is how the SHA256SUMS
    scope error happened in the first place.
    """
    dt.write(tree)
    (tree / "sys-a-r0" / "ground_truth.sqlite3-wal").write_bytes(b"reopened")
    (tree / "sys-a-r0" / "ground_truth.sqlite3-shm").write_bytes(b"reopened")
    assert dt.check(tree) == 0


def test_the_analysis_directory_is_not_treated_as_a_run(dt, tree):
    runs = [p.name for p in dt.run_directories(tree)]
    assert "analysis" not in runs
    assert sorted(runs) == ["sys-a-r0", "sys-a-r1"]


def test_main_rejects_a_missing_root(dt, tmp_path):
    assert dt.main(["--results-root", str(tmp_path / "nope")]) == 2
