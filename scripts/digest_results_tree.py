#!/usr/bin/env python3
"""Digest a raw results tree: every file in every run, plus a tree-level roll-up.

**Why this exists.** `scripts/freeze_results.py` writes a `SHA256SUMS` covering
the manifest and the analysis outputs -- which is what its docstring says and
what it does. Commit `729fbfa` then claimed that file *"is what lets the later
pass prove it analysed what was collected"*. It is not: two manifest lines do
not bind 331 MB of run directories, and phase 17 had to fall back to
regenerating the manifests and checking they matched, which establishes the run
COUNTS are unchanged and nothing about run CONTENTS.

This writes `RAW-SHA256SUMS`, which does bind the contents.

**What it covers.** Every file in every run directory, by SHA-256, in a format
`sha256sum -c` verifies directly. Plus a tree-level digest over the sorted
per-run digests, so a single value identifies the whole collection.

**What it deliberately excludes, and why.** SQLite's `-wal` and `-shm` side
files. They are rewritten whenever the database is opened -- including by a
read-only reader -- so hashing them produces a check that fails for anyone who
looks at the ledger. A gate that cries wolf is one people learn to ignore
(`docs/25` R13's neighbourhood). The `ground_truth.sqlite3` main file IS hashed,
and it is where the committed rows live.

**The limitation this cannot fix, stated in every file it writes.** A digest
taken today binds every pass from today onward. It cannot retroactively bind a
pass that ran before it. Nothing can.

Usage:
    python scripts/digest_results_tree.py --results-root <step-dir>
    python scripts/digest_results_tree.py --results-root <step-dir> --check
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Rewritten by any open of the SQLite database, including a read-only one.
VOLATILE_SUFFIXES = ("-wal", "-shm")

#: The file this module writes. Distinct from freeze_results.py's SHA256SUMS so
#: that neither can be mistaken for the other's coverage.
DIGEST_NAME = "RAW-SHA256SUMS"

CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def is_volatile(path: Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in VOLATILE_SUFFIXES)


def run_directories(root: Path) -> list[Path]:
    """Run directories, which are every child directory except `analysis`."""
    return sorted(
        child for child in root.iterdir()
        if child.is_dir() and child.name != "analysis"
    )


class NoRunDirectories(Exception):
    """Raised for a root with nothing this tool can bind.

    A results root with no run directories yields a RAW-SHA256SUMS with no
    file lines and a tree digest of ``sha256(b"")`` -- a constant. Such a
    file is indistinguishable, by eye or by ``--check``, from one covering a
    real collection, so it reads as coverage while binding nothing.

    Thirteen roots in this repository are analysis-only copies of
    collections whose raw runs live elsewhere. Writing them a digest would
    assert custody this checkout does not have. Refusing is the honest
    answer and it names the reason (`docs/25` R14: an empty result must say
    which kind of empty it is).
    """


def digest_tree(root: Path) -> tuple[list[tuple[str, str]], dict[str, str], str]:
    """Return (file lines, per-run digests, tree digest).

    The per-run digest is over that run's sorted ``relpath  filehash`` lines, so
    it changes if a file is added, removed or altered. The tree digest is over
    the sorted per-run digests, for the same reason one level up.
    """
    runs = run_directories(root)
    if not runs:
        raise NoRunDirectories(
            str(root) + " has no run directories. Refusing to write a"
            " RAW-SHA256SUMS: it would contain no file lines and a tree"
            " digest of the empty string, which is a constant and binds"
            " nothing, while looking exactly like coverage. If this root is"
            " an analysis-only copy, its raw runs are somewhere else and"
            " that is where the digest belongs."
        )
    lines: list[tuple[str, str]] = []
    per_run: dict[str, str] = {}
    for run in runs:
        run_lines: list[str] = []
        for path in sorted(run.rglob("*")):
            if not path.is_file() or is_volatile(path):
                continue
            rel = path.relative_to(root).as_posix()
            digest = sha256_file(path)
            lines.append((digest, rel))
            run_lines.append(f"{digest}  {rel}")
        joined = "\n".join(run_lines).encode("utf-8")
        per_run[run.name] = hashlib.sha256(joined).hexdigest()
    rolled = "\n".join(
        f"{per_run[name]}  {name}" for name in sorted(per_run)
    ).encode("utf-8")
    return lines, per_run, hashlib.sha256(rolled).hexdigest()


def header(root: Path, per_run: dict[str, str], tree: str, when: str) -> list[str]:
    return [
        f"# RAW-SHA256SUMS for {root.name}",
        "#",
        f"# Written {when} by scripts/digest_results_tree.py.",
        "#",
        "# COVERAGE. Every file in every run directory, excluding SQLite -wal and",
        "# -shm side files, which any open of the database rewrites. Verify with:",
        "#     cd <this directory> && sha256sum -c RAW-SHA256SUMS",
        "#",
        f"# runs: {len(per_run)}   files: (one line each, below)",
        f"# tree digest: {tree}",
        "#",
        "# LIMITATION, which no digest taken after a collection can remove.",
        "# This binds every pass from the date above onward. It does NOT",
        "# retroactively bind any pass that ran before it -- in particular it does",
        "# not bind phase 17's analysis, which ran first. What binds that pass is",
        "# weaker and is recorded in its report: the manifests regenerate",
        "# byte-identically, which fixes the run counts and cell shape, not the",
        "# run contents.",
        "#",
        "# per-run digests follow the file lines, as comments, so that a single",
        "# run can be identified without rehashing its neighbours.",
    ]


def write(root: Path) -> Path:
    lines, per_run, tree = digest_tree(root)
    when = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = root / DIGEST_NAME
    body = header(root, per_run, tree, when)
    body += [f"{digest}  {rel}" for digest, rel in lines]
    body += ["#"] + [f"# run {name}  {per_run[name]}" for name in sorted(per_run)]
    out.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return out


def check(root: Path) -> int:
    """Recompute and compare against the committed file."""
    out = root / DIGEST_NAME
    if not out.is_file():
        print(f"FAIL: {out} does not exist")
        return 1
    committed = {}
    committed_tree = None
    for line in out.read_text(encoding="utf-8").splitlines():
        if line.startswith("# tree digest:"):
            committed_tree = line.split(":", 1)[1].strip()
        if not line or line.startswith("#"):
            continue
        digest, rel = line.split("  ", 1)
        committed[rel] = digest
    lines, _per_run, tree = digest_tree(root)
    current = {rel: digest for digest, rel in lines}

    missing = sorted(set(committed) - set(current))
    added = sorted(set(current) - set(committed))
    changed = sorted(r for r in set(committed) & set(current)
                     if committed[r] != current[r])
    for rel in missing:
        print(f"  MISSING  {rel}")
    for rel in added:
        print(f"  ADDED    {rel}")
    for rel in changed:
        print(f"  CHANGED  {rel}")
    ok = not (missing or added or changed)
    print(f"{root.name}: {len(current)} files, "
          f"{len(missing)} missing, {len(added)} added, {len(changed)} changed")
    if committed_tree is not None:
        print(f"  tree digest {'matches' if committed_tree == tree else 'DIFFERS'}")
        ok = ok and committed_tree == tree
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true",
                        help="verify against the committed digest instead of writing")
    args = parser.parse_args(argv)
    root = args.results_root
    if not root.is_dir():
        print(f"FAIL: {root} is not a directory")
        return 2
    try:
        if args.check:
            return check(root)
        out = write(root)
        _lines, per_run, tree = digest_tree(root)
    except NoRunDirectories as exc:
        # Exit 3, distinct from 2 ("not a directory") and 1 ("digest
        # mismatch"), so a caller looping over roots can tell "nothing
        # here to bind" apart from "what is here does not match".
        print("REFUSED: " + str(exc))
        return 3
    print(f"wrote {out}  ({len(per_run)} runs, tree {tree[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
