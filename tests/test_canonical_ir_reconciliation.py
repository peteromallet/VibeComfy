from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from vibecomfy.errors import ModelAssetError
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.registry.static_contract import (
    extract_ready_template_contract,
    reconcile_ready_template_file,
    reconcile_ready_template_source,
)
from vibecomfy.templates import ModelAsset


def test_unresolved_model_asset_requires_explicit_safe_paths() -> None:
    asset = ModelAsset(filename="denoiser.safetensors", url=None, subdir="diffusion_models")
    assert asset.url is None

    with pytest.raises((TypeError, ValueError)):
        ModelAsset(url=None, subdir="diffusion_models")
    with pytest.raises(ValueError):
        ModelAsset(filename="../denoiser.safetensors", url=None, subdir="diffusion_models")


def test_custom_node_normalization_preserves_empty_url_and_unions_class_data() -> None:
    normalized, warnings = normalize_custom_node_requirements({
        "custom_node_refs": [
            {"slug": "example", "url": "", "classes": ["A"]},
            {"slug": "example", "source": "git", "url": "", "class_set": ["B"]},
        ]
    })
    assert not warnings
    assert normalized["custom_node_refs"] == [{
        "slug": "example", "source": "git", "url": "", "classes": ["A"], "class_set": ["B"],
    }]


def test_static_contract_reports_exact_dependency_locations(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "MODELS = {'foo': ModelAsset(filename='foo.safetensors', url=None, subdir='checkpoints')}\n"
        "READY_REQUIREMENTS = {'custom_node_refs': [{'slug': 'pack', 'url': ''}]}\n",
        encoding="utf-8",
    )
    locations = extract_ready_template_contract(source)["source_locations"]
    paths = {item["path"] for item in locations}
    assert 'MODELS["foo"].url' in paths
    assert "READY_REQUIREMENTS.custom_node_refs[0].url" in paths


def test_same_file_reconciliation_is_literal_idempotent_and_preserves_comments() -> None:
    source = """# keep this comment\nfrom vibecomfy.templates import ModelAsset, ReadyMetadata\nMODELS = {\n    'foo': ModelAsset(filename='foo.safetensors', subdir='checkpoints'),\n}\nREADY_METADATA = ReadyMetadata.build(\n    capability='image',\n    requirements={'custom_node_refs': [{'slug': 'pack', 'classes': ['CustomNode']}]},\n)\ndef build():\n    node = CustomNode(_id='1')\n"""
    result = reconcile_ready_template_source(source, source_path="workflow.py")
    assert result["changed"] is True
    assert "url=None" in result["source"]
    assert "# keep this comment" in result["source"]
    assert "'url': None" in result["source"]
    again = reconcile_ready_template_source(result["source"], source_path="workflow.py")
    assert again["changed"] is False
    assert again["edits"] == []


def test_reconciliation_leaves_dynamic_dependencies_unchanged() -> None:
    source = (
        "MODELS = {'foo': ModelAsset(filename='foo.safetensors', url=MODEL_URL, subdir='checkpoints')}\n"
        "READY_REQUIREMENTS = {'custom_node_refs': [{'slug': 'pack', 'url': REPOSITORY_URL}]}\n"
    )
    result = reconcile_ready_template_source(source, source_path="dynamic.py")
    assert result["changed"] is False
    assert result["source"] == source
    assert {item["code"] for item in result["diagnostics"]} == {"static_dynamic_value"}


def test_reconciliation_reports_dynamic_dependency_containers_for_manual_repair() -> None:
    source = (
        "MODELS = load_models()\n"
        "READY_REQUIREMENTS = {\"models\": load_requirements()}\n"
    )

    result = reconcile_ready_template_source(source, source_path="dynamic-containers.py")

    assert result["changed"] is False
    diagnostics = [item for item in result["diagnostics"] if item["code"] == "manual_repair_required"]
    assert {item["location"]["path"] for item in diagnostics} == {
        "MODELS", "READY_REQUIREMENTS.models"
    }
    assert all("manually repair" in item["message"] for item in diagnostics)


def test_reconciliation_collects_located_model_and_node_selector_blockers() -> None:
    source = (
        "from vibecomfy.templates import ModelAsset\n"
        "MODELS = {'foo': ModelAsset(filename='foo.safetensors', url='https://example.test/foo', "
        "subdir='checkpoints', hf_revision='rev1')}\n"
        "READY_REQUIREMENTS = {'custom_node_refs': [{"
        "'url': 'https://example.test/pack.git', 'version': NODE_VERSION}]}\n"
    )

    result = reconcile_ready_template_source(source, source_path="selectors.py")

    blockers = [item for item in result["blockers"] if item["code"].endswith("_selector")]
    assert {item["code"] for item in blockers} == {
        "unsupported_model_selector", "unsupported_node_selector"
    }
    paths = {item["location"]["path"] for item in blockers}
    assert 'MODELS["foo"].hf_revision' in paths
    assert "READY_REQUIREMENTS.custom_node_refs[0]" in paths
    assert "READY_REQUIREMENTS.custom_node_refs[0].version" in paths


