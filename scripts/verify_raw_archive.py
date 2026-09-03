"""Is the archive *sufficient*? Extract it, re-derive, and byte-compare.

An archive that contains files is not the same as an archive from which the
paper can be rebuilt. This script answers the only question that matters for
`ARTIFACT.md` §5: **starting from nothing but the tarball, do you get back the
analysis products the manuscript's numbers are computed from, byte for byte?**

Method, in order:

1. extract `aep-raw-evidence.tar` to a scratch path;
2. check every extracted file against `MANIFEST.sha256`;
3. for each root that produced a tracked `analysis/` directory, run
   `experiments.analyze` over the *extracted* copy -- never over the source, so
   the source cannot be written to even by accident -- with the bootstrap seed
   and resample count each root's own `coverage.json` records;
4. byte-compare every tracked analysis file against its regenerated twin.

A mismatch is reported, with its size and first differing offset. It is a
finding about the evidence, not an error to suppress: it says either that the
archive is missing something, or that the tracked product was not produced by
the code that is in the tree now.

Distinguishing those two is the whole point, so every file that differs is
compared a second time under two **named, declared-in-advance** normalisations,
each corresponding to a change to `experiments/analyze.py` made after the
tracked product was frozen:

* ``regime-label`` -- the crash-always regime is written ``(session-3)`` in
  products frozen on 2026-08-10 and ``crashed`` by today's `analyze.py:406`.
  Phase 10 recorded this as finding F5.
* ``added-columns`` -- `per-execution.csv` has gained `redis_kill_latency_ms`
  and `durability_ack_observed` since the freeze. Columns present in the
  re-derivation and absent from the tracked header are dropped.

A file that is identical **after** a normalisation is reported as
``IDENTICAL (normalised: ...)``, never as ``IDENTICAL``. A file that is still
different afterwards is the finding this script exists to surface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: archive label -> tracked analysis directory, for the roots that produced one.
#: Roots with no tracked analysis (`voided`, the operator-aborted session, the
#: two Phase 10 VOIDED trees) are extracted and manifest-checked but have
#: nothing to compare against, and are listed as such.
TRACKED: dict[str, str] = {
    "matrix": "experiments/results/matrix/analysis",
    "fsync-always": "experiments/results/fsync-always/analysis",
    "b2-2026-08-21": "experiments/results/b2-2026-08-21/analysis",
    "b2-s1-2026-08-21": "experiments/results/b2-s1-2026-08-21/analysis",
    "b2-s2-2026-08-21": "experiments/results/b2-s2-2026-08-21/analysis",
    "b2-s3-2026-08-21": "experiments/results/b2-s3-2026-08-21/analysis",
    "b2-paired-s1-2026-08-28": "experiments/results/b2-paired-s1-2026-08-28/analysis",
    "b2-paired-v2-s1-2026-08-28": (
        "experiments/results/b2-paired-v2-s1-2026-08-28/analysis"
    ),
    "b2-paired-v2-s2-2026-08-28": (
        "experiments/results/b2-paired-v2-s2-2026-08-28/analysis"
    ),
    "b2-paired-v2-s3-2026-08-28": (
        "experiments/results/b2-paired-v2-s3-2026-08-28/analysis"
    ),
    "b2-paired-v2-s4-2026-08-28": (
        "experiments/results/b2-paired-v2-s4-2026-08-28/analysis"
    ),
    "b2-paired-v2-s2-aborted-2026-08-28": (
        "experiments/results/b2-paired-v2-s2-aborted-2026-08-28/analysis"
    ),
    "phase10-replication-ext4-2026-09-02": (
        "experiments/results/phase10-replication-ext4-2026-09-02/analysis"
    ),
    "phase10-replication-ext4-arbb30-2026-09-02": (
        "experiments/results/phase10-replication-ext4-arbb30-2026-09-02/analysis"
    ),
    "phase10-replication-drvfs-2026-09-02": (
        "experiments/results/phase10-replication-drvfs-2026-09-02/analysis"
    ),
    "phase10-replication-drvfs-arbb30-2026-09-02": (
        "experiments/results/phase10-replication-drvfs-arbb30-2026-09-02/analysis"
    ),
}

#: `analysis/comparisons-vs-aep-full.csv` is the one tracked results file that
#: `analyze.py` did not produce. `ARTIFACT.md` §5 records why: the frozen copy
#: pooled three fault regimes, which §VI-A forbids, and was regenerated
#: regime-labelled by `experiments/rebuild_comparisons.py` in `b9617e4`.
#: Comparing it against `analyze.py`'s output would report a difference that is
#: a fact about the repository's history rather than about the archive.
_REBUILT_BY_REBUILD_COMPARISONS = "comparisons-vs-aep-full.csv"

#: PDFs are compared but never expected to match: matplotlib stamps the
#: wall-clock into every file it writes, which the Makefile's own figure
#: comparison normalises away. Reported separately so a real plotted-value
#: change is not hidden inside "PDFs differ".
_TIMESTAMPED = (".pdf",)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


#: The crash-always regime under the two labels it has been written with.
_FROZEN_REGIME_LABEL = "(session-3)"
_CURRENT_REGIME_LABEL = "crashed"


def tracked_files(rel_dir: str) -> list[str]:
    """File names git tracks in `rel_dir`.

    Globbing the working tree instead would compare untracked residue -- old
    `figure-*.pdf` and `comparisons-vs-aep-full.csv` left in several analysis
    directories by ad-hoc re-runs -- and report differences in files no reader
    of the repository can even see.
    """
    out = subprocess.run(
        ["git", "ls-files", "--", rel_dir],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(
        Path(line).name for line in out.stdout.splitlines() if line.strip()
    )


def _normalise(
    name: str, tracked_text: str, regenerated_text: str
) -> tuple[str, list[str]]:
    """Apply the two declared normalisations to the regenerated text.

    Returns the normalised text and the names of the normalisations that
    actually changed anything, so the report can say which one was needed.
    """
    if name.endswith(".json"):
        # `coverage.json` lists the regimes present. Its only post-freeze
        # difference is the same label rename, and it is a JSON string there
        # rather than a CSV field.
        if (
            f'"{_FROZEN_REGIME_LABEL}"' in tracked_text
            and f'"{_CURRENT_REGIME_LABEL}"' in regenerated_text
        ):
            return (
                regenerated_text.replace(
                    f'"{_CURRENT_REGIME_LABEL}"', f'"{_FROZEN_REGIME_LABEL}"'
                ),
                ["regime-label"],
            )
        return regenerated_text, []

    applied: list[str] = []

    # keepends: these CSVs are written by csv.DictWriter, whose default line
    # terminator is CRLF. Splitting on line boundaries and rejoining with "\n"
    # would silently rewrite every line ending and make a byte comparison
    # report a difference that is entirely this function's doing.
    tracked_lines = tracked_text.splitlines(keepends=True)
    lines = regenerated_text.splitlines(keepends=True)
    if not tracked_lines or not lines or "," not in tracked_lines[0]:
        return regenerated_text, applied

    tracked_header = tracked_lines[0].rstrip("\r\n").split(",")
    header = lines[0].rstrip("\r\n").split(",")

    keep = list(range(len(header)))
    if header[: len(tracked_header)] == tracked_header and len(header) > len(
        tracked_header
    ):
        keep = list(range(len(tracked_header)))
        applied.append("added-columns")

    # Substitute the regime label in the `regime` COLUMN only. A plain text
    # replace is wrong here and was wrong once: `per-execution.csv` also has a
    # column *named* `crashed`, so replacing the string rewrote the header.
    regime_index = (
        tracked_header.index("regime") if "regime" in tracked_header else None
    )
    relabelled = False

    rebuilt: list[str] = []
    for number, line in enumerate(lines):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        fields = body.split(",")
        if len(fields) == len(header):
            fields = [fields[i] for i in keep]
        if (
            number > 0
            and regime_index is not None
            and regime_index < len(fields)
            and fields[regime_index] == _CURRENT_REGIME_LABEL
        ):
            fields[regime_index] = _FROZEN_REGIME_LABEL
            relabelled = True
        rebuilt.append(",".join(fields) + ending)

    if relabelled:
        applied.append("regime-label")
    return "".join(rebuilt), applied


def _first_difference(a: Path, b: Path) -> int | None:
    """Byte offset of the first difference, or None if identical."""
    with a.open("rb") as fa, b.open("rb") as fb:
        offset = 0
        while True:
            ba, bb = fa.read(65536), fb.read(65536)
            if not ba and not bb:
                return None
            if ba != bb:
                for i in range(min(len(ba), len(bb))):
                    if ba[i] != bb[i]:
                        return offset + i
                return offset + min(len(ba), len(bb))
            offset += len(ba)


def extract(tar_path: Path, into: Path) -> int:
    into.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(tar_path, "r") as tar:
        for member in tar:
            if not member.isreg():
                continue
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError(f"refusing unsafe archive member: {member.name}")
            tar.extract(member, path=into, set_attrs=False)
            count += 1
    return count


def check_manifest(manifest: Path, extracted: Path) -> tuple[int, list[str]]:
    bad: list[str] = []
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        sha, _, name = line.partition("  ")
        path = extracted / name
        if not path.exists():
            bad.append(f"MISSING {name}")
            continue
        checked += 1
        if _sha(path) != sha:
            bad.append(f"DIGEST  {name}")
    return checked, bad


def bootstrap_params(tracked_analysis: Path) -> tuple[int, int]:
    """(seed, resamples) as the tracked coverage.json records them.

    Re-deriving with different parameters would produce different intervals and
    a mismatch that says nothing about the archive.
    """
    coverage = tracked_analysis / "coverage.json"
    if coverage.exists():
        data = json.loads(coverage.read_text(encoding="utf-8"))
        seed = data.get("bootstrap_seed")
        resamples = data.get("bootstrap_resamples")
        if seed is not None and resamples is not None:
            return int(seed), int(resamples)
    # fsync-always tracks only two CSVs and no coverage.json; the project's
    # defaults are what produced them.
    return 20260806, 10000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", default="/root/aep-raw-archive")
    parser.add_argument("--scratch", default="/root/aep-archive-verify")
    parser.add_argument("--json", default=None)
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="reuse an existing extraction (for re-running the comparison only)",
    )
    arguments = parser.parse_args(argv)

    archive = Path(arguments.archive)
    scratch = Path(arguments.scratch)
    extracted = scratch / "extract"
    derived = scratch / "derived"

    report: dict = {"steps": {}}

    if not arguments.skip_extract:
        print(f"extracting {archive / 'aep-raw-evidence.tar'} -> {extracted}")
        started = time.monotonic()
        count = extract(archive / "aep-raw-evidence.tar", extracted)
        print(f"  {count} files in {time.monotonic() - started:.1f}s")
        report["steps"]["extract"] = {"files": count}

    print("checking the extraction against MANIFEST.sha256")
    checked, bad = check_manifest(archive / "MANIFEST.sha256", extracted)
    print(f"  {checked} files verified, {len(bad)} problems")
    for line in bad[:40]:
        print(f"  {line}")
    report["steps"]["manifest"] = {"checked": checked, "problems": bad}

    derived.mkdir(parents=True, exist_ok=True)
    comparison: dict[str, dict] = {}
    totals = {
        "identical": 0,
        "identical_normalised": 0,
        "differs": 0,
        "missing": 0,
        "timestamped": 0,
    }

    for label, tracked_rel in TRACKED.items():
        root = extracted / label
        tracked = REPO / tracked_rel
        out = derived / label
        seed, resamples = bootstrap_params(tracked)
        print(f"\n=== {label} (seed {seed}, resamples {resamples}) ===")
        started = time.monotonic()
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "experiments.analyze",
                "--results-root",
                str(root),
                "--destination",
                str(out),
                "--bootstrap-seed",
                str(seed),
                "--resamples",
                str(resamples),
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        elapsed = round(time.monotonic() - started, 1)
        if proc.returncode != 0:
            print(f"  analyze.py exited {proc.returncode}")
            print("  " + "\n  ".join(proc.stderr.strip().splitlines()[-15:]))
            comparison[label] = {
                "analyze_returncode": proc.returncode,
                "analyze_stderr_tail": proc.stderr.strip().splitlines()[-15:],
                "seconds": elapsed,
                "files": {},
            }
            continue

        # `matrix`'s tracked comparisons file was NOT produced by analyze.py --
        # it was regenerated regime-labelled by rebuild_comparisons.py, which
        # ARTIFACT.md §5 records. Every other root's was produced by analyze.py.
        # So both candidate producers are run, into different files, and a match
        # from either counts -- with the report naming which one matched.
        rebuilt = subprocess.run(
            [
                sys.executable,
                "-m",
                "experiments.rebuild_comparisons",
                "--analysis",
                str(out),
                "--output",
                str(out / "comparisons-vs-aep-full.rebuilt.csv"),
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if rebuilt.returncode != 0:
            print(
                f"  rebuild_comparisons exited {rebuilt.returncode}: "
                f"{rebuilt.stderr.strip().splitlines()[-1:] or ['']}"
            )

        files: dict[str, str] = {}
        for name in tracked_files(tracked_rel):
            tracked_file = tracked / name
            regenerated = out / name
            if not regenerated.exists():
                files[name] = "NOT REGENERATED (analyze.py does not write it)"
                totals["missing"] += 1
                continue
            offset = _first_difference(tracked_file, regenerated)
            if offset is None:
                files[name] = "IDENTICAL"
                totals["identical"] += 1
                continue
            if tracked_file.suffix in _TIMESTAMPED:
                files[name] = (
                    f"DIFFERS (timestamped format) at byte {offset}; "
                    f"{tracked_file.stat().st_size} vs {regenerated.stat().st_size} bytes"
                )
                totals["timestamped"] += 1
                continue

            tracked_text = tracked_file.read_text(encoding="utf-8")
            normalised, applied = _normalise(
                name, tracked_text, regenerated.read_text(encoding="utf-8")
            )
            if applied and normalised == tracked_text:
                files[name] = f"IDENTICAL (normalised: {', '.join(applied)})"
                totals["identical_normalised"] += 1
            elif (
                name == _REBUILT_BY_REBUILD_COMPARISONS
                and (out / "comparisons-vs-aep-full.rebuilt.csv").exists()
                and _first_difference(
                    tracked_file, out / "comparisons-vs-aep-full.rebuilt.csv"
                )
                is None
            ):
                files[name] = "IDENTICAL (producer: rebuild_comparisons.py)"
                totals["identical"] += 1
            else:
                files[name] = (
                    f"DIFFERS at byte {offset}; "
                    f"{tracked_file.stat().st_size} vs "
                    f"{regenerated.stat().st_size} bytes"
                    + (f"; still differs after {', '.join(applied)}" if applied else "")
                )
                totals["differs"] += 1
        for name, verdict in files.items():
            print(f"  {verdict:70s} {name}")
        comparison[label] = {
            "analyze_returncode": 0,
            "seconds": elapsed,
            "files": files,
        }

    report["comparison"] = comparison
    report["totals"] = totals
    print("\n" + "=" * 78)
    print(
        f"IDENTICAL {totals['identical']}   "
        f"IDENTICAL-after-normalisation {totals['identical_normalised']}   "
        f"DIFFERS {totals['differs']}   "
        f"NOT REGENERATED {totals['missing']}   "
        f"DIFFERS-timestamped-PDF {totals['timestamped']}"
    )

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0 if not bad and totals["differs"] == 0 and totals["missing"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
