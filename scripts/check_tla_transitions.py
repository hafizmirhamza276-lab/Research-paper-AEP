#!/usr/bin/env python3
"""Hold ``formal/AEP.tla`` to the implementation it claims to model.

Three checks, each of which exists because the corresponding claim would
otherwise be a claim nothing verifies.

**1. The transition table.**  ``formal/AEP.tla`` transcribes
``LEGAL_INTENT_TRANSITIONS`` (``aep_core/core/intents.py:65-96``).  A
transcription is a copy, and a copy drifts.  ``scripts/gen_state_machine.py``
already closed this hole for the paper's state-machine figure, for exactly the
stated reason: *"A hand-drawn figure is a claim about the protocol that nothing
checks, and this repository's audit history is largely a history of documents
that claimed properties the code did not have."*  A TLA+ model is that same
kind of claim, with the added hazard that a model checker will happily verify
properties of the wrong state machine and report success.

**2. The status alphabet.**  The short TLA+ names (``ATF``, ``FU``, ...) must
map onto the real ``IntentStatus`` values, or check 1 compares two sets that
merely look alike.

**3. The oracle separation** (``--check-oracle``).  ``effect`` is the model's
god view: whether the endpoint really applied the mutation.  The paper's whole
position is that AEP cannot see this, so no protocol action may branch on it.
That property is easy to state, easy to believe, and easy to break by accident
while editing the model -- and if it breaks, the model proves something
stronger than the implementation can do, which is the one failure mode a
formal artifact must not have.  So it is enforced textually: the identifier
must not occur in any definition belonging to a protocol participant.

Usage:
    python scripts/check_tla_transitions.py            # checks 1 and 2
    python scripts/check_tla_transitions.py --check-oracle   # all three
    python scripts/check_tla_transitions.py --all
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aep_core.core.intents import (  # noqa: E402
    LEGAL_INTENT_TRANSITIONS,
    NONE_STATE,
    IntentStatus,
)

SPEC = ROOT / "formal" / "AEP.tla"

#: The model's god-view variable: what really happened at the endpoint.
ORACLE = "effect"

#: Definitions that belong to a protocol participant -- a worker, the recovery
#: service, or a guard either of them evaluates.  None of these may read the
#: oracle, because none of their real counterparts can.
#:
#: ``Transmit`` is absent deliberately: it is the endpoint applying (or not
#: applying) the mutation, so it is the one action that must write the oracle.
#: ``AllowedEvidence`` and ``AllowedReadback`` are absent for the same reason --
#: they constrain what the ENDPOINT may say, and an endpoint does know what it
#: did.  What matters is that the protocol's own decisions (``RunnerTarget``,
#: ``ClassifiedTarget``, every CAS guard) are functions of the reported
#: evidence alone.
PROTOCOL_DEFS = (
    "AcquireLease",
    "CreateIntent",
    "CreationFenceOpen",
    "Barrier",
    "BarrierFails",
    "Authorize",
    "PreflightOk",
    "Preflight",
    "PreflightRejects",
    "Receive",
    "RunnerTarget",
    "Resolve",
    "ResolveRejected",
    "InFlightAt",
    "RecoveryClaim",
    "ClassifiedTarget",
    "RecoveryReadback",
    "RecoveryEscalateNoQuery",
    "OperatorResolve",
)


def read_spec() -> str:
    if not SPEC.exists():
        raise SystemExit(f"FAIL: {SPEC} does not exist")
    return SPEC.read_text(encoding="utf-8")


def strip_comments(text: str) -> str:
    """Remove TLA+ block and line comments.

    Comments quote the code they transcribe, so they are full of the very
    identifiers these checks look for.  Leaving them in would make check 3
    fail on its own documentation.
    """
    text = re.sub(r"\(\*.*?\*\)", " ", text, flags=re.DOTALL)
    return re.sub(r"\\\*[^\n]*", " ", text)


def definition(body: str, name: str) -> str:
    """Return the body of the TLA+ definition ``name``, comments removed.

    A definition begins at column 0 with ``Name ==`` or ``Name(args) ==`` and
    runs until the next column-0 definition or separator line.
    """
    pattern = re.compile(
        r"^%s(?:\([^)]*\))?\s*==" % re.escape(name), re.MULTILINE
    )
    match = pattern.search(body)
    if match is None:
        raise SystemExit(f"FAIL: {SPEC.name} has no definition named {name!r}")
    rest = body[match.end():]
    end = re.search(r"^(?:[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==|=====|-----)",
                    rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def spec_status_names(body: str) -> dict[str, str]:
    """Map each short TLA+ status identifier to the string it stands for."""
    names = {}
    for ident in ("NONE_STATE", "ATF", "FU", "FC", "FAC", "PA"):
        match = re.search(
            r'^%s\s*==\s*"([A-Z_]+)"' % ident, body, re.MULTILINE
        )
        if match is None:
            raise SystemExit(f"FAIL: {SPEC.name} does not define {ident}")
        names[ident] = match.group(1)
    return names


def check_statuses(names: dict[str, str]) -> list[str]:
    expected = {
        "NONE_STATE": NONE_STATE,
        "ATF": IntentStatus.ABOUT_TO_FIRE.value,
        "FU": IntentStatus.FIRED_UNCONFIRMED.value,
        "FC": IntentStatus.FIRED_CONFIRMED.value,
        "FAC": IntentStatus.FAILED_CONFIRMED.value,
        "PA": IntentStatus.PERMANENTLY_AMBIGUOUS.value,
    }
    problems = []
    for ident, want in expected.items():
        if names[ident] != want:
            problems.append(
                f"{ident} is {names[ident]!r} in {SPEC.name} "
                f"but {want!r} in aep_core.core.intents"
            )
    spec_alphabet = set(names.values())
    code_alphabet = {NONE_STATE} | {s.value for s in IntentStatus}
    for extra in sorted(spec_alphabet - code_alphabet):
        problems.append(f"{SPEC.name} names a status the code does not have: {extra!r}")
    for missing in sorted(code_alphabet - spec_alphabet):
        problems.append(f"{SPEC.name} does not name the code's status {missing!r}")
    return problems


def spec_transitions(body: str, names: dict[str, str]) -> set[tuple[str, str]]:
    block = definition(body, "LegalTransitions")
    pairs = re.findall(r"<<\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*>>",
                       block)
    if not pairs:
        raise SystemExit(f"FAIL: LegalTransitions in {SPEC.name} names no edges")
    edges = set()
    for old, new in pairs:
        for ident in (old, new):
            if ident not in names:
                raise SystemExit(
                    f"FAIL: LegalTransitions uses {ident!r}, which is not a "
                    f"status identifier defined in {SPEC.name}"
                )
        edges.add((names[old], names[new]))
    return edges


def check_transitions(edges: set[tuple[str, str]]) -> list[str]:
    code = {(old, new) for old, new in LEGAL_INTENT_TRANSITIONS}
    problems = []
    for extra in sorted(edges - code):
        problems.append(
            f"{SPEC.name} allows {extra[0]} -> {extra[1]}, which "
            f"LEGAL_INTENT_TRANSITIONS does not"
        )
    for missing in sorted(code - edges):
        problems.append(
            f"LEGAL_INTENT_TRANSITIONS allows {missing[0]} -> {missing[1]}, "
            f"which {SPEC.name} does not"
        )
    return problems


def check_oracle(body: str) -> list[str]:
    problems = []
    word = re.compile(r"\b%s\b" % re.escape(ORACLE))
    for name in PROTOCOL_DEFS:
        block = definition(body, name)
        # An UNCHANGED clause names the oracle only to say it does not move,
        # which is the opposite of reading it.
        without_unchanged = re.sub(
            r"UNCHANGED\s*<<[^>]*>>|UNCHANGED\s+\w+", " ", block
        )
        if word.search(without_unchanged):
            problems.append(
                f"protocol definition {name} reads the oracle {ORACLE!r}; "
                f"no protocol participant can observe whether the endpoint "
                f"applied the mutation"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-oracle", action="store_true",
                        help="also check that no protocol action reads the god view")
    parser.add_argument("--all", action="store_true", help="run every check")
    args = parser.parse_args()
    want_oracle = args.check_oracle or args.all

    raw = read_spec()
    body = strip_comments(raw)

    names = spec_status_names(body)
    problems = check_statuses(names)
    edges = spec_transitions(body, names)
    problems += check_transitions(edges)
    if want_oracle:
        problems += check_oracle(body)

    if problems:
        print(f"FAIL: {SPEC.name} does not match the implementation")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(
        f"OK: {SPEC.name} matches aep_core.core.intents -- "
        f"{len(edges)} transitions, {len(names)} statuses"
        + (f", {len(PROTOCOL_DEFS)} protocol definitions free of the oracle"
           if want_oracle else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
