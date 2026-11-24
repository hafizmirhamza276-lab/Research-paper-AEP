"""Recover, from evidence that exists on this host right now, where each
collection was written and what its Redis AOF sat on.

Why now
-------
`docs/24-revision-backlog.md` B1 (Phase-8.2 addendum) requires B1 to read
`redis_storage_backing` from its own runs *and* from the frozen ones and state
how they differ. Phase 10 established that no tracked file records that field
for any collection, and that `experiments/harness/provenance.py` -- which
records it -- did not exist until 2026-08-27. Everything collected before then
carries no `environment` block at all.

That does not mean the answer is unrecoverable. It means the answer lives in
the host's live state rather than in a field, and the host is degrading. This
script extracts it while it can.

Four independent classes of evidence, in decreasing strength
------------------------------------------------------------
1. **The run's own `environment` block.** Recorded by the harness at run
   construction. This is the only thing that DETERMINES a filesystem.
2. **Absolute paths inside the collection's own artifacts.** A Python traceback
   captured into `matrix-progress.jsonl` names the file that raised it, with
   its absolute path. `results_root` is recorded relative to the process's
   working directory, so an absolute path to the *harness source* determines
   the working directory and therefore the collection path.
3. **Inode change time against modification time.** Neither ext4 nor this
   host's v9fs lets userspace set `ctime`: `cp -a` and `rsync -a` restore
   `mtime` and stamp `ctime` with the copy. `ctime == mtime` across a whole
   collection therefore means it was written where it sits. It was measured on
   both filesystems before being relied on (see `--probe-ctime`).
4. **A phase report's own statement.** Weakest, because a report is a claim
   rather than a measurement, and is used only where 1-3 are silent.

The confidence levels are the prompt's: DETERMINED / INFERRED / UNDETERMINED,
and an inference is never promoted to a determination -- including where the
inference is, in the author's judgement, obviously right.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

#: The collection roots this host holds, keyed the way the Phase 11 archive
#: names them. Source of truth: ARCHIVE-METADATA.json written by
#: scripts/build_raw_archive.py.
ARCHIVE_METADATA = "/root/aep-raw-archive/ARCHIVE-METADATA.json"

#: Absolute paths that would place a harness process's working directory.
#: `/mnt/<letter>/...` is a drvfs path; `/root/...` and `/home/...` are the
#: distro's own. Windows-style paths would appear as `D:\...`.
_ABS = re.compile(
    r"(?:/root/[A-Za-z0-9._/-]{3,120}"
    r"|/home/[A-Za-z0-9._/-]{3,120}"
    r"|/mnt/[a-z]/[A-Za-z0-9._/-]{3,120}"
    r"|[A-Z]:\\\\[A-Za-z0-9._\\\\-]{3,120})"
)

#: Files worth scanning for an absolute path. Deliberately narrow: these are the
#: orchestrator's own top-level logs, where a traceback would land. Scanning
#: every event log of 1400 runs costs minutes and adds nothing -- the harness
#: writes relative paths everywhere else, which is why this is scarce evidence.
_SCAN = (
    "matrix-progress.jsonl",
    "matrix-plan.json",
    "matrix-plan-full.json",
    "MANIFEST.md",
)


def iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def mount_entry(path: str) -> dict[str, str]:
    """Longest-prefix mount entry for `path`, as /proc/mounts has it NOW."""
    best: dict[str, str] = {}
    target = os.path.abspath(path)
    for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        point = fields[1]
        if target == point or target.startswith(point.rstrip("/") + "/"):
            if len(point) >= len(best.get("mount_point", "")):
                best = {
                    "device": fields[0],
                    "mount_point": point,
                    "type": fields[2],
                    "options": fields[3],
                }
    return best


def recorded_environment(root: Path) -> dict:
    """What the runs themselves recorded, and whether they all agree.

    Unanimity matters: a root whose runs disagree about their own filesystem is
    a root that was collected across a change, and reporting the first run's
    value would hide that.
    """
    filesystems: dict[str, int] = {}
    backings: dict[str, int] = {}
    results_roots: dict[str, int] = {}
    total = 0
    without = 0
    sample_fs = None
    sample_backing = None
    for cfg in sorted(root.glob("*/run-config.json")):
        total += 1
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        results_roots[str(data.get("results_root"))] = (
            results_roots.get(str(data.get("results_root")), 0) + 1
        )
        env = data.get("environment")
        if not env:
            without += 1
            continue
        fs = env.get("results_root_filesystem")
        if fs:
            key = json.dumps(fs, sort_keys=True)
            filesystems[key] = filesystems.get(key, 0) + 1
            sample_fs = fs
        backing = env.get("redis_storage_backing")
        if backing:
            key = json.dumps(backing, sort_keys=True)
            backings[key] = backings.get(key, 0) + 1
            sample_backing = backing
    return {
        "runs": total,
        "runs_without_environment_block": without,
        "distinct_results_root_values": results_roots,
        "distinct_filesystems": len(filesystems),
        "distinct_redis_storage_backings": len(backings),
        "filesystem": sample_fs,
        "redis_storage_backing": sample_backing,
        "unanimous": len(filesystems) <= 1 and len(backings) <= 1,
    }


def absolute_paths(root: Path) -> dict[str, list[str]]:
    """Absolute paths recorded by the collection's own orchestrator artifacts."""
    found: dict[str, list[str]] = {}
    for name in _SCAN:
        path = root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = sorted(set(_ABS.findall(text)))
        if hits:
            found[name] = hits
    return found


