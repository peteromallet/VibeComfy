from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise.classify import (
    REASON_BRANCH_PIPELINE_TERMINAL,
    REASON_CLASS_NAME_LOADER,
    REASON_CLASS_NAME_OUTPUT,
    REASON_CLASS_NAME_SAMPLER,
    REASON_CLASS_NAME_UTILITY,
    REASON_EQUIVALENT_SINGLE_NODE_SIBLING_PAIR,
    REASON_HELPER_NODE,
    REASON_SIMPLE_LATENT_SOURCE_TO_SAMPLING,
    REASON_UI_NODE,
    REASON_UNKNOWN_UNASSIGNED,
    REASON_VAE_DECODE_TO_OUTPUT_FOLD,
    classify_layout_facts,
    classify_layout_from_ui,
)
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.plan_types import (
    LAYOUT_BEHAVIOR_NOTE,
    LAYOUT_BEHAVIOR_PRIMARY,
    LAYOUT_BEHAVIOR_SIDECAR,
    LAYOUT_BEHAVIOR_UNKNOWN,
    LAYOUT_BEHAVIOR_WALL,
    LAYOUT_BEHAVIORS,
    ROLE_HINT_CONDITIONING,
    ROLE_HINT_DECODE,
    ROLE_HINT_HELPER,
    ROLE_HINT_LOADER,
    ROLE_HINT_OUTPUT,
    ROLE_HINT_SAMPLER,
    ROLE_HINT_UI,
    ROLE_HINT_UNKNOWN,
    ROLE_HINT_UTILITY,
)


def _node(
    node_id: int,
    class_type: str,
    uid: str,
    *,
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
    widgets_values: list[str] | None = None,
) -> dict:
    node = {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "properties": {"vibecomfy_uid": uid},
    }
    if inputs is not None:
        node["inputs"] = inputs
    if outputs is not None:
        node["outputs"] = outputs
    if widgets_values is not None:
        node["widgets_values"] = widgets_values
    return node


def _hints_by_uid(ui: dict):
    facts = extract_graph_facts(ui)
    report = classify_layout_facts(facts)
    return {hint.ref.uid: hint for hint in report.hints}


def test_classification_folds_immediate_vae_decode_to_output() -> None:
    ui = {
        "nodes": [
            _node(
                1,
                "KSampler",
                "sample",
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [10]}],
            ),
            _node(
                2,
                "VAEDecode",
                "decode",
                inputs=[{"name": "samples", "type": "LATENT", "link": 10}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            ),
            _node(
                3,
                "SaveImage",
                "save",
                inputs=[{"name": "images", "type": "IMAGE", "link": 11}],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "LATENT"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
    }

    hints = _hints_by_uid(ui)

    assert hints["decode"].role_hint == ROLE_HINT_OUTPUT
    assert hints["decode"].confidence == 0.88
    assert hints["decode"].reason_codes == (REASON_VAE_DECODE_TO_OUTPUT_FOLD,)
    assert hints["save"].role_hint == ROLE_HINT_OUTPUT


def test_classification_folds_simple_latent_source_to_sampling() -> None:
    ui = {
        "nodes": [
            _node(
                1,
                "EmptyLatentImage",
                "latent-source",
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [10]}],
            ),
            _node(
                2,
                "KSampler",
                "sample",
                inputs=[{"name": "latent_image", "type": "LATENT", "link": 10}],
            ),
        ],
        "links": [[10, 1, 0, 2, 0, "LATENT"]],
    }

    hints = _hints_by_uid(ui)

    assert hints["latent-source"].role_hint == ROLE_HINT_SAMPLER
    assert hints["latent-source"].reason_codes == (REASON_SIMPLE_LATENT_SOURCE_TO_SAMPLING,)


