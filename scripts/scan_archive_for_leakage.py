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
import os
import re
import sys
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


#: The author's own identifiers. Present on purpose -- the paper names him on
#: page 1 -- so a match on one of these is an ANONYMITY question (B) and never
#: a disclosure one (A).
#:
#: This list is what makes the third-party categories readable. Without it a
#: reader triaging "5 e-mail addresses" sees five equal rows, four of which are
#: the author's own and the trailer's, and reasonably shrugs. With it, a
#: third-party address is the only thing in its category.
AUTHOR_IDENTIFIERS: tuple[bytes, ...] = (
    b"hafizmirhamza276",
    b"0009-0005-9380-2188",
    b"hamzakhan",
    b"hamza khan",
    b"h. khan",
    b"khan, hamza",
    # The author's GitHub no-reply, which is what `git log` records as
    # the committer. Not in the list until 2026-09-24, when it showed up
    # as the only "third-party" address in the repository and was not one.
    b"hamza276@users.noreply.github.com",
    # The Co-Authored-By trailer. A vendor no-reply is not a person.
    b"noreply@anthropic.com",
    # RFC 2606 reserves .invalid; the test fixtures use it precisely so that a
    # scan can tell a synthetic address from a real one.
    b"@example.invalid",
    b"@example.com",
)


def _is_author(value: bytes) -> bool:
    low = value.lower()
    return any(token in low for token in AUTHOR_IDENTIFIERS)


