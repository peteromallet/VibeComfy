from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest

from vibecomfy.identity.scope import sg_key
from vibecomfy.porting.edit.bundle_service import (
    BundleTransitionError,
    _schema_provider_with_uid_aliases,
    transition_bundle,
)
from vibecomfy.schema import (
    FrozenSchemaSnapshotProvider,
    InputSpec,
    NodeSchema,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)
from vibecomfy.security import GateContext, set_gate_context
from vibecomfy.security import CapabilityFenceError
from vibecomfy.security.gate import _gate_context_var
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import WorkflowBundleError, emit_bundle, load_bundle


def _provider() -> FrozenSchemaSnapshotProvider:
    integer = NodeSchema(
        class_type="Integer",
        pack="core",
        inputs={"value": InputSpec(type="INT", required=True)},
        outputs=[],
        widget_input_order=("value",),
    )
    snapshot = capture_schema_snapshot(
        class_types=("Integer",),
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {"Integer": schema_payload_from_node_schema("Integer", integer)},
            "missing_classes": [],
        },
        node_classes={"1": "Integer"},
    )
    return FrozenSchemaSnapshotProvider(snapshot)


def _gate(*, yes: bool = True) -> GateContext:
    context = GateContext(non_interactive=True, assume_yes=yes)
    set_gate_context(context)
    return context


@pytest.fixture(autouse=True)
def _clean_gate():
    prior = _gate_context_var.get()
    yield
    # Some tests install more than one context (preview then save). Restore the
    # fixture's original context instead of only unwinding the most recent one.
    _gate_context_var.set(prior)


def _bundle(directory: Path) -> tuple[Path, bytes, FrozenSchemaSnapshotProvider]:
    directory.mkdir(parents=True, exist_ok=True)
    source_bytes = b'{"workflow_id":"service-fixture","graph":"original bytes\\n"}\n'
    source_json = directory / "source.json"
    source_json.write_bytes(source_bytes)
    workflow = VibeWorkflow("service-fixture", WorkflowSource("service-fixture"))
    workflow.add_node("Integer", uid="integer-one", value=7)
    python_path = directory / "workflow.py"
    emit_bundle(workflow, python_path, {"operation": "authored"})
    return python_path, source_bytes, _provider()


def _edit_call(value: int) -> list[dict[str, object]]:
    return [{"tool": "edit_node", "args": {"target": "integer-one", "field": "value", "value": value}}]


def test_typed_edit_saves_and_reloads_pair_with_parent_revision(tmp_path: Path) -> None:
    python_path, source_bytes, provider = _bundle(tmp_path / "input")
    before = load_bundle(python_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)

    context = _gate()
    result = transition_bundle(
        python_path,
        tool_calls=_edit_call(23),
        schema_provider=provider,
    )

    assert result.status == "saved"
    assert result.kind == "edit"
    assert result.parent_revision == before.revision_id
    assert result.revision_id != before.revision_id
    assert result.operations and result.diff
    assert result.to_dict()["baseline"] == "known"
    reloaded = load_bundle(
        python_path,
        trust=Provenance.USER_CONFIRMED,
        schema_provider=provider,
    )
    assert reloaded.revision_id == result.revision_id
    assert reloaded.parent_revision == before.revision_id
    assert reloaded.workflow.nodes["1"].inputs["value"] == 23
    assert (python_path.parent / "source.json").read_bytes() == source_bytes
    assert any(entry["reason"] == "assume_yes_bypass" for entry in context.audit)