def test_classification_pairs_equivalent_single_node_siblings() -> None:
    ui = {
        "nodes": [
            _node(
                1,
                "CLIPLoader",
                "clip",
                outputs=[{"name": "CLIP", "type": "CLIP", "links": [10, 11]}],
            ),
            _node(
                2,
                "CLIPTextEncode",
                "positive",
                inputs=[{"name": "clip", "type": "CLIP", "link": 10}],
                outputs=[{"name": "CONDITIONING", "type": "CONDITIONING", "links": [12]}],
            ),
            _node(
                3,
                "CLIPTextEncode",
                "negative",
                inputs=[{"name": "clip", "type": "CLIP", "link": 11}],
                outputs=[{"name": "CONDITIONING", "type": "CONDITIONING", "links": [13]}],
            ),
            _node(
                4,
                "KSampler",
                "sample",
                inputs=[
                    {"name": "positive", "type": "CONDITIONING", "link": 12},
                    {"name": "negative", "type": "CONDITIONING", "link": 13},
                ],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "CLIP"],
            [11, 1, 0, 3, 0, "CLIP"],
            [12, 2, 0, 4, 1, "CONDITIONING"],
            [13, 3, 0, 4, 2, "CONDITIONING"],
        ],
    }

    hints = _hints_by_uid(ui)

    assert hints["positive"].role_hint == ROLE_HINT_CONDITIONING
    assert hints["negative"].role_hint == ROLE_HINT_CONDITIONING
    assert REASON_EQUIVALENT_SINGLE_NODE_SIBLING_PAIR in hints["positive"].reason_codes
    assert [ref.uid for ref in hints["positive"].related_refs] == ["negative"]
    assert [ref.uid for ref in hints["negative"].related_refs] == ["positive"]


def test_classification_keeps_branch_pipeline_decode_and_output_terminals_separate() -> None:
    ui = {
        "nodes": [
            _node(
                1,
                "KSampler",
                "sample",
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [10, 12]}],
            ),
            _node(
                2,
                "VAEDecode",
                "decode-a",
                inputs=[{"name": "samples", "type": "LATENT", "link": 10}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            ),
            _node(
                3,
                "SaveImage",
                "save-a",
                inputs=[{"name": "images", "type": "IMAGE", "link": 11}],
            ),
            _node(
                4,
                "VAEDecode",
                "decode-b",
                inputs=[{"name": "samples", "type": "LATENT", "link": 12}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [13]}],
            ),
            _node(
                5,
                "PreviewImage",
                "preview-b",
                inputs=[{"name": "images", "type": "IMAGE", "link": 13}],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "LATENT"],
            [11, 2, 0, 3, 0, "IMAGE"],
            [12, 1, 0, 4, 0, "LATENT"],
            [13, 4, 0, 5, 0, "IMAGE"],
        ],
    }

    hints = _hints_by_uid(ui)

    assert hints["decode-a"].role_hint == ROLE_HINT_DECODE
    assert hints["decode-b"].role_hint == ROLE_HINT_DECODE
    assert REASON_BRANCH_PIPELINE_TERMINAL in hints["decode-a"].reason_codes
    assert REASON_VAE_DECODE_TO_OUTPUT_FOLD not in hints["decode-a"].reason_codes
    assert hints["save-a"].role_hint == ROLE_HINT_OUTPUT
    assert REASON_BRANCH_PIPELINE_TERMINAL in hints["preview-b"].reason_codes


def test_classification_handles_helper_heavy_fixtures_without_mutating_inputs_or_facts() -> None:
    ui = {
        "nodes": [
            _node(
                1,
                "LoadImage",
                "load",
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            ),
            _node(
                2,
                "SetNode",
                "set-image",
                inputs=[{"name": "IMAGE", "type": "IMAGE", "link": 10}],
                widgets_values=["image-channel"],
            ),
            _node(
                3,
                "GetNode",
                "get-image",
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
                widgets_values=["image-channel"],
            ),
            _node(
                4,
                "Reroute",
                "reroute",
                inputs=[{"name": "", "type": "*", "link": 11}],
                outputs=[{"name": "", "type": "*", "links": [12]}],
            ),
            _node(
                5,
                "PreviewImage",
                "preview",
                inputs=[{"name": "images", "type": "IMAGE", "link": 12}],
            ),
            _node(6, "Note", "note"),
            _node(7, "MarkdownNote", "markdown"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 3, 0, 4, 0, "IMAGE"],
            [12, 4, 0, 5, 0, "IMAGE"],
        ],
    }
    before = deepcopy(ui)
    facts = extract_graph_facts(ui)
    facts_before = deepcopy(facts.to_json())

    report = classify_layout_from_ui(ui)
    report_from_facts = classify_layout_facts(facts)

    assert ui == before
    assert facts.to_json() == facts_before
    hints = {hint.ref.uid: hint for hint in report.hints}
    assert hints["set-image"].role_hint == ROLE_HINT_HELPER
    assert hints["set-image"].reason_codes == (REASON_HELPER_NODE,)
    assert hints["get-image"].role_hint == ROLE_HINT_HELPER
    assert hints["reroute"].role_hint == ROLE_HINT_HELPER
    assert hints["note"].role_hint == ROLE_HINT_UI
    assert hints["note"].reason_codes == (REASON_UI_NODE,)
    assert hints["markdown"].role_hint == ROLE_HINT_UI
    assert report.to_json() == report_from_facts.to_json()


