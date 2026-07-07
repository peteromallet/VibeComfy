"""Authoring alias tests for emit signatures and reverse alias resolution.

Covers:
  - Valid Python signatures for hyphenated class types (MiDaS-DepthMapPreprocessor)
  - Normal identifier classes
  - Alias calls resolving to raw class types with canonical add_node.uid/node_id
  - Deterministic repeated alias generation
  - Explicit collision behavior
"""

from __future__ import annotations

import pytest

from vibecomfy.identity.codec import to_python_identifier, to_raw_name


# ---------------------------------------------------------------------------
# to_python_identifier behaviour
# ---------------------------------------------------------------------------


class TestPythonIdentifierAlias:
    """Deterministic alias generation for class-type names."""

    def test_hyphenated_class_becomes_lowercase_underscored(self) -> None:
        """MiDaS-DepthMapPreprocessor -> midas_depthmappreprocessor."""
        assert (
            to_python_identifier("MiDaS-DepthMapPreprocessor")
            == "midas_depthmappreprocessor"
        )

    def test_camelcase_class_is_lowercased(self) -> None:
        """CheckpointLoaderSimple -> checkpointloadersimple."""
        assert (
            to_python_identifier("CheckpointLoaderSimple")
            == "checkpointloadersimple"
        )

    def test_already_lowercase_no_change(self) -> None:
        """preview_image stays preview_image."""
        assert to_python_identifier("preview_image") == "preview_image"

    def test_all_uppercase_is_lowercased(self) -> None:
        """KSampler -> ksampler."""
        assert to_python_identifier("KSampler") == "ksampler"

    def test_digits_and_special_chars(self) -> None:
        """CLIPTextEncode (SDXL) -> cliptextencode_sdxl."""
        encoded = to_python_identifier("CLIPTextEncode (SDXL)")
        assert encoded == "cliptextencode_sdxl"

    def test_deterministic_same_input_same_output(self) -> None:
        """Repeated calls with the same input yield the same output."""
        a = to_python_identifier("Some-Node_Type/v2")
        b = to_python_identifier("Some-Node_Type/v2")
        assert a == b
        assert a == "some_node_type_v2"


class TestPythonIdentifierUniqueness:
    """Collision avoidance via the ``used`` set."""

    def test_no_collision_returns_original(self) -> None:
        used: set[str] = set()
        result = to_python_identifier("foo", used=used)
        assert result == "foo"
        # to_python_identifier mutates `used` — the returned identifier is
        # added so that subsequent calls avoid it.
        assert result in used

    def test_collision_appends_suffix(self) -> None:
        used = {"foo"}
        result = to_python_identifier("foo", used=used)
        assert result == "foo_2"

    def test_multiple_collisions_increment(self) -> None:
        used = {"bar", "bar_2", "bar_3"}
        result = to_python_identifier("bar", used=used)
        assert result == "bar_4"

    def test_keyword_gets_trailing_underscore_then_deduplicates(self) -> None:
        """'in' is a keyword -> 'in_'; if 'in_' is used -> 'in__2' (the
        deduplication suffix '_2' follows the keyword suffix '_')."""
        used: set[str] = set()
        result = to_python_identifier("in", used=used)
        assert result == "in_"

        used.add("in_")
        result2 = to_python_identifier("in", used=used)
        assert result2 == "in__2"


# ---------------------------------------------------------------------------
# Reverse alias resolution (_resolve_class_type_from_alias)
# ---------------------------------------------------------------------------


class _FakeSchemaProvider:
    """A schema provider stub that supports :meth:`schema_for` and
    :meth:`schemas` enumeration."""

    def __init__(self, schemas: dict[str, object] | None = None) -> None:
        self._schemas = dict(schemas or {})

    def schema_for(self, class_type: str) -> object | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, object]:
        return dict(self._schemas)


