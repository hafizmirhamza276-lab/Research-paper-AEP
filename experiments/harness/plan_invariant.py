r"""The agent workload's repeat invariant, checked rather than trusted.

``docs/33-agent-workload.md`` §2.9:

    **Invariant.** The planner may emit a tool call whose fingerprint equals one
    it has already emitted **only** in response to a step whose declared outcome
    was ``PERMANENTLY_AMBIGUOUS``.

**Why it is load-bearing, and not merely tidy.** Two executions sharing a
fingerprint is what plan drift *is*, and it is also what breaks the published
duplicate metric (§2.2). The invariant is what keeps those two facts from
colliding: a repeat can only arise where an ambiguity was declared, so only in a
system with ``can_declare_ambiguity=True``, so only where the attribution repair
of §2.4 applies. For the five systems that cannot declare ambiguity, fingerprints
stay distinct exactly as they are today and their duplicate numbers keep their
current meaning.

A violation therefore does not mean the planner behaved oddly. It means a
number in the paper has quietly changed population, which is why this returns
violations rather than logging a warning.

**This module is not agent code.** It is a checker over a recorded plan, and it
is deliberately independent of how that plan was produced: it takes the
fingerprint and the declared outcome of each step and nothing else, so it can be
applied to a scripted planner, a model-backed one, or a replayed transcript.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

#: The declared reconciliation outcome that licenses a repeat. Spelled as the
#: string the run log carries rather than imported from
#: ``aep_core.core.connector_contract``: this checker reads recorded artifacts,
#: and coupling it to the enum would make it unusable against an archived run
#: collected under a different version of that module.
PERMANENTLY_AMBIGUOUS = "PERMANENTLY_AMBIGUOUS"


@dataclass(frozen=True)
class PlannedStep:
    """One tool call as the recorded plan describes it.

    ``outcome`` is the protocol's *declared* reconciliation outcome for this
    step, which is what the planner was allowed to see (§1.4). It is ``None``
    for a step whose outcome is not yet known at the point the plan is checked.
    """

    index: int
    fingerprint: str
    outcome: str | None = None


@dataclass(frozen=True)
class Violation:
    """A repeat the invariant does not license."""

    index: int
    fingerprint: str
    first_index: int
    reason: str

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"step {self.index} repeats the fingerprint first emitted at step "
            f"{self.first_index}: {self.reason}"
        )


def find_violations(steps: Sequence[PlannedStep] | Iterable[PlannedStep]) -> tuple[
    Violation, ...
]:
    """Every repeat in ``steps`` that no prior declared ambiguity licenses.

    A repeat is licensed iff **some earlier step carrying the same fingerprint**
    was declared ``PERMANENTLY_AMBIGUOUS``. Ambiguity declared on a *different*
    mutation licenses nothing: the planner may re-plan the action whose outcome
    it cannot determine, not an unrelated one.
    """
    violations: list[Violation] = []
    #: fingerprint -> (index of first emission, was any prior one ambiguous)
    seen: dict[str, tuple[int, bool]] = {}

    for step in steps:
        previous = seen.get(step.fingerprint)
        if previous is None:
            seen[step.fingerprint] = (step.index, step.outcome == PERMANENTLY_AMBIGUOUS)
            continue

        first_index, licensed = previous
        if not licensed:
            violations.append(
                Violation(
                    index=step.index,
                    fingerprint=step.fingerprint,
                    first_index=first_index,
                    reason=(
                        "no earlier step with this fingerprint was declared "
                        f"{PERMANENTLY_AMBIGUOUS}"
                    ),
                )
            )
        # A repeat updates the licence: if THIS emission was itself declared
        # ambiguous, a further repeat is licensed by it.
        seen[step.fingerprint] = (
            first_index,
            licensed or step.outcome == PERMANENTLY_AMBIGUOUS,
        )

    return tuple(violations)


def assert_holds(steps: Sequence[PlannedStep]) -> None:
    """Raise if the plan violates the invariant.

    The harness calls this rather than checking a flag, because a workload that
    silently violates it produces a duplicate number whose population nobody
    can reconstruct afterwards.
    """
    violations = find_violations(steps)
    if violations:
        detail = "; ".join(str(violation) for violation in violations)
        raise AssertionError(
            f"agent plan violates the docs/33 §2.9 repeat invariant: {detail}"
        )
