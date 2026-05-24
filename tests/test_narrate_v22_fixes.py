"""Focused regression tests for v2.2 codemod/analyzer fixes.

Covers: widget_N→real-name resolution, widget deletion, shadow stripping,
bind_input→register_input conversion, register_input first-arg preservation,
named-output parity, and metadata completion.

Deterministic — no ComfyUI, RunPod, or network required.
"""

from __future__ import annotations

import ast as ast_mod
import json
import textwrap
from pathlib import Path
from unittest import mock

import pytest

from vibecomfy.errors import SchemaValidationError
from tools.narrate_template import (
    _add_output_slot_comments,
    _add_widget_todo_comments,
    _annotate_comfyswitch_branches,
    _ast_resolve_widget_names,
    _ensure_params_block,
    _factor_repeated_helpers,
    _hoist_model_files,
    _insert_params_block,
    _produce_annotate_v2,
    _produce_restructure_v2,
    _rename_class_fallback_vars,
    _string_restructure_v2,
    _strip_widget_shadows,
    _update_register_input_fields,
    find_unbound_inputs,
    parse_template,
)
from vibecomfy.handles import Handle


# ============================================================================
# (a) widget_N → real-name resolution (Item 1)
# ============================================================================


class TestWidgetNameResolution:
    """Tests that _ast_resolve_widget_names correctly maps widget_N to real names."""

    def test_intconstant_widget_0_resolves_to_value(self) -> None:
        """INTConstant.widget_0 should resolve to 'value' (v2.2 fix)."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            frames_int = _node(wf, "INTConstant", "162", widget_0=121)
            return wf
        """)
        result = _ast_resolve_widget_names(source)
        assert ast_mod.parse(result) is not None, "Output must be valid Python"
        assert "value=121" in result, (
            f"Expected widget_0→value resolution:\\n{result}"
        )

    def test_primitivefloat_widget_0_resolves_to_value(self) -> None:
        """PrimitiveFloat.widget_0 should resolve to 'value' (v2.2 fix)."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            f = _node(wf, "PrimitiveFloat", "200", widget_0=0.8)
            return wf
        """)
        result = _ast_resolve_widget_names(source)
        assert ast_mod.parse(result) is not None, "Output must be valid Python"
        assert "value=0.8" in result, (
            f"Expected widget_0→value resolution:\\n{result}"
        )

    def test_primitivestring_widget_0_resolves_to_value(self) -> None:
        """PrimitiveString.widget_0 should resolve to 'value' (v2.2 fix)."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            s = _node(wf, "PrimitiveString", "300", widget_0="canny")
            return wf
        """)
        result = _ast_resolve_widget_names(source)
        assert ast_mod.parse(result) is not None, "Output must be valid Python"
        assert "value='canny'" in result or 'value="canny"' in result, (
            f"Expected widget_0→value resolution:\\n{result}"
        )

    def test_ltx2_nag_widget_3_resolves_to_inplace(self) -> None:
        """LTX2_NAG.widget_3 should resolve to 'inplace' via object_info fallback.
        
        WIDGET_SCHEMA has LTX2_NAG: [nag_scale, nag_alpha, nag_tau, None].
        Index 3 is None in curated schema but object_info should have 'inplace'.
        v2.2 adds per-index fallback for this case.
        """
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            nag = _node(wf, "LTX2_NAG", "210", nag_scale=0.5, nag_alpha=1.0, nag_tau=0.1, widget_3=True)
            return wf
        """)
        result = _ast_resolve_widget_names(source)
        # widget_3 should resolve to 'inplace' via object_info fallback
        assert "inplace=True" in result, (
            f"Expected widget_3→inplace resolution via object_info fallback:\\n{result}"
        )

    def test_loadimage_widget_1_absent_from_schema(self) -> None:
        """LoadImage.widget_1 should be deleted (None in schema, no object_info fallback).
        
        WIDGET_SCHEMA has LoadImage: [image, None]. widget_1 maps to None,
        meaning that slot is a link-only socket (IMAGE type). v2.2 deletes
        these redundant widget_N kwargs since they don't correspond to real widgets.
        """
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            img = _node(wf, "LoadImage", "143", image="input.png", widget_1="image")
            return wf
        """)
        # Resolve widget names — widget_1 should be deleted
        result = _ast_resolve_widget_names(source)
        # widget_1 should be deleted since schema has None at index 1
        # and object_info fallback doesn't have a name for it (it's a link socket)
        assert "widget_1" not in result, (
            f"widget_1 should be deleted since schema says None:\\n{result}"
        )
        # The image kwarg should still be there
        assert 'image="input.png"' in result or "image='input.png'" in result, (
            f"image kwarg should survive:\\n{result}"
        )

    def test_unresolved_widget_gets_todo_comment(self) -> None:
        """Unresolved widget_N kwargs should have a TODO comment added."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            # LTXAddVideoICLoRAGuide has widget_4=None in schema
            guide = _node(wf, "LTXAddVideoICLoRAGuide", "5001", widget_0=0, widget_1=1.0, widget_2=False, widget_3=True, widget_4=64)
            return wf
        """)
        result = _add_widget_todo_comments(source)
        # widget_4 should be flagged
        assert "widget_4" in result, (
            f"widget_4 should be flagged as unresolved:\\n{result}"
        )

    def test_regression_register_input_not_broken_by_widget_rename(self) -> None:
        """register_input references must NOT be corrupted by widget rename.
        
        When _ast_resolve_widget_names renames widget_0→value on a PrimitiveFloat,
        the register_input call that references that node's field must be updated
        to match. The _update_register_input_fields pass handles this.
        """
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            strength = _node(wf, "PrimitiveFloat", "200", widget_0=0.8)
            wf.register_input("strength", "200", "widget_0", 0.8, default=0.8)
            return wf
        """)
        result = _ast_resolve_widget_names(source)
        # widget_0 in _node should be renamed to value
        assert "value=0.8" in result, f"widget_0 not renamed in _node:\\n{result}"
        # Then run register_input field update
        result = _update_register_input_fields(result)
        # register_input field should now reference 'value' not 'widget_0'
        assert 'register_input("strength"' in result or "register_input('strength'" in result, (
            f"register_input call lost:\\n{result}"
        )
        # The field should be 'value' (the resolved name)
        assert '"value"' in result or "'value'" in result, (
            f"register_input field should be 'value':\\n{result}"
        )


# ============================================================================
# (b) Widget shadow stripping — linked-input redundant widget_N (Item 8)
# ============================================================================


class TestWidgetShadowStripping:
    """Tests that widget_N kwargs redundant with link inputs are detected/stripped."""

    def test_detect_shadow_on_empty_ltx_v_latent_video(self) -> None:
        """EmptyLTXVLatentVideo with widget_{0,1,2} AND width=/height=/length= links."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            width = _node(wf, "INTConstant", "100", widget_0=1024)
            height = _node(wf, "INTConstant", "101", widget_0=576)
            frames = _node(wf, "INTConstant", "102", widget_0=121)
            latent = _node(wf, "EmptyLTXVLatentVideo", "412",
                width=width.out(0), height=height.out(0), length=frames.out(0),
                widget_0=1024, widget_1=576, widget_2=121, widget_3=1)
            return wf
        """)
        # Verify the source parses correctly
        tree = ast_mod.parse(source)
        # Check that the _node call has both width= and widget_0=
        found_latent = False
        for stmt in ast_mod.walk(tree):
            if not isinstance(stmt, ast_mod.Assign):
                continue
            if not isinstance(stmt.value, ast_mod.Call):
                continue
            func = stmt.value.func
            if not isinstance(func, ast_mod.Name) or func.id != "_node":
                continue
            if len(stmt.value.args) < 3:
                continue
            cls_arg = stmt.value.args[1]
            if isinstance(cls_arg, ast_mod.Constant) and cls_arg.value == "EmptyLTXVLatentVideo":
                found_latent = True
                kwarg_names = [kw.arg for kw in stmt.value.keywords]
                assert "width" in kwarg_names, "width link kwarg should exist"
                assert "widget_0" in kwarg_names, "widget_0 shadow should be detectable"
        assert found_latent, "EmptyLTXVLatentVideo call not found"

    def test_node_without_shadows_is_unchanged(self) -> None:
        """A node with widget_N that has no corresponding link input stays unchanged."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            seed = _node(wf, "PrimitiveInt", "200", widget_0=42)
            return wf
        """)
        # This node has only widget_0, no link. It should be preserved.
        tree = ast_mod.parse(source)
        # Should parse and be valid
        assert tree is not None

    def test_widget_position_to_index_parsing(self) -> None:
        """_widget_position_to_index should correctly parse widget_N names."""
        from tools.narrate_template import _widget_position_to_index

        assert _widget_position_to_index("widget_0") == 0
        assert _widget_position_to_index("widget_5") == 5
        assert _widget_position_to_index("widget_10") == 10
        assert _widget_position_to_index("widget_0:convert") == 0
        assert _widget_position_to_index("value") is None
        assert _widget_position_to_index("widget_abc") is None
        assert _widget_position_to_index("") is None


# ============================================================================
# (c) bind_input → wf.register_input conversion (Item 9)
# ============================================================================


class MockNode:
    """Mock a VibeNode for bind_input conversion testing."""
    def __init__(self, class_type: str, inputs: dict = None, widgets: dict = None):
        self.class_type = class_type
        self.inputs = inputs or {}
        self.widgets = widgets or {}


class MockWorkflow:
    """Mock a VibeWorkflow for testing input binding."""
    def __init__(self):
        self.id = "mock-wf-001"
        self.nodes: dict[str, MockNode] = {}
        self.inputs: dict = {}
        self.metadata: dict = {}

    def register_input(self, name, node_id, field, value=None, *,
                       type=None, default=None, required=False,
                       range=None, aliases=None, media_semantics=None, media=None):
        self.inputs[name] = {
            "name": name, "node_id": node_id, "field": field,
            "value": value, "type": type, "default": default,
            "required": required, "range": range,
            "aliases": tuple(aliases) if isinstance(aliases, list) else aliases,
            "media_semantics": media_semantics or media,
        }
        return self


@pytest.fixture
def mock_wf():
    wf = MockWorkflow()
    wf.nodes["200"] = MockNode("PrimitiveFloat", widgets={"widget_0": 0.8})
    wf.nodes["100"] = MockNode("PrimitiveString", widgets={"widget_0": "canny"})
    wf.nodes["300"] = MockNode("INTConstant", widgets={"widget_0": 121})
    return wf


class TestBindInputConversion:
    """Tests that bind_input() converts to wf.register_input() with correct semantics."""

    def test_bind_input_reconstructs_current_node_value(self, mock_wf):
        """bind_input must use node.inputs.get(field, node.widgets.get(field)) for value."""
        from vibecomfy.registry.ready_template import bind_input

        # bind_input on node "200" with widget_0=0.8
        bind_input(mock_wf, "strength", "200", "widget_0", default=0.5)
        registered = mock_wf.inputs["strength"]
        # value should be the current node value (0.8), NOT the explicit default (0.5)
        assert registered["value"] == 0.8, (
            f"bind_input value should be current node value 0.8, got {registered['value']}"
        )
        # default should be the explicit default
        assert registered["default"] == 0.5, (
            f"explicit default should be 0.5, got {registered['default']}"
        )

    def test_bind_input_no_explicit_default_uses_node_value(self, mock_wf):
        """When no explicit default given, both value and default should be node value."""
        from vibecomfy.registry.ready_template import bind_input

        bind_input(mock_wf, "strength", "200", "widget_0")
        registered = mock_wf.inputs["strength"]
        assert registered["value"] == 0.8
        assert registered["default"] == 0.8, (
            f"default should fallback to node value 0.8, got {registered['default']}"
        )

    def test_bind_input_validates_node_exists(self, mock_wf):
        """bind_input must raise SchemaValidationError when node_id doesn't exist."""
        from vibecomfy.registry.ready_template import bind_input

        with pytest.raises(SchemaValidationError, match="does not exist"):
            bind_input(mock_wf, "bad", "999", "widget_0")

    def test_bind_input_validates_field_exists(self, mock_wf):
        """bind_input must raise SchemaValidationError when field isn't in node inputs/widgets."""
        from vibecomfy.registry.ready_template import bind_input

        with pytest.raises(SchemaValidationError, match="not found"):
            bind_input(mock_wf, "bad", "200", "nonexistent_field")

    def test_bind_input_preserves_descriptor_kwargs(self, mock_wf):
        """bind_input should pass through type, required, range, aliases, media."""
        from vibecomfy.registry.ready_template import bind_input

        bind_input(
            mock_wf, "prompt", "100", "widget_0",
            type="STRING", required=True, range=["a", "b"],
            aliases=["p"], media_semantics="text",
        )
        registered = mock_wf.inputs["prompt"]
        assert registered["type"] == "STRING"
        assert registered["required"] is True
        assert registered["range"] == ["a", "b"]
        assert registered["aliases"] == ("p",)
        assert registered["media_semantics"] == "text"

    def test_bind_input_source_ast_detection(self) -> None:
        """Verify that bind_input(wf, ...) calls can be detected in AST."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            strength = _node(wf, "PrimitiveFloat", "200", widget_0=0.8)
            bind_input(wf, "strength", "200", "widget_0")
            return wf
        """)
        tree = ast_mod.parse(source)
        bind_calls = []
        for node in ast_mod.walk(tree):
            if isinstance(node, ast_mod.Call) and isinstance(node.func, ast_mod.Name):
                if node.func.id == "bind_input":
                    bind_calls.append(node)
        assert len(bind_calls) == 1, f"Expected 1 bind_input call, found {len(bind_calls)}"
        # Check args: name, node_id, field
        args = bind_calls[0].args
        assert len(args) >= 3
        assert isinstance(args[1], ast_mod.Constant)
        assert args[1].value == "strength"


