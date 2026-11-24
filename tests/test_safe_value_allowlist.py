"""Coverage for the code-owned allowlist in request_binding.

`SafeValueRule` decides what may be persisted in a request binding, and
`_validate_safe_value` enforces it. Both are pure rejection logic: the
allowlist is only worth as much as the branches that refuse everything
outside it, and those branches are unreachable from the happy path.

Two properties matter here beyond raw coverage:

  * a malformed *rule* is refused at construction, so a mis-specified
    allowlist cannot silently admit values at runtime;
  * canonicalization is refused for anything non-deterministic (floats,
    non-NFC text, duplicate keys, unbounded depth), because the binding
    digest is only meaningful if the bytes are reproducible.
"""

from __future__ import annotations

import pytest

from aep_core.core.request_binding import (
    CanonicalizationError,
    SafeValueKind,
    SafeValueRule,
    UnsafeRequestError,
    _canonical_value,
    _decode_canonical,
    _require_nfc,
    _safe_identifier,
    _validate_safe_field_name,
    _validate_safe_value,
    canonical_json_bytes,
)

STRING_RULE = SafeValueRule(kind=SafeValueKind.STRING, allowed_strings=frozenset({"red", "blue"}))
INTEGER_RULE = SafeValueRule(kind=SafeValueKind.INTEGER, minimum_integer=0, maximum_integer=10)
NULL_RULE = SafeValueRule(kind=SafeValueKind.NULL)
BOOLEAN_RULE = SafeValueRule(kind=SafeValueKind.BOOLEAN)


# ===========================================================================
# Rule construction -- a malformed allowlist must not be constructible
# ===========================================================================


@pytest.mark.parametrize("kind", ["nope", None, 42, object()])
def test_a_rule_with_an_unknown_kind_is_refused(kind):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=kind)


@pytest.mark.parametrize("value", [b"red", 42, None])
def test_a_rule_whose_allowlist_holds_a_non_string_is_refused(value):
    with pytest.raises((UnsafeRequestError, TypeError)):
        SafeValueRule(kind=SafeValueKind.STRING, allowed_strings=frozenset({value}))


@pytest.mark.parametrize("value", ["has space", "-leading", "x" * 200, ""])
def test_a_rule_whose_allowlist_holds_an_unsafe_identifier_is_refused(value):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.STRING, allowed_strings=frozenset({value}))


@pytest.mark.parametrize("maximum_items", [-1, 257, 1.5, None, "8"])
def test_a_rule_with_an_out_of_bounds_item_cap_is_refused(maximum_items):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(
            kind=SafeValueKind.ARRAY, array_item=INTEGER_RULE, maximum_items=maximum_items
        )


@pytest.mark.parametrize("bound", [1.5, "3", object()])
def test_a_rule_with_a_non_integer_bound_is_refused(bound):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.INTEGER, minimum_integer=bound)
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.INTEGER, maximum_integer=bound)


def test_a_rule_with_an_inverted_integer_range_is_refused():
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.INTEGER, minimum_integer=10, maximum_integer=0)


@pytest.mark.parametrize("fields", [[], "fields", 42, (("a", INTEGER_RULE),)])
def test_a_rule_whose_object_fields_are_not_a_dict_is_refused(fields):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.OBJECT, object_fields=fields)


def test_a_rule_whose_object_field_maps_to_a_non_rule_is_refused():
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.OBJECT, object_fields={"colour": "red"})


@pytest.mark.parametrize("name", ["Colour", "9lives", "has-dash", "x" * 100, "password"])
def test_a_rule_whose_object_field_name_is_unsafe_is_refused(name):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.OBJECT, object_fields={name: INTEGER_RULE})


def test_a_rule_whose_variant_is_not_a_rule_is_refused():
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.ONE_OF, variants=(INTEGER_RULE, "nope"))


def test_a_string_rule_with_an_empty_allowlist_is_refused():
    """An empty allowlist admits nothing; it is a specification error."""
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.STRING)


def test_an_array_rule_without_an_item_rule_is_refused():
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.ARRAY)


def test_an_object_rule_without_field_rules_is_refused():
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(kind=SafeValueKind.OBJECT)


@pytest.mark.parametrize("count", [0, 1, 9])
def test_a_one_of_rule_needs_between_two_and_eight_variants(count):
    with pytest.raises(UnsafeRequestError):
        SafeValueRule(
            kind=SafeValueKind.ONE_OF, variants=tuple([INTEGER_RULE] * count)
        )


def test_rule_repr_does_not_disclose_the_allowlist():
    """The allowlist can encode business vocabulary; keep it out of logs."""
    rendered = repr(STRING_RULE)

    assert rendered == "SafeValueRule(kind='string', values=<allowlisted>)"
    assert "red" not in rendered


