"""Emit the paper's state-machine figure from the code's transition table.

`PAPER_ROADMAP.md` §5's Phase 4 prompt: *"Generate the protocol state-machine
figure with TikZ from the transition table in aep_core/core/intents.py."*

The point of generating rather than drawing is drift. A hand-drawn figure is a
claim about the protocol that nothing checks, and this repository's audit
history is largely a history of documents that claimed properties the code did
not have. Here the edge set is imported, so a transition added to or removed
from ``LEGAL_INTENT_TRANSITIONS`` changes the figure or fails the build --
``scripts/check_paper_numbers.py`` re-runs this and diffs the result.

Layout is fixed by hand (positions, bend angles, label anchors); only the
*edges* come from the code. If an edge appears that has no declared position,
this script exits non-zero rather than dropping it silently.

**Label placement is the whole difficulty, and it was got wrong once.** Until
2026-09-16 every edge carried ``node[midway,sloped,above]``. On a vertical edge
``sloped`` rotates the text to vertical and ``midway`` puts it on the path, so
"CAS + barrier" was printed down the middle of the NONE and ABOUT-TO-FIRE
boxes, "anything else" down ABOUT-TO-FIRE and FIRED-UNCONFIRMED, and "budget
spent" down FIRED-UNCONFIRMED. Three of the six node boxes were unreadable in
the built PDF, and the figure had been shipped that way since Phase 4. Every
label now carries its own anchor: vertical edges take upright text offset to
one side, the four diagonals take ``sloped`` where there is empty canvas to
slope into, and no label is placed midway on a path that runs through a node.

**Widths.** ``columnwidth`` in IEEEtran 10pt/journal/compsoc is 252.945pt,
which is 8.89cm. The long status names are set on two lines inside their nodes
so that the terminal row is 5.1cm wide instead of 7.9cm, which is what used to
push FAILED-CONFIRMED past the column edge.

Usage:
    python scripts/gen_state_machine.py > paper/figures/state-machine.tex
    python scripts/gen_state_machine.py --check paper/figures/state-machine.tex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aep_core.core.intents import (  # noqa: E402
    LEGAL_INTENT_TRANSITIONS,
    NONE_STATE,
    IntentStatus,
)

#: Node identifier and printed label per status.
#:
#: **The printed label is the status alphabet the implementation exports**,
#: with underscores set as hyphens and nothing shortened. It used to read
#: "ambiguous" for PERMANENTLY_AMBIGUOUS -- the one name the manuscript never
#: uses, since sec:p2 and sec:p3 both say \textsc{permanently-ambiguous}. The
#: figure was what had drifted, not the prose. Long names are split across two
#: lines rather than abbreviated: the node stays narrow and the word stays the
#: code's word.
NODES: dict[str, tuple[str, str]] = {
    NONE_STATE: ("none", r"\textsc{none}"),
    IntentStatus.ABOUT_TO_FIRE.value: ("atf", r"\textsc{about-to-fire}"),
    IntentStatus.FIRED_UNCONFIRMED.value: (
        "fu", r"\textsc{fired-}\\\textsc{unconfirmed}",
    ),
    IntentStatus.FIRED_CONFIRMED.value: (
        "fc", r"\textsc{fired-}\\\textsc{confirmed}",
    ),
    IntentStatus.FAILED_CONFIRMED.value: (
        "flc", r"\textsc{failed-}\\\textsc{confirmed}",
    ),
    IntentStatus.PERMANENTLY_AMBIGUOUS.value: (
        "pa", r"\textsc{permanently-}\\\textsc{ambiguous}",
    ),
}

#: ``at`` positions in TikZ centimetres. A vertical spine carries the automated
#: path -- NONE, ABOUT-TO-FIRE, FIRED-UNCONFIRMED -- and the three terminal
#: states sit on one row beneath it, so every automated edge runs downward and
#: a reader never has to follow a line back up.
POSITIONS: dict[str, tuple[float, float]] = {
    "none": (0.0, 0.0),
    "atf": (0.0, -1.5),
    "fu": (0.0, -3.3),
    "fc": (-3.08, -5.6),
    "pa": (0.0, -5.6),
    "flc": (3.08, -5.6),
}

#: Per-edge: (path options, label, label-node options, operator?).
#:
#: ``operator`` marks the two edges only a human can take. They are drawn
#: dashed, so the figure shows at a glance that nothing automated leaves
#: PERMANENTLY_AMBIGUOUS.
#:
#: The fourth column is the label's own anchor, and it is load-bearing.
#: ``right=2pt`` on a vertical edge keeps upright text clear of the spine;
#: ``sloped`` is used only on the four diagonals; ``pos`` slides a label to
#: where its neighbours have splayed apart. "budget spent" sits at 0.72 rather
#: than midway because at that height the two diagonals leaving
#: FIRED-UNCONFIRMED are about 3.7cm apart and at the midpoint about 2.2cm,
#: which is narrower than the label.
EDGES: dict[tuple[str, str], tuple[str, str, str, bool]] = {
    (NONE_STATE, IntentStatus.ABOUT_TO_FIRE.value): (
        "", r"CAS $+$ barrier", "midway,right=2pt", False,
    ),
    (IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FIRED_CONFIRMED.value): (
        "out=180,in=90,out looseness=1.5,in looseness=0.45",
        r"declared success", "pos=0.46,sloped,above=1pt", False,
    ),
    (IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FAILED_CONFIRMED.value): (
        "out=0,in=90,out looseness=1.5,in looseness=0.45",
        r"declared failure", "pos=0.46,sloped,above=1pt", False,
    ),
    (IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FIRED_UNCONFIRMED.value): (
        "", r"anything else", "midway,right=2pt", False,
    ),
    (
        IntentStatus.FIRED_UNCONFIRMED.value,
        IntentStatus.FIRED_UNCONFIRMED.value,
    ): (
        "out=200,in=160,looseness=2.8",
        r"unknown;\\budget left", "midway,left=2pt,align=right", False,
    ),
    (IntentStatus.FIRED_UNCONFIRMED.value, IntentStatus.FIRED_CONFIRMED.value): (
        "out=225,in=45",
        r"read-back applied", "pos=0.63,sloped,above=2pt", False,
    ),
    (IntentStatus.FIRED_UNCONFIRMED.value, IntentStatus.FAILED_CONFIRMED.value): (
        "out=315,in=135",
        r"authoritative absence", "pos=0.58,sloped,above=2pt", False,
    ),
    (
        IntentStatus.FIRED_UNCONFIRMED.value,
        IntentStatus.PERMANENTLY_AMBIGUOUS.value,
    ): (
        "", r"budget spent", "pos=0.72,right=2pt", False,
    ),
    (
        IntentStatus.PERMANENTLY_AMBIGUOUS.value,
        IntentStatus.FIRED_CONFIRMED.value,
    ): (
        "dashed,out=170,in=10", "", "", True,
    ),
    (
        IntentStatus.PERMANENTLY_AMBIGUOUS.value,
        IntentStatus.FAILED_CONFIRMED.value,
    ): (
        "dashed,out=10,in=170", "", "", True,
    ),
}


def terminal_states() -> set[str]:
    """States that no *automated* edge leaves.

    Derived, not listed. Section 4.3 names three -- FIRED_CONFIRMED,
    FAILED_CONFIRMED and PERMANENTLY_AMBIGUOUS -- and this recomputes the same
    three from the imported transition set plus the operator annotation, so an
    edge added to the code moves the thick borders with it instead of leaving
    the figure asserting a terminality the code no longer has.
    """
    leaves_automated = {
        source
        for (source, _target), (_o, _l, _lo, operator) in EDGES.items()
        if not operator
    }
    return {status for status in NODES if status not in leaves_automated}


def render() -> str:
    missing = sorted(set(LEGAL_INTENT_TRANSITIONS) - set(EDGES))
    extra = sorted(set(EDGES) - set(LEGAL_INTENT_TRANSITIONS))
    if missing or extra:
        raise SystemExit(
            "the transition table and the figure's edge list disagree.\n"
            f"  in the code but not drawn: {missing}\n"
            f"  drawn but not in the code: {extra}\n"
            "Edit EDGES in scripts/gen_state_machine.py -- do not edit the "
            "generated .tex."
        )

    terminal = terminal_states()

    out: list[str] = []
    out.append("% GENERATED by scripts/gen_state_machine.py -- do not edit.")
    out.append("% Edge set imported from aep_core.core.intents")
    out.append("% .LEGAL_INTENT_TRANSITIONS, so this figure cannot drift from")
    out.append("% the transition table the Lua script enforces.")
    out.append(
        f"% {len(LEGAL_INTENT_TRANSITIONS)} edges, {len(NODES)} states, "
        f"{len(terminal)} terminal for automated reconciliation."
    )
    out.append(r"\begin{tikzpicture}[")
    out.append(r"    every node/.style={font=\scriptsize},")
    out.append(
        r"    state/.style={draw,rounded corners=2pt,inner xsep=4pt,"
        r"inner ysep=3pt,align=center,fill=black!3},"
    )
    out.append(r"    terminal/.style={state,fill=black!8,very thick},")
    out.append(
        r"    elabel/.style={font=\scriptsize,inner sep=1pt,align=center},"
    )
    out.append(
        r"    to/.style={-{Stealth[length=4pt]},shorten >=1pt,shorten <=1pt},"
    )
    out.append(r"  ]")

    for status, (ident, label) in NODES.items():
        x, y = POSITIONS[ident]
        style = "terminal" if status in terminal else "state"
        out.append(f"  \\node[{style}] ({ident}) at ({x},{y}) {{{label}}};")

    out.append("")
    for (source, target), (options, label, label_opts, _op) in EDGES.items():
        src = NODES[source][0]
        dst = NODES[target][0]
        opt = f"to,{options}" if options else "to"
        text = f" node[elabel,{label_opts}] {{{label}}}" if label else ""
        out.append(f"  \\draw[{opt}] ({src}) edge{text} ({dst});")

    out.append(r"\end{tikzpicture}")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        metavar="PATH",
        help="compare against an existing file instead of writing to stdout",
    )
    arguments = parser.parse_args()
    rendered = render()

    if arguments.check:
        path = Path(arguments.check)
        if not path.is_file():
            print(f"MISSING: {path}", file=sys.stderr)
            return 1
        if path.read_text(encoding="utf-8") != rendered:
            print(
                f"STALE: {path} does not match the current transition table.\n"
                f"Regenerate: python scripts/gen_state_machine.py > {path}",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {path} matches aep_core.core.intents")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
