"""Strict, deterministic execution-state JSON handling for Python and Lua."""

from __future__ import annotations

import json
import math
from typing import Any

from src.core.exceptions import (
    AmbiguousStateError,
    StateCorruptionError,
    StateSerializationError,
)


LUA_JSON_INVALID = -1
LUA_JSON_VALID = 0
LUA_JSON_AMBIGUOUS = 1

# Stable cross-script return codes for failures at the raw state boundary.
# Every authoritative Lua path uses these codes, and Python translates them
# here so callers never branch on script-specific implementation details.
LUA_STORED_STATE_INVALID = -10
LUA_STORED_STATE_AMBIGUOUS = -11
LUA_CANDIDATE_STATE_INVALID = -12
LUA_CANDIDATE_STATE_AMBIGUOUS = -13


def lua_state_validation_failure(
    code: int,
) -> tuple[StateCorruptionError | StateSerializationError, str | None] | None:
    """Map shared Lua raw-state codes to stable domain failures.

    The optional string is a bounded quarantine reason for persisted-state
    failures. Candidate failures are never evidence that persisted state is
    corrupt, so they are not quarantined.
    """

    if code == LUA_STORED_STATE_INVALID:
        return (
            StateCorruptionError(
                "stored state is corrupt or unversioned; persisted state "
                "is not valid strict UTF-8 JSON"
            ),
            "invalid-serialization",
        )
    if code == LUA_STORED_STATE_AMBIGUOUS:
        return (
            AmbiguousStateError(
                "ambiguous serialized state: duplicate JSON object member name"
            ),
            "ambiguous-serialization",
        )
    if code in {
        LUA_CANDIDATE_STATE_INVALID,
        LUA_CANDIDATE_STATE_AMBIGUOUS,
    }:
        return (
            StateSerializationError(
                "candidate execution state is not valid unambiguous UTF-8 JSON"
            ),
            None,
        )
    return None


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise AmbiguousStateError(
                "ambiguous serialized state: duplicate JSON object member name"
            )
        result[name] = value
    return result


def _reject_constant(_: str) -> None:
    raise StateCorruptionError("persisted state is not strict JSON")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise StateCorruptionError("persisted state contains a non-finite number")
    return parsed


def decode_state(raw: str | bytes | bytearray) -> Any:
    """Decode strict UTF-8 JSON and reject duplicate members before mappings.

    ``object_pairs_hook`` receives decoded names, so a literal member name and
    its JSON Unicode-escaped equivalent compare as the same name.
    """

    try:
        if isinstance(raw, (bytes, bytearray)):
            text = bytes(raw).decode("utf-8", errors="strict")
        elif isinstance(raw, str):
            raw.encode("utf-8", errors="strict")
            text = raw
        else:
            raise TypeError("execution state must be UTF-8 text or bytes")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except AmbiguousStateError:
        raise
    except StateCorruptionError:
        raise
    except (json.JSONDecodeError, RecursionError, TypeError, UnicodeError, ValueError):
        raise StateCorruptionError("persisted state is not valid UTF-8 JSON") from None


def encode_state(value: Any) -> str:
    """Return the one deterministic UTF-8 JSON representation used for state."""

    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        encoded.encode("utf-8", errors="strict")
        return encoded
    except ValueError:
        raise StateSerializationError(
            "execution state requires finite JSON numbers and valid Unicode"
        ) from None
    except (TypeError, UnicodeError):
        raise StateSerializationError(
            "execution state is not deterministically JSON serializable"
        ) from None


