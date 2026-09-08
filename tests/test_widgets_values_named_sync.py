from __future__ import annotations

from copy import deepcopy

from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.widgets.aliases import synchronize_ui_widget_values


def _ui_graph(class_type: str, values, named):
    return {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": class_type,
                "pos": [0, 0],
                "size": [320, 100],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {},
                "widgets_values": values,
                "widgets_values_named": named,
            }
        ],
        "links": [],
        "groups": [],
        "config": {},
        "extra": {},
    }


def test_synchronizer_projects_positional_values_without_inventing_named_slots() -> None:
    payload = {
        "widgets_values": ["new-file", "auto"],
        "widgets_values_named": {"filename": "old-file", "format": "old"},
    }
    result = synchronize_ui_widget_values(
        payload,
        widget_names=["filename", "format", "unused"],
    )

    assert result["widgets_values"] == ["new-file", "auto"]
    assert result["widgets_values_named"] == {"filename": "new-file", "format": "auto"}


def test_vhs_dict_widgets_and_named_projection_stay_synchronized_after_edit() -> None:
    raw = _ui_graph(
        "VHS_VideoCombine",
        {"crf": 19, "filename_prefix": "old", "format": "video/h264-mp4"},
        {"crf": 19, "filename_prefix": "old", "format": "video/h264-mp4"},
    )
    wf = from_ui(deepcopy(raw), use_comfy_converter=False)
    wf.nodes["1"].inputs["filename_prefix"] = "new"

    emitted = emit_ui_json(wf)["nodes"][0]

    assert emitted["widgets_values"]["filename_prefix"] == "new"
    assert emitted["widgets_values_named"]["filename_prefix"] == "new"


def test_list_widgets_and_named_projection_stay_synchronized_after_edit() -> None:
    raw = _ui_graph("VAELoader", ["old.vae"], {"vae_name": "old.vae"})
    wf = from_ui(deepcopy(raw), use_comfy_converter=False)
    wf.nodes["1"].inputs["vae_name"] = "new.vae"

    emitted = emit_ui_json(wf)["nodes"][0]

    assert emitted["widgets_values"] == ["new.vae"]
    assert emitted["widgets_values_named"] == {"vae_name": "new.vae"}