# ---------------------------------------------------------------------------
# LayoutBehavior coverage for individual node classes
# ---------------------------------------------------------------------------


def test_layout_behavior_set_node_is_sidecar() -> None:
    """SetNode is helper → sidecar layout behavior."""
    ui = {
        "nodes": [
            _node(
                1,
                "LoadImage",
                "load",
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            ),
            _node(
                2,
                "SetNode",
                "set-image",
                inputs=[{"name": "IMAGE", "type": "IMAGE", "link": 10}],
                widgets_values=["colors"],
            ),
        ],
        "links": [[10, 1, 0, 2, 0, "IMAGE"]],
    }
    hints = _hints_by_uid(ui)
    assert hints["set-image"].role_hint == ROLE_HINT_HELPER
    assert hints["set-image"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR
    assert hints["set-image"].reason_codes == (REASON_HELPER_NODE,)


def test_layout_behavior_get_node_is_sidecar() -> None:
    """GetNode is helper → sidecar layout behavior."""
    ui = {
        "nodes": [
            _node(
                1,
                "GetNode",
                "get-data",
                outputs=[{"name": "DATA", "type": "DATA", "links": [10]}],
                widgets_values=["shared-key"],
            ),
            _node(
                2,
                "KSampler",
                "sample",
                inputs=[{"name": "latent_image", "type": "LATENT", "link": 10}],
            ),
        ],
        "links": [[10, 1, 0, 2, 0, "DATA"]],
    }
    hints = _hints_by_uid(ui)
    assert hints["get-data"].role_hint == ROLE_HINT_HELPER
    assert hints["get-data"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR
    assert hints["get-data"].reason_codes == (REASON_HELPER_NODE,)


def test_layout_behavior_note_nodes_are_note() -> None:
    """Note and MarkdownNote are UI helpers → note layout behavior."""
    ui = {
        "nodes": [
            _node(1, "Note", "note-a"),
            _node(2, "MarkdownNote", "markdown-b"),
        ],
        "links": [],
    }
    hints = _hints_by_uid(ui)
    assert hints["note-a"].role_hint == ROLE_HINT_UI
    assert hints["note-a"].layout_behavior == LAYOUT_BEHAVIOR_NOTE
    assert hints["note-a"].reason_codes == (REASON_UI_NODE,)
    assert hints["markdown-b"].role_hint == ROLE_HINT_UI
    assert hints["markdown-b"].layout_behavior == LAYOUT_BEHAVIOR_NOTE
    assert hints["markdown-b"].reason_codes == (REASON_UI_NODE,)


def test_classification_resource_loader_is_primary() -> None:
    """Resource loaders (CheckpointLoader, CLIPLoader, etc.) → primary layout behavior."""
    ui = {
        "nodes": [
            _node(
                1,
                "CheckpointLoaderSimple",
                "ckpt",
                outputs=[{"name": "MODEL", "type": "MODEL", "links": [10]}],
            ),
            _node(
                2,
                "KSampler",
                "sample",
                inputs=[{"name": "model", "type": "MODEL", "link": 10}],
            ),
        ],
        "links": [[10, 1, 0, 2, 0, "MODEL"]],
    }
    hints = _hints_by_uid(ui)
    assert hints["ckpt"].role_hint == ROLE_HINT_LOADER
    assert hints["ckpt"].layout_behavior == LAYOUT_BEHAVIOR_PRIMARY
    assert REASON_CLASS_NAME_LOADER in hints["ckpt"].reason_codes
    assert hints["sample"].role_hint == ROLE_HINT_SAMPLER
    assert hints["sample"].layout_behavior == LAYOUT_BEHAVIOR_PRIMARY
    assert REASON_CLASS_NAME_SAMPLER in hints["sample"].reason_codes


def test_classification_output_node_is_wall() -> None:
    """SaveImage and PreviewImage → output role, wall layout behavior."""
    ui = {
        "nodes": [
            _node(
                1,
                "KSampler",
                "sample",
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10, 11]}],
            ),
            _node(
                2,
                "SaveImage",
                "save",
                inputs=[{"name": "images", "type": "IMAGE", "link": 10}],
            ),
            _node(
                3,
                "PreviewImage",
                "preview",
                inputs=[{"name": "images", "type": "IMAGE", "link": 11}],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 1, 0, 3, 0, "IMAGE"],
        ],
    }
    hints = _hints_by_uid(ui)
    assert hints["save"].role_hint == ROLE_HINT_OUTPUT
    assert hints["save"].layout_behavior == LAYOUT_BEHAVIOR_WALL
    assert REASON_CLASS_NAME_OUTPUT in hints["save"].reason_codes
    assert hints["preview"].role_hint == ROLE_HINT_OUTPUT
    assert hints["preview"].layout_behavior == LAYOUT_BEHAVIOR_WALL
    assert REASON_CLASS_NAME_OUTPUT in hints["preview"].reason_codes


