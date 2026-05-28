from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.registry import models_loader
from vibecomfy.registry.models_loader import (
    DOCUMENTED_NODE_PACK_GAPS,
    ModelTarget,
    canonical_model_node_pack,
    load_registry,
)


def _write_registry(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    models_loader._clear_cache()
    return path


def test_canonical_model_node_pack_handles_aliases_and_gaps() -> None:
    assert canonical_model_node_pack("ComfyUI-GGUF") == "ComfyUI-GGUF"
    assert canonical_model_node_pack("ComfyUI-LTXVideo") == "ComfyUI-LTXVideo"
    assert canonical_model_node_pack("ComfyUI-WanVideoWrapper") == "ComfyUI-WanVideoWrapper"
    assert canonical_model_node_pack("comfy_gguf") == "ComfyUI-GGUF"
    assert canonical_model_node_pack("ltx") == "ComfyUI-LTXVideo"
    assert canonical_model_node_pack("wan_wrapper") == "ComfyUI-WanVideoWrapper"
    for gap in DOCUMENTED_NODE_PACK_GAPS:
        assert canonical_model_node_pack(gap) is None
    assert canonical_model_node_pack("wan_wrappre") is None


def test_load_registry_preserves_raw_target_node_pack_values_after_validation(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: sample
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: comfy_gguf
        path: diffusion_models/model.bin
      - node_pack: comfy_core
        path: checkpoints/model.bin
      - node_pack: ComfyUI-GGUF
        path: unet/model.bin
""",
    )

    entries = load_registry(registry)

    assert entries[0].targets == (
        ModelTarget(node_pack="comfy_gguf", path="diffusion_models/model.bin"),
        ModelTarget(node_pack="comfy_core", path="checkpoints/model.bin"),
        ModelTarget(node_pack="ComfyUI-GGUF", path="unet/model.bin"),
    )


def test_load_registry_validates_each_target_independently(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: sample
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: ace_step
        path: checkpoints/model.bin
      - node_pack: wan_wrappre
        path: diffusion_models/model.bin
""",
    )

    with pytest.raises(ValueError, match="wan_wrappre"):
        load_registry(registry)


def test_default_registry_node_packs_only_use_canonical_alias_or_gap_values() -> None:
    entries = load_registry()

    for entry in entries:
        for target in entry.targets:
            raw_name = target.node_pack
            assert (
                canonical_model_node_pack(raw_name) is not None or raw_name in DOCUMENTED_NODE_PACK_GAPS
            ), f"{entry.id} target uses unexpected node_pack {raw_name!r}"


# ── parametric typo rejection ───────────────────────────────────────────

@pytest.mark.parametrize(
    "typo",
    [
        "wan_wrappre",
        "comfy_ggf",
        "ltxx",
        "comfyui_gguf",
        "ComfyUIGGUF",
        "wan_wraper",
        "LTX",
        "comfy_gyuf",
    ],
)
def test_typo_node_packs_rejected_deterministically(tmp_path: Path, typo: str) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        f"""
models:
  - id: sample
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: {typo}
        path: checkpoints/model.bin
""",
    )

    with pytest.raises(ValueError, match="unknown target.node_pack"):
        load_registry(registry)


def test_typo_rejection_error_names_the_offending_value(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: sample
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: definitely_not_a_pack
        path: checkpoints/model.bin
""",
    )

    with pytest.raises(ValueError) as exc_info:
        load_registry(registry)

    message = str(exc_info.value)
    assert "definitely_not_a_pack" in message
    assert "unknown target.node_pack" in message
    # allowed set must be mentioned so a human can self-correct
    assert "ComfyUI-GGUF" in message
    assert "comfy_gguf" in message
    assert "ace_step" in message


# ── canonical helper edge cases ─────────────────────────────────────────

def test_canonical_model_node_pack_edge_cases() -> None:
    """Empty string, whitespace, and non-string-like values return None."""
    assert canonical_model_node_pack("") is None
    assert canonical_model_node_pack("  ") is None
    # random unknown string
    assert canonical_model_node_pack("totally_random_xyz") is None


# ── multi-target round-trips ────────────────────────────────────────────

def test_all_aliases_in_one_entry_pass_validation(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: multi_alias
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: comfy_gguf
        path: checkpoints/model.bin
      - node_pack: ltx
        path: ltx_models/model.bin
      - node_pack: wan_wrapper
        path: wan_models/model.bin
""",
    )

    entries = load_registry(registry)

    assert len(entries) == 1
    assert entries[0].targets == (
        ModelTarget(node_pack="comfy_gguf", path="checkpoints/model.bin"),
        ModelTarget(node_pack="ltx", path="ltx_models/model.bin"),
        ModelTarget(node_pack="wan_wrapper", path="wan_models/model.bin"),
    )


def test_all_canonical_names_in_one_entry_pass_validation(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: multi_canonical
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: ComfyUI-GGUF
        path: checkpoints/model.bin
      - node_pack: ComfyUI-LTXVideo
        path: ltx_models/model.bin
      - node_pack: ComfyUI-WanVideoWrapper
        path: wan_models/model.bin
""",
    )

    entries = load_registry(registry)

    assert len(entries) == 1
    assert entries[0].targets == (
        ModelTarget(node_pack="ComfyUI-GGUF", path="checkpoints/model.bin"),
        ModelTarget(node_pack="ComfyUI-LTXVideo", path="ltx_models/model.bin"),
        ModelTarget(node_pack="ComfyUI-WanVideoWrapper", path="wan_models/model.bin"),
    )


def test_gap_targets_alongside_valid_targets_pass(tmp_path: Path) -> None:
    """All three documented gaps + one valid alias should pass validation."""
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: gaps_and_valid
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: ace_step
        path: checkpoints/model.bin
      - node_pack: comfy_core
        path: core_models/model.bin
      - node_pack: kijai_ltx
        path: kijai_models/model.bin
      - node_pack: comfy_gguf
        path: gguf_models/model.bin
""",
    )

    entries = load_registry(registry)

    assert len(entries) == 1
    assert entries[0].targets == (
        ModelTarget(node_pack="ace_step", path="checkpoints/model.bin"),
        ModelTarget(node_pack="comfy_core", path="core_models/model.bin"),
        ModelTarget(node_pack="kijai_ltx", path="kijai_models/model.bin"),
        ModelTarget(node_pack="comfy_gguf", path="gguf_models/model.bin"),
    )


def test_per_entry_validation_one_bad_entry_does_not_block_others(tmp_path: Path) -> None:
    """A typo in one entry should fail the whole load (atomic), but the
    validation checks every target independently within an entry."""
    registry = _write_registry(
        tmp_path / "models.yaml",
        """
models:
  - id: good_entry
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: comfy_gguf
        path: checkpoints/model.bin
  - id: bad_entry
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 1
    targets:
      - node_pack: comfy_gguf
        path: checkpoints/ok.bin
      - node_pack: obviously_wrong
        path: checkpoints/bad.bin
""",
    )

    with pytest.raises(ValueError, match="obviously_wrong"):
        load_registry(registry)
