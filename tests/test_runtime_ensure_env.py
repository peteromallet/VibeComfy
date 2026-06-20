from __future__ import annotations

import subprocess
from pathlib import Path

from vibecomfy.node_packs import CustomNodePack
from vibecomfy.node_packs import InstallBatchResult, InstallResult, PipPreflightResult
from vibecomfy.porting.object_info import consume as object_info_consume
from vibecomfy.porting.object_info import serialize as object_info_serialize
from vibecomfy.registry.pack_resolver import PackRef, PackResolution
import vibecomfy.runtime.ensure_env as ensure_env_module
from vibecomfy.runtime.ensure_env import ensure_env


def _pack(name: str) -> CustomNodePack:
    return CustomNodePack(
        name=name,
        repo=f"https://example.test/{name}.git",
        classes=frozenset({f"{name}Node"}),
    )


def test_ensure_env_loads_raw_workflow_and_excludes_comfy_core_from_install(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        """
        {
          "nodes": [
            {"id": 1, "type": "VAELoader", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
            {"id": 2, "type": "ExamplePackNode", "properties": {"cnr_id": "ExamplePack", "ver": "1.2.3"}}
          ]
        }
        """,
        encoding="utf-8",
    )
    calls: list[tuple[str, ...]] = []

    def installer(packs):
        calls.append(tuple(pack.name for pack in packs))
        return InstallBatchResult(
            ok=True,
            results=(
                InstallResult("ExamplePack", "installed", "abc123", None),
            ),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(
        workflow_path,
        known_packs=(_pack("ExamplePack"),),
        installer=installer,
        introspector=lambda packs: {
            "ExamplePackNode": {"python_module": "ExamplePack.nodes"},
            "VAELoader": {"python_module": "."},
        },
        cache_writer=lambda payload: {"written": sorted(payload)},
    )

    assert result.ok is True
    assert calls == [("ExamplePack",)]
    assert [outcome.slug for outcome in result.pack_outcomes] == ["ExamplePack", "comfy-core"]
    assert result.pack_outcomes[0].install_status == "installed"
    assert result.pack_outcomes[1].git_commit_sha is None
    assert not result.failures
    assert result.low_confidence is False
    assert result.warnings == ()


def test_ensure_env_uses_provenance_requirements_for_authored_pins_and_aux_git() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "PinnedPackNode",
                "properties": {
                    "cnr_id": "PinnedPack",
                    "aux_id": "owner/pinned-pack",
                    "ver": "1234567890abcdef1234567890abcdef12345678",
                },
            },
            {
                "id": 2,
                "type": "AuxOnlyNode",
                "properties": {"aux_id": "someone/aux-pack", "ver": "v1.2.3"},
            },
        ]
    }
    install_calls: list[object] = []

    def installer(packs, *, install_refs_by_name=None):
        install_calls.append((tuple(pack.name for pack in packs), install_refs_by_name))
        return InstallBatchResult(
            ok=True,
            results=(
                InstallResult("PinnedPack", "installed", "1234567890abcdef1234567890abcdef12345678", None),
                InstallResult("aux-pack", "installed", "aux123", None),
            ),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(
        workflow,
        known_packs=(_pack("PinnedPack"),),
        installer=installer,
        introspector=lambda packs: {
            "PinnedPackNode": {"python_module": "PinnedPack.nodes"},
            "AuxOnlyNode": {"python_module": "AuxPack.nodes"},
        },
        cache_writer=lambda payload: {"written": sorted(payload)},
    )

    assert result.ok is True
    assert install_calls and install_calls[0][0] == ("PinnedPack", "aux-pack")
    refs = install_calls[0][1]
    assert refs["PinnedPack"].version == "1234567890abcdef1234567890abcdef12345678"
    assert refs["PinnedPack"].commit == "1234567890abcdef1234567890abcdef12345678"
    assert refs["aux-pack"].source == "aux-git"
    assert refs["aux-pack"].url == "https://github.com/someone/aux-pack.git"
    assert refs["aux-pack"].version == "v1.2.3"
    assert result.aux_only[0].aux_id == "someone/aux-pack"
    assert result.warnings[0].code == "aux_only_git_provenance"


def test_ensure_env_collects_unresolved_and_install_failures_without_fail_fast() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "GoodNode", "properties": {"cnr_id": "GoodPack"}},
            {"id": 2, "type": "FailNode", "properties": {"cnr_id": "FailPack"}},
            {"id": 3, "type": "MysteryNode", "properties": {"cnr_id": "MissingPack"}},
        ]
    }
    installed: list[tuple[str, ...]] = []

    def installer(packs):
        installed.append(tuple(pack.name for pack in packs))
        return InstallBatchResult(
            ok=False,
            results=(
                InstallResult("FailPack", "failed", None, "clone failed"),
                InstallResult("GoodPack", "refreshed", "def456", None),
            ),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(
        workflow,
        known_packs=(_pack("GoodPack"), _pack("FailPack")),
        installer=installer,
    )

    assert result.ok is False
    assert installed == [("FailPack", "GoodPack")]
    assert {failure.code for failure in result.failures} == {"unresolved_pack", "install_failed"}
    assert {failure.slug for failure in result.failures} == {"MissingPack", "FailPack"}
    outcomes = {outcome.slug: outcome for outcome in result.pack_outcomes}
    assert outcomes["GoodPack"].ok is True
    assert outcomes["FailPack"].ok is False
    assert outcomes["MissingPack"].ok is False


def test_ensure_env_reports_low_confidence_warnings_without_dropping_legacy_diagnostics() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "UnknownExecutionNode", "properties": {}},
        ]
    }

    result = ensure_env(workflow, known_packs=(), installer=lambda packs: (_ for _ in ()).throw(AssertionError("no install")))

    assert result.ok is True
    assert result.low_confidence is True
    assert [warning.code for warning in result.warnings] == ["unprovenanced_execution_node"]
    assert result.warnings[0].low_confidence is True
    assert result.unprovenanced[0].class_type == "UnknownExecutionNode"
    assert result.diagnostics == {
        "aux_only_count": 0,
        "unprovenanced_count": 1,
        "core_slug_non_core_count": 0,
    }