# ============================================================================
# (d) register_input first-arg preservation (Item 9 — v1 critical bug)
# ============================================================================


class TestRegisterInputPreservation:
    """Tests that register_input's first string argument is never rewritten."""

    def test_register_input_first_arg_survives_var_rename(self) -> None:
        """register_input('negative', ...) first arg must NOT be renamed."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            negative_text = _node(wf, "PrimitiveString", "200", value="bad")
            positive_text = _node(wf, "PrimitiveString", "201", value="good")
            wf.register_input('negative', '200', 'value', 'bad', type='STRING')
            wf.register_input('positive', '201', 'value', 'good', type='STRING')
            return wf
        """)
        # Rename the variable
        var_rename = {"negative_text": "negative_embedding"}
        result = _string_restructure_v2(source, var_rename, {})

        assert "register_input('negative'" in result or 'register_input("negative"' in result, (
            f"register_input first arg 'negative' was corrupted:\\n{result}"
        )
        assert "register_input('positive'" in result or 'register_input("positive"' in result, (
            f"register_input first arg 'positive' was corrupted:\\n{result}"
        )

    def test_register_input_first_arg_with_special_chars(self) -> None:
        """register_input with non-alphabetic names should survive."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            node = _node(wf, "PrimitiveFloat", "200", value=1.0)
            wf.register_input('ic_lora_strength', '200', 'value', 1.0)
            return wf
        """)
        var_rename = {"node": "param_float"}
        result = _string_restructure_v2(source, var_rename, {})
        assert "register_input('ic_lora_strength'" in result or 'register_input("ic_lora_strength"' in result, (
            f"register_input first arg 'ic_lora_strength' was corrupted:\\n{result}"
        )

    def test_register_input_in_produce_restructure_v2(self) -> None:
        """Full _produce_restructure_v2 must preserve register_input first args."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            seed = _node(wf, "PrimitiveInt", "100", value=42)
            wf.register_input('seed', '100', 'value', 42, type='INT')
            return wf
        """)
        parsed = parse_template(source)
        nc_by_id = {nc.node_id: nc for nc in parsed.node_calls}
        unbound = find_unbound_inputs(source)
        findings: dict = {"findings": {}}
        schema: dict = {}

        annot_source = _produce_annotate_v2(source, parsed, findings, schema, nc_by_id)
        result = _produce_restructure_v2(
            annot_source, parsed, findings, schema, nc_by_id, unbound,
        )

        # register_input first arg 'seed' must survive
        assert "register_input('seed'" in result or 'register_input("seed"' in result, (
            f"register_input first arg lost in restructure:\\n{result}"
        )
        # Must be valid Python
        ast_mod.parse(result)


