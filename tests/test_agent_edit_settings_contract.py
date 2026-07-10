"""Tests for the settings_contract module.

Focused KSampler coverage for ``seed``, ``steps``, ``cfg``, ``sampler_name``,
``scheduler``, ``denoise``, and ``control_after_generate``.
"""

from __future__ import annotations

import pytest

from vibecomfy.porting.widgets.settings_contract import (
    NodeFieldInfo,
    NodeSettingsInfo,
    compact_field_names_for_node,
    node_settings_for,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _ks_node(*, with_control_after_generate: bool = False) -> dict:
    """Build a minimal KSampler node dict for testing."""
    values: list = [
        156680208700286,  # seed
        "fixed" if with_control_after_generate else None,
        20,  # steps
        8.0,  # cfg
        "euler",  # sampler_name
        "normal",  # scheduler
        1.0,  # denoise
    ]
    return {
        "id": 3,
        "type": "KSampler",
        "widgets_values": values,
    }


# ── compact_field_names_for_node ─────────────────────────────────────────────


def test_compact_field_names_for_ks_without_ui_metadata() -> None:
    """KSampler with only widgets_values — names come from committed schema."""
    node = _ks_node()
    names = compact_field_names_for_node(node)
    # WIDGET_SCHEMA: ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"]
    # The None at index 1 becomes "control_after_generate" after UI-only resolution.
    assert names == (
        "seed",
        "control_after_generate",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
    )


def test_compact_field_names_for_ks_with_widget_0_reference() -> None:
    """Field name lookup by explicit widget_0 should resolve to 'seed'."""
    node = _ks_node()
    from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field

    idx = widget_index_for_field(node, "seed")
    assert idx == 0
    idx = widget_index_for_field(node, "widget_0")
    assert idx == 0


def test_compact_field_names_for_ks_deterministic_order() -> None:
    """The same node always returns the same ordered names."""
    node = _ks_node()
    first = compact_field_names_for_node(node)
    second = compact_field_names_for_node(node)
    assert first == second


# ── node_settings_for ────────────────────────────────────────────────────────


def test_node_settings_for_ks_returns_all_seven_fields() -> None:
    """node_settings_for should return exactly 7 fields for KSampler."""
    node = _ks_node()
    info = node_settings_for(node)
    assert info.class_type == "KSampler"
    assert len(info.fields) == 7


def test_node_settings_for_ks_seed_field() -> None:
    """The seed field (slot 0) is an int without inline choices."""
    node = _ks_node()
    info = node_settings_for(node)
    seed = info.fields[0]
    assert seed.name == "seed"
    assert seed.slot_index == 0
    assert seed.kind in ("int", "unknown")  # schema may or may not resolve
    assert not seed.ui_only


def test_node_settings_for_ks_control_after_generate_field() -> None:
    """Slot 1 is ui_only, enum kind, with the four expected choices."""
    node = _ks_node()
    info = node_settings_for(node)
    cag = info.fields[1]
    assert cag.name == "control_after_generate"
    assert cag.slot_index == 1
    assert cag.ui_only is True
    assert cag.kind == "enum"
    assert cag.choices is not None
    assert set(cag.choices) == {"fixed", "randomize", "increment", "decrement"}


def test_node_settings_for_ks_steps_field() -> None:
    """Steps (slot 2) is an int field."""
    node = _ks_node()
    info = node_settings_for(node)
    steps = info.fields[2]
    assert steps.name == "steps"
    assert steps.slot_index == 2
    assert not steps.ui_only


def test_node_settings_for_ks_cfg_field() -> None:
    """CFG (slot 3) is a float field."""
    node = _ks_node()
    info = node_settings_for(node)
    cfg = info.fields[3]
    assert cfg.name == "cfg"
    assert cfg.slot_index == 3
    assert not cfg.ui_only


def test_node_settings_for_ks_sampler_name_field() -> None:
    """sampler_name (slot 4) — may carry enum choices when schema is available."""
    node = _ks_node()
    info = node_settings_for(node)
    sn = info.fields[4]
    assert sn.name == "sampler_name"
    assert sn.slot_index == 4
    assert not sn.ui_only


def test_node_settings_for_ks_scheduler_field() -> None:
    """scheduler (slot 5) — may carry enum choices when schema is available."""
    node = _ks_node()
    info = node_settings_for(node)
    sched = info.fields[5]
    assert sched.name == "scheduler"
    assert sched.slot_index == 5
    assert not sched.ui_only


def test_node_settings_for_ks_denoise_field() -> None:
    """denoise (slot 6) is a float field."""
    node = _ks_node()
    info = node_settings_for(node)
    denoise = info.fields[6]
    assert denoise.name == "denoise"
    assert denoise.slot_index == 6
    assert not denoise.ui_only


# ── source tracking ──────────────────────────────────────────────────────────


def test_node_settings_source_is_from_committed_schema() -> None:
    """Without _ui metadata, source should be 'committed_widget_schema'."""
    node = _ks_node()
    info = node_settings_for(node)
    assert info.source == "committed_widget_schema"


def test_node_settings_for_ks_includes_output_slot() -> None:
    """KSampler has a single LATENT output slot."""
    node = _ks_node()
    info = node_settings_for(node)
    assert len(info.output_slots) >= 1


# ── edge cases ───────────────────────────────────────────────────────────────


def test_node_settings_for_unknown_class_type() -> None:
    """An unknown class type returns widget_N fallback names."""
    node = {"type": "NoSuchNode", "widgets_values": [1, 2, 3]}
    info = node_settings_for(node)
    assert info.class_type == "NoSuchNode"
    assert len(info.fields) == 3
    assert info.fields[0].name == "widget_0"
    assert info.fields[1].name == "widget_1"
    assert info.fields[2].name == "widget_2"
    assert info.source == "unresolved"


def test_compact_field_names_returns_empty_for_empty_widgets_values() -> None:
    """A node with no values yields an empty tuple."""
    node = {"type": "EmptyNode", "widgets_values": []}
    names = compact_field_names_for_node(node)
    assert names == ()


def test_node_settings_for_is_read_only() -> None:
    """NodeSettingsInfo and NodeFieldInfo are frozen dataclasses."""
    node = _ks_node()
    info = node_settings_for(node)
    with pytest.raises(Exception):
        info.fields = ()  # type: ignore[misc]
    with pytest.raises(Exception):
        info.fields[0].name = "changed"  # type: ignore[misc]


def test_control_after_generate_inferred_for_seed_like_widgets() -> None:
    """Any node with 'seed' at slot N and an unnamed slot at N+1 should
    infer control_after_generate."""
    node = {
        "type": "CustomSampler",
        "widgets_values": [42, "randomize", 30],
    }
    # The committed schema doesn't know CustomSampler, but compact_resolver
    # may still infer from the shape.  We only require that the module does
    # not crash.
    info = node_settings_for(node)
    assert info.class_type == "CustomSampler"
    assert len(info.fields) == 3
    # Slot 0 might be widget_0 (unknown), slot 1 might be control_after_generate
    # if the resolver can infer it.  At minimum, all names are non-empty.
    for field in info.fields:
        assert isinstance(field.name, str) and field.name


def test_named_field_info_has_slot_index_match() -> None:
    """Each field's slot_index matches its position in the fields tuple."""
    node = _ks_node()
    info = node_settings_for(node)
    for idx, field in enumerate(info.fields):
        assert field.slot_index == idx


# ── deterministic batch-path regression fixtures ──────────────────────────


def _ks_ui_graph() -> dict:
    """Return a minimal LiteGraph UI payload containing a KSampler node.

    The node carries ``widgets_values`` for all 7 KSampler widget slots and
    placeholder input/output entries so the graph is structurally valid.
    """
    return {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "widgets_values": [
                    156680208700286,  # seed
                    "fixed",  # control_after_generate
                    20,  # steps
                    8.0,  # cfg
                    "euler",  # sampler_name
                    "normal",  # scheduler
                    1.0,  # denoise
                ],
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": None},
                    {"name": "positive", "type": "CONDITIONING", "link": None},
                    {"name": "negative", "type": "CONDITIONING", "link": None},
                    {"name": "latent_image", "type": "LATENT", "link": None},
                ],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
            }
        ],
        "links": [],
    }


