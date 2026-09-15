"""Which sources produced the artifacts in ``paper/``?

B21 item 3. ``build_paper.sh`` promotes ``main.log``, ``main.bbl`` and
``main.blg`` into ``paper/`` on every clean build, and
``check_paper_numbers.py`` reads them back whenever ``--build-dir`` is not
given. Nothing connected the two, so a gate run days later reported on
whichever build last happened to promote -- and did so silently. That is how a
``17 passed, 1 failed`` baseline computed from three-week-old artifacts was
quoted as a control through two phases.

**The rule is "produced from THESE sources", not "newer than the sources".**
Age was rejected deliberately: ``git checkout`` resets source mtimes, so an
mtime rule reports stale after every branch switch and is learned-around; and
this project has already recorded that sync clients normalise mtimes, so
depending on them here would mean ignoring its own finding. What this compares
is an exact hash set -- no threshold, no clock -- which is the orphan gate's
construction.

**The writer and the reader live in one module on purpose.** ``freeze_results``
records the same decision for the same reason: a manifest that disagrees with
the analysis is worse than no manifest. Two implementations of "which files are
sources" would drift, and the drift would fail open.

**Deny-list, not allow-list.** Sources are "every file under ``paper/`` that is
not a known artifact". An allow-list would silently omit a new kind of source,
and an omitted source is one whose edits never trigger a mismatch -- fail-open,
the direction that matters. Under a deny-list a new *artifact* type is hashed
by mistake instead, which produces a spurious mismatch and reports STALE. That
is the safe direction (B33: this check authorises "the numbers are current",
so it must over-report staleness).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

STAMP_NAME = ".build-provenance.json"
#: The anonymous build gets its own stamp. Its *payload* is identical to the
#: public one -- both builds read the same sources -- but it must be a separate
#: file, because what the stamp records is when THAT artifact was produced. With
#: one shared stamp, rebuilding main.pdf would silently vouch for a main-anon.pdf
#: that had not been rebuilt, which is exactly how main-anon.pdf sat three days
#: behind section VIII while the checker reported 19 passed.
ANON_STAMP_NAME = ".build-provenance-anon.json"
#: The supplementary is a separate submitted PDF (IEEE CS treats appendices as
#: supplemental material, submitted separately), so it gets its own stamps for
#: the same reason the anonymous build does: one shared stamp would let a
#: rebuild of one artifact vouch for another that was never rebuilt.
SUPP_STAMP_NAME = ".build-provenance-supp.json"
SUPP_ANON_STAMP_NAME = ".build-provenance-supp-anon.json"
STAMP_VERSION = 1

# Top-level build products. Everything else under paper/ is an input.
ARTIFACT_NAMES = {
    STAMP_NAME,
    ANON_STAMP_NAME,
    SUPP_STAMP_NAME,
    SUPP_ANON_STAMP_NAME,
    "main.pdf", "main.aux", "main.bbl", "main.blg", "main.log",
    "main.out", "main.toc", "main.synctex.gz",
    "main-anon.pdf", "main-anon.aux", "main-anon.bbl", "main-anon.blg",
    "main-anon.log", "main-anon.out", "main-anon.toc",
    # The supplementary's products. Its SOURCE, supplementary.tex, is
    # deliberately NOT listed: it stays a source, so editing it marks the main
    # build stale too. That coupling is intentional. The two PDFs are submitted
    # together, and a supplementary newer than the paper that points at it is
    # exactly the state that must not pass silently.
    "supplementary.pdf", "supplementary.aux", "supplementary.bbl",
    "supplementary.blg", "supplementary.log", "supplementary.out",
    "supplementary.toc",
    "supplementary-anon.pdf", "supplementary-anon.aux",
    "supplementary-anon.bbl", "supplementary-anon.blg",
    "supplementary-anon.log", "supplementary-anon.out",
    "supplementary-anon.toc",
}


#: build_paper.sh stages its promoted artifacts inside paper/ as
#: ".<job>.<ext>.stage.<pid>" and ".provenance.stage.<pid>", so they exist under
#: paper/ for the duration of a build. They are products mid-flight, not
#: sources. Counting them as sources made the anonymous-build staleness check
#: report "1 added (.provenance.stage.699)" whenever it ran during a public
#: build -- a check failing on the build's own scaffolding.
_STAGING = re.compile(r"^\..+\.stage\.\d+$")


#: Directories under paper/ that are not build inputs. Kept deliberately short:
#: every name here is a file the stamp stops covering, and the default must be
#: that a file under paper/ IS a source.
NON_SOURCE_DIRS: tuple[str, ...] = (".ai/",)


def _is_artifact(rel: str) -> bool:
    # A session log is not a build input. `.ai/track.md` is written by tooling
    # on every session and is gitignored, so a clone does not have it -- and
    # `verify` treats a recorded-but-absent source as STALE. Including it meant
    # the committed stamps could not verify in a clean clone: a gate that
    # passed on this machine and failed on any other, for a reason nobody had
    # written down. Excluded here so the stamp is reproducible from a clone.
    if rel.startswith(NON_SOURCE_DIRS):
        return True
    # Only at the top level: paper/figures/figure-1-....pdf is an INPUT, and
    # excluding it by extension would drop a real source from coverage.
    if "/" in rel:
        return False
    return rel in ARTIFACT_NAMES or bool(_STAGING.match(rel))


def source_digests(paper: Path) -> dict[str, str]:
    """SHA-256 of every source file under ``paper``, keyed by POSIX relpath.

    Raises OSError if any candidate file cannot be read. Callers convert that
    into STALE rather than skipping the file: "I could not read it" and "it is
    unchanged" must never render the same.
    """
    digests: dict[str, str] = {}
    for path in sorted(paper.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(paper).as_posix()
        if _is_artifact(rel):
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        digests[rel] = digest.hexdigest()
    return digests


def write_stamp(paper: Path, out: Path | None = None) -> Path:
    target = out or (paper / STAMP_NAME)
    payload = {
        "version": STAMP_VERSION,
        "sources": source_digests(paper),
    }
    # newline="\n" and sorted keys: B5's lesson. A stamp whose bytes differ by
    # platform is a stamp that cannot be compared across one.
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def verify(paper: Path, stamp_name: str = STAMP_NAME) -> tuple[bool, str]:
    """(artifacts match current sources, reason).

    EVERY ambiguous outcome returns False. There is no path to True that does
    not require a complete, readable, exactly-matching set.

    ``stamp_name`` selects which build is being verified: the public artifacts
    against :data:`STAMP_NAME`, the anonymous PDF against
    :data:`ANON_STAMP_NAME`.
    """
    stamp = paper / stamp_name
    if not stamp.is_file():
        return False, (
            f"no {stamp_name} in {paper}; the artifacts there were not "
            f"recorded as produced from any source tree. Run "
            f"scripts/build_paper.sh, or pass --build-dir for a staged build."
        )
    try:
        payload = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, f"{stamp_name} unreadable or malformed: {exc}"

    if payload.get("version") != STAMP_VERSION:
        return False, (
            f"{stamp_name} version {payload.get('version')!r}, expected "
            f"{STAMP_VERSION}"
        )
    recorded = payload.get("sources")
    if not isinstance(recorded, dict) or not recorded:
        return False, f"{stamp_name} records no sources"

    try:
        current = source_digests(paper)
    except OSError as exc:
        return False, f"a source under {paper} could not be read: {exc}"

    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    changed = sorted(
        rel for rel in set(current) & set(recorded)
        if current[rel] != recorded[rel]
    )
    if added or removed or changed:
        parts = []
        if changed:
            parts.append(f"{len(changed)} changed ({', '.join(changed[:3])})")
        if added:
            parts.append(f"{len(added)} added ({', '.join(added[:3])})")
        if removed:
            parts.append(f"{len(removed)} removed ({', '.join(removed[:3])})")
        return False, (
            "build artifacts predate the current sources: " + "; ".join(parts)
        )
    return True, f"{len(current)} sources match {stamp_name}"


def main(argv: list[str]) -> int:
    # The optional <out> exists so a build can stage the stamp outside paper/.
    # Writing it into place and moving it away would destroy the previous
    # stamp, and a build that then failed would leave none at all -- turning a
    # failed build into a stale-artifact report on the next run.
    if len(argv) not in (3, 4) or argv[1] != "write":
        print(
            "usage: paper_provenance.py write <paper-dir> [<out>]",
            file=sys.stderr,
        )
        return 2
    out = Path(argv[3]) if len(argv) == 4 else None
    print(f"wrote {write_stamp(Path(argv[2]), out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
