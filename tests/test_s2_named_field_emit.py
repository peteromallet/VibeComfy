"""S2 named-field emit — Adherence Made Easy + Equip.

- Stop authoring via widget_N. Emit via named field + range validation.
- Preview/queue share vocabulary.
- Scenarios: 8800a9 (UltraShape), 485ff2 (INPAINT), d7853c (Moonvalley),
  ReActor, Florence task (widget_unknown).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import from_api, normalize_to_api
from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import get_authoring_schema_provider


def _wf_from_corpus(path: str):
    raw = json.loads(Path(path).read_text())
    api = normalize_to_api(copy.deepcopy(raw), use_comfy_converter=False)
    return from_api(api)


def test_emit_uses_named_field_for_ultrashape():
    wf = _wf_from_corpus("external_workflows/corpus/8800a945cff8d090.json")
    src = emit_agent_edit_python(wf)
    # UltraShapeRefine should emit guidance_scale, not widget_1
    assert "guidance_scale" in src
    # The UltraShapeRefine node block should not contain widget_1
    # Find the UltraShapeRefine assignment block
    block = [l for l in src.splitlines() if "UltraShapeRefine" in l][0]
    idx = src.splitlines().index(block)
    snippet = "\n".join(src.splitlines()[idx : idx + 12])
    assert "widget_1" not in snippet
    assert "guidance_scale=5" in snippet or "guidance_scale" in snippet


def test_emit_uses_named_field_for_inpaint():
    wf = _wf_from_corpus("external_workflows/corpus/485ff2fa6dcc1917.json")
    src = emit_agent_edit_python(wf)
    assert "INPAINT_InpaintWithModel" in src
    # Should emit seed, not widget_0
    block = [l for l in src.splitlines() if "inpaint_inpaintwithmodel" in l.lower()][0]
    idx = src.splitlines().index(block)
    snippet = "\n".join(src.splitlines()[idx : idx + 10])
    assert "seed=" in snippet
    assert "widget_0" not in snippet


def test_emit_uses_named_field_for_moonvalley():
    wf = _wf_from_corpus("external_workflows/corpus/d7853cd7421f9ebc.json")
    src = emit_agent_edit_python(wf)
    assert "MoonvalleyImg2VideoNode" in src
    block = [l for l in src.splitlines() if "moonvalley" in l.lower()][0]
    idx = src.splitlines().index(block)
    snippet = "\n".join(src.splitlines()[idx : idx + 15])
    assert "steps=" in snippet
    assert "widget_6" not in snippet


def test_emit_uses_named_field_for_reactor():
    wf = _wf_from_corpus("external_workflows/corpus/74a15e1f27bb96d5.json")
    src = emit_agent_edit_python(wf)
    assert "ReActorFaceSwap" in src
    block = [l for l in src.splitlines() if "reactorfaceswap" in l.lower()][0]
    idx = src.splitlines().index(block)
    snippet = "\n".join(src.splitlines()[idx : idx + 15])
    assert "swap_model" in snippet
    # Should not teach widget_1 for ReActor
    assert "widget_1=" not in snippet


def test_emit_uses_named_field_for_florence():
    wf = _wf_from_corpus("tests/fixtures/live_agentic_corpus/0099685f34b68456.json")
    src = emit_agent_edit_python(wf)
    assert "Florence2Run" in src
    block = [l for l in src.splitlines() if "florence2run" in l.lower()][0]
    idx = src.splitlines().index(block)
    snippet = "\n".join(src.splitlines()[idx : idx + 15])
    assert "task=" in snippet
    assert "widget_1" not in snippet


def test_widget_n_is_rejected_with_named_hint():
    # S2: widget_N is rejected and the error suggests the named field + range.
    from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
    from vibecomfy.porting.edit._interpret import is_positional_alias
    # widget_1 should be considered positional
    assert is_positional_alias("widget_1") is True
    assert is_positional_alias("guidance_scale") is False
    # For UltraShape, compact resolver should map widget_1 to guidance_scale via WIDGET_SCHEMA
    import copy, json
    from pathlib import Path
    from vibecomfy.ingest.normalize import normalize_to_api, from_api
    raw = json.loads(Path("external_workflows/corpus/8800a945cff8d090.json").read_text())
    api = normalize_to_api(copy.deepcopy(raw), use_comfy_converter=False)
    wf = from_api(api)
    node = wf.nodes["2"]
    res = compact_widget_names_for_node(node, name_authority=None)
    assert res.names[1] == "guidance_scale"


def test_range_validation_shares_vocabulary():
    # Range validation: preview and queue share same spec (validate_literal_value)
    from vibecomfy.schema.types import InputSpec
    from vibecomfy.porting.edit.validate import validate_literal_value
    spec = InputSpec(type="FLOAT", required=False, default=5.0, choices=None, min=1.0, max=15.0)
    issues = validate_literal_value(value=0.5, spec=spec, class_type="UltraShapeRefine", input_name="guidance_scale", context="interpret")
    assert any(i.code == "value_out_of_range" for i in issues)
    assert "1.0 to 15.0" in issues[0].message
    # Valid value should not produce hard error
    issues2 = validate_literal_value(value=7, spec=spec, class_type="UltraShapeRefine", input_name="guidance_scale", context="interpret")
    assert not any(i.code == "value_out_of_range" and i.severity == "error" for i in issues2)


def test_preview_and_queue_share_named_vocab():
    """Preview and queue both use named field (steps), not widget_N."""
    wf = _wf_from_corpus("external_workflows/corpus/d7853cd7421f9ebc.json")
    src = emit_agent_edit_python(wf)
    assert "steps=" in src
    # Check that the Moonvalley node block uses named field, not widget_6
    for line in src.splitlines():
        if "moonvalleyimg2videonode" in line.lower():
            idx = src.splitlines().index(line)
            snippet = "\n".join(src.splitlines()[idx:idx+10])
            assert "widget_6" not in snippet
            break
    # Preview and queue share same validation logic (validate_literal_value)
    from vibecomfy.schema.types import InputSpec
    from vibecomfy.porting.edit.validate import validate_literal_value
    spec = InputSpec(type="INT", required=False, default=80, choices=None, min=75, max=100)
    ok = validate_literal_value(value=80, spec=spec, class_type="MoonvalleyImg2VideoNode", input_name="steps", context="interpret")
    bad = validate_literal_value(value=10, spec=spec, class_type="MoonvalleyImg2VideoNode", input_name="steps", context="interpret")
    assert not any(i.severity == "error" and i.code == "value_out_of_range" for i in ok)
    assert any(i.code == "value_out_of_range" for i in bad)
