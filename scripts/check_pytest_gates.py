#!/usr/bin/env python3
"""Enforce the test-result gates that make CI unable to lie.

The repository's audit history records the failure mode this exists to
prevent: a green build whose green came from tests that never ran. "36
skipped = green" is not a passing suite, it is an unmeasured one.

Three gates, all of which must hold:

  1. **Zero skipped.** A skip in CI means an environment precondition was not
     met -- no cjson, no Redis, no integration flag -- and the coverage it
     was supposed to provide silently vanished. In CI every precondition is
     supposed to be satisfied, so a skip is a misconfiguration, not a
     legitimate outcome.

  2. **Zero xpassed.** A test marked xfail that starts passing is a *result
     change nobody looked at*. Either the bug was fixed and the marker is
     stale, or the test stopped testing what it claimed. Both need a human.
     ``xfail_strict = true`` in pyproject.toml already turns an xpass into a
     failure; this gate is the independent second check, because a per-test
     ``strict=False`` can override the global setting.

  3. **Zero failures and zero errors.** Redundant with pytest's exit code,
     checked anyway so that a mangled invocation (``| tee`` swallowing a
     non-zero status, for instance) cannot produce a green step.

Gates 1 and 3 read the JUnit XML, which carries exact machine-readable
counts. Gate 2 reads the ``-ra`` short summary text, because JUnit XML
reports xpass as a plain pass and cannot distinguish it.

Usage::

    pytest -q -ra --strict-markers --junitxml=junit.xml | tee pytest-output.txt
    python scripts/check_pytest_gates.py --junit junit.xml --output pytest-output.txt

Exit status is 0 only when every gate holds.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

#: `-ra` renders one line per non-passing outcome, e.g.
#: ``XPASS tests/test_thing.py::test_name reason``
XPASS_LINE = re.compile(r"^XPASS\b", re.MULTILINE)

#: The final counts line, e.g. ``3 xpassed, 690 passed in 27.77s``
XPASS_COUNT = re.compile(r"(\d+)\s+xpassed\b")

#: Guards against a truncated or empty capture being read as "no problems".
PYTEST_SUMMARY = re.compile(r"\b(passed|failed|error|no tests ran)\b")


class GateFailure(Exception):
    """One gate did not hold."""


def read_junit_counts(junit_path: Path) -> dict[str, int]:
    """Return aggregate counts from a pytest JUnit XML report."""
    if not junit_path.is_file():
        raise GateFailure(f"JUnit report not found: {junit_path}")

    try:
        root = ElementTree.parse(junit_path).getroot()
    except ElementTree.ParseError as exc:
        raise GateFailure(f"JUnit report is not parseable XML: {exc}") from None

    # pytest writes <testsuites><testsuite .../></testsuites>; older
    # invocations write a bare <testsuite>. Handle both.
    suites = (
        [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    )
    if not suites:
        raise GateFailure(f"JUnit report contains no <testsuite>: {junit_path}")

    counts = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    for suite in suites:
        for key in counts:
            counts[key] += int(suite.get(key, 0) or 0)
    return counts


def gate_no_skips(counts: dict[str, int]) -> None:
    if counts["skipped"]:
        raise GateFailure(
            f"{counts['skipped']} test(s) were SKIPPED. In CI every "
            "precondition is provisioned, so a skip is an unmet environment "
            "assumption, not a legitimate outcome. Re-run with -ra to see "
            "which, and either fix the environment or delete the test."
        )


def gate_no_failures(counts: dict[str, int]) -> None:
    if counts["failures"] or counts["errors"]:
        raise GateFailure(
            f"{counts['failures']} failure(s) and {counts['errors']} error(s)."
        )


def gate_tests_actually_ran(counts: dict[str, int], minimum: int) -> None:
    """A suite that collected nothing must not read as success."""
    if counts["tests"] < minimum:
        raise GateFailure(
            f"only {counts['tests']} test(s) ran, expected at least {minimum}. "
            "A collapsed collection is the other way a green build lies."
        )


def gate_no_xpass(output_text: str) -> None:
    if not PYTEST_SUMMARY.search(output_text):
        raise GateFailure(
            "captured pytest output contains no recognisable summary; the "
            "capture is empty or truncated, so the xpass gate cannot be "
            "evaluated and must not be assumed to hold."
        )

    reported = XPASS_LINE.findall(output_text)
    counted = [int(n) for n in XPASS_COUNT.findall(output_text)]
    total = sum(counted)

    if reported or total:
        raise GateFailure(
            f"{total or len(reported)} test(s) XPASSED -- marked xfail but "
            "passed. That is a result change nobody reviewed: either the "
            "underlying bug is fixed and the marker is stale, or the test no "
            "longer tests what it claims. Resolve it explicitly."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce the AEP CI test-result gates."
    )
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="captured pytest stdout (needs -ra)",
    )
    parser.add_argument(
        "--minimum-tests",
        type=int,
        default=1,
        help="fail if fewer than this many tests ran",
    )
    arguments = parser.parse_args(argv)

    try:
        counts = read_junit_counts(arguments.junit)
        if not arguments.output.is_file():
            raise GateFailure(f"pytest output capture not found: {arguments.output}")
        output_text = arguments.output.read_text(encoding="utf-8", errors="replace")

        gate_tests_actually_ran(counts, arguments.minimum_tests)
        gate_no_failures(counts)
        gate_no_skips(counts)
        gate_no_xpass(output_text)
    except GateFailure as failure:
        print(f"GATE FAILED: {failure}", file=sys.stderr)
        return 1

    print(
        f"OK: {counts['tests']} tests, "
        f"{counts['skipped']} skipped, "
        f"{counts['failures']} failed, "
        f"{counts['errors']} errors, 0 xpassed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