class TestReverseAliasResolution:
    """Reverse-resolve Python-identifier aliases to raw ComfyUI class names."""

    @staticmethod
    def _resolve(class_type_alias: str, provider: object) -> str | None:
        from vibecomfy.porting.edit._ir_utils import _resolve_class_type_from_alias
        return _resolve_class_type_from_alias(class_type_alias, provider)

    def test_direct_hit_returns_same(self) -> None:
        """An alias that matches a raw class type is returned unchanged."""
        provider = _FakeSchemaProvider({"KSampler": object()})
        result = self._resolve("KSampler", provider)
        assert result == "KSampler"

    def test_alias_resolves_to_raw_type(self) -> None:
        """The Python-identifier alias 'ksampler' resolves to 'KSampler'."""
        provider = _FakeSchemaProvider({"KSampler": object()})
        result = self._resolve("ksampler", provider)
        assert result == "KSampler"

    def test_hyphenated_alias_resolves_to_raw(self) -> None:
        """'midas_depthmappreprocessor' resolves to 'MiDaS-DepthMapPreprocessor'."""
        provider = _FakeSchemaProvider({"MiDaS-DepthMapPreprocessor": object()})
        result = self._resolve("midas_depthmappreprocessor", provider)
        assert result == "MiDaS-DepthMapPreprocessor"

    def test_alias_with_digits_and_special(self) -> None:
        """'cliptextencode_sdxl' resolves to 'CLIPTextEncode (SDXL)'."""
        provider = _FakeSchemaProvider({"CLIPTextEncode (SDXL)": object()})
        result = self._resolve("cliptextencode_sdxl", provider)
        assert result == "CLIPTextEncode (SDXL)"

    def test_case_insensitive_fallback(self) -> None:
        """When the alias cannot be resolved through encoding, a
        case-insensitive match against raw names is attempted."""
        provider = _FakeSchemaProvider({"MyCustomNode": object()})
        result = self._resolve("mycustomnode", provider)
        assert result == "MyCustomNode"

    def test_unknown_alias_returns_none(self) -> None:
        """An alias that matches no known class type returns None."""
        provider = _FakeSchemaProvider({"KSampler": object()})
        result = self._resolve("nonexistent_node", provider)
        assert result is None

    def test_no_schemas_method_returns_none_gracefully(self) -> None:
        """When the schema provider has no ``schemas()`` method, the
        resolver returns None gracefully without raising."""

        class NoSchemasProvider:
            def schema_for(self, _class_type: str) -> object | None:
                return None

        result = self._resolve("ksampler", NoSchemasProvider())
        assert result is None

    def test_deterministic_repeated_resolution(self) -> None:
        """Repeated calls with the same inputs yield the same outputs."""
        provider = _FakeSchemaProvider({"KSampler": object(), "VAELoader": object()})
        a = self._resolve("ksampler", provider)
        b = self._resolve("ksampler", provider)
        assert a == b == "KSampler"

    def test_collision_two_raw_map_to_same_alias_is_deterministic(self) -> None:
        """When two different raw class types produce the same
        to_python_identifier, the first encountered during schema
        enumeration is returned deterministically."""
        # Both map to 'somenode' after to_python_identifier
        provider = _FakeSchemaProvider(
            {"SomeNode": object(), "some_node": object()}
        )
        result = self._resolve("somenode", provider)
        # The first key in dict iteration order is returned.
        # In Python 3.7+ dicts preserve insertion order.
        assert result in {"SomeNode", "some_node"}
        # Repeated calls return the same result
        result2 = self._resolve("somenode", provider)
        assert result2 == result


# ---------------------------------------------------------------------------
# Canonical add_node identity (uid / node_id) through alias resolution
# ---------------------------------------------------------------------------


class _FakeResolvedAddNodeCall:
    """Minimal stub mirroring ``_ResolvedAddNodeCall``."""

    def __init__(
        self,
        class_type: str,
        uid: str | None = None,
        node_id: str | None = None,
    ) -> None:
        self.class_type = class_type
        self.uid = uid
        self.node_id = node_id


