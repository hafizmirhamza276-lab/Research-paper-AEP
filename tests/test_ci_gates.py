"""Tests for the CI gates themselves (scripts/check_pytest_gates.py).

The gates exist because this repository's audit history contains a green
build whose green came from tests that never ran. A gate that cannot fail
would reproduce exactly that, one level up: the build would be green because
the *check* was vacuous rather than because the suite was clean.

So each gate is tested in both directions -- it passes what it should pass,
and it fails what it should fail -- including the degenerate inputs that a
naive implementation treats as success: an empty capture, a zero-test run, a
missing file.
"""

from __future__ import annotations

import pytest

from scripts.check_pytest_gates import (
    GateFailure,
    gate_no_failures,
    gate_no_skips,
    gate_no_xpass,
    gate_tests_actually_ran,
    main,
    read_junit_counts,
)

CLEAN_COUNTS = {"tests": 1169, "skipped": 0, "failures": 0, "errors": 0}

CLEAN_OUTPUT = "1169 passed in 33.17s\n"


def write_junit(tmp_path, *, tests=10, skipped=0, failures=0, errors=0, nested=True):
    suite = (
        f'<testsuite name="pytest" tests="{tests}" skipped="{skipped}" '
        f'failures="{failures}" errors="{errors}" />'
    )
    document = f"<testsuites>{suite}</testsuites>" if nested else suite
    path = tmp_path / "junit.xml"
    path.write_text(document, encoding="utf-8")
    return path


# ===========================================================================
# Gate 1 -- zero skipped
# ===========================================================================


def test_a_clean_run_passes_the_skip_gate():
    gate_no_skips(CLEAN_COUNTS)


@pytest.mark.parametrize("skipped", [1, 5, 36])
def test_any_skip_fails_the_gate(skipped):
    """36 skipped = green is the exact failure mode this prevents."""
    with pytest.raises(GateFailure, match="SKIPPED"):
        gate_no_skips({**CLEAN_COUNTS, "skipped": skipped})


# ===========================================================================
# Gate 2 -- zero xpassed
# ===========================================================================


def test_a_clean_run_passes_the_xpass_gate():
    gate_no_xpass(CLEAN_OUTPUT)


def test_an_xpass_short_summary_line_fails_the_gate():
    output = (
        "XPASS tests/test_thing.py::test_name known issue\n"
        "1 xpassed, 1168 passed in 33.17s\n"
    )

    with pytest.raises(GateFailure, match="XPASSED"):
        gate_no_xpass(output)


def test_an_xpass_count_alone_fails_the_gate():
    """Covers -q runs where the per-test XPASS lines are not rendered."""
    with pytest.raises(GateFailure, match="XPASSED"):
        gate_no_xpass("3 xpassed, 1166 passed in 33.17s\n")


def test_an_empty_capture_fails_rather_than_silently_passing():
    """No summary means the gate could not be evaluated -- fail closed."""
    with pytest.raises(GateFailure, match="no recognisable summary"):
        gate_no_xpass("")


def test_a_truncated_capture_fails_rather_than_silently_passing():
    with pytest.raises(GateFailure, match="no recognisable summary"):
        gate_no_xpass("============ test session starts ============\n")


def test_xfailed_without_xpassed_is_permitted():
    """An xfail that still fails is a declared expectation, not a surprise."""
    gate_no_xpass("2 xfailed, 1167 passed in 33.17s\n")


def test_the_word_xpassed_inside_a_test_name_does_not_trip_the_gate():
    gate_no_xpass("1169 passed in 33.17s\n")


# ===========================================================================
# Gate 3 -- zero failures and errors
# ===========================================================================


def test_a_clean_run_passes_the_failure_gate():
    gate_no_failures(CLEAN_COUNTS)


@pytest.mark.parametrize(
    "changes", [{"failures": 1}, {"errors": 1}, {"failures": 2, "errors": 3}]
)
def test_failures_or_errors_fail_the_gate(changes):
    with pytest.raises(GateFailure):
        gate_no_failures({**CLEAN_COUNTS, **changes})


# ===========================================================================
# Gate 4 -- the suite actually ran
# ===========================================================================


def test_a_collapsed_collection_fails_the_gate():
    """Zero tests is the other way a green build lies."""
    with pytest.raises(GateFailure, match="only 0 test"):
        gate_tests_actually_ran({**CLEAN_COUNTS, "tests": 0}, minimum=1100)


def test_a_partial_collection_fails_the_gate():
    with pytest.raises(GateFailure, match="expected at least 1100"):
        gate_tests_actually_ran({**CLEAN_COUNTS, "tests": 42}, minimum=1100)


def test_a_full_collection_passes_the_gate():
    gate_tests_actually_ran(CLEAN_COUNTS, minimum=1100)


# ===========================================================================
# JUnit parsing
# ===========================================================================


def test_counts_are_read_from_a_nested_testsuites_document(tmp_path):
    path = write_junit(tmp_path, tests=1169, skipped=0)

    assert read_junit_counts(path)["tests"] == 1169


def test_counts_are_read_from_a_bare_testsuite_document(tmp_path):
    path = write_junit(tmp_path, tests=7, skipped=2, nested=False)
    counts = read_junit_counts(path)

    assert counts["tests"] == 7
    assert counts["skipped"] == 2


def test_a_missing_junit_report_fails(tmp_path):
    with pytest.raises(GateFailure, match="not found"):
        read_junit_counts(tmp_path / "absent.xml")


def test_an_unparseable_junit_report_fails(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text("<not xml", encoding="utf-8")

    with pytest.raises(GateFailure, match="not parseable"):
        read_junit_counts(path)


def test_a_junit_report_without_a_testsuite_fails(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text("<testsuites></testsuites>", encoding="utf-8")

    with pytest.raises(GateFailure, match="no <testsuite>"):
        read_junit_counts(path)


# ===========================================================================
# End to end -- exit status is what CI keys on
# ===========================================================================


def test_main_returns_zero_for_a_clean_run(tmp_path, capsys):
    junit = write_junit(tmp_path, tests=1169)
    output = tmp_path / "out.txt"
    output.write_text(CLEAN_OUTPUT, encoding="utf-8")

    exit_code = main(
        ["--junit", str(junit), "--output", str(output), "--minimum-tests", "1100"]
    )

    assert exit_code == 0
    assert "0 skipped" in capsys.readouterr().out


def test_main_returns_nonzero_when_tests_were_skipped(tmp_path):
    junit = write_junit(tmp_path, tests=1169, skipped=5)
    output = tmp_path / "out.txt"
    output.write_text("1164 passed, 5 skipped in 23.52s\n", encoding="utf-8")

    assert main(["--junit", str(junit), "--output", str(output)]) == 1


def test_main_returns_nonzero_when_the_output_capture_is_missing(tmp_path):
    junit = write_junit(tmp_path, tests=1169)

    assert main(["--junit", str(junit), "--output", str(tmp_path / "absent.txt")]) == 1


def test_main_returns_nonzero_when_a_test_xpassed(tmp_path):
    junit = write_junit(tmp_path, tests=1169)
    output = tmp_path / "out.txt"
    output.write_text("1 xpassed, 1168 passed in 33.17s\n", encoding="utf-8")

    assert main(["--junit", str(junit), "--output", str(output)]) == 1
