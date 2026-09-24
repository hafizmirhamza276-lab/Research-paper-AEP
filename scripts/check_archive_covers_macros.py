#!/usr/bin/env python3
"""Every manuscript macro's evidence is obtainable: deposited, or tracked.

Why this exists
---------------
On 2026-09-24 five collection roots supplying **eighteen** macros in
``paper/generated/numbers.tex`` were found to be in neither archive part --
including ``ws5-2026-09-10/t1-p0-everysec``, which supplies
``\\BarrierCostFifteen``, RQ3's headline. They were not declined. They were
missed, and the metadata looked complete while they were missing, because
``build_raw_archive.py`` hard-coded one module-global ``EXCLUDED`` list into
every part: the 2026-09-15 extension emitted the 2026-09-03 exclusions verbatim
and declared nothing about its own coverage.

``verify_published_archive.py`` could not catch it. That script verifies the
deposit **against itself** -- six files present, nine digests matching, every
file verifying against its own manifest. Nothing in it knows what the paper
cites. This check closes that gap from the other direction.

What it enforces
----------------
**For every macro in ``numbers.tex``, the source named in its provenance
comment must be obtainable by a reader**, which means exactly one of:

* the collection root it lives in is a top-level directory of some archive
  part's ``MANIFEST.sha256``; or
* the file is tracked in git, so it ships with the repository.

A macro whose source is neither is a number a reader cannot check, which is
the one thing the artifact exists to prevent.

What it does NOT enforce
------------------------
* That the archive parts are *published*. That is
  ``verify_published_archive.py``.
* That the numbers are *right*. That is ``check_paper_numbers.py``.
* Coverage of roots no macro derives from. A root can be deliberately excluded
  (``stage3-replication-2026-08-13``) without failing here, which is correct:
  the invariant is about evidence the manuscript rests on, not about every
  directory on the host.

Usage
-----
    python scripts/check_archive_covers_macros.py
    python scripts/check_archive_covers_macros.py --selftest
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMBERS = ROOT / "paper" / "generated" / "numbers.tex"

#: Where each archive part's manifest lives. Parts sit beside the repository,
#: not inside it -- they are 42 MB of tarball and are not tracked.
MANIFESTS: tuple[tuple[str, Path], ...] = (
    ("2026-09-03", ROOT.parent / "aep-raw-archive" / "MANIFEST.sha256"),
    ("2026-09-15", ROOT.parent / "aep-raw-archive-ext" / "MANIFEST.sha256"),
    ("2026-09-24", ROOT.parent / "aep-raw-archive-p3" / "MANIFEST.sha256"),
)

#: Most provenance comments write the source basename bare, with no directory.
#: A bare name therefore has to be attributed explicitly, and **there is no
#: catch-all default**: an unrecognised bare name is a failure, not a guess.
#:
#: Defaulting bare names to the matrix is exactly the shape of mistake this
#: check exists to catch -- it would have sent ``b5-runs.jsonl`` to a root that
#: is archived and reported the Temporal baseline as covered without ever
#: looking at the root it actually comes from.
BARE_TO_ROOT: dict[str, str] = {
    # The main matrix's own analysis products.
    "per-cell-metrics.csv": "matrix",
    "per-execution.csv": "matrix",
    "redis-kill-ablation.csv": "matrix",
    "comparisons-vs-aep-full.csv": "matrix",
    "latency-and-throughput.csv": "matrix",
    "coverage.json": "matrix",
    "table-1.csv": "matrix",
    # WS-6's real-Temporal baseline writes one JSONL, named bare.
    "b5-runs.jsonl": "ws6-b5-s1-2026-09-08-attempt3",
}

#: Bare names that are tracked repository files rather than collection output.
#: Each is checked against ``git ls-files`` under its real path.
BARE_REPO_FILES: dict[str, str] = {
    "e1-kill-latency-by-run.csv": "reports/raw/e1-kill-latency-by-run.csv",
    "phase13-model-gap.json": "reports/raw/phase13-model-gap.json",
    "phase13-fault-landing.json": "reports/raw/phase13-fault-landing.json",
}

#: Provenance tokens that are repository files rather than collection roots.
#: Each must be TRACKED; the check verifies that rather than trusting the list.
REPO_FILE_PREFIXES = ("reports/raw/", "experiments/results/g2-flakey")

#: Archive labels are not always the repository's root names: the extension
#: renamed WS-4 and WS-6 roots with attempt suffixes, and part 3 flattens the
#: ``ws5-2026-09-10/<cell>`` two-level path to one label. Matching is therefore
#: by prefix on the flattened name, not by equality.
_PATHISH = re.compile(r"[\w./*-]+\.(?:csv|json|jsonl)\b")


def macro_sources(text: str) -> dict[str, set[str]]:
    """{macro name -> set of provenance tokens}, from the comment blocks."""
    out: dict[str, set[str]] = {}
    block: list[str] = []
    for line in text.splitlines()[5:]:          # skip the 5-line file banner
        stripped = line.strip()
        if stripped.startswith("%"):
            block.append(stripped)
            continue
        if "newcommand" in stripped:
            match = re.search(r"newcommand\{\\([A-Za-z]+)\}", stripped)
            name = match.group(1) if match else stripped[:40]
            tokens = {
                token
                for entry in block
                for token in _PATHISH.findall(entry)
            }
            if tokens:
                out[name] = tokens
        block = []
    return out


class Unattributable(Exception):
    """A provenance token that maps to neither a known root nor a known file."""


def root_of(token: str) -> str | None:
    """The collection root a token belongs to.

    Returns ``None`` when the token is a repository file rather than
    collection output. Raises :class:`Unattributable` when the token cannot be
    placed at all -- which is a finding, not a default.
    """
    if any(token.startswith(prefix) for prefix in REPO_FILE_PREFIXES):
        return None
    parts = token.split("/")
    if len(parts) == 1:
        if token in BARE_REPO_FILES:
            return None
        if token in BARE_TO_ROOT:
            return BARE_TO_ROOT[token]
        if "*" in token:                       # g2-flakey-write-loss*.json
            return None
        raise Unattributable(token)
    if parts[0] == "analysis":
        return BARE_TO_ROOT.get(parts[-1], "matrix")
    if parts[0] == "experiments" and len(parts) > 2:
        parts = parts[2:]
        if len(parts) == 1:
            return None
    # ws5-2026-09-10/<cell>/analysis/x.csv -> ws5-2026-09-10-<cell>
    if parts[0].startswith("ws5-") and len(parts) > 2 and parts[1] != "analysis":
        return f"{parts[0]}-{parts[1]}"
    return parts[0]


def _resolve(token: str) -> tuple[str | None, str | None]:
    """(root, problem). Exactly one is non-None."""
    try:
        return root_of(token), None
    except Unattributable:
        return None, (
            f"provenance names {token!r}, a bare filename this check cannot "
            "place. Add it to BARE_TO_ROOT or BARE_REPO_FILES -- an "
            "unattributed source is a number whose evidence nobody has "
            "located"
        )


def archive_labels() -> tuple[dict[str, set[str]], list[str]]:
    """{part label -> top-level names}, and the parts that are absent."""
    found: dict[str, set[str]] = {}
    missing: list[str] = []
    for label, path in MANIFESTS:
        if not path.is_file():
            missing.append(label)
            continue
        names = set()
        for line in path.read_text(encoding="utf-8",
                                   errors="replace").splitlines():
            pieces = line.split(None, 1)
            if len(pieces) == 2:
                names.add(pieces[1].lstrip("*").strip().split("/")[0])
        found[label] = names
    return found, missing


#: Archive labels that differ from the name the provenance comment writes.
#: **Explicit, because prefix matching is unsafe here**: `fsync-always` is a
#: six-run 2026-08-07 collection and `fsync-always-2026-09-14` is a 45-run
#: one, the manuscript quotes both, and any rule that lets one satisfy the
#: other would report a missing root as covered by a different experiment.
ALIASES: dict[str, str] = {
    # Phase 35 suffixed the WS-4 label with the amendment it ran under.
    "ws4-writeloss-s1-2026-09-07": "ws4-writeloss-s1-2026-09-07-a5",
}


def covers(root: str, names: set[str]) -> bool:
    """Is `root` carried by an archive whose top-level names are `names`?

    Exact match, one declared alias, or -- for a provenance comment that
    names a family with a glob -- any member of that family. Nothing else:
    an archive label that merely starts with the root's name does not count.
    """
    if root in names:
        return True
    if "*" in root:
        stem = root.split("*")[0]
        return any(name.startswith(stem) for name in names)
    alias = ALIASES.get(root)
    return alias in names if alias else False


def tracked(token: str) -> bool:
    done = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", token],
        capture_output=True,
    )
    if done.returncode == 0:
        return True
    # A glob token (`g2-flakey-write-loss*.json`) -- ask git for the family.
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", token],
        capture_output=True, text=True,
    )
    return bool(listed.stdout.strip())


def audit(numbers_text: str, parts: dict[str, set[str]]) -> list[str]:
    """Problems, one string each. Empty means every macro's source is reachable."""
    problems: list[str] = []
    every = set().union(*parts.values()) if parts else set()
    by_root: dict[str, set[str]] = {}
    for macro, tokens in macro_sources(numbers_text).items():
        for token in tokens:
            root, problem = _resolve(token)
            if problem:
                problems.append(f"{macro}: {problem}")
                continue
            if root is None:
                path = BARE_REPO_FILES.get(token, token)
                if not tracked(path):
                    problems.append(
                        f"{macro}: provenance names {token!r}, which is "
                        "neither a collection root nor a tracked file -- a "
                        "reader cannot obtain it"
                    )
                continue
            by_root.setdefault(root, set()).add(macro)

    for root in sorted(by_root):
        if covers(root, every):
            continue
        macros = sorted(by_root[root])
        shown = ", ".join(macros[:6]) + (" ..." if len(macros) > 6 else "")
        problems.append(
            f"{root}: supplies {len(macros)} macro(s) and is in NO archive "
            f"part -- {shown}. Either add it to a part, or the macros that "
            "rest on it have no deposited evidence."
        )
    return problems


