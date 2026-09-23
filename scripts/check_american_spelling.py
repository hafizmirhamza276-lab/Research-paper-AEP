#!/usr/bin/env python3
r"""Fail if a British spelling reaches the RENDERED manuscript.

IEEE house style is American English. The manuscript was written in British
``-ise`` throughout and converted in one mechanical pass; this check is what
stops it drifting back, one edit at a time, in a document nobody reads end to
end in one sitting.

**This reads the PDFs, not the LaTeX**, for the reason
``check_no_repo_paths.py`` gives: a word in a caption, a footnote, a table
cell, a run-in heading and a generated file reaches the reader by five
different routes, and only the extracted text sees all of them at once.

**Provenance comments are unaffected**, because a ``%`` comment is not in the
PDF. The spelling pass left every comment byte-identical on purpose, so the
evidence trail still reads as it was written.

What is exempt, and why
-----------------------
* **The references section.** Cited titles are other people's words. A paper
  called *"Analysing …"* is spelled the way its authors spelled it, and
  "correcting" a title in a bibliography is a misquotation. Everything from the
  ``REFERENCES`` heading onward is skipped.
* **Identifiers**, listed in :data:`EXEMPT`. ``analyze.py`` is a filename and
  ``authorization`` is this protocol's term for the Redis-visible record that
  the dispatch guard is consumed to write. Both already happen to be American,
  and both are listed anyway so the reason is recorded rather than
  rediscovered.
* **``capitalise``** is a ``cleveref`` package OPTION in ``main.tex`` and
  ``supplementary.tex``. It is not a word, it never renders, and it must not be
  "fixed" -- doing so breaks the build.
* **Words that are ``-ise`` in both Englishes**: ``exercise``, ``comprise``,
  ``promise``, ``supervise`` and the rest of a closed list. These are not
  ``-ize`` words in American English either, and flagging them would train a
  reader to ignore the check.

Usage
-----
    python scripts/check_american_spelling.py              # all four builds
    python scripts/check_american_spelling.py paper/main.pdf
    python scripts/check_american_spelling.py --text FILE  # extracted text
    python scripts/check_american_spelling.py --selftest   # known-positive
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPER = REPO / "paper"

BUILDS = ["main.pdf", "main-anon.pdf", "supplementary.pdf",
          "supplementary-anon.pdf"]

#: British -> American, for the forms this manuscript actually used. Explicit
#: rather than generative, so the message can name the replacement.
EXPLICIT = {
    "acknowledgement": "acknowledgment",
    "behaviour": "behavior",
    "favour": "favor",
    "honour": "honor",
    "colour": "color",
    "labour": "labor",
    "rigour": "rigor",
    "neighbour": "neighbor",
    "modelled": "modeled",
    "modelling": "modeling",
    "labelled": "labeled",
    "labelling": "labeling",
    "cancelled": "canceled",
    "cancelling": "canceling",
    "signalling": "signaling",
    "travelling": "traveling",
    "totalled": "totaled",
    "enrolment": "enrollment",
    "fulfil": "fulfill",
    "instil": "instill",
    "skilful": "skillful",
    "judgement": "judgment",
    "analogue": "analog",
    "artefact": "artifact",
    "programme": "program",
    "centre": "center",
    "fibre": "fiber",
    "metre": "meter",
    "defence": "defense",
    "offence": "offense",
    "pretence": "pretense",
    "licence": "license",
    "practise": "practice",
    "whilst": "while",
    "amongst": "among",
    "learnt": "learned",
    "spelt": "spelled",
    "grey": "gray",
    "sceptical": "skeptical",
    "sulphur": "sulfur",
    "storey": "story",
    "manoeuvre": "maneuver",
    "ageing": "aging",
}

#: Bases that end in ``-ise`` in American English too. Flagging these would
#: make the check noise. Inflections are generated from them below.
BOTH_ENGLISHES = """
    advertise advise apprise arise chastise circumcise comprise compromise
    demise despise devise disguise enfranchise enterprise excise exercise
    franchise improvise incise merchandise premise prise promise revise rise
    supervise surmise surprise televise treatise precise concise paradise
    noise poise praise raise cruise bruise guise anise expertise mortise
    tortoise valise appraise excise wise likewise otherwise clockwise
    mise anywise
