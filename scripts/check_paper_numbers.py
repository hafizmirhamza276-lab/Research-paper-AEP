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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_provenance  # noqa: E402

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

    def note(self, detail: str) -> None:
        """Visible, and neither a pass nor a failure.

        Used where something is deliberately true-for-now and a reader
        should meet it on every run rather than find it in a report.
        """
        print(f"  NOTE  {detail}")


#: WS-5's collection root. Its four steps are separate analyses, not one
#: directory, because each was frozen when it finished.
WS5_ROOT = ROOT / "experiments" / "results" / "ws5-2026-09-10"


def check_generated_tables(
    result: Result,
    paper: Path,
    analysis: Path,
    fsync_analysis: Path,
    flakey: Path,
    b5_session: Path,
    writeloss_cell: Path,
    ws5_everysec: Path,
    ws5_p30: Path,
    ws5_keying: Path,
    fsync_always_45: Path,
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
        ("WS-6 B5 session", b5_session),
        ("WS-4 write-loss protocol cell", writeloss_cell),
        ("WS-5 everysec 15-run cell", ws5_everysec),
        ("WS-5 30%-crash regime", ws5_p30),
        ("WS-5 read-back keying variant", ws5_keying),
        ("appendfsync=always 45-run arm", fsync_always_45),
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
                "--b5-session",
                str(b5_session),
                "--writeloss-cell",
                str(writeloss_cell),
                "--ws5-everysec",
                str(ws5_everysec),
                "--ws5-p30",
                str(ws5_p30),
                "--ws5-keying",
                str(ws5_keying),
                "--fsync-always-45",
                str(fsync_always_45),
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


#: Macros that exist but are not yet quoted, with the pass that will quote
#: them. Phase 25 built the generator path from WS-5's CSVs to numbers.tex;
#: phase 26 writes the prose. Emitting them and using them in one pass was
#: not possible: the generator change and the prose change are separately
#: gated, and a macro cannot be used before it exists.
#:
#: This is NOT an allowlist that silently subtracts. The check below fails
#: if a name here has vanished from numbers.tex (a stale entry) and fails
#: if a name here IS used (an entry nobody deleted). Both directions, so
#: the list cannot quietly outlive its reason.
PENDING_MACROS: dict[str, str] = {
    # Empty, and that is the point. Phase 25 staged seventeen WS-5 macros here
    # ahead of the prose; phase 26 wrote the prose and every one of them is now
    # quoted, so every entry was deleted. The mechanism stays: the next pass
    # that has to emit a macro before it can be used gets the same two checks
    # -- a stale entry fails, an entry already in use fails -- rather than a
    # silent exemption.
}

def check_macros_are_used(result: Result, paper: Path) -> None:
    """Every generated number must appear somewhere in the manuscript.

    A macro that is defined and never used is a number that was computed and
    then dropped, and the reader has no way to know it existed. That is a
    tolerable accident in a stable draft and a dangerous one during a framing
    revision, which is exactly when a claim gets moved, its replacement gets
    written, and its evidence gets orphaned. LaTeX catches the opposite
    direction -- a macro used and not defined -- and says nothing about this
    one.

    **Widened to the supplementary, WS-9 move 2.** It previously scanned
    ``main.tex`` and ``sections/*.tex`` only. Moving the coverage-gap
    enumeration out of section VIII took 13 macros with it --- ``CellsCollected``,
    ``ExecutionsCollected``, ``ClassRunsPerArm`` and the ``ClassPp*`` family ---
    each used *nowhere else in the paper*. Left unwidened, this gate would have
    reported all 13 orphaned and the honest reading of that report would have
    been wrong: they are used, in a document the gate could not see. A
    submitted PDF whose numbers no gate reads is the ``main-anon.pdf`` failure
    with a new name.
    """
    numbers = paper / "generated" / "numbers.tex"
    if not numbers.is_file():
        result.check(False, "numbers.tex exists", f"missing {numbers}")
        return
    defined = set(
        re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", numbers.read_text(encoding="utf-8"))
    )
    sources = [paper / "main.tex", *sorted((paper / "sections").glob("*.tex"))]
    supplementary = paper / "supplementary.tex"
    if supplementary.is_file():
        sources.append(supplementary)
    used: set[str] = set()
    for path in sources:
        text = path.read_text(encoding="utf-8")
        used.update(re.findall(r"\\([A-Za-z]+)\{?\}?", text))
    orphans = sorted(defined - used)

    # Both directions, so the pending list cannot become a hole.
    stale = sorted(n for n in PENDING_MACROS if n not in defined)
    result.check(
        not stale,
        "every pending macro still exists",
        f"{len(stale)} named in PENDING_MACROS but not in numbers.tex: "
        f"{', '.join(stale)}",
    )
    landed = sorted(n for n in PENDING_MACROS if n in used)
    result.check(
        not landed,
        "no pending macro is already in use",
        f"{len(landed)} now used and still listed as pending -- delete them "
        f"from PENDING_MACROS: {', '.join(landed)}",
    )

    unexplained = [n for n in orphans if n not in PENDING_MACROS]
    result.check(
        not unexplained,
        "every generated number is used in the manuscript",
        f"{len(unexplained)} orphaned: {', '.join(unexplained)}",
    )
    staged = [n for n in orphans if n in PENDING_MACROS]
    if staged:
        result.note(
            f"{len(staged)} macro(s) staged for prose that does not exist yet: "
            + ", ".join(f"{n} ({PENDING_MACROS[n]})" for n in staged)
        )



#: ``\label`` and the reference commands that consume one.
_LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
_REF_RE = re.compile(r"\\(?:cref|Cref|ref|autoref|eqref)\*?\{([^}]*)\}")


def _labels_and_refs(paths: "list[Path]") -> "tuple[set[str], set[str]]":
    r"""Labels defined and labels referenced, with LaTeX comments stripped.

    Comments are stripped because a commented-out ``\cref`` is not a
    reference, and a migration that comments a block out rather than deleting
    it would otherwise read as still-referencing.
    """
    labels: set[str] = set()
    refs: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        text = re.sub(r"(?m)^[ \t]*%.*$", "", path.read_text(encoding="utf-8"))
        labels.update(_LABEL_RE.findall(text))
        for group in _REF_RE.findall(text):
            refs.update(name.strip() for name in group.split(",") if name.strip())
    return labels, refs



#: Numbers allowed to appear as literals in generated caption text, with the
#: reason each is not a measurement. Everything else must come from a macro.
#:
#: The list is deliberately tiny. A generous one would re-open the hole this
#: check exists to close: phase 30 found `28.0` sitting in the deployment
#: caption, computed inline from three-run medians, contradicting section
#: VI-RQ3 on the facing page, with every gate green.
CAPTION_LITERALS: dict[str, str] = {
    "2000": "the provider's configured delay -- a setting, not a measurement",
    "90": "a confidence level",
    "95": "a confidence level",
    "0": "a count of zero, or a bound of zero",
}

_CAPTION_RE = re.compile(
    r"footnotesize (.*?)\}\\\\", re.S)
_MACRO_CALL_RE = re.compile(r"\\[A-Za-z]+\{\}|\\[A-Za-z]+")
_CAPTION_NUM_RE = re.compile(r"(?<![A-Za-z0-9_.])(\d[\d.]*)")


def check_generated_captions_use_macros(result: Result, paper: Path) -> None:
    r"""A caption is a claim, and rule 3 says claims come from macros.

    **The defect this exists for.** ``paper_tables.py`` built the deployment
    table's caption with ``f"{tex(b3 - b0)}"`` -- 28.0 ms, computed inline from
    the three-run medians. It was never a ``
ewcommand``, so
    ``check_macros_are_used`` could not see it, the numbers gate could not see
    it, and when phase 26 retired that figure from every ``.tex`` and from the
    macro set, the caption kept printing it. The paper stated it in the built
    PDF, next to a section saying the decomposition "supports an ordering and
    not a partition", and every gate stayed green.

    So: every number in a generated file's caption prose must either be the
    value of some macro in ``numbers.tex`` or be named in
    ``CAPTION_LITERALS`` with a reason. Data cells are exempt -- producing
    numbers from a CSV is what a table is for, and the CSV is their provenance.
    """
    generated = paper / "generated"
    numbers = generated / "numbers.tex"
    if not numbers.is_file():
        result.check(False, "numbers.tex exists", f"missing {numbers}")
        return

    values = set()
    for raw in re.findall(r"\\newcommand\{\\[A-Za-z]+\}\{([^}]*)\}",
                          numbers.read_text(encoding="utf-8")):
        values.add(raw.replace("\\,", "").replace(",", "").strip())

    offenders: list[str] = []
    for path in sorted(generated.glob("table-*.tex")):
        text = path.read_text(encoding="utf-8")
        for caption in _CAPTION_RE.findall(text):
            # A thousands separator is typography, not two numbers.
            prose = caption.replace("\\,", "")
            prose = _MACRO_CALL_RE.sub(" ", prose)
            for number in _CAPTION_NUM_RE.findall(prose):
                clean = number.rstrip(".")
                if clean in values or clean in CAPTION_LITERALS:
                    continue
                offenders.append(f"{path.name}: {number}")

    result.check(
        not offenders,
        "every number in a generated caption comes from a macro",
        f"{len(offenders)} with nothing behind them: {', '.join(offenders)}",
    )


def check_cross_document_references(result: Result, paper: Path) -> None:
    r"""The paper and the supplementary are two documents, not one.

    ``supplementary.tex`` says so in its own header: it "cannot ``\cref``
    labels defined in main.tex", so references to the paper are spelled out by
    name. That convention is only worth anything if something enforces it.

    **The failure mode this exists for.** WS-9 moves sections out of the main
    text and into the supplementary. Move a block but leave its ``\cref`` in
    main and LaTeX says "undefined reference" -- already caught. *Copy* a block
    instead of moving it, and both documents define the label: LaTeX is silent
    in both, every existing gate passes, and a reader following the pointer in
    the main text lands on whichever copy went stale. Nothing in this file saw
    that before.
    """
    supplementary = paper / "supplementary.tex"
    if not supplementary.is_file():
        result.check(False, "supplementary.tex exists",
                     f"missing {supplementary}")
        return

    # A generated file belongs to whichever document \input s it. Phase 28
    # attributed all of them to the main text, which was true then and stopped
    # being true the moment WS-9 moved a generated table into the
    # supplementary: the label was defined in a file the supplementary inputs,
    # so the supplementary's own reference to it read as unresolved.
    main_sources = [paper / "main.tex"] + sorted(
        (paper / "sections").glob("*.tex"))
    supp_sources = [supplementary]

    def inputs(paths: "list[Path]") -> "set[str]":
        found: set[str] = set()
        for path in paths:
            if not path.is_file():
                continue
            text = re.sub(r"(?m)^[ \t]*%.*$", "",
                          path.read_text(encoding="utf-8"))
            found.update(re.findall(r"\\input\{generated/([A-Za-z0-9_-]+)\}",
                                    text))
        return found

    main_inputs = inputs(main_sources)
    supp_inputs = inputs(supp_sources)
    for generated in sorted((paper / "generated").glob("*.tex")):
        stem = generated.stem
        if stem in supp_inputs and stem not in main_inputs:
            supp_sources.append(generated)
        else:
            # Inputted by main, by both, or by neither. "By neither" stays with
            # main so an orphaned generated file still has its labels checked
            # somewhere rather than falling out of the census entirely.
            main_sources.append(generated)

    main_labels, main_refs = _labels_and_refs(main_sources)
    supp_labels, supp_refs = _labels_and_refs(supp_sources)

    dangling_main = sorted(main_refs - main_labels)
    result.check(
        not dangling_main,
        "every reference in the main text resolves inside the main text",
        f"{len(dangling_main)} unresolved: {', '.join(dangling_main)}",
    )

    dangling_supp = sorted(supp_refs - supp_labels)
    result.check(
        not dangling_supp,
        "every reference in the supplementary resolves inside the supplementary",
        f"{len(dangling_supp)} unresolved -- the supplementary cannot \\cref "
        f"into the paper and must name it instead: {', '.join(dangling_supp)}",
    )

    both = sorted(main_labels & supp_labels)
    result.check(
        not both,
        "no label is defined in both documents",
        f"{len(both)} defined twice -- a migration that copied rather than "
        f"moved: {', '.join(both)}",
    )

    orphan_supp = sorted(supp_labels - supp_refs - main_refs)
    if orphan_supp:
        result.note(
            f"{len(orphan_supp)} supplementary label(s) referenced by nothing; "
            "the main text points at the supplementary by name, so this is "
            f"expected rather than broken: {', '.join(orphan_supp)}"
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


#: DocInfo keys that must be present-but-empty in the anonymous PDF. A value
#: here is a name, a tool version, or a date, and all three are identifying.
_DOCINFO_KEYS = (b"Author", b"Title", b"Subject", b"Keywords", b"Creator", b"Producer")


def check_anonymous_build(result: Result, paper: Path) -> None:
    """WS-10 step 3, as a gate rather than as something someone remembers to do.

    `main-anon.pdf` sat three days behind section VIII while this script
    reported 19 passed, because nothing here ever looked at it. Two failures
    were possible and both are now checked: the artifact being stale, and the
    leak class that `pdftotext` and `pdfinfo` cannot see.

    **Every needle is derived, not hard-coded.** The build path comes from
    ``ROOT``; the byline comes from the public PDF's own title page. Writing the
    author's name into a public repository to check that it is absent would
    reintroduce, in this file, the leak the check exists to prevent.
    """
    anon = paper / "main-anon.pdf"
    if not anon.is_file():
        result.check(False, "anonymous build exists", f"missing {anon}")
        return

    fresh, reason = paper_provenance.verify(
        paper, paper_provenance.ANON_STAMP_NAME
    )
    result.check(fresh, "anonymous build is not stale", reason)

    raw = anon.read_bytes()

    # 1. Absolute build paths. pdfTeX writes /PTEX.FileName for every embedded
    #    PDF figure, recording the path it resolved -- which carries the
    #    repository name and resolves by search to the author's account.
    leaked = []
    if b"/PTEX.FileName" in raw:
        leaked.append("/PTEX.FileName present")
    for needle in (str(ROOT).encode(), ROOT.name.encode()):
        if needle in raw:
            leaked.append(f"build path {needle.decode(errors='replace')!r}")
    result.check(
        not leaked,
        "anonymous build leaks no absolute build path",
        "; ".join(leaked),
    )

    # 2. DocInfo present-but-empty, and no dates. The +05'00' offset on
    #    /CreationDate is a locality hint of the same class.
    # [^)]+ and not (.+?): pdfTeX writes the empty keys adjacently, as
    # "/Author()/Title()/Subject()", so a dot-matching group starting inside
    # /Author() runs past its own ")" and closes on /Title()'s -- reporting
    # every empty key as populated. Caught only because the first run of this
    # check failed on a PDF already verified clean by hand.
    dirty = [
        key.decode()
        for key in _DOCINFO_KEYS
        if re.search(rb"/" + key + rb"\s*\(([^)]+)\)", raw)
    ]
    if re.search(rb"/(Creation|Mod)Date\s*\(", raw):
        dirty.append("CreationDate/ModDate present")
    result.check(
        not dirty, "anonymous build DocInfo is clean", ", ".join(dirty)
    )

    # 3. The byline. Needs the text layer, which is compressed, so this is the
    #    one part that needs pdftotext. If it is absent the check FAILS rather
    #    than passing quietly: "I could not look" and "I looked and it is clean"
    #    must never render the same (paper_provenance's rule, applied here).
    public = paper / "main.pdf"
    if not shutil.which("pdftotext"):
        result.check(
            False,
            "anonymous build carries no byline",
            "pdftotext not installed; cannot verify -- failing closed",
        )
        return

    def first_page(path: Path) -> str:
        done = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", str(path), "-"],
            capture_output=True, text=True,
        )
        return done.stdout if done.returncode == 0 else ""

    anon_text = first_page(anon)
    byline = ""
    if public.is_file():
        lines = [line.strip() for line in first_page(public).splitlines()]
        lines = [line for line in lines if line]
        # The byline is the line after the last title line and before the
        # abstract -- located by structure, so no name appears in this file.
        for index, line in enumerate(lines):
            if line.startswith("Abstract") and index:
                byline = lines[index - 1]
                break

    # 4. The ORCID and the DOI. A Zenodo record names its depositor and an
    #    ORCID identifies a person as surely as a name does, so both get the
    #    byline's treatment. Derived from the PUBLIC pdf, never written here:
    #    this file must contain no identifying string of its own.
    def full_text(path: Path) -> str:
        done = subprocess.run(
            ["pdftotext", str(path), "-"], capture_output=True, text=True,
        )
        return done.stdout if done.returncode == 0 else ""

    anon_full = full_text(anon)
    identifying: list[str] = []
    if public.is_file():
        public_full = full_text(public)
        identifying += re.findall(r"\b\d{4}-\d{4}-\d{4}-\d{3}[0-9X]\b",
                                  public_full)
        # Only the ARCHIVE's DOI, not every DOI on the page: a cited
        # reference's DOI is present in both builds by design and is not an
        # identifying string. Read from main.tex so this file still contains
        # no identifier of its own.
        main_tex = paper / "main.tex"
        if main_tex.is_file():
            declared = re.search(
                r"\\newcommand\{\\archivedoi\}\{([^}]*)\}",
                main_tex.read_text(encoding="utf-8"),
            )
            if declared and declared.group(1) != "PENDING":
                identifying.append(declared.group(1))

    problems = []
    if "Anonymous" not in anon_text:
        problems.append("no 'Anonymous' byline on page 1")
    if byline and byline in anon_text:
        problems.append("public byline appears verbatim in the anonymous build")
    for token in sorted(set(identifying)):
        if token in anon_full:
            problems.append(f"identifier {token!r} survives the anonymous build")
    if public.is_file() and not identifying:
        problems.append(
            "no ORCID or DOI found in the public build, so the anonymous "
            "check has nothing to prove -- a suppression test that passes "
            "because the string was never emitted proves nothing"
        )

    if not byline:
        problems.append("could not locate the public byline to compare against")
    result.check(
        not problems, "anonymous build carries no byline", "; ".join(problems)
    )


def check_supplementary(result: Result, paper: Path) -> None:
    """The supplementary is a submitted artifact, so it is gated like one.

    It is a separate PDF rather than an appendix because IEEE Computer Society
    guidance treats appendices as supplemental material to be submitted
    separately, and excludes supplemental material from the page count. A
    separate PDF is a second surface, and the reason this function exists is
    that ``main-anon.pdf`` sat three days stale while the checker reported 19
    passed -- because nothing read it. A second document nothing reads would be
    the same failure with a new name.

    What is checked here: both artifacts exist; each is fresh against **its
    own** stamp; the anonymous one carries no absolute build path, no populated
    DocInfo, the anonymous byline, and not the main paper's public byline; and
    a supplementary that cites must declare a bibliography.

    What is NOT checked here, stated so nobody assumes otherwise: the
    supplementary's prose is not read against the results, because it holds no
    generated numbers. The moment a macro from ``generated/numbers.tex`` is used
    in it, ``check_macros_are_used`` must be widened to scan it -- that function
    reads ``main.tex`` and ``sections/*.tex`` only, and would silently report an
    orphan as used, or a used macro as orphaned, the day the supplementary
    carries one.
    """
    supp = paper / "supplementary.pdf"
    anon = paper / "supplementary-anon.pdf"
    for path, label in ((supp, "supplementary"), (anon, "supplementary-anon")):
        result.check(path.is_file(), f"{label}.pdf exists", f"missing {path}")
    if not (supp.is_file() and anon.is_file()):
        return

    for stamp, label in (
        (paper_provenance.SUPP_STAMP_NAME, "supplementary"),
        (paper_provenance.SUPP_ANON_STAMP_NAME, "supplementary-anon"),
    ):
        fresh, reason = paper_provenance.verify(paper, stamp)
        result.check(fresh, f"{label}.pdf is not stale", reason)

    raw = anon.read_bytes()

    leaked = []
    if b"/PTEX.FileName" in raw:
        leaked.append("/PTEX.FileName present")
    for needle in (str(ROOT).encode(), ROOT.name.encode()):
        if needle in raw:
            leaked.append(f"build path {needle.decode(errors='replace')!r}")
    result.check(
        not leaked,
        "supplementary-anon leaks no absolute build path",
        "; ".join(leaked),
    )

    dirty = [
        key.decode()
        for key in _DOCINFO_KEYS
        if re.search(rb"/" + key + rb"\s*\(([^)]+)\)", raw)
    ]
    if re.search(rb"/(Creation|Mod)Date\s*\(", raw):
        dirty.append("CreationDate/ModDate present")
    result.check(
        not dirty, "supplementary-anon DocInfo is clean", ", ".join(dirty)
    )

    # The byline. Failing closed when pdftotext is absent, for the same reason
    # the main check does: "I could not look" must not render as "it is clean".
    if not shutil.which("pdftotext"):
        result.check(
            False,
            "supplementary-anon carries no public byline",
            "pdftotext not installed; cannot verify -- failing closed",
        )
        return

    def first_page(path: Path) -> str:
        done = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", str(path), "-"],
            capture_output=True, text=True,
        )
        return done.stdout if done.returncode == 0 else ""

    anon_text = first_page(anon)
    # Derived from the public MAIN paper, never written here: putting the
    # author's name in this file to check for its absence would reintroduce the
    # leak the check exists to prevent.
    byline = ""
    public_main = paper / "main.pdf"
    if public_main.is_file():
        lines = [line.strip() for line in first_page(public_main).splitlines()]
        lines = [line for line in lines if line]
        for index, line in enumerate(lines):
            if line.startswith("Abstract") and index:
                byline = lines[index - 1]
                break

    problems = []
    if "Anonymous" not in anon_text:
        problems.append("no 'Anonymous' byline on page 1")
    if byline and byline in anon_text:
        problems.append("the paper's public byline appears in the supplementary")
    if not byline:
        problems.append("could not locate the public byline to compare against")
    result.check(
        not problems,
        "supplementary-anon carries no public byline",
        "; ".join(problems),
    )

    # The pairing build_paper.sh's skipped-bibtex branch depends on. It skips
    # bibtex when the source declares no bibliography, which is correct for an
    # empty container and wrong the moment content citing anything is moved in.
    source = (paper / "supplementary.tex").read_text(encoding="utf-8")
    stripped = "\n".join(
        line.split("%", 1)[0] for line in source.splitlines()
    )
    cites = bool(re.search(r"\\cite[a-z]*\{", stripped))
    has_bib = bool(re.search(r"\\bibliography\{", stripped))
    result.check(
        not cites or has_bib,
        "supplementary that cites declares a bibliography",
        "supplementary.tex uses \\cite but declares no \\bibliography, so "
        "build_paper.sh skips bibtex and the citations render as [?]",
    )