def inode_evidence(root: Path) -> dict:
    """Was this collection WRITTEN here, or copied here afterwards?"""
    cfgs = sorted(root.glob("*/run-config.json"))
    if not cfgs:
        return {"runs": 0}
    stats = [c.stat() for c in cfgs]
    mtimes = sorted(s.st_mtime for s in stats)
    ctimes = sorted(s.st_ctime for s in stats)
    lags = sorted(s.st_ctime - s.st_mtime for s in stats)
    median = lags[len(lags) // 2]
    return {
        "runs": len(cfgs),
        "mtime_first": iso(mtimes[0]),
        "mtime_last": iso(mtimes[-1]),
        "ctime_first": iso(ctimes[0]),
        "ctime_last": iso(ctimes[-1]),
        "ctime_minus_mtime_seconds": {
            "min": round(lags[0], 1),
            "median": round(median, 1),
            "max": round(lags[-1], 1),
        },
        "written_in_place": abs(median) < 5,
    }


def probe_ctime(directory: Path) -> dict:
    """Does `ctime` mean what this script needs it to mean, on THIS filesystem?

    Relying on an inode field across two filesystems -- one of them a 9p mount
    onto Windows -- without checking it would be exactly the assumption
    `docs/24-revision-backlog.md` B19 is about.
    """
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / "ctime-probe.txt"
    probe.write_text("probe\n", encoding="utf-8")
    fresh = probe.stat()
    os.utime(probe, (fresh.st_atime - 86400, fresh.st_mtime - 86400))
    aged = probe.stat()
    result = {
        "path": str(directory),
        "filesystem": mount_entry(str(directory)).get("type"),
        "fresh_write_ctime_equals_mtime": abs(fresh.st_ctime - fresh.st_mtime) < 2,
        "after_backdating_mtime_ctime_stays_now": (aged.st_ctime - aged.st_mtime)
        > 86000,
    }
    probe.unlink(missing_ok=True)
    result["usable"] = (
        result["fresh_write_ctime_equals_mtime"]
        and result["after_backdating_mtime_ctime_stays_now"]
    )
    return result


def classify(root_label: str, recorded: dict, absolutes: dict, inode: dict) -> dict:
    """Confidence for the two questions, with the reason stated."""
    fs_conf, fs_value, fs_why = "UNDETERMINED", None, []
    bk_conf, bk_value, bk_why = "UNDETERMINED", None, []

    if recorded.get("filesystem"):
        fs_conf = "DETERMINED"
        fs_value = recorded["filesystem"]
        fs_why.append(
            "the runs' own environment.results_root_filesystem, recorded at run "
            f"construction, unanimous across {recorded['runs']} runs"
            if recorded["unanimous"]
            else "the runs' own environment.results_root_filesystem, BUT THE RUNS "
            "DISAGREE -- see distinct_filesystems"
        )
    else:
        if absolutes:
            fs_conf = "INFERRED"
            fs_why.append(
                "no environment block; the collection's own orchestrator "
                "artifacts record absolute paths to the harness source, which "
                "fix the working directory the relative results_root resolves "
                "against"
            )
        if inode.get("written_in_place"):
            fs_conf = "INFERRED" if fs_conf == "UNDETERMINED" else fs_conf
            fs_why.append(
                "ctime == mtime across every run, so the collection was written "
                "where it sits rather than copied here"
            )
        elif inode.get("runs"):
            fs_why.append(
                "ctime is later than mtime across every run: the inodes were "
                "touched after the write, so where the bytes sit now is NOT "
                "evidence of where they were written"
            )

    if recorded.get("redis_storage_backing"):
        bk_conf = "DETERMINED"
        bk_value = recorded["redis_storage_backing"]
        bk_why.append(
            "the runs' own environment.redis_storage_backing, from docker "
            "inspect at run construction"
        )
    else:
        bk_why.append(
            "no environment block: provenance.py did not exist when this was "
            "collected, and nothing else in a run artifact names the AOF's "
            "storage"
        )

    return {
        "results_root_filesystem": {
            "confidence": fs_conf,
            "value": fs_value,
            "evidence": fs_why,
        },
        "redis_storage_backing": {
            "confidence": bk_conf,
            "value": bk_value,
            "evidence": bk_why,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metadata", default=ARCHIVE_METADATA)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    metadata = json.loads(Path(arguments.metadata).read_text(encoding="utf-8"))

    report: dict = {
        "ctime_probe": [
            probe_ctime(Path("/root/.aep-ctime-probe")),
            probe_ctime(
                Path("/mnt/d/personal/AEP/Research-paper-AEP/.scratch/.ctime-probe")
            ),
        ],
        "mounts_now": {
            "/": mount_entry("/"),
            "/mnt/d": mount_entry("/mnt/d"),
            "/var/lib/docker": mount_entry("/var/lib/docker"),
        },
        "roots": {},
    }

    print("=== is ctime usable on each filesystem? ===")
    for probe in report["ctime_probe"]:
        print(
            f"  {str(probe['path']):58s} {probe['filesystem']:10s} "
            f"usable={probe['usable']}"
        )
    print()

    for entry in metadata["roots"]:
        root = Path(entry["source_path"])
        if not root.is_dir():
            continue
        recorded = recorded_environment(root)
        absolutes = absolute_paths(root)
        inode = inode_evidence(root)
        verdict = classify(entry["label"], recorded, absolutes, inode)
        report["roots"][entry["label"]] = {
            "source_path": entry["source_path"],
            "mount_now": mount_entry(entry["source_path"]),
            "recorded": recorded,
            "absolute_paths_in_artifacts": absolutes,
            "inode_evidence": inode,
            "verdict": verdict,
        }
        print(f"{entry['label']}")
        print(f"    path now   {entry['source_path']}")
        m = report["roots"][entry["label"]]["mount_now"]
        print(f"    mount now  {m.get('type')} on {m.get('device')} at {m.get('mount_point')}")
        print(
            f"    recorded   {recorded['runs']} runs, "
            f"{recorded['runs_without_environment_block']} without an environment block"
        )
        print(
            f"    inode      mtime {inode.get('mtime_first')} .. {inode.get('mtime_last')}"
        )
        print(
            f"               ctime {inode.get('ctime_first')} .. {inode.get('ctime_last')}"
            f"   written_in_place={inode.get('written_in_place')}"
        )
        if absolutes:
            for name, hits in absolutes.items():
                print(f"    abs paths  {name}: {len(hits)} distinct, e.g. {hits[0]}")
        print(
            f"    FILESYSTEM {verdict['results_root_filesystem']['confidence']}"
            f"   BACKING {verdict['redis_storage_backing']['confidence']}"
        )
        print()

    counts: dict[str, int] = {}
    for value in report["roots"].values():
        for field in ("results_root_filesystem", "redis_storage_backing"):
            key = f"{field}:{value['verdict'][field]['confidence']}"
            counts[key] = counts.get(key, 0) + 1
    report["summary"] = counts
    print("=== summary ===")
    for key in sorted(counts):
        print(f"  {key:42s} {counts[key]}")

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
