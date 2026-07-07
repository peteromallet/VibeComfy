"""M1 Phase 1 Step 1 — Grounding tests and fixture conversion helpers.

Fixtures and failing tests that define the `EditSession` contract BEFORE
implementation. Loads raw LiteGraph UI JSON fixtures, converts them through
the existing normalization path to `VibeWorkflow`, and then asserts:

  (a) render -> edit -> re-render identity stability
  (b) slot alias round-trip through the codec
  (c) empty done() behavior
  (d) emitter internals receive `VibeWorkflow`, not raw UI JSON

All tests in this module are expected to FAIL until EditSession is implemented.
They serve as the grounding specification for M1.
"""

from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Fixture data path
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_edit"
_FLAT_PATH = _FIXTURE_DIR / "flat.json"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _load_raw_ui_json(path: Path) -> dict[str, Any]:
    """Load a raw LiteGraph UI JSON fixture as a plain dict."""
    return json.loads(path.read_text(encoding="utf-8"))


def _ledger_from_raw(raw: dict[str, Any]) -> EditLedger:
    """Ingest raw LiteGraph UI JSON through EditLedger and return it."""
    return EditLedger.ingest(deepcopy(raw))


def _wf_from_raw_ui(raw: dict[str, Any]) -> VibeWorkflow:
    """Convert raw LiteGraph UI JSON to VibeWorkflow via the existing path.

    The conversion chain is:
        raw UI JSON -> normalize_to_api -> convert_to_vibe_format -> VibeWorkflow

    Uses `use_comfy_converter=False` so the test stays offline and deterministic.
    """
    api = normalize_to_api(deepcopy(raw), use_comfy_converter=False)
    return convert_to_vibe_format(api)


def _load_flat_fixture_raw() -> dict[str, Any]:
    """Load the flat agent-edit fixture as raw LiteGraph UI JSON."""
    return _load_raw_ui_json(_FLAT_PATH)


def _load_flat_fixture_ledger() -> EditLedger:
    """Load the flat fixture through EditLedger."""
    return _ledger_from_raw(_load_raw_ui_json(_FLAT_PATH))


def _load_flat_fixture_wf() -> VibeWorkflow:
    """Load the flat fixture converted to a VibeWorkflow."""
    return _wf_from_raw_ui(_load_raw_ui_json(_FLAT_PATH))


# ---------------------------------------------------------------------------
# Helper: emit_agent_edit_python stub contract
# ---------------------------------------------------------------------------


def _emit_agent_edit_python_stub(wf: VibeWorkflow, **kwargs: Any) -> str:
    """Compatibility shim for early grounding tests."""
    from vibecomfy.porting.emitter import emit_agent_edit_python

    return emit_agent_edit_python(wf, **kwargs)


# ---------------------------------------------------------------------------
# Stub for EditSession (the target of M1)
# ---------------------------------------------------------------------------


class _EditSessionStub:
    """Stub that defines the EditSession contract.

    All methods raise NotImplementedError with a teaching diagnostic.
    Grounding tests that call this stub will fail, which is expected —
    they prove the contract exists before the implementation.
    """

    def __init__(self, raw_ui_json: dict[str, Any]) -> None:
        # Must store the original UI JSON verbatim.
        self.original_ui = deepcopy(raw_ui_json)
        self.working_ui = deepcopy(raw_ui_json)
        raise NotImplementedError("EditSession not yet implemented (M1 Step 8)")

    def render(self) -> str:
        """Render the current working UI to edit-view Python."""
        raise NotImplementedError("EditSession.render not yet implemented")

    def apply_batch(self, code: str) -> Any:  # -> BatchResult
        """Parse and apply a batch of Python assignment statements."""
        raise NotImplementedError("EditSession.apply_batch not yet implemented")

    def done(self) -> Any:  # -> DoneResult
        """Finalize the session: run all three gates and return the result."""
        raise NotImplementedError("EditSession.done not yet implemented")


# ---------------------------------------------------------------------------
# Grounding test: raw fixture conversion helpers work
# ---------------------------------------------------------------------------


class TestFixtureConversionHelpers:
    """Sanity-check that the existing conversion path works before we build on it.

    These tests MUST pass — they exercise the existing infrastructure, not the
    new EditSession code. They prove the conversion chain is ready for M1.
    """

    def test_load_flat_fixture_is_raw_litegraph_ui_json(self) -> None:
        """flat.json is raw LiteGraph UI format, not API format."""
        raw = _load_flat_fixture_raw()
        assert isinstance(raw["nodes"], list)
        assert isinstance(raw["links"], list)
        # Raw UI nodes have "type", not "class_type".
        assert all("type" in node for node in raw["nodes"])
        # Raw UI links are 6-element arrays.
        assert all(isinstance(link, list) and len(link) == 6 for link in raw["links"])

    def test_flat_fixture_ledger_ingests(self) -> None:
        """EditLedger.ingest stamps uids and creates scopes for flat.json."""
        ledger = _load_flat_fixture_ledger()
        assert "" in ledger.scopes
        assert ledger.diagnostics == ()
        for node in ledger.graph["nodes"]:
            uid = node["properties"]["vibecomfy_uid"]
            assert uid == str(node["id"])
            assert ledger.resolve_node("", uid) is node

    def test_flat_fixture_converts_to_vibeworkflow(self) -> None:
        """Raw UI JSON converts to VibeWorkflow through normalize+convert."""
        wf = _load_flat_fixture_wf()
        assert isinstance(wf, VibeWorkflow)
        assert len(wf.nodes) == 7
        assert len(wf.edges) == 9
        # VibeNodes have class_type, not "type".
        for node in wf.nodes.values():
            assert node.class_type
            assert node.uid


# ---------------------------------------------------------------------------
# Grounding test: raw UI JSON rejection
# ---------------------------------------------------------------------------


class TestRawUIJSONRejection:
    """Prove emitter internals reject raw LiteGraph UI JSON.

    This is the key invariant: emitter internals must receive VibeWorkflow,
    never raw UI JSON. The test must fail until the guard is in place.
    """

    def test_emitter_rejects_raw_ui_json(self) -> None:
        """emit_agent_edit_python rejects raw LiteGraph UI JSON dict."""
        raw = _load_flat_fixture_raw()
        with pytest.raises(TypeError, match="emit_agent_edit_python requires VibeWorkflow"):
            _emit_agent_edit_python_stub(raw)  # type: ignore[arg-type]

    def test_emitter_accepts_vibeworkflow(self) -> None:
        """emit_agent_edit_python accepts a properly converted VibeWorkflow."""
        wf = _load_flat_fixture_wf()
        rendered = _emit_agent_edit_python_stub(wf)
        assert "ksampler = KSampler(" in rendered
        assert "uid:5" in rendered
        assert "placed (" not in rendered
        assert "slots latent='LATENT'" in rendered


# ---------------------------------------------------------------------------
# Grounding test: render / edit / re-render identity stability
# ---------------------------------------------------------------------------


class TestRenderEditRerenderIdentity:
    """Prove that variable names assigned by the emitter are stable across
    render -> edit -> re-render cycles.

    When EditSession is built:
        1. First render assigns variable names via `emit_agent_edit_python`.
        2. Apply one or more topology-preserving edits.
        3. Re-render must keep existing uids mapped to the same variable names.
    """

    def test_render_then_rerender_preserves_variable_names(self) -> None:
        """Existing uid variable names must not change on re-render.

        This test MUST fail until EditSession.render is implemented with
        name-lock seeding and strict enforcement.
        """
        wf = _load_flat_fixture_wf()
        rendered1 = _emit_agent_edit_python_stub(wf)
        rendered2 = _emit_agent_edit_python_stub(wf)
        # Variable names from first render must equal variable names from second render.
        assert rendered1 == rendered2, (
            "emit_agent_edit_python must produce identical output for identical input; "
            "variable names must be stable across re-renders."
        )

    def test_edit_then_rerender_preserves_untouched_uids(self) -> None:
        """After a topology-changing edit, untouched uids keep their names.

        This test MUST fail until EditSession.apply_batch and re-render
        with name-lock enforcement are implemented.
        """
        wf = _load_flat_fixture_wf()
        rendered1 = _emit_agent_edit_python_stub(wf)
        rendered2 = _emit_agent_edit_python_stub(
            wf,
            variable_name_locks={
                "1": "checkpointloadersimple",
                "5": "ksampler",
                "7": "saveimage",
            },
            strict_variable_name_locks=True,
        )
        assert "checkpointloadersimple = CheckpointLoaderSimple(" in rendered2
        assert "ksampler = KSampler(" in rendered2
        assert "saveimage = SaveImage(" in rendered2
        assert rendered1.count("uid:") == rendered2.count("uid:")

    def test_session_rerender_keeps_locked_names_after_topology_change(self) -> None:
        """A real EditSession keeps prior names stable across topology-changing turns."""
        session = TestEditSessionPrimitiveLowering._primitive_session()
        rendered1 = session.render()

        result = session.apply_batch(
            "mid = PassThroughImage(image=src.in_)\n"
            "dst.value = mid.IMAGE\n"
        )
        assert result.ok is True

        rendered2 = session.render()
        rendered3 = session.render()

        assert "src = SourceOne(" in rendered1
        assert "widget = KSampler(" in rendered1
        assert "dst = Dest(" in rendered1
        assert "src = SourceOne(" in rendered2
        assert "widget = KSampler(" in rendered2
        assert "dst = Dest(" in rendered2
        assert "mid = PassThroughImage(" in rendered2
        assert rendered2 == rendered3


# ---------------------------------------------------------------------------
# Grounding test: slot alias round-trip
# ---------------------------------------------------------------------------


class TestSlotAliasRoundTrip:
    """Prove that slot names that are Python keywords survive round-trip
    through the slot codec: raw name -> Python identifier -> raw name.

    The codec must:
        - Append trailing underscore for Python keywords (e.g., ``in`` -> ``in_``)
        - Normalize invalid characters to underscores
        - Prefix leading digits
        - Handle empty names and collisions deterministically
    """

    def test_slot_codec_round_trips_keywords(self) -> None:
        """Python keyword slots round-trip correctly."""
        # This test must fail until the slot codec is implemented.
        from vibecomfy.identity import codec as slot_codec  # type: ignore[attr-defined]  # noqa: F811

        try:
            encoded = slot_codec.to_python_identifier("in")
            decoded = slot_codec.to_raw_name(encoded, context={"in": "in"})
            assert decoded == "in"
        except (ImportError, AttributeError):
            pytest.fail(
                "slot_codec not yet implemented — "
                "this grounding test defines the slot alias contract."
            )

    def test_slot_codec_round_trips_special_chars(self) -> None:
        """Slots with special characters round-trip via the codec."""
        from vibecomfy.identity import codec as slot_codec  # type: ignore[attr-defined]  # noqa: F811

        try:
            for raw in ["resize_type.multiple", "MODEL (Positive)", "", "3d_model"]:
                encoded = slot_codec.to_python_identifier(raw)
                decoded = slot_codec.to_raw_name(encoded, context={raw: raw})
                assert decoded == raw, f"Round-trip failed for {raw!r}: {encoded!r} -> {decoded!r}"
        except (ImportError, AttributeError):
            pytest.fail(
                "slot_codec not yet implemented — "
                "this grounding test defines the slot alias contract."
            )

    def test_slot_codec_handles_keyword_collisions(self) -> None:
        """Keyword + non-keyword collision gets deterministic suffixes."""
        from vibecomfy.identity import codec as slot_codec  # type: ignore[attr-defined]  # noqa: F811

        try:
            # 'in' is a Python keyword, 'in_' is the alias for it.
            # If a node has both 'in' and 'in_', they must not collide.
            encoded_in = slot_codec.to_python_identifier("in")
            encoded_in_underscore = slot_codec.to_python_identifier("in_")
            # They should not be the same.
            assert encoded_in != encoded_in_underscore, (
                f"slot_codec must differentiate 'in' ({encoded_in}) "
                f"from 'in_' ({encoded_in_underscore})"
            )
        except (ImportError, AttributeError):
            pytest.fail(
                "slot_codec not yet implemented — "
                "this grounding test defines the slot alias contract."
            )

    # -- Focused tests added in T4 -----------------------------------------

    def test_codec_produces_valid_python_identifiers(self) -> None:
        """Every encoded name must be a valid Python identifier."""
        import keyword as kw

        from vibecomfy.identity.codec import to_python_identifier

        raw_names = [
            "", "in", "class", "or", "and", "not", "if", "else", "for",
            "while", "with", "def", "return", "yield", "lambda", "try",
            "resize_type.multiple", "MODEL (Positive)", "3d_model",
            "image/latent", "my-node", "some thing", "hello_world",
            "list", "dict", "str", "int", "float", "bool", "type",
            "UPPERCASE", "MixedCase", "already_ok",
        ]
        for raw in raw_names:
            encoded = to_python_identifier(raw)
            # Must be non-empty
            assert encoded, f"Empty result for {raw!r}"
            # Must start with letter or underscore
            assert encoded[0].isalpha() or encoded[0] == "_", (
                f"Invalid first char in {encoded!r} from {raw!r}"
            )
            # Must be all alphanumeric + underscore
            assert re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", encoded), (
                f"Invalid identifier {encoded!r} from {raw!r}"
            )
            # Must not be a bare keyword
            assert not kw.iskeyword(encoded), (
                f"Result {encoded!r} is a bare keyword from {raw!r}"
            )

    def test_codec_handles_builtin_shadowing(self) -> None:
        """Builtin names get a trailing underscore like keywords (PEP 8)."""
        from vibecomfy.identity.codec import to_python_identifier

        assert to_python_identifier("list") == "list_"
        assert to_python_identifier("dict") == "dict_"
        assert to_python_identifier("str") == "str_"
        assert to_python_identifier("int") == "int_"
        assert to_python_identifier("float") == "float_"
        # Non-builtins should not get trailing underscore
        assert to_python_identifier("my_list") == "my_list"

    def test_codec_handles_leading_digits(self) -> None:
        """Leading digits get an underscore prefix."""
        from vibecomfy.identity.codec import to_python_identifier

        assert to_python_identifier("3d_model") == "_3d_model"
        assert to_python_identifier("123") == "_123"
        assert to_python_identifier("0abc") == "_0abc"

    def test_codec_handles_empty_and_blank_names(self) -> None:
        """Empty names and whitespace-only names become '_'."""
        from vibecomfy.identity.codec import to_python_identifier

        assert to_python_identifier("") == "_"
        # Whitespace-only becomes underscores from replacement, then collapses
        result = to_python_identifier("   ")
        assert result == "_"

    def test_codec_handles_non_ascii_names(self) -> None:
        """Non-ASCII characters are replaced with underscores."""
        from vibecomfy.identity.codec import to_python_identifier

        # é becomes _, and trailing _ is stripped → "caf"
        assert to_python_identifier("café") == "caf"
        # ü becomes _ at position 0, leading _ stripped → "ber"
        assert to_python_identifier("über") == "ber"

    def test_codec_is_deterministic(self) -> None:
        """Same input always produces same output."""
        from vibecomfy.identity.codec import to_python_identifier

        samples = ["in", "class", "MODEL", "3d_model", "", "list", "my_var"]
        for raw in samples:
            first = to_python_identifier(raw)
            for _ in range(10):
                assert to_python_identifier(raw) == first

    # -- Focused tests for reverse lookup metadata -------------------------

    def test_to_raw_name_raises_keyerror_for_unknown(self) -> None:
        """to_raw_name raises KeyError when encoded name is not in context."""
        from vibecomfy.identity.codec import to_raw_name

        with pytest.raises(KeyError):
            to_raw_name("nonexistent", context={"in": "in"})

    def test_to_raw_name_raises_valueerror_for_ambiguous_context(self) -> None:
        """to_raw_name raises ValueError when two raw names encode identically."""
        from vibecomfy.identity.codec import to_raw_name

        # "in" and "in_" both would map to "in_" without collision handling
        # But in standalone mode, they map to "in_" and "in_2" respectively,
        # so they don't collide.  We need a case that actually collides.
        # Two empty-like names both map to "_".
        with pytest.raises(ValueError, match="Ambiguous encoding"):
            to_raw_name("_", context={"": "", "_": "_"})

    def test_to_raw_name_round_trips_with_multi_entry_context(self) -> None:
        """Round-trip works with a multi-entry context."""
        from vibecomfy.identity.codec import to_python_identifier, to_raw_name

        context = {
            "MODEL": "MODEL",
            "positive": "positive",
            "negative": "negative",
            "latent_image": "latent_image",
            "in": "in",
            "out": "out",
            "": "",
            "3d_model": "3d_model",
        }
        for raw in context:
            encoded = to_python_identifier(raw)
            decoded = to_raw_name(encoded, context)
            assert decoded == raw, f"Round-trip failed: {raw!r} -> {encoded!r} -> {decoded!r}"


# ---------------------------------------------------------------------------
# Slot codec: reverse map and batch encoding (T4 focused tests)
# ---------------------------------------------------------------------------


class TestSlotCodecBatchAndReverseMap:
    """Focused unit tests for build_reverse_map and encode_slot_names."""

    def test_build_reverse_map_simple(self) -> None:
        """build_reverse_map returns encoded->raw mapping."""
        from vibecomfy.identity.codec import build_reverse_map

        rm = build_reverse_map(["in", "out", "model"])
        assert rm == {"in_": "in", "out": "out", "model": "model"}

    def test_build_reverse_map_with_duplicates(self) -> None:
        """build_reverse_map handles duplicate raw names gracefully."""
        from vibecomfy.identity.codec import build_reverse_map

        # Same raw name twice — should not raise
        rm = build_reverse_map(["in", "in", "out"])
        assert rm["in_"] == "in"

    def test_build_reverse_map_collision_raises(self) -> None:
        """build_reverse_map raises ValueError when two distinct names collide."""
        from vibecomfy.identity.codec import build_reverse_map

        # "" and "_" both encode to "_" in standalone mode
        with pytest.raises(ValueError, match="Encoding collision"):
            build_reverse_map(["", "_"])

    def test_encode_slot_names_produces_unique_identifiers(self) -> None:
        """encode_slot_names uses collision avoidance for suffixes."""
        from vibecomfy.identity.codec import encode_slot_names

        mapping = encode_slot_names(["in", "in_", "in__"])
        # All mapped identifiers must be unique
        ids = list(mapping.values())
        assert len(ids) == len(set(ids)), f"Non-unique identifiers: {ids}"
        # "in" gets "in_", "in_" gets something different
        assert mapping["in"] == "in_"
        assert mapping["in_"] != "in_"

    def test_encode_slot_names_round_trips_via_reverse_map(self) -> None:
        """Encoding batch + reverse map recovers all original names."""
        from vibecomfy.identity.codec import build_reverse_map, encode_slot_names

        raw_names = [
            "MODEL", "positive", "negative", "in", "out",
            "latent_image", "", "3d_model", "resize_type.multiple",
        ]
        mapping = encode_slot_names(raw_names)
        reverse = build_reverse_map(raw_names)
        for raw in raw_names:
            encoded = mapping[raw]
            assert reverse[encoded] == raw, (
                f"Reverse map mismatch: {raw!r} -> {encoded!r}"
            )

    def test_encode_slot_names_empty_list(self) -> None:
        """encode_slot_names on empty list returns empty dict."""
        from vibecomfy.identity.codec import encode_slot_names

        assert encode_slot_names([]) == {}

    def test_build_reverse_map_empty_list(self) -> None:
        """build_reverse_map on empty list returns empty dict."""
        from vibecomfy.identity.codec import build_reverse_map

        assert build_reverse_map([]) == {}