def test_classification_utility_primitive_is_primary() -> None:
    """Utility-like nodes (e.g. Primitive) → utility role, primary layout behavior."""
    ui = {
        "nodes": [
            _node(1, "PrimitiveNode", "primitive", widgets_values=["42"]),
        ],
        "links": [],
    }
    hints = _hints_by_uid(ui)
    assert hints["primitive"].role_hint == ROLE_HINT_UTILITY
    assert hints["primitive"].layout_behavior == LAYOUT_BEHAVIOR_PRIMARY
    assert REASON_CLASS_NAME_UTILITY in hints["primitive"].reason_codes


def test_classification_unknown_node_fallback() -> None:
    """Truly unknown class_type → unknown role, unknown layout behavior with fallback reason."""
    ui = {
        "nodes": [
            _node(1, "TotallyUnknownCustomNode", "unk"),
        ],
        "links": [],
    }
    hints = _hints_by_uid(ui)
    assert hints["unk"].role_hint == ROLE_HINT_UNKNOWN
    assert hints["unk"].layout_behavior == LAYOUT_BEHAVIOR_UNKNOWN
    assert hints["unk"].confidence == 0.2
    assert hints["unk"].reason_codes == (REASON_UNKNOWN_UNASSIGNED,)


def test_classification_unknown_class_type_inspection_picks_wall() -> None:
    """Unknown class_type with 'preview' substring → wall layout behavior via fallback.

    'preview' substring triggers _is_output_class which catches via
    lower.startswith('preview') in _class_name_role, but custom class names
    like 'MyPreviewHelper' that don't start with 'preview' fall through to
    UNKNOWN and then get WALL via fallback inspection.
    """
    ui = {
        "nodes": [
            _node(1, "MyPreviewHelper", "preview-helper"),
        ],
        "links": [],
    }
    hints = _hints_by_uid(ui)
    assert hints["preview-helper"].role_hint == ROLE_HINT_UNKNOWN
    assert hints["preview-helper"].layout_behavior == LAYOUT_BEHAVIOR_WALL


def test_classification_unknown_class_type_inspection_picks_sidecar() -> None:
    """Unknown class_type containing 'GetNode' substring → sidecar layout behavior."""
    ui = {
        "nodes": [
            _node(1, "CustomGetNodeWrapper", "get-wrap"),
        ],
        "links": [],
    }
    hints = _hints_by_uid(ui)
    assert hints["get-wrap"].role_hint == ROLE_HINT_UNKNOWN
    assert hints["get-wrap"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR


def test_classification_reroute_node_is_helper_sidecar() -> None:
    """Reroute is a helper → sidecar layout behavior."""
    ui = {
        "nodes": [
            _node(
                1,
                "LoadImage",
                "load",
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            ),
            _node(
                2,
                "Reroute",
                "reroute",
                inputs=[{"name": "", "type": "*", "link": 10}],
                outputs=[{"name": "", "type": "*", "links": [11]}],
            ),
            _node(
                3,
                "PreviewImage",
                "preview",
                inputs=[{"name": "images", "type": "IMAGE", "link": 11}],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
    }
    hints = _hints_by_uid(ui)
    assert hints["reroute"].role_hint == ROLE_HINT_HELPER
    assert hints["reroute"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR
    assert hints["reroute"].reason_codes == (REASON_HELPER_NODE,)


def test_classification_to_json_includes_layout_behavior() -> None:
    """Classification report JSON serialization includes layout_behavior field."""
    ui = {
        "nodes": [
            _node(1, "KSampler", "sample"),
            _node(2, "SaveImage", "save"),
        ],
        "links": [],
    }
    report = classify_layout_from_ui(ui)
    json_payload = report.to_json()
    assert "hints" in json_payload
    for hint_json in json_payload["hints"]:
        assert "layout_behavior" in hint_json
        assert hint_json["layout_behavior"] in LAYOUT_BEHAVIORS