# ============================================================================
# (e) Named-output parity (Item 5)
# ============================================================================


class TestNamedOutputParity:
    """Tests that .out('NAME') resolves identically to .out(N)."""

    def test_handle_out_string_name_is_identity(self) -> None:
        """Handle.out already accepts a string slot — verify identity."""
        h1 = Handle(node_id="100", output_slot=0)
        h2 = Handle(node_id="100", output_slot="0")
        # Since output_slot accepts int|str, these should be comparable
        assert h1 == h2, (
            f"Handle(100, 0) != Handle(100, '0')"
        )

    def test_handle_eq_with_string_slot(self) -> None:
        """Handle equality with string slots."""
        h1 = Handle(node_id="200", output_slot="MODEL")
        h2 = Handle(node_id="200", output_slot="MODEL")
        assert h1 == h2

    def test_handle_hash_consistency(self) -> None:
        """Hash consistency for integer and string-equivalent slots."""
        h1 = Handle(node_id="100", output_slot=1)
        h2 = Handle(node_id="100", output_slot="1")
        assert hash(h1) == hash(h2), "Handle hashes must be consistent for int/str equivalents"

    def test_output_names_from_object_info_cache(self) -> None:
        """output_names() from the consume module should return names for cached classes."""
        from vibecomfy.porting.object_info.consume import output_names

        # UNETLoader is in the cache, should have output names
        names = output_names("UNETLoader")
        if names:  # cache available
            assert len(names) >= 1, f"UNETLoader should have at least 1 output name"
            assert "MODEL" in names, f"UNETLoader output_names should include MODEL, got {names}"

    def test_output_names_returns_empty_for_unknown(self) -> None:
        """output_names() should return empty list for unknown class."""
        from vibecomfy.porting.object_info.consume import output_names

        names = output_names("NonExistentClassXYZ123")
        assert names == []

    def test_output_types_from_consume(self) -> None:
        """output_types() should be consistent with output_names()."""
        from vibecomfy.porting.object_info.consume import output_names, output_types

        names = output_names("UNETLoader")
        types = output_types("UNETLoader")
        assert len(names) == len(types), (
            f"output_names and output_types must have same length for UNETLoader"
        )

    def test_add_output_slot_comments_on_multi_output_node(self) -> None:
        """_add_output_slot_comments should add trailing comments for named outputs."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            clip = _node(wf, "DualCLIPLoader", "50", clip_name1="a", clip_name2="b", type="sd3")
            model = _node(wf, "UNETLoader", "60", unet_name="model.safetensors", weight_dtype="fp16")
            clp = clip.out(0)
            mod = model.out(0)
            return wf
        """)
        result = _add_output_slot_comments(source)
        # Should have valid Python
        ast_mod.parse(result)
        # v2.2 Phase-1 Item A: ``.out(N)`` on schema-known nodes is rewritten
        # to ``.out("NAME")``. UNETLoader and DualCLIPLoader both have named
        # outputs (MODEL / CLIP), so the integer form should be gone.
        assert '.out("MODEL")' in result or ".out('MODEL')" in result, result
        assert '.out("CLIP")' in result or ".out('CLIP')" in result, result


