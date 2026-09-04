"""Regression tests proving the former shim generator is retired."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from vibecomfy.porting.wrappers import codegen
from vibecomfy.porting.wrappers.discovery import ClassSpec, InputFieldSpec


def test_canonical_generated_modules_are_public_and_discoverable() -> None:
    import vibecomfy.nodes as nodes
    from vibecomfy.nodes.core import KSampler, UNETLoader
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    assert callable(KSampler)
    assert callable(UNETLoader)
    assert "KSampler" in nodes.__all__
    assert "KSampler" in nodes.core.__all__ if hasattr(nodes, "core") else True
    assert nodes.core.__vibecomfy_class_types__["KSampler"] == "KSampler"
    wf = VibeWorkflow("test/shims", WorkflowSource("test/shims", path="ready_templates/test.py"))
    unet = UNETLoader(wf, unet_name="model.safetensors", weight_dtype="default")
    sampler = KSampler(wf, model=unet, sampler_name="euler", scheduler="simple", positive="p", negative="n", latent_image="latent")
    assert wf.nodes[unet.node.id].class_type == "UNETLoader"
    assert wf.nodes[sampler.node.id].class_type == "KSampler"
    assert any(edge.from_node == unet.node.id and edge.to_node == sampler.node.id and edge.to_input == "model" for edge in wf.edges)
    assert "Returns:" in (UNETLoader.__doc__ or "")


def test_every_canonical_module_has_matching_public_exports_and_no_old_abi() -> None:
    root = Path(__file__).resolve().parents[1] / "vibecomfy" / "nodes"
    for py_path in sorted(root.glob("*.py")):
        if py_path.name in {"__init__.py", "index.py"}:
            continue
        text = py_path.read_text(encoding="utf-8")
        assert text.startswith("# vibecomfy:generated"), py_path
        assert ".add(" not in text
        assert "_NodeBuilder" not in text
        assert "wf._node" not in text
        stub = py_path.with_suffix(".pyi")
        assert stub.is_file()
        assert stub.read_text(encoding="utf-8").startswith("# vibecomfy:generated")


def test_retired_generator_cannot_write_or_delegate() -> None:
    source = Path(__file__).resolve().parents[1] / "tools" / "generate_node_shims.py"
    text = source.read_text(encoding="utf-8")
    for forbidden in ("_write_module", "_write_stub_module", "_write_nodes_init", "_prune_stale_thin_shims", "GENERATED_HEADER"):
        assert forbidden not in text
    proc = subprocess.run([sys.executable, "-m", "tools.generate_node_shims"], text=True, capture_output=True)
    assert proc.returncode != 0
    assert "retired" in proc.stderr + proc.stdout


def test_codegen_prune_preserves_hand_authored_files(tmp_path: Path) -> None:
    generated = tmp_path / "old.py"
    generated.write_text(codegen.render_pack("old", [], out_dir=tmp_path).source_text, encoding="utf-8")
    hand_authored = tmp_path / "index.py"
    hand_authored.write_text("# hand authored\n", encoding="utf-8")
    codegen.prune_stale_wrappers(tmp_path, live_modules=("live",))
    assert not generated.exists()
    assert hand_authored.exists()


def test_codegen_retains_sanitized_input_collisions(tmp_path: Path) -> None:
    spec = ClassSpec(
        "demo", "Collision", {
            "a-b": InputFieldSpec("a-b", "INT", required=False),
            "a.b": InputFieldSpec("a.b", "INT", required=False),
            "_id": InputFieldSpec("_id", "STRING", required=False),
        }, ("OUT",), ("ANY",), source_provenance="test",
    )
    text = codegen.render_pack("demo", [spec], out_dir=tmp_path).source_text
    assert "a_b: int | _Omitted" in text
    assert "a_b_2: int | _Omitted" in text
    assert "_kwargs['a-b']" in text
    assert "_kwargs['a.b']" in text
