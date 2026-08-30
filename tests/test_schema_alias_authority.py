"""Adversarial schema alias and provider-authority regression tests."""

from __future__ import annotations

import pytest

from vibecomfy.comfy_nodes.agent._frag_ingest import _ensure_ingest_workflow
from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    _graph_class_types,
    capture_ingress_schema_snapshot,
)
from vibecomfy.porting.edit._ir_utils import _resolve_class_type_from_alias
from vibecomfy.porting.widgets.aliases import resolve_widget_name_with_provenance
from vibecomfy.schema import (
    NodeSchema,
    SchemaProviderError,
    SchemaSnapshotError,
    capture_schema_snapshot,
    schema_for,
    schema_snapshot_to_payload,
)
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider


def _schema(class_type: str) -> NodeSchema:
    return NodeSchema(class_type=class_type, pack="test", inputs={}, outputs=[])


class _Provider:
    def __init__(self, names: list[str]) -> None:
        self._schemas = {name: _schema(name) for name in names}

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return dict(self._schemas)


def test_identifier_and_case_aliases_resolve_to_the_unique_authority() -> None:
    provider = _Provider(["Foo Bar"])

    assert _resolve_class_type_from_alias("Foo_Bar", provider) == "Foo Bar"
    assert _resolve_class_type_from_alias("foo bar", provider) == "Foo Bar"


@pytest.mark.parametrize("alias", ["FOO", "foo_bar"])
def test_ambiguous_case_or_identifier_aliases_fail_closed(alias: str) -> None:
    provider = _Provider(["Foo", "foo", "Foo Bar", "Foo_Bar"])

    with pytest.raises(ValueError, match="ambiguous"):
        _resolve_class_type_from_alias(alias, provider)


def test_ingress_snapshot_binds_unique_aliases_in_cold_and_warm_captures() -> None:
    provider = _Provider(["Foo Bar"])
    graph = {"nodes": [{"id": "1", "type": "Foo_Bar"}]}

    cold = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    warm = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)

    assert cold.missing_classes == ()
    assert cold.content_digest == warm.content_digest
    # Keep the graph spelling available to the frozen provider while retaining
    # the raw provider spelling as a separate authoritative entry.
    assert set(cold.schemas) == {"Foo Bar", "Foo_Bar"}


def test_ingress_does_not_record_ambiguous_alias_as_missing() -> None:
    provider = _Provider(["Foo", "foo"])

    with pytest.raises(SchemaSnapshotError, match="schema_provider_error.*ambiguous") as excinfo:
        capture_ingress_schema_snapshot(
            schema_provider=provider,
            graph={"nodes": [{"id": "1", "type": "FOO"}]},
        )
    assert excinfo.value.code == "schema_provider_error"


class _FailingProvider:
    def get_schema(self, class_type: str) -> NodeSchema | None:
        raise RuntimeError(f"boom:{class_type}")


class _FailingEnumerationProvider(_FailingProvider):
    def schemas(self) -> dict[str, NodeSchema]:
        raise OSError("index unreadable")


def test_provider_getter_failure_is_typed_not_a_schema_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FailingProvider()

    with pytest.raises(SchemaProviderError, match="'BrokenNode'"):
        schema_for(provider, "BrokenNode")
    with pytest.raises(SchemaSnapshotError, match="schema_provider_error.*BrokenNode") as excinfo:
        capture_ingress_schema_snapshot(
            schema_provider=provider,
            graph={"nodes": [{"id": "1", "type": "BrokenNode"}]},
        )
    assert excinfo.value.code == "schema_provider_error"

    from vibecomfy.porting.object_info import consume

    monkeypatch.setattr("vibecomfy.schema.provider.get_authoring_schema_provider", lambda: provider)
    with pytest.raises(SchemaProviderError, match="'BrokenNode'"):
        consume.class_is_known("BrokenNode")


def test_widget_alias_does_not_convert_provider_failure_to_unresolved() -> None:
    with pytest.raises(SchemaProviderError, match="'BrokenNode'"):
        resolve_widget_name_with_provenance(
            "BrokenNode", 0, schema_provider=_FailingProvider(), allow_object_info_fallback=False
        )