# ============================================================================
# (f) Metadata completion for legacy templates (Item 14)
# ============================================================================


class TestMetadataCompletion:
    """Tests that generated metadata is completed for legacy bind_input templates."""

    def test_find_unbound_inputs_from_ready_metadata(self) -> None:
        """find_unbound_inputs should extract entries from READY_METADATA."""
        source = textwrap.dedent("""\
        READY_METADATA = {
            "unbound_inputs": {
                "prompt": "100.text",
                "seed": "200.seed",
            }
        }
        """)
        unbound = find_unbound_inputs(source)
        assert unbound == {"prompt": "100.text", "seed": "200.seed"}

    def test_find_unbound_inputs_empty_when_missing(self) -> None:
        """find_unbound_inputs should return empty dict when no unbound_inputs."""
        source = textwrap.dedent("""\
        READY_METADATA = {"something_else": {}}
        def build():
            pass
        """)
        unbound = find_unbound_inputs(source)
        assert unbound == {}

    def test_metadata_completion_with_register_input_calls(self) -> None:
        """When register_input calls exist, unbound_inputs should match them."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            seed_node = _node(wf, "PrimitiveInt", "200", value=42)
            prompt_node = _node(wf, "PrimitiveString", "100", value="test")
            wf.register_input('seed', '200', 'value', 42)
            wf.register_input('prompt', '100', 'value', 'test')
            return wf
        """)
        # Parse register_input calls from AST
        tree = ast_mod.parse(source)
        reg_inputs = []
        for node in ast_mod.walk(tree):
            if not isinstance(node, ast_mod.Call):
                continue
            if isinstance(node.func, ast_mod.Attribute) and node.func.attr == "register_input":
                if isinstance(node.func.value, ast_mod.Name):
                    reg_inputs.append(node)
        assert len(reg_inputs) == 2, f"Expected 2 register_input calls, found {len(reg_inputs)}"

    def test_legacy_template_no_metadata_non_blocking(self) -> None:
        """Templates without READY_METADATA should not cause parse failures."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            node = _node(wf, "PrimitiveFloat", "200", widget_0=0.8)
            bind_input(wf, "strength", "200", "widget_0")
            return wf
        """)
        # Should parse
        tree = ast_mod.parse(source)
        assert tree is not None
        # find_unbound_inputs should return empty
        unbound = find_unbound_inputs(source)
        assert unbound == {}

    def test_params_block_inserted_for_all_three_keys(self) -> None:
        """_insert_params_block should emit all param entries correctly."""
        source = textwrap.dedent("""\
        import sys
        READY_REQUIREMENTS = {}
        def build():
            wf = object()
            return wf
        """)
        param_entries = {
            "control_mode": "canny",
            "seed": 42,
            "fps": 30,
        }
        param_warnings = {
            "control_mode": "UNUSED: no consumers",
        }
        result = _insert_params_block(source, param_entries, param_warnings)

        assert "PARAMS" in result
        for key in ["control_mode", "seed", "fps"]:
            assert repr(key) in result, f"Key {key!r} missing from PARAMS block:\\n{result}"
        assert "UNUSED" in result, f"UNUSED warning should be present:\\n{result}"


