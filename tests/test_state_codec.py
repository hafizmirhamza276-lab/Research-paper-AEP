"""Strict execution-state JSON codec and Redis Lua validation regressions."""

from __future__ import annotations

import math

import pytest

from aep_core.core.exceptions import (
    AmbiguousStateError,
    StateCorruptionError,
    StateSerializationError,
)
from aep_core.core.state_codec import (
    LUA_JSON_AMBIGUOUS,
    LUA_JSON_INVALID,
    LUA_JSON_VALID,
    build_lua_state_validation_script,
    decode_state,
    encode_state,
)


DUPLICATE_OBJECTS = [
    pytest.param('{"status":"IDLE","status":"PAUSED"}', id="top-status"),
    pytest.param('{"version":1,"version":2}', id="version"),
    pytest.param(
        '{"phase2_managed":"intent-ledger-v1","phase2_managed":null}',
        id="phase2-marker",
    ),
    pytest.param(
        '{"intent_ledger":{},"intent_ledger":{}}',
        id="complete-intent-ledger-identical",
    ),
    pytest.param(
        '{"intent_ledger":{"intent-1":{},"intent-1":{"status":"ABOUT_TO_FIRE"}}}',
        id="duplicate-intent-id-conflicting",
    ),
    pytest.param(
        '{"intent_ledger":{"intent-1":{"status":"ABOUT_TO_FIRE",'
        '"status":"FAILED_CONFIRMED"}}}',
        id="intent-status-blocking-nonblocking",
    ),
    pytest.param(
        '{"intent_ledger":{"intent-1":{"step_id":"step-a","step_id":"step-b"}}}',
        id="step-id",
    ),
    pytest.param(
        '{"intent_ledger":{"intent-1":{"attempt":1,"attempt":2}}}',
        id="attempt-number",
    ),
    pytest.param(
        '{"intent_ledger":{"intent-1":{"transitions":[],"transitions":[]}}}',
        id="transition-history-identical",
    ),
    pytest.param(
        '{"intent_ledger":{"intent-1":{"reconcile_after":1.0,'
        '"reconcile_after":2.0}}}',
        id="retention-related-field",
    ),
    pytest.param('{"unknown":1,"unknown":1}', id="unknown-identical"),
    pytest.param(r'{"status":"IDLE","statu\u0073":"PAUSED"}', id="escaped-equivalent"),
    pytest.param(
        '{"context_data":{"metadata":{"region":"a","region":"b"}}}',
        id="nested-metadata",
    ),
    pytest.param(
        '{"context_data":{"items":[{"key":1,"key":2}]}}',
        id="object-inside-array",
    ),
]


VALID_OBJECTS = [
    pytest.param('["same","same",1,1]', id="repeated-array-values"),
    pytest.param('{"status":"IDLE","status_detail":"IDLE"}', id="similar-names"),
    pytest.param(
        '{"text":"quotes: \\\" braces: {} comma: , colon: :"}',
        id="syntax-characters-inside-string",
    ),
    pytest.param(
        r'{"text":"escaped quote: \" and backslash: \\"}',
        id="escaped-quotes-and-backslashes",
    ),
    pytest.param('{"empty_object":{},"empty_array":[]}', id="empty-containers"),
    pytest.param('{"message":"سلام دنیا — 正常"}', id="unicode-values"),
    pytest.param(
        '{"execution_id":"5e82c60c-f00c-4c4f-bdac-a11d2210d7a5",'
        '"status":"IDLE","version":1,"schema_version":"1.0.0",'
        '"intent_ledger":{},"phase2_managed":null,"context_data":{},'
        '"updated_at":1.0}',
        id="historical-phase1-record",
    ),
    pytest.param(
        '{"execution_id":"5e82c60c-f00c-4c4f-bdac-a11d2210d7a5",'
        '"status":"PROCESSING","version":2,"schema_version":"1.0.0",'
        '"intent_ledger":{},"phase2_managed":"intent-ledger-v1",'
        '"context_data":{},"updated_at":1.0}',
        id="historical-phase2-envelope",
    ),
]