# ===========================================================================
# Value validation -- the enforcement side
# ===========================================================================


def test_null_rule_admits_only_none():
    _validate_safe_value(None, NULL_RULE)
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(0, NULL_RULE)


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_boolean_rule_refuses_truthy_lookalikes(value):
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(value, BOOLEAN_RULE)


def test_boolean_rule_admits_real_booleans():
    _validate_safe_value(True, BOOLEAN_RULE)
    _validate_safe_value(False, BOOLEAN_RULE)


def test_integer_rule_refuses_a_bool_masquerading_as_an_int():
    """bool is a subclass of int; type() is not, so True must not pass."""
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(True, INTEGER_RULE)


@pytest.mark.parametrize("value", [-1, 11, 100])
def test_integer_rule_enforces_its_bounds(value):
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(value, INTEGER_RULE)


@pytest.mark.parametrize("value", [0, 5, 10])
def test_integer_rule_admits_values_inside_its_bounds(value):
    _validate_safe_value(value, INTEGER_RULE)


@pytest.mark.parametrize("value", ["green", "", 1, None])
def test_string_rule_refuses_anything_outside_the_allowlist(value):
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(value, STRING_RULE)


def test_string_rule_admits_allowlisted_values():
    _validate_safe_value("red", STRING_RULE)


def test_array_rule_refuses_a_non_list():
    array_rule = SafeValueRule(kind=SafeValueKind.ARRAY, array_item=INTEGER_RULE)

    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(("a",), array_rule)


def test_array_rule_enforces_its_item_cap():
    array_rule = SafeValueRule(
        kind=SafeValueKind.ARRAY, array_item=INTEGER_RULE, maximum_items=2
    )

    _validate_safe_value([1, 2], array_rule)
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value([1, 2, 3], array_rule)


def test_array_rule_validates_every_item():
    array_rule = SafeValueRule(kind=SafeValueKind.ARRAY, array_item=INTEGER_RULE)

    with pytest.raises(UnsafeRequestError):
        _validate_safe_value([1, 2, 99], array_rule)


def test_object_rule_requires_exactly_its_declared_fields():
    object_rule = SafeValueRule(
        kind=SafeValueKind.OBJECT,
        object_fields={"count": INTEGER_RULE, "colour": STRING_RULE},
    )

    _validate_safe_value({"count": 1, "colour": "red"}, object_rule)

    with pytest.raises(UnsafeRequestError):  # missing field
        _validate_safe_value({"count": 1}, object_rule)
    with pytest.raises(UnsafeRequestError):  # extra field
        _validate_safe_value(
            {"count": 1, "colour": "red", "extra": 1}, object_rule
        )
    with pytest.raises(UnsafeRequestError):  # not an object
        _validate_safe_value([1], object_rule)


def test_object_rule_validates_every_member():
    object_rule = SafeValueRule(
        kind=SafeValueKind.OBJECT, object_fields={"count": INTEGER_RULE}
    )

    with pytest.raises(UnsafeRequestError):
        _validate_safe_value({"count": 99}, object_rule)


def test_one_of_requires_exactly_one_matching_variant():
    """Ambiguity is refused: two matches is as bad as none."""
    unambiguous = SafeValueRule(
        kind=SafeValueKind.ONE_OF, variants=(NULL_RULE, INTEGER_RULE)
    )

    _validate_safe_value(None, unambiguous)
    _validate_safe_value(5, unambiguous)
    with pytest.raises(UnsafeRequestError):
        _validate_safe_value("red", unambiguous)


def test_one_of_refuses_a_value_matching_two_variants():
    ambiguous = SafeValueRule(
        kind=SafeValueKind.ONE_OF,
        variants=(
            SafeValueRule(kind=SafeValueKind.INTEGER, minimum_integer=0, maximum_integer=10),
            SafeValueRule(kind=SafeValueKind.INTEGER, minimum_integer=5, maximum_integer=15),
        ),
    )

    with pytest.raises(UnsafeRequestError):
        _validate_safe_value(7, ambiguous)


# ===========================================================================
# Canonicalization -- the digest is only meaningful if the bytes reproduce
# ===========================================================================


# Built from code points, not typed literally: these two strings render
# identically, so an editor or git filter normalising this source file would
# otherwise silently collapse the two cases into one and the test would still
# pass while testing nothing. The file is pure ASCII for the same reason.
NFD_E_ACUTE = "e" + chr(0x0301)  # 'e' + COMBINING ACUTE ACCENT
NFC_E_ACUTE = chr(0x00E9)        # LATIN SMALL LETTER E WITH ACUTE


def test_non_nfc_text_is_refused():
    """The two spellings render identically; only the NFC one may persist."""
    assert NFD_E_ACUTE != NFC_E_ACUTE

    with pytest.raises(CanonicalizationError):
        _require_nfc(NFD_E_ACUTE)


