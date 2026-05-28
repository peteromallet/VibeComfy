from __future__ import annotations

import contextlib
import io
import inspect
from pathlib import Path

import tools.generate_node_shims as generate_node_shims
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def _workflow() -> VibeWorkflow:
    return VibeWorkflow("test/shims", WorkflowSource("test/shims", path="ready_templates/test.py"))


def test_generated_core_wrappers_are_importable_and_delegate() -> None:
    from vibecomfy.nodes.core import CLIPLoader, KSampler, UNETLoader

    wf = _workflow()
    unet = UNETLoader(wf, unet_name="model.safetensors", weight_dtype="default")
    sampler = KSampler(
        wf,
        model=unet,
        sampler_name="euler",
        scheduler="simple",
        positive="p",
        negative="n",
        latent_image="latent",
    )

    assert wf.nodes[unet.node.id].class_type == "UNETLoader"
    assert wf.nodes[sampler.node.id].class_type == "KSampler"
    assert any(edge.from_node == unet.node.id and edge.to_node == sampler.node.id and edge.to_input == "model" for edge in wf.edges)
    assert "Pack:" in (UNETLoader.__doc__ or "")
    assert "Returns:" in (UNETLoader.__doc__ or "")
    assert "type_" in inspect.signature(CLIPLoader).parameters


def test_generated_pack_modules_import_and_exclude_helper_nodes() -> None:
    import vibecomfy.nodes.controlnet_aux as controlnet_aux
    import vibecomfy.nodes.depthanythingv2 as depthanythingv2
    import vibecomfy.nodes.gguf as gguf
    import vibecomfy.nodes.kjnodes as kjnodes
    import vibecomfy.nodes.ltxvideo as ltxvideo
    import vibecomfy.nodes.qwen3tts as qwen3tts
    import vibecomfy.nodes.qwentts as qwentts
    import vibecomfy.nodes.rgthree as rgthree
    import vibecomfy.nodes.sam2 as sam2
    import vibecomfy.nodes.videohelpersuite as videohelpersuite
    import vibecomfy.nodes.wananimatepreprocess as wananimatepreprocess
    import vibecomfy.nodes.wanvideowrapper as wanvideowrapper
    from vibecomfy.nodes import UNETLoader

    assert UNETLoader.__name__ == "UNETLoader"
    for module in (
        controlnet_aux,
        depthanythingv2,
        gguf,
        kjnodes,
        ltxvideo,
        qwen3tts,
        qwentts,
        rgthree,
        sam2,
        videohelpersuite,
        wananimatepreprocess,
        wanvideowrapper,
    ):
        assert isinstance(module.__all__, list)
    assert "SetNode" not in kjnodes.__all__
    assert "GetNode" not in kjnodes.__all__
    assert "Note" not in kjnodes.__all__
    assert "MarkdownNote" not in kjnodes.__all__
    assert "Reroute" not in kjnodes.__all__
    assert "PrimitiveNode" not in kjnodes.__all__


