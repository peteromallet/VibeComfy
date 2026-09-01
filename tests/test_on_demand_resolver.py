"""Tests for the on-demand node-schema resolver (escalation ladder).

L1 (offline, CI): the provider relabels a static-parsed schema and degrades cleanly when no
pack resolves — using a temp-dir sample pack source (no network, no execution).
L1-ladder (offline, CI): the shared extraction core (``vibecomfy.schema.extract``) catches a
static INPUT_TYPES via AST; a *dynamic* INPUT_TYPES is retained in degraded form by AST
(unresolved choices — never silently dropped) and fully resolved by the import rung.
L3 (offline, CI, deterministic): the resolver's rung 2 (runtime INPUT_TYPES) resolves a node
whose schema is built at runtime.
L2 (live, opt-in): resolves real uninstalled registry nodes by cloning their public source.
"""
from __future__ import annotations

import json
import io
import os
import zipfile
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


def test_propost_class_uses_verified_pack_before_fuzzy_github_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")

    def unexpected_fuzzy_lookup(_class_type: str):
        raise AssertionError("exact class witness must outrank fuzzy GitHub search")

    monkeypatch.setattr(
        "vibecomfy.registry.pack_resolver.resolve_missing_nodes",
        unexpected_fuzzy_lookup,
    )

    ref = provider._resolve_pack("ProPostApplyLUT")
    assert ref.slug == "ComfyUI-ProPost"
    assert ref.url == "https://github.com/digitaljohn/comfyui-propost"
    assert ref.source == "verified-class-fallback"


def test_schema_git_commands_skip_lfs_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.schema import on_demand

    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(on_demand.subprocess, "run", fake_run)
    on_demand._run_git(["git", "clone", "source", "target"], timeout=5)
    assert captured["env"]["GIT_LFS_SKIP_SMUDGE"] == "1"


def test_registry_archive_resolves_package_version_without_git_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Comfy Registry package archive is a valid cold-cache schema source."""
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(
            "nodes.py",
            """
class ArchiveNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"strength": ("FLOAT", {"default": 0.5})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
""",
        )
    archive_bytes = payload.getvalue()

    class _Response:
        def __enter__(self):
            return io.BytesIO(archive_bytes)

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("vibecomfy.schema.on_demand.urllib.request.urlopen", lambda *a, **k: _Response())
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")
    ref = type(
        "Ref",
        (),
        {
            "slug": "registry-pack",
            "url": "https://github.com/example/registry-pack",
            "version": "1.3.5",
            "download_url": "https://cdn.comfy.org/example/registry-pack/1.3.5/node.zip",
        },
    )()
    monkeypatch.setattr(provider, "_resolve_pack", lambda _class_type: ref)

    schema = provider.get_schema("ArchiveNode")

    assert schema is not None
    assert schema.source_provider == "on_demand_static"
    assert schema.inputs["strength"].type == "FLOAT"
    marker = tmp_path / "sandbox" / "registry-pack" / ".vibecomfy-clone-complete.json"
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    assert metadata["kind"] == "registry-archive"
    assert metadata["pin"] == "1.3.5"
    assert metadata["archive_sha256"] == metadata["head"]


def test_l1_ladder_ast_degrades_dynamic_import_catches_fully(tmp_path: Path) -> None:
    """The shared extraction ladder: AST parses a literal INPUT_TYPES; a dynamic INPUT_TYPES
    degrades to a retained-but-unresolved entry (never silently dropped), and the import rung
    recovers the fully resolved surface."""
    # Static pack -> AST rung resolves it.
    static = _write_sample_pack(tmp_path / "static-pack")
    res_static = extract_pack_schemas(static, pack_name="static-pack", allow_import=False)
    assert "SampleWidgetNode" in res_static.entries
    assert res_static.method == "ast"

    # Runtime-built pack -> AST keeps the class but cannot resolve the
    # comprehension-built inputs (P4: dynamic combos are retained, not dropped).
    runtime = _write_runtime_built_pack(tmp_path / "runtime-pack")
    res_ast_only = extract_pack_schemas(runtime, pack_name="runtime-pack", allow_import=False)
    assert "RuntimeBuiltNode" in res_ast_only.entries, "AST must retain the dynamic node"
    degraded = res_ast_only.entries["RuntimeBuiltNode"]
    assert not json.dumps(degraded["inputs"]).count("alpha"), (
        "AST must not fabricate comprehension-built input names"
    )

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
    ON, rung 2 (subprocess runtime INPUT_TYPES) resolves it and stamps on_demand_import.
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
    assert schema.source_provider == "on_demand_import"
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


# ── Default-on + bounded sandbox (regression for the HotshotXL "install it" bounce) ──


def _has_on_demand_provider(provider: object) -> bool:
    return any(isinstance(p, OnDemandInstallSchemaProvider) for p in provider._providers)


def test_on_demand_is_default_on_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """On-demand resolution is ON by default — the agent can author uninstalled node
    packs out of the box. This is the regression for the HotshotXL case where a pack the
    user hadn't installed produced 'Install the missing runtime class' instead of building it."""
    from vibecomfy.schema.provider import get_authoring_schema_provider

    monkeypatch.delenv("VIBECOMFY_ON_DEMAND_SCHEMAS", raising=False)
    assert _has_on_demand_provider(get_authoring_schema_provider())