def test_typed_edit_freezes_live_authoring_catalog_at_transition_boundary(tmp_path: Path) -> None:
    class LiveCatalogProvider:
        """Representative authoring provider: queryable, but no snapshot attr."""

        def __init__(self) -> None:
            self.schemas_by_name = {
                name: NodeSchema(
                    class_type=name,
                    pack="fixture",
                    inputs={"value": InputSpec(type="INT", required=True)},
                    outputs=[],
                    widget_input_order=("value",),
                )
                for name in ("FixtureInteger", "FixtureAdded")
            }
            self.lookups: list[str] = []

        def get_schema(self, class_type: str):
            self.lookups.append(class_type)
            return self.schemas_by_name.get(class_type)

    provider = LiveCatalogProvider()
    directory = tmp_path / "live-catalog"
    directory.mkdir()
    source_bytes = b'{"workflow_id":"live-catalog-fixture"}\n'
    (directory / "source.json").write_bytes(source_bytes)
    workflow = VibeWorkflow(
        "live-catalog-fixture", WorkflowSource("live-catalog-fixture")
    )
    workflow.add_node("FixtureInteger", uid="fixture-integer", value=7)
    python_path = directory / "workflow.py"
    emit_bundle(workflow, python_path, {"operation": "authored"})

    _gate()
    result = transition_bundle(
        python_path,
        tool_calls=[
            {
                "tool": "edit_batch",
                "args": {
                    "ops": [
                        {
                            "op": "add_node",
                            "class_type": "FixtureAdded",
                            "uid": "new-node",
                            "fields": {"value": 1},
                        },
                        {
                            "op": "edit_node",
                            "target": "new-node",
                            "field": "value",
                            "value": 23,
                        },
                    ]
                },
            }
        ],
        schema_provider=provider,
    )

    assert result.status == "saved"
    reloaded = load_bundle(
        python_path,
        trust=Provenance.USER_CONFIRMED,
        schema_provider=provider,
    )
    assert reloaded.workflow.nodes["2"].inputs["value"] == 23
    assert {"FixtureInteger", "FixtureAdded"} <= set(provider.lookups)
    assert (directory / "source.json").read_bytes() == source_bytes


def test_schema_fallback_freezes_recursive_classes_and_scoped_uids() -> None:
    class LiveCatalogProvider:
        def get_schema(self, class_type: str):
            if class_type not in {"FixtureNested", "FixtureOther"}:
                return None
            return NodeSchema(
                class_type=class_type,
                pack="fixture",
                inputs={"widget_0": InputSpec(type="INT")},
                outputs=[],
                widget_input_order=("widget_0",),
            )

    def definition(class_type: str) -> dict[str, object]:
        return {
            "name": class_type,
            "nodes": [
                {
                    "id": 1,
                    "uid": "shared-local-uid",
                    "type": class_type,
                    "inputs": [],
                    "outputs": [],
                    "widgets_values": [7],
                    "mode": 0,
                }
            ],
            "links": [],
        }

    workflow = VibeWorkflow(
        "recursive-schema-fixture",
        WorkflowSource("recursive-schema-fixture"),
        definitions={
            "subgraphs": [definition("FixtureNested"), definition("FixtureOther")]
        },
    )

    frozen = _schema_provider_with_uid_aliases(LiveCatalogProvider(), workflow)

    assert isinstance(frozen, FrozenSchemaSnapshotProvider)
    snapshot = frozen.snapshot
    assert {"FixtureNested", "FixtureOther"} <= set(snapshot.schemas)
    scopes = [sg_key(definition) for definition in workflow.definitions["subgraphs"]]
    paths = [f"{scope}#shared-local-uid" for scope in scopes]
    assert snapshot.node_classes[paths[0]] == "FixtureNested"
    assert snapshot.node_classes[paths[1]] == "FixtureOther"
    # A bare UID cannot safely identify two classes in separate scopes.
    assert "shared-local-uid" not in snapshot.node_classes

    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.schema.types import require_known_touched_schema

    nested_edit = SetNodeFieldOp(
        "set_node_field",
        NodeFieldTarget(
            scopes[0],
            "shared-local-uid",
            "widget_0",
        ),
        23,
    )
    other_edit = SetNodeFieldOp(
        "set_node_field",
        NodeFieldTarget(
            scopes[1],
            "shared-local-uid",
            "widget_0",
        ),
        29,
    )
    assert require_known_touched_schema(nested_edit, snapshot) == ("FixtureNested",)
    assert require_known_touched_schema(other_edit, snapshot) == ("FixtureOther",)


def test_dry_run_and_out_preserve_parent_and_copy_source_bytes(tmp_path: Path) -> None:
    python_path, source_bytes, provider = _bundle(tmp_path / "input")
    before_python = python_path.read_bytes()
    before_companion = python_path.with_suffix(".vibe.json").read_bytes()
    before = load_bundle(python_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)

    _gate()
    preview = transition_bundle(
        python_path,
        tool_calls=_edit_call(31),
        dry_run=True,
        schema_provider=provider,
    )
    assert preview.status == "preview"
    assert preview.parent_revision == before.revision_id
    assert python_path.read_bytes() == before_python
    assert python_path.with_suffix(".vibe.json").read_bytes() == before_companion
    assert (python_path.parent / "source.json").read_bytes() == source_bytes

    _gate()
    output_dir = tmp_path / "copy"
    saved = transition_bundle(
        python_path,
        tool_calls=_edit_call(31),
        output=output_dir,
        schema_provider=provider,
    )
    output_python = output_dir / "workflow.py"
    assert saved.python_path == str(output_python)
    assert output_python.is_file()
    assert (output_dir / "workflow.vibe.json").is_file()
    assert (output_dir / "source.json").read_bytes() == source_bytes
    assert python_path.read_bytes() == before_python
    assert load_bundle(
        output_python,
        trust=Provenance.USER_CONFIRMED,
        schema_provider=provider,
    ).revision_id == saved.revision_id