def test_literal_requirements_without_refs_get_one_idempotent_placeholder_list() -> None:
    source = "READY_REQUIREMENTS = {}\ndef build():\n    return None\n"

    result = reconcile_ready_template_source(source, source_path="empty-requirements.py")

    assert result["changed"] is True
    assert result["source"] == "READY_REQUIREMENTS = {'custom_node_refs': []}\ndef build():\n    return None\n"
    assert [item["path"] for item in result["edits"]] == [
        "READY_REQUIREMENTS.custom_node_refs"
    ]
    again = reconcile_ready_template_source(result["source"], source_path="empty-requirements.py")
    assert again["changed"] is False
    assert again["edits"] == []


def test_literal_requirements_placeholder_list_receives_missing_class_refs() -> None:
    source = "READY_REQUIREMENTS = {'models': []}\ndef build():\n    return node('1', 'MissingPlaceholderNode')\n"

    result = reconcile_ready_template_source(source, source_path="missing-refs.py")

    assert result["changed"] is True
    assert "'custom_node_refs': [{'slug': 'MissingPlaceholderNode'" in result["source"]
    assert result["source"].count("'custom_node_refs'") == 1
    again = reconcile_ready_template_source(result["source"], source_path="missing-refs.py")
    assert again["changed"] is False


def test_reconciliation_accounts_for_nested_declared_classes_and_counts_occurrences() -> None:
    source = """
READY_METADATA = {"requirements": {"custom_node_refs": [{
    "slug": "example-pack", "url": "https://example.test/example.git",
    "classes": ["NestedNode"],
}]}}
def build():
    def nested_graph():
        return node("1", "NestedNode")
    return nested_graph()
"""

    result = reconcile_ready_template_source(source, source_path="nested.py")

    assert result["blockers"] == []
    assert result["graph_classes"]["NestedNode"] == 1
    assert result["class_accounting"]["NestedNode"]["status"] == "declared"


def test_reconciliation_batches_distinct_missing_classes_and_is_idempotent() -> None:
    source = """
READY_REQUIREMENTS = {"custom_node_refs": []}
def build():
    first = node("1", "MissingFirstNode")
    second = node("2", "MissingSecondNode")
    return first, second
"""

    result = reconcile_ready_template_source(source, source_path="missing.py")

    assert result["changed"] is True
    assert "'slug': 'MissingFirstNode'" in result["source"]
    assert "'slug': 'MissingSecondNode'" in result["source"]
    assert result["source"].count("'slug': 'Missing") == 2
    assert [item["path"] for item in result["edits"]] == [
        "READY_REQUIREMENTS.custom_node_refs[0]",
        "READY_REQUIREMENTS.custom_node_refs[1]",
    ]
    assert len([item for item in result["blockers"] if item["code"] == "class_not_accounted_for"]) == 2

    again = reconcile_ready_template_source(result["source"], source_path="missing.py")
    assert again["changed"] is False
    assert again["edits"] == []


def test_reconciliation_uses_an_unambiguous_local_pack_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.node_packs as node_packs

    pack = node_packs.CustomNodePack(
        "LocalExample", "https://example.test/example.git", frozenset({"CatalogNode"})
    )
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda: (pack,))

    result = reconcile_ready_template_source(
        "def build():\n    return node('1', 'CatalogNode')\n",
        source_path="catalog.py",
    )

    assert result["blockers"] == []
    assert result["class_accounting"]["CatalogNode"] == {
        "status": "local_catalog", "pack": "LocalExample", "occurrences": 1
    }


def test_reconciliation_rejects_source_cas_without_writing(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    original = "MODELS = {'foo': ModelAsset(filename='foo.safetensors', subdir='checkpoints')}\n"
    source.write_text(original, encoding="utf-8")
    result = reconcile_ready_template_file(
        source,
        expected_source_sha256=hashlib.sha256(b"stale").hexdigest(),
    )
    assert result["changed"] is False
    assert any(item["code"] == "source_cas_mismatch" for item in result["diagnostics"])
    assert source.read_text(encoding="utf-8") == original


def test_emitter_round_trips_unresolved_model_asset_and_runtime_rejects_it() -> None:
    from vibecomfy.porting.emit.emit_constants import _format_models_block

    text = "\n".join(_format_models_block([{
        "name": "foo.safetensors", "url": None, "subdir": "checkpoints",
    }]))
    assert "url=None" in text
    namespace: dict[str, object] = {}
    exec("from vibecomfy.templates import ModelAsset\n" + text, namespace)  # noqa: S102
    assert namespace["MODELS"]["checkpoint"].url is None  # type: ignore[index]

    from vibecomfy.runtime.session import _model_assets_from_workflow
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("unresolved", WorkflowSource("unresolved"))
    workflow.metadata["model_assets"] = [{
        "name": "foo.safetensors", "url": None, "subdir": "checkpoints",
    }]
    with pytest.raises(ModelAssetError, match="unresolved authored model assets"):
        _model_assets_from_workflow(workflow)
