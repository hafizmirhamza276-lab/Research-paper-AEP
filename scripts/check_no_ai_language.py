#!/usr/bin/env python3
r"""Fail if AI-tool or coding-agent language reaches the RENDERED manuscript.

The author's supervisor ruled on 2026-09-25 that the article carries no
acknowledgment section and no reference to AI tools or coding agents anywhere
in it, and that the disclosure is submitted as a separate report. The material
that report needs is preserved in
``reports/ai-use-disclosure-source-2026-09-25.md``; this gate is what keeps the
decision from quietly reversing itself. A sentence, a caption, a table cell or
a generated file could reintroduce it without anyone editing the block that was
removed.

**This reads the PDFs, not the LaTeX**, for the reason
``check_no_repo_paths.py`` does: a string reaches the page from a caption, a
footnote, a table cell and ``paper/generated/`` by four different routes, and
only the extracted text sees all of them at once. A ``%`` comment is not in the
PDF, so the source may keep its provenance comments.

What is deliberately NOT flagged
--------------------------------
**"model" on its own.** It is one of this manuscript's most-used ordinary
words and every use is legitimate. ``LEGITIMATE_MODEL_SENSES`` below lists the
senses, and ``--selftest`` asserts that a real sentence from each one passes.
Only collocations that can only be about an AI system are flagged, such as
*model identifier* or *language model*.

**"agent" on its own.** An autonomous agent calling a non-idempotent endpoint
is this paper's motivating example, named in the abstract, the index terms,
§I and §II, and it is subject matter. Only collocations such as *coding agent*
are flagged.

**Titles of cited works.** ``EXEMPT_CITATIONS`` carries the four reference-list
titles that contain *LLM*, *agent* or *agentic*. Changing a cited title would
be a citation error, so they are exempted by exact string rather than by
pattern. A new citation whose title trips a pattern has to be added here
deliberately, which is the point.

Usage
-----
    python scripts/check_no_ai_language.py                 # all four builds
    python scripts/check_no_ai_language.py paper/main.pdf
    python scripts/check_no_ai_language.py --text FILE     # extracted text
    python scripts/check_no_ai_language.py --selftest      # rule 13 evidence
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

#: Vendors and products. None of these has a non-AI reading in this manuscript.
#: "Opus", "Sonnet" and "Haiku" are model names here; they are also ordinary
#: English words, and if one ever appears in its ordinary sense this gate
#: should fire and a human should decide, which is cheaper than missing a
#: model name.
VENDORS = [
    "anthropic", "claude", "openai", "codex", "copilot", "chatgpt",
    "gemini", "llama", "mistral", "opus", "sonnet", "haiku",
]

#: Words that are about generative AI whatever surrounds them.
AI_WORDS = [
    r"artificial\s+intelligence",
    r"generative\s+ai",
    r"\bAI\b",
    r"\bLLMs?\b",
    r"large\s+language\s+model",
    r"language\s+model",
    r"foundation\s+model",
    r"frontier\s+model",
    r"\bsubagents?\b",
    r"\bprompt\s+engineering\b",
]

#: Collocations. The head word is legitimate on its own and these are not.
COLLOCATIONS = [
    r"coding\s+(?:and\s+drafting\s+)?assistants?",
    r"drafting\s+assistants?",
    r"\bAI\s+assistants?",
    r"\bassistants?\b",
    r"per-assistant\s+configuration",
    r"coding\s+agents?",
    r"\bAI\s+agents?",
    r"agentic\s+(?:assistant|coding|tool)",
    r"model\s+identifiers?",
    r"model\s+that\s+signed",
    r"model\s+each\s+\w+\s+ran",
    r"commit\s+trailers?",
    r"\bCo-Authored-By\b",
    r"phase\s+prompts?",
    r"prompt\s+files?",
    r"committed\s+prompts?",
    r"machine-generated\s+(?:text|code|prose)",
]

PATTERNS: list[tuple[str, str]] = (
    [("vendor or model name", r"(?<![\w-])(?:" + "|".join(VENDORS) + r")(?![\w-])")]
    + [("generative-AI term", pattern) for pattern in AI_WORDS]
    + [("AI-tool collocation", pattern) for pattern in COLLOCATIONS]
)

#: Titles of cited works. Exempted by exact substring, lowercased, because a
#: cited title is the authors' own and altering it would misquote them.
EXEMPT_CITATIONS = [
    "verified tool calls improve llm agent reliability",
    "logact: enabling agentic reliability via shared logs",
    "sovereign execution broker: enforcing certificate-bound authority "
    "in agentic control planes",
    "acrfence: preventing semantic rollback attacks in agent "
    "checkpoint-restore",
]

#: The senses of "model" this manuscript uses, all legitimate, none flagged.
#: ``--selftest`` asserts that a real sentence from each passes. Recorded as
#: prose rather than as a pattern: the gate's job is to explain why it is
#: silent about the word a reader would most expect it to catch.
LEGITIMATE_MODEL_SENSES = [
    ("the TLA+ specification",
     "We specify the protocol in TLA+ and check it with TLC. "
     "The model is transcribed from the implementation."),
    ("model checking as an activity",
     "Seven of the nine configurations that must fail; "
     "the properties are model-checked and the Python is not."),
    ("the fault model",
     "The model is crash-and-delay, not Byzantine."),
    ("our model of a durable-execution engine",
     "B4 is our model of a durable-execution engine, and no rate here "
     "is the engine's."),
    ("the endpoint model",
     "The endpoint is modeled as Section 3 describes it, and this is "
     "the modeling decision the result rests on."),
    ("a statistical model",
     "1.74 h of run time by the planner's own model."),
]

#: Sentences that must NOT fire, beyond the model senses: "agent" as this
#: paper's motivating example, and "acknowledgment" in its durability sense.
LEGITIMATE_OTHER = [
    ("agent as motivating example",
     "A caller that crashes around such a call (an autonomous agent, a "
     "workflow engine) has no safe option."),
    ("agent in the index terms",
     "Fault tolerance, non-idempotent APIs, idempotence, distributed "
     "coordination, autonomous agents."),
    ("agent deployment as subject matter",
     "It is a scripted caller, not an agent. The traces show what the "
     "endpoint does to a caller that crashes."),
    ("durability acknowledgment",
     "AEP's barrier withholds dispatch until the store acknowledges the "
     "intent durable, so the protocol is only as strong as that "
     "acknowledgment."),
    ("agent execution reliability as related work",
     "Agent execution reliability: three contemporaneous systems overlap "
     "substantially and delimit the claim."),
]

#: Lines that must fire, one per pattern family. This is the known-positive:
#: a gate that has never been shown to catch what it exists for is decoration
#: (docs/26 section 3 rule 13).
KNOWN_POSITIVES = [
    "The author used Anthropic's Claude and OpenAI's Codex as coding and "
    "drafting assistants throughout this work.",
    "The author used generative AI assistants under review.",
    "No AI system is an author.",
    "The exact model identifiers are not listed here.",
    "the commit trailers name the model that signed each commit",
    "the per-assistant configuration files committed beside them",
    "The phase prompts issued from Phase 8 onward are committed.",
    "produced with the help of a large language model",
    "each subagent ran a different model",
    "the work was done by a coding agent",
]


def extract_text(pdf: Path) -> str:
    """The PDF's text, via pdftotext."""
    if shutil.which("pdftotext") is None:
        raise RuntimeError(
            "pdftotext not found; it ships with poppler-utils and the paper "
            "build already requires a TeX installation"
        )
    result = subprocess.run(
        ["pdftotext", "-q", str(pdf), "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {pdf}: {result.stderr}")
    return result.stdout


def _exempt_spans(line: str) -> list[tuple[int, int]]:
    """Character ranges belonging to the title of a cited work."""
    lowered = line.lower()
    spans = []
    for title in EXEMPT_CITATIONS:
        start = lowered.find(title)
        while start != -1:
            spans.append((start, start + len(title)))
            start = lowered.find(title, start + 1)
    return spans


def findings(text: str) -> list[tuple[int, str, str, str]]:
    """(line number, kind, matched text, the line) for each hit."""
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        spans = _exempt_spans(line)
        for kind, pattern in PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                if any(s <= match.start() < e for s, e in spans):
                    continue
                out.append((number, kind, match.group(0), line.strip()))
    return out


def check(pdf: Path) -> list[tuple[int, str, str, str]]:
    return findings(extract_text(pdf))


def selftest() -> int:
    """Show the gate firing on what it exists for, and silent on what it does not."""
    failures = 0

    print("known-positive: each must be caught")
    for sentence in KNOWN_POSITIVES:
        hits = findings(sentence)
        if hits:
            print(f"  PASS  caught {hits[0][2]!r}")
        else:
            print(f"  FAIL  missed: {sentence[:72]}")
            failures += 1

    print()
    print("legitimate uses of 'model': each must pass")
    for sense, sentence in LEGITIMATE_MODEL_SENSES:
        hits = findings(sentence)
        if hits:
            print(f"  FAIL  {sense}: false positive {hits[0][2]!r}")
            failures += 1
        else:
            print(f"  PASS  {sense}")

    print()
    print("other legitimate uses: each must pass")
    for sense, sentence in LEGITIMATE_OTHER:
        hits = findings(sentence)
        if hits:
            print(f"  FAIL  {sense}: false positive {hits[0][2]!r}")
            failures += 1
        else:
            print(f"  PASS  {sense}")

    print()
    print("cited titles: each must be exempt")
    citations = [
        '[38] I. K. Mansoor, A. Phadke, and P. Rana, "Verified tool calls '
        'improve LLM agent reliability under non-atomic failures," CoRR, 2026.',
        '[39] M. Balakrishnan et al., "LogAct: Enabling agentic reliability '
        'via shared logs," CoRR, 2026.',
        '[41] Y. Zheng et al., "ACRFence: Preventing semantic rollback '
        'attacks in agent checkpoint-restore," CoRR, 2026.',
    ]
    for entry in citations:
        hits = findings(entry)
        if hits:
            print(f"  FAIL  cited title flagged: {hits[0][2]!r}")
            failures += 1
        else:
            print(f"  PASS  {entry[:46]}...")

    total = (len(KNOWN_POSITIVES) + len(LEGITIMATE_MODEL_SENSES)
             + len(LEGITIMATE_OTHER) + len(citations))
    print()
    if failures:
        print(f"selftest: {total - failures} of {total} -- {failures} FAILED")
        return 1
    print(f"selftest: {total} of {total} confirmed -- it fires, it does not "
          f"over-fire, and it leaves cited titles alone")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--text", type=Path,
                        help="check an already-extracted text file")
    parser.add_argument("--selftest", action="store_true",
                        help="show the gate firing on its own leak")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    total = 0
    if args.text:
        targets = [(args.text, findings(args.text.read_text(encoding="utf-8")))]
    else:
        pdfs = args.pdfs or [PAPER / name for name in BUILDS]
        targets = []
        for pdf in pdfs:
            if not pdf.is_file():
                print(f"  FAIL  {pdf} does not exist; build it first")
                total += 1
                continue
            targets.append((pdf, check(pdf)))

    for target, hits in targets:
        name = target.name
        if not hits:
            print(f"  PASS  {name} carries no AI-tool language")
            continue
        total += len(hits)
        for number, kind, text, line in hits:
            print(f"  FAIL  {name} line {number}: {kind} {text!r}")
            print(f"        {line[:110]}")

    if total:
        print(f"---- {total} occurrence(s) of AI-tool language in rendered text")
        print("     The disclosure ships as a separate report; see")
        print("     reports/ai-use-disclosure-source-2026-09-25.md.")
        return 1
    print(f"---- {len(targets)} build(s) clean, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