def test_ensure_env_fails_on_conflicting_authored_versions_before_install() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "PackNodeA", "properties": {"cnr_id": "VersionedPack", "ver": "1.0.0"}},
            {"id": 2, "type": "PackNodeB", "properties": {"cnr_id": "VersionedPack", "ver": "2.0.0"}},
        ]
    }

    def installer(packs):
        raise AssertionError("conflicting authored versions must not install")

    result = ensure_env(workflow, known_packs=(_pack("VersionedPack"),), installer=installer)

    assert result.ok is False
    assert [failure.code for failure in result.failures] == ["conflicting_authored_versions"]
    assert result.failures[0].slug == "VersionedPack"


def test_ensure_env_resolution_order_prefers_local_then_aux_then_cnr_and_class_fallback(tmp_path: Path) -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "LocalNode", "properties": {"cnr_id": "LocalPack", "ver": "1.0.0"}},
            {"id": 2, "type": "AuxNode", "properties": {"aux_id": "author/aux-pack", "ver": "v2.0.0"}},
            {"id": 3, "type": "RegistryNode", "properties": {"cnr_id": "RegistryPack", "ver": "3.0.0"}},
            {"id": 4, "type": "FallbackNode", "properties": {}},
        ]
    }
    local_root = tmp_path / "custom_nodes"
    local_pack = local_root / "LocalPack"
    local_pack.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/local/LocalPack.git"],
        cwd=local_pack,
        check=True,
        capture_output=True,
        text=True,
    )
    local_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=local_pack,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    resolver_calls: list[tuple[str, str | None, str | None, bool]] = []

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        resolver_calls.append((query, version_pin, aux_id, allow_remote_lookup))
        if aux_id == "author/aux-pack":
            return PackResolution(
                query=query,
                query_type="aux_git",
                ref=PackRef(slug="aux-pack", source="aux-git", version=version_pin, url="https://github.com/author/aux-pack.git"),
            )
        if query == "RegistryPack":
            return PackResolution(
                query=query,
                query_type="slug",
                ref=PackRef(slug="RegistryPack", source="comfy-registry", version=version_pin, url="https://example.test/RegistryPack.git"),
            )
        if query == "FallbackNode":
            return PackResolution(
                query=query,
                query_type="class",
                ref=PackRef(slug="FallbackPack", source="comfy-registry", url="https://example.test/FallbackPack.git"),
            )
        raise AssertionError(query)

    install_calls: list[object] = []

    def installer(packs, *, install_refs_by_name=None):
        install_calls.append((tuple(pack.name for pack in packs), install_refs_by_name))
        return InstallBatchResult(
            ok=True,
            results=(
                InstallResult("LocalPack", "refreshed", local_head, None),
                InstallResult("aux-pack", "installed", "auxhead", None),
                InstallResult("RegistryPack", "installed", "registryhead", None),
                InstallResult("FallbackPack", "installed", "fallbackhead", None),
            ),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(
        workflow,
        known_packs=(_pack("LocalPack"),),
        installer=installer,
        introspector=lambda packs: {
            "LocalNode": {},
            "AuxNode": {},
            "RegistryNode": {},
            "FallbackNode": {},
        },
        cache_writer=lambda payload: {"written": sorted(payload)},
        install_roots=(local_root,),
        resolver=resolver,
    )

    assert result.ok is True
    assert resolver_calls == [
        ("aux-pack", "v2.0.0", "author/aux-pack", False),
        ("RegistryPack", "3.0.0", None, True),
        ("FallbackNode", None, None, True),
    ]
    assert install_calls[0][0] == ("aux-pack", "LocalPack", "RegistryPack", "FallbackPack")
    refs = install_calls[0][1]
    assert refs["LocalPack"].source == "local-git"
    assert refs["LocalPack"].commit == local_head
    assert refs["aux-pack"].source == "aux-git"
    assert refs["RegistryPack"].source == "comfy-registry"
    assert refs["FallbackPack"].slug == "FallbackPack"
    assert result.low_confidence is True
    assert "class_to_pack_fallback" in {warning.code for warning in result.warnings}


def test_ensure_env_aux_id_prefers_local_git_without_remote_lookup(tmp_path: Path) -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "AuxNode", "properties": {"aux_id": "author/aux-pack", "ver": "v2.0.0"}},
        ]
    }
    local_root = tmp_path / "custom_nodes"
    local_pack = local_root / "aux-pack"
    local_pack.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=local_pack, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/author/aux-pack.git"],
        cwd=local_pack,
        check=True,
        capture_output=True,
        text=True,
    )
    local_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=local_pack,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    resolver_calls: list[tuple[str, str | None, str | None, bool]] = []

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        resolver_calls.append((query, version_pin, aux_id, allow_remote_lookup))
        raise AssertionError("local aux-id match should bypass remote resolver")

    install_refs_seen: dict[str, PackRef] = {}

    def installer(packs, *, install_refs_by_name=None):
        install_refs_seen.update(install_refs_by_name or {})
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("aux-pack", "refreshed", local_head, None),),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        introspector=lambda packs: {"AuxNode": {"python_module": "AuxPack.nodes"}},
        cache_writer=lambda payload: {"written": sorted(payload)},
        install_roots=(local_root,),
        resolver=resolver,
    )

    assert result.ok is True
    assert resolver_calls == []
    assert install_refs_seen["aux-pack"].source == "local-git"
    assert install_refs_seen["aux-pack"].version == "v2.0.0"
    assert install_refs_seen["aux-pack"].commit == local_head