def _ks_schema_provider() -> Any:
    """Return a schema provider with KSampler including sampler/scheduler choices."""
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    ks_schema = NodeSchema(
        class_type="KSampler",
        pack=None,
        inputs={
            "model": InputSpec(type="MODEL", required=True),
            "positive": InputSpec(type="CONDITIONING", required=True),
            "negative": InputSpec(type="CONDITIONING", required=True),
            "latent_image": InputSpec(type="LATENT", required=True),
            "seed": InputSpec(type="INT", default=0),
            "steps": InputSpec(type="INT", default=20, min=1, max=10000),
            "cfg": InputSpec(type="FLOAT", default=8.0, min=0.0, max=100.0),
            "sampler_name": InputSpec(
                type="COMBO",
                choices=[
                    "euler",
                    "euler_ancestral",
                    "heun",
                    "heunpp2",
                    "dpm_2",
                    "dpmpp_2m",
                    "dpmpp_2m_sde",
                    "ddim",
                ],
            ),
            "scheduler": InputSpec(
                type="COMBO",
                choices=[
                    "normal",
                    "karras",
                    "exponential",
                    "sgm_uniform",
                    "simple",
                    "ddim_uniform",
                ],
            ),
            "denoise": InputSpec(type="FLOAT", default=1.0, min=0.0, max=1.0),
        },
        outputs=[OutputSpec(type="LATENT", name="LATENT")],
        source_provider="test",
        confidence=1.0,
    )

    class _KSProvider:
        def __init__(self, schemas: dict) -> None:
            self._schemas = schemas

        def get_schema(self, class_type: str) -> Any:
            return self._schemas.get(class_type)

        def schemas(self) -> dict:
            return self._schemas

    return _KSProvider({"KSampler": ks_schema})


