from __future__ import annotations

from pathlib import Path

from vibecomfy.node_packs import CustomNodePack
from vibecomfy.node_packs_install import InstallBatchResult, InstallResult, PipPreflightResult
from vibecomfy.porting.object_info import consume as object_info_consume
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