def test_ensure_env_real_wan_t2v_reports_low_confidence_without_installing() -> None:
    install_calls: list[tuple[str, ...]] = []

    def installer(packs):
        install_calls.append(tuple(pack.name for pack in packs))
        return InstallBatchResult(
            ok=True,
            results=(),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env("ready_templates/sources/official/video/wan_t2v.json", known_packs=(), installer=installer)

    assert result.ok is True
    assert install_calls == []
    assert result.low_confidence is True
    assert any(warning.code == "unprovenanced_execution_node" for warning in result.warnings)
    assert result.unprovenanced


def test_ensure_env_fails_closed_for_suspicious_comfy_core_and_keeps_diagnostics_only() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "ResolutionSelector", "properties": {"cnr_id": "comfy-core"}},
            {"id": 2, "type": "AuxNode", "properties": {"aux_id": "owner/repo", "ver": "abc"}},
            {"id": 3, "type": "KSampler", "properties": {}},
        ]
    }

    def installer(packs):
        raise AssertionError("suspicious comfy-core must not be passed to installer")

    result = ensure_env(workflow, known_packs=(), installer=installer)

    assert result.ok is False
    assert [failure.code for failure in result.failures] == ["suspicious_comfy_core"]
    assert result.aux_only[0].aux_id == "owner/repo"
    assert result.unprovenanced[0].class_type == "KSampler"
    assert result.diagnostics == {
        "aux_only_count": 1,
        "unprovenanced_count": 1,
        "core_slug_non_core_count": 1,
    }


