"""The ceilings in force must be recorded, in the run and in the collection.

`reports/phase-report-40-stage-10-2026-09-21.md` §5.2: auditing the 10-call
stage, the caps could not be established from the archive at all. They were
read from the environment, echoed to a terminal, and written nowhere --
`run-config.json` carries 45 fields and not one of them is a planner cap.

**And that is deliberate, which is why the fix is a separate file.**
`docs/31` §4 keeps planner configuration out of `RunConfig` because
`RunConfig._body()` folds every field into `config_digest`; a cap recorded
there would change the digest of every run and make collections incomparable
across stages. So these tests assert both halves: the record exists, and the
digest does not move.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.harness.planner import (
    CAPS_FILENAME,
    PLANNER_CAPS_SCHEMA_VERSION,
    CallWrapper,
    Caps,
    CumulativeCounter,
    Price,
    caps_echo,
)


def build(tmp_path, caps=None, run_id="r0"):
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    return CallWrapper(run_id=run_id, run_dir=tmp_path / run_id,
                       cumulative=counter, caps=caps)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


# -- the record exists ------------------------------------------------------

def test_the_run_directory_records_the_caps(tmp_path):
    build(tmp_path, Caps(per_run_calls=28, per_collection_calls=10))
    body = read(tmp_path / "r0" / CAPS_FILENAME)
    assert body["in_force"]["per_run_calls"] == 28
    assert body["in_force"]["per_collection_calls"] == 10


def test_the_collection_root_records_the_caps(tmp_path):
    """The per-collection cap and the USD ceiling are collection-wide.

    No single run directory can answer what bounded the collection, which is
    the question those two controls are about.
    """
    build(tmp_path, Caps(per_collection_calls=10))
    body = read(tmp_path / CAPS_FILENAME)
    assert body["in_force"]["per_collection_calls"] == 10


def test_a_missing_caps_record_fails(tmp_path):
    """The known-positive: prove the check above can fail."""
    build(tmp_path, Caps())
    (tmp_path / "r0" / CAPS_FILENAME).unlink()
    assert not (tmp_path / "r0" / CAPS_FILENAME).is_file()
    with pytest.raises(FileNotFoundError):
        read(tmp_path / "r0" / CAPS_FILENAME)


def test_every_cap_that_bounds_spend_is_in_the_record(tmp_path):
    """Named individually, so adding a cap without recording it fails here."""
    build(tmp_path, Caps())
    body = read(tmp_path / "r0" / CAPS_FILENAME)
    for name in ("per_run_calls", "per_collection_calls", "per_collection_usd",
                 "max_prompt_tokens", "max_output_tokens"):
        assert name in body["in_force"], f"{name} is not recorded"
        assert name in body["preregistered_ceiling"], name


def test_the_record_is_versioned(tmp_path):
    build(tmp_path, Caps())
    assert (read(tmp_path / "r0" / CAPS_FILENAME)["schema_version"]
            == PLANNER_CAPS_SCHEMA_VERSION)


# -- what the record is for -------------------------------------------------

def test_the_preregistered_ceiling_is_recorded_beside_what_was_used(tmp_path):
    """``tightened`` must be checkable, not asserted.

    ``stage_caps`` refuses to raise a cap above §3's number. This is the
    evidence in the archive that it did not -- a reader can see both values
    rather than trusting the launcher.
    """
    build(tmp_path, Caps(per_run_calls=28, per_collection_calls=10))
    body = read(tmp_path / "r0" / CAPS_FILENAME)
    assert body["preregistered_ceiling"]["per_run_calls"] == 36
    assert body["preregistered_ceiling"]["per_collection_calls"] == 1000
    assert body["tightened"] == ["per_collection_calls", "per_run_calls"]


def test_an_untightened_collection_records_an_empty_tightened_list(tmp_path):
    build(tmp_path, Caps())
    assert read(tmp_path / "r0" / CAPS_FILENAME)["tightened"] == []


def test_the_price_and_its_source_are_recorded(tmp_path):
    """Amendment 5 C4'(b) reads the price from here, not from the working tree.

    What matters is the price in force when the calls were made; the constant
    in the repository today may have moved since.
    """
    build(tmp_path, Caps())
    body = read(tmp_path / "r0" / CAPS_FILENAME)
    assert body["price"]["input_per_million"] == 0.20
    assert body["price"]["output_per_million"] == 1.20
    assert body["price_source"]["url"].startswith("https://")
    assert body["price_source"]["retrieved"]


def test_the_per_call_ceiling_is_recorded(tmp_path):
    build(tmp_path, Caps())
    body = read(tmp_path / "r0" / CAPS_FILENAME)
    assert body["per_call_ceiling_usd"] == pytest.approx(0.0016288)


# -- the digest must not move ----------------------------------------------

def test_no_cap_leaks_into_the_run_config_digest():
    """docs/31 §4. A cap in RunConfig would change every run's digest.

    Asserted against ``RunConfig``'s own field names rather than a sample
    config, so a field added later fails here.
    """
    from dataclasses import fields

    from experiments.harness.config import RunConfig

    names = {f.name for f in fields(RunConfig)}
    for cap in ("per_run_calls", "per_collection_calls", "per_collection_usd",
                "max_prompt_tokens", "max_output_tokens"):
        assert cap not in names, (
            f"{cap} is a RunConfig field, so it is inside config_digest and "
            f"every stage that tightens it produces incomparable runs"
        )


def test_the_caps_file_is_not_inside_the_run_config():
    """The record is a sibling file, which is what keeps the digest still."""
    from experiments.harness.config import RunConfig

    assert CAPS_FILENAME not in json.dumps(
        {f: str(v) for f, v in vars(RunConfig).items()
         if not f.startswith("__")}
    )


# -- a collection whose caps changed part-way -------------------------------

def test_the_first_writer_wins_and_a_later_difference_is_recorded(tmp_path):
    """First-writer-wins, same rule as the cumulative journal.

    Several worker processes reach this concurrently, and last-writer-wins is
    how the counter lost 598 of 800 increments. A mismatch means the ceiling
    moved mid-collection -- the single thing this record exists to make
    visible -- so it is reported on the run that saw it.
    """
    build(tmp_path, Caps(per_collection_calls=10), run_id="r0")
    build(tmp_path, Caps(per_collection_calls=5), run_id="r1")

    assert read(tmp_path / CAPS_FILENAME)["in_force"][
        "per_collection_calls"] == 10
    assert read(tmp_path / "r0" / CAPS_FILENAME)[
        "collection_caps_differ"] is False
    assert read(tmp_path / "r1" / CAPS_FILENAME)[
        "collection_caps_differ"] is True
    # The run's own record still says what actually bounded it.
    assert read(tmp_path / "r1" / CAPS_FILENAME)["in_force"][
        "per_collection_calls"] == 5


def test_identical_caps_are_not_reported_as_a_difference(tmp_path):
    """The known-negative: the flag must not fire on every run after the first."""
    build(tmp_path, Caps(per_collection_calls=10), run_id="r0")
    build(tmp_path, Caps(per_collection_calls=10), run_id="r1")
    assert read(tmp_path / "r1" / CAPS_FILENAME)[
        "collection_caps_differ"] is False


def test_a_mismatch_does_not_abort_the_run(tmp_path):
    """Recorded, not raised. Aborting would destroy the evidence."""
    build(tmp_path, Caps(per_collection_calls=10), run_id="r0")
    wrapper = build(tmp_path, Caps(per_collection_calls=5), run_id="r1")
    assert wrapper.budget.voided is None


# -- which branch produced the collection -----------------------------------

def test_the_record_says_which_branch_ran(tmp_path):
    """Amendment 4 added a third branch; a collection must say which it used.

    The whole justification for re-running stage 10 is that the loop changed.
    A collection that cannot say which loop it ran under cannot be compared
    against one that ran the other, which makes the re-run unauditable for
    exactly the reason it was commissioned.
    """
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    CallWrapper(run_id="r0", run_dir=tmp_path / "r0", cumulative=counter,
                planner={"mode": "live", "loop": "interactive"})
    assert read(tmp_path / "r0" / CAPS_FILENAME)["planner"] == {
        "mode": "live", "loop": "interactive"
    }


def test_agent_loop_resolves_the_branch_from_the_environment(monkeypatch):
    """The env read belongs in agent_loop, not in planner.

    ``planner.py`` must not read the environment -- pinned separately by
    ``test_nothing_in_this_module_reads_the_environment``, and the reason is
    that the next thing it would pick up implicitly is a key. The first version
    of this feature read AEP_PLANNER_* inside planner.py and broke that.
    """
    from experiments.harness.agent_loop import planner_record

    monkeypatch.setenv("AEP_PLANNER_MODE", "live")
    monkeypatch.setenv("AEP_PLANNER_LOOP", "interactive")
    assert planner_record() == {"mode": "live", "loop": "interactive"}

    monkeypatch.delenv("AEP_PLANNER_LOOP", raising=False)
    monkeypatch.setenv("AEP_PLANNER_MODE", "stub")
    assert planner_record() == {"mode": "stub", "loop": "planned"}


def test_planner_does_not_read_the_environment_for_this():
    """The invariant, asserted against this feature specifically."""
    from pathlib import Path as _Path

    text = (_Path(__file__).resolve().parents[1] / "experiments" / "harness"
            / "planner.py").read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "AEP_PLANNER_MODE" not in text
    assert "AEP_PLANNER_LOOP" not in text


def test_an_unstated_branch_records_none_rather_than_guessing(tmp_path):
    """A direct construction did not state it; "planned" would be a guess."""
    build(tmp_path, Caps())
    assert read(tmp_path / "r0" / CAPS_FILENAME)["planner"] is None


def test_the_live_launcher_refuses_an_unset_loop():
    """The launcher set AEP_PLANNER_MODE=live and never set the loop.

    Run as it stood, the stage-10 re-run would have collected the PLANNED
    branch at real cost -- the exact shape amendment 5 §5 commissioned the
    re-run to replace. Checked as source because the script cannot be run
    here without a key.
    """
    script = (Path(__file__).resolve().parents[1]
              / "scripts" / "run_phase40_live.sh").read_text(encoding="utf-8")
    assert "AEP_PLANNER_LOOP" in script
    # ":?" is the refusal. A plain default would reintroduce the defect.
    assert 'AEP_PLANNER_LOOP:?' in script.replace("${", "").replace("\\\n", "")
    assert "interactive|planned" in script


# -- caps_echo on its own ---------------------------------------------------

def test_caps_echo_is_serialisable(tmp_path):
    """It is written with json.dumps; a non-serialisable field fails late."""
    json.dumps(caps_echo(Caps(), Price()), sort_keys=True)