def test_gate_requires_callers_yes_or_interactive_confirmation(tmp_path: Path) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "input")
    original = python_path.read_bytes()
    _gate(yes=False)

    with pytest.raises(CapabilityFenceError, match="non_interactive_refusal"):
        transition_bundle(python_path, tool_calls=_edit_call(40), schema_provider=provider)
    assert python_path.read_bytes() == original

    with pytest.raises(CapabilityFenceError, match="non_interactive_refusal"):
        transition_bundle(python_path, capture=True, schema_provider=provider)
    assert python_path.read_bytes() == original


def test_later_batch_failure_leaves_pair_and_revision_untouched(tmp_path: Path) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "input")
    original_python = python_path.read_bytes()
    original_companion = python_path.with_suffix(".vibe.json").read_bytes()

    _gate()
    with pytest.raises(BundleTransitionError) as raised:
        transition_bundle(
            python_path,
            tool_calls=[
                {"tool": "edit_node", "args": {"target": "integer-one", "field": "value", "value": 9}},
                {"tool": "edit_node", "args": {"target": "integer-one", "field": "missing", "value": 1}},
            ],
            schema_provider=provider,
        )
    report = json.loads(str(raised.value))
    assert report["reason"] == "unknown_field"
    assert report["transitions"]
    assert report["transitions"][0]["occurrence"] == 0
    assert report["transitions"][0]["outcome"] == "staged"
    assert report["transitions"][1]["occurrence"] == 1
    assert report["transitions"][1]["outcome"] == "rejected"
    assert report["transitions"][1]["diagnostics"][0]["code"] == "unknown_field"
    assert python_path.read_bytes() == original_python
    assert python_path.with_suffix(".vibe.json").read_bytes() == original_companion


def test_compare_and_swap_refuses_changed_parent_without_clobber(tmp_path: Path, monkeypatch) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "input")
    companion_path = python_path.with_suffix(".vibe.json")
    original_companion = companion_path.read_bytes()
    concurrent_bytes = b"concurrent writer won\n"
    real_copy2 = shutil.copy2
    changed = False

    def mutate_after_backup(source, target, *args, **kwargs):
        nonlocal changed
        result = real_copy2(source, target, *args, **kwargs)
        if Path(source) == python_path and not changed:
            python_path.write_bytes(concurrent_bytes)
            changed = True
        return result

    monkeypatch.setattr("vibecomfy.workflow_bundle.shutil.copy2", mutate_after_backup)
    _gate()
    with pytest.raises(WorkflowBundleError, match="changed before publication"):
        transition_bundle(python_path, tool_calls=_edit_call(50), schema_provider=provider)
    # The failed CAS must not restore its stale backup over another writer.
    assert python_path.read_bytes() == concurrent_bytes
    assert companion_path.read_bytes() == original_companion