def test_provider_enumeration_failure_is_not_treated_as_no_aliases() -> None:
    with pytest.raises(SchemaProviderError, match="index unreadable"):
        _resolve_class_type_from_alias("BrokenNode", _FailingEnumerationProvider())


@pytest.mark.parametrize("listing_only", [False, True])
def test_ingress_rejects_present_non_mapping_enumeration(listing_only: bool) -> None:
    class _MalformedEnumerationProvider:
        def __init__(self) -> None:
            self.listing_only = listing_only

        def schemas(self) -> list[object]:
            return []

        def get_schema(self, _class_type: str) -> None:
            return None

    with pytest.raises(SchemaSnapshotError, match="schema_provider_error") as excinfo:
        capture_ingress_schema_snapshot(
            schema_provider=_MalformedEnumerationProvider(),
            graph={"nodes": [{"type": "BrokenNode"}]},
        )
    assert excinfo.value.code == "schema_provider_error"


def test_exact_raw_id_wins_over_identifier_collision() -> None:
    provider = _Provider(["Foo Bar", "Foo_Bar"])

    assert _resolve_class_type_from_alias("Foo Bar", provider) == "Foo Bar"
    assert _resolve_class_type_from_alias("Foo_Bar", provider) == "Foo_Bar"
    with pytest.raises(ValueError, match="ambiguous"):
        _resolve_class_type_from_alias("foo_bar", provider)


class _ChangingSurfaceProvider:
    def __init__(self) -> None:
        self.calls = 0
        self._foo = _schema("Foo Bar")
        self._other = _schema("Other")

    def schemas(self) -> dict[str, NodeSchema]:
        self.calls += 1
        return {"Foo Bar": self._foo} if self.calls == 1 else {"Other": self._other}

    def get_schema(self, class_type: str) -> NodeSchema | None:
        # The second surface is deliberately different. A correct ingress
        # capture must keep using the first physical listing it took.
        return {"Foo Bar": self._foo}.get(class_type) if self.calls == 1 else {"Other": self._other}.get(class_type)


def test_ingress_uses_one_immutable_surface_enumeration() -> None:
    provider = _ChangingSurfaceProvider()

    snapshot = capture_ingress_schema_snapshot(
        schema_provider=provider,
        graph={"nodes": [{"id": "1", "type": "Foo_Bar"}]},
    )

    assert provider.calls == 1
    assert snapshot.missing_classes == ()
    assert set(snapshot.schemas) == {"Foo Bar", "Foo_Bar"}