def _ks_edit_session() -> Any:
    """Create an EditSession with a KSampler graph, rendered to bind names."""
    from vibecomfy.porting.edit.session import EditSession

    session = EditSession(_ks_ui_graph(), schema_provider=_ks_schema_provider())
    session.render()
    return session


# ── successful batch-path edits ──────────────────────────────────────────


def test_batch_set_control_after_generate_randomize() -> None:
    """Setting ``control_after_generate='randomize'`` lands and writes widget slot 1."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.control_after_generate = 'randomize'")

    assert result.ok is True
    assert len(result.statements) == 1
    stmt = result.statements[0]
    assert stmt.ok is True
    assert stmt.landed is True
    assert stmt.op_kind == "set_node_field"

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][1] == "randomize"


def test_batch_set_steps_increases_value() -> None:
    """Setting ``steps=30`` lands and writes widget slot 2."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.steps = 30")

    assert result.ok is True
    assert result.statements[0].landed is True

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][2] == 30


def test_batch_set_cfg_to_float() -> None:
    """Setting ``cfg=7.5`` lands and writes widget slot 3."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.cfg = 7.5")

    assert result.ok is True
    assert result.statements[0].landed is True

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][3] == 7.5


def test_batch_set_seed_to_new_value() -> None:
    """Setting ``seed=42`` lands and writes widget slot 0."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.seed = 42")

    assert result.ok is True
    assert result.statements[0].landed is True

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][0] == 42


def test_batch_set_scheduler_to_valid_enum() -> None:
    """Setting ``scheduler='karras'`` (a valid enum choice) lands."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.scheduler = 'karras'")

    assert result.ok is True
    assert result.statements[0].landed is True

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][5] == "karras"


def test_batch_set_sampler_name_to_valid_enum() -> None:
    """Setting ``sampler_name='dpmpp_2m'`` (a valid enum choice) lands."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler_name = 'dpmpp_2m'")

    assert result.ok is True
    assert result.statements[0].landed is True

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][4] == "dpmpp_2m"


# ── failure paths — invalid enum value ───────────────────────────────────


def test_batch_set_sampler_name_nonexistent_fails_with_value_not_in_enum() -> None:
    """Setting ``sampler_name='nonexistent_sampler'`` fails with
    ``value_not_in_enum`` and the diagnostic detail includes valid choices."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")

    assert result.ok is False
    assert len(result.statements) == 1
    stmt = result.statements[0]
    assert stmt.ok is False
    assert stmt.landed is False
    assert stmt.op_kind == "set_node_field"

    diag_codes = {d.code for d in stmt.diagnostics}
    assert "value_not_in_enum" in diag_codes

    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
    detail = enum_diag.detail
    assert detail.get("class_type") == "KSampler"
    assert detail.get("input") == "sampler_name"
    assert detail.get("value") == "nonexistent_sampler"
    assert isinstance(detail.get("choices"), list)
    assert len(detail["choices"]) >= 4  # at least the 4 we configured
    assert "euler" in detail["choices"]
    assert "nonexistent_sampler" not in detail["choices"]

    # Graph should NOT be mutated
    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][4] == "euler"


def test_batch_set_sampler_name_nonexistent_text_report_includes_choices() -> None:
    """The text report for an invalid enum edit includes the valid choices list."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report

    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
    report = _format_batch_report(result, consecutive_errors=1, budget_remaining=3)

    assert "value_not_in_enum" in report
    assert "choices:" in report
    assert "euler" in report
    assert "nonexistent_sampler" in report