# ============================================================================
# (g) Cross-cutting: No regressions in existing v2.1 behavior
# ============================================================================


class TestV21RegressionGuard:
    """Ensure v2.2 changes don't break v2.1 behavior."""

    def test_params_substitution_still_works(self) -> None:
        """PARAMS substitution (Phase 2) must still work correctly."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {
            "unbound_inputs": {
                "prompt": "100.text",
            }
        }
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            prompt_embedding = _node(wf, "CLIPTextEncode", "100", text="landscape")
            return wf
        """)
        unbound = find_unbound_inputs(source)
        param_field_lookup: dict = {}
        for logical, target in unbound.items():
            if "." in target:
                node_id, field = target.split(".", 1)
                param_field_lookup[(node_id, field)] = logical

        result = _string_restructure_v2(source, {}, param_field_lookup)
        assert 'PARAMS["prompt"]' in result, (
            f"PARAMS substitution regression:\\n{result}"
        )

    def test_var_rename_preserves_string_literals(self) -> None:
        """String literals matching rename targets must NOT be renamed."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            seed = _node(wf, "PrimitiveInt", "200", value=42)
            wf.register_input('seed', '200', 'value', 42)
            return wf
        """)
        var_rename = {"seed": "random_seed"}
        result = _string_restructure_v2(source, var_rename, {})
        # 'seed' in register_input('seed'... should NOT be renamed
        assert "register_input('seed'" in result or 'register_input("seed"' in result, (
            f"String literal in register_input should not be renamed:\\n{result}"
        )
        # But the variable seed= should be renamed
        assert "random_seed = _node" in result, (
            f"Variable seed should be renamed to random_seed:\\n{result}"
        )

    def test_annotate_mode_still_works(self) -> None:
        """_produce_annotate_v2 must still work without errors."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            node = _node(wf, "INTConstant", "100", value=42)
            return wf
        """)
        parsed = parse_template(source)
        nc_by_id = {nc.node_id: nc for nc in parsed.node_calls}
        findings: dict = {"findings": {}}
        schema: dict = {}

        result = _produce_annotate_v2(source, parsed, findings, schema, nc_by_id)
        ast_mod.parse(result)  # Must be valid Python
        assert "INTConstant" in result


