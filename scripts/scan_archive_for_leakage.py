r"""What is in the raw evidence archive that a public deposit would expose?

Run **before** the archive is uploaded anywhere. 26 300 files written by a
harness that was never designed with publication in mind will contain whatever
the host happened to put in them, and the only way to know what that is, is to
look.

Two different questions, kept apart because they have different answers
-----------------------------------------------------------------------
**(A) Should any of this not be public at all?** Secrets, credentials, personal
data, anything belonging to a third party.

**(B) Does any of it break review anonymity?** The manuscript has an anonymous
build (`scripts/build_paper.sh --anonymous`). A deposit that a reviewer can open
and find the author's name in is a different problem from a deposit that leaks a
password, and conflating them produces the wrong remedy for both.

Author identity is **not** a leak for question (A): the deposit is made under the
author's own name and licence. It is only a question for (B).

The category list is this script's own
--------------------------------------
The phase correction asked for "all the listed categories" from an earlier
specification. **No such list exists in the session this was written in**, so the
categories below are derived here from what is actually at risk in this artifact,
and this is stated rather than glossed. Changing the list is a one-line edit to
``CATEGORIES`` and a re-run.

For each category the report answers the three questions the correction asks:

* **reviewer-visible** -- does it occur in a file a reader would plausibly open?
  A run's `run-config.json` and `summary.json` are read; the twelfth
  `events-worker-1-attempt-5.jsonl` of run 300 is not, unless something points
  at it.
* **removing it breaks a digest** -- every file is covered by `MANIFEST.sha256`
  and by the tar's own digest, so *any* edit invalidates both and the archive
  must be rebuilt and re-verified. Recorded per category anyway, because the
  answer is what makes "just strip it" not free.
* **load-bearing for docs/28** -- `docs/28-storage-backing-recovery.md` §3.1
  DETERMINES the frozen `matrix` collection's path from absolute paths inside
  the collection's own artifacts. Removing those paths would delete the only
  evidence that determination rests on.

Nothing is stripped. This script reads and reports.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Category:
    key: str
    why: str
    pattern: re.Pattern[bytes]
    #: True when finding this would stop a publication outright.
    blocking: bool
    #: Whether it bears on anonymity (B) rather than on disclosure (A).
    anonymity_only: bool


CATEGORIES: tuple[Category, ...] = (
    Category(
        "credential",
        "tokens, API keys, passwords, private keys -- the only category that "
        "would stop a deposit outright",
        re.compile(
            rb"(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|"
            rb"authorization:\s*bearer|password\s*[=:]\s*\S|"
            rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
            rb"gh[pousr]_[A-Za-z0-9]{16,}|xox[baprs]-[A-Za-z0-9-]{10,})"
        ),
        blocking=True,
        anonymity_only=False,
    ),
    Category(
        "email_address",
        "personal or corporate email addresses",
        re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "windows_user_path",
        r"Windows paths naming the account, e.g. C:\Users\<name>",
        re.compile(rb"(?i)[A-Z]:\\\\?Users\\\\?[A-Za-z0-9._-]+"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "windows_drive_path",
        r"any Windows drive path, e.g. D:\personal\AEP",
        re.compile(rb"[A-Z]:\\\\?[A-Za-z0-9._\\-]{2,}"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "wsl_absolute_path",
        "absolute POSIX paths revealing the host's directory layout -- and the "
        "evidence docs/28 3.1 determines the matrix collection path from",
        re.compile(rb"/(?:root|home)/[A-Za-z0-9._/-]{3,}"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "drvfs_mount_path",
        "/mnt/<letter>/... paths, which name the Windows-side layout",
        re.compile(rb"/mnt/[a-z]/[A-Za-z0-9._/-]{3,}"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "hostname",
        "the collection host's name, recorded by provenance and by docker info",
        re.compile(rb"(?i)\bKP248\b"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "account_name",
        "OS or directory-service account names seen on this host",
        re.compile(rb"(?i)(?:AzureAD[\\+/]|\bhamzakhan\b|\bHamza\s?Khan\b)"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "non_loopback_ip",
        "IP addresses that are not loopback -- a routable address can identify "
        "a network. 127.0.0.1 and 0.0.0.0 are configuration, not identity.",
        re.compile(rb"\b(?!127\.|0\.0\.0\.0)(?:\d{1,3}\.){3}\d{1,3}\b"),
        blocking=False,
        anonymity_only=False,
    ),
    Category(
        "mac_address",
        "hardware addresses, which identify a specific machine",
        re.compile(rb"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"),
        blocking=False,
        anonymity_only=False,
    ),
    Category(
        "github_identity",
        "URLs or handles naming the author's accounts",
        re.compile(rb"(?i)github\.com/[A-Za-z0-9._-]+"),
        blocking=False,
        anonymity_only=True,
    ),
    Category(
        "env_dump",
        "wholesale environment dumps, which sweep in whatever was exported",
        re.compile(rb"(?i)\"(?:environ|env_vars|os_environ)\"\s*:"),
        blocking=False,
        anonymity_only=False,
    ),
)

#: Files a reader would plausibly open, in the order they would open them.
#: Everything else is bulk event data reached only by tooling.
REVIEWER_VISIBLE = (
    "run-config.json",
    "summary.json",
    "mock-api.yaml",
    "MANIFEST.md",
    "MANIFEST.csv",
    "SHA256SUMS",
    "README.md",
    "matrix-plan.json",
    "matrix-plan.txt",
    "matrix-progress.jsonl",
    "coverage.json",
    "ARCHIVE-METADATA.json",
)

#: The exact artifacts docs/28 3.1's DETERMINED verdict rests on.
LOAD_BEARING_FOR_DOCS28 = ("matrix-progress.jsonl", "matrix-plan.json")


@dataclass
class Hit:
    files: set[str] = field(default_factory=set)
    occurrences: int = 0
    samples: list[tuple[str, str]] = field(default_factory=list)
    reviewer_visible_files: set[str] = field(default_factory=set)
    load_bearing_files: set[str] = field(default_factory=set)
    #: Every DISTINCT matched string, capped. A count alone cannot be read: the
    #: first run of this scan reported 3 717 files of "non-loopback IP" and the
    #: distinct set turned out to be the kernel version 6.6.114.1. A category
    #: whose distinct values are not shown is a category that cannot be audited.
    values: set[str] = field(default_factory=set)


def is_reviewer_visible(name: str) -> bool:
    return Path(name).name in REVIEWER_VISIBLE


def is_load_bearing(name: str) -> bool:
    return Path(name).name in LOAD_BEARING_FOR_DOCS28


def scan(tar_path: Path, sample_limit: int, max_members: int | None) -> dict:
    hits: dict[str, Hit] = defaultdict(Hit)
    members_scanned = 0
    bytes_scanned = 0
    with tarfile.open(tar_path, "r|") as tar:
        for member in tar:
            if not member.isreg():
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            data = handle.read()
            members_scanned += 1
            bytes_scanned += len(data)
            for category in CATEGORIES:
                found = category.pattern.findall(data)
                if not found:
                    continue
                hit = hits[category.key]
                hit.files.add(member.name)
                hit.occurrences += len(found)
                if is_reviewer_visible(member.name):
                    hit.reviewer_visible_files.add(member.name)
                if is_load_bearing(member.name):
                    hit.load_bearing_files.add(member.name)
                for raw in found:
                    if isinstance(raw, tuple):
                        raw = raw[0]
                    if len(hit.values) < 200:
                        hit.values.add(raw.decode("utf-8", "replace")[:160])
                if len(hit.samples) < sample_limit:
                    example = found[0]
                    if isinstance(example, tuple):
                        example = example[0]
                    hit.samples.append(
                        (member.name, example.decode("utf-8", "replace")[:120])
                    )
            if max_members and members_scanned >= max_members:
                break
    return {
        "members_scanned": members_scanned,
        "bytes_scanned": bytes_scanned,
        "hits": hits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", default="/root/aep-raw-archive/aep-raw-evidence.tar")
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--max-members", type=int, default=None)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    tar_path = Path(arguments.archive)
    if not tar_path.is_file():
        print(f"no archive at {tar_path}", file=sys.stderr)
        return 2

    print(f"scanning {tar_path} ({tar_path.stat().st_size:,} bytes)")
    print(
        "categories are THIS SCRIPT'S OWN -- see the module docstring; the "
        "specification they were asked to match is not in the session."
    )
    print()
    result = scan(tar_path, arguments.samples, arguments.max_members)
    hits: dict[str, Hit] = result["hits"]
    print(
        f"scanned {result['members_scanned']:,} files, "
        f"{result['bytes_scanned']:,} bytes"
    )
    print()

    report: dict = {
        "archive": str(tar_path),
        "members_scanned": result["members_scanned"],
        "bytes_scanned": result["bytes_scanned"],
        "category_source": "defined in scripts/scan_archive_for_leakage.py",
        "categories": {},
    }

    blocking_found = False
    for category in CATEGORIES:
        hit = hits.get(category.key)
        files = len(hit.files) if hit else 0
        occurrences = hit.occurrences if hit else 0
        visible = len(hit.reviewer_visible_files) if hit else 0
        load_bearing = len(hit.load_bearing_files) if hit else 0
        if files and category.blocking:
            blocking_found = True
        report["categories"][category.key] = {
            "why": category.why,
            "blocking_if_present": category.blocking,
            "anonymity_only": category.anonymity_only,
            "files": files,
            "occurrences": occurrences,
            "reviewer_visible_files": visible,
            "load_bearing_for_docs28_files": load_bearing,
            "removal_breaks_manifest_and_tar_digest": bool(files),
            "samples": [list(s) for s in (hit.samples if hit else [])],
            "distinct_values": sorted(hit.values) if hit else [],
        }
        flag = "BLOCKING" if (files and category.blocking) else ""
        print(
            f"{category.key:22s} files={files:>6}  occurrences={occurrences:>8}  "
            f"reviewer-visible={visible:>5}  docs28-load-bearing={load_bearing:>3}  {flag}"
        )
        if hit:
            distinct = sorted(hit.values)
            print(
                f"    {len(distinct)}{'+' if len(distinct) >= 200 else ''} "
                f"distinct value(s); the shortest few:"
            )
            for value in sorted(distinct, key=len)[:6]:
                print(f"      {value[:100]}")
            for name, _ in hit.samples[:2]:
                print(f"    e.g. in {name[:88]}")
    print()
    print(
        "BLOCKING CATEGORY PRESENT -- do not publish"
        if blocking_found
        else "No blocking category present."
    )
    report["blocking_category_present"] = blocking_found

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
