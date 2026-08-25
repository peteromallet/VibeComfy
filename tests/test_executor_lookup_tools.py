"""A02 tests: registry / node-schema / ready-template lookup tools.

Focused suite — no network, no plugins.  Registry lookups use a fake resolver
(typed ``MissingNodeResolution``), node-schema uses a fake provider, and
ready-template paths are exercised against ``tmp_path`` roots plus the real
repo template set where noted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.executor.lookup_tools import (
    EXACT_OWNERSHIP_SOURCES,
    LOOKUP_TOOLS,
    READY_CONTENT_CHAR_CAP,
    READY_IS_RESEARCH_EVIDENCE,
    REGISTRY_LOOKUP_BUDGET_PER_STAGE,
    RegistryLookupBudget,
    TOOL_NODE_SCHEMA,
    TOOL_READY_TEMPLATE_LIST,
    TOOL_READY_TEMPLATE_LOAD,
    TOOL_REGISTRY_LOOKUP,
    node_schema,
    ready_template_list,
    ready_template_load,
    registry_lookup,
)
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus
from vibecomfy.registry.pack_resolver import (
    MissingNodeResolution,
    PackRef,
    ResolverCandidate,
)
from vibecomfy.schema import NodeSchema, SchemaProvider
from vibecomfy.schema.types import InputSpec, OutputSpec


# ── Fixtures / fakes ─────────────────────────────────────────────────────────

def _candidate(
    *,
    slug: str = "comfyui-kjnodes",
    source: str = "comfyui-manager",
    expected_classes: tuple[str, ...] = ("SomeNodeKJ",),
) -> ResolverCandidate:
    return ResolverCandidate(
        ref=PackRef(slug=slug, source=source, name=slug),
        expected_classes=expected_classes,
        validation_mode="class_validatable" if source in EXACT_OWNERSHIP_SOURCES else "evidence_only",
    )


def _resolution(
    query: str,
    *,
    candidates: tuple[ResolverCandidate, ...] = (),
    warnings: tuple[str, ...] = (),
    attempted: tuple[str, ...] = ("comfyui-manager", "comfy-registry", "github"),
) -> MissingNodeResolution:
    return MissingNodeResolution(
        query=query,
        query_intent="class_name",
        candidates=candidates,
        warnings=warnings,
        source_tiers_attempted=attempted,
    )


class FakeResolver:
    """Resolver factory returning a canned MissingNodeResolution."""

    def __init__(self, resolution: MissingNodeResolution, *, error: Exception | None = None):
        self.resolution = resolution
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def __call__(self, query: str, *, query_intent: str | None = None, **kwargs: object) -> MissingNodeResolution:
        self.calls.append((query, query_intent or ""))
        if self.error is not None:
            raise self.error
        return self.resolution


class FakeProvider:
    """Minimal in-memory SchemaProvider."""

    def __init__(self, schemas: dict[str, NodeSchema] | None = None, *, error: Exception | None = None):
        self._schemas = schemas or {}
        self.error = error

    def get_schema(self, class_type: str) -> NodeSchema | None:
        if self.error is not None:
            raise self.error
        return self._schemas.get(class_type)


def _schema(
    class_type: str = "TestNode",
    *,
    pack: str | None = "test-pack",
    inputs: dict[str, InputSpec] | None = None,
    outputs: list[OutputSpec] | None = None,
    **provenance: object,
) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=pack,
        inputs=inputs if inputs is not None else {"seed": InputSpec(type="INT", required=True, default=0)},
        outputs=outputs if outputs is not None else [OutputSpec(type="IMAGE", name="IMAGE")],
        **provenance,
    )


def _write_template(root: Path, template_id: str, content: str = "def build():\n    pass\n") -> Path:
    path = root / f"{template_id}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ── registry_lookup ──────────────────────────────────────────────────────────

def test_registry_lookup_exact_manager_ownership_ok() -> None:
    resolver = FakeResolver(
        _resolution(
            "SomeNodeKJ",
            candidates=(_candidate(expected_classes=("SomeNodeKJ",)),),
        )
    )
    result = registry_lookup("SomeNodeKJ", resolver=resolver)

    assert result.status is ToolStatus.OK
    assert result.result["exact_ownership"] is True
    assert result.result["candidates"][0]["pack"]["slug"] == "comfyui-kjnodes"
    assert result.result["candidates"][0]["expected_classes"] == ("SomeNodeKJ",)
    assert result.result["is_research_evidence"] is True
    assert result.evidence_ids == ()


def test_registry_lookup_exact_registry_ownership_ok() -> None:
    resolver = FakeResolver(
        _resolution(
            "ImageResizeKJv2",
            candidates=(
                _candidate(slug="comfyui-kjnodes", source="comfy-registry", expected_classes=("ImageResizeKJv2",)),
            ),
        )
    )
    result = registry_lookup("ImageResizeKJv2", resolver=resolver)

    assert result.status is ToolStatus.OK
    assert result.result["candidates"][0]["pack"]["source"] == "comfy-registry"


def test_registry_lookup_github_evidence_never_implies_ownership() -> None:
    # GitHub candidates carry the queried class in expected_classes (search
    # text) but are not an authoritative tier — they must NOT be promoted.
    resolver = FakeResolver(
        _resolution(
            "SomeNodeKJ",
            candidates=(_candidate(source="github", expected_classes=("SomeNodeKJ",)),),
        )
    )
    result = registry_lookup("SomeNodeKJ", resolver=resolver)

    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["exact_ownership"] is False
    assert result.result["candidates"] == ()
    assert result.diagnostics[0].code == "no_exact_ownership"
    assert "SomeNodeKJ" in result.diagnostics[0].message


def test_registry_lookup_authoritative_candidate_without_class_declaration_is_not_promoted() -> None:
    # A manager candidate that matched the query but declares a DIFFERENT class
    # in expected_classes is not exact ownership of the queried class.
    resolver = FakeResolver(
        _resolution(
            "WantedClass",
            candidates=(_candidate(expected_classes=("OtherClass",)),),
        )
    )
    result = registry_lookup("WantedClass", resolver=resolver)

    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["exact_ownership"] is False
    assert result.result["candidates"] == ()
    assert result.diagnostics[0].code == "no_exact_ownership"


def test_registry_lookup_unknown_class_no_results() -> None:
    resolver = FakeResolver(_resolution("TotallyUnknown"))
    result = registry_lookup("TotallyUnknown", resolver=resolver)

    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["exact_ownership"] is False
    assert result.result["candidates"] == ()
    assert result.diagnostics[0].code == "no_pack_found"


def test_registry_lookup_capability_query_is_invalid_request() -> None:
    result = registry_lookup("video generation", resolver=FakeResolver(_resolution("video generation")))

    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.diagnostics[0].code == "capability_query_rejected"
    assert "replacement" in result.diagnostics[0].message


def test_registry_lookup_empty_class_is_invalid_request() -> None:
    result = registry_lookup("   ", resolver=FakeResolver(_resolution("")))

    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.diagnostics[0].code == "empty_node_class"


def test_registry_lookup_budget_is_one_per_stage() -> None:
    budget = RegistryLookupBudget()
    resolver = FakeResolver(
        _resolution(
            "SomeNodeKJ",
            candidates=(_candidate(expected_classes=("SomeNodeKJ",)),),
        )
    )
    first = registry_lookup("SomeNodeKJ", resolver=resolver, budget=budget)
    second = registry_lookup("SomeNodeKJ", resolver=resolver, budget=budget)

    assert first.status is ToolStatus.OK
    assert second.status is ToolStatus.REFUSED
    assert second.diagnostics[0].code == "registry_budget_exhausted"
    assert second.result["node_class"] == "SomeNodeKJ"
    assert len(resolver.calls) == 1


def test_registry_lookup_budget_defaults_to_one() -> None:
    assert RegistryLookupBudget().remaining == REGISTRY_LOOKUP_BUDGET_PER_STAGE
    budget = RegistryLookupBudget()
    assert budget.consume() is True
    assert budget.consume() is False
    assert budget.exhausted is True


def test_registry_lookup_rate_limited_is_not_absence_of_evidence() -> None:
    resolver = FakeResolver(
        _resolution(
            "SomeNodeKJ",
            warnings=("GitHub code search rate-limited (403); GitHub tier skipped for cooldown.",),
        )
    )
    result = registry_lookup("SomeNodeKJ", resolver=resolver)

    assert result.status is ToolStatus.RATE_LIMITED
    assert result.diagnostics[0].code == "registry_rate_limited"


def test_registry_lookup_rate_limit_with_exact_evidence_still_ok() -> None:
    # A rate limit on one tier must never hide exact ownership found elsewhere.
    resolver = FakeResolver(
        _resolution(
            "SomeNodeKJ",
            candidates=(_candidate(expected_classes=("SomeNodeKJ",)),),
            warnings=("GitHub code search rate-limited (403); GitHub tier skipped for cooldown.",),
        )
    )
    result = registry_lookup("SomeNodeKJ", resolver=resolver)

    assert result.status is ToolStatus.OK
    assert result.result["exact_ownership"] is True


def test_registry_lookup_timeout_is_typed() -> None:
    resolver = FakeResolver(
        _resolution(
            "SomeNodeKJ",
            warnings=("registry sub-budget exceeded during ComfyUI-Manager lookup; partial evidence.",),
        )
    )
    result = registry_lookup("SomeNodeKJ", resolver=resolver)

    assert result.status is ToolStatus.TIMEOUT
    assert result.diagnostics[0].code == "registry_timeout"


def test_registry_lookup_transport_failure_is_unavailable() -> None:
    resolver = FakeResolver(_resolution("SomeNodeKJ"), error=RuntimeError("connection refused"))
    result = registry_lookup("SomeNodeKJ", resolver=resolver)

    assert result.status is ToolStatus.UNAVAILABLE
    assert result.diagnostics[0].code == "registry_lookup_unavailable"


# ── node_schema ──────────────────────────────────────────────────────────────

def test_node_schema_known_class_ok() -> None:
    provider = FakeProvider(
        {
            "TestNode": _schema(
                inputs={
                    "seed": InputSpec(type="INT", required=True, default=0),
                    "model": InputSpec(type="MODEL", required=False),
                    "positive": InputSpec(type="CONDITIONING", required=True),
                },
                outputs=[OutputSpec(type="LATENT", name="LATENT")],
                source_provider="object_info_cache",
                source_package="test-pack",
                confidence=0.9,
            )
        }
    )
    result = node_schema("TestNode", provider=provider)

    assert result.status is ToolStatus.OK
    body = result.result
    assert body["available"] is True
    assert body["pack"] == "test-pack"
    assert [row["name"] for row in body["inputs"]] == ["model", "positive", "seed"]
    seed = next(row for row in body["inputs"] if row["name"] == "seed")
    assert seed["required"] is True
    assert seed["default"] == 0
    assert seed["type"] == "INT"
    assert body["output_count"] == 1
    assert body["outputs"][0]["type"] == "LATENT"
    assert body["provenance"]["source_provider"] == "object_info_cache"
    assert body["provenance"]["confidence"] == 0.9
    assert body["is_research_evidence"] is True


def test_node_schema_unknown_class_no_results() -> None:
    result = node_schema("NoSuchClass", provider=FakeProvider())

    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["available"] is False
    assert result.diagnostics[0].code == "class_not_found"


def test_node_schema_empty_class_invalid_request() -> None:
    result = node_schema("", provider=FakeProvider())

    assert result.status is ToolStatus.INVALID_REQUEST


def test_node_schema_provider_failure_is_unavailable() -> None:
    result = node_schema("TestNode", provider=FakeProvider(error=OSError("index unreadable")))

    assert result.status is ToolStatus.UNAVAILABLE
    assert result.diagnostics[0].code == "schema_provider_unavailable"


def test_node_schema_stub_schema_is_flagged() -> None:
    provider = FakeProvider(
        {
            "StubNode": _schema(class_type="StubNode", source_version="stub"),
        }
    )
    result = node_schema("StubNode", provider=provider)

    assert result.status is ToolStatus.OK
    assert result.result["stub_schema"] is True


def test_node_schema_real_offline_provider_resolves_ksampler() -> None:
    result = node_schema("KSampler")

    assert result.status is ToolStatus.OK
    assert result.result["available"] is True
    assert result.result["pack"] == "comfy_core"
    assert "model" in result.result["input_names"]


# ── ready_template_list ──────────────────────────────────────────────────────

def test_ready_template_list_lists_rows_from_roots(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")
    _write_template(tmp_path, "audio/qwen_tts", content="def build():\n    return None\n")
    (tmp_path / "_private.py").write_text("", encoding="utf-8")

    result = ready_template_list(roots=[tmp_path])

    assert result.status is ToolStatus.OK
    assert result.result["count"] == 2
    ids = [row["id"] for row in result.result["templates"]]
    assert ids == ["audio/qwen_tts", "video/wan_t2v"]
    assert result.result["is_research_evidence"] is False
    assert result.result["evidence_label"] == "direct_asset"


def test_ready_template_list_capability_filter(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")
    _write_template(tmp_path, "audio/qwen_tts")
    _write_template(tmp_path, "image/flux_t2i")

    result = ready_template_list("wan", roots=[tmp_path])

    assert result.status is ToolStatus.OK
    assert result.result["filter"] == "wan"
    assert [row["id"] for row in result.result["templates"]] == ["video/wan_t2v"]


def test_ready_template_list_capability_no_match_is_no_results(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")

    result = ready_template_list("sdxl", roots=[tmp_path])

    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["count"] == 0
    assert result.diagnostics[0].code == "no_ready_templates"


def test_ready_template_list_empty_root_is_no_results(tmp_path: Path) -> None:
    result = ready_template_list(roots=[tmp_path])

    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["count"] == 0


def test_ready_template_list_invalid_capability(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")

    result = ready_template_list(123, roots=[tmp_path])  # type: ignore[arg-type]

    assert result.status is ToolStatus.INVALID_REQUEST


def test_ready_template_list_real_repo_templates() -> None:
    result = ready_template_list("wan")

    assert result.status is ToolStatus.OK
    assert result.result["count"] >= 1
    assert all(row["id"].startswith(("video/", "audio/", "image/", "edit/")) for row in result.result["templates"])


# ── ready_template_load ──────────────────────────────────────────────────────

def test_ready_template_load_stable_identity_and_hash(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v", content="def build():\n    return 42\n")

    first = ready_template_load("video/wan_t2v", roots=[tmp_path])
    second = ready_template_load("video/wan_t2v", roots=[tmp_path])

    assert first.status is ToolStatus.OK
    assert second.status is ToolStatus.OK
    assert first.result["id"] == "video/wan_t2v"
    assert first.result["sha256"] == second.result["sha256"]
    assert first.result["size_bytes"] == second.result["size_bytes"]
    assert first.result["content"] == "def build():\n    return 42\n"
    assert first.result["content_truncated"] is False
    assert first.result["is_research_evidence"] is False
    assert first.result["evidence_label"] == "direct_asset"
    assert first.evidence_ids == ()


def test_ready_template_load_flat_id_resolves_via_shallow_glob(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")

    result = ready_template_load("wan_t2v", roots=[tmp_path])

    assert result.status is ToolStatus.OK
    assert result.result["id"] == "video/wan_t2v"
    assert result.result["requested_id"] == "wan_t2v"


def test_ready_template_load_hash_changes_with_content(tmp_path: Path) -> None:
    path = _write_template(tmp_path, "video/wan_t2v", content="def build():\n    return 1\n")
    before = ready_template_load("video/wan_t2v", roots=[tmp_path]).result["sha256"]

    path.write_text("def build():\n    return 2\n", encoding="utf-8")
    after = ready_template_load("video/wan_t2v", roots=[tmp_path]).result["sha256"]

    assert before != after


def test_ready_template_load_traversal_refused(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"
    outside.write_text("secret", encoding="utf-8")

    for hostile in ("../outside", "../../etc/passwd", "/etc/passwd", "~/.bashrc", "a/../b"):
        result = ready_template_load(hostile, roots=[tmp_path])
        assert result.status is ToolStatus.REFUSED, hostile
        assert result.diagnostics[0].code == "template_path_escape_refused", hostile


def test_ready_template_load_symlink_escape_refused(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret_asset.py"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "innocent.py"
    link.symlink_to(outside)

    result = ready_template_load("innocent", roots=[tmp_path])

    assert result.status is ToolStatus.REFUSED
    assert result.diagnostics[0].code == "template_path_escape_refused"


def test_ready_template_load_missing_is_no_results(tmp_path: Path) -> None:
    result = ready_template_load("video/does_not_exist", roots=[tmp_path])

    assert result.status is ToolStatus.NO_RESULTS
    assert result.diagnostics[0].code == "template_not_found"


def test_ready_template_load_empty_id_invalid_request(tmp_path: Path) -> None:
    result = ready_template_load("", roots=[tmp_path])

    assert result.status is ToolStatus.INVALID_REQUEST


def test_ready_template_load_content_truncation(tmp_path: Path) -> None:
    big = ("x" * 1000) + "\n"
    _write_template(tmp_path, "video/big", content=big * (READY_CONTENT_CHAR_CAP // len(big) + 2))

    result = ready_template_load("video/big", roots=[tmp_path])

    assert result.status is ToolStatus.OK
    assert result.result["content_truncated"] is True
    assert len(result.result["content"]) == READY_CONTENT_CHAR_CAP


def test_ready_template_load_real_repo_template() -> None:
    result = ready_template_load("video/wan_t2v")

    assert result.status is ToolStatus.OK
    assert result.result["id"] == "video/wan_t2v"
    assert result.result["scope"] == "repo"
    assert result.result["sha256"]
    assert result.result["content"].strip()


# ── Typed contract / registry surface ────────────────────────────────────────

def test_lookup_tool_results_round_trip_through_typed_contract(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")
    result = ready_template_load("video/wan_t2v", roots=[tmp_path])
    assert result.status is ToolStatus.OK

    restored = ToolResult.from_dict(result.to_dict())

    assert restored == result
    assert restored.tool_name == TOOL_READY_TEMPLATE_LOAD


def test_lookup_tools_registry_exposes_all_four_tools() -> None:
    assert set(LOOKUP_TOOLS) == {
        TOOL_REGISTRY_LOOKUP,
        TOOL_NODE_SCHEMA,
        TOOL_READY_TEMPLATE_LIST,
        TOOL_READY_TEMPLATE_LOAD,
    }


def test_ready_templates_are_explicitly_not_research_evidence(tmp_path: Path) -> None:
    _write_template(tmp_path, "video/wan_t2v")
    listed = ready_template_list(roots=[tmp_path])
    loaded = ready_template_load("video/wan_t2v", roots=[tmp_path])

    assert listed.result["is_research_evidence"] is READY_IS_RESEARCH_EVIDENCE
    assert loaded.result["is_research_evidence"] is READY_IS_RESEARCH_EVIDENCE
    assert listed.result["evidence_label"] == "direct_asset"
    assert loaded.result["evidence_label"] == "direct_asset"
    assert listed.evidence_ids == ()
    assert loaded.evidence_ids == ()


def _frozen_admission_provider(class_types: tuple[str, ...]) -> Any:
    """Frozen admission authority over exactly *class_types*."""
    from vibecomfy.schema.types import (
        FrozenSchemaSnapshotProvider,
        capture_schema_snapshot,
        schema_payload_from_node_schema,
    )

    schemas = {}
    for class_type in class_types:
        schemas[class_type] = schema_payload_from_node_schema(
            class_type,
            _schema(
                inputs={"value": InputSpec(type="INT", required=True)},
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
            ),
        )
    snap = capture_schema_snapshot(
        class_types=list(class_types),
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": schemas,
            "missing_classes": [],
        },
        node_classes={str(i + 1): ct for i, ct in enumerate(class_types)},
    )
    return FrozenSchemaSnapshotProvider(snap)


def test_node_schema_labels_hit_unavailable_to_current_admission() -> None:
    """RRSYN-5: ambient hit outside the frozen snapshot is labeled inadmissible."""
    provider = FakeProvider(
        {
            "GhostNode": _schema(
                inputs={"value": InputSpec(type="INT", required=True)},
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
            )
        }
    )
    admission = _frozen_admission_provider(("OtherNode",))
    result = node_schema("GhostNode", provider=provider, admission_provider=admission)

    assert result.status is ToolStatus.OK
    body = result.result
    assert body["available"] is True
    assert body["admissible"] is False
    assert "frozen" in str(body["admission_note"])


def test_node_schema_hit_inside_admission_is_admissible() -> None:
    provider = FakeProvider(
        {
            "KnownNode": _schema(
                inputs={"value": InputSpec(type="INT", required=True)},
                outputs=[],
            )
        }
    )
    admission = _frozen_admission_provider(("KnownNode",))
    result = node_schema("KnownNode", provider=provider, admission_provider=admission)

    assert result.status is ToolStatus.OK
    assert result.result["admissible"] is True
    assert result.result["admission_note"] is None


def test_node_schema_without_admission_provider_defaults_admissible() -> None:
    provider = FakeProvider(
        {
            "TestNode": _schema(
                inputs={"value": InputSpec(type="INT", required=True)},
                outputs=[],
            )
        }
    )
    result = node_schema("TestNode", provider=provider)
    assert result.result["admissible"] is True