# Redis 7.2 embeds Lua 5.1 and cjson but exposes neither a strict UTF-8 check
# nor a duplicate-preserving JSON decoder. The byte scanner rejects every
# non-shortest, surrogate, out-of-range, truncated, or otherwise illegal
# UTF-8 sequence before cjson or JSON structure is consulted. The recursive
# descent component then scans the same exact bytes for duplicate members.
# It decodes each object name independently with cjson only after locating the
# complete JSON string token, then compares decoded names within that object.
# Thus escaped-equivalent names collide while punctuation inside strings does
# not affect object/array parsing.  A depth cap turns adversarial nesting into
# a typed corruption result rather than an unbounded Lua stack failure.
LUA_STATE_JSON_VALIDATOR = r"""
local function aep_utf8_check(raw)
    if type(raw) ~= 'string' then return false end
    local length = string.len(raw)
    local position = 1

    local function continuation(byte)
        return byte ~= nil and byte >= 128 and byte <= 191
    end

    while position <= length do
        local first = string.byte(raw, position)
        if first <= 127 then
            position = position + 1
        elseif first >= 194 and first <= 223 then
            if not continuation(string.byte(raw, position + 1)) then
                return false
            end
            position = position + 2
        elseif first == 224 then
            local second = string.byte(raw, position + 1)
            local third = string.byte(raw, position + 2)
            if second == nil or second < 160 or second > 191 or
               not continuation(third) then return false end
            position = position + 3
        elseif first >= 225 and first <= 236 then
            if not continuation(string.byte(raw, position + 1)) or
               not continuation(string.byte(raw, position + 2)) then
                return false
            end
            position = position + 3
        elseif first == 237 then
            local second = string.byte(raw, position + 1)
            local third = string.byte(raw, position + 2)
            if second == nil or second < 128 or second > 159 or
               not continuation(third) then return false end
            position = position + 3
        elseif first >= 238 and first <= 239 then
            if not continuation(string.byte(raw, position + 1)) or
               not continuation(string.byte(raw, position + 2)) then
                return false
            end
            position = position + 3
        elseif first == 240 then
            local second = string.byte(raw, position + 1)
            if second == nil or second < 144 or second > 191 or
               not continuation(string.byte(raw, position + 2)) or
               not continuation(string.byte(raw, position + 3)) then
                return false
            end
            position = position + 4
        elseif first >= 241 and first <= 243 then
            if not continuation(string.byte(raw, position + 1)) or
               not continuation(string.byte(raw, position + 2)) or
               not continuation(string.byte(raw, position + 3)) then
                return false
            end
            position = position + 4
        elseif first == 244 then
            local second = string.byte(raw, position + 1)
            if second == nil or second < 128 or second > 143 or
               not continuation(string.byte(raw, position + 2)) or
               not continuation(string.byte(raw, position + 3)) then
                return false
            end
            position = position + 4
        else
            return false
        end
    end
    return true
end

local function aep_json_member_check(raw)
    if type(raw) ~= 'string' then return -1 end
    if not aep_utf8_check(raw) then return -1 end
    local length = string.len(raw)
    local position = 1
    local max_depth = 128

    local function byte_at(index)
        return string.byte(raw, index)
    end

    local function skip_whitespace()
        while position <= length do
            local byte = byte_at(position)
            if byte == 32 or byte == 9 or byte == 10 or byte == 13 then
                position = position + 1
            else
                break
            end
        end
    end

    local function is_hex(byte)
        return (byte >= 48 and byte <= 57) or
               (byte >= 65 and byte <= 70) or
               (byte >= 97 and byte <= 102)
    end

    local function parse_string(decode_name)
        if byte_at(position) ~= 34 then return false, nil end
        local start_position = position
        position = position + 1
        while position <= length do
            local byte = byte_at(position)
            if byte == 34 then
                position = position + 1
                if not decode_name then return true, nil end
                local token = string.sub(raw, start_position, position - 1)
                local ok, decoded = pcall(cjson.decode, token)
                if not ok or type(decoded) ~= 'string' then return false, nil end
                return true, decoded
            end
            if byte == 92 then
                position = position + 1
                if position > length then return false, nil end
                local escaped = byte_at(position)
                if escaped == 117 then
                    if position + 4 > length then return false, nil end
                    for offset = 1, 4 do
                        if not is_hex(byte_at(position + offset)) then
                            return false, nil
                        end
                    end
                    position = position + 5
                elseif escaped == 34 or escaped == 92 or escaped == 47 or
                       escaped == 98 or escaped == 102 or escaped == 110 or
                       escaped == 114 or escaped == 116 then
                    position = position + 1
                else
                    return false, nil
                end
            elseif byte < 32 then
                return false, nil
            else
                position = position + 1
            end
        end
        return false, nil
    end

    local function is_digit(byte)
        return byte ~= nil and byte >= 48 and byte <= 57
    end

    local function parse_number()
        local start_position = position
        if byte_at(position) == 45 then position = position + 1 end
        local first = byte_at(position)
        if first == 48 then
            position = position + 1
            if is_digit(byte_at(position)) then return false end
        elseif first ~= nil and first >= 49 and first <= 57 then
            repeat position = position + 1 until not is_digit(byte_at(position))
        else
            return false
        end
        if byte_at(position) == 46 then
            position = position + 1
            if not is_digit(byte_at(position)) then return false end
            repeat position = position + 1 until not is_digit(byte_at(position))
        end
        local exponent = byte_at(position)
        if exponent == 69 or exponent == 101 then
            position = position + 1
            local sign = byte_at(position)
            if sign == 43 or sign == 45 then position = position + 1 end
            if not is_digit(byte_at(position)) then return false end
            repeat position = position + 1 until not is_digit(byte_at(position))
        end
        local number = tonumber(string.sub(raw, start_position, position - 1))
        return number ~= nil and number ~= math.huge and number ~= -math.huge
    end

    local parse_value

    local function parse_object(depth)
        if depth > max_depth then return -1 end
        position = position + 1
        skip_whitespace()
        if byte_at(position) == 125 then
            position = position + 1
            return 0
        end
        local seen = {}
        while position <= length do
            local ok, name = parse_string(true)
            if not ok then return -1 end
            if seen[name] then return 1 end
            seen[name] = true
            skip_whitespace()
            if byte_at(position) ~= 58 then return -1 end
            position = position + 1
            local result = parse_value(depth + 1)
            if result ~= 0 then return result end
            skip_whitespace()
            local byte = byte_at(position)
            if byte == 125 then
                position = position + 1
                return 0
            end
            if byte ~= 44 then return -1 end
            position = position + 1
            skip_whitespace()
        end
        return -1
    end

    local function parse_array(depth)
        if depth > max_depth then return -1 end
        position = position + 1
        skip_whitespace()
        if byte_at(position) == 93 then
            position = position + 1
            return 0
        end
        while position <= length do
            local result = parse_value(depth + 1)
            if result ~= 0 then return result end
            skip_whitespace()
            local byte = byte_at(position)
            if byte == 93 then
                position = position + 1
                return 0
            end
            if byte ~= 44 then return -1 end
            position = position + 1
            skip_whitespace()
        end
        return -1
    end

    parse_value = function(depth)
        if depth > max_depth then return -1 end
        skip_whitespace()
        local byte = byte_at(position)
        if byte == 123 then return parse_object(depth) end
        if byte == 91 then return parse_array(depth) end
        if byte == 34 then
            local ok = parse_string(false)
            if ok then return 0 else return -1 end
        end
        if byte == 116 and string.sub(raw, position, position + 3) == 'true' then
            position = position + 4
            return 0
        end
        if byte == 102 and string.sub(raw, position, position + 4) == 'false' then
            position = position + 5
            return 0
        end
        if byte == 110 and string.sub(raw, position, position + 3) == 'null' then
            position = position + 4
            return 0
        end
        if byte == 45 or is_digit(byte) then
            if parse_number() then return 0 else return -1 end
        end
        return -1
    end

    skip_whitespace()
    local result = parse_value(0)
    if result ~= 0 then return result end
    skip_whitespace()
    if position <= length then return -1 end
    local ok = pcall(cjson.decode, raw)
    if not ok then return -1 end
    return 0
end
"""


def build_lua_state_validation_script(body: str) -> str:
    """Prefix a Redis Lua body with the shared raw-state JSON validator."""

    return f"{LUA_STATE_JSON_VALIDATOR}\n{body}"
