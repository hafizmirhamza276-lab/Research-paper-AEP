"""One run's complete, self-describing configuration.

Amendment C4 requires ``events.jsonl`` to open with a full config echo. This
module is what gets echoed, so it has to carry every decision that could change
a number -- seeds, worker and execution counts, the crash point, the timing
policy, and the two measurement decisions of amendment C1 (read-back keying)
and C2 (dispatch mode).

Amendment C2 is enforced structurally rather than by discipline:
:class:`RunConfig` refuses to represent a run in ``TEST`` mode. There is no
flag to set, so there is no flag to leave set by accident. ``PRODUCTION`` is
refused too, because this repository ships no production vault or connector and
a run configured for it could only fail closed inside a worker, several seconds
and one spawned process later.

The configuration also validates the timing policy up front by constructing the
``ConnectorPolicy`` it will hand to workers. ``T_client <= T_lock - Buffer`` is
one of AEP's three hard invariants; discovering a violation of it in three
concurrently spawned subprocesses is strictly worse than discovering it here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from aep_core.core.intent_workflow import ConnectorPolicy, DispatchMode

from experiments.baselines.contract import (
    ResumePolicy,
    SystemId,
    descriptor_for,
    resolve_system,
)
from experiments.baselines.crash_points import resolve_for_system
from experiments.harness.crash_points import CrashPoint
from experiments.harness.injector import CrashStyle
from experiments.harness import provenance
from experiments.mock_api.config import ReadbackKeying

#: Bumping this is a statement that previously collected runs are not
#: comparable to new ones.
RUN_CONFIG_VERSION = "aep.harness.run-config/1"


@dataclass(frozen=True)
class RunConfig:
    """Everything one run of the harness needs, and nothing it may hide."""

    run_id: str
    seed: int
    workers: int
    executions_per_worker: int
    endpoint: str
    mock_api_config_path: str
    mock_api_base_url: str
    redis_url: str
    results_root: str

    # -- measurement decisions --------------------------------------------
    dispatch_mode: DispatchMode = DispatchMode.EVALUATION
    readback_keying: ReadbackKeying = ReadbackKeying.CALLER_REFERENCE
    #: Which of PAPER_ROADMAP.md section 3.3's six systems this run measures.
    #: Named explicitly rather than inferred, and inside ``config_digest``, so
    #: two systems' runs can never be pooled by accident.
    system: SystemId = SystemId.AEP_FULL
    #: ``None`` takes the system's declared policy. Set it to measure the
    #: other choice -- ``experiments/baselines/contract.py`` explains why the
    #: choice exists and why it is not the harness's to make silently.
    resume_policy: ResumePolicy | None = None
    #: How many times a retrying system sends the same mutation before giving
    #: up. Ignored by the systems that never retry; recorded for all of them,
    #: because a duplicate count is uninterpretable without it.
    max_dispatch_attempts: int = 3

    # -- fault injection ---------------------------------------------------
    crash_point: str | None = None
    crash_style: str | None = None
    crash_delay_ms: int = 400
    #: Probability that any one execution is selected for the crash. Drawn
    #: from the run seed, so the selection is reproducible and recorded.
    crash_probability: float = 1.0
    poisoned_executions: int = 0
    redis_restarts: int = 0
    partition_seconds: float = 0.0
    #: Amendment E1. The instruction boundary at which a worker hard-kills
    #: Redis (``docker kill -s KILL``), named in the same vocabulary as
    #: ``crash_point``. ``None`` means no Redis kill, and the disabled path is
    #: the absence of the injector rather than a disabled one.
    redis_kill_point: str | None = None
    #: How long the watchdog waits after the checkpoint before issuing the
    #: kill. Zero aims it at the checkpoint itself; a few hundred milliseconds
    #: aims it past a dispatch the checkpoint precedes.
    redis_kill_delay_ms: int = 0
    #: How many of the run's executions arm the kill, taken from the front of
    #: the plan. More than one would land a second kill on a Redis the first
    #: one is still restarting, so this is 1 wherever it is not 0.
    redis_kill_executions: int = 0

    # -- timing validity (amendment E5) ------------------------------------
    #: Whether the operator declared, before the run, that this host cannot
    #: suspend. Session 3 lost the timings of 5 runs in 83 to a host that
    #: entered S0 low-power idle after five minutes: ``CLOCK_MONOTONIC``
    #: stopped, ``CLOCK_REALTIME`` was resynchronised on resume, and every
    #: wall-clock interval in those runs silently contained the suspension.
    #:
    #: Amendment E5 says absolute timing may re-enter the paper only from runs
    #: on a host with suspend disabled. This field is the *declaration*; the
    #: analysis's wall-versus-monotonic gate is the *detection*. Both are
    #: required, because a declaration can be wrong and a detection can only
    #: catch a suspension that actually happened -- a run that was simply never
    #: idle long enough looks identical either way.
    suspend_disabled_declared: bool = False

    # -- timing policy -----------------------------------------------------
    client_timeout_seconds: float = 5.0
    settlement_lag_seconds: float = 0.0
    buffer_margin_seconds: float = 15.0
    lock_ttl_seconds: int = 25
    durability_timeout_ms: int = 2000
    lease_acquire_attempts: int = 3

    # -- recovery ----------------------------------------------------------
    recovery_pass_interval_seconds: float = 2.0
    recovery_deadline_seconds: float = 180.0

    # -- infrastructure ----------------------------------------------------
    compose_file: str = "compose.phase2.yml"
    redis_container: str = "aep-phase2-redis72"
    redis_service: str = "redis-phase2"
    toxiproxy_api_url: str = "http://127.0.0.1:8474"
    toxiproxy_proxy_name: str = "aep-redis"
    toxiproxy_listen: str = "0.0.0.0:6382"
    toxiproxy_upstream: str = "redis-phase2:6379"
    #: The URL workers use. Points at the toxiproxy listener when a partition
    #: is part of the run; at Redis directly otherwise.
    worker_redis_url: str | None = None

    config_version: str = RUN_CONFIG_VERSION

    # -- validation --------------------------------------------------------

    def __post_init__(self) -> None:
        object.__setattr__(self, "dispatch_mode", DispatchMode(self.dispatch_mode))
        object.__setattr__(self, "readback_keying", ReadbackKeying(self.readback_keying))
        object.__setattr__(self, "system", resolve_system(self.system))
        if self.resume_policy is not None:
            object.__setattr__(self, "resume_policy", ResumePolicy(self.resume_policy))

        if self.dispatch_mode is not DispatchMode.EVALUATION:
            raise ValueError(
                "the harness runs in EVALUATION mode only (amendment C2): "
                f"{self.dispatch_mode.value} is not configurable. TEST mode "
                "would measure a composition carrying test authorisations; "
                "PRODUCTION has no vault or connector in this repository."
            )
        if self.workers < 1:
            raise ValueError("workers must be at least 1")
        if self.executions_per_worker < 1:
            raise ValueError("executions_per_worker must be at least 1")
        if not 0.0 <= self.crash_probability <= 1.0:
            raise ValueError("crash_probability must be in [0, 1]")
        if self.crash_delay_ms < 0:
            raise ValueError("crash_delay_ms must not be negative")
        if self.poisoned_executions < 0:
            raise ValueError("poisoned_executions must not be negative")
        if self.redis_restarts < 0:
            raise ValueError("redis_restarts must not be negative")
        if self.partition_seconds < 0:
            raise ValueError("partition_seconds must not be negative")
        if self.redis_kill_delay_ms < 0:
            raise ValueError("redis_kill_delay_ms must not be negative")
        if self.redis_kill_executions < 0:
            raise ValueError("redis_kill_executions must not be negative")
        if self.redis_kill_point is not None and self.redis_kill_executions < 1:
            raise ValueError(
                "a redis_kill_point with no armed executions would be a fault "
                "the run log claims and never injects; set "
                "redis_kill_executions to at least 1"
            )
        if self.redis_kill_point is None and self.redis_kill_executions:
            raise ValueError(
                "redis_kill_executions is set with no redis_kill_point, so "
                "nothing would arm; name the instruction boundary"
            )
        if self.recovery_deadline_seconds <= 0:
            raise ValueError("recovery_deadline_seconds must be positive")
        if self.max_dispatch_attempts < 1:
            raise ValueError("max_dispatch_attempts must be at least 1")
        if self.config_version != RUN_CONFIG_VERSION:
            raise ValueError(
                f"unsupported run config version {self.config_version!r}; this "
                f"harness understands {RUN_CONFIG_VERSION!r}"
            )

        # Raises KeyError on a typo rather than silently running without a
        # crash, CrashPointNotApplicable when this system has no such moment,
        # and ValueError on an impossible timing policy. All three are
        # discovered here rather than inside three spawned subprocesses.
        resolve_for_system(self.system, self.crash_point)
        # Same treatment for the Redis kill: a name this system has no moment
        # for is refused here rather than inside a spawned worker.
        resolve_for_system(self.system, self.redis_kill_point)
        if self.crash_style is not None:
            CrashStyle(self.crash_style)
        try:
            self.policy()
        except ValueError as error:
            raise ValueError(f"invalid timing policy: {error}") from None

    # -- derived -----------------------------------------------------------

    @property
    def descriptor(self):
        """What the system under test claims about itself."""
        return descriptor_for(self.system)

    @property
    def effective_resume_policy(self) -> ResumePolicy:
        """The supervisor policy in force, explicit or declared."""
        return self.resume_policy or self.descriptor.resume_policy

    @property
    def resolved_crash_point(self):
        return resolve_for_system(self.system, self.crash_point)

    @property
    def total_executions(self) -> int:
        return self.workers * self.executions_per_worker

    @property
    def results_dir(self) -> Path:
        return Path(self.results_root) / self.run_id

    @property
    def effective_worker_redis_url(self) -> str:
        """Where workers connect. The proxy when a partition is scheduled."""
        return self.worker_redis_url or self.redis_url

    def policy(self) -> ConnectorPolicy:
        """The exact ``ConnectorPolicy`` every worker and recovery pass uses."""
        return ConnectorPolicy(
            client_timeout_seconds=self.client_timeout_seconds,
            settlement_lag_seconds=self.settlement_lag_seconds,
            buffer_margin_seconds=self.buffer_margin_seconds,
            lock_ttl_seconds=self.lock_ttl_seconds,
            durability_timeout_ms=self.durability_timeout_ms,
            lease_acquire_attempts=self.lease_acquire_attempts,
        )

    # -- echo --------------------------------------------------------------

    def _body(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        for entry in fields(self):
            value = getattr(self, entry.name)
            body[entry.name] = value.value if hasattr(value, "value") else value
        point = self.resolved_crash_point
        body["resolved_crash_point"] = point.value if point is not None else None
        return body

    def echo(self) -> dict[str, Any]:
        """The whole configuration, JSON-ready, with its digest.

        Written as the first record of every run log. A result whose log does
        not carry this object cannot be attributed to a configuration.

        ``environment`` carries what the run can *detect* about itself rather
        than what it was told -- the filesystem under the results root and the
        storage actually backing Redis's ``/data``. Phase 9C compared five
        collections key by key, found "40 of 44 identical", and concluded they
        were interchangeable; the filesystem difference that Phase 8.1 later
        found was invisible to that comparison because it was not a key. See
        ``experiments/harness/provenance.py`` for why there are two fields.

        It is deliberately outside ``_body()`` and therefore outside the
        digest. Two runs that differ only in where Docker happened to place a
        volume are the same configuration observed twice -- and, decisively,
        the digest is re-verified whenever a saved configuration is parsed
        (:func:`run_config_from_mapping`), so digesting these keys would make
        every already-frozen run fail its own check the next time anything
        read it.
        """
        return {
            **self._body(),
            "config_digest": self.config_digest,
            "environment": provenance.collect(
                Path(self.results_root), self.redis_container
            ),
        }

    @property
    def config_digest(self) -> str:
        """SHA-256 over everything that could change a number.

        ``run_id`` and ``results_root`` are excluded: the same configuration
        run twice, or written to a different directory, is the same
        configuration, and two runs of it must be comparable.
        ``resolved_crash_point`` is excluded because it is derived from
        ``crash_point`` and would double-count it.
        """
        excluded = {"run_id", "results_root", "resolved_crash_point"}
        body = {
            key: value
            for key, value in self._body().items()
            if key not in excluded
        }
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def run_config_from_mapping(document: dict[str, Any]) -> RunConfig:
    """Rebuild a configuration from its echo, refusing anything unrecognised."""
    known = set(RunConfig.__dataclass_fields__)
    # Derived and self-describing keys the echo adds back. ``environment`` is
    # detected at run construction and is not a knob: it must be accepted here
    # so a run collected after Phase 8.2 can be re-read, and ignored rather
    # than reconstructed so a run collected before it still can be.
    derived = {"config_digest", "resolved_crash_point", "environment"}
    unknown = sorted(set(document) - known - derived)
    if unknown:
        raise ValueError(
            f"unknown key(s) {unknown} in the saved run configuration; a field "
            "silently ignored here would misdescribe the run it produced"
        )
    accepted = {key: value for key, value in document.items() if key in known}
    config = RunConfig(**accepted)

    declared = document.get("config_digest")
    if declared is not None and declared != config.config_digest:
        raise ValueError(
            "the saved run configuration does not match its own digest: "
            f"{declared} != {config.config_digest}"
        )
    return config


def load_run_config(path: Path | str) -> RunConfig:
    """Load a run configuration a runner wrote for its workers."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("a run configuration must be a JSON object")
    return run_config_from_mapping(document)
