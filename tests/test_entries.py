from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._cli_helpers import _write_port_node_index, _write_port_workflow
from vibecomfy.cli import build_parser
from vibecomfy.entries import discover_entries, draft_entry, import_as_entry, load_entry
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
from vibecomfy.porting.emit.emit_ready import _infer_public_input_bindings


def test_import_entry_and_cli(tmp_path, monkeypatch, capsys):
    _write_port_node_index(tmp_path)
    source = _write_port_workflow(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_ENTRIES_DIR", str(tmp_path / "entries"))
    args = build_parser().parse_args(["import", str(source), "--as-entry", "my-style", "--json"])
    assert args.func(args) == 0
    entry = json.loads(capsys.readouterr().out)["entry"]
    assert entry["id"] == "my-style"
    assert entry["kind"] == "image" and entry["modes"] == ["edit"]
    assert entry["binds"]["image"] == "image"
    assert Path(entry["bundle"], "source.json").read_bytes() == source.read_bytes()
    assert discover_entries() == [entry]
    with pytest.raises(FileExistsError):
        import_as_entry(source, "my-style")


def test_manifest_validation_and_relative_bundle(tmp_path):
    path = tmp_path / "entry.json"
    manifest = {"id": "a", "kind": "image", "modes": ["t2i"], "bundle": "bundle", "needs": [], "binds": {"prompt": "prompt", "width": {"node": "1", "field": "width"}}, "defaults": {}}
    path.write_text(json.dumps(manifest))
    assert load_entry(path)["bundle"] == str(tmp_path / "bundle")
    for kind, modes in {"image": ["t2i", "i2i", "edit", "inpaint", "outpaint", "upscale"], "video": ["t2v", "i2v", "flf", "v2v", "video-edit"], "audio": ["tts", "music", "sfx"]}.items():
        path.write_text(json.dumps({**manifest, "kind": kind, "modes": modes}))
        assert load_entry(path)["modes"] == modes
    for change in ({"id": "../bad"}, {"modes": ["t2v"]}, {"binds": {"prompt": {"node": "1"}}}, {"needs": {}}, {"kind": "unknown"}):
        path.write_text(json.dumps({**manifest, **change}))
        with pytest.raises(ValueError):
            load_entry(path)


def test_output_ambiguity_and_loader_roles():
    wf = VibeWorkflow("a", WorkflowSource("a"))
    wf.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "model.safetensors"})
    wf.nodes["2"] = VibeNode("2", "CustomMysteryLoader", inputs={"model_name": "x.safetensors"})
    wf.nodes["3"] = VibeNode("3", "SaveImage")
    entry = draft_entry(wf, "a")
    assert entry["needs"][0]["role"] == "diffusion_model"
    assert entry["needs"][1]["role"] is None
    assert entry["needs"][1]["ambiguity"] == "unknown loader role"
    wf.nodes["4"] = VibeNode("4", "SaveAudio")
    with pytest.raises(ValueError, match="ambiguous"):
        draft_entry(wf, "a")
    wf.nodes.pop("3")
    wf.nodes["5"] = VibeNode("5", "PreviewImage")
    audio = draft_entry(wf, "a")
    assert audio["kind"] == "audio" and audio["modes"] == []
    assert "audio mode is unknown" in audio["needs"][0]["ambiguity"]


def test_loader_roles_follow_model_fields():
    wf = VibeWorkflow("a", WorkflowSource("a"))
    wf.nodes["1"] = VibeNode("1", "DualCLIPLoader", inputs={"clip_name1": "one.safetensors", "clip_name2": "two.safetensors"})
    wf.nodes["2"] = VibeNode("2", "CLIPVisionLoader", inputs={"clip_name": "vision.safetensors"})
    wf.nodes["3"] = VibeNode("3", "LatentUpscaleModelLoader", inputs={"model_name": "upscale.pth"})
    wf.nodes["4"] = VibeNode("4", "SaveVideo")
    wf.nodes["5"] = VibeNode("5", "PreviewImage")
    entry = draft_entry(wf, "a")
    assert entry["kind"] == "video"
    assert [(need["field"], need["role"]) for need in entry["needs"]] == [
        ("clip_name1", "text_encoder"), ("clip_name2", "text_encoder"),
        ("clip_name", "vision_encoder"), ("model_name", "upscaler"),
    ]