def test_nfc_text_passes_through():
    assert _require_nfc(NFC_E_ACUTE) == NFC_E_ACUTE


def test_text_beyond_the_byte_ceiling_is_refused():
    with pytest.raises(CanonicalizationError):
        _require_nfc("a" * 8_193)


def test_a_lone_surrogate_is_refused():
    with pytest.raises(CanonicalizationError):
        _require_nfc("\ud800")


@pytest.mark.parametrize("value", [1.5, float("nan"), b"bytes", object(), {1, 2}])
def test_canonicalization_refuses_types_it_cannot_reproduce(value):
    """Floats are excluded by design: the schema uses integer minor units."""
    with pytest.raises(CanonicalizationError):
        _canonical_value(value)


def test_canonicalization_refuses_an_integer_beyond_the_safe_range():
    with pytest.raises(CanonicalizationError):
        _canonical_value((1 << 53))


def test_canonicalization_admits_the_largest_safe_integer():
    assert _canonical_value((1 << 53) - 1) == (1 << 53) - 1


def test_canonicalization_refuses_a_non_string_mapping_key():
    with pytest.raises(CanonicalizationError):
        _canonical_value({1: "a"})


def test_canonicalization_refuses_keys_that_collide_after_normalisation():
    """Two NFC-distinct spellings of one key would make the digest ambiguous."""
    with pytest.raises(CanonicalizationError):
        _canonical_value({NFC_E_ACUTE: 1, NFD_E_ACUTE: 2})


def test_canonicalization_refuses_excessive_depth():
    deep = value = {}
    for _ in range(200):
        value["child"] = {}
        value = value["child"]

    with pytest.raises(CanonicalizationError):
        _canonical_value(deep)


def test_tuples_canonicalize_as_arrays():
    assert _canonical_value(("a", "b")) == ["a", "b"]


def test_canonical_json_is_sorted_and_compact():
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_json_refuses_a_float():
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes({"a": 1.5})


# --- Decoding is the inverse, and rejects anything not already canonical ---


def test_decoding_requires_bytes():
    with pytest.raises(CanonicalizationError):
        _decode_canonical('{"a":1}')


def test_decoding_refuses_non_canonical_byte_order():
    """Correct JSON, wrong bytes: re-encoding must reproduce the input exactly."""
    with pytest.raises(CanonicalizationError):
        _decode_canonical(b'{"b":1,"a":2}')


def test_decoding_refuses_whitespace_padded_json():
    with pytest.raises(CanonicalizationError):
        _decode_canonical(b'{"a": 1}')


def test_decoding_refuses_duplicate_keys():
    with pytest.raises(CanonicalizationError):
        _decode_canonical(b'{"a":1,"a":2}')


@pytest.mark.parametrize("raw", [b'{"a":1.5}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_decoding_refuses_non_integer_numerics(raw):
    with pytest.raises(CanonicalizationError):
        _decode_canonical(raw)


def test_decoding_refuses_malformed_json():
    with pytest.raises(CanonicalizationError):
        _decode_canonical(b"{not json")


def test_decoding_refuses_invalid_utf8():
    with pytest.raises(CanonicalizationError):
        _decode_canonical(b'{"a":"\xff"}')


def test_canonical_bytes_round_trip():
    value = {"a": 1, "b": ["x", "y"], "c": {"d": True, "e": None}}

    assert _decode_canonical(canonical_json_bytes(value)) == value


# ===========================================================================
# Identifier and field-name safety
# ===========================================================================


@pytest.mark.parametrize("value", ["Colour", "9lives", "has-dash", "", "x" * 100])
def test_unsafe_field_names_are_refused(value):
    with pytest.raises(UnsafeRequestError):
        _validate_safe_field_name(value)


@pytest.mark.parametrize(
    "value", ["password", "auth_token", "card_number", "session_cookie"]
)
def test_field_names_carrying_sensitive_tokens_are_refused(value):
    """Name-based screening: a field called 'password' never becomes a safe field."""
    with pytest.raises(UnsafeRequestError):
        _validate_safe_field_name(value)


@pytest.mark.parametrize("value", ["colour", "item_count", "line_items_2"])
def test_ordinary_field_names_are_admitted(value):
    assert _validate_safe_field_name(value) == value


@pytest.mark.parametrize("value", [None, 42, b"id", "", "-leading", "x" * 200])
def test_unsafe_identifiers_are_refused(value):
    with pytest.raises(UnsafeRequestError):
        _safe_identifier(value)


@pytest.mark.parametrize("value", ["orders.v1", "acme:billing/charge", "a-b_c"])
def test_ordinary_identifiers_are_admitted(value):
    assert _safe_identifier(value) == value