""".split()

#: Identifiers that reach the rendered text and must never be flagged. Each
#: carries the reason, so a later reader does not have to re-derive it.
EXEMPT = {
    "analyze.py": "a filename, and already American",
    "authorization": "this protocol's term for the Redis-visible record",
    "authorize": "the verb form of the protocol's own term",
    "authorized": "the verb form of the protocol's own term",
    "capitalise": "a cleveref package option, not a word; never rendered",
    "Idempotency-Key": "an HTTP header name, spelled as the vendors spell it",
    "analysis": "the noun is the same in both Englishes",
    "analyses": "ambiguous noun plural; the verb is checked as -yse below",
    "basis": "not an -ise word",
    "emphasis": "not an -ise word",
    "hypothesis": "not an -ise word",
    "synthesis": "not an -ise word",
    "parenthesis": "not an -ise word",
    "crisis": "not an -ise word",
    "thesis": "not an -ise word",
    "diagnosis": "not an -ise word",
}


def _allowed_ise_words() -> set[str]:
    """Every inflection of a base that is ``-ise`` in American English too."""
    out: set[str] = set()
    for base in BOTH_ENGLISHES:
        stem = base[:-1] if base.endswith("e") else base
        out.update({base, base + "s", base + "d", stem + "ing", stem + "es",
                    stem + "ed"})
    return out


ALLOWED_ISE = _allowed_ise_words()

#: A prefix does not change which English a word belongs to. "imprecise" is
#: "precise" with a negation and is American; "unrecognised" is "recognised"
#: with one and is not, because "recognise" is British in the first place. So
#: the prefix is stripped and the remainder decides. Found by the check firing
#: on "imprecise" in §VI and the supplementary.
NEUTRAL_PREFIXES = ("un", "im", "in", "dis", "non", "re", "mis", "over",
                    "under", "pre", "co")


def is_allowed_ise(word: str) -> bool:
    if word in ALLOWED_ISE:
        return True
    for prefix in NEUTRAL_PREFIXES:
        if word.startswith(prefix) and word[len(prefix):] in ALLOWED_ISE:
            return True
    return False

#: Generative families, for words the explicit table does not know about.
ISE = re.compile(r"\b[A-Za-z]+is(?:e|es|ed|ing|ation|ations)\b")
YSE = re.compile(r"\b[A-Za-z]+ys(?:e|es|ed|ing)\b")

#: Everything from this heading onward is somebody else's words.
REFERENCES = re.compile(r"^\s*REFERENCES\s*$", re.M | re.I)


def explicit_form(word: str) -> str | None:
    """The American form from :data:`EXPLICIT`, prefix included if there is
    one. "remodelled" is "modelled" with a prefix and is just as British."""
    if word in EXPLICIT:
        return EXPLICIT[word]
    for prefix in NEUTRAL_PREFIXES:
        rest = word[len(prefix):]
        if word.startswith(prefix) and rest in EXPLICIT:
            return prefix + EXPLICIT[rest]
    return None


def americanise(word: str) -> str:
    """The American form, for the failure message."""
    low = word.lower()
    explicit = explicit_form(low)
    if explicit:
        return explicit
    if low.endswith(("ise", "ises", "ised", "ising", "isation", "isations")):
        return re.sub(r"is(e|es|ed|ing|ation|ations)$", r"iz\1", low)
    if low.endswith(("yse", "yses", "ysed", "ysing")):
        return re.sub(r"ys(e|es|ed|ing)$", r"yz\1", low)
    return "?"


def scan(text: str) -> list[tuple[int, str, str, str]]:
    """Return (line number, word, suggestion, line) for each British form."""
    cut = REFERENCES.search(text)
    if cut:
        text = text[:cut.start()]

    hits: list[tuple[int, str, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if any(term in line for term in EXEMPT):
            # Only the exempt term is protected, not the whole line: blank it
            # out and keep checking what remains.
            stripped = line
            for term in EXEMPT:
                stripped = stripped.replace(term, " ")
        else:
            stripped = line

        candidates = set()
        for word in re.findall(r"\b[A-Za-z][A-Za-z-]*\b", stripped):
            low = word.lower()
            if low in EXEMPT or is_allowed_ise(low):
                continue
            if explicit_form(low):
                candidates.add(word)
            elif ISE.fullmatch(low) or YSE.fullmatch(low):
                candidates.add(word)
        for word in sorted(candidates):
            hits.append((number, word, americanise(word), line.strip()))
    return hits


def extract(pdf: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise SystemExit("pdftotext not found; this check reads the built PDFs")
    done = subprocess.run(["pdftotext", str(pdf), "-"],
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit(f"pdftotext failed on {pdf}")
    return done.stdout


def selftest() -> int:
    """Known-positive, plus the two exemptions that matter."""
    failures = 0

    positive = "The system modelled the behaviour and we analysed it.\n"
    hits = scan(positive)
    found = {w.lower() for _, w, _, _ in hits}
    for want in ("modelled", "behaviour", "analysed"):
        if want in found:
            print(f"  PASS  known-positive: {want!r} is caught")
        else:
            print(f"  FAIL  known-positive: {want!r} was NOT caught")
            failures += 1

    negative = ("We exercise the endpoint, comprise a premise, and the\n"
                "authorization record is written by analyze.py. The bound is\n"
                "imprecise rather than wrong, and nothing here is unwise.\n")
    hits = scan(negative)
    if hits:
        print(f"  FAIL  known-negative: flagged {[w for _, w, _, _ in hits]}")
        failures += 1
    else:
        print("  PASS  known-negative: -ise words common to both Englishes, "
              "their prefixed forms, and the exempt identifiers, are not "
              "flagged")

    # The prefix rule must not become a blanket pardon.
    still_caught = {w.lower() for _, w, _, _ in
                    scan("an unrecognised capability, disorganised and "
                         "remodelled\n")}
    for want in ("unrecognised", "disorganised", "remodelled"):
        if want in still_caught:
            print(f"  PASS  prefixed British form {want!r} is still caught")
        else:
            print(f"  FAIL  prefixed British form {want!r} slipped through")
            failures += 1

    reference = "REFERENCES\n[1] A. Author, \"Analysing behaviour,\" 2026.\n"
    if scan(reference):
        print("  FAIL  references section is not exempt")
        failures += 1
    else:
        print("  PASS  the references section is exempt, so a cited title "
              "keeps its own spelling")

    if failures:
        print(f"---- selftest: {failures} check(s) did not behave as stated")
        return 1
    print("---- selftest: 6 of 6 confirmed -- it fires, it does not "
          "over-fire, and it leaves cited titles alone")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--text", type=Path,
                        help="check an already-extracted text file")
    parser.add_argument("--selftest", action="store_true",
                        help="prove the check fires, and does not over-fire")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.text:
        targets = [(args.text, scan(args.text.read_text(encoding="utf-8")))]
    else:
        pdfs = args.pdfs or [PAPER / name for name in BUILDS]
        targets = []
        for pdf in pdfs:
            if not pdf.is_file():
                print(f"  FAIL  {pdf} does not exist; build it first")
                return 1
            targets.append((pdf, scan(extract(pdf))))

    total = 0
    for target, hits in targets:
        if not hits:
            print(f"  PASS  {target.name} carries no British spelling")
            continue
        total += len(hits)
        for number, word, suggestion, line in hits:
            print(f"  FAIL  {target.name} line {number}: "
                  f"{word!r} -> {suggestion!r}")
            print(f"        {line[:110]}")

    if total:
        print(f"---- {total} British spelling(s) in rendered text")
        print("     IEEE house style is American English. If the word is an "
              "identifier or a cited title, add it to EXEMPT with the reason.")
        return 1
    print(f"---- {len(targets)} build(s) clean, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