def test_ensure_env_calls_introspector_and_cache_writer_after_success() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "ExamplePackNode", "properties": {"cnr_id": "ExamplePack"}},
        ]
    }
    events: list[object] = []

    def installer(packs):
        events.append(("install", tuple(pack.name for pack in packs)))
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("ExamplePack", "refreshed", "abc123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(packs):
        events.append(("introspect", tuple(pack.name for pack in packs)))
        return {"ExamplePackNode": {"python_module": "ExamplePack.nodes"}}

    def cache_writer(payload):
        events.append(("cache", payload))
        return {"written": 1}

    result = ensure_env(
        workflow,
        known_packs=(_pack("ExamplePack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )

    assert result.ok is True
    assert events == [
        ("install", ("ExamplePack",)),
        ("introspect", ("ExamplePack",)),
        ("cache", {"ExamplePack": {"ExamplePackNode": {"python_module": "ExamplePack.nodes"}}}),
    ]
    assert result.pack_outcomes[0].introspected is True
    assert result.pack_outcomes[0].cache_written is True
    assert result.cache_write_result == {"written": 1}


def test_ensure_env_default_introspection_filters_and_writes_identity_cache(monkeypatch) -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "ExamplePackNode", "properties": {"cnr_id": "ExamplePack"}},
            {"id": 2, "type": "VAELoader", "properties": {"cnr_id": "comfy-core"}},
        ]
    }
    provider_calls: list[str | None] = []
    build_calls: list[tuple[dict[str, object], object, str]] = []

    class FakeRuntimeSchemaProvider:
        def __init__(self, *, server_url=None):
            provider_calls.append(server_url)

        def object_info(self):
            return {
                "ExamplePackNode": {"python_module": "ExamplePack.nodes"},
                "VAELoader": {"python_module": "."},
                "UnrelatedNode": {"python_module": "OtherPack.nodes"},
            }

    def installer(packs):
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("ExamplePack", "installed", "abc123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def fake_build_cache(source_path, *, version, identity, full_pack_refresh):
        import json

        build_calls.append((json.loads(Path(source_path).read_text(encoding="utf-8")), identity, version))
        assert full_pack_refresh == {identity.pack_slug}
        return (len(build_calls[-1][0]), 1)

    monkeypatch.setattr(ensure_env_module, "RuntimeSchemaProvider", FakeRuntimeSchemaProvider)
    monkeypatch.setattr(ensure_env_module, "build_cache", fake_build_cache)

    result = ensure_env(
        workflow,
        known_packs=(_pack("ExamplePack"),),
        installer=installer,
        server_url="http://runtime.test:8188",
    )

    assert result.ok is True
    assert provider_calls == ["http://runtime.test:8188"]
    assert [call[0] for call in build_calls] == [
        {"ExamplePackNode": {"python_module": "ExamplePack.nodes"}},
        {"VAELoader": {"python_module": "."}},
    ]
    custom_identity = build_calls[0][1]
    core_identity = build_calls[1][1]
    assert custom_identity.pack_slug == "ExamplePack"
    assert custom_identity.git_commit == "abc123"
    assert custom_identity.evidence_identity is None
    assert core_identity.pack_slug == "comfy-core"
    assert core_identity.git_commit is None
    assert core_identity.evidence_identity == "ensure-env:comfy-core"
    assert result.cache_write_result == {
        "written": {
            "ExamplePack": {"classes": 1, "packs": 1},
            "comfy-core": {"classes": 1, "packs": 1},
        }
    }


def test_ensure_env_default_cache_write_requires_custom_git_identity(monkeypatch) -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "ExamplePackNode", "properties": {"cnr_id": "ExamplePack"}},
        ]
    }

    class FakeRuntimeSchemaProvider:
        def __init__(self, *, server_url=None):
            pass

        def object_info(self):
            return {"ExamplePackNode": {"python_module": "ExamplePack.nodes"}}

    def installer(packs):
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("ExamplePack", "installed", None, None),),
            preflight=PipPreflightResult(ok=True),
        )

    monkeypatch.setattr(ensure_env_module, "RuntimeSchemaProvider", FakeRuntimeSchemaProvider)

    result = ensure_env(
        workflow,
        known_packs=(_pack("ExamplePack"),),
        installer=installer,
    )

    assert result.ok is False
    assert [failure.code for failure in result.failures] == ["introspection_or_cache_failed"]
    assert "without git commit identity" in result.failures[0].message