def test_on_demand_env_zero_opts_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """VIBECOMFY_ON_DEMAND_SCHEMAS=0 explicitly disables on-demand (escape hatch)."""
    from vibecomfy.schema.provider import get_authoring_schema_provider

    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_SCHEMAS", "0")
    assert not _has_on_demand_provider(get_authoring_schema_provider())


def test_on_demand_explicit_flag_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit on_demand_schemas flag wins over the env var (the settings-box toggle
    is authoritative for the request that carries it)."""
    from vibecomfy.schema.provider import AuthoringSchemaProvider, get_authoring_schema_provider

    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_SCHEMAS", "0")
    assert _has_on_demand_provider(get_authoring_schema_provider(on_demand_schemas=True))
    assert not _has_on_demand_provider(AuthoringSchemaProvider(on_demand_schemas=False))


def test_sandbox_cap_evicts_oldest_packs_first(tmp_path: Path) -> None:
    """The clone sandbox is bounded: exceeding max_packs evicts the oldest clone (LRU by
    mtime), so on-demand resolution can't grow the cache without limit."""
    import os

    root = tmp_path / "sandbox"
    root.mkdir()
    for i, name in enumerate(["a", "b", "c"]):
        pack = root / name
        pack.mkdir()
        (pack / "f").write_text("x" * (10 * (i + 1)))
        os.utime(pack, (i, i))  # a oldest, c newest
    provider = OnDemandInstallSchemaProvider(sandbox_root=root, max_packs=1, max_bytes=10 * 1024 * 1024)
    provider._enforce_cap()
    assert sorted(p.name for p in root.iterdir()) == ["c"]  # only the newest survives


def test_sandbox_cap_respects_byte_budget(tmp_path: Path) -> None:
    """The byte budget evicts oldest clones until total size fits."""
    import os

    root = tmp_path / "sandbox"
    root.mkdir()
    for i, name in enumerate(["old", "mid", "new"]):
        pack = root / name
        pack.mkdir()
        (pack / "big").write_text("y" * (1024 * 1024))
        os.utime(pack, (i, i))
    provider = OnDemandInstallSchemaProvider(
        sandbox_root=root, max_packs=999, max_bytes=int(1.5 * 1024 * 1024)
    )
    provider._enforce_cap()
    remaining = sorted(p.name for p in root.iterdir())
    assert "old" not in remaining  # oldest evicted first


def test_sandbox_clone_reuse_bumps_lru_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-resolving an already-cloned pack touches its mtime so it reads as recently used
    for eviction (a hot pack isn't wrongly evicted over a cold one)."""
    import os
    import time

    root = tmp_path / "sandbox"
    root.mkdir()
    cold = root / "cold"
    (cold / ".git").mkdir(parents=True)
    (cold / ".vibecomfy-clone-complete.json").write_text(
        json.dumps(
            {
                "complete": True,
                "slug": "cold",
                "url": "https://example.invalid/cold",
                "pin": None,
                "head": "commit-123",
            }
        ),
        encoding="utf-8",
    )
    os.utime(cold, (1_000_000, 1_000_000))  # old
    provider = OnDemandInstallSchemaProvider(sandbox_root=root)
    from types import SimpleNamespace

    ref = SimpleNamespace(slug="cold", url="https://example.invalid/cold")
    monkeypatch.setattr(
        "vibecomfy.schema.on_demand._run_git",
        lambda command, timeout: __import__("subprocess").CompletedProcess(
            command, 0, stdout="commit-123\n", stderr=""
        ),
    )
    before = cold.stat().st_mtime
    time.sleep(1.05)
    assert provider._ensure_clone(ref) == cold
    assert cold.stat().st_mtime > before  # touched -> recently used
