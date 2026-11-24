"""Fail when a commit flips a file's line endings wholesale.

**Three times a tool rewrote a CRLF file as LF.** `CITATION.cff` and
`paper/arxiv-metadata.md` were caught before their commits; `docs/33-agent-
workload.md` was not, and shipped as `b379809` — a commit whose real change was
44 insertions and 7 deletions but which reads as 885/833 because every line
changed. A reader running `git log` on that file sees a whole-document rewrite
at the commit that corrected two status lines, and cannot tell from the diff
which it was. The repair cost a third commit (`5494f9c`).

**Why the repository is exposed.** `core.autocrlf` is `false` locally, so git
performs no conversion: whatever bytes a tool writes are the bytes that get
stored. `.gitattributes` declares a policy for exactly two things —
`experiments/results/** -text` and `*.sh text eol=lf` — and says nothing about
the other 3 000 files. Endings are therefore an accident of whichever editor
touched a file last, and 216 tracked files carry CRLF while 2 487 carry LF.

**Why not `* text=auto`.** It would renormalise every unprotected file on the
next touch, including twelve frozen analysis CSVs under `reports/raw/` and three
raw captures with deliberately mixed endings. `.gitattributes`'s own comment
records why that is unacceptable: those bytes are evidence, and
`sha256sum -c` over a manifest fails if a single byte moves. The policy stays
narrow and this gate covers the gap instead.

**What this checks.** For every file changed between two revisions, compare the
dominant line ending before and after. A flip — CRLF-dominant to LF-dominant or
back — fails, because it is never what the author meant and it destroys the
readability of the diff. A file whose *content* changed keeps whatever endings
it had.

Usage:
    python scripts/check_line_endings.py                  # HEAD~1..HEAD
    python scripts/check_line_endings.py --staged         # index vs HEAD
    python scripts/check_line_endings.py --base REF       # REF..HEAD
    python scripts/check_line_endings.py --commit REF     # REF~1..REF

A flip that *is* intended -- normalising a file on purpose -- passes only when
named: ``--allow PATH``. Naming it is the point. A deliberate normalisation is
a decision someone made and should appear on the command line or in the CI
config, not be indistinguishable from an accident.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: A file whose stored bytes are evidence and whose endings are deliberate.
#: Listed rather than inferred: these are the paths `.gitattributes` marks
#: `-text`, plus the raw captures whose mixed endings are what the tool emitted.
#: A flip in one of these is *more* serious, not less, so they are not skipped —
#: the tuple exists to document that the gate deliberately covers them.
EVIDENCE_PREFIXES = (
    "experiments/results/",
    "reports/raw/",
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=False, check=False
    ).stdout.decode("utf-8", errors="replace")


def blob(rev: str, path: str) -> bytes | None:
    """The file's bytes at a revision, or None if it did not exist there."""
    completed = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=ROOT, capture_output=True, check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def staged_blob(path: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=ROOT, capture_output=True, check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def profile(data: bytes) -> tuple[str, int, int]:
    """(dominant ending, crlf count, lone-lf count).

    Counted on bytes, never on decoded text: a file that is not valid UTF-8 is
    still a file whose endings can flip.
    """
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf == 0 and lf == 0:
        return "none", 0, 0
    if crlf and lf:
        return "mixed", crlf, lf
    return ("crlf" if crlf else "lf"), crlf, lf


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8000]


def check(before: str | None, staged: bool, commit: str | None = None,
          allow: tuple[str, ...] = ()) -> int:
    if commit:
        changed = git("diff", "--name-only", "--diff-filter=M",
                      f"{commit}~1", commit)
        after_of = lambda p: blob(commit, p)  # noqa: E731
        after_label = commit
        before = f"{commit}~1"
    elif staged:
        changed = git("diff", "--cached", "--name-only", "--diff-filter=M")
        after_of = staged_blob
        after_label = "the index"
    else:
        base = before or "HEAD~1"
        changed = git("diff", "--name-only", "--diff-filter=M", base, "HEAD")
        after_of = lambda p: blob("HEAD", p)  # noqa: E731
        after_label = "HEAD"
        before = base

    paths = [p for p in changed.splitlines() if p.strip()]
    if not paths:
        print("  no modified files to check")
        return 0

    if commit:
        base_rev = f"{commit}~1"
    else:
        base_rev = "HEAD" if staged else (before or "HEAD~1")
    flips: list[str] = []
    checked = 0

    for path in paths:
        old = blob(base_rev, path)
        new = after_of(path)
        if old is None or new is None:
            continue
        if is_binary(old) or is_binary(new):
            continue
        checked += 1
        old_kind, old_crlf, old_lf = profile(old)
        new_kind, new_crlf, new_lf = profile(new)
        if old_kind in ("none",) or new_kind in ("none",):
            continue
        if old_kind != new_kind:
            if path in allow:
                print(f"  ALLOWED flip (named on the command line): {path}")
                continue
            evidence = any(path.startswith(p) for p in EVIDENCE_PREFIXES)
            flips.append(
                f"  {path}\n"
                f"      {base_rev}: {old_kind} ({old_crlf} CRLF, {old_lf} LF)\n"
                f"      {after_label}: {new_kind} ({new_crlf} CRLF, {new_lf} LF)"
                + ("\n      *** this path is tracked evidence; its bytes are "
                   "covered by a SHA-256 manifest ***" if evidence else "")
            )

    print(f"  {checked} modified text file(s) compared")
    if not flips:
        print("  OK: no file changed its dominant line ending")
        return 0

    print()
    print(f"LINE ENDINGS FLIPPED in {len(flips)} file(s):")
    for entry in flips:
        print(entry)
    print()
    print("A flip is never an intended edit. It makes every line read as changed,")
    print("so the diff no longer shows what the commit did. Rewrite the file with")
    print("the endings it had -- read the bytes, keep them -- and commit again.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base", default=None,
        help="compare this revision against HEAD (default: HEAD~1)",
    )
    parser.add_argument(
        "--staged", action="store_true",
        help="compare the index against HEAD, for a pre-commit check",
    )
    parser.add_argument(
        "--commit", default=None,
        help="compare this commit against its parent",
    )
    parser.add_argument(
        "--allow", action="append", default=[], metavar="PATH",
        help="a flip in this path is deliberate; repeat per path",
    )
    arguments = parser.parse_args(argv)
    return check(
        arguments.base, arguments.staged, arguments.commit,
        tuple(arguments.allow),
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