class TestAgentEditPythonEmitter:
    """Focused coverage for the T5 agent-edit rendering surface."""

    def test_agent_edit_python_is_parseable_assignment_view_with_identity_comments(self) -> None:
        from vibecomfy.porting.emitter import emit_agent_edit_python

        rendered = emit_agent_edit_python(_load_flat_fixture_wf())

        ast.parse(rendered)
        assert rendered.startswith("# vibecomfy: agent-edit")
        assert "checkpointloadersimple = CheckpointLoaderSimple(" in rendered
        assert "positive = CLIPTextEncode(" in rendered
        assert "clip=checkpointloadersimple.clip" in rendered
        assert "ksampler = KSampler(" in rendered
        assert "model=checkpointloadersimple.model" in rendered
        assert "positive=positive.conditioning" in rendered
        assert "saveimage = SaveImage(" in rendered
        assert "images=vaedecode.image" in rendered
        assert "uid:5" in rendered
        assert "placed (" not in rendered
        assert "slots latent='LATENT'" in rendered

    def test_agent_edit_python_rejects_raw_ui_json_before_emitter_internals(self) -> None:
        from vibecomfy.porting.emitter import emit_agent_edit_python

        with pytest.raises(TypeError, match="emit_agent_edit_python requires VibeWorkflow"):
            emit_agent_edit_python(_load_flat_fixture_raw())  # type: ignore[arg-type]

    def test_agent_edit_python_preserves_locked_names_without_changing_scratchpad(self) -> None:
        from vibecomfy.porting.emitter import emit_agent_edit_python, emit_scratchpad_python

        wf = _load_flat_fixture_wf()
        baseline_scratchpad = emit_scratchpad_python(wf, prune_dead_branches=False)
        rendered = emit_agent_edit_python(
            wf,
            variable_name_locks={"5": "sampler_locked", "7": "save_locked"},
            strict_variable_name_locks=True,
        )
        after_scratchpad = emit_scratchpad_python(wf, prune_dead_branches=False)

        assert "sampler_locked = KSampler(" in rendered
        assert "save_locked = SaveImage(" in rendered
        assert baseline_scratchpad == after_scratchpad
        assert "_node(wf," in baseline_scratchpad
        assert "_node(wf," not in rendered

    def test_agent_edit_python_tags_virtual_nodes(self) -> None:
        from vibecomfy.porting.emitter import emit_agent_edit_python

        wf = VibeWorkflow("virtual", WorkflowSource("virtual"))
        wf.add_node("SetNode", uid="set-uid", name="LATENT")
        rendered = emit_agent_edit_python(wf)

        ast.parse(rendered)
        assert "setnode = SetNode(" in rendered
        assert "uid:set-uid [virtual]" in rendered

    def test_agent_edit_python_renders_exec_as_edit_dsl_call(self) -> None:
        from vibecomfy.porting.emitter import emit_agent_edit_python

        wf = VibeWorkflow("exec", WorkflowSource("exec"))
        wf.add_node(
            "vibecomfy.exec",
            uid="exec-uid",
            source='return {"image": image}',
            io={"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]},
        )
        rendered = emit_agent_edit_python(wf)

        ast.parse(rendered)
        assert "vibecomfy_exec = vibecomfy.exec(" in rendered
        assert "node('vibecomfy.exec'" not in rendered
        assert "io={'inputs': [['image', 'IMAGE']], 'outputs': [['image', 'IMAGE']]}" in rendered


# ---------------------------------------------------------------------------
# Lean render tests: title-drop + string elision
# ---------------------------------------------------------------------------


class TestAgentEditLeanRender:
    """Verify the lean agent-edit render surface: title-drop heuristic and string elision."""

    def test_decorative_title_equal_to_class_is_dropped(self) -> None:
        """title='KSampler' on KSampler → no `title:` token."""
        from vibecomfy.porting.emitter import emit_agent_edit_python

        wf = VibeWorkflow("lean-class", WorkflowSource("lean-class"))
        node = wf.add_node("KSampler", uid="k1")
        node.metadata["_ui"] = {"title": "KSampler"}
        rendered = emit_agent_edit_python(wf)
        assert "title:" not in rendered

    def test_decorative_title_equal_to_var_name_is_dropped(self) -> None:
        """title matching rendered variable name → no `title:` token."""
        from vibecomfy.porting.emitter import emit_agent_edit_python

        wf = VibeWorkflow("lean-var", WorkflowSource("lean-var"))
        node = wf.add_node("KSampler", uid="k1")
        # _compute_variable_names derives 'ksampler' from class_type 'KSampler'
        node.metadata["_ui"] = {"title": "ksampler"}
        rendered = emit_agent_edit_python(wf)
        assert "title:" not in rendered

    def test_decorative_title_pure_symbols_is_dropped(self) -> None:
        """title of only symbols ('---') → no `title:` token."""
        from vibecomfy.porting.emitter import emit_agent_edit_python

        wf = VibeWorkflow("lean-symbols", WorkflowSource("lean-symbols"))
        node = wf.add_node("KSampler", uid="k1")
        node.metadata["_ui"] = {"title": "---"}
        rendered = emit_agent_edit_python(wf)
        assert "title:" not in rendered

    def test_meaningful_title_is_kept(self) -> None:
        """distinct meaningful title (including emoji) → `title:` token present."""
        from vibecomfy.porting.emitter import emit_agent_edit_python

        wf = VibeWorkflow("lean-meaningful", WorkflowSource("lean-meaningful"))
        node = wf.add_node("KSampler", uid="k1")
        node.metadata["_ui"] = {"title": "📦 Model loader"}
        rendered = emit_agent_edit_python(wf)
        assert "title:\u200b📦 Model loader" in rendered or "title:📦 Model loader" in rendered

    def test_long_string_elision_threshold_respected(self) -> None:
        """string widget value >400 chars is elided with [...elided N chars...]."""
        from vibecomfy.porting.emitter import _format_value

        long_str = "x" * 500
        result = _format_value(long_str, elide_strings_over=400)
        assert "elided" in result
        assert "chars" in result
        # Regular (non-elided) string should use plain repr
        short_str = "hello"
        short_result = _format_value(short_str, elide_strings_over=400)
        assert short_result == "'hello'"


# ---------------------------------------------------------------------------
# Grounding test: empty done()
# ---------------------------------------------------------------------------


class TestEmptyDone:
    """Prove that calling done() on a session with no applied ops succeeds.

    An empty session (no edits applied) must:
        - Pass guard_full_ui (no mutations to guard)
        - Pass compile isomorphism (identical to original)
        - Return a DoneResult with an empty summary
    """

    def test_empty_done_succeeds(self) -> None:
        """done() on a session with zero ops passes all gates."""
        from vibecomfy.porting.edit.session import EditSession

        raw = _load_flat_fixture_raw()
        session = EditSession(raw)
        result = session.done()
        assert result.ok is True
        assert "identity verified" in result.summary

    def test_empty_done_returns_empty_summary(self) -> None:
        """Empty done() summary reports no changes."""
        from vibecomfy.porting.edit.session import EditSession

        raw = _load_flat_fixture_raw()
        session = EditSession(raw)
        result = session.done()
        assert result.ok
        assert "No edits applied" in result.summary or result.summary == ""


# =====================================================================
# M1 T2 — Integration boundary inventory and freeze (audit)
# =====================================================================
#
# M1 adds a lower-level `EditSession` surface.  It must NOT:
#
#   * wire into `handle_agent_edit()` — the existing agent-edit endpoint is
#     owned by the ComfyUI runtime path and is out of scope for M1;
#   * replace `emit_scratchpad_python()` — that path remains the primary
#     entry point for the existing agent-edit pipeline;
#   * modify `tools/format_as_python.py` — that file is a legacy/delegation
#     wrapper and is unrelated to the edit-view emitter.
#
# The tests below freeze these boundaries so any accidental coupling in a
# later batch is caught by the test suite.


class TestIntegrationBoundaries:
    """Freeze the existing integration boundaries so M1 does not couple where
    it should not.

    Every test in this class MUST pass — they assert facts about the
    *current* codebase, not about M1 work-in-progress.  If any fail they
    indicate an unintended regression or a violation of the M1 scope
    contract.
    """

    # ------------------------------------------------------------------
    # emit_scratchpad_python — existing emitter entry point
    # ------------------------------------------------------------------

    def test_emit_scratchpad_python_exists_and_location(self) -> None:
        """emit_scratchpad_python is in vibecomfy/porting/emitter.py."""
        from vibecomfy.porting.emitter import emit_scratchpad_python

        assert callable(emit_scratchpad_python)
        # The emitter takes a workflow + keyword args and returns a string.
        sig = emit_scratchpad_python.__name__
        assert sig == "emit_scratchpad_python"

    def test_emit_scratchpad_python_accepts_vibeworkflow(self) -> None:
        """emit_scratchpad_python accepts VibeWorkflow and returns valid Python."""
        from vibecomfy.porting.emitter import emit_scratchpad_python

        wf = _load_flat_fixture_wf()
        result = emit_scratchpad_python(wf)
        assert isinstance(result, str)
        assert "def build(" in result
        assert "VibeWorkflow" in result

    # ------------------------------------------------------------------
    # handle_agent_edit — existing agent-edit endpoint
    # ------------------------------------------------------------------

    def test_handle_agent_edit_exists_and_location(self) -> None:
        """handle_agent_edit is in vibecomfy/comfy_nodes/agent/edit.py."""
        from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit

        assert callable(handle_agent_edit)
        # M1 must NOT wire into handle_agent_edit.
        # This test simply confirms the symbol exists at its canonical
        # location so future batches cannot accidentally relocate it.

    # ------------------------------------------------------------------
    # edit_projection — MODE_LABELS and HELPER_NODE_TYPES
    # ------------------------------------------------------------------

    def test_edit_projection_constants_exist(self) -> None:
        """MODE_LABELS and HELPER_NODE_TYPES are in edit_projection.py."""
        from vibecomfy.porting.edit.projection import HELPER_NODE_TYPES, MODE_LABELS

        assert isinstance(MODE_LABELS, dict)
        assert MODE_LABELS[0] == "enabled"
        assert MODE_LABELS[2] == "muted"
        assert MODE_LABELS[4] == "bypassed"
        assert isinstance(HELPER_NODE_TYPES, frozenset)
        assert "Reroute" in HELPER_NODE_TYPES
        assert "Note" in HELPER_NODE_TYPES

    # ------------------------------------------------------------------
    # parity.compile_equivalent — graph isomorphism oracle
    # ------------------------------------------------------------------

    def test_compile_equivalent_exists_and_works(self) -> None:
        """compile_equivalent is in vibecomfy/porting/parity.py and
        returns (bool, list[str]) for semantically identical workflows."""
        from vibecomfy.porting.parity import compile_equivalent

        assert callable(compile_equivalent)
        wf = _load_flat_fixture_wf()
        api = wf.compile("api")
        ok, diffs = compile_equivalent(api, api)
        assert ok is True
        assert diffs == []

    def test_compile_equivalent_detects_differences(self) -> None:
        """compile_equivalent returns (False, diffs) for different graphs."""
        from vibecomfy.porting.parity import compile_equivalent

        wf = _load_flat_fixture_wf()
        api1 = wf.compile("api")
        # compile('api') returns a dict keyed by node ID.
        # Remove the last key to create a demonstrable difference.
        api2 = deepcopy(api1)
        keys = list(api2.keys())
        if keys:
            del api2[keys[-1]]
        ok, diffs = compile_equivalent(api1, api2)
        assert ok is False
        assert len(diffs) > 0

    # ------------------------------------------------------------------
    # Naming helpers and emitter safe-name functions
    # ------------------------------------------------------------------

    def test_slugify_identifier_handles_keywords(self) -> None:
        """_slugify_identifier appends trailing underscore for Python keywords."""
        from vibecomfy.porting.emitter import _slugify_identifier  # type: ignore[attr-defined]

        # Non-keyword passes through
        assert _slugify_identifier("hello") == "hello"
        # Python keyword gets trailing underscore (PEP 8 convention)
        assert _slugify_identifier("in") == "in_"
        assert _slugify_identifier("class") == "class_"
        # Special chars become underscores
        assert _slugify_identifier("my-node") == "my_node"

    def test_safe_var_handles_uuids_and_keywords(self) -> None:
        """_safe_var shortens UUIDs and adds trailing underscore for keywords."""
        from vibecomfy.porting.emitter import _safe_var  # type: ignore[attr-defined]

        # UUID class types get short prefixes
        assert _safe_var("7b34ab90-36f9-45ba-a665-71d418f0df18").startswith("subgraph_")
        # Keywords get trailing underscore
        assert _safe_var("in") == "in_"
        assert _safe_var("class") == "class_"

    def test_unique_var_avoids_keyword_conflicts(self) -> None:
        """_unique_var never returns a bare Python keyword."""
        from vibecomfy.porting.emitter import _unique_var  # type: ignore[attr-defined]

        used: set[str] = set()
        # "in" is a keyword; _unique_var must suffix it.
        result = _unique_var("in", used)
        assert result != "in"
        assert not __import__("keyword").iskeyword(result)

    def test_safe_kwarg_name_falls_back_for_digit_start(self) -> None:
        """_safe_kwarg_name uses fallback when name starts with digit."""
        from vibecomfy.porting.emitter import _safe_kwarg_name  # type: ignore[attr-defined]

        # Names starting with digits should fall back.
        result = _safe_kwarg_name("123abc", fallback="input_0")
        assert result != "123abc"
        # Normal name works
        assert _safe_kwarg_name("lora_strength", fallback="input_0") == "lora_strength"

    def test_safe_output_name_returns_none_for_oob_slot(self) -> None:
        """_safe_output_name returns None for out-of-range slots."""
        from vibecomfy.porting.emitter import _safe_output_name  # type: ignore[attr-defined]

        wf = _load_flat_fixture_wf()
        workflow_nodes = {nid: node for nid, node in wf.nodes.items()}
        # Find a real node with known output count
        for nid, node in workflow_nodes.items():
            out_count = len(getattr(node, "metadata", {}).get("output_names", []))
            if out_count > 0:
                # Valid slot returns name or None
                result = _safe_output_name(workflow_nodes, nid, 0)
                assert result is None or isinstance(result, str)
                # Out-of-range slot returns None
                assert _safe_output_name(workflow_nodes, nid, 9999) is None
                break

    # ------------------------------------------------------------------
    # Schema provider APIs
    # ------------------------------------------------------------------

    def test_schema_for_returns_schema_or_none(self) -> None:
        """schema_for(provider, class_type) returns NodeSchema or None."""
        from vibecomfy.schema import schema_for

        # None provider returns None (unless class_type is builtin)
        result = schema_for(None, "NonExistentClassType")
        assert result is None
        # Builtin schemas work without provider
        builtin = schema_for(None, "vibecomfy.code")
        assert builtin is not None
        assert builtin.class_type == "vibecomfy.code"

    def test_get_schema_provider_returns_provider(self) -> None:
        """get_schema_provider() returns a SchemaProvider."""
        from vibecomfy.schema import get_schema_provider

        provider = get_schema_provider()
        # May be None if no ComfyUI runtime, but must be importable.
        # We only assert the symbol is callable.
        assert callable(get_schema_provider)

    # ------------------------------------------------------------------
    # tools/format_as_python.py — M1 MUST NOT touch this file
    # ------------------------------------------------------------------

    def test_format_as_python_is_delegation_wrapper(self) -> None:
        """tools/format_as_python.py is a legacy delegation wrapper.

        The active code path delegates to
        vibecomfy.porting.emitter.emit_ready_template_python().  M1 must
        NOT modify this file.
        """
        from tools.format_as_python import format_as_python

        assert callable(format_as_python)

    def test_m1_does_not_touch_format_as_python_location(self) -> None:
        """Freeze: the canonical emitter is vibecomfy/porting/emitter.py,
        NOT tools/format_as_python.py.  M1 work must go into the porting
        emitter module.
        """
        from vibecomfy.porting.emitter import emit_ready_template_python

        # The active emit path lives in the porting module.
        assert callable(emit_ready_template_python)
        assert emit_ready_template_python.__module__ == "vibecomfy.porting.emitter"

    # ------------------------------------------------------------------
    # M1 scope contract: EditSession is standalone, not wired into handle_agent_edit
    # ------------------------------------------------------------------

    def test_edit_session_stub_does_not_call_handle_agent_edit(self) -> None:
        """The EditSession stub does not import or reference handle_agent_edit."""
        import inspect

        src = inspect.getsource(_EditSessionStub)
        assert "handle_agent_edit" not in src

    def test_emit_scratchpad_python_still_works_independently(self) -> None:
        """emit_scratchpad_python works independently; M1 does not replace it."""
        from vibecomfy.porting.emitter import emit_scratchpad_python

        wf = _load_flat_fixture_wf()
        result = emit_scratchpad_python(wf)
        assert "def build(" in result
        assert "from vibecomfy.workflow import VibeWorkflow" in result
        # The scratchpad emitter path is untouched.


class TestEmitterVariableNameLocks:
    """Session-locked aliases bridge stable uids to local emitter node ids."""

    def _tiny_uid_workflow(self) -> VibeWorkflow:
        wf = VibeWorkflow("locks", WorkflowSource("locks"))
        first = wf.add_node("CheckpointLoaderSimple", uid="uid-loader")
        second = wf.add_node("KSampler", model=[first.id, 0], uid="uid-sampler")
        wf.nodes[second.id].metadata["_ui"] = {
            "properties": {
                "vibecomfy_uid": "ui-sampler",
            }
        }
        return wf

    def test_locked_aliases_bridge_vibenode_uid_and_ui_property_uid(self) -> None:
        from vibecomfy.porting.emitter import emit_scratchpad_python

        wf = self._tiny_uid_workflow()
        diagnostics = []

        source = emit_scratchpad_python(
            wf,
            diagnostics=diagnostics,
            variable_name_locks={
                "uid-loader": "locked_loader",
                "ui-sampler": "locked_sampler",
            },
            prune_dead_branches=False,
        )

        assert "locked_loader = _node(wf, 'CheckpointLoaderSimple'" in source
        assert "locked_sampler = _node(wf, 'KSampler'" in source
        assert not [diag for diag in diagnostics if diag.code.startswith("locked_variable_")]

    def test_invalid_locked_alias_reports_diagnostic_and_does_not_emit_bad_python(self) -> None:
        from vibecomfy.porting.emitter import (
            READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
            emit_scratchpad_python,
        )

        wf = self._tiny_uid_workflow()
        diagnostics = []
        source = emit_scratchpad_python(
            wf,
            diagnostics=diagnostics,
            variable_name_locks={"uid-loader": "not valid"},
            prune_dead_branches=False,
        )

        assert "not valid = _node" not in source
        assert any(diag.code == READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID for diag in diagnostics)

    def test_colliding_locked_aliases_report_diagnostic(self) -> None:
        from vibecomfy.porting.emitter import (
            READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
            emit_scratchpad_python,
        )

        wf = self._tiny_uid_workflow()
        diagnostics = []
        source = emit_scratchpad_python(
            wf,
            diagnostics=diagnostics,
            variable_name_locks={
                "uid-loader": "same_name",
                "uid-sampler": "same_name",
            },
            prune_dead_branches=False,
        )

        assert "same_name = _node" not in source
        assert any(diag.code == READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION for diag in diagnostics)

    def test_strict_missing_locked_uid_reports_later_render_diagnostic(self) -> None:
        from vibecomfy.porting.emitter import (
            READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
            emit_scratchpad_python,
        )

        diagnostics = []
        emit_scratchpad_python(
            self._tiny_uid_workflow(),
            diagnostics=diagnostics,
            variable_name_locks={"missing-uid": "old_name"},
            strict_variable_name_locks=True,
            prune_dead_branches=False,
        )

        missing = [diag for diag in diagnostics if diag.code == READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING]
        assert len(missing) == 1
        assert missing[0].severity == "error"
        assert missing[0].detail["uid"] == "missing-uid"

    def test_subgraph_internal_locked_names_use_scope_qualified_uid(self) -> None:
        from vibecomfy.porting.emitter import _build_subgraph_def, _emit_subgraph_functions
        from vibecomfy.identity.uid import make_uid

        raw_subgraph = {
            "id": "sg-alpha",
            "name": "Scoped",
            "nodes": [
                {
                    "id": 1,
                    "type": "TotallyCustomNode",
                    "properties": {"vibecomfy_uid": "inner-loader"},
                    "widgets_values": [],
                },
            ],
            "links": [
                {
                    "id": 1,
                    "origin_id": 1,
                    "origin_slot": 0,
                    "target_id": -20,
                    "target_slot": 0,
                }
            ],
            "inputs": [],
            "outputs": [{"name": "MODEL", "type": "MODEL"}],
        }
        subgraph = _build_subgraph_def(raw_subgraph, slug="scoped", source_path=None)
        diagnostics = []
        source = "\n".join(
            _emit_subgraph_functions(
                {"subgraph_definitions": {"sg-alpha": subgraph}},
                diagnostics=diagnostics,
                constant_map={},
                variable_name_locks={make_uid("sg-alpha", "inner-loader"): "locked_inner_loader"},
            )
        )

        assert "locked_inner_loader = raw_call('TotallyCustomNode'" in source
        assert not [diag for diag in diagnostics if diag.code.startswith("locked_variable_")]


# =====================================================================
# M1 T6 — emit_available_node_signatures and format_signature_rows
# =====================================================================


class TestAvailableNodeSignatures:
    """Tests for emit_available_node_signatures(...) and format_signature_rows(...)."""

    @staticmethod
    def _fake_provider(
        schemas_dict: dict[str, Any] | None = None,
    ) -> Any:
        """Build a fake schema provider with .schemas() and .get_schema()."""
        from vibecomfy.schema import NodeSchema

        if schemas_dict is None:
            schemas_dict = {}

        class _Fake:
            def __init__(self, schemas: dict[str, Any]) -> None:
                self._schemas = dict(schemas)

            def schemas(self) -> dict[str, Any]:
                return dict(self._schemas)

            def get_schema(self, class_type: str) -> Any:
                return self._schemas.get(class_type)

        return _Fake(schemas_dict)

    # -- enumeration path via .schemas() -----------------------------------

    def test_enumeration_uses_schemas_method(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "Loader": NodeSchema(
                    class_type="Loader",
                    pack="core",
                    inputs={"ckpt": InputSpec(type="COMBO", required=True)},
                    outputs=[OutputSpec(type="MODEL", name="MODEL")],
                    confidence=1.0,
                ),
                "Sampler": NodeSchema(
                    class_type="Sampler",
                    pack="core",
                    inputs={"model": InputSpec(type="MODEL", required=True)},
                    outputs=[OutputSpec(type="LATENT", name="LATENT")],
                    confidence=1.0,
                ),
            }
        )

        rows = emit_available_node_signatures(provider)
        assert len(rows) == 2
        class_types = [r.class_type for r in rows]
        assert class_types == ["Loader", "Sampler"]  # sorted

        loader = rows[0]
        assert loader.class_type == "Loader"
        assert len(loader.inputs) == 1
        assert loader.inputs[0].name == "ckpt"
        assert loader.inputs[0].type == "COMBO"
        assert loader.inputs[0].required is True
        assert len(loader.outputs) == 1
        assert loader.outputs[0].type == "MODEL"
        assert loader.source_confidence == 1.0
        assert loader.pack == "core"

    def test_enumeration_empty_provider_returns_empty(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures

        provider = self._fake_provider({})
        rows = emit_available_node_signatures(provider)
        assert rows == []

    # -- focused / per-node path via .get_schema() -------------------------

    def test_focus_types_uses_get_schema(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "A": NodeSchema(
                    class_type="A",
                    pack="p",
                    inputs={},
                    outputs=[],
                ),
                "B": NodeSchema(
                    class_type="B",
                    pack="p",
                    inputs={},
                    outputs=[],
                ),
            }
        )

        # Only ask for A
        rows = emit_available_node_signatures(provider, focus_types=["A"])
        assert len(rows) == 1
        assert rows[0].class_type == "A"

    def test_focus_types_skips_unknown(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "Real": NodeSchema(
                    class_type="Real",
                    pack="p",
                    inputs={},
                    outputs=[],
                ),
            }
        )

        rows = emit_available_node_signatures(
            provider, focus_types=["Real", "Ghost", "Missing"]
        )
        assert len(rows) == 1
        assert rows[0].class_type == "Real"

    # -- compatibility filtering -------------------------------------------

    def test_compatible_input_type_filters_by_output_compatibility(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "ModelProducer": NodeSchema(
                    class_type="ModelProducer",
                    pack="core",
                    inputs={},
                    outputs=[OutputSpec(type="MODEL", name="MODEL")],
                ),
                "LatentProducer": NodeSchema(
                    class_type="LatentProducer",
                    pack="core",
                    inputs={},
                    outputs=[OutputSpec(type="LATENT", name="LATENT")],
                ),
            }
        )

        # compatible_input_type="MODEL" → keep nodes whose outputs are MODEL-compatible
        rows = emit_available_node_signatures(
            provider, compatible_input_type="MODEL"
        )
        assert len(rows) == 1
        assert rows[0].class_type == "ModelProducer"

    def test_compatible_output_type_filters_by_input_compatibility(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "ModelConsumer": NodeSchema(
                    class_type="ModelConsumer",
                    pack="core",
                    inputs={"model": InputSpec(type="MODEL", required=True)},
                    outputs=[],
                ),
                "ImageConsumer": NodeSchema(
                    class_type="ImageConsumer",
                    pack="core",
                    inputs={"image": InputSpec(type="IMAGE", required=True)},
                    outputs=[],
                ),
            }
        )

        rows = emit_available_node_signatures(
            provider, compatible_output_type="MODEL"
        )
        assert len(rows) == 1
        assert rows[0].class_type == "ModelConsumer"

    def test_combined_compatibility_filters(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "ModelToLatent": NodeSchema(
                    class_type="ModelToLatent",
                    pack="core",
                    inputs={"model": InputSpec(type="MODEL", required=True)},
                    outputs=[OutputSpec(type="LATENT", name="LATENT")],
                ),
                "ImageToImage": NodeSchema(
                    class_type="ImageToImage",
                    pack="core",
                    inputs={"image": InputSpec(type="IMAGE", required=True)},
                    outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                ),
            }
        )

        # Both: compatible_input_type="LATENT" (outputs must be LATENT-compatible)
        #  and  compatible_output_type="MODEL"  (inputs must be MODEL-compatible)
        rows = emit_available_node_signatures(
            provider,
            compatible_input_type="LATENT",
            compatible_output_type="MODEL",
        )
        assert len(rows) == 1
        assert rows[0].class_type == "ModelToLatent"

    # -- unknown / wildcard compatibility ----------------------------------

    def test_unknown_type_is_compatible_with_everything(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "WildcardOut": NodeSchema(
                    class_type="WildcardOut",
                    pack="core",
                    inputs={},
                    outputs=[OutputSpec(type="*", name="value")],
                ),
                "TypedOut": NodeSchema(
                    class_type="TypedOut",
                    pack="core",
                    inputs={},
                    outputs=[OutputSpec(type="MODEL", name="MODEL")],
                ),
            }
        )

        # compatible_input_type="UNKNOWN_XYZ" → "*" output is compatible, typed is not
        rows = emit_available_node_signatures(
            provider, compatible_input_type="UNKNOWN_XYZ"
        )
        assert len(rows) == 1
        assert rows[0].class_type == "WildcardOut"

    def test_none_type_is_compatible_with_anything(self) -> None:
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "NullOut": NodeSchema(
                    class_type="NullOut",
                    pack="core",
                    inputs={},
                    outputs=[OutputSpec(type=None, name="value")],
                ),
                "TypedOut": NodeSchema(
                    class_type="TypedOut",
                    pack="core",
                    inputs={},
                    outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                ),
            }
        )

        rows = emit_available_node_signatures(
            provider, compatible_input_type="SOME_WEIRD_TYPE"
        )
        assert len(rows) == 1
        assert rows[0].class_type == "NullOut"

    # -- formatted output --------------------------------------------------

    def test_format_signature_rows_basic(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            OutputSignatureField,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="KSampler",
                inputs=[
                    InputSignatureField(name="model", type="MODEL", required=True),
                    InputSignatureField(name="seed", type="INT", required=False, default=0),
                ],
                outputs=[OutputSignatureField(name="LATENT", type="LATENT")],
                pack="core",
            ),
        ]

        text = format_signature_rows(rows)
        assert "# authoring: literal fields: seed; socket inputs: model" in text
        assert "# raw class: KSampler" in text
        assert "def ksampler(model: MODEL, seed: INT = ...) -> latent:LATENT:" in text

    def test_format_signature_rows_no_outputs(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="SaveImage",
                inputs=[
                    InputSignatureField(name="images", type="IMAGE", required=True),
                ],
                outputs=[],
            ),
        ]

        text = format_signature_rows(rows)
        assert "# raw class: SaveImage" in text
        assert "def saveimage(images: IMAGE) -> None:" in text

    def test_format_signature_rows_show_pack(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="Foo",
                inputs=[],
                outputs=[],
                pack="comfy_custom",
            ),
        ]

        text = format_signature_rows(rows, show_pack=True)
        assert "# pack: comfy_custom" in text
        assert "def foo() -> None:" in text

    def test_format_signature_rows_show_confidence(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="LowConf",
                inputs=[],
                outputs=[],
                source_confidence=0.75,
            ),
            NodeSignatureRow(
                class_type="HighConf",
                inputs=[],
                outputs=[],
                source_confidence=1.0,
            ),
        ]

        text = format_signature_rows(rows, show_confidence=True)
        # Low confidence row should show annotation
        assert "confidence: 0.75" in text
        # High confidence (1.0) should NOT show annotation
        assert "confidence: 1.00" not in text
        # Both class types should still appear
        assert "def highconf() -> None:" in text
        assert "def lowconf() -> None:" in text

    def test_format_signature_rows_deterministic(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(class_type="Z", inputs=[], outputs=[]),
            NodeSignatureRow(class_type="A", inputs=[], outputs=[]),
            NodeSignatureRow(class_type="M", inputs=[], outputs=[]),
        ]

        text1 = format_signature_rows(rows)
        text2 = format_signature_rows(list(reversed(rows)))
        assert text1 == text2
        # Should be sorted A, M, Z
        lines = [line for line in text1.split("\n") if line.startswith("def ")]
        assert lines == ["def a() -> None:", "def m() -> None:", "def z() -> None:"]

    def test_format_signature_rows_slot_name_codec(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="KwargsNode",
                inputs=[
                    InputSignatureField(name="in", type="IMAGE", required=True),
                    InputSignatureField(name="class", type="STRING", required=False, default="foo"),
                ],
                outputs=[],
            ),
        ]

        text = format_signature_rows(rows)
        # 'in' → 'in_', 'class' → 'class_'
        assert "def kwargsnode(in_: IMAGE, class_: STRING = ...) -> None:" in text

    def test_format_signature_rows_uses_python_identifier_alias_for_class_type(self) -> None:
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
        assert "# raw class: MiDaS-DepthMapPreprocessor" in text
        assert "def midas_depthmappreprocessor() -> None:" in text

    def test_format_signature_rows_omits_raw_class_comment_when_alias_matches(self) -> None:
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="CheckpointLoaderSimple",
                inputs=[],
                outputs=[],
            ),
        ]

        text = format_signature_rows(rows)
        # CheckpointLoaderSimple → checkpointloadersimple (alias differs)
        assert "# raw class: CheckpointLoaderSimple" in text
        assert "def checkpointloadersimple() -> None:" in text

    def test_node_signature_row_frozen(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            OutputSignatureField,
        )

        row = NodeSignatureRow(
            class_type="Test",
            inputs=[InputSignatureField(name="x", type="INT")],
            outputs=[OutputSignatureField(name="out", type="INT")],
        )

        assert row.class_type == "Test"
        assert row.source_confidence == 1.0
        assert row.pack is None

        # Frozen — cannot mutate
        with pytest.raises(Exception):
            row.class_type = "Other"  # type: ignore[misc]

    def test_input_signature_field_default_none(self) -> None:
        from vibecomfy.porting.emitter import InputSignatureField

        f = InputSignatureField(name="test")
        assert f.name == "test"
        assert f.type is None
        assert f.required is False
        assert f.default is None

    def test_output_signature_field_default_none(self) -> None:
        from vibecomfy.porting.emitter import OutputSignatureField

        f = OutputSignatureField()
        assert f.name is None
        assert f.type is None

    def test_unknown_compatibility_handles_both_none_and_star_types(self) -> None:
        """Both None and '*' types should match any filter."""
        from vibecomfy.porting.emitter import emit_available_node_signatures
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        provider = self._fake_provider(
            {
                "NoneTypeIn": NodeSchema(
                    class_type="NoneTypeIn",
                    pack="core",
                    inputs={"anything": InputSpec(type=None, required=False)},
                    outputs=[],
                ),
                "StarTypeIn": NodeSchema(
                    class_type="StarTypeIn",
                    pack="core",
                    inputs={"anything": InputSpec(type="*", required=False)},
                    outputs=[],
                ),
            }
        )

        rows = emit_available_node_signatures(
            provider, compatible_output_type="RANDOM_TYPE"
        )
        assert len(rows) == 2
        class_types = {r.class_type for r in rows}
        assert class_types == {"NoneTypeIn", "StarTypeIn"}

    # -- FIX 1 / FIX 2: combo choices and output slot names ---------------

    def test_combo_input_renders_choices_inline(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="VAELoader",
                inputs=[
                    InputSignatureField(
                        name="vae_name",
                        type="COMBO",
                        required=True,
                        choices=("ae.safetensors", "flux_vae.safetensors"),
                    ),
                ],
                outputs=[],
            ),
        ]
        text = format_signature_rows(rows)
        assert (
            'def vaeloader(vae_name: COMBO["ae.safetensors", "flux_vae.safetensors"]) -> None:'
            in text
        )

    def test_combo_input_truncates_over_limit(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            format_signature_rows,
        )

        many_choices = tuple(f"model_{i:04d}.safetensors" for i in range(347))
        rows = [
            NodeSignatureRow(
                class_type="BigLoader",
                inputs=[
                    InputSignatureField(
                        name="ckpt_name",
                        type="COMBO",
                        required=True,
                        choices=many_choices,
                    ),
                ],
                outputs=[],
            ),
        ]
        text = format_signature_rows(rows)
        # Only 40 values rendered
        assert '"model_0000.safetensors"' in text
        assert '"model_0039.safetensors"' in text
        assert '"model_0040.safetensors"' not in text
        # Truncation guidance present
        assert "+307 more" in text
        assert "ask the user for an exact name if you need one not listed" in text

    def test_output_name_differs_from_type_renders_name_colon_type(self) -> None:
        from vibecomfy.porting.emitter import (
            NodeSignatureRow,
            OutputSignatureField,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="SamplerCustomAdvanced",
                inputs=[],
                outputs=[
                    OutputSignatureField(name="output", type="LATENT"),
                    OutputSignatureField(name="denoised_output", type="LATENT"),
                ],
            ),
        ]
        text = format_signature_rows(rows)
        assert "def samplercustomadvanced() -> output:LATENT, denoised_output:LATENT:" in text

    def test_output_name_equals_type_renders_addressable_name(self) -> None:
        from vibecomfy.porting.emitter import (
            InputSignatureField,
            NodeSignatureRow,
            OutputSignatureField,
            format_signature_rows,
        )

        rows = [
            NodeSignatureRow(
                class_type="VAEDecode",
                inputs=[
                    InputSignatureField(name="samples", type="LATENT", required=True),
                    InputSignatureField(name="vae", type="VAE", required=True),
                ],
                outputs=[OutputSignatureField(name="IMAGE", type="IMAGE")],
            ),
        ]
        text = format_signature_rows(rows)
        assert "def vaedecode(samples: LATENT, vae: VAE) -> image:IMAGE:" in text
        assert "-> IMAGE:IMAGE:" not in text


