#!/usr/bin/env python3
"""Derive a .gitignore negation block from a frozen root's SHA256SUMS.

The rule, stated by the operator and not negotiable here: negate exactly the
files SHA256SUMS names, plus SHA256SUMS itself. Nothing else. Then list
analysis/ on disk and compare. A file present in analysis/ that SHA256SUMS does
not name is a STOP condition -- it is an unhashed artefact sitting inside a
frozen root, which is the B13 class, and it must be reported before anything is
written or staged.

Deriving from SHA256SUMS rather than from `ls` matters: publish_session.sh
builds its block from `ls analysis/`, which would silently track a file the
freeze never attested. That is the reverse of what the block is for.

Read-only. Prints the block; writes nothing.

Usage: derive_negations.py <run root> [<run root> ...]
"""

from __future__ import annotations

import sys
from pathlib import Path


def entries(root: Path) -> list[str]:
    """Path column of SHA256SUMS, normalised to forward slashes.

    freeze_results.py emits backslashes and CRLF when run on Windows (B5), so
    both are normalised here rather than assumed absent.
    """
    out = []
    raw = (root / "SHA256SUMS").read_text(encoding="utf-8", errors="replace")
    for line in raw.splitlines():
        line = line.rstrip("\r").strip()
        if not line:
            continue
        # "<64 hex>  <path>" or "<64 hex> *<path>" (binary mode)
        _, _, path = line.partition(" ")
        path = path.strip().lstrip("*").strip()
        out.append(path.replace("\\", "/"))
    return out


def main(argv: list[str]) -> int:
    rc = 0
    for arg in argv:
        root = Path(arg).resolve()
        rel = f"experiments/results/{root.name}"
        named = entries(root)
        named_analysis = sorted(p for p in named if p.startswith("analysis/"))
        named_top = sorted(p for p in named if "/" not in p)
        on_disk = sorted(p.name for p in (root / "analysis").iterdir())

        print(f"################ {root.name} ################")
        print(f"SHA256SUMS entries                 : {len(named)}")
        print(f"  of which under analysis/         : {len(named_analysis)}")
        print(f"  of which at the root             : {len(named_top)}  {named_top}")
        print(f"files on disk in analysis/         : {len(on_disk)}")

        unhashed = [f for f in on_disk if f"analysis/{f}" not in named]
        missing = [p for p in named_analysis if p.split("/", 1)[1] not in on_disk]

        if unhashed:
            print(f"  !! in analysis/ but NOT named by SHA256SUMS: {unhashed}")
            rc = 2
        if missing:
            print(f"  !! named by SHA256SUMS but NOT on disk      : {missing}")
            rc = 2
        if not unhashed and not missing:
            print("  analysis/ on disk and SHA256SUMS's analysis/ entries agree exactly")

        # Arithmetic, derived rather than asserted.
        staged = len(named) + 1  # every named file, plus SHA256SUMS itself
        print(f"\nfiles to stage = {len(named)} named + 1 (SHA256SUMS) = {staged}")

        print("\n--- negation block ---")
        print(f"!{rel}/")
        print(f"{rel}/*")
        for p in named_top:
            print(f"!{rel}/{p}")
        print(f"!{rel}/SHA256SUMS")
        print(f"!{rel}/analysis/")
        print(f"{rel}/analysis/*")
        for p in named_analysis:
            print(f"!{rel}/{p}")
        print("--- end block ---\n")

    if rc:
        print("STOP: a root's analysis/ does not reconcile with its SHA256SUMS.")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
