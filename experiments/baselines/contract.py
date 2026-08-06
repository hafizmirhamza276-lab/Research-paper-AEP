"""What a "system under test" is, and what each one claims about itself.

PAPER_ROADMAP.md section 3.3 lists six systems. They are compared on one
workload, through one connector, against one ground-truth oracle, and they
differ in exactly the respects the table below records. Everything the harness
does differently for a baseline is read from a :class:`SystemDescriptor`, so a
reader can check "B1 has a lease and no intent ledger" against a data structure
instead of against prose -- and ``tests/test_contract.py`` checks the
descriptors against the implementations.

Two design decisions in here are *modelling* decisions, not implementation
details, and both change numbers. They are stated at the top because a reviewer
must be able to find them.

**1. What a supervisor does with a crashed execution.** After a worker dies
mid-execution, a framework has to decide whether to run that step again. With
no durable pre-dispatch record there is no third option: the supervisor either
re-executes (and may duplicate a non-idempotent effect) or drops it (and may
lose one). It cannot reconcile, because nothing was written down before the
call. B0, B1, B2 and B4 therefore re-execute -- that is what "retry-on-timeout
(what most agent frameworks do today)" means once a process can die -- and B3
and AEP-full do not, because they have an intent record and a recovery service
that can classify it. :attr:`SystemDescriptor.resume_policy` is what the runner
reads, it is echoed into every run log, and it is overridable per run so the
opposite choice can be measured rather than argued about.

**2. The client reference.** AEP mints a stable request fingerprint *before*
dispatch and sends it, which is what lets it find its own past effect under
``CALLER_REFERENCE`` read-back. B0, B1 and B2 have no pre-dispatch record to
hold such an identifier across a process death, and a naive caller does not
invent one, so they send none. This is not a handicap imposed on the baselines:
it is the discipline whose absence defines them. Its consequence -- that they
could not reconcile even if they tried -- is a result, and
``docs/24-readback-keying.md`` is where the keying question is argued.

**Outcome classes.** Each system records what it thinks happened in its own
vocabulary. The metrics need one. :class:`OutcomeClass` is that vocabulary, and
the distinction that carries the paper is between ``DECLARED_AMBIGUOUS`` -- the
system says it does not know and escalates -- and ``UNVERIFIED_FAILURE`` -- the
system wrote down "failed" without evidence that nothing was applied. Both are
"the call did not visibly succeed". Only the first is *detectable*, which is
the entire claim of the protocol under test.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class SystemId(str, Enum):
    """The systems PAPER_ROADMAP.md section 3.3 puts in one table."""

    B0_NAIVE_RETRY = "B0_NAIVE_RETRY"
    B1_LEASE_ONLY = "B1_LEASE_ONLY"
    B2_CAS_ONLY = "B2_CAS_ONLY"
    B3_INTENT_NO_BARRIER = "B3_INTENT_NO_BARRIER"
    B4_DURABLE_WORKFLOW = "B4_DURABLE_WORKFLOW"
    AEP_FULL = "AEP_FULL"


class OutcomeClass(str, Enum):
    """What a system's own durable record says, in one shared vocabulary."""

    #: The system asserts the effect happened, on evidence.
    CONFIRMED_APPLIED = "CONFIRMED_APPLIED"
    #: The system asserts the effect definitively did not happen, on evidence
    #: (here: a 4xx refusal, which the provider issues before applying).
    CONFIRMED_NOT_APPLIED = "CONFIRMED_NOT_APPLIED"
    #: The system declares that it does not know, and escalates. The only
    #: class that counts as "flagged" for the headline duplicate metric.
    DECLARED_AMBIGUOUS = "DECLARED_AMBIGUOUS"
    #: The system wrote "failed" with no evidence that nothing was applied.
    #: Indistinguishable from CONFIRMED_NOT_APPLIED to an operator reading the
    #: system's own record, which is exactly why it is counted separately here.
    UNVERIFIED_FAILURE = "UNVERIFIED_FAILURE"
    #: The system has no durable record of this execution at all.
    NO_RECORD = "NO_RECORD"
    #: A record exists and cannot be read. Never silently merged with the
    #: others: an unreadable record is a different failure from an absent one.
    UNREADABLE = "UNREADABLE"


#: Outcome classes in which the system has declared it does not know. The
#: headline "undetected duplicate rate" counts duplicates on executions *not*
#: in this set.
FLAGGED_CLASSES = frozenset({OutcomeClass.DECLARED_AMBIGUOUS})

