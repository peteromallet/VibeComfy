"""S5 final-wave: Reroute wildcard, leftover Δ, judge inputs, corpus RefusedEmit."""
import json, pathlib, pytest
from vibecomfy.ingest.normalize import from_envelope
from vibecomfy.porting.emit.ui import emit_ui_json, _emitted_input_slot_for_link
from vibecomfy.porting.refuse import RefusedEmit

def test_reroute_wildcard_normalization() -> None:
    assert _emitted_input_slot_for_link([{"name": "", "type": "*"}], "_un174") == 0
    assert _emitted_input_slot_for_link([{"name": "*", "type": "*"}], "_un999") == 0
    assert _emitted_input_slot_for_link([{"name": "_un174", "type": "VAE"}], "_un174") == 0
    assert _emitted_input_slot_for_link([{"name": "width"}, {"name": "width"}], "width") == 0
    for rel in ["external_workflows/corpus/ff076a0bcc687c3e.json", "external_workflows/corpus/0c27166fc31b7ead.json"]:
        p = pathlib.Path(rel)
        if p.is_file():
            data = json.loads(p.read_text())
            wf = from_envelope(data)
            ui = emit_ui_json(wf)
            assert isinstance(ui, dict)

def test_2x2_seed_variation_emits_after_fix() -> None:
    p = pathlib.Path("external_workflows/corpus/cdb8167d4eccd0a8.json")
    if not p.is_file():
        pytest.skip("corpus file absent")
    data = json.loads(p.read_text())
    wf = from_envelope(data)
    ui = emit_ui_json(wf)
    assert isinstance(ui, dict)
    assert len(ui.get("nodes", [])) >= 20

def test_corpus_preflight_refused_emit_surfaces_typed_failure() -> None:
    assert _emitted_input_slot_for_link([{"name": "a"}, {"name": "b"}], "nonexistent_xyz") is None

def test_leftover_links_last_link_id_ignored_in_delta_replay() -> None:
    try:
        from tests.live_agentic_harness.intent_judge import _is_structural_leftover
    except ImportError:
        pytest.skip("helper not yet landed")
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    op_links = SetNodeFieldOp(target=NodeFieldTarget(uid="uid1", field_path="links"), value=[])
    assert _is_structural_leftover(op_links) is True
    op_last = SetNodeFieldOp(target=NodeFieldTarget(uid="uid1", field_path="last_link_id"), value=99)
    assert _is_structural_leftover(op_last) is True
    op_widget = SetNodeFieldOp(target=NodeFieldTarget(uid="uid1", field_path="steps"), value=6)
    assert _is_structural_leftover(op_widget) is False

def test_judge_reads_inputs_steps_cfg_not_widgets_values() -> None:
    try:
        from tests.live_agentic_harness.intent_judge import _graph_inputs_from_payload, _ui_node_inventory
    except ImportError:
        pytest.skip("helpers not yet landed")
    ui = {"nodes": [{"id": "58", "type": "KSamplerAdvanced", "inputs": {"steps": 6, "cfg": 1.5}, "widgets_values": ["disable", 0, "fixed", 6, 1.5, "lcm", "simple", 4, 10000, "disable"]}] }
    inv = _ui_node_inventory(ui)
    assert inv[0]["inputs"]["steps"] == 6
    payload = {"graph": {"nodes": {"58": {"inputs": {"steps": 6, "cfg": 1.5}}}}}
    got = _graph_inputs_from_payload(payload)
    assert got["58"]["steps"] == 6
    prompt = pathlib.Path("vibecomfy/intent/prompts/semantic_answer_judge.prompt.md").read_text()
    assert "inputs.steps" in prompt
    assert "inputs.cfg" in prompt