def test_visible_pair_failure_rolls_back_both_members(tmp_path: Path, monkeypatch) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "input")
    companion_path = python_path.with_suffix(".vibe.json")
    original_python = python_path.read_bytes()
    original_companion = companion_path.read_bytes()
    real_replace = __import__("os").replace
    visible_replacements = 0

    def fail_second_replace(source, destination):
        nonlocal visible_replacements
        if Path(destination) in {python_path, companion_path}:
            visible_replacements += 1
            if visible_replacements == 2:
                raise OSError("injected companion publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr("vibecomfy.workflow_bundle.os.replace", fail_second_replace)
    _gate()
    with pytest.raises(OSError, match="injected companion publication failure"):
        transition_bundle(python_path, tool_calls=_edit_call(60), schema_provider=provider)
    assert python_path.read_bytes() == original_python
    assert companion_path.read_bytes() == original_companion


def test_ui_capture_binds_flat_graph_to_parent_and_reports_aggregate_diff(tmp_path: Path) -> None:
    python_path, source_bytes, provider = _bundle(tmp_path / "input")
    parent = load_bundle(python_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)
    graph = parent.materialize_ui(schema_provider=provider, strict=True)
    assert "workflow_id" not in graph and "workflow_identity" not in graph
    for node in graph["nodes"]:
        if node.get("type") == "Integer":
            node["widgets_values"][0] = 88
    _gate()

    result = transition_bundle(
        python_path,
        capture_graph=graph,
        schema_provider=provider,
    )

    assert result.kind == "ui_capture"
    assert result.operations == ()
    assert result.diff
    assert result.parent_revision == parent.revision_id
    assert result.before_semantic_digest == parent.semantic_digest
    assert result.revision_id != parent.revision_id
    assert (python_path.parent / "source.json").read_bytes() == source_bytes


def test_direct_python_capture_does_not_invent_missing_revision_lineage(tmp_path: Path) -> None:
    python_path, source_bytes, _provider_value = _bundle(tmp_path / "input")
    parent = load_bundle(python_path, trust=Provenance.USER_CONFIRMED, schema_provider=_provider())
    original_source = python_path.read_text(encoding="utf-8")
    assert "value=7" in original_source
    # A direct source edit makes the old presentation stale only when graph
    # structure changes; the semantic edit itself is loaded through the normal
    # untrusted-code gate and captured as a new honest baseline.
    python_path.write_text(original_source.replace("value=7", "value=19"), encoding="utf-8")
    _gate()

    result = transition_bundle(python_path, capture=True, schema_provider=_provider())

    assert result.kind == "python_capture"
    # Ordinary local bundles do not carry a trusted revision witness. Direct
    # Python capture therefore records an unavailable baseline rather than
    # claiming that the last loaded bundle is the parent of an out-of-band edit.
    assert result.parent_revision is None
    assert result.before_semantic_digest is None
    assert result.before_ui_digest is None
    assert result.diff is None
    assert result.operations == ()
    assert result.to_dict()["baseline"] == "unknown"
    assert result.to_dict()["diff_status"] == "unavailable"
    assert result.diagnostics[0]["code"] == "capture_baseline_unavailable"
    assert (python_path.parent / "source.json").read_bytes() == source_bytes
    reopened = load_bundle(
        python_path,
        trust=Provenance.USER_CONFIRMED,
        schema_provider=_provider(),
    )
    assert reopened.workflow.nodes["1"].inputs["value"] == 19


def test_candidate_python_capture_uses_immutable_parent_and_preserves_custom_source(tmp_path: Path) -> None:
    parent_path, source_bytes, provider = _bundle(tmp_path / "parent")
    parent = load_bundle(parent_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    candidate_path = candidate_dir / "workflow.py"
    custom_code = b"\nCUSTOM_CAPTURE_SENTINEL = ('keep candidate bytes', 31)\n"
    candidate_path.write_bytes(parent_path.read_bytes().replace(b"value=7", b"value=31") + custom_code)
    candidate_path.with_suffix(".vibe.json").write_bytes(parent_path.with_suffix(".vibe.json").read_bytes())
    original_parent_python = parent_path.read_bytes()
    original_parent_sidecar = parent_path.with_suffix(".vibe.json").read_bytes()
    _gate()

    result = transition_bundle(
        parent_path,
        capture=True,
        candidate_python=candidate_path,
        expected_parent_revision=parent.revision_id,
        schema_provider=provider,
    )

    assert result.status == "saved"
    assert result.kind == "python_capture"
    assert result.parent_revision == parent.revision_id
    assert result.before_semantic_digest == parent.semantic_digest
    assert result.before_ui_digest == parent.ui_digest
    assert result.diff
    assert result.operations == ()
    assert parent_path.read_bytes().endswith(custom_code)
    assert parent_path.read_bytes() != original_parent_python
    assert parent_path.with_suffix(".vibe.json").read_bytes() != original_parent_sidecar
    assert (parent_path.parent / "source.json").read_bytes() == source_bytes
    assert candidate_path.read_bytes().endswith(custom_code)
    reloaded = load_bundle(parent_path, trust=Provenance.USER_CONFIRMED, schema_provider=provider)
    assert reloaded.revision_id == result.revision_id
    assert reloaded.parent_revision == parent.revision_id
    assert reloaded.workflow.nodes["1"].inputs["value"] == 31


def test_direct_python_capture_preserves_custom_executable_source_bytes(tmp_path: Path) -> None:
    python_path, _source_bytes, _provider_value = _bundle(tmp_path / "input")
    custom_code = b"\nCUSTOM_CAPTURE_SENTINEL = ('preserve these bytes', 23)\n"
    edited_source = python_path.read_bytes().replace(b"value=7", b"value=23") + custom_code
    python_path.write_bytes(edited_source)
    _gate()

    result = transition_bundle(python_path, capture=True, schema_provider=_provider())

    assert result.kind == "python_capture"
    captured_source = python_path.read_bytes()
    assert captured_source.endswith(custom_code)
    assert b"value=23" in captured_source
    reopened = load_bundle(
        python_path,
        trust=Provenance.USER_CONFIRMED,
        schema_provider=_provider(),
    )
    assert reopened.workflow.nodes["1"].inputs["value"] == 23


def test_typed_edit_refuses_to_discard_custom_python_after_capture(tmp_path: Path) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "input")
    custom_code = b"\nCUSTOM_CAPTURE_SENTINEL = ('keep this code', 23)\n"
    python_path.write_bytes(python_path.read_bytes().replace(b"value=7", b"value=23") + custom_code)
    _gate()
    transition_bundle(python_path, capture=True, schema_provider=provider)

    before = {
        path.name: path.read_bytes()
        for path in (
            python_path,
            python_path.with_suffix(".vibe.json"),
            python_path.parent / "source.json",
        )
    }
    with pytest.raises(BundleTransitionError, match="typed edit cannot safely preserve"):
        transition_bundle(
            python_path,
            tool_calls=_edit_call(31),
            schema_provider=provider,
        )

    after = {
        path.name: path.read_bytes()
        for path in (
            python_path,
            python_path.with_suffix(".vibe.json"),
            python_path.parent / "source.json",
        )
    }
    assert after == before
    assert python_path.read_bytes().endswith(custom_code)

    with pytest.raises(BundleTransitionError, match="UI capture cannot safely preserve"):
        transition_bundle(
            python_path,
            capture_graph={},
            schema_provider=provider,
        )
    assert {
        path.name: path.read_bytes()
        for path in (
            python_path,
            python_path.with_suffix(".vibe.json"),
            python_path.parent / "source.json",
        )
    } == before


@pytest.mark.parametrize("mutation", ["same_line_statement", "chained_assignment_target"])
def test_noncanonical_metadata_statement_cannot_be_rewritten_by_typed_or_ui_capture(
    tmp_path: Path,
    mutation: str,
) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / mutation)
    source = python_path.read_bytes()
    module = ast.parse(source)
    assignment = next(
        statement
        for statement in module.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "READY_METADATA"
            for target in statement.targets
        )
    )
    lines = source.splitlines(keepends=True)

    def byte_offset(line: int, column: int) -> int:
        return sum(len(item) for item in lines[: line - 1]) + column

    if mutation == "same_line_statement":
        insertion = byte_offset(assignment.end_lineno, assignment.end_col_offset)
        source = (
            source[:insertion]
            + b"; CUSTOM_CAPTURE_SENTINEL = ('keep this code', 23)"
            + source[insertion:]
        )
    else:
        insertion = byte_offset(assignment.value.lineno, assignment.value.col_offset)
        source = source[:insertion] + b"CUSTOM_CAPTURE_SENTINEL = " + source[insertion:]
    python_path.write_bytes(source)
    _gate()

    members = (
        python_path,
        python_path.with_suffix(".vibe.json"),
        python_path.parent / "source.json",
    )
    before = {path.name: path.read_bytes() for path in members}
    with pytest.raises(BundleTransitionError, match="typed edit cannot safely preserve"):
        transition_bundle(
            python_path,
            tool_calls=_edit_call(31),
            schema_provider=provider,
        )
    assert {path.name: path.read_bytes() for path in members} == before

    with pytest.raises(BundleTransitionError, match="UI capture cannot safely preserve"):
        transition_bundle(
            python_path,
            capture_graph={},
            schema_provider=provider,
        )
    assert {path.name: path.read_bytes() for path in members} == before


def test_direct_capture_after_typed_edit_reads_previous_ui_digest_without_report_sidecar(
    tmp_path: Path,
) -> None:
    python_path, _source_bytes, provider = _bundle(tmp_path / "input")
    _gate()
    transition_bundle(
        python_path,
        tool_calls=_edit_call(9),
        schema_provider=provider,
    )
    python_path.write_bytes(python_path.read_bytes().replace(b"value=9", b"value=11"))

    captured = transition_bundle(python_path, capture=True, schema_provider=provider)

    assert captured.kind == "python_capture"
    assert captured.parent_revision
    # This bundle has only the three canonical sibling files, so the previous
    # UI digest comes from the trusted companion instead of a local report.
    assert captured.before_ui_digest