#: Outcome classes carrying a positive evidential claim, which reconciliation
#: is entitled to contradict.
ASSERTED_CLASSES = frozenset(
    {OutcomeClass.CONFIRMED_APPLIED, OutcomeClass.CONFIRMED_NOT_APPLIED}
)


class ResumePolicy(str, Enum):
    """What the supervisor does with an execution whose worker died."""

    #: Continue with the next execution; the dead one is somebody else's
    #: problem -- specifically, a recovery service's.
    NEXT_EXECUTION = "NEXT_EXECUTION"
    #: Run it again from the beginning. The only other option available to a
    #: system with no durable pre-dispatch record.
    REEXECUTE_CRASHED = "REEXECUTE_CRASHED"


@dataclass(frozen=True)
class SystemDescriptor:
    """One row of the roadmap's table, as a fact the harness can read."""

    system: SystemId
    label: str
    description: str
    #: Does it take the execution lease before touching anything?
    uses_lease: bool
    #: Are state writes fenced (expected-version CAS + live lock token)?
    uses_fenced_state_writes: bool
    #: Is a record of the *intent to call* durable before any provider bytes?
    writes_pre_dispatch_record: bool
    #: Is that record acknowledged durable (WAITAOF) before dispatch?
    uses_durability_barrier: bool
    #: Does a recovery service classify unresolved records after a crash?
    has_recovery_service: bool
    #: Does the caller itself re-send a mutation it already sent once?
    retries_on_ambiguity: bool
    #: Can the system ever record DECLARED_AMBIGUOUS?
    can_declare_ambiguity: bool
    #: Does it send a stable caller reference the provider can index?
    sends_client_reference: bool
    resume_policy: ResumePolicy

    @property
    def dispatches_at_most_once(self) -> bool:
        """True when the caller can contribute no duplicate of its own.

        Read by ``reconcile.py``: the prediction "the caller contributes no
        duplicates" is a property of AEP's dispatch discipline, not of the
        harness, so a baseline that duplicates must not be reported as a
        reconciliation failure.
        """
        return not self.retries_on_ambiguity and (
            self.resume_policy is ResumePolicy.NEXT_EXECUTION
        )

    def echo(self) -> dict[str, Any]:
        return {
            "system": self.system.value,
            "label": self.label,
            "description": self.description,
            "uses_lease": self.uses_lease,
            "uses_fenced_state_writes": self.uses_fenced_state_writes,
            "writes_pre_dispatch_record": self.writes_pre_dispatch_record,
            "uses_durability_barrier": self.uses_durability_barrier,
            "has_recovery_service": self.has_recovery_service,
            "retries_on_ambiguity": self.retries_on_ambiguity,
            "can_declare_ambiguity": self.can_declare_ambiguity,
            "sends_client_reference": self.sends_client_reference,
            "resume_policy": self.resume_policy.value,
            "dispatches_at_most_once": self.dispatches_at_most_once,
        }