def report(parts: dict[str, set[str]], numbers_text: str) -> None:
    by_root: dict[str, set[str]] = {}
    for macro, tokens in macro_sources(numbers_text).items():
        for token in tokens:
            root, _problem = _resolve(token)
            if root is not None:
                by_root.setdefault(root, set()).add(macro)
    every = set().union(*parts.values()) if parts else set()
    print(f"{'collection root':44s} {'macros':>7s}  carried by")
    for root in sorted(by_root, key=lambda r: -len(by_root[r])):
        where = [label for label, names in parts.items()
                 if covers(root, names)] or ["*** NONE ***"]
        print(f"{root:44s} {len(by_root[root]):7d}  {', '.join(where)}")
    print(f"\n{len(by_root)} roots supply "
          f"{sum(len(v) for v in by_root.values())} macro attributions; "
          f"{len(every)} top-level names across {len(parts)} archive part(s)")


SELFTEST_NUMBERS = """\
% GENERATED by scripts/paper_tables.py -- do not edit.
% Sources: analysis/per-cell-metrics.csv
%
%
%

% per-cell-metrics.csv | system=AEP_FULL regime=crashed
\\newcommand{\\RealMacro}{0.0000}

% a-root-that-was-never-archived-2026-01-01/analysis/per-cell-metrics.csv | x
\\newcommand{\\OrphanMacro}{1.2345}
"""


