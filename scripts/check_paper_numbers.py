"""Fail if the manuscript has drifted from the results it claims to report.

Amendment F3 requires every number in the paper to point at its source. This
script is the enforcement: it re-derives the generated artifacts from the
frozen CSVs and compares them byte for byte with what is checked in, so a
manuscript cannot quietly keep a number after the CSV under it changed.

It also encodes four rules that were each learned by being violated:

* **The pooled table is not a source.** ``analysis/table-1.csv`` mixes fault
  regimes; Session 3B §F2 banned it. If any generated file mentions it, that is
  a defect.
* **The per-cell file must be keyed by regime.** Without that column a
  crash-free cell and a hard-Redis-kill cell can be averaged into one rate.
* **The bibliography must not be empty.** BibTeX emits empty ``\\bibitem``
  blocks for entries it failed to parse and LaTeX reports no undefined
  citation, so a blank bibliography compiles clean. Both failure modes hit this
  paper once.
* **The state-machine figure must match the code.** It is generated from the
  implementation's transition set.

Exit code 0 means every check passed. Any other value means do not submit.

Run it inside the locked environment -- the state-machine check imports the
implementation, which needs the project's dependencies:

    uv run --frozen python scripts/check_paper_numbers.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED_SOURCES = ("table-1.csv",)


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: list[str] = []

    def check(self, ok: bool, name: str, detail: str = "") -> None:
        if ok:
            self.passes.append(name)
            print(f"  PASS  {name}")
        else:
            self.failures.append(f"{name}: {detail}")
            print(f"  FAIL  {name}\n        {detail}")


def check_generated_tables(
    result: Result,
    paper: Path,
    analysis: Path,
    fsync_analysis: Path,
    flakey: Path,
) -> None:
    """Regenerate into a temp dir and diff against what is committed.

    Amendment G1 widened what "the numbers" means. The deployment-choice
    table and the host-level write-loss macros are claims in the same sense
    the outcome rates are, so they are regenerated here too rather than
    trusted because a script wrote them once. The two extra inputs are
    passed explicitly and their absence is a failure, not a silent skip: a
    gate that quietly checks less than it did yesterday is the failure mode
    this whole file exists to prevent.
    """
    generated = paper / "generated"
    for label, path in (
        ("appendfsync=always analysis", fsync_analysis),
        ("G2 write-loss results", flakey),
    ):
        result.check(path.is_dir(), f"{label} is present", f"missing {path}")
    with tempfile.TemporaryDirectory() as scratch:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "paper_tables.py"),
                "--analysis",
                str(analysis),
                "--fsync-analysis",
                str(fsync_analysis),
                "--flakey",
                str(flakey),
                "--out",
                scratch,
            ],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            result.check(
                False,
                "paper_tables.py runs",
                completed.stderr.strip() or completed.stdout.strip(),
            )
            return
        result.check(True, "paper_tables.py runs")

        for fresh in sorted(Path(scratch).glob("*.tex")):
            committed = generated / fresh.name
            if not committed.is_file():
                result.check(False, f"{fresh.name} exists", f"missing {committed}")
                continue
            same = committed.read_text(encoding="utf-8") == fresh.read_text(
                encoding="utf-8"
            )
            result.check(
                same,
                f"{fresh.name} matches the CSVs",
                "regenerate: python scripts/paper_tables.py "
                f"--analysis {analysis} --out {generated}",
            )


def check_no_banned_source(result: Result, paper: Path) -> None:
    """The banned table must not be *used*. Naming it in prose is fine.

    The first version of this check grepped for the filename anywhere in the
    generated files and duly failed on a comment that explained why the file
    is banned. What matters is whether a number was *drawn* from it, so the
    check reads the `% Source:` declarations only -- which is also why
    paper_tables.py is required to emit one.
    """
    offenders = []
    declared = 0
    for path in sorted((paper / "generated").glob("*.tex")):
        sources = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if re.match(r"^%\s*Sources?:", line, flags=re.IGNORECASE)
        ]
        declared += len(sources)
        for line in sources:
            for banned in BANNED_SOURCES:
                if banned in line:
                    offenders.append(f"{path.name}: {line.strip()}")
    result.check(
        not offenders,
        "no generated table draws from the banned pooled table",
        "; ".join(offenders),
    )
    result.check(
        declared > 0,
        "generated tables declare their sources",
        "no '% Source:' line found in paper/generated/*.tex",
    )


def check_macros_are_used(result: Result, paper: Path) -> None:
    """Every generated number must appear somewhere in the manuscript.

    A macro that is defined and never used is a number that was computed and
    then dropped, and the reader has no way to know it existed. That is a
    tolerable accident in a stable draft and a dangerous one during a framing
    revision, which is exactly when a claim gets moved, its replacement gets
    written, and its evidence gets orphaned. LaTeX catches the opposite
    direction -- a macro used and not defined -- and says nothing about this
    one.
    """
    numbers = paper / "generated" / "numbers.tex"
    if not numbers.is_file():
        result.check(False, "numbers.tex exists", f"missing {numbers}")
        return
    defined = set(
        re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", numbers.read_text(encoding="utf-8"))
    )
    used: set[str] = set()
    for path in [paper / "main.tex", *sorted((paper / "sections").glob("*.tex"))]:
        text = path.read_text(encoding="utf-8")
        used.update(re.findall(r"\\([A-Za-z]+)\{?\}?", text))
    orphans = sorted(defined - used)
    result.check(
        not orphans,
        "every generated number is used in the manuscript",
        f"{len(orphans)} orphaned: {', '.join(orphans)}",
    )


def check_per_cell_has_regime(result: Result, analysis: Path) -> None:
    path = analysis / "per-cell-metrics.csv"
    if not path.is_file():
        result.check(False, "per-cell-metrics.csv exists", f"missing {path}")
        return
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    result.check(
        "regime" in header,
        "per-cell-metrics.csv is keyed by regime",
        f"header is {header}",
    )


def check_state_machine(result: Result, paper: Path) -> None:
    target = paper / "figures" / "state-machine.tex"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "gen_state_machine.py"),
            "--check",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    result.check(
        completed.returncode == 0,
        "state-machine figure matches the transition table",
        (completed.stderr or completed.stdout).strip(),
    )


def check_bibliography(result: Result, paper: Path) -> None:
    """A blank bibliography compiles clean. Check the artifact, not the log."""
    bbl = paper / "main.bbl"
    if not bbl.is_file():
        result.check(
            False, "main.bbl exists", f"missing {bbl}; run bibtex first"
        )
        return
    text = bbl.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\\bibitem", text)[1:]
    empty = [
        block.splitlines()[0].strip()
        for block in blocks
        if len("\n".join(block.splitlines()[1:]).strip()) < 20
    ]
    result.check(len(blocks) > 0, "bibliography has entries", "no \\bibitem found")
    result.check(
        not empty,
        "no empty bibliography entries",
        f"{len(empty)} empty: {empty[:5]}",
    )

    blg = paper / "main.blg"
    if blg.is_file():
        log = blg.read_text(encoding="utf-8", errors="replace")
        bad = [
            line
            for line in log.splitlines()
            if "I was expecting" in line
            or "missing a field name" in line
            or "skipping whatever remains" in line
        ]
        result.check(
            not bad, "bibtex reported no parse errors", "; ".join(bad[:3])
        )


def check_undefined_references(result: Result, paper: Path) -> None:
    log = paper / "main.log"
    if not log.is_file():
        result.check(False, "main.log exists", f"missing {log}")
        return
    text = log.read_text(encoding="utf-8", errors="replace")
    undefined = [
        line
        for line in text.splitlines()
        if "Warning" in line
        and ("undefined" in line or "Citation" in line)
        and "Font" not in line
    ]
    result.check(
        not undefined,
        "no undefined references or citations",
        "; ".join(undefined[:3]),
    )


def check_todos(result: Result, paper: Path) -> None:
    """\\todoitem is permitted, but it must be counted and reported."""
    found: list[str] = []
    for path in sorted((paper / "sections").glob("*.tex")):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if r"\todoitem" in line:
                found.append(f"{path.name}:{number}")
    print(f"  NOTE  {len(found)} \\todoitem marker(s): {', '.join(found)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=ROOT / "paper")
    parser.add_argument(
        "--analysis",
        type=Path,
        default=ROOT / "experiments" / "results" / "matrix" / "analysis",
    )
    parser.add_argument(
        "--fsync-analysis",
        type=Path,
        default=ROOT / "experiments" / "results" / "fsync-always" / "analysis",
    )
    parser.add_argument(
        "--flakey",
        type=Path,
        default=ROOT / "experiments" / "results",
    )
    arguments = parser.parse_args()

    print("=" * 70)
    print("check_paper_numbers.py -- the manuscript against its results")
    print("=" * 70)
    print(f"paper          {arguments.paper}")
    print(f"analysis       {arguments.analysis}")
    print(f"fsync analysis {arguments.fsync_analysis}")
    print(f"flakey results {arguments.flakey}")
    print()

    result = Result()
    check_per_cell_has_regime(result, arguments.analysis)
    check_generated_tables(
        result,
        arguments.paper,
        arguments.analysis,
        arguments.fsync_analysis,
        arguments.flakey,
    )
    check_no_banned_source(result, arguments.paper)
    check_macros_are_used(result, arguments.paper)
    check_state_machine(result, arguments.paper)
    check_bibliography(result, arguments.paper)
    check_undefined_references(result, arguments.paper)
    check_todos(result, arguments.paper)

    print()
    print("-" * 70)
    print(f"{len(result.passes)} passed, {len(result.failures)} failed")
    if result.failures:
        print("\nDO NOT SUBMIT:")
        for failure in result.failures:
            print(f"  - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