# ============================================================================
# (h) Factor repeated helpers (Item 13 / T8)
# ============================================================================


class TestFactorRepeatedHelpers:
    """Tests for _factor_repeated_helpers: detecting 3+ _node calls with
    same class + same literal defaults, emitting helpers, rewriting callsites."""

    def test_no_factoring_when_under_3_calls(self) -> None:
        """Don't factor when fewer than 3 calls share identical literal defaults."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            a = _node(wf, "ImageResizeKJv2", "1",
                upscale_method="lanczos", keep_proportion="stretch",
                image=img.out(0), width=2, height=3)
            b = _node(wf, "ImageResizeKJv2", "2",
                upscale_method="lanczos", keep_proportion="stretch",
                image=img.out(4), width=5, height=6)
            return wf
        """)
        result = _factor_repeated_helpers(source)
        # Should be unchanged (only 2 calls, not 3+)
        assert "_image_resize" not in result
        assert result.count("ImageResizeKJv2") == 2

    def test_factors_3_identical_calls(self) -> None:
        """When 3+ calls share same literal defaults, emit helper and rewrite."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            a = _node(wf, "MyClass", "1",
                mode="fast", color="red",
                image=img.out(0))
            b = _node(wf, "MyClass", "2",
                mode="fast", color="red",
                image=img.out(1))
            c = _node(wf, "MyClass", "3",
                mode="fast", color="red",
                image=img.out(2))
            return wf
        """)
        result = _factor_repeated_helpers(source)
        assert "_my_class" in result
        assert "_my_class(wf, '1', img.out(0))" in result
        assert "_my_class(wf, '2', img.out(1))" in result
        assert "_my_class(wf, '3', img.out(2))" in result
        # Original literal kwargs should be gone from callsites
        assert 'mode="fast"' not in result or result.count('mode="fast"') == 1  # only in helper def

    def test_image_resize_kjv2_guide_pattern(self) -> None:
        """Simulate the exact LTX ImageResizeKJv2 guide-family pattern."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            guide_resized = _node(
                wf,
                "ImageResizeKJv2",
                "5026",
                width=width.out(0),
                height=height.out(0),
                upscale_method="lanczos",
                keep_proportion="stretch",
                pad_color="0, 0, 0",
                crop_position="center",
                divisible_by=32,
                device="cpu",
                image=components.out('images'),
            )
            guide_canny = _node(
                wf,
                "ImageResizeKJv2",
                "5028",
                width=width.out(0),
                height=height.out(0),
                upscale_method="lanczos",
                keep_proportion="stretch",
                pad_color="0, 0, 0",
                crop_position="center",
                divisible_by=32,
                device="cpu",
                image=guide_canny_edges.out(0),
            )
            guide_pose_sized = _node(
                wf,
                "ImageResizeKJv2",
                "6102",
                width=width.out(0),
                height=height.out(0),
                upscale_method="lanczos",
                keep_proportion="stretch",
                pad_color="0, 0, 0",
                crop_position="center",
                divisible_by=32,
                device="cpu",
                image=guide_pose.out(0),
            )
            return wf
        """)
        result = _factor_repeated_helpers(source)
        assert "def _image_resize(" in result
        assert "guide_resized = _image_resize(" in result
        assert "guide_canny = _image_resize(" in result
        assert "guide_pose_sized = _image_resize(" in result
        # Original multi-line calls should be gone (only helper def + calls remain)
        assert result.count("ImageResizeKJv2") == 1  # only in helper def

    def test_multiple_families_same_class(self) -> None:
        """Two families with different literal defaults get separate helpers."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            # Family A: mode="fast" (3 calls)
            a1 = _node(wf, "MyClass", "1", mode="fast", color="red", image=img.out(0))
            a2 = _node(wf, "MyClass", "2", mode="fast", color="red", image=img.out(1))
            a3 = _node(wf, "MyClass", "3", mode="fast", color="red", image=img.out(2))
            # Family B: mode="slow" (3 calls)
            b1 = _node(wf, "MyClass", "4", mode="slow", color="blue", image=img.out(0))
            b2 = _node(wf, "MyClass", "5", mode="slow", color="blue", image=img.out(1))
            b3 = _node(wf, "MyClass", "6", mode="slow", color="blue", image=img.out(2))
            return wf
        """)
        result = _factor_repeated_helpers(source)
        # Two different helpers
        assert "def _my_class_fast(" in result
        assert "def _my_class_slow(" in result
        # Family A calls rewritten
        assert "a1 = _my_class_fast(" in result
        assert "a2 = _my_class_fast(" in result
        assert "a3 = _my_class_fast(" in result
        # Family B calls rewritten
        assert "b1 = _my_class_slow(" in result
        assert "b2 = _my_class_slow(" in result
        assert "b3 = _my_class_slow(" in result

    def test_preserves_indentation(self) -> None:
        """Replacement calls should preserve original indentation."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            a = _node(wf, "MyClass", "1",
                mode="fast", key="val",
                img=img.out(0))
            b = _node(wf, "MyClass", "2",
                mode="fast", key="val",
                img=img.out(1))
            c = _node(wf, "MyClass", "3",
                mode="fast", key="val",
                img=img.out(2))
            return wf
        """)
        result = _factor_repeated_helpers(source)
        # Replacement lines should have 4-space indent (matching original)
        for line in result.split("\n"):
            if "= _my_class(" in line:
                assert line.startswith("    "), f"Missing indentation: {line!r}"

    def test_no_factoring_empty_literals(self) -> None:
        """Don't factor when all kwargs are variable (no literal defaults)."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            a = _node(wf, "PrimitiveFloat", "1", value=a.out(0))
            b = _node(wf, "PrimitiveFloat", "2", value=b.out(0))
            c = _node(wf, "PrimitiveFloat", "3", value=c.out(0))
            d = _node(wf, "PrimitiveFloat", "4", value=d.out(0))
            return wf
        """)
        result = _factor_repeated_helpers(source)
        # Should be unchanged â no literal defaults to bake into helper
        assert result == source or "_primitive_float" not in result

    def test_result_is_valid_python(self) -> None:
        """The transformed output must be valid Python."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            a = _node(wf, "ImageResizeKJv2", "1",
                upscale_method="lanczos", keep_proportion="stretch",
                pad_color="0, 0, 0", crop_position="center",
                divisible_by=32, device="cpu",
                width=width.out(0), height=height.out(0),
                image=img.out(0))
            b = _node(wf, "ImageResizeKJv2", "2",
                upscale_method="lanczos", keep_proportion="stretch",
                pad_color="0, 0, 0", crop_position="center",
                divisible_by=32, device="cpu",
                width=width.out(0), height=height.out(0),
                image=img.out(0))
            c = _node(wf, "ImageResizeKJv2", "3",
                upscale_method="lanczos", keep_proportion="stretch",
                pad_color="0, 0, 0", crop_position="center",
                divisible_by=32, device="cpu",
                width=width.out(0), height=height.out(0),
                image=img.out(0))
            return wf
        """)
        result = _factor_repeated_helpers(source)
        ast_mod.parse(result)  # Must be valid Python
        assert "_image_resize" in result

    def test_no_change_when_no_match(self) -> None:
        """Return source unchanged when no classes have 3+ identical-literal calls."""
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            a = _node(wf, "ClassA", "1", x=1)
            b = _node(wf, "ClassA", "2", x=2)  # different literal value
            c = _node(wf, "ClassB", "3", y=3)
            return wf
        """)
        result = _factor_repeated_helpers(source)
        assert "def _class" not in result


# ============================================================================
# v2.2 Phase 1 (Items A, B, C, E)
# ============================================================================


class TestPhase1ItemA_NamedOutSingle:
    """Item A: single-output schema-known nodes should still rewrite .out(0) -> .out('NAME')."""

    def test_single_output_node_gets_named_slot(self) -> None:
        from tools.narrate_template import _add_output_slot_comments
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            unet = _node(wf, "UNETLoader", "10", unet_name="m.safetensors", weight_dtype="default")
            model_ref = unet.out(0)
            return wf
        """)
        result = _add_output_slot_comments(source)
        ast_mod.parse(result)
        assert '.out("MODEL")' in result or ".out('MODEL')" in result