def selftest() -> int:
    """The known-positive: an unarchived root must be caught."""
    parts, _ = archive_labels()
    if not parts:
        print("selftest: no archive manifest is readable; cannot run", file=sys.stderr)
        return 2
    problems = audit(SELFTEST_NUMBERS, parts)
    orphan = [p for p in problems
              if p.startswith("a-root-that-was-never-archived-2026-01-01")]
    ok_real = not any(p.startswith("matrix:") for p in problems)
    print("selftest: synthetic numbers.tex with one archived and one "
          "unarchived root")
    print(f"  orphan root detected                    : "
          f"{'PASS' if orphan else 'FAIL'}")
    print(f"  archived root NOT falsely reported      : "
          f"{'PASS' if ok_real else 'FAIL'}")
    if orphan:
        print(f"  message: {orphan[0]}")
    if orphan and ok_real:
        print("selftest: 2 of 2")
        return 0
    print("selftest: FAILED -- the check cannot detect what it exists for",
          file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true",
                        help="prove the check fails on an unarchived root")
    parser.add_argument("--allow-missing-parts", action="store_true",
                        help="do not fail when an archive part is not on disk "
                             "(for a clone without the archives beside it)")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if not NUMBERS.is_file():
        print(f"missing {NUMBERS}", file=sys.stderr)
        return 2

    parts, absent = archive_labels()
    for label in absent:
        print(f"archive part {label}: manifest not on disk")
    if absent and not args.allow_missing_parts:
        if not parts:
            print("no archive manifest readable; nothing to check against",
                  file=sys.stderr)
            return 2
        print("  (checking against the parts that are present)")

    text = NUMBERS.read_text(encoding="utf-8")
    report(parts, text)
    problems = audit(text, parts)
    print()
    if problems:
        print(f"FAILING: {len(problems)}")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("every macro's evidence is obtainable: deposited, or tracked.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