MALFORMED_JSON = [
    pytest.param("{", id="unterminated-object"),
    pytest.param('{"x":1', id="missing-close-brace"),
    pytest.param('{"x" 1}', id="missing-colon"),
    pytest.param('{"x":"unterminated}', id="unterminated-string"),
    pytest.param("NaN", id="nonstandard-nan"),
    pytest.param("Infinity", id="nonstandard-infinity"),
]


INVALID_UTF8_JSON = [
    pytest.param(b'{"x":"\xff"}', id="byte-ff"),
    pytest.param(b'{"x":"\x80"}', id="isolated-continuation-80"),
    pytest.param(b'{"x":"\xbf"}', id="isolated-continuation-bf"),
    pytest.param(b'{"x":"\xc0\x80"}', id="illegal-c0-overlong-two-byte"),
    pytest.param(b'{"x":"\xc1\xbf"}', id="illegal-c1-overlong-two-byte"),
    pytest.param(b'{"x":"\xe0\x80\x80"}', id="overlong-three-byte-min"),
    pytest.param(b'{"x":"\xe0\x9f\xbf"}', id="overlong-three-byte-max"),
    pytest.param(b'{"x":"\xf0\x80\x80\x80"}', id="overlong-four-byte-min"),
    pytest.param(b'{"x":"\xf0\x8f\xbf\xbf"}', id="overlong-four-byte-max"),
    pytest.param(b'{"x":"\xc2"}', id="truncated-two-byte"),
    pytest.param(b'{"x":"\xe1\x80"}', id="truncated-three-byte"),
    pytest.param(b'{"x":"\xf1\x80\x80"}', id="truncated-four-byte"),
    pytest.param(b'{"x":"\xed\xa0\x80"}', id="surrogate-d800"),
    pytest.param(b'{"x":"\xed\xbf\xbf"}', id="surrogate-dfff"),
    pytest.param(b'{"x":"\xf4\x90\x80\x80"}', id="above-unicode-maximum"),
    *[
        pytest.param(
            b'{"x":"' + bytes([lead]) + b'"}',
            id=f"illegal-leading-{lead:02x}",
        )
        for lead in range(0xF5, 0x100)
    ],
    pytest.param(b'{"\xff":1}', id="invalid-root-key"),
    pytest.param(b'{"root":"\xff"}', id="invalid-root-value"),
    pytest.param(b'{"root":{"\xff":1}}', id="invalid-nested-key"),
    pytest.param(b'{"root":{"value":"\xff"}}', id="invalid-nested-value"),
    pytest.param(
        b'{"root":[{"\xff":1}]}', id="invalid-array-object-key"
    ),
    pytest.param(
        b'{"root":[{"value":"\xff"}]}', id="invalid-array-object-value"
    ),
]


VALID_UTF8_JSON = [
    pytest.param(b'{"x":"ASCII"}', id="ascii"),
    pytest.param(b'{"x":"\x7f"}', id="one-byte-upper-boundary"),
    pytest.param(b'{"x":"\xc2\x80"}', id="two-byte-lower-boundary"),
    pytest.param(b'{"x":"\xdf\xbf"}', id="two-byte-upper-boundary"),
    pytest.param(b'{"x":"\xe0\xa0\x80"}', id="three-byte-lower-boundary"),
    pytest.param(b'{"x":"\xed\x9f\xbf"}', id="before-surrogate-boundary"),
    pytest.param(b'{"x":"\xee\x80\x80"}', id="after-surrogate-boundary"),
    pytest.param(b'{"x":"\xef\xbf\xbf"}', id="three-byte-upper-boundary"),
    pytest.param(b'{"x":"\xf0\x90\x80\x80"}', id="four-byte-lower-boundary"),
    pytest.param(b'{"x":"\xf4\x8f\xbf\xbf"}', id="four-byte-upper-boundary"),
    pytest.param(
        '{"x":"\u0633\u0644\u0627\u0645 \u062f\u0646\u06cc\u0627"}'.encode(),
        id="urdu",
    ),
    pytest.param('{"x":"\u4e2d\u6587"}'.encode(), id="chinese"),
    pytest.param('{"x":"caf\u00e9"}'.encode(), id="accented"),
    pytest.param('{"x":"\U0001f600"}'.encode(), id="emoji"),
    pytest.param(
        rb'{"x":"\u00e9\u4e2d\ud83d\ude00"}', id="escaped-unicode"
    ),
]