def test_ensure_env_default_cache_write_uses_authored_semver_and_actual_head(monkeypatch) -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "SemverNode", "properties": {"cnr_id": "SemverPack", "ver": "1.2.3"}},
        ]
    }
    build_calls: list[tuple[object, str]] = []

    class FakeRuntimeSchemaProvider:
        def __init__(self, *, server_url=None):
            pass

        def object_info(self):
            return {"SemverNode": {"python_module": "SemverPack.nodes"}}

    def installer(packs, *, install_refs_by_name=None):
        assert install_refs_by_name["SemverPack"].version == "1.2.3"
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("SemverPack", "installed", "actualhead", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        return PackResolution(
            query=query,
            query_type="slug",
            ref=PackRef(slug="SemverPack", source="comfy-registry", version=version_pin, url="https://example.test/SemverPack.git"),
        )

    def fake_build_cache(source_path, *, version, identity, full_pack_refresh):
        build_calls.append((identity, version))
        return (1, 1)

    monkeypatch.setattr(ensure_env_module, "RuntimeSchemaProvider", FakeRuntimeSchemaProvider)
    monkeypatch.setattr(ensure_env_module, "build_cache", fake_build_cache)

    result = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        resolver=resolver,
    )

    assert result.ok is True
    identity, version = build_calls[0]
    assert version == "1.2.3"
    assert identity.pack_slug == "SemverPack"
    assert identity.pack_version == "1.2.3"
    assert identity.git_commit == "actualhead"


def test_ensure_env_default_cache_write_refuses_commit_pin_head_mismatch(monkeypatch) -> None:
    authored_commit = "1234567890abcdef1234567890abcdef12345678"
    workflow = {
        "nodes": [
            {"id": 1, "type": "PinnedNode", "properties": {"cnr_id": "PinnedPack", "ver": authored_commit}},
        ]
    }

    class FakeRuntimeSchemaProvider:
        def __init__(self, *, server_url=None):
            pass

        def object_info(self):
            return {"PinnedNode": {"python_module": "PinnedPack.nodes"}}

    def installer(packs, *, install_refs_by_name=None):
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("PinnedPack", "installed", "differenthead", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        return PackResolution(
            query=query,
            query_type="slug",
            ref=PackRef(
                slug="PinnedPack",
                source="comfy-registry",
                version=version_pin,
                commit=authored_commit,
                url="https://example.test/PinnedPack.git",
            ),
        )

    monkeypatch.setattr(ensure_env_module, "RuntimeSchemaProvider", FakeRuntimeSchemaProvider)

    result = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        resolver=resolver,
    )

    assert result.ok is False
    assert [failure.code for failure in result.failures] == ["introspection_or_cache_failed"]
    assert "does not match authored commit" in result.failures[0].message


def test_ensure_env_default_cache_write_warns_when_semver_head_is_unverifiable(monkeypatch) -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "SemverNode", "properties": {"cnr_id": "SemverPack", "ver": "1.2.3"}},
        ]
    }
    build_calls: list[object] = []

    class FakeRuntimeSchemaProvider:
        def __init__(self, *, server_url=None):
            pass

        def object_info(self):
            return {"SemverNode": {"python_module": "SemverPack.nodes"}}

    def installer(packs, *, install_refs_by_name=None):
        assert install_refs_by_name["SemverPack"].version == "1.2.3"
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("SemverPack", "installed", None, None),),
            preflight=PipPreflightResult(ok=True),
        )

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        return PackResolution(
            query=query,
            query_type="slug",
            ref=PackRef(slug="SemverPack", source="comfy-registry", version=version_pin, url="https://example.test/SemverPack.git"),
        )

    def fake_build_cache(source_path, *, version, identity, full_pack_refresh):
        build_calls.append((version, identity, full_pack_refresh))
        return (1, 1)

    monkeypatch.setattr(ensure_env_module, "RuntimeSchemaProvider", FakeRuntimeSchemaProvider)
    monkeypatch.setattr(ensure_env_module, "build_cache", fake_build_cache)

    result = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        resolver=resolver,
    )

    assert result.ok is True
    assert build_calls == []
    assert result.cache_write_result == {"written": {}}
    assert [warning.code for warning in result.warnings if warning.code == "cache_identity_unverified"] == [
        "cache_identity_unverified"
    ]
    assert result.pack_outcomes[0].cache_written is False