def test_inference_preserves_controls_and_connected_negative():
    nodes = {
        "1": VibeNode("1", "CLIPTextEncode", inputs={"text": "good"}),
        "2": VibeNode("2", "CLIPTextEncode", inputs={"text": ""}),
        "3": VibeNode("3", "KSampler", inputs={"seed": 7}, metadata={"schema_source": {"confidence": 1}}),
        "4": VibeNode("4", "EmptyLatentImage", inputs={"width": 640, "height": 480, "length": 25}),
        "5": VibeNode("5", "LoadImage", inputs={"image": "input.png"}),
        "6": VibeNode("6", "VHS_VideoCombine", inputs={"frame_rate": 24}),
    }
    edges = {"3": [VibeEdge("1", "0", "3", "positive"), VibeEdge("2", "0", "3", "negative")]}
    bindings = {item.name: (item.node_id, item.field) for item in _infer_public_input_bindings(nodes, edges, connected_prompt_roles=True)}
    assert bindings == {"prompt": ("1", "text"), "negative_prompt": ("2", "text"), "seed": ("3", "seed"), "width": ("4", "width"), "height": ("4", "height"), "frames": ("4", "length"), "image": ("5", "image"), "fps": ("6", "frame_rate")}


@pytest.mark.parametrize("class_type,field,name", [
    ("LoadVideo", "file", "video"), ("VHS_LoadVideo", "video", "video"),
    ("VHS_LoadVideoFFmpeg", "video", "video"), ("LoadAudio", "audio", "audio"),
])
def test_media_loader_bindings(class_type, field, name):
    node = VibeNode("1", class_type, inputs={field: "input.file"})
    binding = _infer_public_input_bindings({"1": node}, {})[0]
    assert (binding.name, binding.field, binding.media_semantics) == (name, field, name)


def test_ambiguous_input_is_reported_and_not_bound(tmp_path, monkeypatch):
    _write_port_node_index(tmp_path)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "ambiguous.json"
    source.write_text(json.dumps({
        "1": {"class_type": "LoadImage", "inputs": {"image": "first.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "second.png"}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "out"}},
    }))
    entry = import_as_entry(source, "ambiguous", tmp_path / "entries")
    assert "image" not in entry["binds"]
    assert entry["modes"] == ["edit"]
    ambiguity = next(n for n in entry["needs"] if n.get("ambiguity") == "multiple targets for image")
    assert ambiguity["candidates"] == [{"node": "1", "field": "image"}, {"node": "2", "field": "image"}]


def test_ambiguous_prompt_is_not_emitted_as_public_input(tmp_path):
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import load_bundle

    source = tmp_path / "ambiguous.json"
    source.write_text(json.dumps({
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "one"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "two"}},
        "3": {"class_type": "SaveImage", "inputs": {"filename_prefix": "out"}},
    }))
    entry = import_as_entry(source, "ambiguous", tmp_path / "entries")
    assert "prompt" not in entry["binds"]
    wf = load_bundle(Path(entry["bundle"]) / "workflow.py", trust=Provenance.USER_CONFIRMED).workflow
    assert "prompt" not in wf.inputs


def test_existing_canonical_bundle_can_be_imported_as_entry(tmp_path, monkeypatch):
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import load_bundle

    _write_port_node_index(tmp_path)
    monkeypatch.chdir(tmp_path)
    source = _write_port_workflow(tmp_path)
    original = import_as_entry(source, "original", tmp_path / "entries")
    entry = import_as_entry(original["bundle"], "existing", tmp_path / "entries")
    assert entry["kind"] == "image"
    restored = load_bundle(Path(entry["bundle"]) / "workflow.py", trust=Provenance.USER_CONFIRMED)
    assert any(node.class_type == "SaveImage" for node in restored.workflow.nodes.values())


def test_import_retains_dimension_frame_and_fps_inputs(tmp_path):
    from vibecomfy.porting.import_service import import_workflow_bytes
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import load_bundle

    raw = {
        "1": {"class_type": "EmptyLatentImage", "inputs": {"width": 640, "height": 480, "batch_size": 1}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
        "3": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["2", 0], "frame_rate": 24, "loop_count": 0, "filename_prefix": "out", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    artifacts = import_workflow_bytes(json.dumps(raw).encode(), workflow_id="controls", infer_inputs=True)
    folder = tmp_path / "bundle"
    folder.mkdir()
    (folder / "workflow.py").write_bytes(artifacts.python_bytes)
    (folder / "workflow.vibe.json").write_bytes(artifacts.companion_bytes)
    (folder / "source.json").write_bytes(artifacts.source_bytes)
    wf = load_bundle(folder / "workflow.py", trust=Provenance.USER_CONFIRMED).workflow
    for name in ("width", "height", "image", "fps"):
        assert name in wf.inputs
    wf.set_input("width", 768)
    wf.set_input("height", 512)
    wf.set_input("image", "other.png")
    wf.set_input("fps", 12)
    assert wf.nodes[wf.inputs["fps"].node_id].inputs["frame_rate"] == 12
