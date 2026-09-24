"""Exercise ``scripts/verify_published_archive.py`` on the branches where it fails.

``docs/26`` §3 rule 13, and rule 14: this is the gate that stands between a
reviewer and the evidence the paper's numbers come from, so **a false
``VERIFIED`` is worse than no verifier at all.** It was rewritten on 2026-09-16
from one archive to two, and it went into that rewrite with no test. Every way
it can report success over something it did not check is exercised here.

**Everything runs against synthetic archives built in ``tmp_path``.** The real
deposit is 848 MB across two trees that exist only on the collection host, and a
test that needs ``/root`` or ``D:`` is a test that does not run in CI or in the
clean clone an evaluator uses. The fixtures below are three-file tarballs with
their own manifests and their own digests, and ``ARCHIVES`` is monkeypatched to
describe them — so the *logic* is under test at full fidelity while the data is
small.

**What is not tested here, named rather than implied.** These 37 tests cover
95% of the script. The 13 statements they do not reach are exactly two
things, both of which need a published record:

* ``download()`` — the HTTP fetch itself;
* the ``--doi`` branch of ``main()``, which is six calls to it.

``resolve_doi()`` *is* tested, through a stubbed ``urlopen``: what it does
with a record's file list is logic, and only the socket is absent. But no
test here fetches from Zenodo, because there is nothing published to fetch.
``docs/29`` §2 puts that on the operator's sandbox rehearsal and §6 states it
as the untested half; **it is untested, not assumed to work.**

The re-derivation subprocess is driven through a stub: ``verify_raw_archive.py``
over a real 26 300-file extraction is a ten-minute operation and belongs to
``docs/29`` §6, not to a unit suite. What *is* pinned here is the part that
failed during the rewrite — that the manifest reaches that subprocess at all.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_published_archive.py"


def load():
    spec = importlib.util.spec_from_file_location("verify_published_archive", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_published_archive"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def vpa():
    return load()


# --------------------------------------------------------------------------
# Fixtures: two synthetic archives shaped like the real deposit.
# --------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def build_archive(
    base: Path,
    label: str,
    root_name: str,
    *,
    runs: int = 2,
    with_config: bool = True,
    extra_in_tar: dict[str, bytes] | None = None,
    omit_from_manifest: tuple[str, ...] = (),
    corrupt_manifest_digest_for: str | None = None,
) -> dict:
    """One archive directory: a tarball, a manifest over it, and metadata.

    The knobs are the failure modes. ``extra_in_tar`` adds a file the manifest
    will not know about; ``omit_from_manifest`` drops a manifest line for a file
    that is in the tar; ``corrupt_manifest_digest_for`` records the wrong digest
    for a file that is present and correct.
    """
    directory = base / f"archive-{label}"
    directory.mkdir(parents=True)

    payload: dict[str, bytes] = {}
    for index in range(runs):
        run = f"{root_name}/cell-{index:04x}-r{index}"
        payload[f"{run}/events.jsonl"] = f'{{"run":{index}}}\n'.encode()
        if with_config:
            payload[f"{run}/run-config.json"] = (
                json.dumps({"run": index}).encode() + b"\n"
            )
    payload.update(extra_in_tar or {})

    tar_path = directory / "aep-raw-evidence.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name, data in sorted(payload.items()):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))

    lines = []
    for name, data in sorted(payload.items()):
        if name in omit_from_manifest:
            continue
        digest = sha256_bytes(data)
        if name == corrupt_manifest_digest_for:
            digest = "0" * 64
        lines.append(f"{digest}  {name}")
    manifest_path = directory / "MANIFEST.sha256"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    metadata_path = directory / "ARCHIVE-METADATA.json"
    metadata_path.write_text(
        json.dumps({"archive": label, "roots": [{"label": root_name}]}) + "\n",
        encoding="utf-8",
    )

    named = {n.rsplit("/", 1)[0] for n in payload if "-r" in n.split("/")[1]}
    configs = {
        n.rsplit("/", 1)[0] for n in payload if n.endswith("/run-config.json")
    }
    return {
        "dir": directory,
        "files": len(payload),
        "run_dirs": len(named | configs),
        "tar_gz_sha256": sha256_file(tar_path),
        "manifest_sha256": sha256_file(manifest_path),
        "metadata_sha256": sha256_file(metadata_path),
    }


def make_record(vpa, label: str, built: dict, *, rederive: bool = False, **over):
    fields = dict(
        label=label,
        source_root=f"aep-raw-archive-{label}",
        deposited_tar_gz=f"aep-raw-evidence-{label}.tar.gz",
        deposited_manifest=f"MANIFEST-{label}.sha256",
        deposited_metadata=f"ARCHIVE-METADATA-{label}.json",
        manifest_sha256=built["manifest_sha256"],
        tar_sha256="0" * 64,  # not checked on the --local path
        tar_gz_sha256=built["tar_gz_sha256"],
        metadata_sha256=built["metadata_sha256"],
        files=built["files"],
        run_dirs=built["run_dirs"],
        roots=1,
        rederive=rederive,
        min_configs=1,
        note="no re-derivation baseline recorded; manifest check only",
    )
    fields.update(over)
    return vpa.Archive(**fields)


@pytest.fixture
def deposit(vpa, tmp_path, monkeypatch):
    """Two correct archives, and ARCHIVES describing exactly them."""
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    records = (
        make_record(vpa, "2026-09-03", first),
        make_record(vpa, "2026-09-15", second),
    )
    monkeypatch.setattr(vpa, "ARCHIVES", records)
    return {"first": first, "second": second, "records": records}


def run_main(vpa, tmp_path, *dirs, extra: tuple[str, ...] = ()) -> int:
    argv = []
    for directory in dirs:
        argv += ["--local", str(directory)]
    argv += ["--scratch", str(tmp_path / "scratch"), *extra]
    return vpa.main(argv)


# --------------------------------------------------------------------------
# The success path. If this cannot pass, nothing below means anything.
# --------------------------------------------------------------------------


def test_both_archives_present_and_correct_verifies(vpa, tmp_path, deposit, capsys):
    code = run_main(
        vpa, tmp_path, deposit["first"]["dir"], deposit["second"]["dir"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert "VERIFIED" in out
    assert "VERIFICATION FAILED" not in out


def test_the_success_path_actually_checked_both_archives(
    vpa, tmp_path, deposit, capsys
):
    """A pass that examined one archive is the failure this rewrite was for."""
    run_main(vpa, tmp_path, deposit["first"]["dir"], deposit["second"]["dir"])
    out = capsys.readouterr().out
    assert "ARCHIVE 2026-09-03" in out
    assert "ARCHIVE 2026-09-15" in out
    assert out.count("files verified against the manifest") == 2


# --------------------------------------------------------------------------
# Which archives were supplied.
# --------------------------------------------------------------------------


def test_one_archive_alone_is_refused_and_the_missing_one_is_named(
    vpa, tmp_path, deposit
):
    with pytest.raises(SystemExit) as excinfo:
        run_main(vpa, tmp_path, deposit["first"]["dir"])
    message = str(excinfo.value)
    assert "2026-09-15" in message
    assert "missing archive" in message


def test_the_same_archive_twice_is_not_counted_as_two(vpa, tmp_path, deposit):
    with pytest.raises(SystemExit) as excinfo:
        run_main(vpa, tmp_path, deposit["first"]["dir"], deposit["first"]["dir"])
    assert "same archive" in str(excinfo.value)


def test_a_directory_matching_no_known_archive_is_refused(
    vpa, tmp_path, deposit
):
    """Matching is by manifest digest, so a stranger cannot stand in."""
    stranger = build_archive(tmp_path, "stranger", "other", runs=1)
    with pytest.raises(SystemExit) as excinfo:
        run_main(vpa, tmp_path, deposit["first"]["dir"], stranger["dir"])
    assert "matches no archive" in str(excinfo.value)


def test_a_directory_with_no_manifest_is_refused(vpa, tmp_path, deposit):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        run_main(vpa, tmp_path, deposit["first"]["dir"], empty)
    assert "no MANIFEST.sha256" in str(excinfo.value)


# --------------------------------------------------------------------------
# The contents, against what the repository expects.
# --------------------------------------------------------------------------


def test_a_wrong_tarball_digest_is_refused(vpa, tmp_path, monkeypatch, capsys):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    # The record says one thing; the bytes on disk say another.
    wrong = make_record(
        vpa, "2026-09-03", first, tar_gz_sha256="f" * 64
    )
    monkeypatch.setattr(
        vpa, "ARCHIVES", (wrong, make_record(vpa, "2026-09-15", second))
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "MISMATCH" in out
    assert "aep-raw-evidence-2026-09-03.tar.gz digest" in out


def test_a_wrong_metadata_digest_is_refused(vpa, tmp_path, monkeypatch, capsys):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, metadata_sha256="a" * 64),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "ARCHIVE-METADATA-2026-09-03.json digest" in out


def test_a_file_in_the_manifest_but_absent_from_the_archive_is_refused(
    vpa, tmp_path, monkeypatch, capsys
):
    """The manifest promises a file the tarball does not carry."""
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    manifest = first["dir"] / "MANIFEST.sha256"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + f"{'b' * 64}  matrix/cell-ffff-r9/events.jsonl\n",
        encoding="utf-8",
    )
    record = make_record(
        vpa, "2026-09-03", first, manifest_sha256=sha256_file(manifest)
    )
    monkeypatch.setattr(
        vpa, "ARCHIVES", (record, make_record(vpa, "2026-09-15", second))
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "manifest problems" in out


def test_a_file_in_the_archive_but_absent_from_the_manifest_is_refused(
    vpa, tmp_path, monkeypatch, capsys
):
    """The tarball carries something no manifest line attests.

    Caught by the file count rather than by the per-file loop, which walks the
    manifest and so cannot see a file the manifest never mentions. That is
    exactly why the count is checked separately.
    """
    first = build_archive(
        tmp_path,
        "2026-09-03",
        "matrix",
        runs=3,
        extra_in_tar={"matrix/cell-dead-r7/events.jsonl": b"smuggled\n"},
        omit_from_manifest=("matrix/cell-dead-r7/events.jsonl",),
    )
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    # The record's file count is what the manifest attests, not what the tar has.
    record = make_record(vpa, "2026-09-03", first, files=first["files"] - 1)
    monkeypatch.setattr(
        vpa, "ARCHIVES", (record, make_record(vpa, "2026-09-15", second))
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "file count" in out


def test_a_file_whose_content_does_not_match_its_manifest_digest_is_refused(
    vpa, tmp_path, monkeypatch, capsys
):
    first = build_archive(
        tmp_path,
        "2026-09-03",
        "matrix",
        runs=3,
        corrupt_manifest_digest_for="matrix/cell-0000-r0/events.jsonl",
    )
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "1 manifest problems" in out


def test_a_wrong_run_directory_count_is_refused(
    vpa, tmp_path, monkeypatch, capsys
):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, run_dirs=99),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "run directories, expected 99" in out


# --------------------------------------------------------------------------
# Counting run directories: one definition, two tests, and they disagree.
# --------------------------------------------------------------------------


def test_run_directories_are_the_union_of_the_two_tests(vpa):
    """1 457 by name and 1 458 by config is 1 458; 1 332 and 992 is 1 332.

    Either test alone contradicts a figure the manuscript prints, so the union
    is the definition. Shaped here the way both real archives are shaped.
    """
    manifest = "\n".join(
        [
            # named -r<N> and holding a config: both tests agree
            f"{'0'*64}  matrix/a-r0/run-config.json",
            f"{'0'*64}  matrix/a-r0/events.jsonl",
            # named, no config -- the B5 session shape
            f"{'0'*64}  ws6/b-r1/events.jsonl",
            # a config under a name the -r<N> test misses -- the .attempt shape
            f"{'0'*64}  voided/c-r2.attempt-1/run-config.json",
        ]
    )
    total, named, with_config = vpa.count_run_directories(manifest)
    # matrix/a-r0 and ws6/b-r1 are named; matrix/a-r0 and voided/c-r2.attempt-1
    # hold a config. Neither set is the answer: the union of three is.
    assert (named, with_config) == (2, 2)
    assert total == 3, "the union, not either test alone"


def test_a_blank_or_malformed_manifest_line_is_skipped_not_counted(vpa):
    total, named, with_config = vpa.count_run_directories(
        "\n\n   \nnot-a-manifest-line\n"
    )
    assert (total, named, with_config) == (0, 0, 0)


# --------------------------------------------------------------------------
# The re-derivation: the guard that caught the rewrite's own bug.
# --------------------------------------------------------------------------


def _stub_run(recorder, stdout: str, returncode: int = 0):
    def fake(args, **kwargs):
        recorder.append((list(args), kwargs))
        return subprocess.CompletedProcess(args, returncode, stdout, "")
    return fake


HEALTHY = (
    "checking the extraction\n"
    "=====\n"
    "IDENTICAL 114   IDENTICAL-after-normalisation 8   DIFFERS 0   "
    "NOT REGENERATED 8   DIFFERS-timestamped-PDF 0\n"
)

SILENT = "checking the extraction against MANIFEST.sha256\n"


def test_the_manifest_is_staged_where_verify_raw_archive_will_look(
    vpa, tmp_path, monkeypatch, capsys
):
    """The regression. Pin it so the ZERO guard never has to catch it again.

    ``verify_raw_archive.py`` reads ``<--archive>/MANIFEST.sha256`` under that
    exact name. The 2026-09-16 rewrite gave each archive its own work directory
    and stopped copying the manifest into it, so the subprocess found nothing
    and compared nothing. The guard below reported it, which is the guard
    working; this test is so that it does not have to.
    """
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    calls: list = []
    monkeypatch.setattr(vpa.subprocess, "run", _stub_run(calls, HEALTHY))
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    run_main(vpa, tmp_path, first["dir"], second["dir"])

    rederive_calls = [c for c in calls if "verify_raw_archive.py" in " ".join(c[0])]
    assert rederive_calls, "the re-derivation was never invoked"
    args = rederive_calls[0][0]
    archive_dir = Path(args[args.index("--archive") + 1])
    staged = archive_dir / "MANIFEST.sha256"
    assert staged.is_file(), (
        f"{staged} is absent, so verify_raw_archive.py would compare nothing"
    )
    assert staged.read_bytes() == (first["dir"] / "MANIFEST.sha256").read_bytes()


def test_a_re_derivation_that_compared_nothing_is_a_failure_not_a_pass(
    vpa, tmp_path, monkeypatch, capsys
):
    """``DIFFERS 0`` is also true of a run that compared zero files."""
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(vpa.subprocess, "run", _stub_run([], SILENT))
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "compared ZERO files" in out
    assert "VERIFIED:" not in out


def test_a_re_derivation_reporting_differences_is_a_failure(
    vpa, tmp_path, monkeypatch, capsys
):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    differing = HEALTHY.replace("DIFFERS 0", "DIFFERS 3")
    monkeypatch.setattr(vpa.subprocess, "run", _stub_run([], differing))
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    assert code == 1
    assert "3 differing files" in capsys.readouterr().out


def test_the_extension_prints_NOT_RUN_with_its_reason(
    vpa, tmp_path, deposit, capsys
):
    """R14's third outcome. "I did not look" must not render as "I looked"."""
    code = run_main(
        vpa, tmp_path, deposit["first"]["dir"], deposit["second"]["dir"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "re-derivation: NOT RUN" in out
    assert "no re-derivation baseline recorded" in out


def test_skip_rederive_stops_before_any_subprocess(
    vpa, tmp_path, monkeypatch, capsys
):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    calls: list = []
    monkeypatch.setattr(vpa.subprocess, "run", _stub_run(calls, HEALTHY))
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"],
                    extra=("--skip-rederive",))
    assert code == 0
    assert calls == []


# --------------------------------------------------------------------------
# resolve_doi: what the record must carry.
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _record_with(vpa, names) -> bytes:
    return json.dumps(
        {
            "files": [
                {"key": name, "links": {"self": f"https://zenodo.test/{name}"}}
                for name in names
            ]
        }
    ).encode()


def test_resolve_doi_returns_a_link_for_every_deposited_file(
    vpa, monkeypatch, deposit
):
    names = [n for a in vpa.ARCHIVES for n in a.deposited_names]
    monkeypatch.setattr(
        vpa.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(_record_with(vpa, names)),
    )
    links = vpa.resolve_doi("10.5281/zenodo.22766567")
    assert sorted(links) == sorted(names)
    assert len(links) == 6


@pytest.mark.parametrize("dropped", [0, 3, 5])
def test_resolve_doi_refuses_a_record_missing_any_deposited_file(
    vpa, monkeypatch, deposit, dropped
):
    """Four digests matching is not a pass when two files were never uploaded."""
    names = [n for a in vpa.ARCHIVES for n in a.deposited_names]
    absent = names[dropped]
    monkeypatch.setattr(
        vpa.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(
            _record_with(vpa, [n for n in names if n != absent])
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        vpa.resolve_doi("10.5281/zenodo.22766567")
    message = str(excinfo.value)
    assert "missing 1 of 6" in message
    assert absent in message


def test_resolve_doi_refuses_a_record_holding_only_one_archive(
    vpa, monkeypatch, deposit
):
    """The specific shape docs/29 §0 calls Ruin #2."""
    names = list(vpa.ARCHIVES[0].deposited_names)
    monkeypatch.setattr(
        vpa.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(_record_with(vpa, names)),
    )
    with pytest.raises(SystemExit) as excinfo:
        vpa.resolve_doi("10.5281/zenodo.22766567")
    assert "missing 3 of 6" in str(excinfo.value)


def test_resolve_doi_accepts_the_doi_in_the_forms_a_reader_will_paste(
    vpa, monkeypatch, deposit
):
    seen: list[str] = []

    def fake_urlopen(url, *a, **k):
        seen.append(url)
        names = [n for arc in vpa.ARCHIVES for n in arc.deposited_names]
        return _FakeResponse(_record_with(vpa, names))

    monkeypatch.setattr(vpa.urllib.request, "urlopen", fake_urlopen)
    for form in (
        "10.5281/zenodo.22766567",
        "https://doi.org/10.5281/zenodo.22766567",
        "doi:10.5281/zenodo.22766567",
    ):
        vpa.resolve_doi(form)
    assert seen == ["https://zenodo.org/api/records/22766567"] * 3


# --------------------------------------------------------------------------
# The table itself. A test that cannot find its subject must say so (R14).
# --------------------------------------------------------------------------


#: The deposit's shape, spelled out rather than counted.
#:
#: This is deliberately a table and not a number. It was
#: ``len(ARCHIVES) == 2`` until 2026-09-24, and when the third part was added
#: the only thing that failed was an integer -- which tells whoever is looking
#: at a red build nothing about what changed or whether it was intended. The
#: entry below is what a reviewer would have to read and agree with.
#:
#: Adding or removing a part means editing this table, and editing it means
#: stating the label, the three deposited filenames and whether the part has a
#: re-derivation baseline. That is the decision; the count follows from it.
EXPECTED_DEPOSIT: dict[str, dict[str, object]] = {
    "2026-09-03": {
        "tar_gz": "aep-raw-evidence-2026-09-03.tar.gz",
        "manifest": "MANIFEST-2026-09-03.sha256",
        "metadata": "ARCHIVE-METADATA-2026-09-03.json",
        "rederive": True,
        "why": "the 432-run matrix and the collections around it",
    },
    "2026-09-15": {
        "tar_gz": "aep-raw-evidence-2026-09-15.tar.gz",
        "manifest": "MANIFEST-2026-09-15.sha256",
        "metadata": "ARCHIVE-METADATA-2026-09-15.json",
        "rederive": False,
        "why": "WS-4 write-loss, the real-Temporal baseline, phase 13",
    },
    "2026-09-24": {
        "tar_gz": "aep-raw-evidence-2026-09-24.tar.gz",
        "manifest": "MANIFEST-2026-09-24.sha256",
        "metadata": "ARCHIVE-METADATA-2026-09-24.json",
        "rederive": False,
        "why": (
            "the roots neither earlier part reached, including the five that "
            "supply eighteen manuscript macros"
        ),
    },
}


def test_the_real_table_still_describes_the_deposit_this_repository_claims():
    """Guards the fixtures above from describing a shape the script has left.

    Asserts the CONTENTS, not the count. A part added or removed without
    ``EXPECTED_DEPOSIT`` being edited fails here with the label that moved,
    which is the thing a reader needs; the count is then a consequence.
    """
    module = load()
    actual = {
        a.label: {
            "tar_gz": a.deposited_tar_gz,
            "manifest": a.deposited_manifest,
            "metadata": a.deposited_metadata,
            "rederive": a.rederive,
        }
        for a in module.ARCHIVES
    }

    added = sorted(set(actual) - set(EXPECTED_DEPOSIT))
    removed = sorted(set(EXPECTED_DEPOSIT) - set(actual))
    assert not added and not removed, (
        f"the deposit's parts changed: added {added}, removed {removed}. "
        "Update EXPECTED_DEPOSIT in this file, and with it docs/29 §1's "
        "digest table, §3's description, ARTIFACT.md §5 and CITATION.cff -- "
        "each of those states the parts by name or digest."
    )

    for label, expected in EXPECTED_DEPOSIT.items():
        got = actual[label]
        for field in ("tar_gz", "manifest", "metadata"):
            assert got[field] == expected[field], (
                f"{label}: deposited {field} is {got[field]!r}, this test "
                f"expects {expected[field]!r}"
            )
        assert got["rederive"] == expected["rederive"], (
            f"{label}: rederive is {got['rederive']}, expected "
            f"{expected['rederive']}. A part gaining or losing a "
            "re-derivation baseline changes paper/sections/09-artifact.tex "
            "and docs/29 §6, which both state which parts have one"
        )

    # Uniqueness is a property of the record, not of the table: Zenodo cannot
    # hold two files of one name, which is why the deposited copies carry a
    # date suffix at all.
    names = [n for a in module.ARCHIVES for n in a.deposited_names]
    assert len(set(names)) == len(names), (
        "deposited names must be unique within one Zenodo record"
    )
    assert len(names) == 3 * len(EXPECTED_DEPOSIT)

    for archive in module.ARCHIVES:
        for digest in (
            archive.manifest_sha256,
            archive.tar_sha256,
            archive.tar_gz_sha256,
            archive.metadata_sha256,
        ):
            assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")


def test_exactly_one_archive_carries_a_re_derivation_baseline():
    """If this changes, §9 of the manuscript and docs/29 §6 change with it."""
    module = load()
    rederiving = [a.label for a in module.ARCHIVES if a.rederive]
    assert rederiving == ["2026-09-03"], (
        "the extension has no recorded re-derivation baseline; if one is "
        "established, paper/sections/09-artifact.tex and docs/29 §6 both say "
        "it has not been done and must be updated in the same pass"
    )


# --------------------------------------------------------------------------
# Refusals on the way in, and the paths a first pass left unexecuted.
# --------------------------------------------------------------------------


def _stub_dispatch(responses: dict[str, tuple[int, str]]):
    """Different answers for verify_raw_archive.py and audit_config_digests.py."""
    def fake(args, **kwargs):
        joined = " ".join(str(a) for a in args)
        for needle, (code, stdout) in responses.items():
            if needle in joined:
                return subprocess.CompletedProcess(args, code, stdout, "")
        raise AssertionError(f"unstubbed subprocess: {joined}")
    return fake


def test_a_member_escaping_the_extraction_root_is_refused(
    vpa, tmp_path, monkeypatch
):
    """A path-traversal member in a tarball fetched over the network.

    This is a security refusal on untrusted input and it had never been
    executed. ``filter="data"`` would also reject it, but the explicit check
    runs first and is the one that names the member.
    """
    good = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    hostile_dir = tmp_path / "archive-hostile"
    hostile_dir.mkdir()
    payload = b"escaped\n"
    tar_path = hostile_dir / "aep-raw-evidence.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(payload)
        info.mtime = 0
        tar.addfile(info, io.BytesIO(payload))
    manifest = hostile_dir / "MANIFEST.sha256"
    manifest.write_text(f"{sha256_bytes(payload)}  ../escape.txt\n", encoding="utf-8")
    metadata = hostile_dir / "ARCHIVE-METADATA.json"
    metadata.write_text("{}\n", encoding="utf-8")

    hostile = {
        "dir": hostile_dir,
        "files": 1,
        "run_dirs": 0,
        "tar_gz_sha256": sha256_file(tar_path),
        "manifest_sha256": sha256_file(manifest),
        "metadata_sha256": sha256_file(metadata),
    }
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", hostile),
            make_record(vpa, "2026-09-15", good),
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        run_main(vpa, tmp_path, hostile_dir, good["dir"])
    assert "unsafe archive member" in str(excinfo.value)


def test_an_archive_directory_without_its_tarball_is_refused(
    vpa, tmp_path, deposit
):
    (deposit["first"]["dir"] / "aep-raw-evidence.tar.gz").unlink()
    with pytest.raises(SystemExit) as excinfo:
        run_main(vpa, tmp_path, deposit["first"]["dir"], deposit["second"]["dir"])
    assert "is missing" in str(excinfo.value)


def test_absent_metadata_is_reported_as_not_checked_rather_than_passed(
    vpa, tmp_path, deposit, capsys
):
    """R14 again: "I could not look" must not render as "I looked"."""
    (deposit["first"]["dir"] / "ARCHIVE-METADATA.json").unlink()
    code = run_main(
        vpa, tmp_path, deposit["first"]["dir"], deposit["second"]["dir"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "not supplied by this source; not checked" in out


def test_neither_doi_nor_local_is_a_usage_error(vpa, tmp_path):
    with pytest.raises(SystemExit):
        vpa.main(["--scratch", str(tmp_path / "s")])


def test_doi_and_local_together_are_a_usage_error(vpa, tmp_path, deposit):
    with pytest.raises(SystemExit):
        vpa.main(
            [
                "--doi", "10.5281/zenodo.22766567",
                "--local", str(deposit["first"]["dir"]),
                "--scratch", str(tmp_path / "s"),
            ]
        )


def test_a_pre_existing_scratch_directory_is_cleared_not_reused(
    vpa, tmp_path, deposit
):
    """Stale extractions from a previous run must not be counted as this one's."""
    scratch = tmp_path / "scratch"
    (scratch / "leftover").mkdir(parents=True)
    (scratch / "leftover" / "stale.txt").write_text("old\n", encoding="utf-8")
    code = run_main(
        vpa, tmp_path, deposit["first"]["dir"], deposit["second"]["dir"]
    )
    assert code == 0
    assert not (scratch / "leftover").exists()


def test_the_json_report_records_both_archives_and_the_failures(
    vpa, tmp_path, monkeypatch
):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, run_dirs=99),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    out_path = tmp_path / "report.json"
    code = run_main(
        vpa, tmp_path, first["dir"], second["dir"],
        extra=("--json", str(out_path)),
    )
    assert code == 1
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert sorted(report["archives"]) == ["2026-09-03", "2026-09-15"]
    assert report["archives"]["2026-09-15"]["manifest_problems"] == 0
    assert any("run directories" in f for f in report["failures"])


def test_a_re_derivation_subprocess_that_crashes_is_a_failure(
    vpa, tmp_path, monkeypatch, capsys
):
    """Exit 0 and 1 are verdicts; anything else means it did not get that far."""
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa.subprocess,
        "run",
        _stub_dispatch(
            {
                "verify_raw_archive.py": (2, HEALTHY),
                "audit_config_digests.py": (0, "NONE UNEXPLAINED\n"),
            }
        ),
    )
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    assert code == 1
    assert "verify_raw_archive exited 2" in capsys.readouterr().out


def test_a_failing_config_digest_audit_is_a_failure(
    vpa, tmp_path, monkeypatch, capsys
):
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa.subprocess,
        "run",
        _stub_dispatch(
            {
                "verify_raw_archive.py": (0, HEALTHY),
                "audit_config_digests.py": (1, "a digest matches no generation\n"),
            }
        ),
    )
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 1
    assert "config-digest audit exited 1" in out


def test_a_healthy_re_derivation_passes_end_to_end(
    vpa, tmp_path, monkeypatch, capsys
):
    """The shape docs/29 6 prints as expected output."""
    first = build_archive(tmp_path, "2026-09-03", "matrix", runs=3)
    second = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    monkeypatch.setattr(
        vpa.subprocess,
        "run",
        _stub_dispatch(
            {
                "verify_raw_archive.py": (0, HEALTHY),
                "audit_config_digests.py": (0, "NONE UNEXPLAINED\n"),
            }
        ),
    )
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", first, rederive=True),
            make_record(vpa, "2026-09-15", second),
        ),
    )
    code = run_main(vpa, tmp_path, first["dir"], second["dir"])
    out = capsys.readouterr().out
    assert code == 0
    assert "compared 122 tracked analysis files" in out
    assert "VERIFIED" in out