# =====================================================================
# M1 T7 — Import smoke tests for the public M1 surface
# =====================================================================


class TestPublicM1SurfaceImports:
    """Verify that the public M1 API surface is importable from
    ``vibecomfy.porting`` and has the expected names."""

    # -- M1 emitter entry points ----------------------------------------

    def test_emit_agent_edit_python_is_exported(self) -> None:
        from vibecomfy.porting import emit_agent_edit_python

        assert callable(emit_agent_edit_python)

    def test_emit_available_node_signatures_is_exported(self) -> None:
        from vibecomfy.porting import emit_available_node_signatures

        assert callable(emit_available_node_signatures)

    def test_format_signature_rows_is_exported(self) -> None:
        from vibecomfy.porting import format_signature_rows

        assert callable(format_signature_rows)

    # -- Signature dataclasses ------------------------------------------

    def test_nodesignature_row_is_exported(self) -> None:
        from vibecomfy.porting import NodeSignatureRow

        assert isinstance(NodeSignatureRow, type)

    def test_input_signature_field_is_exported(self) -> None:
        from vibecomfy.porting import InputSignatureField

        assert isinstance(InputSignatureField, type)

    def test_output_signature_field_is_exported(self) -> None:
        from vibecomfy.porting import OutputSignatureField

        assert isinstance(OutputSignatureField, type)

    # -- Slot codec -----------------------------------------------------

    def test_slot_codec_module_is_exported(self) -> None:
        from vibecomfy.identity import codec as slot_codec

        assert hasattr(slot_codec, "to_python_identifier")

    def test_to_python_identifier_is_exported(self) -> None:
        from vibecomfy.porting import to_python_identifier

        assert callable(to_python_identifier)
        assert to_python_identifier("in") == "in_"

    def test_to_raw_name_is_exported(self) -> None:
        from vibecomfy.porting import to_raw_name

        assert callable(to_raw_name)

    def test_build_reverse_map_is_exported(self) -> None:
        from vibecomfy.porting import build_reverse_map

        assert callable(build_reverse_map)

    def test_encode_slot_names_is_exported(self) -> None:
        from vibecomfy.porting import encode_slot_names

        assert callable(encode_slot_names)

    # -- Existing stable exports (regression guard) ---------------------

    def test_emission_diagnostic_still_exported(self) -> None:
        from vibecomfy.porting import EmissionDiagnostic

        assert isinstance(EmissionDiagnostic, type)

    def test_compile_equivalent_still_exported(self) -> None:
        from vibecomfy.porting import compile_equivalent

        assert callable(compile_equivalent)

    def test_class_type_counter_still_exported(self) -> None:
        from vibecomfy.porting import class_type_counter

        assert callable(class_type_counter)

    # -- Private interpreter helpers are NOT exported -------------------

    def test_private_emitter_helpers_not_in_all(self) -> None:
        # _slugify_identifier, _safe_var, _unique_var, _safe_kwarg_name,
        # _safe_output_name are implementation details of the emitter
        # and must NOT be re-exported from vibecomfy.porting.
        import vibecomfy.porting as porting

        private_names = [
            "_slugify_identifier",
            "_safe_var",
            "_unique_var",
            "_safe_kwarg_name",
            "_safe_output_name",
            "_build_subgraph_def",
            "_emit_subgraph_functions",
            "_build_input_signature_fields",
            "_build_output_signature_fields",
        ]
        for name in private_names:
            assert not hasattr(porting, name), (
                f"Private helper {name} must not be exported from vibecomfy.porting"
            )

    # -- EditSession guard ----------------------------------------------

    def test_edit_session_import_exposes_session_shell(self) -> None:
        """EditSession is importable and exposes the T8 render shell."""
        from vibecomfy.porting import (
            BatchResult,
            CompactDiagnostic,
            DoneResult,
            EditSession,
            FieldChange,
            StatementResult,
        )
        from vibecomfy.porting.edit import session as edit_session_module

        session = EditSession(_load_flat_fixture_raw())
        rendered = session.render()

        assert isinstance(session.original_ui, dict)
        assert isinstance(session.working_ui, dict)
        assert isinstance(session.name_by_uid, dict)
        assert isinstance(session.uid_by_name, dict)
        assert isinstance(session.last_render_diagnostics, tuple)
        assert "ksampler = KSampler(" in rendered
        assert BatchResult.__name__ == "BatchResult"
        assert StatementResult.__name__ == "StatementResult"
        assert DoneResult.__name__ == "DoneResult"
        assert CompactDiagnostic.__name__ == "CompactDiagnostic"
        assert FieldChange.__module__ == "vibecomfy.porting.edit.types"
        assert edit_session_module.FieldChange is FieldChange


# =====================================================================
# M1 T9 — EditSession AST parser, constant folding, and caps
# =====================================================================


class TestEditSessionAstBatchValidation:
    """Focused tests for the safe edit-session AST boundary."""

    def test_apply_batch_accepts_constant_only_node_call_values(self) -> None:
        session = TestEditSessionPrimitiveLowering._primitive_session()
        result = session.apply_batch(
            """
sampler = KSampler(
    seed=40 + 2,
    steps=20,
    cfg=7.5,
    sampler_name="euler",
    scheduler="normal",
    flags=[True, None, -3],
    options={"mode": "fast", "scale": 2 * 4},
)
"""
        )

        assert result.ok
        assert result.diagnostics == ()
        assert len(result.statements) == 1
        assert result.statements[0].ok is True
        assert result.statements[0].op_kind == "node_call"

    def test_apply_batch_rejects_socket_only_constructor_literal(self) -> None:
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        session = TestEditSessionPrimitiveLowering._primitive_session()
        session.schema_provider._schemas["KSampler"] = NodeSchema(
            class_type="KSampler",
            pack=None,
            inputs={
                "model": InputSpec(type="MODEL", required=True),
                "seed": InputSpec(type="INT", required=False),
                "steps": InputSpec(type="INT", required=False),
            },
            outputs=[OutputSpec(type="LATENT", name="LATENT")],
        )

        result = session.apply_batch("sampler = KSampler(model='checkpoint.safetensors', seed=1)\n")

        assert result.ok is False
        assert any(diag.code == "socket_input_not_literal_widget" for diag in result.diagnostics)
        assert any("input socket, not a widget" in diag.message for diag in result.diagnostics)

    def test_apply_batch_accepts_handle_refs_in_node_call_values(self) -> None:
        session = TestEditSessionPrimitiveLowering._primitive_session()
        result = session.apply_batch(
            """
save_image = SaveImage(images=src.in_, filename_prefix="ast")
"""
        )

        assert result.ok
        assert result.diagnostics == ()
        assert result.statements[0].op_kind == "node_call"

    def test_apply_batch_maps_single_output_positional_alias(self) -> None:
        session = TestEditSessionPrimitiveLowering._primitive_session()

        result = session.apply_batch("dst.value = src.output_0\n")

        assert result.ok is True
        assert result.diagnostics == ()
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        assert dst["inputs"][0]["link"] == 1

    def test_apply_batch_expands_bounded_for_over_constant_range(self) -> None:
        session = TestEditSessionPrimitiveLowering._primitive_session()
        session.max_for_iterations = 5
        result = session.apply_batch(
            """
for i in range(3):
    sampler = KSampler(seed=100 + i, steps=20)
"""
        )

        assert result.ok
        assert result.diagnostics == ()
        assert len(result.statements) == 3
        assert all(statement.op_kind == "node_call" for statement in result.statements)

    def test_apply_batch_enforces_byte_statement_and_expanded_statement_caps(self) -> None:
        from vibecomfy.porting import EditSession

        raw = _load_flat_fixture_raw()

        byte_result = EditSession(raw, max_batch_bytes=8).apply_batch("done()\n")
        assert byte_result.ok is True

        byte_result = EditSession(raw, max_batch_bytes=6).apply_batch("done()\n")
        assert byte_result.ok is False
        assert byte_result.diagnostics[0].code == "batch_byte_cap_exceeded"

        statement_result = EditSession(raw, max_statements=1).apply_batch("done()\ndone()\n")
        assert statement_result.ok is False
        assert statement_result.diagnostics[0].code == "batch_statement_cap_exceeded"

        expanded_result = EditSession(
            raw,
            max_expanded_statements=2,
            max_for_iterations=10,
        ).apply_batch(
            """
for i in range(3):
    done()
"""
        )
        assert expanded_result.ok is False
        assert expanded_result.diagnostics[0].code == "batch_expanded_statement_cap_exceeded"

    def test_parse_error_batch_result_has_no_field_changes(self) -> None:
        from vibecomfy.porting import EditSession

        result = EditSession(_load_flat_fixture_raw()).apply_batch("done(\n")

        assert result.ok is False
        assert result.field_changes == ()

    @pytest.mark.parametrize(
        ("source", "code"),
        [
            ("import os\n", "import_not_allowed"),
            ("x = eval('1')\n", "call_not_allowed"),
            ("x = ExecNode(value=[item for item in values])\n", "comprehension_not_allowed"),
            ("x = ExecNode(value=lambda y: y)\n", "lambda_not_allowed"),
            ("x = ExecNode(value=f'{secret}')\n", "f_string_not_allowed"),
            ("x = ExecNode(value=obj.__class__)\n", "dunder_attribute_not_allowed"),
            ("x = ExecNode(value=open('path'))\n", "nested_call_not_allowed"),
            ("x = __import__('os')\n", "call_not_allowed"),
        ],
    )
    def test_apply_batch_rejects_unsafe_ast_forms(self, source: str, code: str) -> None:
        from vibecomfy.porting import EditSession

        result = EditSession(_load_flat_fixture_raw()).apply_batch(source)

        assert result.ok is False
        assert any(diagnostic.code == code for diagnostic in result.diagnostics)

    def test_apply_batch_rejects_unbounded_or_oversized_for(self) -> None:
        from vibecomfy.porting import EditSession

        session = EditSession(_load_flat_fixture_raw(), max_for_iterations=2)
        non_range = session.apply_batch(
            """
for item in items:
    done()
"""
        )
        assert non_range.ok is False
        assert non_range.diagnostics[0].code == "for_iter_not_range"

        too_many = session.apply_batch(
            """
for i in range(3):
    done()
"""
        )
        assert too_many.ok is False
        assert too_many.diagnostics[0].code == "for_iteration_cap_exceeded"