SYSTEMS: Mapping[SystemId, SystemDescriptor] = MappingProxyType(
    {
        SystemId.B0_NAIVE_RETRY: SystemDescriptor(
            system=SystemId.B0_NAIVE_RETRY,
            label="B0: naive retry",
            description=(
                "No lease, no CAS, no record before the call. Retries the "
                "mutation whenever the response was not definitive, and writes "
                "down what happened only after it has happened."
            ),
            uses_lease=False,
            uses_fenced_state_writes=False,
            writes_pre_dispatch_record=False,
            uses_durability_barrier=False,
            has_recovery_service=False,
            retries_on_ambiguity=True,
            can_declare_ambiguity=False,
            sends_client_reference=False,
            resume_policy=ResumePolicy.REEXECUTE_CRASHED,
        ),
        SystemId.B1_LEASE_ONLY: SystemDescriptor(
            system=SystemId.B1_LEASE_ONLY,
            label="B1: lease-only",
            description=(
                "Redis lock around the step, state written with a raw SET, no "
                "intent ledger. The lease serialises concurrent workers and "
                "does nothing at all about a worker that has died."
            ),
            uses_lease=True,
            uses_fenced_state_writes=False,
            writes_pre_dispatch_record=False,
            uses_durability_barrier=False,
            has_recovery_service=False,
            retries_on_ambiguity=True,
            can_declare_ambiguity=False,
            sends_client_reference=False,
            resume_policy=ResumePolicy.REEXECUTE_CRASHED,
        ),
        SystemId.B2_CAS_ONLY: SystemDescriptor(
            system=SystemId.B2_CAS_ONLY,
            label="B2: CAS-only",
            description=(
                "Fenced state writes -- expected-version CAS under a live lock "
                "token, AEP's own storage path -- and no write-ahead intent. "
                "State cannot be corrupted or resurrected; external effects are "
                "entirely unprotected."
            ),
            uses_lease=True,
            uses_fenced_state_writes=True,
            writes_pre_dispatch_record=False,
            uses_durability_barrier=False,
            has_recovery_service=False,
            retries_on_ambiguity=True,
            can_declare_ambiguity=False,
            sends_client_reference=False,
            resume_policy=ResumePolicy.REEXECUTE_CRASHED,
        ),
        SystemId.B3_INTENT_NO_BARRIER: SystemDescriptor(
            system=SystemId.B3_INTENT_NO_BARRIER,
            label="B3: intent without the durability barrier",
            description=(
                "The complete protocol with WAITAOF removed: the intent is "
                "written and the dispatch proceeds without waiting for Redis to "
                "acknowledge the fsync. Isolates what the barrier buys."
            ),
            uses_lease=True,
            uses_fenced_state_writes=True,
            writes_pre_dispatch_record=True,
            uses_durability_barrier=False,
            has_recovery_service=True,
            retries_on_ambiguity=False,
            can_declare_ambiguity=True,
            sends_client_reference=True,
            resume_policy=ResumePolicy.NEXT_EXECUTION,
        ),
        SystemId.B4_DURABLE_WORKFLOW: SystemDescriptor(
            system=SystemId.B4_DURABLE_WORKFLOW,
            label="B4: durable-workflow (event-sourced re-execution)",
            description=(
                "A minimal Temporal-shaped durable execution: an append-only "
                "history, durably acknowledged, replayed from the beginning "
                "after a crash. It has a write-ahead record and still "
                "duplicates, because its policy on finding an activity "
                "scheduled-but-not-completed is to run the activity again "
                "rather than to declare the outcome unknown."
            ),
            uses_lease=True,
            uses_fenced_state_writes=False,
            writes_pre_dispatch_record=True,
            uses_durability_barrier=True,
            has_recovery_service=False,
            retries_on_ambiguity=True,
            can_declare_ambiguity=False,
            sends_client_reference=False,
            resume_policy=ResumePolicy.REEXECUTE_CRASHED,
        ),
        SystemId.AEP_FULL: SystemDescriptor(
            system=SystemId.AEP_FULL,
            label="AEP-full",
            description=(
                "The complete protocol: lease, fenced expected-version CAS, "
                "write-ahead intent acknowledged durable by WAITAOF before any "
                "provider bytes exist, bounded reconciliation, and escalation "
                "of everything it cannot resolve."
            ),
            uses_lease=True,
            uses_fenced_state_writes=True,
            writes_pre_dispatch_record=True,
            uses_durability_barrier=True,
            has_recovery_service=True,
            retries_on_ambiguity=False,
            can_declare_ambiguity=True,
            sends_client_reference=True,
            resume_policy=ResumePolicy.NEXT_EXECUTION,
        ),
    }
)


def resolve_system(name: str | SystemId | None) -> SystemId:
    """Accept a system id; refuse anything else.

    ``None`` is refused too. A run that does not say which system produced it
    is not evidence about any system, and defaulting would make the omission
    invisible.
    """
    if name is None:
        raise KeyError(
            "a run must name the system under test; permitted: "
            f"{sorted(member.value for member in SystemId)}"
        )
    if isinstance(name, SystemId):
        return name
    try:
        return SystemId(name)
    except ValueError:
        raise KeyError(
            f"unknown system {name!r}; permitted: "
            f"{sorted(member.value for member in SystemId)}"
        ) from None


def descriptor_for(name: str | SystemId) -> SystemDescriptor:
    return SYSTEMS[resolve_system(name)]


@dataclass(frozen=True)
class ExecutionOutcome:
    """What one system did with one execution, in the shared vocabulary."""

    system: SystemId
    execution_id: str
    #: The system's own word for it -- an ``IntentStatus`` value for AEP and
    #: B3, a baseline's own status string otherwise. Kept alongside the class
    #: so a result can be traced back to the record it came from.
    status: str
    outcome_class: OutcomeClass
    #: How many times this system transmitted the mutation. One for AEP by
    #: construction; the count is what makes a baseline's duplicates
    #: attributable to the caller rather than to the provider.
    dispatch_attempts: int = 0
    intent_id: str | None = None
    request_fingerprint: str | None = None

    def echo(self) -> dict[str, Any]:
        return {
            "system": self.system.value,
            "execution_id": self.execution_id,
            "status": self.status,
            "outcome_class": self.outcome_class.value,
            "dispatch_attempts": self.dispatch_attempts,
            "intent_id": self.intent_id,
            "request_fingerprint": self.request_fingerprint,
        }