def test_directory_members_are_not_counted_as_files(
    vpa, tmp_path, monkeypatch, capsys
):
    """A tarball carrying directory entries must still report the file count.

    Real archives carry them; the synthetic fixtures above do not, so the
    skip-non-regular branch went unexecuted until this test.
    """
    good = build_archive(tmp_path, "2026-09-15", "ws5", runs=2)
    directory = tmp_path / "archive-withdirs"
    directory.mkdir()
    payload = {"matrix/cell-0000-r0/events.jsonl": b'{"run":0}\n'}
    tar_path = directory / "aep-raw-evidence.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in ("matrix", "matrix/cell-0000-r0"):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mtime = 0
            tar.addfile(info)
        for name, data in payload.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    manifest = directory / "MANIFEST.sha256"
    manifest.write_text(
        "".join(f"{sha256_bytes(d)}  {n}\n" for n, d in payload.items()),
        encoding="utf-8",
    )
    metadata = directory / "ARCHIVE-METADATA.json"
    metadata.write_text("{}\n", encoding="utf-8")

    built = {
        "dir": directory,
        "files": len(payload),
        "run_dirs": 1,
        "tar_gz_sha256": sha256_file(tar_path),
        "manifest_sha256": sha256_file(manifest),
        "metadata_sha256": sha256_file(metadata),
    }
    monkeypatch.setattr(
        vpa,
        "ARCHIVES",
        (
            make_record(vpa, "2026-09-03", built),
            make_record(vpa, "2026-09-15", good),
        ),
    )
    code = run_main(vpa, tmp_path, directory, good["dir"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "extracted 1 files (expected 1)" in out


def test_a_reused_work_directory_does_not_accumulate_an_old_extraction(
    vpa, tmp_path, deposit
):
    """Two passes over one work directory must count the second, not both."""
    archive = deposit["records"][0]
    base = deposit["first"]["dir"]
    work = tmp_path / "reused"
    for _ in range(2):
        outcome = vpa.verify_one(
            archive,
            base / "aep-raw-evidence.tar.gz",
            base / "MANIFEST.sha256",
            base / "ARCHIVE-METADATA.json",
            work,
            skip_rederive=True,
        )
    assert outcome.failures == []
    assert outcome.report["extracted_files"] == archive.files