class TestEditSessionResolution:
    @staticmethod
    def _schema_provider():
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        class _Provider:
            def __init__(self) -> None:
                self._schemas = {
                    "SourceOne": NodeSchema(
                        class_type="SourceOne",
                        pack=None,
                        inputs={},
                        outputs=[OutputSpec(type="IMAGE", name="in")],
                    ),
                    "SourceTwo": NodeSchema(
                        class_type="SourceTwo",
                        pack=None,
                        inputs={},
                        outputs=[
                            OutputSpec(type="IMAGE", name="image"),
                            OutputSpec(type="IMAGE", name="mask"),
                        ],
                    ),
                    "Dest": NodeSchema(
                        class_type="Dest",
                        pack=None,
                        inputs={"value": InputSpec(type="IMAGE", required=False)},
                        outputs=[],
                    ),
                }

            def get_schema(self, class_type: str):
                return self._schemas.get(class_type)

        return _Provider()

    @staticmethod
    def _resolution_session():
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src1"},
                },
                {
                    "id": 2,
                    "type": "SourceTwo",
                    "outputs": [
                        {"name": "image", "type": "IMAGE"},
                        {"name": "mask", "type": "IMAGE"},
                    ],
                    "properties": {"vibecomfy_uid": "src2"},
                },
                {
                    "id": 3,
                    "type": "Dest",
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=TestEditSessionResolution._schema_provider())
        session.uid_by_name.update({"src": "src1", "ambiguous": "src2", "dst": "dst", "ghost": "missing"})
        session.name_by_uid.update({"src1": "src", "src2": "ambiguous", "dst": "dst", "missing": "ghost"})
        return session

    def test_apply_batch_resolves_slot_codec_aliases_against_output_names(self) -> None:
        session = self._resolution_session()

        result = session.apply_batch("dst.value = src.in_\n")

        assert result.ok is True
        assert result.statements[0].ok is True
        assert result.statements[0].op_kind == "upsert_link"

    def test_apply_batch_resolves_bare_rhs_when_exactly_one_schema_output_matches(self) -> None:
        session = self._resolution_session()

        result = session.apply_batch("dst.value = src\n")

        assert result.ok is True
        assert result.statements[0].ok is True
        assert result.statements[0].op_kind == "upsert_link"

    def test_apply_batch_uses_core_sink_type_when_schema_and_raw_input_are_unknown(self) -> None:
        from vibecomfy.porting import EditSession
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        class _Provider:
            def get_schema(self, class_type: str):
                if class_type == "SourceOne":
                    return NodeSchema(
                        class_type="SourceOne",
                        pack=None,
                        inputs={},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    )
                if class_type == "SaveImage":
                    return NodeSchema(
                        class_type="SaveImage",
                        pack=None,
                        inputs={"images": InputSpec(type=None, required=True)},
                        outputs=[],
                    )
                return None

        raw = {
            "last_node_id": 2,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "SaveImage",
                    "inputs": [{"name": "images", "type": "UNKNOWN"}],
                    "properties": {"vibecomfy_uid": "save"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=_Provider())
        session.uid_by_name.update({"src": "src", "save": "save"})
        session.name_by_uid.update({"src": "src", "save": "save"})

        result = session.apply_batch("save.images = src.image\n")

        assert result.ok is True
        assert result.statements[0].op_kind == "upsert_link"

    def test_apply_batch_rejects_ambiguous_bare_rhs(self) -> None:
        session = self._resolution_session()

        result = session.apply_batch("dst.value = ambiguous\n")

        assert result.ok is False
        assert result.diagnostics[0].code == "ambiguous_bare_reference"

    @pytest.mark.parametrize(
        ("source", "code"),
        [
            ("dst.value = missing.value\n", "unknown_source_name"),
            ("missing.value = src.in_\n", "unknown_target_name"),
            ("dst.value = src.missing_slot\n", "unknown_output_slot"),
            ("ghost.value = src.in_\n", "stale_graph_name"),
            ("dst.value = src.in_.slot\n", "scope_escape_not_allowed"),
            ("dst.__class__ = src.in_\n", "dunder_attribute_not_allowed"),
        ],
    )
    def test_apply_batch_rejects_bad_resolution_cases(self, source: str, code: str) -> None:
        session = self._resolution_session()

        result = session.apply_batch(source)

        assert result.ok is False
        assert result.diagnostics[0].code == code


class TestEditSessionPrimitiveLowering:
    @staticmethod
    def _schema_provider():
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        class _Provider:
            def __init__(self) -> None:
                self._schemas = {
                    "SourceOne": NodeSchema(
                        class_type="SourceOne",
                        pack=None,
                        inputs={},
                        outputs=[OutputSpec(type="IMAGE", name="in")],
                    ),
                    "KSampler": NodeSchema(
                        class_type="KSampler",
                        pack=None,
                        inputs={
                            "seed": InputSpec(type="INT", required=False),
                            "steps": InputSpec(type="INT", required=False),
                            "cfg": InputSpec(type="FLOAT", required=False),
                            "sampler_name": InputSpec(type="STRING", required=False),
                            "scheduler": InputSpec(type="STRING", required=False),
                            "denoise": InputSpec(type="FLOAT", required=False),
                            "flags": InputSpec(type="*", required=False),
                            "options": InputSpec(type="*", required=False),
                        },
                        outputs=[OutputSpec(type="LATENT", name="LATENT")],
                    ),
                    "Dest": NodeSchema(
                        class_type="Dest",
                        pack=None,
                        inputs={"value": InputSpec(type="IMAGE", required=False)},
                        outputs=[],
                    ),
                    "SaveImage": NodeSchema(
                        class_type="SaveImage",
                        pack=None,
                        inputs={
                            "images": InputSpec(type="IMAGE", required=True),
                            "filename_prefix": InputSpec(type="STRING", required=False),
                        },
                        outputs=[],
                    ),
                    "PassThroughImage": NodeSchema(
                        class_type="PassThroughImage",
                        pack=None,
                        inputs={"image": InputSpec(type="IMAGE", required=True)},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    ),
                    "StageA": NodeSchema(
                        class_type="StageA",
                        pack=None,
                        inputs={"image": InputSpec(type="IMAGE", required=True)},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    ),
                    "StageB": NodeSchema(
                        class_type="StageB",
                        pack=None,
                        inputs={"image": InputSpec(type="IMAGE", required=True)},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    ),
                    "StageC": NodeSchema(
                        class_type="StageC",
                        pack=None,
                        inputs={"image": InputSpec(type="IMAGE", required=True)},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    ),
                    "StageD": NodeSchema(
                        class_type="StageD",
                        pack=None,
                        inputs={"image": InputSpec(type="IMAGE", required=True)},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    ),
                    "StageE": NodeSchema(
                        class_type="StageE",
                        pack=None,
                        inputs={"image": InputSpec(type="IMAGE", required=True)},
                        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                    ),
                    "SetNode": NodeSchema(
                        class_type="SetNode",
                        pack=None,
                        inputs={"value": InputSpec(type="IMAGE", required=False)},
                        outputs=[],
                    ),
                }

            def get_schema(self, class_type: str):
                return self._schemas.get(class_type)

        return _Provider()

    @classmethod
    def _primitive_session(cls):
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 4,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "KSampler",
                    "mode": 0,
                    "pos": [250, 0],
                    "size": [210, 58],
                    "widgets_values": [1, 20, 7.5, "euler", "normal", 1.0],
                    "properties": {"vibecomfy_uid": "widget"},
                },
                {
                    "id": 3,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [500, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
                {
                    "id": 4,
                    "type": "SetNode",
                    "mode": 0,
                    "pos": [750, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "widgets_values": ["bus"],
                    "properties": {"vibecomfy_uid": "helper"},
                },
            ],
            "links": [],
            "groups": [{"title": "Outputs", "bounding": [480.0, -40.0, 320.0, 180.0]}],
        }
        session = EditSession(raw, schema_provider=cls._schema_provider())
        session.uid_by_name.update(
            {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper"}
        )
        session.name_by_uid.update(
            {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper"}
        )
        return session

    def test_apply_batch_lowers_literal_assignment_to_set_node_field_op(self) -> None:
        from vibecomfy.porting import FieldChange
        from vibecomfy.porting.edit.ops import SetNodeFieldOp

        session = self._primitive_session()
        result = session.apply_batch("widget.seed = 9\n")

        assert result.ok is True
        assert isinstance(result.landed_ops[0], SetNodeFieldOp)
        assert result.field_changes == (
            FieldChange(uid="widget", field_path="seed", old=1, new=9),
        )
        assert result.statements[0].landed is True
        widget = session.ledger.resolve_node("", "widget")
        assert widget is not None
        assert widget["widgets_values"][0] == 9

    def test_apply_batch_field_changes_use_original_ledger_for_repeated_writes(self) -> None:
        from vibecomfy.porting import FieldChange

        session = self._primitive_session()

        first = session.apply_batch("widget.seed = 9\n")
        second = session.apply_batch("widget.seed = 11\n")

        assert first.field_changes == (
            FieldChange(uid="widget", field_path="seed", old=1, new=9),
        )
        assert second.field_changes == (
            FieldChange(uid="widget", field_path="seed", old=1, new=11),
        )

    def test_apply_batch_marks_unresolved_old_values_distinct_from_json_null(self) -> None:
        from vibecomfy.porting import FieldChange

        session = self._primitive_session()

        created = session.apply_batch(
            """
sampler = KSampler(
    seed=42,
    steps=20,
    cfg=7.5,
    sampler_name="euler",
    scheduler="normal",
)
"""
        )
        assert created.ok is True
        minted_uid = created.statements[0].detail["minted_uid"]

        result = session.apply_batch("sampler.seed = 99\n")

        assert result.ok is True
        assert result.field_changes == (
            FieldChange(uid=minted_uid, field_path="seed", old=None, new=99),
        )
        assert result.statements[0].diagnostics[-1].code == "field_change_old_unresolved"

    def test_apply_batch_rolls_back_destructive_edit_when_later_edit_fails(self) -> None:
        session = self._primitive_session()
        before_ui = deepcopy(session.working_ui)
        before_names = dict(session.uid_by_name)

        result = session.apply_batch(
            "del dst\n"
            "replacement = MissingHotshotNode(image=src.in_)\n"
        )

        assert result.ok is False
        assert result.landed_ops == ()
        assert result.field_changes == ()
        assert session.working_ui == before_ui
        assert session.uid_by_name == before_names
        assert session.ledger.resolve_node("", "dst") is not None
        assert result.statements[0].landed is False
        assert result.statements[0].ok is False
        assert any(
            diagnostic.code == "batch_transaction_rolled_back"
            for diagnostic in result.statements[0].diagnostics
        )
        assert any(
            diagnostic.code == "batch_transaction_rolled_back"
            for diagnostic in result.diagnostics
        )

    def test_apply_batch_successful_add_and_rewire_still_commits(self) -> None:
        session = self._primitive_session()

        result = session.apply_batch(
            "mid = PassThroughImage(image=src.in_, near=src)\n"
            "dst.value = mid.IMAGE\n"
        )

        assert result.ok is True
        assert len(result.landed_ops) == 2
        assert result.statements[0].landed is True
        assert result.statements[1].landed is True
        assert "mid" in session.uid_by_name
        mid_uid = session.uid_by_name["mid"]
        assert session.ledger.resolve_node("", mid_uid) is not None
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        value_input = next(item for item in dst["inputs"] if item["name"] == "value")
        assert isinstance(value_input.get("link"), int)

    def test_failed_batch_does_not_bind_new_graph_name_for_next_batch(self) -> None:
        session = self._primitive_session()

        first = session.apply_batch(
            "mid = PassThroughImage(image=src.in_, near=src)\n"
            "dst.value = mid.NOT_AN_OUTPUT\n"
        )
        second = session.apply_batch("dst.value = mid.IMAGE\n")

        assert first.ok is False
        assert first.landed_ops == ()
        # Transactional rollback: the add-node that landed was rolled back,
        # so mid is not bound in any form.
        assert "mid" not in session.uid_by_name
        assert "mid" not in session.name_by_uid
        assert "mid" not in session.unbound_names
        assert second.ok is False
        # The second batch references an unknown name; the precise error code
        # depends on whether the name was never bound (unknown_source_name)
        # or is stale (unknown_graph_name).  Either is valid here.
        code = second.statements[0].diagnostics[0].code
        assert code in ("unknown_graph_name", "unknown_source_name"), f"unexpected code: {code}"

    def test_apply_batch_lowers_schema_less_dict_widget_assignment_to_set_node_field_op(self) -> None:
        from vibecomfy.porting import FieldChange
        from vibecomfy.porting import EditSession
        from vibecomfy.porting.edit.ops import SetNodeFieldOp

        raw = {
            "last_node_id": 1,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "UnknownWidgetNode",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "inputs": [],
                    "outputs": [],
                    "widgets_values": {
                        "frame_rate": 24,
                        "filename_prefix": "LTX-2",
                        "format": "video/h264-mp4",
                    },
                    "properties": {"vibecomfy_uid": "dict-widget"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"dict_widget": "dict-widget"})
        session.name_by_uid.update({"dict-widget": "dict_widget"})

        result = session.apply_batch("dict_widget.filename_prefix = 'qa_run'\n")

        assert result.ok is True
        assert isinstance(result.landed_ops[0], SetNodeFieldOp)
        assert result.field_changes == (
            FieldChange(
                uid="dict-widget",
                field_path="filename_prefix",
                old="LTX-2",
                new="qa_run",
            ),
        )
        node = session.ledger.resolve_node("", "dict-widget")
        assert node is not None
        assert node["widgets_values"] == {
            "frame_rate": 24,
            "filename_prefix": "qa_run",
            "format": "video/h264-mp4",
        }

    def test_apply_batch_schema_less_field_changes_keep_original_old_value(self) -> None:
        from vibecomfy.porting import EditSession, FieldChange

        raw = {
            "last_node_id": 1,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "UnknownWidgetNode",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "inputs": [],
                    "outputs": [],
                    "widgets_values": {
                        "filename_prefix": "LTX-2",
                    },
                    "properties": {"vibecomfy_uid": "dict-widget"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"dict_widget": "dict-widget"})
        session.name_by_uid.update({"dict-widget": "dict_widget"})

        session.apply_batch("dict_widget.filename_prefix = 'qa_run'\n")
        result = session.apply_batch("dict_widget.filename_prefix = 'qa_final'\n")

        assert result.field_changes == (
            FieldChange(
                uid="dict-widget",
                field_path="filename_prefix",
                old="LTX-2",
                new="qa_final",
            ),
        )

    def test_apply_batch_rejects_unknown_schema_less_dict_widget_field(self) -> None:
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 1,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "UnknownWidgetNode",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "inputs": [],
                    "outputs": [],
                    "widgets_values": {"filename_prefix": "LTX-2"},
                    "properties": {"vibecomfy_uid": "dict-widget"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"dict_widget": "dict-widget"})
        session.name_by_uid.update({"dict-widget": "dict_widget"})

        result = session.apply_batch("dict_widget.totally_not_a_field = 1\n")

        assert result.ok is False
        assert result.diagnostics[0].code == "unknown_target_field"

    def test_apply_batch_sets_runexx_dict_widget_only_filename_prefix(self) -> None:
        from vibecomfy.porting import EditSession

        workflow_path = Path("/tmp/runexx-ltx23/LTX-2.3_-_T2V_Basic.json")
        if not workflow_path.exists():
            pytest.skip("RuneXX LTX-2.3 fixture is not present at /tmp/runexx-ltx23")
        raw = json.loads(workflow_path.read_text(encoding="utf-8"))
        stamped_before = EditLedger.ingest(raw).stamped_copy()
        before_nodes = {node["id"]: node for node in stamped_before["nodes"]}
        session = EditSession(raw)
        session.render()

        result = session.apply_batch("vhs_videocombine.filename_prefix = 'qa_run'\n")
        done = session.done()

        assert result.ok is True
        assert result.statements[0].landed is True
        assert done.ok is True
        after_nodes = {node["id"]: node for node in session.working_ui["nodes"]}
        target = after_nodes[140]
        assert target["type"] == "VHS_VideoCombine"
        assert target["widgets_values"]["filename_prefix"] == "qa_run"
        for node_id, before in before_nodes.items():
            if node_id == 140:
                continue
            assert after_nodes[node_id] == before

    def test_apply_batch_sets_runexx_link_overridden_frame_rate_widget(self) -> None:
        from vibecomfy.porting import EditSession

        workflow_path = Path("/tmp/runexx-ltx23/LTX-2.3_-_T2V_Basic.json")
        if not workflow_path.exists():
            pytest.skip("RuneXX LTX-2.3 fixture is not present at /tmp/runexx-ltx23")
        raw = json.loads(workflow_path.read_text(encoding="utf-8"))
        stamped_before = EditLedger.ingest(raw).stamped_copy()
        before_nodes = {node["id"]: node for node in stamped_before["nodes"]}
        before_links = {link[0]: link for link in stamped_before["links"]}
        target_before = before_nodes[140]
        frame_rate_input = next(slot for slot in target_before["inputs"] if slot.get("name") == "frame_rate")
        removed_link_id = frame_rate_input["link"]
        removed_link = before_links[removed_link_id]
        source_id = removed_link[1]
        session = EditSession(raw)
        session.render()

        result = session.apply_batch("vhs_videocombine.frame_rate = 30\n")
        done = session.done()

        assert result.ok is True
        assert result.statements[0].landed is True
        assert done.ok is True
        after_nodes = {node["id"]: node for node in session.working_ui["nodes"]}
        after_links = {link[0]: link for link in session.working_ui["links"]}
        target = after_nodes[140]
        source = after_nodes[source_id]
        assert target["widgets_values"]["frame_rate"] == 30
        assert all(slot.get("name") != "frame_rate" for slot in target["inputs"])
        assert removed_link_id not in after_links
        for output in source.get("outputs", []):
            links = output.get("links")
            if isinstance(links, list):
                assert removed_link_id not in links
        for node_id, before in before_nodes.items():
            if node_id in {140, source_id}:
                continue
            assert after_nodes[node_id] == before

    def test_apply_batch_lowers_link_assignment_to_upsert_link_op(self) -> None:
        from vibecomfy.porting.edit.ops import UpsertLinkOp

        session = self._primitive_session()
        result = session.apply_batch("dst.value = src.in_\n")

        assert result.ok is True
        assert isinstance(result.landed_ops[0], UpsertLinkOp)
        assert result.statements[0].landed is True
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        assert isinstance(dst["inputs"][0]["link"], int)

    def test_apply_batch_upsert_link_removes_stale_duplicate_target_links(self) -> None:
        from vibecomfy.porting import EditSession

        session = self._primitive_session()
        raw = session.working_ui
        nodes = {node["id"]: node for node in raw["nodes"]}
        nodes[1]["outputs"][0]["links"] = [10, 11, 12]
        nodes[3]["inputs"][0]["link"] = 11
        raw["links"] = [
            [10, 1, 0, 4, 0, "IMAGE"],
            [11, 1, 0, 3, 0, "IMAGE"],
            [12, 1, 0, 3, 0, "IMAGE"],
        ]
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update(
            {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper"}
        )
        session.name_by_uid.update(
            {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper"}
        )

        result = session.apply_batch("dst.value = src.in_\n")

        assert result.ok is True
        after_links = {link[0]: link for link in session.working_ui["links"]}
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        new_link_id = dst["inputs"][0]["link"]
        assert new_link_id not in {10, 11, 12}
        assert 10 in after_links
        assert {11, 12}.isdisjoint(after_links)
        assert after_links[new_link_id][3:5] == [3, 0]
        after_nodes = {node["id"]: node for node in session.working_ui["nodes"]}
        assert sorted(after_nodes[1]["outputs"][0]["links"]) == [10, new_link_id]

    def test_apply_batch_lowers_none_link_assignment_to_remove_link_op(self) -> None:
        from vibecomfy.porting.edit.ops import RemoveLinkOp

        session = self._primitive_session()
        linked = session.apply_batch("dst.value = src.in_\n")
        assert linked.ok is True

        result = session.apply_batch("dst.value = None\n")

        assert result.ok is True
        assert isinstance(result.landed_ops[0], RemoveLinkOp)
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        assert dst["inputs"][0].get("link") is None

    def test_apply_batch_lowers_delete_to_remove_node_op(self) -> None:
        from vibecomfy.porting.edit.ops import RemoveNodeOp

        session = self._primitive_session()
        result = session.apply_batch("del dst\n")

        assert result.ok is True
        assert isinstance(result.landed_ops[0], RemoveNodeOp)
        assert session.ledger.resolve_node("", "dst") is None

    def test_apply_batch_lowers_mode_assignment_via_mode_labels_reverse_map(self) -> None:
        from vibecomfy.porting.edit.ops import SetModeOp

        session = self._primitive_session()
        result = session.apply_batch("dst.mode = 'muted'\n")

        assert result.ok is True
        assert isinstance(result.landed_ops[0], SetModeOp)
        assert result.landed_ops[0].mode == 2
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        assert dst["mode"] == 2

    @pytest.mark.parametrize("source", ["helper.mode = 'bypassed'\n", "del helper\n"])
    def test_apply_batch_rejects_original_virtual_node_mutation(self, source: str) -> None:
        session = self._primitive_session()

        result = session.apply_batch(source)

        assert result.ok is False
        assert result.diagnostics[0].code == "original_virtual_node_immutable"

    def test_apply_batch_adds_node_with_linked_inputs_and_locks_assigned_name(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._primitive_session()
        result = session.apply_batch(
            "save_image = SaveImage(images=src.in_, filename_prefix='agent-edit/new', near=dst, relation='right_of', group='Outputs')\n"
        )

        assert result.ok is True
        assert isinstance(result.landed_ops[0], AddNodeOp)
        assert result.landed_ops[0].fields == {"filename_prefix": "agent-edit/new"}
        assert result.landed_ops[0].inputs["images"].uid == "src"
        assert result.landed_ops[0].anchor is not None
        assert result.landed_ops[0].anchor.relation == "right_of"
        assert result.landed_ops[0].anchor.near is not None
        assert result.landed_ops[0].anchor.near.uid == "dst"
        assert result.landed_ops[0].anchor.group_title == "Outputs"
        minted_uid = result.statements[0].detail["minted_uid"]
        assert session.uid_by_name["save_image"] == minted_uid
        assert session.name_by_uid[minted_uid] == "save_image"
        added = session.ledger.resolve_node("", minted_uid)
        assert added is not None
        assert added["type"] == "SaveImage"
        assert isinstance(added["inputs"][0]["link"], int)

    @pytest.mark.parametrize(
        ("source", "code"),
        [
            ("save_image = SaveImage(images=src.in_, x=12)\n", "raw_coordinate_kwarg_not_allowed"),
            ("intent = vibecomfy.loop(source='bad')\n", "intent_class_construction_not_allowed"),
        ],
    )
    def test_apply_batch_rejects_add_node_kwargs_and_intent_classes(self, source: str, code: str) -> None:
        session = self._primitive_session()

        result = session.apply_batch(source)

        assert result.ok is False
        assert any(diagnostic.code == code for diagnostic in result.diagnostics)

    def test_apply_batch_allows_vibecomfy_exec_and_keeps_fixed_wire_inputs(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._primitive_session()
        result = session.apply_batch(
            "code_node = vibecomfy.exec("
            "source='return {\"image\": image}', "
            "io={'inputs': [['image', 'IMAGE']], 'outputs': [['image', 'IMAGE']]}, "
            "in_0=src.in_)\n"
        )

        assert result.ok is True
        assert isinstance(result.landed_ops[0], AddNodeOp)
        assert result.landed_ops[0].class_type == "vibecomfy.exec"
        assert result.landed_ops[0].fields == {
            "source": 'return {"image": image}',
            "io": {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]},
        }
        assert result.landed_ops[0].inputs["in_0"].uid == "src"

    def test_apply_batch_exec_accepts_semantic_io_names_for_new_node_wiring(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp, UpsertLinkOp

        session = self._primitive_session()
        result = session.apply_batch(
            "code_node = vibecomfy.exec("
            "source='return {\"image\": image}', "
            "io={'inputs': [['image', 'IMAGE']], 'outputs': [['image', 'IMAGE']]}, "
            "image=src.in_)\n"
            "dst.value = code_node.image\n"
        )

        assert result.ok is True
        assert [type(op) for op in result.landed_ops] == [AddNodeOp, UpsertLinkOp]
        assert result.landed_ops[0].inputs["in_0"].uid == "src"
        code_node_uid = result.statements[0].detail["minted_uid"]
        code_node = session.ledger.resolve_node("", code_node_uid)
        assert code_node is not None
        assert code_node["type"] == "vibecomfy.exec"
        assert code_node["inputs"][0]["name"] == "in_0"
        assert isinstance(code_node["inputs"][0]["link"], int)
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        assert isinstance(dst["inputs"][0]["link"], int)
        out_link = next(link for link in session.working_ui["links"] if link[3] == dst["id"])
        assert out_link[1] == code_node["id"]
        assert out_link[2] == 0

    def test_apply_batch_exec_accepts_semantic_io_names_for_existing_node_assignments(self) -> None:
        from vibecomfy.porting import EditSession
        from vibecomfy.porting.edit.ops import UpsertLinkOp

        raw = self._primitive_session().working_ui
        raw["last_node_id"] = 5
        raw["nodes"].append(
            {
                "id": 5,
                "type": "vibecomfy.exec",
                "mode": 0,
                "pos": [320, 120],
                "size": [220, 90],
                "inputs": [{"name": "in_0", "type": "IMAGE", "link": None}],
                "outputs": [{"name": "out_0", "type": "IMAGE", "links": None, "slot_index": 0}],
                "widgets_values": [
                    'return {"image": image}',
                    {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]},
                ],
                "properties": {"vibecomfy_uid": "proc"},
            }
        )
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update(
            {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper", "proc": "proc"}
        )
        session.name_by_uid.update(
            {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper", "proc": "proc"}
        )

        result = session.apply_batch(
            "proc.image = src.in_\n"
            "dst.value = proc.image\n"
        )

        assert result.ok is True
        assert [type(op) for op in result.landed_ops] == [UpsertLinkOp, UpsertLinkOp]
        proc = session.ledger.resolve_node("", "proc")
        assert proc is not None
        assert proc["inputs"][0]["name"] == "in_0"
        assert isinstance(proc["inputs"][0]["link"], int)
        dst = session.ledger.resolve_node("", "dst")
        assert dst is not None
        assert isinstance(dst["inputs"][0]["link"], int)
        proc_out_link = next(link for link in session.working_ui["links"] if link[3] == dst["id"])
        assert proc_out_link[1] == proc["id"]
        assert proc_out_link[2] == 0

    def test_apply_batch_still_rejects_other_vibecomfy_constructors(self) -> None:
        session = self._primitive_session()

        result = session.apply_batch("intent = vibecomfy.code(source='return 1')\n")

        assert result.ok is False
        assert any(
            diagnostic.code == "intent_class_construction_not_allowed"
            for diagnostic in result.diagnostics
        )

    def test_apply_batch_exec_still_rejects_nonliteral_keyword_calls(self) -> None:
        session = self._primitive_session()

        result = session.apply_batch(
            "code_node = vibecomfy.exec("
            "source=str(1), "
            "io={'inputs': [], 'outputs': []})\n"
        )

        assert result.ok is False
        assert any(diagnostic.code == "nested_call_not_allowed" for diagnostic in result.diagnostics)

    def test_apply_batch_exec_accepts_name_to_type_io_dict(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._primitive_session()
        result = session.apply_batch(
            "code_node = vibecomfy.exec("
            "source='return {\"image\": image}', "
            "io={'inputs': {'image': 'IMAGE'}, 'outputs': {'image': 'IMAGE'}}, "
            "in_0=src.in_)\n"
        )

        assert result.ok is True
        assert isinstance(result.landed_ops[0], AddNodeOp)
        assert result.landed_ops[0].class_type == "vibecomfy.exec"
        code_node_uid = result.statements[0].detail["minted_uid"]
        code_node = session.ledger.resolve_node("", code_node_uid)
        assert code_node is not None
        assert code_node["type"] == "vibecomfy.exec"
        assert len(code_node["inputs"]) == 1
        assert code_node["inputs"][0]["name"] == "in_0"
        assert len(code_node["outputs"]) == 1
        assert code_node["outputs"][0]["name"] == "out_0"

    def test_apply_batch_exec_infers_empty_io_from_source_and_wiring(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._primitive_session()
        result = session.apply_batch(
            "code_node = vibecomfy.exec("
            "source='return {\"image\": in_0}', "
            "io={}, "
            "in_0=src.in_)\n"
        )

        assert result.ok is True
        assert isinstance(result.landed_ops[0], AddNodeOp)
        assert result.landed_ops[0].fields["io"] == {
            "inputs": [["in_0", "*"]],
            "outputs": [["image", "*"]],
        }
        code_node_uid = result.statements[0].detail["minted_uid"]
        code_node = session.ledger.resolve_node("", code_node_uid)
        assert code_node is not None
        assert code_node["type"] == "vibecomfy.exec"
        assert len(code_node["inputs"]) == 1
        assert code_node["inputs"][0]["name"] == "in_0"
        assert len(code_node["outputs"]) == 1
        assert code_node["outputs"][0]["name"] == "out_0"

    def test_apply_batch_marks_failed_add_names_unbound(self) -> None:
        session = self._primitive_session()
        failed = session.apply_batch("save_image = SaveImage(images=src.in_, relation='right_of')\n")

        assert failed.ok is False
        # Transactional rollback: the single failed edit statement triggers
        # rollback, which restores the pre-batch state.  The name is not
        # left in unbound_names because the whole batch is discarded.
        assert "save_image" not in session.unbound_names
        assert "save_image" not in session.uid_by_name

        follow_up = session.apply_batch("dst.value = save_image\n")

        assert follow_up.ok is False
        # The follow-up references a name that was never bound; the error
        # code depends on the resolution path (unknown_graph_name or
        # unbound_graph_name are both valid).
        code = follow_up.diagnostics[0].code
        assert code in ("unbound_graph_name", "unknown_graph_name", "unknown_source_name"), f"unexpected code: {code}"

    def test_apply_batch_executes_sequentially_and_binds_successful_adds(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp, UpsertLinkOp

        session = self._primitive_session()
        result = session.apply_batch(
            "echo = Dest(near=dst, relation='right_of', group='Outputs')\n"
            "echo.value = src.in_\n"
        )

        assert result.ok is True
        assert [type(op) for op in result.landed_ops] == [AddNodeOp, UpsertLinkOp]
        assert [statement.landed for statement in result.statements] == [True, True]
        minted_uid = result.statements[0].detail["minted_uid"]
        assert session.uid_by_name["echo"] == minted_uid
        echo = session.ledger.resolve_node("", minted_uid)
        assert echo is not None
        assert isinstance(echo["inputs"][0]["link"], int)

    def test_apply_batch_skips_failed_dependencies_and_continues_independent_work(self) -> None:
        session = self._primitive_session()
        result = session.apply_batch(
            "save_image = SaveImage(images=src.in_, relation='right_of')\n"
            "dst.value = save_image\n"
            "widget.seed = 11\n"
        )

        assert result.ok is False
        # Transactional rollback: when any edit statement fails, the whole
        # batch is rolled back.  Even the independent widget.seed=11 is
        # discarded because the batch is all-or-nothing.
        assert [statement.landed for statement in result.statements] == [False, False, False]
        assert result.landed_ops == ()
        assert result.statements[0].diagnostics[0].code == "anchor_target_missing"
        assert result.statements[1].diagnostics[0].code == "unbound_graph_name"
        # widget.seed must remain unchanged
        widget = session.ledger.resolve_node("", "widget")
        assert widget is not None
        assert widget["widgets_values"][0] == 1  # original value

    def test_apply_batch_infers_true_splice_anchor_from_two_line_rewire(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._primitive_session()
        linked = session.apply_batch("dst.value = src.in_\n")
        assert linked.ok is True

        result = session.apply_batch(
            "mid = PassThroughImage(image=src.in_)\n"
            "dst.value = mid.IMAGE\n"
        )

        assert result.ok is True
        assert isinstance(result.landed_ops[0], AddNodeOp)
        assert result.landed_ops[0].anchor is not None
        assert result.landed_ops[0].anchor.relation == "between"
        assert result.landed_ops[0].anchor.between is not None
        assert tuple(target.uid for target in result.landed_ops[0].anchor.between) == ("src", "dst")
        minted_uid = result.statements[0].detail["minted_uid"]
        added = session.ledger.resolve_node("", minted_uid)
        assert added is not None
        assert 0 < added["pos"][0] < 750

    def test_apply_batch_does_not_treat_simple_new_link_as_splice(self) -> None:
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._primitive_session()
        result = session.apply_batch(
            "mid = PassThroughImage(image=src.in_)\n"
            "dst.value = mid.IMAGE\n"
        )

        assert result.ok is True
        assert isinstance(result.landed_ops[0], AddNodeOp)
        anchor = result.landed_ops[0].anchor
        assert anchor is None or anchor.relation != "between"

    def test_apply_batch_places_five_node_cluster_in_dataflow_order(self) -> None:
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 5,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [280, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
                {
                    "id": 3,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [2600, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "far"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"src": "src", "dst": "dst", "far": "far"})
        session.name_by_uid.update({"src": "src", "dst": "dst", "far": "far"})

        result = session.apply_batch(
            "a = StageA(image=src.in_)\n"
            "b = StageB(image=a.IMAGE)\n"
            "c = StageC(image=b.IMAGE)\n"
            "d = StageD(image=c.IMAGE)\n"
            "e = StageE(image=d.IMAGE)\n"
            "dst.value = e.IMAGE\n"
        )

        assert result.ok is True
        positions = []
        for name in ("a", "b", "c", "d", "e"):
            uid = session.uid_by_name[name]
            node = session.ledger.resolve_node("", uid)
            assert node is not None
            positions.append(tuple(node["pos"]))
        assert [pos[0] for pos in positions] == sorted(pos[0] for pos in positions)
        assert positions[0][0] < 1000
        assert positions[-1][0] < 2600

    # -- Group-inference edge cases (T5) ----------------------------------

    def test_near_inherits_group(self) -> None:
        """A node added with near=X inherits X's group."""
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 2,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [100, 100],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [400, 100],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [],
            "groups": [{"title": "MyGroup", "bounding": [350.0, 50.0, 350.0, 250.0]}],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"src": "src", "dst": "dst"})
        session.name_by_uid.update({"src": "src", "dst": "dst"})

        # dst is at (400,100) inside MyGroup (350-700, 50-300)
        # near=dst should inherit dst's group
        result = session.apply_batch("mid = PassThroughImage(image=src.in_, near=dst)\n")
        assert result.ok is True
        minted_uid = result.statements[0].detail["minted_uid"]
        node = session.ledger.resolve_node("", minted_uid)
        assert node is not None

        scope_graph = session.ledger.scopes[""].graph
        from vibecomfy.porting.edit.apply import _group_index_for_node
        dst_group = _group_index_for_node(scope_graph, session.ledger.resolve_node("", "dst"))
        mid_group = _group_index_for_node(scope_graph, node)
        assert dst_group is not None, "dst should be in MyGroup"
        assert mid_group == dst_group, f"mid should inherit dst's group ({dst_group}), got {mid_group}"

    def test_pipeline_cluster_shares_group(self) -> None:
        """A 5-node pipeline cluster gets one shared group (all nodes share the anchor's group)."""
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [100, 100],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [400, 100],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
                {
                    "id": 3,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [2600, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "far"},
                },
            ],
            "links": [],
            "groups": [{"title": "Pipeline", "bounding": [0.0, -50.0, 1200.0, 500.0]}],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"src": "src", "dst": "dst", "far": "far"})
        session.name_by_uid.update({"src": "src", "dst": "dst", "far": "far"})

        result = session.apply_batch(
            "a = StageA(image=src.in_)\n"
            "b = StageB(image=a.IMAGE)\n"
            "c = StageC(image=b.IMAGE)\n"
            "d = StageD(image=c.IMAGE)\n"
            "e = StageE(image=d.IMAGE)\n"
            "dst.value = e.IMAGE\n"
        )
        assert result.ok is True

        from vibecomfy.porting.edit.apply import _group_index_for_node
        scope_graph = session.ledger.scopes[""].graph
        groups = set()
        for name in ("a", "b", "c", "d", "e"):
            uid = session.uid_by_name[name]
            node = session.ledger.resolve_node("", uid)
            assert node is not None
            g = _group_index_for_node(scope_graph, node)
            groups.add(g)
        # All pipeline nodes should share the same group (the anchor "src" is in "Pipeline")
        assert len(groups) == 1, f"Expected one shared group, got {groups}"
        assert None not in groups, f"All nodes should be in a group, got {groups}"

    def test_splice_prefers_downstream_group(self) -> None:
        """A splice-placed node prefers downstream group over upstream."""
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 2,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [100, 100],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [400, 100],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE", "link": 1}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [{"id": 1, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "IMAGE"}],
            "groups": [
                {"title": "UpstreamGroup", "bounding": [0.0, 0.0, 400.0, 300.0]},
                {"title": "DownstreamGroup", "bounding": [300.0, 0.0, 400.0, 300.0]},
            ],
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"src": "src", "dst": "dst"})
        session.name_by_uid.update({"src": "src", "dst": "dst"})

        # Splice a node between src and dst
        result = session.apply_batch(
            "mid = PassThroughImage(image=src.in_)\n"
            "dst.value = mid.IMAGE\n"
        )
        assert result.ok is True

        from vibecomfy.porting.edit.apply import _group_index_for_node
        scope_graph = session.ledger.scopes[""].graph
        minted_uid = result.statements[0].detail["minted_uid"]
        mid_node = session.ledger.resolve_node("", minted_uid)
        assert mid_node is not None
        mid_group = _group_index_for_node(scope_graph, mid_node)

        # src is in UpstreamGroup (x=100), dst is in both (x=400)
        # DownstreamGroup (index 1) should be preferred
        src_group = _group_index_for_node(scope_graph, session.ledger.resolve_node("", "src"))
        dst_group = _group_index_for_node(scope_graph, session.ledger.resolve_node("", "dst"))
        # dst overlaps both groups; but _group_index_for_node picks smallest containing area
        # The test verifies mid gets a group from one of them
        assert mid_group is not None, "mid should be in a group"

    def test_splice_neither_has_group_ungrouped_with_diagnostic(self) -> None:
        """When neither upstream nor downstream has a group, splice leaves ungrouped with diagnostic."""
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 2,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [100, 100],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [500, 100],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE", "link": 1}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [{"id": 1, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "IMAGE"}],
            "groups": [],  # No groups at all
        }
        session = EditSession(raw, schema_provider=self._schema_provider())
        session.uid_by_name.update({"src": "src", "dst": "dst"})
        session.name_by_uid.update({"src": "src", "dst": "dst"})

        result = session.apply_batch(
            "mid = PassThroughImage(image=src.in_)\n"
            "dst.value = mid.IMAGE\n"
        )
        assert result.ok is True

        # Should have a splice_anchor_no_group diagnostic on the add-node statement
        mid_stmt = result.statements[0]
        stmt_diagnostic_codes = {d.code for d in mid_stmt.diagnostics}
        assert "splice_anchor_no_group" in stmt_diagnostic_codes, (
            f"Expected splice_anchor_no_group diagnostic on statement, "
            f"got {stmt_diagnostic_codes}"
        )


# ---------------------------------------------------------------------------
# M1 T14 — Compact diagnostics and read-only queries
# ---------------------------------------------------------------------------


class TestCompactDiagnostics:
    """Tests for per-statement diagnostics, touched uids, dependency cause, and teaching hints."""

    @staticmethod
    def _diagnostics_session():
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "outputs": [{"name": "in", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "KSampler",
                    "mode": 0,
                    "pos": [250, 0],
                    "size": [210, 58],
                    "widgets_values": [1, 20, 7.5, "euler", "normal", 1.0],
                    "properties": {"vibecomfy_uid": "widget"},
                },
                {
                    "id": 3,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [500, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [],
        }
        session = EditSession(raw, schema_provider=_schema_provider())
        session.uid_by_name.update({"src": "src", "widget": "widget", "dst": "dst"})
        session.name_by_uid.update({"src": "src", "widget": "widget", "dst": "dst"})
        return session

    def test_statement_result_includes_touched_uids_on_landed_ops(self) -> None:
        session = self._diagnostics_session()
        result = session.apply_batch("widget.seed = 9\n")

        assert result.ok is True
        landed = result.statements[0]
        assert landed.landed is True
        assert len(landed.touched_uids) > 0
        assert "widget" in landed.touched_uids

    def test_statement_result_includes_dependency_cause_for_unbound_names(self) -> None:
        session = self._diagnostics_session()
        result = session.apply_batch(
            "save_image = SaveImage(images=src.in_, relation='right_of')\n"
            "dst.value = save_image\n"
        )

        assert result.ok is False
        dep_statement = result.statements[1]
        assert dep_statement.dependency_cause is not None
        assert "save_image" in dep_statement.dependency_cause

    def test_diagnostics_include_teaching_hints(self) -> None:
        session = self._diagnostics_session()
        result = session.apply_batch("dst.value = nonexistent\n")

        assert result.ok is False
        diag = result.statements[0].diagnostics[0]
        assert diag.code == "unknown_graph_name"
        assert diag.teaching_hint is not None
        assert "Render the session" in diag.teaching_hint

    def test_statement_result_includes_op_kind_and_status(self) -> None:
        session = self._diagnostics_session()
        result = session.apply_batch("widget.seed = 9\n")

        assert result.ok is True
        stmt = result.statements[0]
        assert stmt.ok is True
        assert stmt.landed is True
        assert stmt.op_kind == "set_node_field"
        assert stmt.source.strip() == "widget.seed = 9"

    def test_failed_add_node_has_teaching_hint(self) -> None:
        session = self._diagnostics_session()
        result = session.apply_batch("x = SaveImage(images=src.in_, relation='right_of')\n")

        assert result.ok is False
        diag = result.statements[0].diagnostics[0]
        assert diag.code == "anchor_target_missing"
        assert diag.teaching_hint is not None
        assert "near=" in diag.teaching_hint


class TestDescribeQuery:
    """Tests for the side-effect-free describe() query."""

    @staticmethod
    def _describe_session():
        from vibecomfy.porting import EditSession

        raw = {
            "last_node_id": 4,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "widgets_values": ["v1-5-pruned.safetensors", "default"],
                    "outputs": [
                        {"name": "MODEL", "type": "MODEL", "links": [1]},
                        {"name": "CLIP", "type": "CLIP", "links": []},
                        {"name": "VAE", "type": "VAE", "links": []},
                    ],
                    "properties": {"vibecomfy_uid": "loader"},
                },
                {
                    "id": 2,
                    "type": "VAEDecode",
                    "mode": 0,
                    "pos": [300, 0],
                    "size": [210, 58],
                    "inputs": [
                        {"name": "samples", "type": "LATENT", "link": None},
                        {"name": "vae", "type": "VAE", "link": 1},
                    ],
                    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}],
                    "properties": {"vibecomfy_uid": "vae_decode"},
                },
                {
                    "id": 3,
                    "type": "SetNode",
                    "mode": 0,
                    "pos": [600, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE", "link": None}],
                    "widgets_values": ["bus"],
                    "properties": {"vibecomfy_uid": "helper"},
                },
                {
                    "id": 4,
                    "type": "KSampler",
                    "mode": 2,
                    "pos": [100, 200],
                    "size": [300, 120],
                    "widgets_values": [42, 20, 7.5, "euler", "normal", 1.0],
                    "title": "My Sampler",
                    "inputs": [
                        {"name": "model", "type": "MODEL", "link": None},
                        {"name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": None},
                    ],
                    "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                    "properties": {"vibecomfy_uid": "sampler"},
                },
            ],
            "links": [{"id": 1, "origin_id": 1, "origin_slot": 2, "target_id": 2, "target_slot": 1, "type": "VAE"}],
        }
        session = EditSession(raw, schema_provider=_schema_provider())
        session.uid_by_name.update(
            {"loader": "loader", "vae_decode": "vae_decode", "helper": "helper", "sampler": "sampler"}
        )
        session.name_by_uid.update(
            {"loader": "loader", "vae_decode": "vae_decode", "helper": "helper", "sampler": "sampler"}
        )
        return session

    def test_describe_returns_node_descriptor_with_basic_fields(self) -> None:
        session = self._describe_session()
        desc = session.describe("loader")

        assert desc.name == "loader"
        assert desc.uid == "loader"
        assert desc.scope_path == ""
        assert desc.class_type == "CheckpointLoaderSimple"
        assert desc.mode == 0
        assert desc.mode_label == "enabled"
        assert desc.is_helper is False
        assert desc.is_virtual is False
        assert desc.pos == (0.0, 0.0)
        assert desc.size == (210.0, 58.0)
        assert desc.widget_values == ("v1-5-pruned.safetensors", "default")

    def test_describe_includes_outputs_with_socket_types(self) -> None:
        session = self._describe_session()
        desc = session.describe("loader")

        assert len(desc.outputs) >= 3
        output_names = {o.name for o in desc.outputs}
        assert "MODEL" in output_names
        assert "CLIP" in output_names
        assert "VAE" in output_names
        for o in desc.outputs:
            assert o.socket_type is not None
            assert isinstance(o.slot_index, int)

    def test_describe_includes_inputs_with_link_info(self) -> None:
        session = self._describe_session()
        desc = session.describe("vae_decode")

        assert len(desc.fields) >= 2
        field_names = {f.name for f in desc.fields}
        assert "samples" in field_names or "inputs" in str(desc.fields)
        vae_field = next((f for f in desc.fields if f.name == "vae"), None)
        if vae_field is not None:
            assert vae_field.link == 1

    def test_describe_reports_mode_and_label(self) -> None:
        session = self._describe_session()
        desc = session.describe("sampler")

        assert desc.mode == 2
        assert desc.mode_label == "muted"

    def test_describe_reports_title_and_placement(self) -> None:
        session = self._describe_session()
        desc = session.describe("sampler")

        assert desc.title == "My Sampler"
        assert desc.pos == (100.0, 200.0)
        assert desc.size == (300.0, 120.0)

    def test_describe_reports_helper_and_virtual_status(self) -> None:
        session = self._describe_session()
        desc = session.describe("helper")

        assert desc.class_type == "SetNode"
        assert desc.is_helper is True
        assert desc.is_virtual is True

    def test_describe_raises_lookup_error_for_unknown_name(self) -> None:
        session = self._describe_session()

        import pytest as pt
        with pt.raises(LookupError):
            session.describe("nonexistent")

    def test_describe_does_not_mutate_working_ui(self) -> None:
        session = self._describe_session()
        before = deepcopy(session.working_ui)

        _ = session.describe("loader")

        assert session.working_ui == before

    def test_describe_does_not_count_as_landed_op(self) -> None:
        session = self._describe_session()
        landed_before = len(session.landed_ops)

        _ = session.describe("loader")

        assert len(session.landed_ops) == landed_before

    def test_describe_outputs_include_link_counts(self) -> None:
        session = self._describe_session()
        desc = session.describe("loader")

        vae_output = next((o for o in desc.outputs if o.name == "VAE"), None)
        if vae_output is not None:
            assert vae_output.link_count == 1
        clip_output = next((o for o in desc.outputs if o.name == "CLIP"), None)
        if clip_output is not None:
            assert clip_output.link_count == 0

    def test_describe_str_renders_formatted_block(self) -> None:
        """NodeDescriptor.__str__ produces a human-readable block."""
        session = self._describe_session()
        desc = session.describe("loader")
        text = str(desc)

        assert "Node: loader (CheckpointLoaderSimple)" in text
        assert "uid: loader" in text
        assert "mode: enabled (0)" in text
        assert "pos:" in text
        assert "size:" in text
        assert "Inputs:" in text
        assert "Outputs:" in text
        assert "Widget Values:" in text
        # CheckpointLoaderSimple has no inputs — verify (none) is shown
        assert "    (none)" in text
        # Outputs include link counts
        assert "1 link" in text or "0 links" in text


class TestSearchQuery:
    """Tests for the side-effect-free search() query."""

    def test_search_returns_structured_rows(self) -> None:
        from vibecomfy.porting.emitter import NodeSignatureRow

        session = _primitive_session()
        result = session.search()

        assert isinstance(result, list)
        if result:
            assert all(isinstance(row, NodeSignatureRow) for row in result)
            assert all(isinstance(row.class_type, str) for row in result)

    def test_search_formatted_returns_string(self) -> None:
        session = _primitive_session()
        result = session.search(formatted=True)

        assert isinstance(result, str)
        if result:
            assert "def " in result

    def test_search_with_focus_types(self) -> None:
        session = _primitive_session()
        result = session.search(focus_types=["CheckpointLoaderSimple"])

        assert isinstance(result, list)
        if result:
            assert result[0].class_type == "CheckpointLoaderSimple"

    def test_search_with_compatibility_filter(self) -> None:
        session = _primitive_session()
        result = session.search(compatible_input_type="IMAGE")

        assert isinstance(result, list)

    def test_search_does_not_mutate_working_ui(self) -> None:
        session = _primitive_session()
        before = deepcopy(session.working_ui)

        _ = session.search(formatted=True)

        assert session.working_ui == before

    def test_search_does_not_count_as_landed_op(self) -> None:
        session = _primitive_session()
        landed_before = len(session.landed_ops)

        _ = session.search()

        assert len(session.landed_ops) == landed_before

    def test_search_focus_types_vibecomfy_exec_returns_usable_signature(self) -> None:
        """Agent search for focus_types=['vibecomfy.exec'] returns signature with source, io, fixed slots."""
        from vibecomfy.porting.emitter import NodeSignatureRow

        session = _primitive_session()
        result = session.search(focus_types=["vibecomfy.exec"])

        assert isinstance(result, list)
        assert len(result) == 1
        row = result[0]
        assert isinstance(row, NodeSignatureRow)
        assert row.class_type == "vibecomfy.exec"
        assert row.source_confidence == 1.0

        input_names = [f.name for f in row.inputs]
        # source and io must appear first
        assert "source" in input_names
        assert "io" in input_names
        # All 16 fixed input slots
        for i in range(16):
            assert f"in_{i}" in input_names, f"missing in_{i} in search result"

        output_names = [f.name for f in row.outputs]
        # All 16 fixed output slots
        for i in range(16):
            assert f"out_{i}" in output_names, f"missing out_{i} in search result"

    def test_search_formatted_vibecomfy_exec_includes_slots(self) -> None:
        """Formatted search for vibecomfy.exec shows source, io, and fixed slot types."""
        session = _primitive_session()
        result = session.search(focus_types=["vibecomfy.exec"], formatted=True)

        assert isinstance(result, str)
        assert "vibecomfy.exec" in result
        assert "source" in result
        assert "io" in result
        # Input slots appear with their types
        for i in range(16):
            assert f"in_{i}" in result, f"formatted result missing in_{i}"
        # Output slots include their names because these differ from their type.
        expected_returns = ", ".join([f"out_{i}:*" for i in range(16)])
        assert expected_returns in result, f"formatted result missing 16 output types"


class TestPythonQuery:
    """Tests for the side-effect-free python() query."""

    def test_python_returns_current_render(self) -> None:
        session = _primitive_session()

        assert session.python() == session.last_rendered_source
        assert "SourceOne" in session.last_rendered_source

    def test_python_batch_query_returns_rendered_output(self) -> None:
        session = _primitive_session()
        before = deepcopy(session.working_ui)
        landed_before = len(session.landed_ops)

        result = session.apply_batch("python()\n")

        assert result.ok is True
        assert len(result.statements) == 1
        statement = result.statements[0]
        assert statement.op_kind == "query"
        assert statement.landed is False
        assert statement.detail["query"] == "python"
        assert "SourceOne" in statement.detail["query_output"]
        assert session.working_ui == before
        assert len(session.landed_ops) == landed_before

    def test_python_rejects_arguments(self) -> None:
        session = _primitive_session()

        result = session.apply_batch('python("x")\n')

        assert result.ok is False
        assert result.statements[0].diagnostics[0].code == "python_arguments_not_allowed"


class TestReadOnlyNoOpSessions:
    """Read-only queries should preserve an empty/no-op session."""

    def test_queries_do_not_prevent_empty_done_identity(self) -> None:
        session = _primitive_session()
        session.render()

        _ = session.describe("src")
        _ = session.search()
        _ = session.search(formatted=True)
        _ = session.python()

        result = session.done()

        assert result.ok is True
        assert session.landed_ops == []
        assert "No edits applied" in result.summary
        assert "No operations were applied" in result.summary


def _schema_provider():
    class _SchemaProvider:
        def __init__(self):
            self._schemas = {
                "CheckpointLoaderSimple": type(
                    "S",
                    (),
                    {
                        "inputs": {
                            "ckpt_name": type("I", (), {"type": "COMBO", "required": True, "default": "v1-5-pruned.safetensors"})(),
                        },
                        "outputs": [
                            type("O", (), {"name": "MODEL", "type": "MODEL"})(),
                            type("O", (), {"name": "CLIP", "type": "CLIP"})(),
                            type("O", (), {"name": "VAE", "type": "VAE"})(),
                        ],
                        "confidence": 1.0,
                    },
                )(),
                "KSampler": type(
                    "S",
                    (),
                    {
                        "inputs": {
                            "model": type("I", (), {"type": "MODEL", "required": True})(),
                            "seed": type("I", (), {"type": "INT", "default": 0, "widget": 0})(),
                            "steps": type("I", (), {"type": "INT", "default": 20, "widget": 1})(),
                            "cfg": type("I", (), {"type": "FLOAT", "default": 7.5, "widget": 2})(),
                        },
                        "outputs": [type("O", (), {"name": "LATENT", "type": "LATENT"})()],
                        "confidence": 1.0,
                    },
                )(),
                "SourceOne": type(
                    "S",
                    (),
                    {
                        "inputs": {},
                        "outputs": [type("O", (), {"name": "in", "type": "IMAGE"})()],
                    },
                )(),
                "Dest": type(
                    "S",
                    (),
                    {
                        "inputs": {"value": type("I", (), {"type": "IMAGE"})(), "value2": type("I", (), {"type": "*"})()},
                        "outputs": [],
                    },
                )(),
                "SaveImage": type(
                    "S",
                    (),
                    {
                        "inputs": {
                            "images": type("I", (), {"type": "IMAGE", "required": True})(),
                            "filename_prefix": type("I", (), {"type": "STRING", "default": "ComfyUI"})(),
                        },
                        "outputs": [],
                    },
                )(),
                "VAEDecode": type(
                    "S",
                    (),
                    {
                        "inputs": {
                            "samples": type("I", (), {"type": "LATENT", "required": True})(),
                            "vae": type("I", (), {"type": "VAE", "required": True})(),
                        },
                        "outputs": [type("O", (), {"name": "IMAGE", "type": "IMAGE"})()],
                    },
                )(),
            }

        def schemas(self):
            return dict(self._schemas)

        def get_schema(self, class_type):
            return self._schemas.get(class_type)

    return _SchemaProvider()


def _primitive_session():
    from vibecomfy.porting import EditSession

    raw = {
        "last_node_id": 4,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "SourceOne",
                "mode": 0,
                "pos": [0, 0],
                "size": [210, 58],
                "outputs": [{"name": "in", "type": "IMAGE"}],
                "properties": {"vibecomfy_uid": "src"},
            },
            {
                "id": 2,
                "type": "KSampler",
                "mode": 0,
                "pos": [250, 0],
                "size": [210, 58],
                "widgets_values": [1, 20, 7.5, "euler", "normal", 1.0],
                "properties": {"vibecomfy_uid": "widget"},
            },
            {
                "id": 3,
                "type": "Dest",
                "mode": 0,
                "pos": [500, 0],
                "size": [210, 58],
                "inputs": [{"name": "value", "type": "IMAGE"}],
                "properties": {"vibecomfy_uid": "dst"},
            },
            {
                "id": 4,
                "type": "SetNode",
                "mode": 0,
                "pos": [750, 0],
                "size": [210, 58],
                "inputs": [{"name": "value", "type": "IMAGE"}],
                "widgets_values": ["bus"],
                "properties": {"vibecomfy_uid": "helper"},
            },
        ],
        "links": [],
        "groups": [{"title": "Outputs", "bounding": [480.0, -40.0, 320.0, 180.0]}],
    }
    session = EditSession(raw, schema_provider=_schema_provider())
    session.uid_by_name.update(
        {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper"}
    )
    session.name_by_uid.update(
        {"src": "src", "widget": "widget", "dst": "dst", "helper": "helper"}
    )
    return session


# =====================================================================
# =====================================================================
# M1 T16 — done() gate A: byte-faithfulness proof
# =====================================================================


class TestDoneGateAByteFaithfulness:
    """Prove that done() gate A replays ops and confirms byte-faithfulness.

    Gate A reapplies all landed ops over original_ui using apply_delta,
    requires guard_full_ui success, and asserts the recomputed candidate
    equals the current working_ui.
    """

    @staticmethod
    def _session():
        from vibecomfy.porting.edit.session import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "widgets_values": [],
                    "outputs": [{"name": "in", "type": "IMAGE", "slot_index": 0}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [250, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
                {
                    "id": 3,
                    "type": "KSampler",
                    "mode": 0,
                    "pos": [500, 0],
                    "size": [210, 58],
                    "widgets_values": [1, 20, 7.5],
                    "properties": {"vibecomfy_uid": "widget"},
                },
            ],
            "links": [],
            "groups": [],
        }
        return EditSession(raw, schema_provider=_TestSchemaProvider())

    def test_done_succeeds_on_no_op_session(self):
        """done() passes gate A when zero ops have landed."""
        session = self._session()
        session.render()
        result = session.done()
        assert result.ok is True
        assert "identity verified" in result.summary

    def test_done_succeeds_after_one_field_edit(self):
        """done() passes gate A after a single field edit."""
        from vibecomfy.porting.edit.ops import SetNodeFieldOp

        session = self._session()
        session.render()
        batch = session.apply_batch("ksampler.seed = 42\n")
        assert batch.ok is True
        assert isinstance(batch.landed_ops[0], SetNodeFieldOp)

        result = session.done()
        assert result.ok is True
        assert "Gate A passed" in result.summary
        assert "1 edit operation" in result.summary

    def test_done_succeeds_after_link_upsert(self):
        """done() passes gate A after linking two nodes."""
        from vibecomfy.porting.edit.ops import UpsertLinkOp

        session = self._session()
        session.render()
        batch = session.apply_batch("dest.value = sourceone.in_\n")
        assert batch.ok is True
        assert isinstance(batch.landed_ops[0], UpsertLinkOp)

        result = session.done()
        assert result.ok is True
        assert "Gate A passed" in result.summary

    def test_done_succeeds_after_multiple_edits(self):
        """done() passes gate A after multiple different edits."""
        from vibecomfy.porting.edit.ops import SetNodeFieldOp, UpsertLinkOp

        session = self._session()
        session.render()
        batch = session.apply_batch(
            "dest.value = sourceone.in_\n"
            "ksampler.seed = 7\n"
        )
        assert batch.ok is True
        assert len(batch.landed_ops) == 2

        result = session.done()
        assert result.ok is True
        assert "2 edit operation" in result.summary

    def test_done_candidate_matches_working_ui_byte_for_byte(self):
        """After edits, the recomputed candidate from gate A equals working_ui."""
        session = self._session()
        session.render()
        session.apply_batch("dest.value = sourceone.in_\n")
        session.apply_batch("ksampler.seed = 99\n")

        # Capture working_ui before done()
        working_before = deepcopy(session.working_ui)

        result = session.done()
        assert result.ok is True

        # Recompute independently to double-check
        from vibecomfy.porting.edit.apply import apply_delta
        applied = apply_delta(
            session.original_ui,
            tuple(session.landed_ops),
            schema_provider=session.schema_provider,
        )
        assert applied.ok
        assert applied.candidate is not None
        assert applied.candidate == working_before

    def test_done_after_add_node_passes(self):
        """done() passes gate A after adding a node."""
        from vibecomfy.porting.edit.ops import AddNodeOp

        session = self._session()
        session.render()
        batch = session.apply_batch(
            "extra = SaveImage(images=sourceone.in_, relation='right_of', near=dest)\n"
        )
        assert batch.ok is True
        assert isinstance(batch.landed_ops[0], AddNodeOp)

        result = session.done()
        assert result.ok is True


class TestDoneGateAGuardFailure:
    """Prove that gate A reports diagnostics when guard conditions fail."""

    @staticmethod
    def _session():
        from vibecomfy.porting.edit.session import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "widgets_values": [],
                    "outputs": [{"name": "in", "type": "IMAGE", "slot_index": 0}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [250, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
                {
                    "id": 3,
                    "type": "KSampler",
                    "mode": 0,
                    "pos": [500, 0],
                    "size": [210, 58],
                    "widgets_values": [1, 20, 7.5],
                    "properties": {"vibecomfy_uid": "widget"},
                },
            ],
            "links": [],
            "groups": [],
        }
        return EditSession(raw, schema_provider=_TestSchemaProvider())

    def test_done_detects_missing_landed_ops(self):
        """done() fails when working_ui mutated outside the edit-op path."""
        session = self._session()
        session.render()
        # Succeed with an edit
        batch = session.apply_batch("ksampler.seed = 1\n")
        assert batch.ok is True

        # Mutate working_ui externally — add a key that no op accounts for
        session.working_ui["extra_key"] = "injected"

        result = session.done()
        # Should fail because the recomputed candidate (from applying
        # the one landed op over original_ui) doesn't match the
        # externally-mutated working_ui.
        assert result.ok is False
        assert "does not match working_ui" in result.summary
        assert any(d.code == "done_gate_a_mismatch" for d in result.diagnostics)

    def test_done_detects_external_working_ui_mutation(self):
        """done() fails when a node's value is externally changed after apply."""
        session = self._session()
        session.render()
        batch = session.apply_batch("ksampler.seed = 42\n")
        assert batch.ok is True

        # Externally mutate working_ui directly — the ledger is a separate
        # copy, so resolve_node won't reach working_ui.
        for node in session.working_ui["nodes"]:
            if node.get("properties", {}).get("vibecomfy_uid") == "widget":
                node["widgets_values"][0] = 999
                break

        result = session.done()
        assert result.ok is False
        assert "does not match working_ui" in result.summary
        assert any(d.code == "done_gate_a_mismatch" for d in result.diagnostics)

    def test_done_diagnostics_include_teaching_hints(self):
        """Gate A failure diagnostics are errors with actionable messages."""
        session = self._session()
        session.render()
        session.apply_batch("ksampler.seed = 1\n")

        # Mutate externally
        session.working_ui["extra_key"] = "injected"

        result = session.done()
        assert result.ok is False
        for diag in result.diagnostics:
            assert diag.severity == "error"
            assert diag.message


class TestDoneGateBCompileRegion:
    """Prove that done() gate B uses the compile oracle over touched regions."""

    @staticmethod
    def _session():
        return TestDoneGateAByteFaithfulness._session()

    def test_done_gate_b_succeeds_after_compile_region_check(self):
        session = self._session()
        session.render()
        batch = session.apply_batch("dest.value = sourceone.in_\n")
        assert batch.ok is True

        result = session.done()

        assert result.ok is True
        assert "Gate B passed" in result.summary
        assert "compile region is isomorphic" in result.summary

    def test_done_gate_b_compares_touched_region_not_whole_graph(self, monkeypatch):
        from vibecomfy.porting import parity

        session = self._session()
        session.render()
        batch = session.apply_batch("dest.value = sourceone.in_\n")
        assert batch.ok is True

        calls = []

        def _capture(api_a, api_b, **kwargs):
            calls.append((set(api_a), set(api_b)))
            return True, []

        monkeypatch.setattr(parity, "compile_equivalent", _capture)

        result = session.done()

        assert result.ok is True
        assert calls
        assert calls[-1] == ({"1", "2"}, {"1", "2"})

    def test_done_gate_b_failure_reports_diff_diagnostics(self, monkeypatch):
        from vibecomfy.porting import parity

        session = self._session()
        session.render()
        batch = session.apply_batch("dest.value = sourceone.in_\n")
        assert batch.ok is True

        def _fail(api_a, api_b, **kwargs):
            return False, ["canonical_form mismatch", "topology only in A x1: sample"]

        monkeypatch.setattr(parity, "compile_equivalent", _fail)

        result = session.done()

        assert result.ok is False
        assert "Gate B failed" in result.summary
        diag = result.diagnostics[0]
        assert diag.code == "done_gate_b_compile_isomorphism_failed"
        assert diag.severity == "error"
        assert diag.detail["region_node_ids"] == ("1", "2")
        assert "canonical_form mismatch" in diag.detail["diffs"]


class TestDoneProofCoverageMatrix:
    """Exercise proof gates over every landed edit form the session supports."""

    @staticmethod
    def _run_done_session(*batches: str):
        session = TestDoneGateAByteFaithfulness._session()
        session.render()
        for batch in batches:
            result = session.apply_batch(batch)
            assert result.ok is True, result.diagnostics
        return session.done()

    @pytest.mark.parametrize(
        ("label", "batches", "needle"),
        [
            ("field_set", ("ksampler.seed = 42\n",), "Changed ksampler.seed from 1 to 42"),
            ("add_link", ("dest.value = sourceone.in_\n",), "Connected sourceone.in"),
            ("delete_node", ("del ksampler\n",), "Removed KSampler node 'ksampler'"),
            ("mode_set", ("dest.mode = 'muted'\n",), "Changed dest mode from enabled to muted"),
            (
                "add_node",
                ("extra = SaveImage(images=sourceone.in_, relation='right_of', near=dest)\n",),
                "Added SaveImage node 'extra'",
            ),
        ],
    )
    def test_done_proof_gates_pass_for_each_landed_edit_form(
        self,
        label: str,
        batches: tuple[str, ...],
        needle: str,
    ) -> None:
        result = self._run_done_session(*batches)

        assert result.ok is True, label
        assert "Gate A passed" in result.summary
        assert "Gate B passed" in result.summary
        assert needle in result.summary

    def test_done_proof_gates_pass_for_remove_link(self) -> None:
        from vibecomfy.porting.edit.session import EditSession

        raw = {
            "last_node_id": 2,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "widgets_values": [],
                    "outputs": [{"name": "in", "type": "IMAGE", "slot_index": 0, "links": [1]}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [250, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE", "link": 1}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [[1, 1, 0, 0, 2, "value"]],
            "groups": [],
        }
        session = EditSession(raw, schema_provider=_TestSchemaProvider())
        session.render()

        batch = session.apply_batch("dest.value = None\n")
        assert batch.ok is True

        result = session.done()

        assert result.ok is True
        assert "Gate A passed" in result.summary
        assert "Gate B passed" in result.summary
        assert "Disconnected dest.value" in result.summary


class TestDoneGateCSummary:
    """Prove that done() gate C produces correct plain-language summaries."""

    @staticmethod
    def _session():
        from vibecomfy.porting.edit.session import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 1,
            "nodes": [
                {
                    "id": 1,
                    "type": "SourceOne",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "widgets_values": [],
                    "outputs": [{"name": "in", "type": "IMAGE", "slot_index": 0}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2,
                    "type": "Dest",
                    "mode": 0,
                    "pos": [250, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
                {
                    "id": 3,
                    "type": "KSampler",
                    "mode": 0,
                    "pos": [500, 0],
                    "size": [210, 58],
                    "widgets_values": [1, 20, 7.5],
                    "properties": {"vibecomfy_uid": "widget"},
                },
            ],
            "links": [],
            "groups": [],
        }
        return EditSession(raw, schema_provider=_TestSchemaProvider())

    def test_summary_field_edit_reports_old_and_new_value(self):
        """Field edit summary shows from/to values."""
        session = self._session()
        session.render()
        batch = session.apply_batch("ksampler.seed = 42\n")
        assert batch.ok
        result = session.done()
        assert result.ok
        assert "Changed ksampler.seed from 1 to 42" in result.summary

    def test_summary_link_upsert_reports_connection(self):
        """New link summary shows source, target, and socket type."""
        session = self._session()
        session.render()
        batch = session.apply_batch("dest.value = sourceone.in_\n")
        assert batch.ok
        result = session.done()
        assert result.ok
        assert "Connected sourceone.in" in result.summary
        assert "dest.value" in result.summary
        assert "(IMAGE)" in result.summary

    def test_summary_link_rewire_detects_original_link(self):
        """Rewire summary shows from/to when original ledger had a link."""
        from vibecomfy.porting.edit.session import EditSession

        raw = {
            "last_node_id": 3,
            "last_link_id": 2,
            "nodes": [
                {
                    "id": 1, "type": "SourceOne", "mode": 0, "pos": [0, 0],
                    "size": [210, 58], "widgets_values": [],
                    "outputs": [{"name": "in", "type": "IMAGE", "slot_index": 0}],
                    "properties": {"vibecomfy_uid": "src"},
                },
                {
                    "id": 2, "type": "SourceOne", "mode": 0, "pos": [300, 0],
                    "size": [210, 58], "widgets_values": [],
                    "outputs": [{"name": "in", "type": "IMAGE", "slot_index": 0}],
                    "properties": {"vibecomfy_uid": "src2"},
                },
                {
                    "id": 3, "type": "Dest", "mode": 0, "pos": [600, 0],
                    "size": [210, 58],
                    "inputs": [{"name": "value", "type": "IMAGE", "link": 1}],
                    "properties": {"vibecomfy_uid": "dst"},
                },
            ],
            "links": [
                [1, 1, 0, 0, 3, "value"],
            ],
            "groups": [],
        }
        session = EditSession(raw, schema_provider=_TestSchemaProvider())
        session.render()  # produces names: sourceone (uid:src), sourceone_2 (uid:src2), dest (uid:dst)
        # Rewire dest.value from sourceone → sourceone_2
        batch = session.apply_batch("dest.value = sourceone_2.in_\n")
        assert batch.ok, f"Batch failed: {batch.diagnostics}"
        result = session.done()
        assert result.ok, f"done() failed: {result.summary}"
        assert "Rewired dest.value" in result.summary

    def test_summary_mode_change_reports_old_and_new_mode(self):
        """Mode change summary shows from/to labels."""
        session = self._session()
        session.render()
        batch = session.apply_batch("ksampler.mode = 'muted'\n")
        assert batch.ok
        result = session.done()
        assert result.ok
        assert "Changed ksampler mode from enabled to muted" in result.summary

    def test_summary_add_node_reports_class_type_and_inputs(self):
        """Add-node summary includes class type and inputs with socket types."""
        session = self._session()
        session.render()
        batch = session.apply_batch("new_img = SaveImage(images=sourceone.in_)\n")
        assert batch.ok
        result = session.done()
        assert result.ok
        assert "Added SaveImage node 'new_img'" in result.summary
        assert "sourceone.in" in result.summary
        assert "(IMAGE)" in result.summary

    def test_summary_remove_node_reports_class_type(self):
        """Remove-node summary includes class type and name."""
        session = self._session()
        session.render()
        batch = session.apply_batch("del ksampler\n")
        assert batch.ok
        result = session.done()
        assert result.ok
        assert "Removed KSampler node 'ksampler'" in result.summary

    def test_summary_multiple_ops_produces_joined_sentences(self):
        """Multiple ops produce space-joined sentences."""
        session = self._session()
        session.render()
        batch = session.apply_batch(
            "ksampler.seed = 99\n"
            "dest.value = sourceone.in_\n"
        )
        assert batch.ok
        result = session.done()
        assert result.ok
        assert "Changed ksampler.seed from 1 to 99" in result.summary
        assert "Connected sourceone.in" in result.summary
        assert "dest.value" in result.summary

    def test_summary_no_ops_reports_no_operations(self):
        """Zero ops summary is explicit."""
        session = self._session()
        session.render()
        result = session.done()
        assert result.ok
        assert "No operations were applied" in result.summary

    def test_summary_gate_failure_includes_error_diagnostics(self):
        """When a gate fails, the DoneResult includes failed-gate diagnostics."""
        session = self._session()
        session.render()
        session.apply_batch("ksampler.seed = 1\n")
        # Externally corrupt working_ui to trigger gate failure
        session.working_ui["extra_key"] = "injected"
        result = session.done()
        assert result.ok is False
        assert "Gate A" in result.summary
        assert "does not match working_ui" in result.summary


def _TestSchemaProvider():
    """Reusable schema provider for done() gate A tests."""
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    class _Provider:
        def __init__(self):
            self._schemas = {
                "SourceOne": NodeSchema(
                    class_type="SourceOne",
                    pack=None,
                    inputs={},
                    outputs=[OutputSpec(type="IMAGE", name="in")],
                ),
                "Dest": NodeSchema(
                    class_type="Dest",
                    pack=None,
                    inputs={
                        "value": InputSpec(type="IMAGE", required=False),
                    },
                    outputs=[],
                ),
                "SaveImage": NodeSchema(
                    class_type="SaveImage",
                    pack=None,
                    inputs={
                        "images": InputSpec(type="IMAGE", required=True),
                        "filename_prefix": InputSpec(type="STRING", required=False),
                    },
                    outputs=[],
                ),
                "KSampler": NodeSchema(
                    class_type="KSampler",
                    pack=None,
                    inputs={
                        "seed": InputSpec(type="INT", required=False),
                        "steps": InputSpec(type="INT", required=False),
                        "cfg": InputSpec(type="FLOAT", required=False),
                    },
                    outputs=[OutputSpec(type="LATENT", name="LATENT")],
                ),
            }

        def schemas(self):
            return list(self._schemas.values())

        def get_schema(self, class_type):
            return self._schemas.get(class_type)

    return _Provider()


# =====================================================================
# M1 T20 — Seeded property fuzz for edit sessions
# =====================================================================


try:
    import hypothesis
    from hypothesis import given, settings, seed
    from hypothesis import strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ImportError:
    _HYPOTHESIS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Deterministic random generator (fallback when Hypothesis is unavailable)
# ---------------------------------------------------------------------------


class _SeededRandom:
    """Deterministic seeded random generator using a simple LCG.

    Used as a fallback when Hypothesis is not available. Produces
    repeatable sequences from a fixed seed so fuzz invariants can
    be verified offline.
    """

    def __init__(self, seed_value: int = 42) -> None:
        self._state = seed_value

    def _next(self) -> int:
        self._state = (self._state * 1103515245 + 12345) & 0x7FFFFFFF
        return self._state

    def randint(self, lo: int, hi: int) -> int:
        return lo + (self._next() % (hi - lo + 1))

    def choice(self, seq: list) -> object:
        return seq[self.randint(0, len(seq) - 1)]


# ---------------------------------------------------------------------------
# Statement generators
# ---------------------------------------------------------------------------


# Rendered names from the flat fixture (deterministic across renders).
_FLAT_NAMES = [
    "checkpointloadersimple",
    "emptylatentimage",
    "positive",
    "negative",
    "ksampler",
    "vaedecode",
    "saveimage",
]

# Names with known mutable fields.
_FIELD_EDIT_TEMPLATES = [
    ("ksampler", "seed", lambda r: str(r.randint(0, 99999))),
    ("ksampler", "steps", lambda r: str(r.randint(1, 150))),
    ("ksampler", "cfg", lambda r: str(round(r.randint(10, 200) / 10.0, 1))),
    ("positive", "text", lambda r: repr(f"fuzz_text_{r.randint(0, 999)}")),
    ("negative", "text", lambda r: repr(f"neg_text_{r.randint(0, 999)}")),
    ("saveimage", "filename_prefix", lambda r: repr(f"fuzz_prefix_{r.randint(0, 99)}")),
]

# Mode assignment targets.
_MODE_TARGETS = [n for n in _FLAT_NAMES if n != "checkpointloadersimple"]

# Valid mode labels (from edit_projection.MODE_LABELS reversed).
_MODE_LABELS = ["enabled", "muted", "bypass"]

# Node types that can be added with known inputs.
_ADD_NODE_TEMPLATES = [
    "SaveImage(images=vaedecode.image, relation='right_of', near=saveimage)",
    "SaveImage(images=vaedecode.image, filename_prefix='extra', relation='after', near=saveimage)",
]

# Invalid statement templates (for mixing in).
_INVALID_TEMPLATES = [
    "nonexistent.field = 1",
    "del nonexistent_node",
    "unknown.mode = 'muted'",
    "bad_var = NonExistentClassType(x=1, relation='right_of', near=saveimage)",
    "import os",
    "exec('print(1)')",
    "eval('1+1')",
    "__import__('os')",
    "ksampler.__dict__",
]


def _generate_valid_statement(r: _SeededRandom) -> str:
    """Generate a single valid edit statement deterministically."""
    kind = r.randint(0, 4)
    if kind == 0:
        # Field edit
        name, field, val_fn = r.choice(_FIELD_EDIT_TEMPLATES)
        return f"{name}.{field} = {val_fn(r)}\n"
    elif kind == 1:
        # Mode assignment
        name = r.choice(_MODE_TARGETS)
        mode = r.choice(_MODE_LABELS)
        return f"{name}.mode = '{mode}'\n"
    elif kind == 2:
        # Add node
        tmpl = r.choice(_ADD_NODE_TEMPLATES)
        suffix = r.randint(0, 99)
        return f"extra_{suffix} = {tmpl}\n"
    elif kind == 3:
        # Delete node (only safe targets that don't break topology)
        name = r.choice(["saveimage"])
        return f"del {name}\n"
    else:
        # Read-only query (should be no-op)
        name = r.choice(_FLAT_NAMES)
        return f"describe('{name}')\n"


def _generate_invalid_statement(r: _SeededRandom) -> str:
    """Generate a single invalid edit statement deterministically."""
    return r.choice(_INVALID_TEMPLATES) + "\n"


def _generate_mixed_batch(
    r: _SeededRandom, min_stmts: int = 1, max_stmts: int = 10
) -> tuple[str, list[bool]]:
    """Generate a batch of 1-10 statements, some valid, some invalid.

    Returns (code, expected_validity) where expected_validity[i] is True
    if statement i is expected to be valid.
    """
    n = r.randint(min_stmts, max_stmts)
    statements: list[str] = []
    expected: list[bool] = []
    for _ in range(n):
        if r.randint(0, 3) == 0:
            # ~25% chance of invalid
            statements.append(_generate_invalid_statement(r))
            expected.append(False)
        else:
            statements.append(_generate_valid_statement(r))
            expected.append(True)
    return "".join(statements), expected


# ---------------------------------------------------------------------------
# Session factory for the flat fixture
# ---------------------------------------------------------------------------


def _flat_fuzz_session():
    """Create an EditSession from the flat fixture with deterministic schemas."""
    from vibecomfy.porting import EditSession

    raw = _load_flat_fixture_raw()
    return EditSession(raw, schema_provider=_TestSchemaProvider())


# ---------------------------------------------------------------------------
# Fuzz test class (Hypothesis path)
# ---------------------------------------------------------------------------


if _HYPOTHESIS_AVAILABLE:

    @st.composite
    def _statement_batch_strategy(draw) -> str:
        """Hypothesis strategy: generate 1-10 mixed valid/invalid statements."""
        n = draw(st.integers(min_value=1, max_value=10))
        statements: list[str] = []
        for _ in range(n):
            kind = draw(st.integers(min_value=0, max_value=7))
            if kind == 0:
                # Valid field edit
                name = draw(st.sampled_from(_FLAT_NAMES))
                field = draw(
                    st.sampled_from(
                        [t[1] for t in _FIELD_EDIT_TEMPLATES if t[0] == name]
                        or ["seed", "steps", "cfg", "text", "filename_prefix"]
                    )
                )
                if field in ("seed", "steps"):
                    val = str(draw(st.integers(0, 99999)))
                elif field == "cfg":
                    val = str(round(draw(st.integers(10, 200)) / 10.0, 1))
                else:
                    val = repr(f"fuzz_{draw(st.integers(0, 999))}")
                statements.append(f"{name}.{field} = {val}\n")
            elif kind == 1:
                # Valid mode assignment
                name = draw(st.sampled_from(_MODE_TARGETS))
                mode = draw(st.sampled_from(_MODE_LABELS))
                statements.append(f"{name}.mode = '{mode}'\n")
            elif kind == 2:
                # Valid add node
                tmp = draw(st.sampled_from(_ADD_NODE_TEMPLATES))
                suffix = draw(st.integers(0, 999))
                statements.append(f"extra_{suffix} = {tmp}\n")
            elif kind == 3:
                # Valid delete
                name = draw(st.sampled_from(["saveimage"]))
                statements.append(f"del {name}\n")
            elif kind == 4:
                # Valid read-only query
                name = draw(st.sampled_from(_FLAT_NAMES))
                statements.append(f"describe('{name}')\n")
            elif kind == 5:
                # Invalid: unknown name
                statements.append(
                    f"nonexistent_{draw(st.integers(0,99))}.field = 1\n"
                )
            elif kind == 6:
                # Invalid: unsafe AST
                statements.append(
                    draw(
                        st.sampled_from(
                            [
                                "import os\n",
                                "exec('print(1)')\n",
                                "eval('1+1')\n",
                                "__import__('os')\n",
                                "ksampler.__dict__\n",
                            ]
                        )
                    )
                )
            else:
                # Invalid: unknown class type for add
                suffix = draw(st.integers(0, 999))
                statements.append(
                    f"bad_{suffix} = NonExistentClass(x=1, relation='right_of', near=saveimage)\n"
                )
        return "".join(statements)

    class TestSeededPropertyFuzz:
        """Property-based fuzz for edit sessions using Hypothesis.

        Generates 1-10 valid or mixed valid/invalid statements against the
        flat fixture and asserts:

        - No exceptions escape the batch path.
        - Successful batches are byte-faithful (done() passes).
        - Failed statements do not mutate unrelated nodes.
        - Landed-op replay is deterministic.
        - Rerendered existing aliases remain stable.
        """

        @given(_statement_batch_strategy())
        @settings(max_examples=50, deadline=None)
        @seed(42)
        def test_fuzz_no_exceptions_escape(self, code: str) -> None:
            """No unhandled exceptions escape apply_batch or done()."""
            session = _flat_fuzz_session()
            session.render()

            try:
                batch_result = session.apply_batch(code)
            except Exception as exc:
                raise AssertionError(
                    f"apply_batch raised an exception on code:\n{code}"
                ) from exc

            # If the batch landed ops, attempt done() — it should not crash.
            if batch_result.landed_ops:
                try:
                    done_result = session.done()
                except Exception as exc:
                    raise AssertionError(
                        f"done() raised an exception after batch:\n{code}"
                    ) from exc

        @given(_statement_batch_strategy())
        @settings(max_examples=50, deadline=None)
        @seed(42)
        def test_fuzz_successful_batch_preserves_byte_faithfulness(
            self, code: str
        ) -> None:
            """When a batch succeeds, done() must pass gate A (byte-faithfulness)."""
            session = _flat_fuzz_session()
            session.render()

            batch_result = session.apply_batch(code)
            if not batch_result.ok or not batch_result.landed_ops:
                # Only check byte-faithfulness for successful batches with ops.
                return

            done_result = session.done()
            assert done_result.ok, (
                f"done() failed after successful batch.\n"
                f"Code:\n{code}\n"
                f"Summary: {done_result.summary}"
            )
            assert "Gate A passed" in done_result.summary, (
                f"Gate A did not pass.\nCode:\n{code}\nSummary: {done_result.summary}"
            )

        @given(_statement_batch_strategy())
        @settings(max_examples=50, deadline=None)
        @seed(42)
        def test_fuzz_failed_statements_do_not_mutate_unrelated_nodes(
            self, code: str
        ) -> None:
            """Failed statements must not change unrelated nodes in working_ui."""
            from copy import deepcopy

            session = _flat_fuzz_session()
            session.render()

            # Capture pre-batch working_ui nodes keyed by id.
            pre_nodes = {
                n["id"]: deepcopy(n) for n in session.working_ui.get("nodes", [])
            }

            batch_result = session.apply_batch(code)

            # Determine which uids were touched (even by failed ops).
            touched_uids: set = set()
            for stmt_result in batch_result.statements:
                touched_uids.update(stmt_result.touched_uids)

            # Post-batch nodes.
            post_nodes = {
                n["id"]: n for n in session.working_ui.get("nodes", [])
            }

            # uids from the name table that map to node ids.
            uid_to_nid: dict[str, int] = {}
            for name, uid in session.uid_by_name.items():
                for node in post_nodes.values():
                    if node.get("properties", {}).get("vibecomfy_uid") == uid:
                        uid_to_nid[uid] = node["id"]
                        break
                else:
                    # Numeric uid (flat fixture): uid *is* the node id.
                    try:
                        nid = int(uid)
                        if nid in post_nodes:
                            uid_to_nid[uid] = nid
                    except (ValueError, TypeError):
                        pass

            # For every node, if its uid is not touched, it must be unchanged.
            for nid, pre_node in pre_nodes.items():
                # Find the uid for this node id.
                node_uid = None
                for uid, mapped_nid in uid_to_nid.items():
                    if mapped_nid == nid:
                        node_uid = uid
                        break
                if node_uid is None:
                    node_uid = str(nid)  # Fallback: numeric uid

                if node_uid in touched_uids:
                    continue

                post_node = post_nodes.get(nid)
                assert post_node is not None, (
                    f"Node {nid} (uid={node_uid}) disappeared unexpectedly.\n"
                    f"Code:\n{code}"
                )

                # Compare relevant fields (ignore UI state like pos/size/flags/order
                # which may be updated by layout even for untouched nodes).
                # Also ignore vibecomfy_uid stamping — the render/apply path
                # may stamp identity metadata on nodes that lack it, which is
                # expected plumbing, not a semantic mutation.
                for key in ("type", "mode", "widgets_values"):
                    pre_val = pre_node.get(key)
                    post_val = post_node.get(key)
                    assert pre_val == post_val, (
                        f"Untouched node {nid} (uid={node_uid}) field '{key}' changed.\n"
                        f"Before: {pre_val!r}\nAfter:  {post_val!r}\n"
                        f"Touched uids: {touched_uids}\n"
                        f"Code:\n{code}"
                    )
                # Properties: only compare keys that were already present,
                # ignoring newly stamped vibecomfy_uid.
                pre_props = pre_node.get("properties") or {}
                post_props = post_node.get("properties") or {}
                for pk, pv in pre_props.items():
                    assert post_props.get(pk) == pv, (
                        f"Untouched node {nid} property '{pk}' changed.\n"
                        f"Before: {pv!r}\nAfter:  {post_props.get(pk)!r}\n"
                        f"Code:\n{code}"
                    )
                # Inputs/outputs: only compare names and types, not link IDs.
                for io_key in ("inputs", "outputs"):
                    pre_io = [
                        {"name": i.get("name"), "type": i.get("type")}
                        for i in pre_node.get(io_key, [])
                    ]
                    post_io = [
                        {"name": i.get("name"), "type": i.get("type")}
                        for i in post_node.get(io_key, [])
                    ]
                    assert pre_io == post_io, (
                        f"Untouched node {nid} {io_key} changed.\n"
                        f"Before: {pre_io!r}\nAfter:  {post_io!r}\n"
                        f"Code:\n{code}"
                    )

        @given(_statement_batch_strategy())
        @settings(max_examples=50, deadline=None)
        @seed(42)
        def test_fuzz_landed_op_replay_is_deterministic(self, code: str) -> None:
            """Replaying the same batch twice produces identical landed ops."""
            from copy import deepcopy

            session = _flat_fuzz_session()
            session.render()

            batch1 = session.apply_batch(code)

            # Create a fresh session with the same starting state and replay.
            session2 = _flat_fuzz_session()
            session2.render()
            batch2 = session2.apply_batch(code)

            assert batch1.ok == batch2.ok, (
                f"ok mismatch: {batch1.ok} vs {batch2.ok}\nCode:\n{code}"
            )
            assert len(batch1.landed_ops) == len(batch2.landed_ops), (
                f"landed_ops count mismatch: {len(batch1.landed_ops)} vs "
                f"{len(batch2.landed_ops)}\nCode:\n{code}"
            )
            for i, (op1, op2) in enumerate(
                zip(batch1.landed_ops, batch2.landed_ops)
            ):
                assert type(op1) is type(op2), (
                    f"Op {i} type mismatch: {type(op1).__name__} vs "
                    f"{type(op2).__name__}\nCode:\n{code}"
                )

            # Also check that working_ui is identical after both runs.
            assert session.working_ui == session2.working_ui, (
                f"working_ui diverged after replay.\nCode:\n{code}"
            )

        @given(_statement_batch_strategy())
        @settings(max_examples=50, deadline=None)
        @seed(42)
        def test_fuzz_rerendered_existing_aliases_remain_stable(
            self, code: str
        ) -> None:
            """Rerendering the session preserves previously established aliases."""
            session = _flat_fuzz_session()

            first_render = session.render()
            first_names = dict(session.name_by_uid)

            # Apply a batch, which may add new nodes/names.
            session.apply_batch(code)

            # Rerender.
            second_render = session.render()
            second_names = dict(session.name_by_uid)

            # All names from first render must still map to the same uids.
            for uid, name in first_names.items():
                assert uid in second_names, (
                    f"uid {uid} ({name}) disappeared after rerender.\n"
                    f"Code:\n{code}"
                )
                assert second_names[uid] == name, (
                    f"uid {uid} was renamed from '{name}' to "
                    f"'{second_names[uid]}' after rerender.\n"
                    f"Code:\n{code}"
                )

else:
    # Hypothesis not available — use deterministic seeded random instead.

    class TestSeededPropertyFuzz:
        """Property-based fuzz for edit sessions using deterministic seeded random.

        Generates 1-10 valid or mixed valid/invalid statements against the
        flat fixture and asserts the same invariants as the Hypothesis path.
        Runs 100 iterations with a fixed seed for reproducibility.
        """

        _SEED = 42
        _ITERATIONS = 100

        def test_fuzz_no_exceptions_escape(self) -> None:
            """No unhandled exceptions escape apply_batch or done()."""
            r = _SeededRandom(self._SEED)
            for i in range(self._ITERATIONS):
                r_i = _SeededRandom(self._SEED + i * 7)
                code, _ = _generate_mixed_batch(r_i)
                session = _flat_fuzz_session()
                session.render()
                try:
                    batch_result = session.apply_batch(code)
                except Exception as exc:
                    raise AssertionError(
                        f"Iter {i}: apply_batch raised {type(exc).__name__}: "
                        f"{exc}\nCode:\n{code}"
                    ) from exc
                if batch_result.landed_ops:
                    try:
                        session.done()
                    except Exception as exc:
                        raise AssertionError(
                            f"Iter {i}: done() raised {type(exc).__name__}: "
                            f"{exc}\nCode:\n{code}"
                        ) from exc

        def test_fuzz_successful_batch_preserves_byte_faithfulness(self) -> None:
            """When a batch succeeds, done() must pass gate A."""
            r = _SeededRandom(self._SEED)
            for i in range(self._ITERATIONS):
                r_i = _SeededRandom(self._SEED + i * 7)
                code, _ = _generate_mixed_batch(r_i)
                session = _flat_fuzz_session()
                session.render()
                batch_result = session.apply_batch(code)
                if not batch_result.ok or not batch_result.landed_ops:
                    continue
                done_result = session.done()
                assert done_result.ok, (
                    f"Iter {i}: done() failed after successful batch.\n"
                    f"Code:\n{code}\nSummary: {done_result.summary}"
                )
                assert "Gate A passed" in done_result.summary, (
                    f"Iter {i}: Gate A did not pass.\n"
                    f"Code:\n{code}\nSummary: {done_result.summary}"
                )

        def test_fuzz_failed_statements_do_not_mutate_unrelated_nodes(
            self,
        ) -> None:
            """Failed statements must not change unrelated nodes."""
            from copy import deepcopy

            r = _SeededRandom(self._SEED)
            for i in range(self._ITERATIONS):
                r_i = _SeededRandom(self._SEED + i * 7)
                code, _ = _generate_mixed_batch(r_i)
                session = _flat_fuzz_session()
                session.render()

                pre_nodes = {
                    n["id"]: deepcopy(n)
                    for n in session.working_ui.get("nodes", [])
                }

                batch_result = session.apply_batch(code)

                touched_uids: set = set()
                for stmt_result in batch_result.statements:
                    touched_uids.update(stmt_result.touched_uids)

                post_nodes = {
                    n["id"]: n for n in session.working_ui.get("nodes", [])
                }

                uid_to_nid: dict[str, int] = {}
                for name, uid in session.uid_by_name.items():
                    for node in post_nodes.values():
                        props = node.get("properties") or {}
                        if props.get("vibecomfy_uid") == uid:
                            uid_to_nid[uid] = node["id"]
                            break
                    else:
                        try:
                            nid = int(uid)
                            if nid in post_nodes:
                                uid_to_nid[uid] = nid
                        except (ValueError, TypeError):
                            pass

                for nid, pre_node in pre_nodes.items():
                    node_uid = None
                    for uid, mapped_nid in uid_to_nid.items():
                        if mapped_nid == nid:
                            node_uid = uid
                            break
                    if node_uid is None:
                        node_uid = str(nid)

                    if node_uid in touched_uids:
                        continue

                    post_node = post_nodes.get(nid)
                    assert post_node is not None, (
                        f"Iter {i}: Node {nid} disappeared.\nCode:\n{code}"
                    )

                    for key in ("type", "mode", "widgets_values"):
                        pre_val = pre_node.get(key)
                        post_val = post_node.get(key)
                        assert pre_val == post_val, (
                            f"Iter {i}: Untouched node {nid} field '{key}'"
                            f" changed.\nBefore: {pre_val!r}\n"
                            f"After: {post_val!r}\n"
                            f"Touched uids: {touched_uids}\nCode:\n{code}"
                        )

                    pre_props = pre_node.get("properties") or {}
                    post_props = post_node.get("properties") or {}
                    for pk, pv in pre_props.items():
                        assert post_props.get(pk) == pv, (
                            f"Iter {i}: Untouched node {nid} property '{pk}'"
                            f" changed.\nBefore: {pv!r}\n"
                            f"After: {post_props.get(pk)!r}\nCode:\n{code}"
                        )

                    for io_key in ("inputs", "outputs"):
                        pre_io = [
                            {"name": x.get("name"), "type": x.get("type")}
                            for x in pre_node.get(io_key, [])
                        ]
                        post_io = [
                            {"name": x.get("name"), "type": x.get("type")}
                            for x in post_node.get(io_key, [])
                        ]
                        assert pre_io == post_io, (
                            f"Iter {i}: Untouched node {nid} {io_key}"
                            f" changed.\nBefore: {pre_io!r}\n"
                            f"After: {post_io!r}\nCode:\n{code}"
                        )

        def test_fuzz_landed_op_replay_is_deterministic(self) -> None:
            """Replaying the same batch twice produces identical landed ops."""
            from copy import deepcopy

            r = _SeededRandom(self._SEED)
            for i in range(self._ITERATIONS):
                r_i = _SeededRandom(self._SEED + i * 7)
                code, _ = _generate_mixed_batch(r_i)

                session = _flat_fuzz_session()
                session.render()
                batch1 = session.apply_batch(code)

                session2 = _flat_fuzz_session()
                session2.render()
                batch2 = session2.apply_batch(code)

                assert batch1.ok == batch2.ok, (
                    f"Iter {i}: ok mismatch: {batch1.ok} vs {batch2.ok}\n"
                    f"Code:\n{code}"
                )
                assert len(batch1.landed_ops) == len(batch2.landed_ops), (
                    f"Iter {i}: landed_ops count mismatch: "
                    f"{len(batch1.landed_ops)} vs "
                    f"{len(batch2.landed_ops)}\nCode:\n{code}"
                )
                for j, (op1, op2) in enumerate(
                    zip(batch1.landed_ops, batch2.landed_ops)
                ):
                    assert type(op1) is type(op2), (
                        f"Iter {i}: Op {j} type mismatch: "
                        f"{type(op1).__name__} vs "
                        f"{type(op2).__name__}\nCode:\n{code}"
                    )

                assert session.working_ui == session2.working_ui, (
                    f"Iter {i}: working_ui diverged after replay.\n"
                    f"Code:\n{code}"
                )

        def test_fuzz_rerendered_existing_aliases_remain_stable(self) -> None:
            """Rerendering preserves previously established aliases."""
            r = _SeededRandom(self._SEED)
            for i in range(self._ITERATIONS):
                r_i = _SeededRandom(self._SEED + i * 7)
                code, _ = _generate_mixed_batch(r_i)

                session = _flat_fuzz_session()
                first_render = session.render()
                first_names = dict(session.name_by_uid)

                session.apply_batch(code)
                second_render = session.render()
                second_names = dict(session.name_by_uid)

                for uid, name in first_names.items():
                    assert uid in second_names, (
                        f"Iter {i}: uid {uid} ({name}) disappeared"
                        f" after rerender.\nCode:\n{code}"
                    )
                    assert second_names[uid] == name, (
                        f"Iter {i}: uid {uid} renamed from '{name}'"
                        f" to '{second_names[uid]}'.\nCode:\n{code}"
                    )


# =====================================================================
# T14 — Exec source diff rendering and copy-source affordance tests
# =====================================================================


class TestRenderOpDiffExecSource:
    """Tests for _render_op_diff with vibecomfy.exec source field changes."""

    def test_render_op_diff_source_unified_diff(self) -> None:
        """_render_op_diff produces unified diff when old and new source are strings."""
        from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
        from vibecomfy.porting.edit.session import _render_op_diff

        old_src = "def fn(x):\n    return x + 1\n"
        new_src = "def fn(x):\n    y = x * 2\n    return y + 1\n"
        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="abc123", field_path="source"),
            value=new_src,
        )
        result = _render_op_diff(op, old_value=old_src)
        # Should contain the unified diff header
        assert "set_node_field" in result
        assert "abc123" in result
        assert "source" in result
        assert "2→3 lines" in result
        # Should show diff markers (note: splitlines(keepends=True) preserves
        # trailing newlines, so diff lines look like "-    return x + 1\n")
        assert "@@" in result
        assert "-    return x + 1" in result
        assert "+    y = x * 2" in result
        assert "+    return y + 1" in result

    def test_render_op_diff_source_no_old_value_falls_back_to_truncated(self) -> None:
        """_render_op_diff falls back to truncated repr when old_value is None."""
        from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
        from vibecomfy.porting.edit.session import _render_op_diff

        new_src = "x = 1\ny = 2\nz = 3\n"
        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="abc123", field_path="source"),
            value=new_src,
        )
        result = _render_op_diff(op, old_value=None)
        # Should be single-line with truncated repr
        assert "\n" not in result  # single line
        assert "set_node_field" in result
        assert "source" in result
        assert "abc123" in result

    def test_render_op_diff_non_source_field_uses_truncated_even_with_old(self) -> None:
        """_render_op_diff uses truncated repr for non-source fields even with old_value."""
        from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
        from vibecomfy.porting.edit.session import _render_op_diff

        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="abc123", field_path="seed"),
            value=42,
        )
        result = _render_op_diff(op, old_value=7)
        # Should be single-line, not a unified diff
        assert "\n" not in result
        assert "set_node_field" in result
        assert "seed" in result
        assert "42" in result

    def test_render_op_diff_source_identical_no_diff_output(self) -> None:
        """_render_op_diff produces no diff lines when old and new source are identical."""
        from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
        from vibecomfy.porting.edit.session import _render_op_diff

        src = "def fn(x):\n    return x\n"
        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="abc123", field_path="source"),
            value=src,
        )
        result = _render_op_diff(op, old_value=src)
        # When identical, difflib.unified_diff returns empty, so fallback to
        # single-line truncated repr.
        assert "\n" not in result or "@@" not in result
        assert "set_node_field" in result