def test_index_listing_does_not_read_pack_files(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    (root / "index.json").write_text('{"FooNode": "foo.json"}', encoding="utf-8")
    reads: list[str] = []

    def _load(path: object) -> dict[str, str] | None:
        reads.append(str(path))
        if str(path).endswith("index.json"):
            return {"FooNode": "foo.json"}
        return None

    monkeypatch.setattr("vibecomfy.schema.provider.load_object_info_cache", _load)
    provider = ObjectInfoIndexSchemaProvider(root)

    listing = provider.schemas()

    assert list(listing) == ["FooNode"]
    assert reads == [str(root / "index.json")]


def test_composed_listing_does_not_materialize_index_packs() -> None:
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from vibecomfy.schema.provider import CompositeSchemaProvider

    with TemporaryDirectory() as directory:
        provider = ObjectInfoIndexSchemaProvider(Path(directory))
        provider._index = {"A": "a.json", "B": "b.json"}
        reads: list[str] = []
        provider._load_pack = lambda filename, class_type: (
            reads.append(filename) or {class_type: {"input": {}, "output": []}}
        )

        listing = CompositeSchemaProvider(provider).schemas()

    assert listing == {"A": None, "B": None}
    assert reads == []


def test_authoring_listing_does_not_materialize_index_packs() -> None:
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from vibecomfy.schema.provider import AuthoringSchemaProvider

    with TemporaryDirectory() as directory:
        provider = ObjectInfoIndexSchemaProvider(Path(directory))
        provider._index = {"A": "a.json", "B": "b.json"}
        reads: list[str] = []
        provider._load_pack = lambda filename, class_type: (
            reads.append(filename) or {class_type: {"input": {}, "output": []}}
        )
        authoring = AuthoringSchemaProvider.__new__(AuthoringSchemaProvider)
        authoring._providers = (provider,)

        listing = authoring.schemas()

    assert listing == {"A": None, "B": None}
    assert reads == []


def test_composed_ingress_fetches_only_graph_requested_index_pack(tmp_path: object) -> None:
    from pathlib import Path

    from vibecomfy.schema.provider import CompositeSchemaProvider

    root = Path(str(tmp_path))
    (root / "index.json").write_text(
        '{"A": "a.json", "Unused": "broken.json"}', encoding="utf-8"
    )
    (root / "a.json").write_text(
        '{"A": {"input": {"required": {}}, "output": []}}', encoding="utf-8"
    )
    (root / "broken.json").write_text("not-json", encoding="utf-8")

    snapshot = capture_ingress_schema_snapshot(
        schema_provider=CompositeSchemaProvider(ObjectInfoIndexSchemaProvider(root)),
        graph={"nodes": [{"type": "A"}]},
    )

    assert snapshot.missing_classes == ()
    assert "A" in snapshot.schemas


def test_index_alias_capture_is_warm_cold_digest_stable(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    (root / "index.json").write_text('{"Foo Bar": "foo.json"}', encoding="utf-8")
    (root / "foo.json").write_text(
        '{"Foo Bar": {"input": {"required": {"x": ["INT", {}]}}, '
        '"output": ["INT"], "output_name": ["out"], '
        '"output_is_list": [false], "category": "test"}}',
        encoding="utf-8",
    )
    graph = {"nodes": [{"id": "1", "type": "Foo_Bar"}]}

    cold_provider = ObjectInfoIndexSchemaProvider(root)
    cold = capture_ingress_schema_snapshot(schema_provider=cold_provider, graph=graph)
    warm_provider = ObjectInfoIndexSchemaProvider(root)
    assert warm_provider.get_schema("Foo Bar") is not None
    warm = capture_ingress_schema_snapshot(schema_provider=warm_provider, graph=graph)

    assert cold.content_digest == warm.content_digest
    assert cold.missing_classes == warm.missing_classes == ()
    assert set(cold.schemas) == set(warm.schemas) == {"Foo_Bar"}


def test_corrupt_indexed_pack_is_typed_provider_error(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    (root / "index.json").write_text('{"BrokenNode": "broken.json"}', encoding="utf-8")
    (root / "broken.json").write_text("not-json", encoding="utf-8")
    provider = ObjectInfoIndexSchemaProvider(root)

    with pytest.raises(SchemaProviderError, match="BrokenNode"):
        schema_for(provider, "BrokenNode")


def test_existing_corrupt_index_is_typed_not_an_empty_listing(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    (root / "index.json").write_bytes(b"not valid utf-8: \xff")
    provider = ObjectInfoIndexSchemaProvider(root)

    with pytest.raises(SchemaProviderError, match="schema index"):
        provider.schemas()
    with pytest.raises(SchemaSnapshotError, match="schema_provider_error"):
        capture_ingress_schema_snapshot(
            schema_provider=ObjectInfoIndexSchemaProvider(root),
            graph={"nodes": [{"type": "BrokenNode"}]},
        )


def test_indexed_pack_missing_advertised_class_is_typed_not_a_schema_miss(
    tmp_path: object,
) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    (root / "index.json").write_text('{"AdvertisedNode": "pack.json"}', encoding="utf-8")
    (root / "pack.json").write_text('{"DifferentNode": {}}', encoding="utf-8")
    provider = ObjectInfoIndexSchemaProvider(root)

    with pytest.raises(SchemaProviderError, match="AdvertisedNode"):
        schema_for(provider, "AdvertisedNode")
    with pytest.raises(SchemaSnapshotError, match="schema_provider_error.*AdvertisedNode"):
        capture_ingress_schema_snapshot(
            schema_provider=ObjectInfoIndexSchemaProvider(root),
            graph={"nodes": [{"type": "AdvertisedNode"}]},
        )


def test_composed_listing_only_consumers_focus_fetch_without_fake_rows_or_crash(
    tmp_path: object,
) -> None:
    from pathlib import Path

    from vibecomfy.porting.emit.signatures import emit_available_node_signatures
    from vibecomfy.search.index import _object_info_entries
    from vibecomfy.schema.provider import AuthoringSchemaProvider, CompositeSchemaProvider

    root = Path(str(tmp_path))
    (root / "index.json").write_text('{"A": "a.json"}', encoding="utf-8")
    (root / "a.json").write_text(
        '{"A": {"input": {"required": {"x": ["INT"]}}, '
        '"output": ["INT"], "output_name": ["out"]}}',
        encoding="utf-8",
    )
    index_provider = ObjectInfoIndexSchemaProvider(root)
    composite = CompositeSchemaProvider(index_provider)
    authoring = AuthoringSchemaProvider.__new__(AuthoringSchemaProvider)
    authoring._providers = (index_provider,)

    for provider in (composite, authoring):
        assert provider.listing_only is True
        assert provider.schemas() == {"A": None}
        rows = emit_available_node_signatures(provider)
        assert len(rows) == 1
        assert rows[0].class_type == "A"
        assert [field.name for field in rows[0].inputs] == ["x"]
        entries = _object_info_entries(provider)
        assert [entry.class_type for entry in entries] == ["A"]
def test_ingest_helper_does_not_warm_or_swallow_provider_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    import vibecomfy.ingest.normalize as normalize

    provider = _ChangingSurfaceProvider()
    workflow = object()
    monkeypatch.setattr(
        normalize,
        "ingest_workflow_and_ui",
        lambda graph, *, schema_provider: (workflow, graph),
    )
    state = SimpleNamespace(
        workflow=None,
        workflow_snapshot=None,
        graph={"nodes": [{"id": "1", "type": "BrokenNode"}]},
        schema_provider=provider,
        baseline_graph_hash=None,
        session_dir=None,
        turn_dir=None,
    )

    assert _ensure_ingest_workflow(state) is workflow
    assert provider.calls == 0

    def _raise_ingest(graph: object, *, schema_provider: object) -> object:
        raise SchemaProviderError("BrokenNode", OSError("index unreadable"))

    state.workflow = None
    monkeypatch.setattr(normalize, "ingest_workflow_and_ui", _raise_ingest)
    with pytest.raises(SchemaProviderError, match="index unreadable"):
        _ensure_ingest_workflow(state)


def test_unicode_equivalent_class_ids_share_alias_collision_authority() -> None:
    provider = _Provider(["Café", "Cafe\u0301"])

    assert _resolve_class_type_from_alias("Café", provider) == "Café"
    assert _resolve_class_type_from_alias("Cafe\u0301", provider) == "Cafe\u0301"
    with pytest.raises(ValueError, match="ambiguous"):
        _resolve_class_type_from_alias("caf", provider)


@pytest.mark.parametrize("filename", ["../outside.json", "/tmp/outside.json"])
def test_indexed_pack_paths_cannot_escape_root(
    tmp_path: object,
    filename: str,
) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    (root / "index.json").write_text(
        '{"EscapeNode": ' + repr(filename).replace("'", '"') + "}",
        encoding="utf-8",
    )
    provider = ObjectInfoIndexSchemaProvider(root)

    with pytest.raises(SchemaProviderError, match="indexed pack"):
        schema_for(provider, "EscapeNode")


def test_indexed_pack_symlink_escape_is_rejected(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path)) / "root"
    outside = Path(str(tmp_path)) / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "pack.json").write_text("{}", encoding="utf-8")
    (root / "link").symlink_to(outside, target_is_directory=True)
    (root / "index.json").write_text(
        '{"EscapeNode": "link/pack.json"}',
        encoding="utf-8",
    )

    with pytest.raises(SchemaProviderError, match="escapes authority root"):
        schema_for(ObjectInfoIndexSchemaProvider(root), "EscapeNode")


def test_schema_snapshot_is_deeply_immutable_and_roundtrips_digest() -> None:
    snapshot = capture_schema_snapshot(
        class_types=["KnownNode"],
        connected_object_info={
            "KnownNode": {
                "input": {"required": {"nested": ["STRING", {"default": {"a": [1]}}]}},
                "output": [],
            }
        },
        connected_object_info_verified=True,
    )

    with pytest.raises(TypeError):
        snapshot.schemas["KnownNode"] = {}
    with pytest.raises(TypeError):
        snapshot.schemas["KnownNode"]["inputs"]["nested"]["default"]["a"] += (2,)
    assert schema_snapshot_to_payload(snapshot)["content_digest"] == snapshot.content_digest


def test_schema_graph_cycles_and_oversize_fail_closed_typedly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle: dict[str, object] = {}
    cycle["definitions"] = {"self": cycle}
    with pytest.raises(SchemaSnapshotError) as cycle_error:
        _graph_class_types(cycle)
    assert cycle_error.value.code == "schema_graph_cycle"

    import vibecomfy.comfy_nodes.agent.candidate_transaction as transaction

    monkeypatch.setattr(transaction, "MAX_GRAPH_TRAVERSAL_ITEMS", 3)
    with pytest.raises(SchemaSnapshotError) as size_error:
        _graph_class_types({"nodes": [{"type": "A"}, {"type": "B"}, {"type": "C"}]})
    assert size_error.value.code == "schema_graph_items_exceeded"


def test_index_materialization_is_bounded_by_bytes_and_entries(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path
    import vibecomfy.schema.provider as provider_module

    root = Path(str(tmp_path))
    (root / "index.json").write_text('{"A": "a.json", "B": "b.json"}', encoding="utf-8")
    monkeypatch.setattr(provider_module, "MAX_SCHEMA_INDEX_BYTES", 1)
    with pytest.raises(SchemaProviderError, match="schema index exceeds"):
        ObjectInfoIndexSchemaProvider(root).schemas()

    monkeypatch.setattr(provider_module, "MAX_SCHEMA_INDEX_BYTES", 1024 * 1024)
    monkeypatch.setattr(provider_module, "MAX_SCHEMA_INDEX_ENTRIES", 1)
    with pytest.raises(SchemaProviderError, match="schema index exceeds"):
        ObjectInfoIndexSchemaProvider(root).schemas()


def test_external_resolver_failure_is_typed_not_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.schema.provider as provider_module

    class _FailingExternalResolver:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def get_schema(self, class_type: str) -> None:
            raise OSError(f"source broken: {class_type}")

    monkeypatch.setattr(provider_module, "SourceSchemaProvider", _FailingExternalResolver)
    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_SCHEMAS", "0")
    with pytest.raises(SchemaProviderError, match="source broken"):
        capture_schema_snapshot(
            class_types=["MissingNode"],
            connected_object_info={"KnownNode": {}},
            connected_object_info_verified=True,
        )


def test_malformed_provider_schema_is_typed_not_missing() -> None:
    class _MalformedSchema:
        pack = "test"
        outputs: list[object] = []

        @property
        def inputs(self) -> object:
            raise OSError("malformed schema")

    class _Provider:
        def schemas(self) -> dict[str, object]:
            return {"Broken": _MalformedSchema()}

        def get_schema(self, class_type: str) -> object | None:
            return _MalformedSchema() if class_type == "Broken" else None

    with pytest.raises(SchemaSnapshotError, match="schema_provider_error.*Broken") as excinfo:
        capture_ingress_schema_snapshot(
            schema_provider=_Provider(),
            graph={"nodes": [{"type": "Broken"}]},
        )
    assert excinfo.value.code == "schema_provider_error"