def test_prune_stale_thin_shims_removes_only_generated_outputs(tmp_path: Path, monkeypatch) -> None:
    """Prove stale generated files are removed while live targets and hand-authored files survive.

    Scenarios covered:
    - Stale _generated/<mod>.py with thin-wrapper docstring marker → pruned
    - Stale _generated/<mod>.pyi with stub docstring marker → pruned
    - Stale nodes/<mod>.py with re-export structural content → pruned
    - Stale nodes/<mod>.pyi with re-export stub structural content → pruned
    - Live _generated/<mod>.py with marker, in target set → preserved
    - Live _generated/<mod>.pyi with stub marker, in target set → preserved
    - Live nodes/<mod>.py with structural content, in target set → preserved
    - Live nodes/<mod>.pyi with structural content, in target set → preserved
    - Hand-authored _generated file without marker → preserved
    - Hand-authored nodes file without marker → preserved
    - Rich-wrapper codegen output (not thin-shim) → preserved
    """
    generated_dir = tmp_path / "_generated"
    nodes_dir = tmp_path / "nodes"
    generated_dir.mkdir()
    nodes_dir.mkdir()

    monkeypatch.setattr(generate_node_shims, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_node_shims, "NODES_DIR", nodes_dir)

    keep_module = "core"
    stale_module = "stale_pack"
    hand_authored_module = "hand_authored"
    rich_wrapper_module = "comfyui_kjnodes"

    # --- Stale generated module (should be pruned) ---
    (generated_dir / f"{stale_module}.py").write_text(
        '"""Auto-generated thin wrappers for ComfyUI node classes.\n\nRegenerate via: python -m tools.generate_node_shims\n"""\n',
        encoding="utf-8",
    )
    (generated_dir / f"{stale_module}.pyi").write_text(
        '"""Type stubs for generated ComfyUI node wrappers."""\n',
        encoding="utf-8",
    )
    (nodes_dir / f"{stale_module}.py").write_text(
        "\n".join([
            f"from vibecomfy.nodes._generated import {stale_module} as _generated",
            f"from vibecomfy.nodes._generated.{stale_module} import *",
            "",
            "__all__ = list(_generated.__all__)",
            "",
        ]),
        encoding="utf-8",
    )
    (nodes_dir / f"{stale_module}.pyi").write_text(
        "\n".join([
            f"from vibecomfy.nodes._generated.{stale_module} import *",
            "",
            "__all__: list[str]",
            "",
        ]),
        encoding="utf-8",
    )

    # --- Live target module (should be preserved) ---
    (generated_dir / f"{keep_module}.py").write_text(
        '"""Auto-generated thin wrappers for ComfyUI node classes.\n\nRegenerate via: python -m tools.generate_node_shims\n"""\n',
        encoding="utf-8",
    )
    (generated_dir / f"{keep_module}.pyi").write_text(
        '"""Type stubs for generated ComfyUI node wrappers."""\n',
        encoding="utf-8",
    )
    (nodes_dir / f"{keep_module}.py").write_text(
        "\n".join([
            f"from vibecomfy.nodes._generated import {keep_module} as _generated",
            f"from vibecomfy.nodes._generated.{keep_module} import *",
            "",
            "__all__ = list(_generated.__all__)",
            "",
        ]),
        encoding="utf-8",
    )
    (nodes_dir / f"{keep_module}.pyi").write_text(
        "\n".join([
            f"from vibecomfy.nodes._generated.{keep_module} import *",
            "",
            "__all__: list[str]",
            "",
        ]),
        encoding="utf-8",
    )

    # --- Hand-authored files without markers (should be preserved) ---
    (generated_dir / f"{hand_authored_module}.py").write_text('print("keep me")\n', encoding="utf-8")
    (nodes_dir / f"{hand_authored_module}.py").write_text('print("also keep me")\n', encoding="utf-8")

    # --- Rich-wrapper codegen output (not a thin shim, should be preserved) ---
    (nodes_dir / f"{rich_wrapper_module}.py").write_text("# vibecomfy:generated rich wrapper\n", encoding="utf-8")

    generate_node_shims._prune_stale_thin_shims((keep_module,), [tmp_path / "ComfyUI-KJNodes@stub.json"])

    # Stale files removed
    assert not (generated_dir / f"{stale_module}.py").exists(), "stale _generated .py should be pruned"
    assert not (generated_dir / f"{stale_module}.pyi").exists(), "stale _generated .pyi should be pruned"
    assert not (nodes_dir / f"{stale_module}.py").exists(), "stale nodes re-export .py should be pruned"
    assert not (nodes_dir / f"{stale_module}.pyi").exists(), "stale nodes re-export .pyi should be pruned"

    # Live target preserved (including .pyi stubs)
    assert (generated_dir / f"{keep_module}.py").exists(), "live _generated .py should be preserved"
    assert (generated_dir / f"{keep_module}.pyi").exists(), "live _generated .pyi should be preserved"
    assert (nodes_dir / f"{keep_module}.py").exists(), "live nodes re-export .py should be preserved"
    assert (nodes_dir / f"{keep_module}.pyi").exists(), "live nodes re-export .pyi should be preserved"

    # Hand-authored files preserved
    assert (generated_dir / f"{hand_authored_module}.py").exists(), "hand-authored _generated file should be preserved"
    assert (nodes_dir / f"{hand_authored_module}.py").exists(), "hand-authored nodes file should be preserved"

    # Rich-wrapper preserved
    assert (nodes_dir / f"{rich_wrapper_module}.py").exists(), "rich-wrapper codegen output should be preserved"


def test_prune_stale_thin_shims_skips_when_cache_pack_files_missing(tmp_path: Path, monkeypatch) -> None:
    generated_dir = tmp_path / "_generated"
    nodes_dir = tmp_path / "nodes"
    generated_dir.mkdir()
    nodes_dir.mkdir()

    monkeypatch.setattr(generate_node_shims, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(generate_node_shims, "NODES_DIR", nodes_dir)

    stale_module = "stale_pack"
    stale_generated = generated_dir / f"{stale_module}.py"
    stale_generated.write_text(
        '"""Auto-generated thin wrappers for ComfyUI node classes.\n\nRegenerate via: python -m tools.generate_node_shims\n"""\n',
        encoding="utf-8",
    )

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        generate_node_shims._prune_stale_thin_shims(("core",), [])

    assert stale_generated.exists()
    assert "skipping thin-shim pruning" in stdout.getvalue()