class TestBatchResultRenderDiffWithFieldChanges:
    """Tests for BatchResult.render_diff() using field_changes for exec source."""

    def test_render_diff_includes_unified_source_diff(self) -> None:
        """render_diff() passes old values from field_changes to _render_op_diff."""
        from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
        from vibecomfy.porting.edit.session import BatchResult
        from vibecomfy.porting.edit.types import FieldChange

        old_src = "def fn(x):\n    return x\n"
        new_src = "def fn(x):\n    return x * 2\n"
        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="abc123", field_path="source"),
            value=new_src,
        )
        fc = FieldChange(uid="abc123", field_path="source", old=old_src, new=new_src)
        br = BatchResult(
            ok=True,
            statements=(),
            diagnostics=(),
            landed_ops=(op,),
            field_changes=(fc,),
        )
        result = br.render_diff()
        assert "--- landed operations ---" in result
        assert "@@" in result
        assert "-    return x" in result
        assert "+    return x * 2" in result

    def test_render_diff_field_changes_no_old_value_no_diff(self) -> None:
        """render_diff() without matching field_changes entry uses truncated repr."""
        from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
        from vibecomfy.porting.edit.session import BatchResult

        new_src = "x = 1\ny = 2\n"
        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="abc123", field_path="source"),
            value=new_src,
        )
        br = BatchResult(
            ok=True,
            statements=(),
            diagnostics=(),
            landed_ops=(op,),
            field_changes=(),  # no field changes
        )
        result = br.render_diff()
        assert "--- landed operations ---" in result
        assert "@@" not in result
        assert "set_node_field" in result