@dataclass(frozen=True)
class Category:
    key: str
    why: str
    pattern: re.Pattern[bytes]
    #: True when finding this would stop a publication outright.
    blocking: bool
    #: Whether it bears on anonymity (B) rather than on disclosure (A).
    anonymity_only: bool
    #: Drop matches belonging to the author. Set on the categories where a
    #: THIRD PARTY's value is the finding and the author's own is not.
    exclude_author: bool = False


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
    # --------------------------------------------------------------------
    # Third-party personal data. Added 2026-09-24, after a colleague's work
    # e-mail address was found in the `createdBy`/`lastModifiedBy` fields of
    # reports/raw/phase40-deployment-2026-09-18/deployment-show.json -- Azure
    # records who created a deployment, and `az ... deployment show` prints
    # it. It had been committed and public for six days.
    #
    # An `email_address` category already existed and would have matched it.
    # It did not stop anything, for three reasons, all fixed here:
    #
    #   1. it was blocking=False, anonymity_only=True -- so a third party's
    #      address was filed as an ANONYMITY concern, which is exactly the
    #      class a reader dismisses once the venue turns out to be
    #      single-anonymous. Someone else's personal data is a DISCLOSURE
    #      concern and it blocks;
    #   2. there was no author allow-list, so the finding would have sat in a
    #      row beside the author's own deliberate addresses;
    #   3. the scanner read one .tar and nothing else, so neither the
    #      repository working tree nor a .tar.gz was ever in scope -- and the
    #      first draft of the report ABOUT the leak, which quoted the address
    #      verbatim in a markdown file, was unreachable by it.
    # --------------------------------------------------------------------
    Category(
        "third_party_email",
        "an e-mail address that is not the author's -- someone else's "
        "personal data, which blocks a deposit until it is redacted or the "
        "file is withheld",
        re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        blocking=True,
        anonymity_only=False,
        exclude_author=True,
    ),
    Category(
        "azure_principal",
        "Azure/ARM audit fields naming the account that created or last "
        "modified a resource -- createdBy, lastModifiedBy, userPrincipalName",
        re.compile(
            rb'(?i)"(?:created_?by|last_?modified_?by|modified_?by|owner|upn|'
            rb'user_?principal_?name)"\s*:\s*"(?!<)[^"]{3,}"'
        ),
        blocking=True,
        anonymity_only=False,
        exclude_author=True,
    ),
    Category(
        "corporate_domain",
        "a third party's organisation, by domain -- names an employer or "
        "tenant the repository otherwise says nothing about",
        re.compile(
            rb"(?i)\b[\w-]+\.(?:komatsu|onmicrosoft\.com)\b"
        ),
        blocking=True,
        anonymity_only=False,
        exclude_author=True,
    ),
    Category(
        "azure_resource_path",
        "an ARM resource path carrying a real subscription or tenant GUID. "
        "Bare UUIDs are NOT matched: execution_id and intent_id are UUIDs and "
        "there are hundreds of thousands of them",
        re.compile(
            rb"(?i)/subscriptions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            rb"[0-9a-f]{4}-[0-9a-f]{12}"
        ),
        blocking=True,
        anonymity_only=False,
    ),
    Category(
        "phone_number",
        "a telephone number, which identifies a person directly",
        re.compile(
            rb"(?:\+\d{1,3}[ -]?)?\(?\d{3}\)?[ -]\d{3}[ -]\d{4}\b"
        ),
        blocking=True,
        anonymity_only=False,
    ),
    Category(
        "email_address",
        "any e-mail address, including the author's own. Kept beside "
        "third_party_email so the author's deliberate addresses are still "
        "counted rather than silently dropped",
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


def _matches(category: Category, data: bytes) -> list[bytes]:
    """Every match for `category` in `data`, minus the author's own values.

    ``exclude_author`` is applied per MATCH, not per file: a file may carry
    the author's address and a third party's, and dropping the file because
    one of them is expected is how the second one survives.
    """
    found = [
        raw[0] if isinstance(raw, tuple) else raw
        for raw in category.pattern.findall(data)
    ]
    if category.exclude_author:
        found = [value for value in found if not _is_author(value)]
    return found


def scan_bytes(name: str, data: bytes, hits: dict, sample_limit: int) -> None:
    """Accumulate every category's matches for one named blob."""
    for category in CATEGORIES:
        found = _matches(category, data)
        if not found:
            continue
        hit = hits[category.key]
        hit.files.add(name)
        hit.occurrences += len(found)
        if is_reviewer_visible(name):
            hit.reviewer_visible_files.add(name)
        if is_load_bearing(name):
            hit.load_bearing_files.add(name)
        for raw in found:
            if len(hit.values) < 200:
                hit.values.add(raw.decode("utf-8", "replace")[:160])
        if len(hit.samples) < sample_limit:
            hit.samples.append(
                (name, found[0].decode("utf-8", "replace")[:120])
            )


def scan_tree(root: Path, sample_limit: int) -> dict:
    """Scan a directory tree -- the repository, or an unpacked archive.

    The repository has to be scannable. The first draft of the report about
    the 2026-09-24 leak quoted the leaked address verbatim in a markdown file
    under ``reports/``; a scanner that reads only a tar could not have seen it.
    """
    hits: dict[str, Hit] = defaultdict(Hit)
    files_scanned = 0
    bytes_scanned = 0
    skip_suffix = {".png", ".jpg", ".jpeg", ".pdf", ".gz", ".zip", ".tar",
                   ".sqlite3", ".sqlite3-wal", ".pyc", ".whl"}
    # Pruned rather than filtered: `.venv/lib64` is a POSIX symlink the
    # Windows scandir cannot traverse at all, so the walk has to not enter it.
    skip_dirs = {".git", "__pycache__", ".venv", ".mypy_cache",
                 ".pytest_cache", ".ruff_cache", "node_modules", ".scratch"}
    # This file carries the known-positive fixtures -- a synthetic address, a
    # synthetic ARM path -- by design. A detector that reports its own test
    # data is a detector nobody reads twice. It is skipped by NAME and only
    # here, so a real leak in any other script is still a finding.
    self_name = Path(__file__).name
    for parent, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in sorted(filenames):
            path = Path(parent) / filename
            if path.suffix.lower() in skip_suffix or filename == self_name:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            files_scanned += 1
            bytes_scanned += len(data)
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = str(path)
            scan_bytes(rel, data, hits, sample_limit)
    return {
        "members_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "hits": hits,
    }


def scan(tar_path: Path, sample_limit: int, max_members: int | None) -> dict:
    hits: dict[str, Hit] = defaultdict(Hit)
    members_scanned = 0
    bytes_scanned = 0
    mode = "r|gz" if tar_path.name.endswith((".gz", ".tgz")) else "r|"
    with tarfile.open(tar_path, mode) as tar:
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
                found = _matches(category, data)
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


#: The known-positive fixtures. **These are the two shapes the 2026-09-24 leak
#: actually took**, reproduced with a synthetic address, not invented shapes
#: that happen to match.
#:
#: The second one matters as much as the first. A scanner that catches leaks in
#: JSON but not in the incident report written about them is a scanner that
#: lets the second copy through, which is exactly what nearly happened.
SELFTEST_FIXTURES: tuple[tuple[str, str, bytes, tuple[str, ...]], ...] = (
    (
        "the original file",
        "deployment-show.json",
        b'{\n  "systemData": {\n'
        b'    "createdAt": "2026-08-17T13:15:02.747066+00:00",\n'
        b'    "createdBy": "a_colleague@global.komatsu",\n'
        b'    "createdByType": "User",\n'
        b'    "lastModifiedBy": "a_colleague@global.komatsu"\n  }\n}\n',
        ("third_party_email", "azure_principal", "corporate_domain"),
    ),
    (
        "the report that quoted it -- fenced code block",
        "disclosure-report.md",
        b"```json\n"
        b'    "createdBy": "a_colleague@global.komatsu",\n'
        b"```\n",
        ("third_party_email", "azure_principal", "corporate_domain"),
    ),
    (
        "the report that quoted it -- diff line",
        "disclosure-report.md",
        b"```diff\n"
        b'-    "lastModifiedBy": "a_colleague@global.komatsu",\n'
        b'+    "lastModifiedBy": "<azure-account-redacted>",\n'
        b"```\n",
        ("third_party_email", "corporate_domain"),
    ),
    (
        "an ARM path with a real subscription GUID",
        "deployment-show.json",
        b'{"id": "/subscriptions/3f2a1b4c-5d6e-7f80-9a1b-2c3d4e5f6071/rg/x"}',
        ("azure_resource_path",),
    ),
)

#: Must NOT fire. The author's own identifiers are deliberate, the redaction
#: marker is the fix, and execution_id is a UUID of which there are ~10 000.
SELFTEST_NEGATIVES: tuple[tuple[str, bytes], ...] = (
    ("the author's own address", b'"contact": "hafizmirhamza276@gmail.com"'),
    ("the Co-Authored-By trailer", b"Co-Authored-By: X <noreply@anthropic.com>"),
    ("a synthetic test fixture", b'"to": "tester@example.invalid"'),
    ("the redaction marker itself", b'"createdBy": "<azure-account-redacted>"'),
    ("a bare execution UUID",
     b'{"execution_id": "3f2a1b4c-5d6e-7f80-9a1b-2c3d4e5f6071"}'),
)


def selftest() -> int:
    """Prove the third-party categories fire on the leak's real shapes."""
    failures = 0
    print("POSITIVES -- each must be caught, and must BLOCK")
    for label, name, data, expected in SELFTEST_FIXTURES:
        hits: dict[str, Hit] = defaultdict(Hit)
        scan_bytes(name, data, hits, 2)
        blocking = {
            c.key for c in CATEGORIES if c.blocking and hits.get(c.key)
        }
        missing = [key for key in expected if key not in hits]
        status = "PASS" if not missing and blocking else "FAIL"
        failures += status == "FAIL"
        print(f"  {status}  {label}")
        print(f"        fired: {', '.join(sorted(hits)) or 'NOTHING'}")
        if missing:
            print(f"        MISSING: {', '.join(missing)}")
        if not blocking:
            print("        NOT BLOCKING -- would not stop a deposit")

    print()
    print("NEGATIVES -- each must NOT fire a third-party category")
    third_party = {
        c.key for c in CATEGORIES if c.blocking and c.exclude_author
    } | {"azure_resource_path"}
    for label, data in SELFTEST_NEGATIVES:
        hits = defaultdict(Hit)
        scan_bytes("x.json", data, hits, 2)
        fired = sorted(set(hits) & third_party)
        status = "PASS" if not fired else "FAIL"
        failures += status == "FAIL"
        print(f"  {status}  {label}"
              + (f"  -- fired {', '.join(fired)}" if fired else ""))

    total = len(SELFTEST_FIXTURES) + len(SELFTEST_NEGATIVES)
    print()
    print(f"selftest: {total - failures} of {total}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", default="/root/aep-raw-archive/aep-raw-evidence.tar")
    parser.add_argument(
        "--root",
        default=None,
        help="scan a DIRECTORY TREE instead of an archive -- the repository "
             "working tree, or an unpacked part. The repository has to be "
             "scannable: the first draft of the report about the 2026-09-24 "
             "leak quoted the leaked address in a markdown file, which no "
             "archive scan could reach.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="prove the third-party categories fire on the two shapes the "
             "2026-09-24 leak actually took",
    )
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--max-members", type=int, default=None)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    if arguments.selftest:
        return selftest()

    if arguments.root:
        tar_path = Path(arguments.root)
        if not tar_path.is_dir():
            print(f"no directory at {tar_path}", file=sys.stderr)
            return 2
        print(f"scanning tree {tar_path}")
        print()
        result = scan_tree(tar_path, arguments.samples)
    else:
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