@pytest.mark.parametrize("raw", DUPLICATE_OBJECTS)
def test_python_decoder_rejects_duplicate_members_before_mapping(raw):
    with pytest.raises(AmbiguousStateError, match="ambiguous serialized state"):
        decode_state(raw)


@pytest.mark.parametrize("raw", VALID_OBJECTS)
def test_python_decoder_accepts_unambiguous_json_without_false_positive(raw):
    decode_state(raw)


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_python_decoder_rejects_nonstandard_numeric_constants(raw):
    with pytest.raises(StateCorruptionError) as exc_info:
        decode_state(raw)
    assert isinstance(exc_info.value, StateSerializationError) is False


@pytest.mark.parametrize("raw", MALFORMED_JSON)
def test_python_decoder_rejects_malformed_json_as_corruption(raw):
    with pytest.raises(StateCorruptionError) as exc_info:
        decode_state(raw)
    assert not isinstance(exc_info.value, AmbiguousStateError)


@pytest.mark.parametrize("raw", INVALID_UTF8_JSON)
def test_python_decoder_rejects_every_invalid_utf8_class(raw):
    with pytest.raises(StateCorruptionError) as exc_info:
        decode_state(raw)
    assert not isinstance(exc_info.value, AmbiguousStateError)


def test_deterministic_encoder_uses_utf8_sorted_keys_and_compact_separators():
    encoded = encode_state({"z": "سلام", "a": [1, 2]})
    assert encoded == '{"a":[1,2],"z":"سلام"}'
    assert encoded.encode("utf-8").decode("utf-8") == encoded


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_deterministic_encoder_rejects_nonfinite_numbers(value):
    with pytest.raises(StateSerializationError, match="finite JSON numbers"):
        encode_state({"value": value})


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", DUPLICATE_OBJECTS)
async def test_lua_validator_rejects_duplicate_members_at_every_depth(
    redis_client, cjson_available, raw
):
    if not cjson_available:
        pytest.skip("cjson is required for exact Lua validation")
    script = redis_client.register_script(
        build_lua_state_validation_script("return aep_json_member_check(ARGV[1])")
    )
    assert int(await script(args=[raw])) == LUA_JSON_AMBIGUOUS


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", VALID_OBJECTS)
async def test_lua_validator_accepts_valid_json_without_false_positive(
    redis_client, cjson_available, raw
):
    if not cjson_available:
        pytest.skip("cjson is required for exact Lua validation")
    script = redis_client.register_script(
        build_lua_state_validation_script("return aep_json_member_check(ARGV[1])")
    )
    assert int(await script(args=[raw])) == LUA_JSON_VALID


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", MALFORMED_JSON)
async def test_lua_validator_keeps_malformed_json_distinct_from_duplicates(
    redis_client, cjson_available, raw
):
    if not cjson_available:
        pytest.skip("cjson is required for exact Lua validation")
    script = redis_client.register_script(
        build_lua_state_validation_script("return aep_json_member_check(ARGV[1])")
    )
    assert int(await script(args=[raw])) == LUA_JSON_INVALID


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", INVALID_UTF8_JSON)
async def test_lua_validator_rejects_invalid_utf8_before_json_interpretation(
    redis_client, cjson_available, raw
):
    if not cjson_available:
        pytest.skip("cjson is required for exact Lua validation")
    script = redis_client.register_script(
        build_lua_state_validation_script("return aep_json_member_check(ARGV[1])")
    )
    assert int(await script(args=[raw])) == LUA_JSON_INVALID


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", VALID_UTF8_JSON)
async def test_lua_validator_accepts_utf8_boundaries_and_multilingual_text(
    redis_client, cjson_available, raw
):
    if not cjson_available:
        pytest.skip("cjson is required for exact Lua validation")
    script = redis_client.register_script(
        build_lua_state_validation_script("return aep_json_member_check(ARGV[1])")
    )
    assert int(await script(args=[raw])) == LUA_JSON_VALID