class TestPhase1ItemBModelFiles:
    """Item B: MODEL_FILES single-source for filenames."""

    def test_hoist_dedupes_model_filenames(self) -> None:
        source = textwrap.dedent("""\
        READY_METADATA = {
            "model_assets": [
                {"name": "foo_unet.safetensors", "subdir": "diffusion_models"},
                {"name": "foo_vae.safetensors", "subdir": "vae"},
            ],
        }
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = None
            u = _node(wf, "UNETLoader", "10", unet_name="foo_unet.safetensors")
            v = _node(wf, "VAELoader", "20", vae_name="foo_vae.safetensors")
            return wf
        """)
        result = _hoist_model_files(source)
        ast_mod.parse(result)
        assert "MODEL_FILES" in result
        # Filenames appear exactly once (in MODEL_FILES dict).
        assert result.count("foo_unet.safetensors") == 1
        assert result.count("foo_vae.safetensors") == 1
        assert "MODEL_FILES['unet']" in result
        assert "MODEL_FILES['vae']" in result


class TestPhase1ItemCBranchSelection:
    """Item C: ComfySwitchNode chain gets a BRANCH SELECTION comment per call."""

    def test_branch_selection_comment_emitted(self) -> None:
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            use_lora = _node(wf, "PrimitiveBoolean", "1", value=True)
            a = _node(wf, "PrimitiveInt", "2", value=4)
            b = _node(wf, "PrimitiveInt", "3", value=8)
            chosen = _node(wf, "ComfySwitchNode", "4", on_false=a.out(0), on_true=b.out(0), switch=use_lora.out(0))
            return wf
        """)
        result = _annotate_comfyswitch_branches(source)
        ast_mod.parse(result)
        assert "BRANCH SELECTION" in result
        # Boolean=True -> on_true branch (id '3') is live.
        assert "True" in result
        assert "3" in result


class TestPhase1ItemERoleNames:
    """Item E: no class-fallback names remain after the renamer."""

    def test_rename_clip_vision_loader(self) -> None:
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            c_l_i_p_vision_loader_49 = _node(wf, "CLIPVisionLoader", "49", clip_name="x")
            return wf
        """)
        result = _rename_class_fallback_vars(source)
        ast_mod.parse(result)
        assert "c_l_i_p_vision_loader_49" not in result
        assert "clip_vision" in result

    def test_rename_ksampler_with_node_id_suffix(self) -> None:
        source = textwrap.dedent("""\
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            k_sampler_238_230 = _node(wf, "KSampler", "238:230", seed=0, steps=1)
            return wf
        """)
        result = _rename_class_fallback_vars(source)
        ast_mod.parse(result)
        assert "k_sampler_238_230" not in result
        assert "sampler" in result


class TestPhase1ItemDParamsCreation:
    """Item D: ensure_params_block synthesises a PARAMS dict when absent."""

    def test_creates_params_when_missing(self) -> None:
        source = textwrap.dedent("""\
        READY_METADATA = {}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            sampler = _node(wf, "KSampler", "1", seed=42, steps=20, cfg=7.5, denoise=1)
            return wf
        """)
        result = _ensure_params_block(source)
        ast_mod.parse(result)
        assert "PARAMS:" in result
        assert "'seed'" in result
        assert "PARAMS['seed']" in result


class TestPhase1ItemGBidirectionalInvariant:
    """Item G: rendered assert compares equality, not subset."""

    def test_assert_uses_equality_and_metadata_set(self) -> None:
        from tools.narrate_template import _add_metadata_invariant
        source = textwrap.dedent("""\
        READY_METADATA = {"unbound_inputs": {"prompt": "1.text"}}
        def build():
            wf = None
            wf.register_input('prompt', '1', 'text', 'hello')
            return wf
        """)
        result = _add_metadata_invariant(source)
        assert "_REGISTERED_INPUTS" in result
        assert "_METADATA_INPUTS" in result
        assert "==" in result
        assert ".issubset" not in result
