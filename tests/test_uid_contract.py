"""Unit tests for the frozen uid contract (T2).

Covers make_uid/parse_uid round-trip (scalar collapse and scope:local form),
mint_local_uid precedence, and the NOT-a-hash / NOT-uuid4 invariant.
"""
from __future__ import annotations

from vibecomfy.porting.uid import make_uid, mint_local_uid, parse_uid


# ---------------------------------------------------------------------------
# make_uid / parse_uid round-trip
# ---------------------------------------------------------------------------


def test_make_uid_scalar_collapse():
    """scope_path == '' returns local_uid unchanged."""
    assert make_uid("", "42") == "42"


def test_make_uid_scoped():
    """Non-empty scope_path composes as scope#local (SD3 separator)."""
    assert make_uid("myscope", "42") == "myscope#42"


def test_parse_uid_bare_scalar():
    """Bare uid (no separator) returns ('', uid)."""
    assert parse_uid("42") == ("", "42")


def test_parse_uid_scoped():
    """Scoped uid splits into (scope_path, local_uid)."""
    assert parse_uid("scope#local") == ("scope", "local")


def test_parse_uid_splits_on_rightmost_separator():
    """A chained scope_path (joined with '/') survives — split is rightmost '#'."""
    assert parse_uid("a/b/c#5") == ("a/b/c", "5")


def test_parse_uid_ignores_colon_inside_sg_key():
    """':' inside an sg_key is not a separator and is preserved verbatim."""
    assert parse_uid("name:abcd1234#7") == ("name:abcd1234", "7")


def test_round_trip_multi_scope_chain():
    """make_uid->parse_uid is identity for a multi-scope chain."""
    scope = "outer:aa/inner:bb"
    uid = make_uid(scope, "9")
    assert parse_uid(uid) == (scope, "9")


def test_flat_uid_unchanged_no_migration():
    """Flat uids (scope_path == '') are byte-identical to M1.5 — no separator added."""
    assert make_uid("", "42") == "42"
    assert "#" not in make_uid("", "42")
    assert parse_uid("42") == ("", "42")


def test_round_trip_scalar():
    """make_uid then parse_uid is the identity for scalar form."""
    uid = make_uid("", "99")
    assert parse_uid(uid) == ("", "99")


def test_round_trip_scoped():
    """make_uid then parse_uid is the identity for scoped form."""
    uid = make_uid("scope", "local")
    assert parse_uid(uid) == ("scope", "local")


def test_parse_uid_scope_local_label():
    """scope#local form round-trips with no data loss."""
    scope, local = parse_uid("scope#local")
    assert make_uid(scope, local) == "scope#local"


# ---------------------------------------------------------------------------
# mint_local_uid precedence
# ---------------------------------------------------------------------------


def test_mint_precedence_vibecomfy_uid_wins():
    """properties['vibecomfy_uid'] is the highest-priority source."""
    raw = {"id": 42, "properties": {"vibecomfy_uid": "custom_uid"}}
    assert mint_local_uid(raw, "fallback") == "custom_uid"


def test_mint_precedence_litegraph_id():
    """Litegraph id used when no vibecomfy_uid is present."""
    raw = {"id": 42, "properties": {}}
    assert mint_local_uid(raw, "fallback") == "42"


def test_mint_precedence_fallback_when_none():
    """fallback_id is used when raw_ui_node is None."""
    assert mint_local_uid(None, "fallback") == "fallback"


def test_mint_precedence_fallback_when_no_id():
    """fallback_id used when raw node has no 'id' key."""
    raw = {"type": "KSampler"}
    assert mint_local_uid(raw, "fallback") == "fallback"


def test_mint_no_properties_key():
    """Litegraph id used when 'properties' key is absent entirely."""
    raw = {"id": 5}
    assert mint_local_uid(raw, "fallback") == "5"


# ---------------------------------------------------------------------------
# NOT a content hash or uuid4 — equals the source integer id
# ---------------------------------------------------------------------------


def test_mint_equals_source_integer_id():
    """The minted uid equals str(litegraph integer id) — not a content hash or uuid4."""
    raw = {"id": 7}
    result = mint_local_uid(raw, "0")
    assert result == "7"


def test_mint_not_uuid4():
    """Result is not a uuid4 (36 chars with hyphens in 8-4-4-4-12 form)."""
    raw = {"id": 7}
    result = mint_local_uid(raw, "0")
    # uuid4 is 36 chars with dashes, e.g. '550e8400-e29b-41d4-a716-446655440000'
    assert len(result) < 36
    assert "-" not in result


def test_mint_not_content_hash():
    """Two nodes with different ids but same type get different uids (not content-derived)."""
    raw_a = {"id": 1, "type": "CLIPTextEncode", "widgets_values": ["prompt"]}
    raw_b = {"id": 2, "type": "CLIPTextEncode", "widgets_values": ["prompt"]}
    uid_a = mint_local_uid(raw_a, "1")
    uid_b = mint_local_uid(raw_b, "2")
    # If uid were content-based, identical content would yield the same uid
    assert uid_a != uid_b
    assert uid_a == "1"
    assert uid_b == "2"
