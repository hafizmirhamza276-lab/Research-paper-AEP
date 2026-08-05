"""Declarative fault surface for MockLegacyAPI (PAPER_ROADMAP.md 3.1(1)).

Five configurable dimensions, per endpoint:

===============================  ==========================================
``delay``                        response delay distribution
``timeout_probability``          probability the endpoint never responds
``server_error_probability``     probability of a 5xx
``duplicate_response_probability`` probability the request is delivered twice
``response_class``               the endpoint's reconciliation capability
===============================  ==========================================

**On ``duplicate_response_probability``.** The roadmap names this fault
"duplicate-response probability". A single HTTP exchange cannot deliver two
responses to one request, so the observable form of that fault -- and the one
implemented here -- is a *duplicated delivery of the request inside the
provider*: with this probability the endpoint applies the mutation a second
time before responding, as a legacy system with an at-least-once internal
retry does. The caller receives one response; the ground-truth ledger records
two applied mutations sharing one fingerprint. This is the only reading of the
knob that produces something measurable, and it is stated here because it is
an interpretation of the roadmap's wording rather than a literal transcription
of it.

**On the response class.** ``response_class`` is parsed directly into
``aep_core.core.connector_contract.ReconciliationCapability``. The service does
not define its own vocabulary of response classes and does not compare
capability names as strings anywhere; the enum constructor is the validator,
so an endpoint declaring anything outside the production contract fails to
load rather than defaulting.

Everything unrecognised is refused. A typo in a fault probability must not
read as "the default", because the default is *no fault* and an experiment
would then silently measure an unperturbed API.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

import yaml

from aep_core.core.connector_contract import ReconciliationCapability

#: The document schema this loader understands. A run collected under a
#: different version is not comparable and is refused rather than coerced.
CONFIG_VERSION = "aep.mock-legacy-api.config/1"

_TOP_LEVEL_KEYS = frozenset(
    {
        "config_version",
        "seed",
        "ledger_path",
        "defaults",
        "endpoints",
        "readback_keying",
    }
)
_ENDPOINT_KEYS = frozenset(
    {"response_class", "identity_fields", "faults", "crash_simulation"}
)
_FAULT_KEYS = frozenset(
    {
        "delay",
        "timeout_probability",
        "server_error_probability",
        "duplicate_response_probability",
    }
)
_CRASH_KEYS = frozenset(
    {
        "hold_in_transaction_seconds",
        "hold_after_commit_seconds",
        "progress_marker_path",
    }
)
_DELAY_KEYS = frozenset({"distribution", "seconds", "low", "high", "mean"})


class ConfigError(Exception):
    """The configuration document cannot be loaded, so no run may start."""


class DelayDistribution(str, Enum):
    """How a response delay is drawn."""

    CONSTANT = "constant"
    UNIFORM = "uniform"
    EXPONENTIAL = "exponential"


class ReadbackKeying(str, Enum):
    """What a provider is able to look a past mutation up *by*.

    This is a modelling decision inside the measurement apparatus, not a
    feature of the protocol, and amendment C1 makes it an explicit per-run
    configuration with exactly two values so that no result can be quoted
    without saying which one produced it. The rationale is in
    ``docs/24-readback-keying.md``; the short form:

    ``CALLER_REFERENCE``
        The provider indexes past mutations by the opaque reference the caller
        supplied. Finding your own past effect requires having minted a stable
        identifier for it *before* the ambiguity arose -- which is precisely
        the discipline the protocol under test has and the naive baselines do
        not. This is the primary model; every headline number is collected
        under it.

    ``ORACLE_FINGERPRINT``
        The provider indexes past mutations by their content, using the
        oracle's own identity function (Definition 1 in ``fingerprint.py``).
        Any caller that can describe the mutation can find it, so a baseline
        with no idempotency discipline still gets a working read-back. This is
        the sensitivity variant: it is *more* generous than a real legacy
        endpoint, and it deliberately cannot distinguish two intended
        mutations with identical content -- a hazard asserted by test in
        ``tests/test_readback_keying.py``.
    """

    CALLER_REFERENCE = "CALLER_REFERENCE"
    ORACLE_FINGERPRINT = "ORACLE_FINGERPRINT"


def _reject_unknown(document: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ConfigError(
            f"unknown key(s) {unknown} in {where}; permitted: {sorted(allowed)}"
        )


def _require_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{where} must be a mapping, got {type(value).__name__}")
    return value


def _probability(value: Any, name: str) -> float:
    # bool is excluded deliberately: `timeout_probability: true` is a mistake,
    # not a request for probability 1.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number in [0, 1], got {value!r}")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ConfigError(f"{name} must be a number in [0, 1], got {number}")
    return number


def _non_negative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number, got {value!r}")
    number = float(value)
    if number < 0:
        raise ConfigError(f"{name} must not be negative, got {number}")
    return number


def _positive(value: Any, name: str) -> float:
    number = _non_negative(value, name)
    if number <= 0:
        raise ConfigError(f"{name} must be positive, got {number}")
    return number


@dataclass(frozen=True)
class DelayProfile:
    """A seeded response-delay distribution."""

    distribution: DelayDistribution = DelayDistribution.CONSTANT
    seconds: float = 0.0
    low: float = 0.0
    high: float = 0.0
    mean: float = 0.0

    @classmethod
    def parse(cls, document: Any) -> "DelayProfile":
        document = _require_mapping(document, "delay")
        _reject_unknown(document, _DELAY_KEYS, "delay")
        raw = document.get("distribution", DelayDistribution.CONSTANT.value)
        try:
            distribution = DelayDistribution(raw)
        except ValueError:
            raise ConfigError(
                f"unknown delay distribution {raw!r}; permitted: "
                f"{[member.value for member in DelayDistribution]}"
            ) from None

        if distribution is DelayDistribution.CONSTANT:
            return cls(
                distribution=distribution,
                seconds=_non_negative(document.get("seconds", 0.0), "delay.seconds"),
            )
        if distribution is DelayDistribution.UNIFORM:
            low = _non_negative(document.get("low", 0.0), "delay.low")
            high = _non_negative(document.get("high", 0.0), "delay.high")
            if low > high:
                raise ConfigError(f"delay.low ({low}) exceeds delay.high ({high})")
            return cls(distribution=distribution, low=low, high=high)
        return cls(
            distribution=distribution,
            mean=_positive(document.get("mean", 0.0), "delay.mean"),
        )

    def sample(self, generator: random.Random) -> float:
        """Draw one delay in seconds.

        ``CONSTANT`` deliberately does not touch the generator: a run with
        delays disabled must produce the same stream of fault decisions as one
        with delays enabled, so the two are comparable.
        """
        if self.distribution is DelayDistribution.CONSTANT:
            return self.seconds
        if self.distribution is DelayDistribution.UNIFORM:
            return generator.uniform(self.low, self.high)
        return generator.expovariate(1.0 / self.mean)

    def echo(self) -> dict[str, Any]:
        if self.distribution is DelayDistribution.CONSTANT:
            return {"distribution": self.distribution.value, "seconds": self.seconds}
        if self.distribution is DelayDistribution.UNIFORM:
            return {
                "distribution": self.distribution.value,
                "low": self.low,
                "high": self.high,
            }
        return {"distribution": self.distribution.value, "mean": self.mean}


@dataclass(frozen=True)
class FaultProfile:
    """The four per-endpoint fault knobs. All default to no fault."""

    delay: DelayProfile = DelayProfile()
    timeout_probability: float = 0.0
    server_error_probability: float = 0.0
    duplicate_response_probability: float = 0.0

    @classmethod
    def parse(cls, document: Any, *, base: "FaultProfile") -> "FaultProfile":
        document = _require_mapping(document, "faults")
        _reject_unknown(document, _FAULT_KEYS, "faults")
        return cls(
            delay=(
                DelayProfile.parse(document["delay"])
                if "delay" in document
                else base.delay
            ),
            timeout_probability=(
                _probability(document["timeout_probability"], "timeout_probability")
                if "timeout_probability" in document
                else base.timeout_probability
            ),
            server_error_probability=(
                _probability(
                    document["server_error_probability"], "server_error_probability"
                )
                if "server_error_probability" in document
                else base.server_error_probability
            ),
            duplicate_response_probability=(
                _probability(
                    document["duplicate_response_probability"],
                    "duplicate_response_probability",
                )
                if "duplicate_response_probability" in document
                else base.duplicate_response_probability
            ),
        )

    def echo(self) -> dict[str, Any]:
        return {
            "delay": self.delay.echo(),
            "timeout_probability": self.timeout_probability,
            "server_error_probability": self.server_error_probability,
            "duplicate_response_probability": self.duplicate_response_probability,
        }


@dataclass(frozen=True)
class CrashSimulation:
    """Deliberate stalls around the ledger's commit boundary.

    Used only by the crash-safety test, which needs the service to be
    reliably *inside* a write transaction when SIGKILL arrives. Zero in every
    experimental configuration.
    """

    hold_in_transaction_seconds: float = 0.0
    hold_after_commit_seconds: float = 0.0
    progress_marker_path: str | None = None

    @classmethod
    def parse(cls, document: Any, *, base: "CrashSimulation") -> "CrashSimulation":
        document = _require_mapping(document, "crash_simulation")
        _reject_unknown(document, _CRASH_KEYS, "crash_simulation")
        marker = document.get("progress_marker_path", base.progress_marker_path)
        if marker is not None and not isinstance(marker, str):
            raise ConfigError("crash_simulation.progress_marker_path must be a string")
        return cls(
            hold_in_transaction_seconds=(
                _non_negative(
                    document["hold_in_transaction_seconds"],
                    "crash_simulation.hold_in_transaction_seconds",
                )
                if "hold_in_transaction_seconds" in document
                else base.hold_in_transaction_seconds
            ),
            hold_after_commit_seconds=(
                _non_negative(
                    document["hold_after_commit_seconds"],
                    "crash_simulation.hold_after_commit_seconds",
                )
                if "hold_after_commit_seconds" in document
                else base.hold_after_commit_seconds
            ),
            progress_marker_path=marker,
        )

    @property
    def is_armed(self) -> bool:
        return (
            self.hold_in_transaction_seconds > 0 or self.hold_after_commit_seconds > 0
        )

    def echo(self) -> dict[str, Any]:
        return {
            "hold_in_transaction_seconds": self.hold_in_transaction_seconds,
            "hold_after_commit_seconds": self.hold_after_commit_seconds,
            "progress_marker_path": self.progress_marker_path,
        }


@dataclass(frozen=True)
class EndpointConfig:
    """One simulated legacy endpoint."""

    name: str
    response_class: ReconciliationCapability
    identity_fields: tuple[str, ...]
    faults: FaultProfile
    crash_simulation: CrashSimulation

    @classmethod
    def parse(
        cls,
        name: str,
        document: Any,
        *,
        default_faults: FaultProfile,
        default_crash: CrashSimulation,
    ) -> "EndpointConfig":
        document = _require_mapping(document, f"endpoints.{name}")
        _reject_unknown(document, _ENDPOINT_KEYS, f"endpoints.{name}")

        if "response_class" not in document:
            raise ConfigError(f"endpoints.{name} declares no response_class")
        try:
            # The production contract is the validator. No local vocabulary,
            # no string comparison of capability names.
            capability = ReconciliationCapability(document["response_class"])
        except ValueError:
            raise ConfigError(
                f"endpoints.{name}.response_class {document['response_class']!r} is "
                "not a declared reconciliation capability; permitted: "
                f"{[member.value for member in ReconciliationCapability]}"
            ) from None

        fields = document.get("identity_fields", [])
        if not isinstance(fields, (list, tuple)) or not fields:
            raise ConfigError(
                f"endpoints.{name}.identity_fields must be a non-empty list; "
                "without one, every mutation on the endpoint has the same "
                "fingerprint and the oracle cannot distinguish them"
            )
        if any(not isinstance(field, str) or not field for field in fields):
            raise ConfigError(f"endpoints.{name}.identity_fields must be field names")
        if len(set(fields)) != len(fields):
            raise ConfigError(f"endpoints.{name}.identity_fields contains duplicates")

        return cls(
            name=name,
            response_class=capability,
            identity_fields=tuple(fields),
            faults=(
                FaultProfile.parse(document["faults"], base=default_faults)
                if "faults" in document
                else default_faults
            ),
            crash_simulation=(
                CrashSimulation.parse(
                    document["crash_simulation"], base=default_crash
                )
                if "crash_simulation" in document
                else default_crash
            ),
        )

    def echo(self) -> dict[str, Any]:
        return {
            "response_class": self.response_class.value,
            "identity_fields": list(self.identity_fields),
            "faults": self.faults.echo(),
            "crash_simulation": self.crash_simulation.echo(),
        }


@dataclass(frozen=True)
class MockApiConfig:
    """A complete, self-describing description of one mock API run."""

    config_version: str
    seed: int
    ledger_path: str
    endpoints: Mapping[str, EndpointConfig]
    source_path: str
    #: Amendment C1. Part of the digest: a result collected under one keying
    #: must not be attributable to a run under the other.
    readback_keying: ReadbackKeying = ReadbackKeying.CALLER_REFERENCE

    def echo(self) -> dict[str, Any]:
        """The whole configuration, JSON-ready, with its own digest.

        Written into every run's result log. A result whose log does not carry
        this object cannot be attributed to a configuration, and a result that
        cannot be attributed to a configuration is not evidence.
        """
        body = self._body()
        return {**body, "config_digest": self.config_digest}

    def _body(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "seed": self.seed,
            "ledger_path": self.ledger_path,
            "source_path": self.source_path,
            "readback_keying": self.readback_keying.value,
            "endpoints": {
                name: endpoint.echo()
                for name, endpoint in sorted(self.endpoints.items())
            },
        }

    @property
    def config_digest(self) -> str:
        """SHA-256 over the echo body. Changes when any knob changes.

        ``source_path`` is excluded: the same configuration moved to another
        directory is the same configuration, and two runs of it must be
        comparable.
        """
        body = {
            key: value for key, value in self._body().items() if key != "source_path"
        }
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def endpoint(self, name: str) -> EndpointConfig:
        try:
            return self.endpoints[name]
        except KeyError:
            raise ConfigError(f"no endpoint named {name!r} is configured") from None


def load_config(path: str | Path) -> MockApiConfig:
    """Load and fully validate a mock API configuration document."""
    source = Path(path)
    if not source.is_file():
        raise ConfigError(f"configuration file not found: {source}")

    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"configuration is not valid YAML: {exc}") from None

    document = _require_mapping(document, "configuration document")
    _reject_unknown(document, _TOP_LEVEL_KEYS, "configuration document")

    version = document.get("config_version")
    if version is None:
        raise ConfigError("configuration document declares no config_version")
    if version != CONFIG_VERSION:
        raise ConfigError(
            f"unsupported config_version {version!r}; this loader understands "
            f"{CONFIG_VERSION!r}"
        )

    seed = document.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ConfigError(f"seed must be an integer, got {seed!r}")

    defaults = _require_mapping(document.get("defaults", {}), "defaults")
    _reject_unknown(defaults, frozenset({"faults", "crash_simulation"}), "defaults")
    default_faults = (
        FaultProfile.parse(defaults["faults"], base=FaultProfile())
        if "faults" in defaults
        else FaultProfile()
    )
    default_crash = (
        CrashSimulation.parse(defaults["crash_simulation"], base=CrashSimulation())
        if "crash_simulation" in defaults
        else CrashSimulation()
    )

    endpoints_document = _require_mapping(document.get("endpoints", {}), "endpoints")
    if not endpoints_document:
        raise ConfigError("configuration must declare at least one endpoint")

    endpoints = {
        name: EndpointConfig.parse(
            name,
            endpoint_document,
            default_faults=default_faults,
            default_crash=default_crash,
        )
        for name, endpoint_document in endpoints_document.items()
    }

    ledger_path = document.get("ledger_path", "ground_truth.sqlite3")
    if not isinstance(ledger_path, str) or not ledger_path:
        raise ConfigError("ledger_path must be a non-empty string")

    raw_keying = document.get(
        "readback_keying", ReadbackKeying.CALLER_REFERENCE.value
    )
    try:
        keying = ReadbackKeying(raw_keying)
    except ValueError:
        raise ConfigError(
            f"readback_keying {raw_keying!r} is not a declared keying; "
            f"permitted: {[member.value for member in ReadbackKeying]}"
        ) from None

    return MockApiConfig(
        config_version=version,
        seed=seed,
        ledger_path=ledger_path,
        endpoints=endpoints,
        source_path=str(source),
        readback_keying=keying,
    )
