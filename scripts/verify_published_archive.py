"""Verify a published archive: fetch it, check the manifest, re-derive, compare.

Run this **after** depositing (`docs/29-archive-deposit.md`). It is the check
that turns "a file exists at a DOI" into "the paper's numbers follow from what
is at that DOI", and it does the whole chain from the outside: it takes a DOI or
a URL and nothing else, and ends by byte-comparing the re-derived analysis
products against the ones this repository tracks.

    python scripts/verify_published_archive.py --doi 10.5281/zenodo.XXXXXXX
    python scripts/verify_published_archive.py --url https://.../aep-raw-evidence.tar.gz
    python scripts/verify_published_archive.py --local /root/aep-raw-archive

`--local` skips the download and exercises everything after it, which is how the
script was tested before any deposit existed: only the fetching half is
untested, and that is stated rather than implied.

Expected result, from `reports/phase-report-11-rescue-2026-09-03.md`:
**114 identical, 8 identical after normalisation, 0 differing.** Anything else
is a finding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The digests Phase 11 recorded, tracked here so the check needs no network
#: to know what it is expecting. `ARTIFACT.md` §5 carries the same values.
EXPECTED = {
    "manifest_sha256": (
        "87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7"
    ),
    "tar_sha256": (
        "3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94"
    ),
    "tar_gz_sha256": (
        "fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353"
    ),
    "files": 26300,
}

ARCHIVE_NAME = "aep-raw-evidence.tar.gz"
MANIFEST_NAME = "MANIFEST.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_doi(doi: str) -> tuple[str, str]:
    """DOI -> (archive URL, manifest URL), via the Zenodo record API.

    Deliberately goes through the DOI rather than a remembered URL: the point of
    minting one is that it is the durable identifier, and a verifier that needs
    to be told the file location has not verified the DOI.
    """
    doi = doi.removeprefix("https://doi.org/").removeprefix("doi:")
    record_id = doi.rstrip("/").split(".")[-1]
    api = f"https://zenodo.org/api/records/{record_id}"
    with urllib.request.urlopen(api, timeout=60) as response:
        record = json.loads(response.read())
    links = {entry["key"]: entry["links"]["self"] for entry in record.get("files", [])}
    missing = [n for n in (ARCHIVE_NAME, MANIFEST_NAME) if n not in links]
    if missing:
        raise SystemExit(
            f"the record at {doi} does not carry {missing}; it has {sorted(links)}"
        )
    return links[ARCHIVE_NAME], links[MANIFEST_NAME]


def download(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetching {url}")
    with urllib.request.urlopen(url, timeout=600) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    print(f"  {target.name}: {target.stat().st_size:,} bytes")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--doi", help="e.g. 10.5281/zenodo.XXXXXXX")
    source.add_argument("--url", help="direct URL to aep-raw-evidence.tar.gz")
    source.add_argument(
        "--local", help="a directory already holding the archive and manifest"
    )
    parser.add_argument("--scratch", default="/root/aep-published-verify")
    parser.add_argument(
        "--skip-rederive",
        action="store_true",
        help="stop after the manifest check (fast; proves integrity, not sufficiency)",
    )
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    scratch = Path(arguments.scratch)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    report: dict = {"source": arguments.doi or arguments.url or arguments.local}
    failures: list[str] = []

    print("=== 1. obtain ===")
    if arguments.local:
        base = Path(arguments.local)
        archive = base / ARCHIVE_NAME
        manifest = base / MANIFEST_NAME
        if not archive.is_file() or not manifest.is_file():
            raise SystemExit(f"{base} does not hold {ARCHIVE_NAME} and {MANIFEST_NAME}")
        print(f"  local: {base}")
        # Step 4 hands `scratch` to verify_raw_archive.py, which reads the
        # manifest from there. Copy rather than special-case, so the local and
        # fetched paths run identical code from here on.
        shutil.copy2(manifest, scratch / MANIFEST_NAME)
        manifest = scratch / MANIFEST_NAME
    else:
        if arguments.doi:
            archive_url, manifest_url = resolve_doi(arguments.doi)
        else:
            archive_url = arguments.url
            manifest_url = arguments.url.rsplit("/", 1)[0] + "/" + MANIFEST_NAME
        archive = download(archive_url, scratch / ARCHIVE_NAME)
        manifest = download(manifest_url, scratch / MANIFEST_NAME)

    print()
    print("=== 2. digests against what the repository expects ===")
    for name, path, expected in (
        (ARCHIVE_NAME, archive, EXPECTED["tar_gz_sha256"]),
        (MANIFEST_NAME, manifest, EXPECTED["manifest_sha256"]),
    ):
        actual = sha256(path)
        ok = actual == expected
        report[f"{name}_sha256"] = actual
        report[f"{name}_matches"] = ok
        print(f"  {name:26s} {'MATCH   ' if ok else 'MISMATCH'} {actual}")
        if not ok:
            failures.append(f"{name} digest")
            print(f"  {'':26s} expected {expected}")

    print()
    print("=== 3. extract and check every file against the manifest ===")
    extract = scratch / "extract"
    extract.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = 0
        for member in tar:
            if not member.isreg():
                continue
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise SystemExit(f"unsafe archive member: {member.name}")
            tar.extract(member, path=extract, set_attrs=False)
            members += 1
    print(f"  extracted {members:,} files")
    report["extracted_files"] = members
    if members != EXPECTED["files"]:
        failures.append(f"file count {members} != {EXPECTED['files']}")

    bad = 0
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        path = extract / name
        if not path.exists():
            bad += 1
            continue
        checked += 1
        if sha256(path) != digest:
            bad += 1
    print(f"  {checked:,} files verified against the manifest, {bad} problems")
    report["manifest_checked"] = checked
    report["manifest_problems"] = bad
    if bad:
        failures.append(f"{bad} manifest problems")

    if not arguments.skip_rederive:
        print()
        print("=== 4. re-derive and byte-compare against the tracked products ===")
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "verify_raw_archive.py"),
                "--archive",
                str(scratch),
                # verify_raw_archive.py reads its extraction from
                # <scratch>/extract, which is exactly where step 3 put it.
                # Passing a different directory here made this script report
                # "IDENTICAL 0 ... DIFFERS 0" and then declare success, which is
                # a check that passes by doing nothing.
                "--scratch",
                str(scratch),
                "--skip-extract",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        tail = result.stdout.strip().splitlines()[-4:]
        for line in tail:
            print(f"  {line}")
        report["rederive_returncode"] = result.returncode
        report["rederive_tail"] = tail

        # Parse the counts rather than grep for a substring. "DIFFERS 0" is
        # true of a run that compared nothing, so a substring test cannot tell
        # success from silence.
        counts = {}
        for token, key in (
            ("IDENTICAL ", "identical"),
            ("IDENTICAL-after-normalisation ", "normalised"),
            ("DIFFERS ", "differs"),
        ):
            for line in tail:
                if token in line:
                    fragment = line.split(token, 1)[1].split()[0]
                    if fragment.isdigit():
                        counts.setdefault(key, int(fragment))
        report["rederive_counts"] = counts
        compared = counts.get("identical", 0) + counts.get("normalised", 0)
        print(f"  compared {compared} tracked analysis files")
        if compared == 0:
            failures.append(
                "the re-derivation compared ZERO files -- it did not run, and "
                "a zero difference count over zero comparisons is not a pass"
            )
        elif counts.get("differs", -1) != 0:
            failures.append(
                f"re-derivation reported {counts.get('differs')} differing files"
            )
        if result.returncode not in (0, 1):
            failures.append(f"verify_raw_archive exited {result.returncode}")

        print()
        print("=== 5. every run's config against its own digest ===")
        # This lives here rather than in CI because CI has no run directories:
        # they are gitignored, so a job over the tracked roots would examine
        # zero configs and report a clean pass. The archive is the only place
        # the check has anything to check, and it is where a reviewer meets it.
        roots = sorted(
            path.parent
            for path in (extract).glob("*/*/run-config.json")
        )
        distinct = sorted({str(path.parent) for path in roots})
        audit = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "audit_config_digests.py"),
                *sum(([f"--root", root] for root in distinct), []),
                "--require-runs",
                "1000",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        for line in audit.stdout.strip().splitlines()[-6:]:
            print(f"  {line}")
        report["digest_audit_returncode"] = audit.returncode
        if audit.returncode != 0:
            failures.append(
                f"config-digest audit exited {audit.returncode} "
                "(1 = a stored digest matches no schema generation; "
                "2 = nothing was examined; 3 = ambiguous generation match)"
            )

    print()
    if failures:
        print("VERIFICATION FAILED:")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print(
            "VERIFIED: the archive at this source is byte-for-byte the one this "
            "repository describes, and the paper's analysis products follow "
            "from it."
        )
    report["failures"] = failures

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
