"""Tests for the on-demand node-schema resolver (escalation ladder).

L1 (offline, CI): the provider relabels a static-parsed schema and degrades cleanly when no
pack resolves — using a temp-dir sample pack source (no network, no execution).
L1-ladder (offline, CI): the shared extraction core (``vibecomfy.schema.extract``) catches a
static INPUT_TYPES via AST and a *dynamic* INPUT_TYPES via the import rung that AST provably
misses.
L3 (offline, CI, deterministic): the resolver's rung 2 (runtime INPUT_TYPES) resolves a node
whose schema is built at runtime — AST misses it, the import rung catches it.
L2 (live, opt-in): resolves real uninstalled registry nodes by cloning their public source.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.schema.extract import extract_pack_schemas
from vibecomfy.schema.on_demand import OnDemandInstallSchemaProvider


def _write_sample_pack(root: Path) -> Path:
    """A minimal custom-node pack source whose INPUT_TYPES is statically parseable."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "nodes.py").write_text(
        """
class SampleWidgetNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0}),
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {"seed": ("INT", {"default": 0})},
        }
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "execute"
    CATEGORY = "sample/tests"
""",
        encoding="utf-8",
    )
    return root


def _write_runtime_built_pack(root: Path, *, class_name: str = "RuntimeBuiltNode") -> Path:
    """A pack whose INPUT_TYPES is built at runtime so static AST CANNOT parse it.

    The return statement embeds a dict comprehension, which the AST SafeEval does not
    handle -> rung 1 records a parse failure and misses the class. At runtime the
    comprehension executes normally, so rung 2 (import) catches it with real inputs.
    The class + NODE_CLASS_MAPPINGS live in ``__init__.py`` so the import rung finds them.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text(
        f"""