def test_ensure_env_second_call_is_noop_after_successful_realization(monkeypatch) -> None:
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())
    workflow = {
        "nodes": [
            {"id": 1, "type": "IdempotentNode", "properties": {"cnr_id": "IdempotentPack"}},
            {"id": 2, "type": "VAELoader", "properties": {"cnr_id": "comfy-core"}},
        ]
    }
    events: list[object] = []

    def installer(packs):
        events.append(("install", tuple(pack.name for pack in packs)))
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("IdempotentPack", "installed", "id123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(packs):
        events.append(("introspect", tuple(pack.name for pack in packs)))
        return {
            "IdempotentNode": {"python_module": "IdempotentPack.nodes"},
            "VAELoader": {"python_module": "."},
        }

    def cache_writer(payload):
        events.append(("cache", sorted(payload)))
        return {"written": sorted(payload)}

    first = ensure_env(
        workflow,
        known_packs=(_pack("IdempotentPack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )
    second = ensure_env(
        workflow,
        known_packs=(_pack("IdempotentPack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )

    assert first.ok is True
    assert first.noop is False
    assert second.ok is True
    assert second.noop is True
    assert second.install_batch is None
    assert second.introspection_result is None
    assert second.cache_write_result is None
    assert events == [
        ("install", ("IdempotentPack",)),
        ("introspect", ("IdempotentPack",)),
        ("cache", ["IdempotentPack", "comfy-core"]),
    ]


def test_ensure_env_aggregates_partial_failure_and_preflight_failure(monkeypatch) -> None:
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())
    workflow = {
        "nodes": [
            {"id": 1, "type": "OkNode", "properties": {"cnr_id": "OkPack"}},
            {"id": 2, "type": "FailedNode", "properties": {"cnr_id": "FailedPack"}},
        ]
    }

    def installer(packs):
        return InstallBatchResult(
            ok=False,
            results=(
                InstallResult("OkPack", "installed", "ok123", None),
                InstallResult("FailedPack", "failed", None, "pip failed"),
            ),
            preflight=PipPreflightResult(ok=False, error="joint preflight failed"),
        )

    result = ensure_env(
        workflow,
        known_packs=(_pack("OkPack"), _pack("FailedPack")),
        installer=installer,
    )

    assert result.ok is False
    assert result.noop is False
    assert {failure.code for failure in result.failures} == {
        "install_failed",
        "install_preflight_failed",
    }
    outcomes = {outcome.slug: outcome for outcome in result.pack_outcomes}
    assert outcomes["OkPack"].ok is True
    assert outcomes["FailedPack"].ok is False
    assert result.introspection_result is None
    assert result.cache_write_result is None


def test_ensure_env_cache_writer_resets_stale_object_info_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())
    monkeypatch.setattr(object_info_consume, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(object_info_consume, "INDEX_PATH", tmp_path / "index.json")
    object_info_consume.reset_cache()
    (tmp_path / "old.json").write_text(
        '{"FreshEvidenceNode": {"outputs": [{"name": "OLD", "type": "OLD"}]}}',
        encoding="utf-8",
    )
    (tmp_path / "index.json").write_text('{"FreshEvidenceNode": "old.json"}', encoding="utf-8")

    assert object_info_consume.output_names("FreshEvidenceNode") == ["OLD"]

    workflow = {
        "nodes": [
            {"id": 1, "type": "FreshEvidenceNode", "properties": {"cnr_id": "FreshPack"}},
        ]
    }
    cache_writes = 0

    def installer(packs):
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("FreshPack", "installed", "fresh123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def cache_writer(payload):
        nonlocal cache_writes
        cache_writes += 1
        assert payload == {"FreshPack": {"FreshEvidenceNode": {"python_module": "FreshPack.nodes"}}}
        (tmp_path / "fresh.json").write_text(
            '{"FreshEvidenceNode": {"outputs": [{"name": "NEW", "type": "NEW"}]}}',
            encoding="utf-8",
        )
        (tmp_path / "index.json").write_text('{"FreshEvidenceNode": "fresh.json"}', encoding="utf-8")
        return {"written": 1}

    result = ensure_env(
        workflow,
        known_packs=(_pack("FreshPack"),),
        installer=installer,
        introspector=lambda packs: {"FreshEvidenceNode": {"python_module": "FreshPack.nodes"}},
        cache_writer=cache_writer,
    )

    assert result.ok is True
    assert cache_writes == 1
    assert object_info_consume.output_names("FreshEvidenceNode") == ["NEW"]


def test_ensure_env_same_slug_different_version_avoids_noop_reuse(monkeypatch) -> None:
    """Prove that same slug/classes with a different authored version produces noop=False.

    The _realization_signature incorporates authored identity (slug, cnr_id, aux_id,
    version) and ref identity (slug, source, version, commit, url, path, registry_id).
    Changing the version pin must produce a different signature so the second call is
    NOT short-circuited as a noop.
    """
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())

    workflow_v1 = {
        "nodes": [
            {"id": 1, "type": "PackNode", "properties": {"cnr_id": "TestPack", "ver": "1.0.0"}},
        ]
    }
    workflow_v2 = {
        "nodes": [
            {"id": 1, "type": "PackNode", "properties": {"cnr_id": "TestPack", "ver": "2.0.0"}},
        ]
    }
    events: list[object] = []

    def installer(packs, *, install_refs_by_name=None):
        events.append(("install", tuple(pack.name for pack in packs)))
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("TestPack", "installed", "abc123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(packs):
        events.append(("introspect", tuple(pack.name for pack in packs)))
        return {"PackNode": {"python_module": "TestPack.nodes"}}

    def cache_writer(payload):
        events.append(("cache", sorted(payload)))
        return {"written": sorted(payload)}

    first = ensure_env(
        workflow_v1,
        known_packs=(_pack("TestPack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )
    second = ensure_env(
        workflow_v2,
        known_packs=(_pack("TestPack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )

    assert first.ok is True
    assert first.noop is False
    assert second.ok is True
    assert second.noop is False, (
        "same slug/classes with different authored version must NOT be a noop"
    )
    # Both calls fully executed the pipeline
    assert events == [
        ("install", ("TestPack",)),
        ("introspect", ("TestPack",)),
        ("cache", ["TestPack"]),
        ("install", ("TestPack",)),
        ("introspect", ("TestPack",)),
        ("cache", ["TestPack"]),
    ]


def test_ensure_env_same_slug_different_ref_identity_avoids_noop_reuse(monkeypatch) -> None:
    """Prove that same slug/classes with different install ref identity produces noop=False.

    The ref identity in _realization_signature is built from (slug, source, version,
    commit, url, path, registry_id). Two resolver paths that return different sources
    or URLs for the same slug must produce different signatures.
    """
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())

    workflow = {
        "nodes": [
            {"id": 1, "type": "PackNode", "properties": {"cnr_id": "TestPack", "ver": "1.0.0"}},
        ]
    }
    events: list[object] = []

    resolver_calls: list[object] = []

    def make_resolver(source: str, url: str):
        def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
            resolver_calls.append((source, query, version_pin))
            return PackResolution(
                query=query,
                query_type="slug",
                ref=PackRef(
                    slug="TestPack",
                    source=source,
                    version=version_pin,
                    url=url,
                ),
            )
        return resolver

    def installer(packs, *, install_refs_by_name=None):
        events.append(("install", tuple(pack.name for pack in packs)))
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("TestPack", "installed", "abc123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(packs):
        events.append(("introspect", tuple(pack.name for pack in packs)))
        return {"PackNode": {"python_module": "TestPack.nodes"}}

    def cache_writer(payload):
        events.append(("cache", sorted(payload)))
        return {"written": sorted(payload)}

    first = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
        resolver=make_resolver("comfy-registry", "https://example.test/TestPack.git"),
    )
    second = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
        resolver=make_resolver("git-proxy", "https://mirror.example.test/TestPack.git"),
    )

    assert first.ok is True
    assert first.noop is False
    assert second.ok is True
    assert second.noop is False, (
        "same slug/classes with different install ref identity must NOT be a noop"
    )
    # Both calls fully executed the pipeline
    assert events == [
        ("install", ("TestPack",)),
        ("introspect", ("TestPack",)),
        ("cache", ["TestPack"]),
        ("install", ("TestPack",)),
        ("introspect", ("TestPack",)),
        ("cache", ["TestPack"]),
    ]


def test_ensure_env_same_identity_second_call_is_noop(monkeypatch) -> None:
    """Confirm that _identical_ authored identity + ref identity + classes still produces noop=True.

    This is the positive counter-case to the regression tests above: when nothing
    relevant changes, the dedupe must still trigger.
    """
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())

    workflow = {
        "nodes": [
            {"id": 1, "type": "PackNode", "properties": {"cnr_id": "TestPack", "ver": "1.0.0"}},
        ]
    }
    events: list[object] = []

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        return PackResolution(
            query=query,
            query_type="slug",
            ref=PackRef(
                slug="TestPack",
                source="comfy-registry",
                version=version_pin,
                url="https://example.test/TestPack.git",
            ),
        )

    def installer(packs, *, install_refs_by_name=None):
        events.append(("install", tuple(pack.name for pack in packs)))
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("TestPack", "installed", "abc123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(packs):
        events.append(("introspect", tuple(pack.name for pack in packs)))
        return {"PackNode": {"python_module": "TestPack.nodes"}}

    def cache_writer(payload):
        events.append(("cache", sorted(payload)))
        return {"written": sorted(payload)}

    first = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
        resolver=resolver,
    )
    second = ensure_env(
        workflow,
        known_packs=(),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
        resolver=resolver,
    )

    assert first.ok is True
    assert first.noop is False
    assert second.ok is True
    assert second.noop is True, "identical realization inputs must still trigger noop"
    assert events == [
        ("install", ("TestPack",)),
        ("introspect", ("TestPack",)),
        ("cache", ["TestPack"]),
    ]


def test_ensure_env_core_refresh_does_not_clobber_custom_pack_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())
    cache_root = tmp_path / "cache_obj"
    cache_root.mkdir()
    monkeypatch.setattr(object_info_serialize, "CACHE_DIR", cache_root)
    monkeypatch.setattr(object_info_consume, "CACHE_DIR", cache_root)
    monkeypatch.setattr(object_info_consume, "INDEX_PATH", cache_root / "index.json")
    object_info_consume.reset_cache()

    real_build_cache = object_info_serialize.build_cache

    def scoped_build_cache(source_path, *, version, identity, full_pack_refresh):
        return real_build_cache(
            source_path,
            version=version,
            identity=identity,
            full_pack_refresh=full_pack_refresh,
            cache_dir=cache_root,
        )

    class FakeRuntimeSchemaProvider:
        payloads: list[dict[str, dict[str, str]]] = []

        def __init__(self, *, server_url=None):
            pass

        def object_info(self):
            return FakeRuntimeSchemaProvider.payloads.pop(0)

    monkeypatch.setattr(ensure_env_module, "RuntimeSchemaProvider", FakeRuntimeSchemaProvider)
    monkeypatch.setattr(ensure_env_module, "build_cache", scoped_build_cache)

    custom_workflow = {
        "nodes": [
            {"id": 1, "type": "ExamplePackNode", "properties": {"cnr_id": "ExamplePack", "ver": "1.2.3"}},
        ]
    }

    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        return PackResolution(
            query=query,
            query_type="slug",
            ref=PackRef(slug="ExamplePack", source="comfy-registry", version=version_pin, url="https://example.test/ExamplePack.git"),
        )

    def custom_installer(packs, *, install_refs_by_name=None):
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("ExamplePack", "installed", "customhead", None),),
            preflight=PipPreflightResult(ok=True),
        )

    FakeRuntimeSchemaProvider.payloads.append({"ExamplePackNode": {"python_module": "ExamplePack.nodes"}})
    first = ensure_env(
        custom_workflow,
        known_packs=(),
        installer=custom_installer,
        resolver=resolver,
    )

    core_workflow = {
        "nodes": [
            {"id": 2, "type": "VAELoader", "properties": {"cnr_id": "comfy-core"}},
        ]
    }
    FakeRuntimeSchemaProvider.payloads.append({"VAELoader": {"python_module": "."}})
    second = ensure_env(
        core_workflow,
        known_packs=(),
        installer=lambda packs: (_ for _ in ()).throw(AssertionError("core-only should not install")),
    )

    assert first.ok is True
    assert second.ok is True
    assert (cache_root / "ExamplePack@1.2.3.json").is_file()
    assert (cache_root / "comfy-core@runtime-core.json").is_file()
    index = (cache_root / "index.json").read_text(encoding="utf-8")
    assert "ExamplePack@1.2.3.json" in index
    assert "comfy-core@runtime-core.json" in index
