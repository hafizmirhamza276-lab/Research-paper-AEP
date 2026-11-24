#!/usr/bin/env python3
"""Resolve every `file:line` citation in the docs against the tree.

Until now docs/24-revision-backlog.md and docs/25-collection-tooling-rules.md
cited collection-driver files by line number while those files existed only
outside the repository. The citations were unresolvable for any reader. Now that
phase8-driver/ is tracked, each one can be checked -- and a citation that points
at the wrong line is worse than one that points at nothing, because it looks
resolved.

Prints the cited line so the claim can be judged, not just the fact that the line
exists. Read-only.

Usage: check_citations.py <doc> [<doc> ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# `name.ext:12` or `name.ext:12-17`, the forms actually used in these docs.
CITE = re.compile(r"`?([A-Za-z0-9_./-]+\.(?:py|sh|md|yml|json)):(\d+)(?:-(\d+))?`?")

# Where a bare filename lives, for citations written without a directory.
SEARCH_DIRS = ["", "phase8-driver/", "scripts/", "experiments/", "docs/"]


def resolve(name: str) -> Path | None:
    for d in SEARCH_DIRS:
        p = REPO / (d + name)
        if p.is_file():
            return p
    hits = list(REPO.rglob(name))
    return hits[0] if len(hits) == 1 else None


def main(argv: list[str]) -> int:
    bad = 0
    total = 0
    for doc in argv:
        dp = REPO / doc
        print(f"################ {doc} ################")
        for n, line in enumerate(dp.read_text(encoding="utf-8").splitlines(), 1):
            for m in CITE.finditer(line):
                name, start, end = m.group(1), int(m.group(2)), m.group(3)
                end = int(end) if end else start
                total += 1
                target = resolve(name)
                if target is None:
                    print(f"  {doc}:{n}  {name}:{start}  -> UNRESOLVED FILE")
                    bad += 1
                    continue
                body = target.read_text(encoding="utf-8", errors="replace").splitlines()
                if start > len(body):
                    print(f"  {doc}:{n}  {name}:{start}  -> OUT OF RANGE "
                          f"(file has {len(body)} lines)")
                    bad += 1
                    continue
                rel = target.relative_to(REPO).as_posix()
                for ln in range(start, min(end, len(body)) + 1):
                    print(f"  {doc}:{n}  {rel}:{ln}  | {body[ln - 1].rstrip()}")
        print()
    print(f"{total} citations checked, {bad} unresolvable or out of range")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
