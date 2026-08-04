"""Phase 2 typed intent ledger and lease-fenced Redis state transitions.

This module deliberately does not dispatch external effects.  It owns the
persisted intent schema and the one atomic state-machine write path used by
the Phase 2 runner and recovery worker.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, AsyncIterator, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from redis.asyncio import Redis

from src.core.exceptions import (
    AEPException,
    LockAcquisitionError,
    StaleWriteError,
    StateCorruptionError,
)
from src.core.state_codec import build_lua_state_validation_script, encode_state
from src.core.request_binding import (
    CanonicalizationError,
    PersistedRequestBinding,
    canonical_request_binding_bytes,
    parse_canonical_request_binding,
)
from src.core.storage import (
    PHASE2_MANAGED_MARKER,
    AEPExecutionState,
    AEPStatus,
    RedisStorageAdapter,
)


MINIMUM_UNRESOLVED_TTL_SECONDS = 31 * 24 * 60 * 60
NONE_STATE = "NONE"


class IntentStatus(str, Enum):
    ABOUT_TO_FIRE = "ABOUT_TO_FIRE"
    FIRED_CONFIRMED = "FIRED_CONFIRMED"
    FAILED_CONFIRMED = "FAILED_CONFIRMED"
    FIRED_UNCONFIRMED = "FIRED_UNCONFIRMED"
    PERMANENTLY_AMBIGUOUS = "PERMANENTLY_AMBIGUOUS"


UNRESOLVED_INTENT_STATUSES = frozenset(
    {IntentStatus.ABOUT_TO_FIRE, IntentStatus.FIRED_UNCONFIRMED}
)

LEGAL_INTENT_TRANSITIONS = frozenset(
    {
        (NONE_STATE, IntentStatus.ABOUT_TO_FIRE.value),
        (IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FIRED_CONFIRMED.value),
        (IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FAILED_CONFIRMED.value),
        (IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FIRED_UNCONFIRMED.value),
        (
            IntentStatus.FIRED_UNCONFIRMED.value,
            IntentStatus.FIRED_UNCONFIRMED.value,
        ),
        (
            IntentStatus.FIRED_UNCONFIRMED.value,
            IntentStatus.FIRED_CONFIRMED.value,
        ),
        (
            IntentStatus.FIRED_UNCONFIRMED.value,
            IntentStatus.FAILED_CONFIRMED.value,
        ),
        (
            IntentStatus.FIRED_UNCONFIRMED.value,
            IntentStatus.PERMANENTLY_AMBIGUOUS.value,
        ),
        (
            IntentStatus.PERMANENTLY_AMBIGUOUS.value,
            IntentStatus.FIRED_CONFIRMED.value,
        ),
        (
            IntentStatus.PERMANENTLY_AMBIGUOUS.value,
            IntentStatus.FAILED_CONFIRMED.value,
        ),
    }
)


def require_legal_intent_transition(old_status: str, new_status: str) -> None:
    """Reject every edge outside the normative exhaustive transition set."""

    if (old_status, new_status) not in LEGAL_INTENT_TRANSITIONS:
        raise IllegalIntentTransitionError(
            f"illegal intent transition {old_status} -> {new_status}"
        )


class IntentStateError(AEPException):
    """Base class for a rejected Phase 2 intent operation."""


class IllegalIntentTransitionError(IntentStateError):
    """The requested edge is not in the exhaustive transition table."""


class IntentInvariantError(IntentStateError):
    """An immutable, uniqueness, retention, or append-only rule was broken."""


class IntentCreationEligibilityError(IntentStateError):
    """Normal creation is not eligible under the same-step predecessor rule."""


class ExecutionIntentFenceError(IntentInvariantError):
    """Normal creation is blocked by PAUSED or an execution-wide intent fence."""


class IntentPreflightError(IntentStateError):
    """The final atomic lease/version/status pre-dispatch check failed."""


class IntentBindingError(IntentInvariantError):
    """A mandatory immutable request binding is absent or inconsistent."""


_SAFE_PERSISTED_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def _safe_persisted_value(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _SAFE_PERSISTED_VALUE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a bounded safe identifier")
    return value


class IntentAuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    old_state: str
    new_state: IntentStatus
    redis_time: float = Field(ge=0)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_hash: str

    @field_validator("old_state")
    @classmethod
    def _known_old_state(cls, value: str) -> str:
        if value != NONE_STATE:
            IntentStatus(value)
        return value

    @field_validator("evidence_hash")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if len(value) != 64:
            raise ValueError("evidence_hash must be a SHA-256 hex digest")
        try:
            int(value, 16)
        except ValueError:
            raise ValueError("evidence_hash must be a SHA-256 hex digest") from None
        return value.lower()

    @field_validator("actor", "reason")
    @classmethod
    def _safe_text(cls, value: str, info) -> str:
        return _safe_persisted_value(value, field=info.field_name)


class IntentObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_class: str = Field(min_length=1)
    observed_at: float = Field(ge=0)
    detail: str = Field(min_length=1)

    @field_validator("evidence_class", "detail")
    @classmethod
    def _safe_text(cls, value: str, info) -> str:
        return _safe_persisted_value(value, field=info.field_name)


class ReconciliationProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_count: int = Field(default=0, ge=0, strict=True)
    first_check_at: float | None = Field(default=None, ge=0)
    last_check_at: float | None = Field(default=None, ge=0)
    next_check_at: float = Field(ge=0)
    last_evidence_class: str | None = None

    @field_validator("last_evidence_class")
    @classmethod
    def _safe_evidence_class(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_persisted_value(value, field="last_evidence_class")


class IntentRecord(BaseModel):
    """The exact persisted record contract from design section 3."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True
    )

    intent_id: str
    step_id: str = Field(min_length=1)
    attempt: int = Field(ge=1, strict=True)
    connector: str = Field(min_length=1)
    target: str = Field(min_length=1)
    request_fingerprint: str
    request_binding: PersistedRequestBinding | None = Field(
        default=None, exclude=True, repr=False
    )
    canonical_request_binding: str | None = Field(
        default=None, max_length=1_048_576, repr=False
    )
    correlation_id: str
    status: IntentStatus
    prepared_at: float = Field(ge=0)
    client_timeout_seconds: float = Field(gt=0)
    settlement_lag_seconds: float = Field(ge=0)
    reconcile_after: float = Field(ge=0)
    prepared_state_version: int = Field(ge=1, strict=True)
    external_reference: str | None = None
    last_observation: IntentObservation | None = None
    reconciliation: ReconciliationProgress | None = None
    transitions: tuple[IntentAuditEntry, ...] = Field(min_length=1)
    risk_acceptance_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _load_authoritative_canonical_binding(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        supplied = dict(value)
        binding_value = supplied.get("request_binding")
        canonical = supplied.get("canonical_request_binding")
        if canonical is None:
            if binding_value is not None:
                raise ValueError(
                    "bound intent requires an authoritative canonical binding"
                )
            supplied["request_binding"] = None
            return supplied
        if type(canonical) is not str:
            raise ValueError("canonical request binding must be UTF-8 text")
        try:
            parsed = parse_canonical_request_binding(canonical)
        except CanonicalizationError:
            raise ValueError("canonical request binding is invalid") from None
        if binding_value is not None:
            try:
                provided = (
                    binding_value
                    if isinstance(binding_value, PersistedRequestBinding)
                    else PersistedRequestBinding.model_validate(binding_value)
                )
            except (ValueError, TypeError):
                raise ValueError("request binding is invalid") from None
            if canonical_request_binding_bytes(provided).decode("utf-8") != canonical:
                raise ValueError("request binding does not match canonical bytes")
        supplied["request_binding"] = parsed
        return supplied

    @field_validator("intent_id", "correlation_id")
    @classmethod
    def _uuid4(cls, value: str) -> str:
        parsed = uuid.UUID(value)
        if parsed.version != 4 or str(parsed) != value.lower():
            raise ValueError("must be a canonical UUIDv4 string")
        return str(parsed)

    @field_validator("request_fingerprint")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if len(value) != 64:
            raise ValueError("request_fingerprint must be a SHA-256 hex digest")
        try:
            int(value, 16)
        except ValueError:
            raise ValueError(
                "request_fingerprint must be a SHA-256 hex digest"
            ) from None
        return value.lower()

    @field_validator("step_id", "connector", "target")
    @classmethod
    def _safe_identity(cls, value: str, info) -> str:
        return _safe_persisted_value(value, field=info.field_name)

    @field_validator("external_reference", "risk_acceptance_id")
    @classmethod
    def _safe_optional_identity(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _safe_persisted_value(value, field=info.field_name)

    @model_validator(mode="after")
    def _time_and_history_consistency(self) -> "IntentRecord":
        if self.reconcile_after < self.prepared_at:
            raise ValueError("reconcile_after cannot precede prepared_at")
        latest = self.transitions[-1]
        if latest.new_state is not self.status:
            raise ValueError("latest transition must end at current status")
        if self.status is IntentStatus.FIRED_UNCONFIRMED:
            if self.reconciliation is None:
                raise ValueError("FIRED_UNCONFIRMED requires reconciliation state")
        binding = self.request_binding
        if binding is not None:
            if (
                binding.intent_id != self.intent_id
                or binding.step_id != self.step_id
                or binding.correlation_id != self.correlation_id
                or binding.connector_operation != self.connector
                or binding.safe_descriptor.redacted_target != self.target
                or binding.request_fingerprint != self.request_fingerprint
            ):
                raise ValueError("intent/request-binding identity mismatch")
        elif self.canonical_request_binding is not None:
            raise ValueError("canonical request binding has no typed binding")
        return self


class Phase2ExecutionState(AEPExecutionState):
    """Strict Phase 2 view over the Phase 1-compatible execution envelope."""

    intent_ledger: dict[str, IntentRecord] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ledger_keys_and_uniqueness(self) -> "Phase2ExecutionState":
        unresolved_steps: set[str] = set()
        attempts: dict[str, set[int]] = {}
        for key, intent in self.intent_ledger.items():
            if key != intent.intent_id:
                raise ValueError("intent ledger key must equal intent_id")
            if (
                intent.request_binding is not None
                and intent.request_binding.execution_id != self.execution_id
            ):
                raise ValueError("request binding belongs to another execution")
            step_attempts = attempts.setdefault(intent.step_id, set())
            if intent.attempt in step_attempts:
                raise ValueError("intent attempt must be unique within step_id")
            step_attempts.add(intent.attempt)
            if intent.status in UNRESOLVED_INTENT_STATUSES:
                if intent.step_id in unresolved_steps:
                    raise ValueError(
                        "at most one unresolved intent is allowed per step_id"
                    )
                unresolved_steps.add(intent.step_id)
        return self


# The candidate is built and typed in Python.  This Lua script is the
# authoritative race-free validator: every rule below is checked again in the
# same atomic invocation that performs SET.
_INTENT_CAS_SCRIPT_BODY = r"""
local current_raw = redis.call('GET', KEYS[1])
if not current_raw then return -2 end

local current_check = aep_json_member_check(current_raw)
if current_check == 1 then return -11 end
if current_check ~= 0 then return -10 end
local candidate_check = aep_json_member_check(ARGV[1])
if candidate_check == 1 then return -13 end
if candidate_check ~= 0 then return -12 end

-- Raw stored and candidate serializations are authoritative and therefore
-- validated before lease, version, status, ledger, marker, or retention data.
if redis.call('GET', KEYS[2]) ~= ARGV[2] then return -3 end

local ok_current, current = pcall(cjson.decode, current_raw)
local ok_next, candidate = pcall(cjson.decode, ARGV[1])
if not ok_current or type(current) ~= 'table' or
   type(current.version) ~= 'number' or
   type(current.intent_ledger) ~= 'table' then
    return -2
end
if not ok_next or type(candidate) ~= 'table' or
   type(candidate.intent_ledger) ~= 'table' then return -12 end

local expected = tonumber(ARGV[3])
local ttl = tonumber(ARGV[8])
if not expected or current.version ~= expected or
   candidate.version ~= expected + 1 then return -1 end
if not ttl or ttl < 1 then return -5 end
if current.execution_id ~= candidate.execution_id or
   current.schema_version ~= candidate.schema_version then return -5 end

local function has_value(value)
    return value ~= nil and value ~= cjson.null
end

local phase2_marker = ARGV[10]
if has_value(current.phase2_managed) and
   current.phase2_managed ~= phase2_marker then return -2 end
if candidate.phase2_managed ~= phase2_marker then return -8 end
if has_value(current.phase2_managed) and
   candidate.phase2_managed ~= current.phase2_managed then return -8 end

local function deep_equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= 'table' then return a == b end
    for k, v in pairs(a) do
        if not deep_equal(v, b[k]) then return false end
    end
    for k, _ in pairs(b) do
        if a[k] == nil then return false end
    end
    return true
end

for k, v in pairs(current) do
    if k ~= 'version' and k ~= 'status' and k ~= 'updated_at' and
       k ~= 'intent_ledger' and k ~= 'phase2_managed' and
       not deep_equal(v, candidate[k]) then
        return -5
    end
end
for k, _ in pairs(candidate) do
    if current[k] == nil and k ~= 'version' and k ~= 'status' and
       k ~= 'updated_at' and k ~= 'intent_ledger' and
       k ~= 'phase2_managed' then return -5 end
end

local intent_id = ARGV[4]
local old_status = ARGV[5]
local new_status = ARGV[6]
local old_record = current.intent_ledger[intent_id]
local new_record = candidate.intent_ledger[intent_id]
if type(new_record) ~= 'table' or new_record.intent_id ~= intent_id or
   new_record.status ~= new_status then return -5 end

local legal = {
 ['NONE>ABOUT_TO_FIRE']=true,
 ['ABOUT_TO_FIRE>FIRED_CONFIRMED']=true,
 ['ABOUT_TO_FIRE>FAILED_CONFIRMED']=true,
 ['ABOUT_TO_FIRE>FIRED_UNCONFIRMED']=true,
 ['FIRED_UNCONFIRMED>FIRED_UNCONFIRMED']=true,
 ['FIRED_UNCONFIRMED>FIRED_CONFIRMED']=true,
 ['FIRED_UNCONFIRMED>FAILED_CONFIRMED']=true,
 ['FIRED_UNCONFIRMED>PERMANENTLY_AMBIGUOUS']=true,
 ['PERMANENTLY_AMBIGUOUS>FIRED_CONFIRMED']=true,
 ['PERMANENTLY_AMBIGUOUS>FAILED_CONFIRMED']=true
}
if not legal[old_status .. '>' .. new_status] then return -4 end

local function count_entries(t)
    local n = 0
    for _, _ in pairs(t) do n = n + 1 end
    return n
end

if old_status == 'NONE' then
    if old_record ~= nil then return -5 end
    if type(new_record.canonical_request_binding) ~= 'string' or
       new_record.canonical_request_binding ~= ARGV[12] then return -9 end
    local ok_binding, binding = pcall(
        cjson.decode, new_record.canonical_request_binding
    )
    if not ok_binding or type(binding) ~= 'table' then return -9 end
    if binding.execution_id ~= candidate.execution_id or
       binding.step_id ~= new_record.step_id or
       binding.intent_id ~= intent_id or
       binding.correlation_id ~= new_record.correlation_id or
       binding.connector_operation ~= new_record.connector or
       binding.request_fingerprint ~= new_record.request_fingerprint or
       type(binding.retention_not_after_ms) ~= 'number' or
       binding.retention_not_after_ms < tonumber(ARGV[11]) then return -9 end
    if current.status == 'PAUSED' then return -7 end
    if candidate.status ~= 'PROCESSING' then return -5 end
    if count_entries(candidate.intent_ledger) ~=
       count_entries(current.intent_ledger) + 1 then return -5 end
    local max_attempt = 0
    local latest_status = nil
    for key, record in pairs(current.intent_ledger) do
        if type(record) ~= 'table' or type(record.status) ~= 'string' or
           type(record.step_id) ~= 'string' or
           type(record.attempt) ~= 'number' then return -5 end
        if record.status == 'ABOUT_TO_FIRE' or
           record.status == 'FIRED_UNCONFIRMED' or
           record.status == 'PERMANENTLY_AMBIGUOUS' then return -7 end
        if candidate.intent_ledger[key] == nil or
           not deep_equal(record, candidate.intent_ledger[key]) then return -5 end
        if record.step_id == new_record.step_id and
           type(record.attempt) == 'number' and record.attempt > max_attempt then
            max_attempt = record.attempt
            latest_status = record.status
        end
    end
    if has_value(new_record.risk_acceptance_id) then return -6 end
    if latest_status ~= nil and latest_status ~= 'FAILED_CONFIRMED' then
        return -6
    end
    if new_record.attempt ~= max_attempt + 1 or
       new_record.prepared_state_version ~= expected + 1 then return -5 end
    if type(new_record.transitions) ~= 'table' or
       #new_record.transitions ~= 1 then return -5 end
else
    if type(old_record) ~= 'table' or old_record.status ~= old_status then
        return -4
    end
    if count_entries(candidate.intent_ledger) ~=
       count_entries(current.intent_ledger) then return -5 end
    for key, record in pairs(current.intent_ledger) do
        if candidate.intent_ledger[key] == nil then return -5 end
        if key ~= intent_id and
           not deep_equal(record, candidate.intent_ledger[key]) then return -5 end
    end
    if has_value(old_record.canonical_request_binding) ~=
       has_value(new_record.canonical_request_binding) then return -9 end
    if has_value(old_record.canonical_request_binding) and
       (old_record.canonical_request_binding ~=
        new_record.canonical_request_binding or
        new_record.canonical_request_binding ~= ARGV[12]) then return -9 end
    if not has_value(old_record.canonical_request_binding) and
       ARGV[12] ~= '' then return -9 end
    local immutable = {'intent_id','step_id','attempt','connector','target',
      'request_fingerprint','correlation_id','prepared_at',
      'client_timeout_seconds','settlement_lag_seconds','reconcile_after',
      'prepared_state_version','risk_acceptance_id'}
    for _, field in ipairs(immutable) do
        if not deep_equal(old_record[field], new_record[field]) then
            return -5
        end
    end
    if type(old_record.transitions) ~= 'table' or
       type(new_record.transitions) ~= 'table' or
       #new_record.transitions ~= #old_record.transitions + 1 then return -5 end
    for i = 1, #old_record.transitions do
        if not deep_equal(old_record.transitions[i], new_record.transitions[i]) then
            return -5
        end
    end
end

if new_status == 'FIRED_UNCONFIRMED' then
    if type(new_record.reconciliation) ~= 'table' or
       type(new_record.reconciliation.attempt_count) ~= 'number' or
       type(new_record.reconciliation.next_check_at) ~= 'number' then return -5 end
    if old_status == 'ABOUT_TO_FIRE' and
       (new_record.reconciliation.attempt_count ~= 0 or
        new_record.reconciliation.next_check_at < new_record.reconcile_after) then
        return -5
    end
    if old_status == 'FIRED_UNCONFIRMED' and
       new_record.reconciliation.attempt_count ~=
       old_record.reconciliation.attempt_count + 1 then return -5 end
end

if type(new_record.transitions) ~= 'table' or #new_record.transitions < 1 then
    return -5
end
local audit = new_record.transitions[#new_record.transitions]
if type(audit) ~= 'table' or audit.old_state ~= old_status or
   audit.new_state ~= new_status then return -5 end

local unresolved_by_step = {}
local attempts_by_step = {}
for key, record in pairs(candidate.intent_ledger) do
    if type(record) ~= 'table' or record.intent_id ~= key or
       type(record.step_id) ~= 'string' or type(record.attempt) ~= 'number' then
        return -5
    end
    local attempt_key = record.step_id .. ':' .. tostring(record.attempt)
    if attempts_by_step[attempt_key] then return -5 end
    attempts_by_step[attempt_key] = true
    if record.status == 'ABOUT_TO_FIRE' or
       record.status == 'FIRED_UNCONFIRMED' then
        if unresolved_by_step[record.step_id] then return -5 end
        unresolved_by_step[record.step_id] = true
    end
end
if next(unresolved_by_step) ~= nil and ttl < tonumber(ARGV[9]) then return -5 end

redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[8])
return 1
"""

_INTENT_CAS_SCRIPT = build_lua_state_validation_script(_INTENT_CAS_SCRIPT_BODY)


_PREFLIGHT_SCRIPT_BODY = r"""
local raw = redis.call('GET', KEYS[1])
if not raw then return -3 end
local state_check = aep_json_member_check(raw)
if state_check == 1 then return -11 end
if state_check ~= 0 then return -10 end

-- Preflight is read-only, but its classification follows the same strict
-- raw-before-lease ordering as every state mutation path.
if redis.call('GET', KEYS[2]) ~= ARGV[1] then return -1 end
local ttl = redis.call('PTTL', KEYS[2])
if ttl < tonumber(ARGV[4]) then return -2 end
local ok, state = pcall(cjson.decode, raw)
if not ok or type(state) ~= 'table' or type(state.intent_ledger) ~= 'table' then
    return -3
end
if state.version ~= tonumber(ARGV[2]) then return -4 end
local intent = state.intent_ledger[ARGV[3]]
if type(intent) ~= 'table' or intent.status ~= 'ABOUT_TO_FIRE' then return -5 end
if type(intent.canonical_request_binding) ~= 'string' then return -6 end
if intent.canonical_request_binding ~= ARGV[6] then return -8 end
local ok_binding, binding = pcall(
    cjson.decode, intent.canonical_request_binding
)
if not ok_binding or type(binding) ~= 'table' then return -8 end
if binding.request_binding_digest ~= ARGV[5] then return -7 end
return ttl
"""

_PREFLIGHT_SCRIPT = build_lua_state_validation_script(_PREFLIGHT_SCRIPT_BODY)


def evidence_hash(evidence: Mapping[str, Any] | str | None) -> str:
    allowed_keys = frozenset({"class", "call_id", "exception_type", "reason"})
    if isinstance(evidence, str):
        canonical_value: Any = _safe_persisted_value(evidence, field="evidence")
    else:
        supplied = evidence or {}
        if type(supplied) is not dict or not set(supplied).issubset(allowed_keys):
            raise IntentInvariantError("unsafe evidence rejected")
        canonical_value = {}
        for key, value in supplied.items():
            if value is None:
                canonical_value[key] = None
            elif isinstance(value, str):
                canonical_value[key] = _safe_persisted_value(
                    value, field="evidence"
                )
            else:
                raise IntentInvariantError("unsafe evidence rejected")
    canonical = json.dumps(
        canonical_value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IntentLedgerStore:
    """Typed Phase 2 state access and atomic intent transition persistence."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        unresolved_ttl_seconds: int = MINIMUM_UNRESOLVED_TTL_SECONDS,
    ) -> None:
        if unresolved_ttl_seconds < MINIMUM_UNRESOLVED_TTL_SECONDS:
            raise ValueError(
                "unresolved_ttl_seconds must retain 24h reconciliation plus "
                "7d operator history (at least 31 days)"
            )
        self.redis = redis_client
        self.unresolved_ttl_seconds = unresolved_ttl_seconds
        self._intent_cas = redis_client.register_script(_INTENT_CAS_SCRIPT)
        self._preflight = redis_client.register_script(_PREFLIGHT_SCRIPT)

    @asynccontextmanager
    async def pinned_connection(self) -> AsyncIterator[Redis]:
        """Yield a single-connection client for CAS plus durability barrier."""

        async with self.redis.client() as connection:
            yield connection

    async def redis_time(self, *, connection: Redis | None = None) -> float:
        client = connection or self.redis
        seconds, microseconds = await client.time()
        return float(seconds) + float(microseconds) / 1_000_000

    async def get_execution(
        self, execution_id: str, *, connection: Redis | None = None
    ) -> Phase2ExecutionState | None:
        client = connection or self.redis
        adapter = RedisStorageAdapter(client)
        state = await adapter.get_state(execution_id)
        if state is None:
            return None
        try:
            return Phase2ExecutionState.model_validate(state.model_dump())
        except ValueError:
            await adapter._quarantine(
                execution_id,
                reason="phase2-intent-validation",
                raw=encode_state(state.model_dump(mode="json")),
            )
            raise StateCorruptionError(
                f"execution {execution_id} failed typed Phase 2 state validation"
            ) from None

    async def create_intent(
        self,
        *,
        execution_id: str,
        expected_version: int,
        lock_token: str,
        step_id: str,
        connector: str,
        target: str,
        request_fingerprint: str,
        request_binding: PersistedRequestBinding | None = None,
        client_timeout_seconds: float,
        settlement_lag_seconds: float,
        buffer_margin_seconds: float,
        actor: str,
        reason: str = "write-ahead-before-dispatch",
        intent_id: str | None = None,
        correlation_id: str | None = None,
        risk_acceptance_id: str | None = None,
        connection: Redis | None = None,
    ) -> IntentRecord:
        client = connection or self.redis
        if request_binding is None:
            raise IntentBindingError("new intent requires an immutable request binding")
        current = await self.get_execution(execution_id, connection=client)
        if current is None:
            raise IntentInvariantError(
                "Phase 2 requires an existing execution state before intent creation"
            )
        now = await self.redis_time(connection=client)
        new_intent_id = intent_id or str(uuid.uuid4())
        new_correlation_id = correlation_id or str(uuid.uuid4())
        now_ms = int(now * 1000)
        if (
            request_binding.execution_id != execution_id
            or request_binding.step_id != step_id
            or request_binding.intent_id != new_intent_id
            or request_binding.correlation_id != new_correlation_id
            or request_binding.connector_operation != connector
            or request_binding.safe_descriptor.redacted_target != target
            or request_binding.request_fingerprint != request_fingerprint
            or now_ms > request_binding.intent_creation_not_after_ms
            or request_binding.retention_not_after_ms
            < now_ms + self.unresolved_ttl_seconds * 1000
        ):
            raise IntentBindingError("request binding does not match intent creation")
        attempts = [
            item.attempt
            for item in current.intent_ledger.values()
            if item.step_id == step_id
        ]
        attempt = max(attempts, default=0) + 1
        audit = IntentAuditEntry(
            old_state=NONE_STATE,
            new_state=IntentStatus.ABOUT_TO_FIRE,
            redis_time=now,
            actor=actor,
            reason=reason,
            evidence_hash=evidence_hash({"reason": reason}),
        )
        record = IntentRecord(
            intent_id=new_intent_id,
            step_id=step_id,
            attempt=attempt,
            connector=connector,
            target=target,
            request_fingerprint=request_fingerprint,
            request_binding=request_binding,
            canonical_request_binding=canonical_request_binding_bytes(
                request_binding
            ).decode("utf-8"),
            correlation_id=new_correlation_id,
            status=IntentStatus.ABOUT_TO_FIRE,
            prepared_at=now,
            client_timeout_seconds=client_timeout_seconds,
            settlement_lag_seconds=settlement_lag_seconds,
            reconcile_after=(
                now
                + client_timeout_seconds
                + buffer_margin_seconds
                + settlement_lag_seconds
            ),
            prepared_state_version=expected_version + 1,
            transitions=(audit,),
            risk_acceptance_id=risk_acceptance_id,
        )
        ledger = dict(current.intent_ledger)
        ledger[new_intent_id] = record
        # Do not let the Python unresolved-step validator become the
        # authoritative rejection for a racing normal creation.  The record
        # itself and the stored current state are already typed; the complete
        # predecessor/global-fence decision is made inside the same Lua CAS
        # that can perform SET.
        candidate = Phase2ExecutionState.model_construct(
            **{
                **current.model_dump(),
                "intent_ledger": ledger,
                "phase2_managed": PHASE2_MANAGED_MARKER,
                "version": expected_version + 1,
                "status": AEPStatus.PROCESSING,
                "updated_at": now,
            }
        )
        await self.commit_transition(
            candidate,
            intent_id=new_intent_id,
            old_status=NONE_STATE,
            new_status=IntentStatus.ABOUT_TO_FIRE,
            expected_version=expected_version,
            lock_token=lock_token,
            connection=client,
        )
        return record

    async def transition_intent(
        self,
        *,
        execution_id: str,
        intent_id: str,
        expected_version: int,
        lock_token: str,
        new_status: IntentStatus,
        actor: str,
        reason: str,
        evidence: Mapping[str, Any] | str | None = None,
        observation_class: str | None = None,
        observation_detail: str | None = None,
        external_reference: str | None = None,
        reconciliation: ReconciliationProgress | None = None,
        connection: Redis | None = None,
    ) -> IntentRecord:
        client = connection or self.redis
        current = await self.get_execution(execution_id, connection=client)
        if current is None or intent_id not in current.intent_ledger:
            raise IllegalIntentTransitionError(
                f"cannot transition absent intent {intent_id} from NONE to "
                f"{new_status.value}"
            )
        old = current.intent_ledger[intent_id]
        edge = (old.status.value, new_status.value)
        require_legal_intent_transition(*edge)
        now = await self.redis_time(connection=client)
        audit = IntentAuditEntry(
            old_state=old.status.value,
            new_state=new_status,
            redis_time=now,
            actor=actor,
            reason=reason,
            evidence_hash=evidence_hash(evidence),
        )
        observation = old.last_observation
        if observation_class is not None:
            observation = IntentObservation(
                evidence_class=observation_class,
                observed_at=now,
                detail=observation_detail or reason,
            )
        next_reconciliation = reconciliation
        if new_status is IntentStatus.FIRED_UNCONFIRMED and reconciliation is None:
            if old.status is IntentStatus.FIRED_UNCONFIRMED:
                raise IntentInvariantError(
                    "FIRED_UNCONFIRMED self-transition requires updated "
                    "reconciliation progress"
                )
            next_reconciliation = ReconciliationProgress(
                attempt_count=0,
                next_check_at=max(old.reconcile_after, now),
            )
        if next_reconciliation is None:
            next_reconciliation = old.reconciliation
        updated = old.model_copy(
            update={
                "status": new_status,
                "external_reference": external_reference
                if external_reference is not None
                else old.external_reference,
                "last_observation": observation,
                "reconciliation": next_reconciliation,
                "transitions": (*old.transitions, audit),
            }
        )
        # model_copy does not revalidate updates in Pydantic v2.
        updated = IntentRecord.model_validate(updated.model_dump())
        ledger = dict(current.intent_ledger)
        ledger[intent_id] = updated
        top_status = (
            AEPStatus.PAUSED
            if new_status
            in {IntentStatus.FIRED_UNCONFIRMED, IntentStatus.PERMANENTLY_AMBIGUOUS}
            else current.status
        )
        candidate = Phase2ExecutionState.model_validate(
            {
                **current.model_dump(),
                "intent_ledger": ledger,
                "phase2_managed": PHASE2_MANAGED_MARKER,
                "version": expected_version + 1,
                "status": top_status,
                "updated_at": now,
            }
        )
        await self.commit_transition(
            candidate,
            intent_id=intent_id,
            old_status=old.status.value,
            new_status=new_status,
            expected_version=expected_version,
            lock_token=lock_token,
            connection=client,
        )
        return updated

    async def commit_transition(
        self,
        candidate: Phase2ExecutionState,
        *,
        intent_id: str,
        old_status: str,
        new_status: IntentStatus,
        expected_version: int,
        lock_token: str,
        ttl_seconds: int | None = None,
        connection: Redis | None = None,
    ) -> None:
        """Commit a typed candidate after the Lua script rechecks all rules."""

        client = connection or self.redis
        ttl = ttl_seconds or self.unresolved_ttl_seconds
        payload = encode_state(candidate.model_dump(mode="json"))
        candidate_record = candidate.intent_ledger.get(intent_id)
        canonical_binding = (
            candidate_record.canonical_request_binding
            if isinstance(candidate_record, IntentRecord)
            and candidate_record.canonical_request_binding is not None
            else (
                candidate_record.get("canonical_request_binding") or ""
                if isinstance(candidate_record, dict)
                else ""
            )
        )
        try:
            result = await self._intent_cas(
                keys=[
                    f"aep:state:{candidate.execution_id}",
                    f"aep:lock:{candidate.execution_id}",
                ],
                args=[
                    payload,
                    lock_token,
                    str(expected_version),
                    intent_id,
                    old_status,
                    new_status.value,
                    str(time.time()),
                    str(ttl),
                    str(MINIMUM_UNRESOLVED_TTL_SECONDS),
                    PHASE2_MANAGED_MARKER,
                    str(int(candidate.updated_at * 1000) + ttl * 1000),
                    canonical_binding,
                ],
                client=client,
            )
        except (IntentStateError, LockAcquisitionError, StaleWriteError):
            raise
        except Exception:
            raise IntentStateError("intent state CAS operation failed") from None
        code = int(result)
        await RedisStorageAdapter(client)._raise_lua_state_validation(
            candidate.execution_id, code
        )
        if code == 1:
            return
        if code == -1:
            raise StaleWriteError(
                f"intent CAS expected version {expected_version} is stale"
            )
        if code == -2:
            raise IntentInvariantError("stored Phase 2 execution is missing/corrupt")
        if code == -3:
            raise LockAcquisitionError(
                "intent CAS rejected a missing, expired, or mismatched lease token"
            )
        if code == -4:
            raise IllegalIntentTransitionError(
                f"illegal intent transition {old_status} -> {new_status.value}"
            )
        if code == -5:
            raise IntentInvariantError(
                "intent CAS rejected an immutable, append-only, uniqueness, "
                "attempt, deletion, or TTL invariant"
            )
        if code == -6:
            raise IntentCreationEligibilityError(
                "normal intent creation requires no predecessor or latest "
                "FAILED_CONFIRMED; a raw risk_acceptance_id is not "
                "authenticated authorization"
            )
        if code == -7:
            raise ExecutionIntentFenceError(
                "normal intent creation is blocked by the execution-wide "
                "uniqueness/fence rule while the execution is PAUSED or any "
                "intent is ABOUT_TO_FIRE, FIRED_UNCONFIRMED, or "
                "PERMANENTLY_AMBIGUOUS"
            )
        if code == -8:
            raise IntentInvariantError(
                "intent CAS rejected removal or modification of the immutable "
                "Phase 2 managed-state marker"
            )
        if code == -9:
            raise IntentBindingError(
                "intent CAS rejected a missing, transplanted, or under-retained binding"
            )
        raise IntentStateError("intent state CAS returned an unrecognized result")

    async def preflight(
        self,
        *,
        execution_id: str,
        intent_id: str,
        prepared_state_version: int,
        lock_token: str,
        required_ttl_ms: int,
        request_binding: PersistedRequestBinding,
        connection: Redis | None = None,
    ) -> int:
        client = connection or self.redis
        if not isinstance(request_binding, PersistedRequestBinding):
            raise IntentBindingError(
                "pre-dispatch request binding is absent or invalid"
            )
        binding_payload = canonical_request_binding_bytes(request_binding).decode(
            "utf-8"
        )
        try:
            result = int(
                await self._preflight(
                    keys=[
                        f"aep:state:{execution_id}",
                        f"aep:lock:{execution_id}",
                    ],
                    args=[
                        lock_token,
                        str(prepared_state_version),
                        intent_id,
                        str(required_ttl_ms),
                        request_binding.request_binding_digest,
                        binding_payload,
                    ],
                    client=client,
                )
            )
        except Exception:
            raise IntentPreflightError(
                "pre-dispatch state validation could not complete"
            ) from None
        if result >= 0:
            return result
        await RedisStorageAdapter(client)._raise_lua_state_validation(
            execution_id, result
        )
        reasons = {
            -1: "lease token is no longer owned",
            -2: "lease TTL is below client timeout plus safety buffer",
            -3: "execution state is missing or corrupt",
            -4: "execution version no longer matches prepared_state_version",
            -5: "intent is no longer ABOUT_TO_FIRE",
        }
        if result in {-6, -7, -8}:
            raise IntentBindingError(
                "pre-dispatch request binding is absent or does not match"
            )
        raise IntentPreflightError(
            reasons.get(result, "pre-dispatch state validation was rejected")
        )