class {class_name}:
    @classmethod
    def INPUT_TYPES(cls):
        # Dict comprehension inside the return: AST SafeEval raises on it -> rung 1 miss.
        return {{"required": {{k: ("FLOAT", {{"default": 0.5}}) for k in ("alpha", "beta")}}}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "sample/runtime"


NODE_CLASS_MAPPINGS = {{"{class_name}": {class_name}}}
""",
        encoding="utf-8",
    )
    return root


def test_l1_static_parse_relabels_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rung 1 parses a cloned pack statically and stamps on_demand_static provenance."""
    clone = _write_sample_pack(tmp_path / "sample-pack")
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")

    # Stub the network/clone rungs so this is offline + deterministic.
    fake_ref = SimpleNamespace(slug="sample-pack", url="https://example.invalid/sample-pack")
    monkeypatch.setattr(provider, "_resolve_pack", lambda class_type: fake_ref)
    monkeypatch.setattr(provider, "_ensure_clone", lambda ref: clone)

    schema = provider.get_schema("SampleWidgetNode")
    assert schema is not None
    assert schema.source_provider == "on_demand_static"
    assert schema.source_package == "sample-pack"
    assert schema.confidence == pytest.approx(0.9)
    assert "image" in schema.inputs and "strength" in schema.inputs
    # Memoized in-process: second call does not re-resolve.
    assert provider.get_schema("SampleWidgetNode") is schema


def test_l1_no_pack_resolves_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A class with no resolvable pack returns None (cached), never raises."""
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")
    monkeypatch.setattr(provider, "_resolve_pack", lambda class_type: None)
    assert provider.get_schema("DoesNotExistNode") is None
    # Cached negative so the chain doesn't keep retrying network lookups.
    assert provider._cache["DoesNotExistNode"] is None


def test_l1_ladder_ast_catches_static_import_catches_dynamic(tmp_path: Path) -> None:
    """The shared extraction ladder: AST parses a literal INPUT_TYPES; the import rung catches a
    dynamic INPUT_TYPES that AST provably misses."""
    # Static pack -> AST rung resolves it.
    static = _write_sample_pack(tmp_path / "static-pack")
    res_static = extract_pack_schemas(static, pack_name="static-pack", allow_import=False)
    assert "SampleWidgetNode" in res_static.entries
    assert res_static.method == "ast"

    # Runtime-built pack -> AST misses (dict comprehension), import rung catches it.
    runtime = _write_runtime_built_pack(tmp_path / "runtime-pack")
    res_ast_only = extract_pack_schemas(runtime, pack_name="runtime-pack", allow_import=False)
    assert "RuntimeBuiltNode" not in res_ast_only.entries, "AST must miss the dynamic INPUT_TYPES"

    res_with_import = extract_pack_schemas(runtime, pack_name="runtime-pack", allow_import=True)
    assert "RuntimeBuiltNode" in res_with_import.entries, "import rung must catch the dynamic node"
    assert res_with_import.method == "import"
    entry = res_with_import.entries["RuntimeBuiltNode"]
    assert set(entry["inputs"]["required"]) == {"alpha", "beta"}


def test_l3_runtime_resolves_dynamic_node_when_ast_misses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L3 (deterministic): rung 2 resolves a node whose INPUT_TYPES is built at runtime.

    With the boot gate OFF, rung 1 (AST) misses the dynamic node -> None. With the boot gate
    ON, rung 2 (subprocess runtime INPUT_TYPES) resolves it and stamps on_demand_runtime.
    """
    clone = _write_runtime_built_pack(tmp_path / "runtime-pack")
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")
    fake_ref = SimpleNamespace(slug="runtime-pack", url="https://example.invalid/runtime-pack")
    monkeypatch.setattr(provider, "_resolve_pack", lambda class_type: fake_ref)
    monkeypatch.setattr(provider, "_ensure_clone", lambda ref: clone)

    # Rung 1 only (boot off): AST cannot parse the dict comprehension -> a degenerate
    # empty-inputs schema (the parse landed but yielded no inputs).
    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_BOOT", "0")
    provider._cache.clear()
    degenerate = provider.get_schema("RuntimeBuiltNode")
    assert degenerate is None or not degenerate.inputs

    # Rung 2 (boot on): the import subprocess runs INPUT_TYPES() at runtime -> real inputs.
    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_BOOT", "1")
    provider._cache.clear()
    schema = provider.get_schema("RuntimeBuiltNode")
    assert schema is not None
    assert schema.source_provider == "on_demand_runtime"
    assert schema.confidence == 1.0
    assert set(schema.inputs) == {"alpha", "beta"}


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("VIBECOMFY_ON_DEMAND_SCHEMAS") != "1",
    reason="needs VIBECOMFY_ON_DEMAND_SCHEMAS=1 (clones public GitHub repos)",
)
@pytest.mark.parametrize(
    "class_type",
    [
        "FaceDetailer",  # ComfyUI-Impact-Pack
        "PreviewBridge",  # ComfyUI-Impact-Pack
        "ImpactLogger",  # ComfyUI-Impact-Pack
        "GradientImage",  # comfyui-tooling-nodes
    ],
)
def test_l2_resolve_real_uninstalled_registry_node(class_type: str) -> None:
    """L2: real uninstalled registry nodes resolve via their public pack (rung 1, static AST).

    These classes are absent from the shipped comfy-core corpus but resolve by cloning the
    pack and statically parsing INPUT_TYPES. Rung 2 (runtime) is a marginal supplement whose
    real-world coverage depends on pack import-cleanliness; broad third-party coverage is
    measured by the L5 sweep and the corpus builder (L6).
    """
    provider = OnDemandInstallSchemaProvider()
    schema = provider.get_schema(class_type)
    assert schema is not None, f"{class_type} should resolve via its public pack source"
    assert schema.source_provider.startswith("on_demand_")
    assert schema.inputs, f"{class_type} resolved with no inputs"


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("VIBECOMFY_RUN_LIVE_DEMO") != "1",
    reason="needs VIBECOMFY_RUN_LIVE_DEMO=1 + DEEPSEEK creds (runs a real agent-edit, costs tokens)",
)
def test_l4_additive_edit_lands_valid(tmp_path: Path) -> None:
    """L4 (live, end-to-end): a headless additive edit of a removed feature node lands a valid graph.

    Drives the real product path: run_additive_case removes a feature (here the upscale node of
    image/basic_image_upscale) then asks the fixer to add it back in additive mode, with the
    on-demand resolver on. Verdict accepted/alternative_repair == the chain works end-to-end.
    Proven green (alternative_repair, attempt 1, ~54s) on 2026-07-24.
    """
    os.environ["VIBECOMFY_HEADLESS"] = "1"
    os.environ.setdefault("VIBECOMFY_ON_DEMAND_SCHEMAS", "1")
    from vibecomfy.demo_factory.run_campaign import run_additive_case

    result = run_additive_case("image/basic_image_upscale", "upscale", 1, tmp_path / "l4")
    assert result["verdict"] in {"accepted", "alternative_repair"}, (
        f"additive edit should land a sound repair, got verdict={result.get('verdict')}"
    )