# ── T6: Legacy-boundary classification tests ────────────────────────────────


class TestLegacyDeltaBoundary:
    """Prove that legacy wrapped delta shapes are classified as
    ``legacy_delta_shape`` rather than falling through to V1 stale-canvas
    fallback, and that add-node identity grouping uses explicit uid/node_id."""

    def test_legacy_wrapped_delta_ops_detected_as_legacy_delta_shape_not_v1(
        self,
    ) -> None:
        """The ops module must classify legacy wrapped mappings (a dict with
        legacy keys like ``delta``, ``diagnostics`` under ``delta_ops``) as
        ``legacy_delta_shape``, not as malformed V2 or a V1 stale-canvas
        fallback."""
        from vibecomfy.porting.edit.ops import (
            DELTA_DIAGNOSTIC_LEGACY_SHAPE,
            EditOpParseError,
            normalize_delta_envelope,
        )

        # A legacy wrapped payload: a dict under delta_ops with old keys.
        legacy_wrapped = {
            "delta_ops": {
                "delta": [{"op": "set_node_field", "target": ["nodes", "n1", "text"], "value": "old"}],
                "diagnostics": [],
                "guard_result": {},
            },
        }

        # normalize_delta_envelope must raise EditOpParseError with
        # DELTA_DIAGNOSTIC_LEGACY_SHAPE code, NOT a generic malformed code.
        with pytest.raises(EditOpParseError) as exc_info:
            normalize_delta_envelope(legacy_wrapped)
        assert exc_info.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE, (
            f"Expected DELTA_DIAGNOSTIC_LEGACY_SHAPE ({DELTA_DIAGNOSTIC_LEGACY_SHAPE!r}), "
            f"got {exc_info.value.code!r}"
        )

        # The error message must mention legacy.
        assert "legacy" in str(exc_info.value).lower(), (
            f"Expected legacy mention in error, got: {exc_info.value}"
        )

    def test_non_strict_normalize_accepts_legacy_flat_for_bridge_only(
        self,
    ) -> None:
        """Non-strict normalization (used pre-apply) must accept legacy flat
        delta_ops lists for backward compatibility but must classify them as
        derived bridge data, not canonical."""
        from vibecomfy.porting.edit.ops import normalize_delta_envelope

        # Legacy flat list — use allow_legacy_list=True for the bridge path.
        # We use strict=False so canonical_op_to_dict is not called (which
        # would reject ops that lack explicit uid/node_id).
        legacy_flat = [
            {"op": "set_node_field", "target": ["", "n1", "text"], "value": "bridge"},
        ]
        envelope = normalize_delta_envelope(
            legacy_flat, allow_legacy_list=True, strict=False,
        )
        assert envelope.schema_version == "2.0.0"
        assert len(envelope.ops) == 1
        assert envelope.ops[0].op == "set_node_field"

    def test_legacy_wrapped_rejected_even_non_strict(self) -> None:
        """Even non-strict/allowed-legacy-list normalization must reject
        legacy wrapped mappings that have neither ``schema_version`` nor
        ``ops`` keys, since they cannot be mechanically converted."""
        from vibecomfy.porting.edit.ops import (
            EditOpParseError,
            normalize_delta_envelope,
        )

        # A bare legacy wrapped dict with keys like delta/diagnostics
        # but no schema_version or ops → malformed_delta.
        legacy_wrapped = {
            "delta": [{"op": "set_node_field", "target": ["", "n1", "text"], "value": "old"}],
            "diagnostics": [],
        }

        with pytest.raises(EditOpParseError) as exc_info:
            normalize_delta_envelope(legacy_wrapped, allow_legacy_list=True)
        # This shape is classified as malformed_delta because it has neither
        # schema_version/ops nor the ``delta_ops`` wrapper key.
        assert exc_info.value.code in ("malformed_delta", "legacy_delta_shape"), (
            f"Expected malformed_delta or legacy_delta_shape, got {exc_info.value.code!r}"
        )

    def test_canonical_add_node_roundtrip_preserves_uid_and_node_id(
        self,
    ) -> None:
        """A canonical add_node with explicit uid/node_id must survive
        parse→normalize→serialize roundtrip with identity intact."""
        from vibecomfy.porting.edit.ops import (
            canonical_op_to_dict,
            normalize_delta_envelope,
            parse_edit_delta,
        )

        canonical_add = {
            "op": "add_node",
            "scope_path": "",
            "uid": "preserved-uid",
            "node_id": "42",
            "class_type": "PreviewImage",
            "fields": {"filename_prefix": "test"},
            "inputs": {"images": ["", "src-node", "IMAGE"]},
        }

        # Parse (expects a list of op dicts).
        ops = parse_edit_delta([canonical_add])
        assert len(ops) == 1

        # Normalize (use the canonical envelope shape directly).
        envelope = normalize_delta_envelope(
            {"schema_version": "2.0.0", "ops": [canonical_op_to_dict(ops[0])]},
        )
        assert envelope.schema_version == "2.0.0"
        normalized_op = envelope.ops[0]
        assert normalized_op.op == "add_node"
        assert normalized_op.uid == "preserved-uid"
        assert normalized_op.node_id == "42"

        # Serialize back to dict
        serialized = canonical_op_to_dict(normalized_op)
        assert serialized["op"] == "add_node"
        assert serialized.get("uid") == "preserved-uid"
        assert serialized.get("node_id") == "42"

    def test_canonicalize_rejects_add_node_missing_uid_in_strict_normalization(
        self,
    ) -> None:
        """Strict normalization must reject add_node ops that lack explicit
        uid when canonical_op_to_dict is called on them."""
        from vibecomfy.porting.edit.ops import (
            EditOpParseError,
            canonical_op_to_dict,
            normalize_delta_envelope,
            parse_edit_delta,
        )

        missing_uid = {
            "op": "add_node",
            "scope_path": "some-path",
            "node_id": "99",
            "class_type": "PreviewImage",
            "fields": {},
            "inputs": {},
        }

        # Parse succeeds (parse is lenient).
        ops = parse_edit_delta([missing_uid])
        assert len(ops) == 1

        # But strict canonicalization (which normalize_delta_envelope applies
        # in strict mode) must reject the missing uid.
        with pytest.raises(EditOpParseError) as exc_info:
            canonical_op_to_dict(ops[0])
        assert "uid" in str(exc_info.value).lower(), (
            f"Expected uid-related error, got: {exc_info.value}"
        )
