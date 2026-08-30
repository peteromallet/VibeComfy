"""Regression tests for fail-closed schema listing authorities."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.candidate_transaction import capture_ingress_schema_snapshot
from vibecomfy.porting.emit.signatures import emit_available_node_signatures
from vibecomfy.search.index import _object_info_entries
from vibecomfy.schema import (
    AuthoringSchemaProvider,
    CompositeSchemaProvider,
    SchemaProviderError,
    SchemaSnapshotError,
    schema_for,
)
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider


@pytest.mark.parametrize("listing_only", [False, True])
def test_ingress_rejects_present_non_mapping_enumeration(listing_only: bool) -> None:
    class MalformedEnumerationProvider:
        def __init__(self) -> None:
            self.listing_only = listing_only

        def schemas(self) -> list[object]:
            return []

        def get_schema(self, _class_type: str) -> None:
            return None

    with pytest.raises(SchemaSnapshotError, match="schema_provider_error") as excinfo:
        capture_ingress_schema_snapshot(
            schema_provider=MalformedEnumerationProvider(),
            graph={"nodes": [{"type": "BrokenNode"}]},
        )
    assert excinfo.value.code == "schema_provider_error"


def test_existing_corrupt_index_is_typed_not_an_empty_listing(tmp_path: Path) -> None:
    (tmp_path / "index.json").write_bytes(b"not valid utf-8: \xff")
    provider = ObjectInfoIndexSchemaProvider(tmp_path)

    with pytest.raises(SchemaProviderError, match="schema index"):
        provider.schemas()
    with pytest.raises(SchemaSnapshotError, match="schema_provider_error"):
        capture_ingress_schema_snapshot(
            schema_provider=ObjectInfoIndexSchemaProvider(tmp_path),
            graph={"nodes": [{"type": "BrokenNode"}]},
        )


def test_indexed_pack_missing_advertised_class_is_typed_not_a_schema_miss(
    tmp_path: Path,
) -> None:
    (tmp_path / "index.json").write_text(
        '{"AdvertisedNode": "pack.json"}', encoding="utf-8"
    )
    (tmp_path / "pack.json").write_text('{"DifferentNode": {}}', encoding="utf-8")
    provider = ObjectInfoIndexSchemaProvider(tmp_path)

    with pytest.raises(SchemaProviderError, match="AdvertisedNode"):
        schema_for(provider, "AdvertisedNode")
    with pytest.raises(SchemaSnapshotError, match="schema_provider_error.*AdvertisedNode"):
        capture_ingress_schema_snapshot(
            schema_provider=ObjectInfoIndexSchemaProvider(tmp_path),
            graph={"nodes": [{"type": "AdvertisedNode"}]},
        )


def test_composed_listing_only_consumers_focus_fetch_without_fake_rows_or_crash(
    tmp_path: Path,
) -> None:
    (tmp_path / "index.json").write_text('{"A": "a.json"}', encoding="utf-8")
    (tmp_path / "a.json").write_text(
        '{"A": {"input": {"required": {"x": ["INT"]}}, '
        '"output": ["INT"], "output_name": ["out"]}}',
        encoding="utf-8",
    )
    index_provider = ObjectInfoIndexSchemaProvider(tmp_path)
    composite = CompositeSchemaProvider(index_provider)
    authoring = AuthoringSchemaProvider.__new__(AuthoringSchemaProvider)
    authoring._providers = (index_provider,)

    for provider in (composite, authoring):
        assert provider.listing_only is True
        assert provider.schemas() == {"A": None}
        rows = emit_available_node_signatures(provider)
        assert len(rows) == 1
        assert rows[0].class_type == "A"
        assert _object_info_entries(provider)[0].class_type == "A"
