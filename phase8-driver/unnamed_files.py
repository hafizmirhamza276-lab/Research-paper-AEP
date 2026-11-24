#!/usr/bin/env python3
"""Which files inside a frozen root are NOT named by its SHA256SUMS.

Every count printed here comes from the listing. Nothing is carried from an
earlier reading -- an asserted count is how "16 files in analysis/" became "18"
and "seven unnamed files" became "eight" in the same task.

Read-only. stat and listing only; no file is opened for reading or writing.

Usage: unnamed_files.py <run root> [<run root> ...]
"""

from __future__ import annotations

import sys
from pathlib import Path


def named(root: Path) -> set[str]:
    out = set()
    raw = (root / "SHA256SUMS").read_text(encoding="utf-8", errors="replace")
    for line in raw.splitlines():
        line = line.rstrip("\r").strip()
        if not line:
            continue
        _, _, path = line.partition(" ")
        out.add(path.strip().lstrip("*").strip().replace("\\", "/"))
    return out


def main(argv: list[str]) -> int:
    for arg in argv:
        root = Path(arg).resolve()
        attested = named(root)

        top_files = sorted(p.name for p in root.iterdir() if p.is_file())
        analysis_files = sorted(p.name for p in (root / "analysis").iterdir())

        # SHA256SUMS is the manifest; it cannot name itself.
        top_unnamed = [f for f in top_files if f not in attested and f != "SHA256SUMS"]
        analysis_unnamed = [
            f for f in analysis_files if f"analysis/{f}" not in attested
        ]

        # Of the unnamed top-level files, which are duplicates of a hashed
        # artefact under analysis/ and which exist only at the top level?
        dup = [f for f in top_unnamed if f in analysis_files]
        only_top = [f for f in top_unnamed if f not in analysis_files]

        print(f"################ {root.name} ################")
        print(f"SHA256SUMS names                     : {len(attested)}")
        print(f"top-level files on disk              : {len(top_files)}")
        print(f"  named by SHA256SUMS                : "
              f"{len([f for f in top_files if f in attested])}")
        print(f"  SHA256SUMS itself                  : 1")
        print(f"  UNNAMED                            : {len(top_unnamed)}")
        for f in top_unnamed:
            tag = "also under analysis/, hashed there" if f in dup else "top level only"
            print(f"      {f:<32} {tag}")
        print(f"  of which duplicated under analysis/: {len(dup)}")
        print(f"  of which top-level only            : {len(only_top)}")
        print(f"analysis/ files unnamed              : {len(analysis_unnamed)} "
              f"{analysis_unnamed}")

        run_dirs = [p for p in root.iterdir() if p.is_dir() and p.name != "analysis"]
        all_files = [p for p in root.rglob("*") if p.is_file()]
        print(f"run directories                      : {len(run_dirs)}")
        print(f"ALL files anywhere in the root       : {len(all_files)}")
        print(f"attested fraction                    : {len(attested)}/{len(all_files)}"
              f" = {100 * len(attested) / len(all_files):.1f}%")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
