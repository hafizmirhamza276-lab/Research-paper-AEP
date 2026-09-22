#!/usr/bin/env python3
r"""Measure the manuscript's prose against ``docs/37-prose-style.md``.

**Non-gating, by design.** It reports; it never fails a build. Prose quality is
a judgement, and a threshold on any number here would be gamed by the next
edit rather than met. What the numbers are for is comparison: this section
against that one, and a section before a rewrite against the same section
after.

What it measures, and what each number is a proxy for
-----------------------------------------------------
* **em-dashes** (``---``): the habit ``docs/37`` §1 exists to break. Reported
  both as a count and per page-equivalent, since a target of "about one per
  page" cannot be checked against a raw count. En dashes (``--``) are counted
  separately and are not a fault: number ranges use them.
* **words, sentences, mean and spread of sentence length**: ``docs/37`` §5 asks
  for varied sentence length. A low standard deviation is the measurable
  signature of the fault, not the fault itself.
* **corrective constructions**: ``not X but Y``, ``X, not Y``, ``rather than``
  used for contrast. ``docs/37`` §2.
* **flagged vocabulary**: the words ``docs/37`` §6 asks us to avoid.
* **emphasis**: ``\emph`` and ``\textbf`` runs. ``docs/37`` §7.
* **signposting**: ``docs/37`` §10 allows one per section.
* **hedging** and **first person**: ``docs/37`` §8 and §9 want these present,
  so a count of zero is the thing to look at.
* **short paragraph-final sentences**: the closest mechanical proxy for the
  punchline ending ``docs/37`` §3 prohibits. It is a weak proxy and is labelled
  as one --- a short final sentence is often just a short sentence.

Every count is over *prose*. LaTeX comments are stripped first, so provenance
comments are never measured, and command names are removed so that
``\texttt{redis-kill-preack}`` contributes its argument and not its wrapper.

Usage
-----
    python scripts/prose_metrics.py                     # the whole manuscript
    python scripts/prose_metrics.py paper/sections/01-introduction.tex
    python scripts/prose_metrics.py --json              # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPER = REPO / "paper"

#: Words of body prose per page, at this document's layout. Used only to turn
#: an em-dash count into the per-page figure docs/37 §1 states its target in.
#: Derived, not measured: the nine section files hold about 15 800 words of
#: prose and the body runs to 24 pages, of which roughly 3 are tables, figures
#: and references. Re-derive if the layout changes.
WORDS_PER_PAGE = 750


def default_targets() -> list[Path]:
    return sorted((PAPER / "sections").glob("*.tex")) + [
        PAPER / "main.tex", PAPER / "supplementary.tex"
    ]


# -- getting to the prose ---------------------------------------------------

#: Environments whose contents are not prose and would distort every count.
_SKIP_ENVIRONMENTS = (
    "table", "table\\*", "tabular", "figure", "figure\\*", "lstlisting",
    "verbatim", "equation", "align", "algorithmic", "algorithm",
)


def to_prose(source: str) -> str:
    """LaTeX source reduced to the words a reader reads."""
    # Comments first. Provenance comments are the project's discipline and
    # measuring them as prose would punish it.
    text = re.sub(r"(?<!\\)%.*", "", source)

    for environment in _SKIP_ENVIRONMENTS:
        text = re.sub(
            rf"\\begin\{{{environment}\}}.*?\\end\{{{environment}\}}",
            " ", text, flags=re.DOTALL,
        )

    # Sectioning commands: drop the command, keep nothing. A heading is not a
    # sentence and would skew sentence length.
    text = re.sub(
        r"\\(?:sub)*section\*?\{[^{}]*\}|\\paragraph\*?\{[^{}]*\}", " ", text
    )

    # Reference-like commands become a placeholder token, so that a sentence
    # built around one still parses as a sentence.
    text = re.sub(r"\\(?:cref|Cref|ref|eqref|autoref)\{[^{}]*\}", "REF", text)
    text = re.sub(r"\\cite[a-z]*\{[^{}]*\}", "CITE", text)
    text = re.sub(r"\\label\{[^{}]*\}", " ", text)

    # Content-carrying wrappers: keep the argument.
    for _ in range(4):
        text = re.sub(
            r"\\(?:emph|textbf|textit|texttt|textsc|text|mbox|underline)"
            r"\{([^{}]*)\}", r"\1", text,
        )

    # Generated macros resolve to numbers; one token each is the right weight.
    text = re.sub(r"\\[A-Z][A-Za-z]*\{\}", "NUM", text)

    text = re.sub(r"\$[^$]*\$", "NUM", text)
    text = re.sub(r"\\begin\{[^{}]*\}|\\end\{[^{}]*\}", " ", text)
    # A list item is its own prose unit. Joined with a space, consecutive
    # items that do not end in terminal punctuation fuse into one enormous
    # "sentence" -- §I's contributions produced a 116-word reading that was an
    # artefact of the itemize and not of the writing. A paragraph break makes
    # each item count as itself, for sentence length and for paragraphs alike.
    text = re.sub(r"\\item(?:\[[^\]]*\])?", "\n\n", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = text.replace("~", " ").replace("\\", " ")
    text = re.sub(r"[{}]", " ", text)
    return text


def sentences(prose: str) -> list[str]:
    """Split on terminal punctuation, leaving common abbreviations alone."""
    guarded = prose
    for abbreviation in ("e.g.", "i.e.", "cf.", "vs.", "et al.", "Fig.",
                         "Sec.", "Eq.", "Ref.", "No.", "approx."):
        guarded = guarded.replace(abbreviation, abbreviation.replace(".", "\x00"))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"])", guarded)
    out = []
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part.replace("\x00", ".")).strip()
        if len(cleaned.split()) >= 3:
            out.append(cleaned)
    return out


def paragraphs(prose: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", prose) if len(p.split()) >= 20]


# -- the patterns docs/37 names ---------------------------------------------

CORRECTIVE = {
    "not X but Y": r"\bnot\s+(?:\w+\s+){0,6}?but\b",
    "X, not Y": r",\s+not\s+\w+",
    "rather than": r"\brather than\b",
    "instead of": r"\binstead of\b",
    "is not A, it is B": r"\bis not\b[^.]{0,60}\bit is\b",
}

FLAGGED_WORDS = [
    "load-bearing", "honest", "honestly", "honesty", "discipline",
    "disciplined", "crucially", "crucial", "notably", "it is worth noting",
    "worth noting", "the point is", "the whole point", "precisely",
    "deliberately", "quietly", "silently", "genuinely", "simply put",
    "in other words", "that is to say", "tellingly", "strikingly",
    "importantly", "critically", "fundamentally", "essentially",
]

SIGNPOSTS = [
    "in this section", "we now", "as we will see", "as we shall see",
    "in what follows", "recall that", "the rest of this section",
    "we begin by", "we turn to", "having established", "before we",
    "this section", "below we", "we first",
]

HEDGES = [
    "we observe", "this suggests", "suggests that", "in our setting",
    "appears to", "may ", "might ", "we did not", "we cannot", "consistent with",
    "we interpret", "our data", "we have no", "we do not claim",
]


def count_phrases(prose: str, phrases: list[str]) -> dict[str, int]:
    low = prose.lower()
    found = {}
    for phrase in phrases:
        pattern = (
            rf"\b{re.escape(phrase.strip())}\b" if phrase == phrase.strip()
            else re.escape(phrase)
        )
        n = len(re.findall(pattern, low))
        if n:
            found[phrase.strip()] = n
    return found


# -- measurement ------------------------------------------------------------

def measure(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    prose = to_prose(source)

    # Em dashes come from the source: to_prose does not touch them, but
    # counting before stripping keeps the number honest about what is written.
    em_dashes = len(re.findall(r"(?<!-)---(?!-)", re.sub(r"(?<!\\)%.*", "", source)))
    en_dashes = len(re.findall(r"(?<!-)--(?!-)", re.sub(r"(?<!\\)%.*", "", source)))

    sents = sentences(prose)
    lengths = [len(s.split()) for s in sents]
    words = sum(lengths)

    paras = paragraphs(prose)
    short_finals = 0
    for para in paras:
        para_sents = sentences(para)
        if para_sents and len(para_sents[-1].split()) <= 9:
            short_finals += 1

    corrective = {
        name: len(re.findall(pattern, prose, re.IGNORECASE))
        for name, pattern in CORRECTIVE.items()
    }

    body = re.sub(r"(?<!\\)%.*", "", source)
    return {
        "file": path.name,
        "words": words,
        "sentences": len(sents),
        "page_equivalents": round(words / WORDS_PER_PAGE, 2) if words else 0.0,
        "em_dashes": em_dashes,
        "em_dashes_per_page": (
            round(em_dashes / (words / WORDS_PER_PAGE), 2) if words else 0.0
        ),
        "en_dashes": en_dashes,
        "sentence_len_mean": round(statistics.mean(lengths), 1) if lengths else 0,
        "sentence_len_sd": (
            round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else 0
        ),
        "sentence_len_min": min(lengths) if lengths else 0,
        "sentence_len_max": max(lengths) if lengths else 0,
        "sentence_len_median": (
            round(statistics.median(lengths), 1) if lengths else 0
        ),
        "corrective": corrective,
        "corrective_total": sum(corrective.values()),
        "flagged_words": count_phrases(prose, FLAGGED_WORDS),
        "flagged_words_total": sum(count_phrases(prose, FLAGGED_WORDS).values()),
        "signposts": count_phrases(prose, SIGNPOSTS),
        "signposts_total": sum(count_phrases(prose, SIGNPOSTS).values()),
        "hedges_total": sum(count_phrases(prose, HEDGES).values()),
        "first_person_we": len(re.findall(r"\bwe\b", prose, re.IGNORECASE)),
        "emph": len(re.findall(r"\\emph\{", body)),
        "textbf": len(re.findall(r"\\textbf\{", body)),
        "paragraphs": len(paras),
        "short_paragraph_finals": short_finals,
    }


def print_report(rows: list[dict]) -> None:
    print("prose metrics -- NON-GATING, reports only. See docs/37-prose-style.md.")
    print(f"page-equivalents assume {WORDS_PER_PAGE} words of prose per page.\n")

    header = (
        f"{'file':<26}{'words':>7}{'sent':>6}{'pg':>6}{'em':>5}{'em/pg':>7}"
        f"{'en':>5}{'len':>7}{'sd':>6}{'min':>5}{'max':>5}"
        f"{'corr':>6}{'flag':>6}{'sign':>6}{'hedge':>7}{'we':>5}"
        f"{'emph':>6}{'bold':>6}{'para':>6}{'punch':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['file']:<26}{r['words']:>7}{r['sentences']:>6}"
            f"{r['page_equivalents']:>6}{r['em_dashes']:>5}"
            f"{r['em_dashes_per_page']:>7}{r['en_dashes']:>5}"
            f"{r['sentence_len_mean']:>7}{r['sentence_len_sd']:>6}"
            f"{r['sentence_len_min']:>5}{r['sentence_len_max']:>5}"
            f"{r['corrective_total']:>6}{r['flagged_words_total']:>6}"
            f"{r['signposts_total']:>6}{r['hedges_total']:>7}"
            f"{r['first_person_we']:>5}{r['emph']:>6}{r['textbf']:>6}"
            f"{r['paragraphs']:>6}{r['short_paragraph_finals']:>7}"
        )

    total_words = sum(r["words"] for r in rows)
    total_em = sum(r["em_dashes"] for r in rows)
    print("-" * len(header))
    print(
        f"{'TOTAL':<26}{total_words:>7}"
        f"{sum(r['sentences'] for r in rows):>6}"
        f"{round(total_words / WORDS_PER_PAGE, 1):>6}{total_em:>5}"
        f"{round(total_em / (total_words / WORDS_PER_PAGE), 2):>7}"
    )

    print("\ndetail, where non-zero:")
    for r in rows:
        bits = []
        if r["corrective"]:
            live = {k: v for k, v in r["corrective"].items() if v}
            if live:
                bits.append("corrective " + ", ".join(
                    f"{k}={v}" for k, v in sorted(live.items(), key=lambda x: -x[1])
                ))
        if r["flagged_words"]:
            bits.append("words " + ", ".join(
                f"{k}={v}" for k, v in
                sorted(r["flagged_words"].items(), key=lambda x: -x[1])[:8]
            ))
        if r["signposts"]:
            bits.append("signposts " + ", ".join(
                f"{k}={v}" for k, v in
                sorted(r["signposts"].items(), key=lambda x: -x[1])[:5]
            ))
        if bits:
            print(f"  {r['file']}")
            for bit in bits:
                print(f"      {bit}")

    print("\n'punch' counts paragraphs ending in a sentence of <=9 words. It is a")
    print("weak proxy for docs/37 §3 and should be read by eye, not by number.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    targets = args.files or default_targets()
    rows = [measure(p if p.is_absolute() else REPO / p) for p in targets]

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print_report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
