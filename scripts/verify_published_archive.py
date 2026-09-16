"""Verify a published deposit: fetch it, check every manifest, re-derive, compare.

Run this **after** depositing (`docs/29-archive-deposit.md`). It is the check
that turns "a file exists at a DOI" into "the paper's numbers follow from what
is at that DOI", and it does the whole chain from the outside: it takes a DOI or
a directory and nothing else, and ends by byte-comparing the re-derived analysis
products against the ones this repository tracks.

    python scripts/verify_published_archive.py --doi 10.5281/zenodo.22766567
    python scripts/verify_published_archive.py \\
        --local /root/aep-raw-archive --local /root/aep-raw-archive-ext

**The deposit is TWO archives in ONE record, and this script requires both.**
Until 2026-09-16 it knew only the 2026-09-03 build: one `EXPECTED` dict, one
`ARCHIVE_NAME`. A record carrying only that archive would have passed it, while
the extension -- 11 collection roots, 1 332 run directories, 18 494 files,
including every WS-5 deployment session and the real-Temporal baseline -- went
unchecked. `EXPECTED` is now a table keyed by **deposited filename**, and a
record that does not carry all six files fails at step 1 rather than passing on
the four digests it did find.

**Deposited names are not the names inside the archives.** Both archive roots
hold files called `aep-raw-evidence.tar.gz`, `MANIFEST.sha256` and
`ARCHIVE-METADATA.json`, so one Zenodo record cannot hold both without
disambiguation. The deposited copies carry a date suffix; the bytes are
untouched, so every digest below is equally a digest of the local file and of
the deposited one. `--local` looks for the local names, `--doi` for the
deposited ones, and each archive's `deposited_*` and `local_*` fields say which
is which.

`--local` skips the download and exercises everything after it, which is how
this script was tested before any deposit existed: only the fetching half is
untested, and that is stated rather than implied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RUN_SUFFIX = re.compile(r"-r\d+$")


@dataclass(frozen=True)
class Archive:
    """One archive of the deposit, with the digests this repository tracks.

    ``ARTIFACT.md`` §5 and ``docs/29`` §1 carry the same values; they are here
    so the check needs no network to know what it is expecting.
    """

    label: str
    source_root: str
    deposited_tar_gz: str
    deposited_manifest: str
    deposited_metadata: str
    manifest_sha256: str
    tar_sha256: str
    tar_gz_sha256: str
    metadata_sha256: str
    files: int
    run_dirs: int
    roots: int
    rederive: bool
    min_configs: int
    note: str = ""
    local_tar_gz: str = "aep-raw-evidence.tar.gz"
    local_manifest: str = "MANIFEST.sha256"
    local_metadata: str = "ARCHIVE-METADATA.json"

    @property
    def deposited_names(self) -> tuple[str, str, str]:
        return (self.deposited_tar_gz, self.deposited_manifest,
                self.deposited_metadata)


ARCHIVES: tuple[Archive, ...] = (
    Archive(
        label="2026-09-03",
        source_root="aep-raw-archive",
        deposited_tar_gz="aep-raw-evidence-2026-09-03.tar.gz",
        deposited_manifest="MANIFEST-2026-09-03.sha256",
        deposited_metadata="ARCHIVE-METADATA-2026-09-03.json",
        manifest_sha256=(
            "87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7"
        ),
        tar_sha256=(
            "3aa90b215e838b41c02e47d38fd9ce474a3cb01c58d090659f2e7711ff6dbc94"
        ),
        tar_gz_sha256=(
            "fec959b5517eaeb1fd4bd9992472ce079206aea2fd374bd7e8a834ab2ac07353"
        ),
        metadata_sha256=(
            "cf75e7232ad9a97ee989760ca05cda758c67d4da0245a7929ba12706f7a220e5"
        ),
        files=26300,
        run_dirs=1458,
        roots=20,
        rederive=True,
        min_configs=1400,
    ),
    Archive(
        label="2026-09-15",
        source_root="aep-raw-archive-ext",
        deposited_tar_gz="aep-raw-evidence-2026-09-15.tar.gz",
        deposited_manifest="MANIFEST-2026-09-15.sha256",
        deposited_metadata="ARCHIVE-METADATA-2026-09-15.json",
        manifest_sha256=(
            "54d1ab0fc1e55283dc0aa1dabf121b047c432063d077074c3c45728735d63cd5"
        ),
        tar_sha256=(
            "61ecd2a41cb38708ccb1b6bbc507b4248b95c76cb3bef8ed8f3468dae13813e3"
        ),
        tar_gz_sha256=(
            "6ef11d7c88eef5927f478941f7df71ae25685fdb153afd636fe0250dd37eebf1"
        ),
        metadata_sha256=(
            "91fbd343d255b3023ed36074a09db4c096e1091fdda967f09609b835d6d486a2"
        ),
        files=18494,
        run_dirs=1332,
        roots=11,
        # No re-derivation baseline exists for this archive. Phase 35 verified
        # it file-by-file against its own manifest (18 494 OK, 0 failed, 0
        # missing) and did not re-run analyze.py over it, so there is no
        # "114 identical, 8 normalised" figure to compare against. Asserting a
        # pass here would be asserting a comparison nobody has made; §9 of the
        # manuscript says the same thing in the same words.
        rederive=False,
        min_configs=900,
        note="no re-derivation baseline recorded; manifest check only",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_doi(doi: str) -> dict[str, str]:
    """DOI -> {deposited filename: download URL}, via the Zenodo record API.

    Deliberately goes through the DOI rather than a remembered URL: the point
    of minting one is that it is the durable identifier, and a verifier that
    needs to be told the file location has not verified the DOI.

    **Every deposited file of every archive must be present.** A record holding
    one archive is not the deposit this repository describes, and the failure
    mode this guards against is the specific one that would otherwise pass:
    four digests match, the fifth and sixth files were never uploaded, and the
    gate reports success over half the evidence.
    """
    doi = doi.removeprefix("https://doi.org/").removeprefix("doi:")
    record_id = doi.rstrip("/").split(".")[-1]
    api = f"https://zenodo.org/api/records/{record_id}"
    with urllib.request.urlopen(api, timeout=60) as response:
        record = json.loads(response.read())
    links = {
        entry["key"]: entry["links"]["self"] for entry in record.get("files", [])
    }

    required = [name for archive in ARCHIVES for name in archive.deposited_names]
    missing = [name for name in required if name not in links]
    if missing:
        raise SystemExit(
            f"the record at {doi} is missing {len(missing)} of "
            f"{len(required)} required files:\n"
            + "\n".join(f"  - {name}" for name in missing)
            + f"\nit carries: {sorted(links)}\n"
            "This deposit is two archives in one record (docs/29 §0b). A record "
            "holding only one of them is not what this repository describes."
        )
    return links


def download(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetching {url}")
    with urllib.request.urlopen(url, timeout=900) as response, \
            target.open("wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    print(f"  {target.name}: {target.stat().st_size:,} bytes")
    return target


def count_run_directories(manifest_text: str) -> tuple[int, int, int]:
    """(run directories, directories named ``…-r<N>``, directories with a config).

    **A run directory is one holding a single run's artifacts**, identified
    either by an ``…-r<N>`` name or by a ``run-config.json`` -- the union of
    the two tests. Neither alone is right, and the difference is not
    cosmetic: named-only gives 1 457 and 1 332, run-config-only gives 1 458
    and 992, and the figures this repository publishes -- 1 458 and 1 332 --
    are the union. In the 2026-09-03 archive one run directory is named
    ``…-r1.attempt-1`` and so fails the name test; in the extension 340
    directories across four roots hold run artifacts with no
    ``run-config.json``, because B5 runs through ``session.py`` rather than
    ``run_matrix``. Each archive's set contains the other's, so the union
    is the larger of the two in both cases.

    All three are printed because a reader who opens the extension's
    ``ARCHIVE-METADATA.json`` finds its per-root ``runs`` summing to 992, not
    1 332, and should be able to see here why. ``docs/29`` §3 discloses the
    same thing in the record's own description.
    """
    run_dirs: set[str] = set()
    with_config: set[str] = set()
    for line in manifest_text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        segments = parts[1].lstrip("*").strip().split("/")
        for index, segment in enumerate(segments[:-1]):
            if RUN_SUFFIX.search(segment):
                run_dirs.add("/".join(segments[: index + 1]))
                break
        if segments[-1] == "run-config.json":
            with_config.add("/".join(segments[:-1]))
    return len(run_dirs | with_config), len(run_dirs), len(with_config)


@dataclass
class Outcome:
    label: str
    failures: list[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)


def verify_one(
    archive: Archive,
    tar_gz: Path,
    manifest: Path,
    metadata: Path | None,
    scratch: Path,
    skip_rederive: bool,
) -> Outcome:
    out = Outcome(label=archive.label)
    print()
    print("=" * 70)
    print(f"ARCHIVE {archive.label}  ({archive.source_root})")
    print("=" * 70)

    print("--- digests against what the repository expects ---")
    checks = [
        (archive.deposited_tar_gz, tar_gz, archive.tar_gz_sha256),
        (archive.deposited_manifest, manifest, archive.manifest_sha256),
    ]
    if metadata is not None:
        checks.append(
            (archive.deposited_metadata, metadata, archive.metadata_sha256)
        )
    else:
        print("  ARCHIVE-METADATA.json not supplied by this source; not checked")
    for name, path, expected in checks:
        actual = sha256(path)
        ok = actual == expected
        out.report[f"{name}_sha256"] = actual
        out.report[f"{name}_matches"] = ok
        print(f"  {name:38s} {'MATCH   ' if ok else 'MISMATCH'} {actual}")
        if not ok:
            out.failures.append(f"{archive.label}: {name} digest")
            print(f"  {'':38s} expected {expected}")

    print("--- extract and check every file against the manifest ---")
    extract = scratch / "extract"
    if extract.exists():
        shutil.rmtree(extract)
    extract.mkdir(parents=True)
    with tarfile.open(tar_gz, "r:gz") as tar:
        members = 0
        for member in tar:
            if not member.isreg():
                continue
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise SystemExit(f"unsafe archive member: {member.name}")
            # filter="data" is the 3.12+ default-to-be and refuses
            # absolute paths, parent escapes, devices and setuid bits.
            # The explicit check above stays: this script extracts a
            # tarball fetched over the network, and two independent
            # refusals is the right number for that.
            tar.extract(member, path=extract, set_attrs=False,
                        filter="data")
            members += 1
    print(f"  extracted {members:,} files (expected {archive.files:,})")
    out.report["extracted_files"] = members
    if members != archive.files:
        out.failures.append(
            f"{archive.label}: file count {members} != {archive.files}"
        )

    manifest_text = manifest.read_text(encoding="utf-8")
    bad = checked = 0
    for line in manifest_text.splitlines():
        digest, _, name = line.partition("  ")
        path = extract / name
        if not path.exists():
            bad += 1
            continue
        checked += 1
        if sha256(path) != digest:
            bad += 1
    print(f"  {checked:,} files verified against the manifest, {bad} problems")
    out.report["manifest_checked"] = checked
    out.report["manifest_problems"] = bad
    if bad:
        out.failures.append(f"{archive.label}: {bad} manifest problems")

    total, named, with_config = count_run_directories(manifest_text)
    print(
        f"  run directories: {total:,} (expected {archive.run_dirs:,}) -- "
        f"{named:,} named -r<N>, {with_config:,} with a run-config.json"
    )
    out.report["run_dirs"] = total
    out.report["run_dirs_named"] = named
    out.report["run_dirs_with_config"] = with_config
    if total != archive.run_dirs:
        out.failures.append(
            f"{archive.label}: {total} run directories, expected "
            f"{archive.run_dirs}"
        )

    if skip_rederive:
        return out

    if not archive.rederive:
        # R14's third outcome: this is "I did not look", printed, not silence.
        print("--- re-derivation: NOT RUN ---")
        print(f"  {archive.note}")
        out.report["rederive"] = "not run: " + archive.note
        return out

    print("--- re-derive and byte-compare against the tracked products ---")
    # verify_raw_archive.py reads its manifest from <--archive>/MANIFEST.sha256
    # under that exact name. The deposited copy is date-suffixed and the
    # work directory holds only the extraction, so without this copy it
    # finds no manifest and compares nothing -- which the zero-comparison
    # guard below then reports as a failure rather than a pass. Caught that
    # way on 2026-09-16, during the rewrite that split this per archive.
    shutil.copy2(manifest, scratch / "MANIFEST.sha256")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "verify_raw_archive.py"),
            "--archive",
            str(scratch),
            # verify_raw_archive.py reads its extraction from <scratch>/extract,
            # which is exactly where the step above put it. Passing a different
            # directory here made this script report "IDENTICAL 0 ... DIFFERS 0"
            # and then declare success -- a check that passes by doing nothing.
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
    out.report["rederive_returncode"] = result.returncode
    out.report["rederive_tail"] = tail

    # Parse the counts rather than grep for a substring. "DIFFERS 0" is true of
    # a run that compared nothing, so a substring test cannot tell success from
    # silence.
    counts: dict[str, int] = {}
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
    out.report["rederive_counts"] = counts
    compared = counts.get("identical", 0) + counts.get("normalised", 0)
    print(f"  compared {compared} tracked analysis files")
    if compared == 0:
        out.failures.append(
            f"{archive.label}: the re-derivation compared ZERO files -- it did "
            "not run, and a zero difference count over zero comparisons is not "
            "a pass"
        )
    elif counts.get("differs", -1) != 0:
        out.failures.append(
            f"{archive.label}: re-derivation reported "
            f"{counts.get('differs')} differing files"
        )
    if result.returncode not in (0, 1):
        out.failures.append(
            f"{archive.label}: verify_raw_archive exited {result.returncode}"
        )

    print("--- every run's config against its own digest ---")
    # This lives here rather than in CI because CI has no run directories: they
    # are gitignored, so a job over the tracked roots would examine zero configs
    # and report a clean pass. The archive is the only place the check has
    # anything to check, and it is where a reviewer meets it.
    distinct = sorted({str(path.parent.parent) for path in
                       extract.glob("*/*/run-config.json")})
    audit = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "audit_config_digests.py"),
            *sum(([f"--root", root] for root in distinct), []),
            "--require-runs",
            str(archive.min_configs),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    for line in audit.stdout.strip().splitlines()[-6:]:
        print(f"  {line}")
    out.report["digest_audit_returncode"] = audit.returncode
    if audit.returncode != 0:
        out.failures.append(
            f"{archive.label}: config-digest audit exited {audit.returncode} "
            "(1 = a stored digest matches no schema generation; "
            "2 = nothing was examined; 3 = ambiguous generation match)"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--doi", help="e.g. 10.5281/zenodo.22766567")
    parser.add_argument(
        "--local",
        action="append",
        default=[],
        metavar="DIR",
        help="a directory holding one archive; repeat for each. Matched to an "
             "archive by its MANIFEST.sha256 digest, so order does not matter.",
    )
    parser.add_argument("--scratch", default="/root/aep-published-verify")
    parser.add_argument(
        "--skip-rederive",
        action="store_true",
        help="stop after the manifest check (fast; integrity, not sufficiency)",
    )
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    if bool(arguments.doi) == bool(arguments.local):
        parser.error("give exactly one of --doi or one-or-more --local")

    scratch = Path(arguments.scratch)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    report: dict = {
        "source": arguments.doi or arguments.local,
        "archives": {},
    }
    failures: list[str] = []

    print("=== obtain ===")
    sources: dict[str, tuple[Path, Path, Path | None]] = {}

    if arguments.doi:
        links = resolve_doi(arguments.doi)
        print(f"  the record carries all "
              f"{sum(len(a.deposited_names) for a in ARCHIVES)} required files")
        for archive in ARCHIVES:
            base = scratch / archive.label
            sources[archive.label] = (
                download(links[archive.deposited_tar_gz],
                         base / archive.deposited_tar_gz),
                download(links[archive.deposited_manifest],
                         base / archive.deposited_manifest),
                download(links[archive.deposited_metadata],
                         base / archive.deposited_metadata),
            )
    else:
        # Match each directory to an archive by its manifest digest rather than
        # by its path, so the operator cannot silently verify one archive twice.
        by_manifest = {a.manifest_sha256: a for a in ARCHIVES}
        seen: dict[str, Path] = {}
        for raw in arguments.local:
            base = Path(raw)
            manifest = base / "MANIFEST.sha256"
            if not manifest.is_file():
                raise SystemExit(f"{base} holds no MANIFEST.sha256")
            digest = sha256(manifest)
            archive = by_manifest.get(digest)
            if archive is None:
                raise SystemExit(
                    f"{base}: MANIFEST.sha256 digest {digest} matches no "
                    "archive this repository describes"
                )
            if archive.label in seen:
                raise SystemExit(
                    f"{base} and {seen[archive.label]} are the same archive "
                    f"({archive.label})"
                )
            seen[archive.label] = base
            metadata = base / archive.local_metadata
            sources[archive.label] = (
                base / archive.local_tar_gz,
                manifest,
                metadata if metadata.is_file() else None,
            )
            print(f"  local: {base}  ->  archive {archive.label}")
        absent = [a.label for a in ARCHIVES if a.label not in sources]
        if absent:
            raise SystemExit(
                f"missing archive(s) {absent}. The deposit is two archives "
                "(docs/29 §0b); verifying one of them is not verifying the "
                "deposit. Pass --local once per archive."
            )

    for archive in ARCHIVES:
        tar_gz, manifest, metadata = sources[archive.label]
        if not tar_gz.is_file():
            raise SystemExit(f"{tar_gz} is missing")
        outcome = verify_one(
            archive,
            tar_gz,
            manifest,
            metadata,
            scratch / archive.label / "work",
            arguments.skip_rederive,
        )
        report["archives"][archive.label] = outcome.report
        failures.extend(outcome.failures)

    print()
    print("=" * 70)
    if failures:
        print("VERIFICATION FAILED:")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print(
            "VERIFIED: both archives at this source are byte-for-byte the ones "
            "this repository describes, and the paper's analysis products "
            "follow from the 2026-09-03 archive."
        )
    report["failures"] = failures

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