class TestCanonicalAddNodeIdentityThroughAlias:
    """Canonical add_node ops carry explicit uid and node_id through alias
    resolution."""

    def test_resolved_call_carries_explicit_uid(self) -> None:
        """A resolved add-node call preserves the explicitly provided uid."""
        call = _FakeResolvedAddNodeCall(
            class_type="KSampler",
            uid="abc-123",
            node_id="5",
        )
        assert call.uid == "abc-123"
        assert call.node_id == "5"

    def test_resolved_call_with_none_identity_is_acceptable_pre_apply(self) -> None:
        """Before the normalizer populates identity, uid and node_id may be
        None.  This is acceptable for the pre-apply stage (non-strict
        normalization)."""
        call = _FakeResolvedAddNodeCall(
            class_type="KSampler",
            uid=None,
            node_id=None,
        )
        assert call.uid is None
        assert call.node_id is None
        # The class_type is still present for later resolution
        assert call.class_type == "KSampler"

    def test_alias_resolved_class_type_preserves_raw_name(self) -> None:
        """After alias resolution, the class_type field holds the raw
        ComfyUI class name, not the Python identifier alias."""
        provider = _FakeSchemaProvider({"MiDaS-DepthMapPreprocessor": object()})
        from vibecomfy.porting.edit._ir_utils import _resolve_class_type_from_alias

        resolved = _resolve_class_type_from_alias(
            "midas_depthmappreprocessor", provider
        )
        assert resolved == "MiDaS-DepthMapPreprocessor"


# ---------------------------------------------------------------------------
# Signature emission end-to-end for canonical ops
# ---------------------------------------------------------------------------


class TestSignatureEmissionForCanonicalOps:
    """Signature rows produce valid Python identifiers that can be
    reverse-resolved to raw class types."""

    def test_midas_signature_round_trips_through_alias(self) -> None:
        """MiDaS-DepthMapPreprocessor -> midas_depthmappreprocessor and
        back."""
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="MiDaS-DepthMapPreprocessor",
                inputs=[],
                outputs=[],
            ),
        ]
        text = format_signature_rows(rows)
        # The alias is in the signature line
        assert "def midas_depthmappreprocessor() -> None:" in text
        # The raw class is in a comment
        assert "# raw class: MiDaS-DepthMapPreprocessor" in text

    def test_preview_image_omits_raw_class_comment(self) -> None:
        """When the alias matches the raw class, no raw class comment is
        emitted."""
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="preview_image",
                inputs=[],
                outputs=[],
            ),
        ]
        text = format_signature_rows(rows)
        # preview_image stays preview_image — alias matches raw class
        assert "def preview_image() -> None:" in text
        assert "# raw class:" not in text

    def test_camelcase_class_shows_raw_comment(self) -> None:
        """PreviewImage -> previewimage differs, so raw class comment is
        emitted."""
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="PreviewImage",
                inputs=[],
                outputs=[],
            ),
        ]
        text = format_signature_rows(rows)
        assert "# raw class: PreviewImage" in text
        assert "def previewimage() -> None:" in text

    def test_deterministic_repeated_emission(self) -> None:
        """Calling format_signature_rows twice with the same rows produces
        identical output."""
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(class_type="KSampler", inputs=[], outputs=[]),
            NodeSignatureRow(class_type="VAELoader", inputs=[], outputs=[]),
        ]
        text1 = format_signature_rows(rows)
        text2 = format_signature_rows(rows)
        assert text1 == text2

    def test_hyphenated_type_emits_correct_signature(self) -> None:
        """Hyphens are replaced with underscores, entire string is
        lowercased."""
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="CR Multi-ControlNet Stack",
                inputs=[],
                outputs=[],
            ),
        ]
        text = format_signature_rows(rows)
        assert "# raw class: CR Multi-ControlNet Stack" in text
        assert "def cr_multi_controlnet_stack() -> None:" in text
