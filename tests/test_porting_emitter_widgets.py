from __future__ import annotations

from vibecomfy.porting.emit import emitter
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_ui_widget_values_by_name_ksampler_skips_ui_only_rows_without_shifting() -> None:
    ui_node = {
        "type": "KSampler",
        "widgets_values": [123456789, "randomize", 30, 6.5, "euler", "normal", 1],
        "properties": {
            "proxyWidgets": [
                [0, "seed"],
                [1, "control_after_generate"],
                [2, "steps"],
                [3, "cfg"],
                [4, "sampler_name"],
                [5, "scheduler"],
                [6, "denoise"],
            ]
        },
        "inputs": [
            {"name": "latent_image", "link": 7},
            {"name": "model", "link": 8},
            {"name": "positive", "link": 9},
            {"name": "negative", "link": 10},
            {"name": "", "widget": {"name": ""}},
            {"name": "control_after_generate", "widget": {"name": "control_after_generate"}},
            {"name": "steps", "widget": {"name": "steps"}},
            {"name": "cfg", "widget": {"name": "cfg"}},
        ],
    }

    values = emitter._ui_widget_values_by_name(ui_node)

    assert values["seed"] == 123456789
    assert values["control_after_generate"] == "randomize"
    assert values["steps"] == 30
    assert values["cfg"] == 6.5


def test_talking_avatar_widget_mapping_and_default_lookup_use_named_fields(
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        emitter.WIDGET_SCHEMA,
        "TalkingAvatarSampler",
        [None, "voice", "unload_models", "seed"],
    )
    ui_node = {
        "type": "TalkingAvatarSampler",
        "widgets_values": ["ui-only", 986337553816914, "randomize", 116899311982882],
        "input_aliases": [None, "voice", "unload_models", "seed"],
        "properties": {
            "proxyWidgets": [
                [1, "voice"],
                [2, "unload_models"],
                [3, "seed"],
            ]
        },
        "inputs": [
            {"name": "audio", "link": 11},
            {"name": "image", "link": 12},
            {"name": "", "widget": {"name": ""}},
            {"name": "voice", "widget": {"name": "voice"}},
            {"name": "unload_models", "widget": {"name": "unload_models"}},
            {"name": "seed", "widget": {"name": "seed"}},
        ],
    }

    values = emitter._ui_widget_values_by_name(ui_node)

    assert values["voice"] == 986337553816914
    assert values["unload_models"] == "randomize"
    assert values["seed"] == 116899311982882
    assert emitter._widget_default_for_target(ui_node, 3) == 986337553816914
    assert emitter._widget_default_for_target(ui_node, 4) == "randomize"
    assert emitter._widget_default_for_target(ui_node, 5) == 116899311982882


def test_node_kwargs_does_not_shift_widget_aliases_past_blank_slots(
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        emitter.WIDGET_SCHEMA,
        "TalkingAvatarSampler",
        [None, "voice", "unload_models", "seed"],
    )
    node = VibeNode("1", "TalkingAvatarSampler")
    node.metadata["_ui"] = {
        "inputs": [
            {"name": "", "widget": {"name": ""}},
            {"name": "voice", "widget": {"name": "voice"}},
            {"name": "unload_models", "widget": {"name": "unload_models"}},
            {"name": "seed", "widget": {"name": "seed"}},
        ]
    }
    node.widgets.update(
        {
            "widget_1": 986337553816914,
            "widget_2": "randomize",
            "widget_3": 116899311982882,
        }
    )

    kwargs = emitter._node_kwargs(
        node,
        edges_in={},
        var_names={},
        use_ui_widget_aliases=True,
    )

    assert ("voice", "986337553816914") in kwargs
    assert ("unload_models", "'randomize'") in kwargs
    assert ("seed", "116899311982882") in kwargs
    assert not any(key == "widget_1" for key, _ in kwargs)


def test_public_input_specs_do_not_create_bogus_blank_alias_inputs(
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        emitter.WIDGET_SCHEMA,
        "TalkingAvatarSampler",
        [None, "voice", "unload_models", "seed"],
    )
    workflow = VibeWorkflow("test/widgets", WorkflowSource("test/widgets"))
    sampler = VibeNode("1", "TalkingAvatarSampler")
    sampler.metadata["_ui"] = {
        "inputs": [
            {"name": "", "widget": {"name": ""}},
            {"name": "voice", "widget": {"name": "voice"}},
            {"name": "unload_models", "widget": {"name": "unload_models"}},
            {"name": "seed", "widget": {"name": "seed"}},
        ]
    }
    sampler.widgets.update(
        {
            "widget_1": 986337553816914,
            "widget_2": "randomize",
            "widget_3": 116899311982882,
        }
    )
    workflow.nodes["1"] = sampler
    workflow.nodes["2"] = VibeNode("2", "SaveImage")
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))

    specs = emitter._public_input_specs(
        workflow.nodes,
        {"2": [VibeEdge("1", "0", "2", "images")]},
        {"1": "sampler", "2": "save_image"},
        {},
        registered_inputs={"voice": ("1", "widget_1")},
        constant_map={},
    )

    spec_by_name = {spec.name: spec for spec in specs}
    assert spec_by_name["voice"].field == "voice"
    assert spec_by_name["seed"].field == "seed"
    assert "widget_1" not in spec_by_name
    assert "" not in spec_by_name