def check_bibliography(result: Result, build_dir: Path) -> None:
    """A blank bibliography compiles clean. Check the artifact, not the log."""
    bbl = build_dir / "main.bbl"
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

    blg = build_dir / "main.blg"
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


def check_undefined_references(result: Result, build_dir: Path) -> None:
    log = build_dir / "main.log"
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
        "--build-dir",
        type=Path,
        help=(
            "directory containing a freshly staged main.bbl/main.blg/main.log; "
            "defaults to --paper for direct and legacy invocations"
        ),
    )
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
    parser.add_argument(
        "--writeloss-cell",
        type=Path,
        default=ROOT / "reports" / "raw" / "ws4-writeloss-s1-2026-09-07",
    )
    parser.add_argument(
        "--b5-session",
        type=Path,
        default=ROOT / "reports" / "raw" / "ws6-b5-s1-2026-09-08-attempt3",
    )
    # WS-5's four roots. These default to the committed collections on
    # purpose: the gate regenerates with EXACTLY the inputs the generator is
    # run with, and that identity is the only reason the gate is worth
    # anything. A default that differed from the documented invocation would
    # make the gate pass on a numbers.tex nobody can reproduce.
    parser.add_argument(
        "--ws5-everysec",
        type=Path,
        default=WS5_ROOT / "t1-p0-everysec" / "analysis",
    )
    parser.add_argument(
        "--ws5-p30", type=Path, default=WS5_ROOT / "t2-p30" / "analysis",
    )
    parser.add_argument(
        "--ws5-keying", type=Path, default=WS5_ROOT / "t2-keying" / "analysis",
    )
    parser.add_argument(
        "--fsync-always-45",
        type=Path,
        default=(ROOT / "experiments" / "results"
                 / "fsync-always-2026-09-14" / "analysis"),
    )
    arguments = parser.parse_args()
    build_dir = arguments.build_dir or arguments.paper

    print("=" * 70)
    print("check_paper_numbers.py -- the manuscript against its results")
    print("=" * 70)
    print(f"paper          {arguments.paper}")
    print(f"build artifacts {build_dir}")
    print(f"analysis       {arguments.analysis}")
    print(f"fsync analysis {arguments.fsync_analysis}")
    print(f"flakey results {arguments.flakey}")
    print(f"b5 session     {arguments.b5_session}")
    print(f"write-loss cell {arguments.writeloss_cell}")
    print()

    result = Result()
    check_per_cell_has_regime(result, arguments.analysis)
    check_generated_tables(
        result,
        arguments.paper,
        arguments.analysis,
        arguments.fsync_analysis,
        arguments.flakey,
        arguments.b5_session,
        arguments.writeloss_cell,
        arguments.ws5_everysec,
        arguments.ws5_p30,
        arguments.ws5_keying,
        arguments.fsync_always_45,
    )
    check_generated_captions_use_macros(result, arguments.paper)
    check_cross_document_references(result, arguments.paper)
    check_no_banned_source(result, arguments.paper)
    check_macros_are_used(result, arguments.paper)
    check_state_machine(result, arguments.paper)
    # Always against paper/, never against --build-dir: the anonymous PDF is
    # never staged there, and the artifact that ships is the promoted one.
    check_anonymous_build(result, arguments.paper)
    # The supplementary ships alongside the paper, so it is gated alongside it.
    check_supplementary(result, arguments.paper)

    # B21 item 3. The two checks below read main.bbl/main.blg/main.log. When
    # --build-dir was not given they come from paper/, where build_paper.sh
    # promotes them -- so without a provenance check this run reports on
    # whichever build last happened to promote, and says nothing about which.
    # That is how a "17 passed, 1 failed" baseline computed from three-week-old
    # artifacts was quoted as a control through two phases.
    #
    # An explicit --build-dir pointing somewhere else is the build staging its
    # own output and checking it before promotion; that is the one caller whose
    # artifacts are fresh by construction.
    if build_dir.resolve() == arguments.paper.resolve():
        fresh, reason = paper_provenance.verify(arguments.paper)
        result.check(fresh, "build artifacts match current sources", reason)
    else:
        fresh = True

    if fresh:
        check_bibliography(result, build_dir)
        check_undefined_references(result, build_dir)
    else:
        # Report the exclusion rather than omitting it silently: B29a exists
        # because a tool that skips a class and says nothing is indistinguishable
        # from one that found nothing.
        print(
            "  SKIP  2 checks not run (bibliography, undefined references): "
            "artifacts cannot be shown to match the sources"
        )

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