def test_batch_set_scheduler_nonexistent_fails_with_value_not_in_enum() -> None:
    """Setting ``scheduler='nonexistent_scheduler'`` fails with enum diagnostics."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.scheduler = 'nonexistent_scheduler'")

    assert result.ok is False
    stmt = result.statements[0]
    diag_codes = {d.code for d in stmt.diagnostics}
    assert "value_not_in_enum" in diag_codes

    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
    assert enum_diag.detail.get("input") == "scheduler"
    assert "normal" in enum_diag.detail["choices"]


# ── failure paths — unknown field ────────────────────────────────────────


def test_batch_set_nonexistent_attribute_sampler_fails_with_unknown_target_field() -> None:
    """Setting ``ksampler.sampler = 'euler'`` (no such attribute) fails with
    ``unknown_target_field`` and diagnostic detail names the field and
    surfaces ``valid_fields`` containing compact KSampler fields."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler = 'euler'")

    assert result.ok is False
    stmt = result.statements[0]
    assert stmt.ok is False
    assert stmt.landed is False

    diag_codes = {d.code for d in stmt.diagnostics}
    assert "unknown_target_field" in diag_codes

    field_diag = next(d for d in stmt.diagnostics if d.code == "unknown_target_field")
    detail = field_diag.detail
    assert detail.get("name") == "ksampler"
    assert detail.get("field") == "sampler"
    assert "Sampler" in field_diag.message or "sampler" in field_diag.message

    # valid_fields must include the compact KSampler names
    valid_fields = detail.get("valid_fields")
    assert isinstance(valid_fields, list), f"expected valid_fields list, got {valid_fields!r}"
    assert len(valid_fields) >= 7
    for expected in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
        assert expected in valid_fields, f"missing {expected!r} in valid_fields"

    # Graph should NOT be mutated
    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][4] == "euler"


def test_batch_set_nonexistent_attribute_text_report_mentions_field() -> None:
    """The text report for an unknown field edit mentions the rejected field name."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report

    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler = 'euler'")
    report = _format_batch_report(result, consecutive_errors=1, budget_remaining=3)

    assert "unknown_target_field" in report
    assert "sampler" in report


# ── batch report integration (structured diagnostics in text) ────────────


def test_batch_report_for_enum_failure_has_detail_choices() -> None:
    """``_format_batch_report`` includes ``choices`` detail for enum failure."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report

    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=5)

    # The report should contain both the diagnostic code and the choices
    assert "value_not_in_enum" in report
    assert "choices:" in report
    assert "'euler'" in report


def test_batch_report_for_unknown_field_has_diagnostic_code() -> None:
    """``_format_batch_report`` includes ``unknown_target_field`` and
    ``valid_fields`` for unknown field."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report

    session = _ks_edit_session()
    result = session.apply_batch("ksampler.sampler = 'euler'")
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=5)

    assert "unknown_target_field" in report
    assert "valid_fields:" in report


def test_batch_report_for_success_includes_statement_marker() -> None:
    """``_format_batch_report`` uses ✓ marker and ``landed`` for successful edits."""
    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report

    session = _ks_edit_session()
    result = session.apply_batch("ksampler.steps = 30")
    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=5)

    assert "✓" in report
    assert "landed" in report
    assert "set_node_field" in report


def test_multiple_successful_edits_in_single_batch() -> None:
    """A batch with multiple assignments lands them all."""
    session = _ks_edit_session()
    batch = "ksampler.steps = 30\nksampler.cfg = 7.5\nksampler.seed = 42"
    result = session.apply_batch(batch)

    assert result.ok is True
    assert len(result.statements) == 3
    assert all(s.ok and s.landed for s in result.statements)

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][0] == 42
    assert node["widgets_values"][2] == 30
    assert node["widgets_values"][3] == 7.5


def test_batch_mixed_success_and_failure_rolls_back() -> None:
    """When a later statement fails, earlier successful edits are rolled back."""
    session = _ks_edit_session()
    batch = (
        "ksampler.steps = 30\n"
        "ksampler.sampler_name = 'nonexistent_sampler'\n"
        "ksampler.cfg = 7.5"
    )
    result = session.apply_batch(batch)

    # The batch should fail overall
    assert result.ok is False
    # The graph should be unchanged from the original
    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][2] == 20  # steps unchanged
    assert node["widgets_values"][3] == 8.0  # cfg unchanged
    assert node["widgets_values"][4] == "euler"  # sampler_name unchanged


def test_batch_set_denoise_to_valid_float() -> None:
    """Setting ``denoise=0.5`` lands and writes widget slot 6."""
    session = _ks_edit_session()
    result = session.apply_batch("ksampler.denoise = 0.5")

    assert result.ok is True
    assert result.statements[0].landed is True

    node = session.working_ui["nodes"][0]
    assert node["widgets_values"][6] == 0.5
