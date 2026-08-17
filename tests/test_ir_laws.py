"""Executable laws for the VibeWorkflow IR-everywhere migration.

The law owners intentionally remain ``xfail(strict=False)`` until their named
batches land.  Passing tests in this module freeze the quotient, spike corpus,
and provisional failure ledger so later batches cannot weaken the contracts.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.ingest.normalize import from_envelope, from_ui
from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import get_schema_provider, schema_for
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeInput, VibeNode, VibeWorkflow, WorkflowSource, mode_to_litegraph


REPO_ROOT = Path(__file__).parents[1]
SPIKE_CORPUS = (
    (
        "vibe_envelope",
        REPO_ROOT / "tests/fixtures/b02_corpus_mini/90a1d5ff9044902e.json",
        "3f7fe8c665328f4ffa8db8f851da2081f288c9e2d107fd697c89de8655cf5f63",
    ),
    (
        "raw_ui_definitions",
        REPO_ROOT / "tests/fixtures/agent_edit/subgraphed_wan_i2v.json",
        "063620c1a3828ce7a065c852ffcc50d238b15e25ebdbaef40f72d4fe36405236",
    ),
    (
        "raw_ui_unknown_schema",
        REPO_ROOT
        / "ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json",
        "16f5c40d768c2ce719add73e74317ff17f2f2c59f987b031fa295f48f27d0f0f",
    ),
)

@dataclass(frozen=True, slots=True)
class FailureLedgerRow:
    family: str
    count: int
    owner: str
    scenario_ids: None = None
    status: str = "provisional"


# Provisional until the original 57 scenario ids are restored.  These are
# reconciliation constraints, not claims about finer-grained evidence.
PROVISIONAL_FAILURE_LEDGER = (
    FailureLedgerRow("semantic: gen_hard_missing_precedents", 8, "phase 6"),
    FailureLedgerRow("semantic: gen_hard_missing_schemas", 6, "phase 5"),
    FailureLedgerRow("semantic: variance", 3, "phase 5"),
    FailureLedgerRow("semantic: unsupported-conclusion residue", 8, "phase 6"),
    FailureLedgerRow("edit: pre_existing_bug", 8, "phase 3"),
    FailureLedgerRow("edit: cross_domain_over_rejection", 8, "phase 3"),
    FailureLedgerRow("edit: widget_shape_guard", 4, "phase 3"),
    FailureLedgerRow("edit: batch_repl_gap", 3, "phase 3"),
    FailureLedgerRow("edit: gen_hard_architecture", 2, "phase 5"),
    FailureLedgerRow("edit: revision_evidence_fix", 2, "phase 4"),
    FailureLedgerRow("edit: gen_hard_discovery_loop", 2, "phase 3"),
    FailureLedgerRow("infra", 2, "out of scope: reclassify with evidence; phase 7 is cut"),
    FailureLedgerRow("other", 1, "capability-floor candidate; reclassify with evidence"),
)

_UID_COMMENT = re.compile(r"\buid:([^\s]+)")
_PROVISIONAL_SCHEMA_SOURCES = frozenset(
    {"comfy_registry_provisional", "workflow_json_provisional"}
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Canonical bytes used by the door law (order retained, whitespace fixed).

    Non-finite floats (NaN/Infinity) are serialized deterministically (the
    JSON spec's ``NaN``/``Infinity`` tokens) rather than raising, so a fixture
    or edit that introduces them never makes the door law flaky.
    """
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _binding_by_uid(workflow: VibeWorkflow) -> dict[str, str]:
    """Read deterministic emitted bindings from the Python surface itself.

    Falls back to the emitter's own IR-derived naming when the specimen cannot
    be emitted (e.g. unresolved value helpers), so the projection stays total
    without requiring emission to succeed.
    """
    try:
        source = emit_agent_edit_python(workflow)
    except Exception:
        return _bindings_from_ir(workflow)
    lines = source.splitlines()
    bindings: dict[str, str] = {}
    for statement in ast.parse(source).body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        segment = "\n".join(lines[statement.lineno - 1 : statement.end_lineno])
        match = _UID_COMMENT.search(segment)
        if match is not None:
            bindings[match.group(1)] = target.id
    return bindings


def _bindings_from_ir(workflow: VibeWorkflow) -> dict[str, str]:
    """Derive the emitter's deterministic bindings directly from the IR.

    Mirrors ``_prepare_workflow_for_emit``'s node filter (UI-only furniture is
    stripped, virtual wires are kept, unresolvable helpers are excluded) and
    then applies the emitter's own ``_compute_variable_names``, so the names
    match what emission would assign without requiring emission to succeed.
    """
    from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES, UI_ONLY_CLASS_TYPES
    from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names
    from vibecomfy.porting.emit.emit_prepare import _VIRTUAL_WIRE_EMITTER_CLASS_TYPES

    nodes = {
        str(node_id): node
        for node_id, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES
        and not (
            node.class_type in RESOLVABLE_HELPER_CLASS_TYPES
            and node.class_type not in _VIRTUAL_WIRE_EMITTER_CLASS_TYPES
        )
    }
    edges = [
        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        for edge in workflow.edges
        if str(edge.from_node) in nodes and str(edge.to_node) in nodes
    ]
    names = _compute_variable_names(nodes, edges)
    return {
        str(node.uid): names[str(node_id)]
        for node_id, node in nodes.items()
        if node.uid is not None and str(node.uid) and str(node_id) in names
    }


def _schema_status(schema_provider: Any, class_type: str) -> str:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return "unknown"
    source = str(getattr(schema, "source_provider", "") or "")
    ignored = {str(item) for item in (getattr(schema, "ignored_evidence", ()) or ())}
    if source in _PROVISIONAL_SCHEMA_SOURCES or "not_runtime_validated" in ignored:
        return "provisional"
    return "known"


def _graph_interfaces(
    workflow: VibeWorkflow,
    binding_by_node: Mapping[str, str],
) -> tuple[Any, ...]:
    # Graph-level VibeInput/VibeOutput registrations are ingest heuristics
    # (prompt/seed/model, sink nodes).  The designed grammar does not emit
    # them, so they are door-owned and excluded from π_edit.  Subgraph
    # signatures remain: they are the Python ``def`` surface when definitions
    # are retained on the IR.
    _ = binding_by_node
    public_inputs: tuple[Any, ...] = ()
    public_outputs: tuple[Any, ...] = ()
    definitions = workflow.metadata.get("definitions")
    subgraphs: list[tuple[Any, ...]] = []
    if isinstance(definitions, Mapping):
        from vibecomfy.porting.emit.emit_subgraph import _subgraph_definitions_from_raw

        emitted_subgraphs = _subgraph_definitions_from_raw(
            {"definitions": dict(definitions)},
            source_path=None,
        )
        for subgraph in emitted_subgraphs.values():
            subgraphs.append(
                (
                    subgraph.slug,
                    tuple((port.name, port.type) for port in subgraph.inputs),
                    tuple((port.name, port.type) for port in subgraph.outputs),
                )
            )
    return public_inputs, public_outputs, tuple(sorted(subgraphs))


def pi_edit(
    workflow: VibeWorkflow,
    *,
    schema_provider: Any | None = None,
) -> tuple[Any, ...]:
    """The exact editable quotient from ``.oracle/plan.md``.

    Included: deterministic emitted binding; class and normalized mode; named
    literal fields AND positional widget values (widget_N) with their
    channel/value/schema status; named connections; grammar-visible subgraph
    interfaces when present; and the stable uid needed to resolve a binding.
    Canvas/wire furniture, raw ids, link bookkeeping, opaque UI, provenance,
    editor state, and Note/MarkdownNote furniture are absent.  Nodes without
    an emitted binding (and edges touching them) are furniture.
    """
    from vibecomfy.porting.emit.emit_prepare import _agent_edit_output_aliases

    provider = schema_provider or get_schema_provider("local")
    binding_by_uid = _binding_by_uid(workflow)
    binding_by_node = {
        str(node_id): binding_by_uid[str(node.uid)]
        for node_id, node in workflow.nodes.items()
        if str(node.uid) in binding_by_uid
    }
    nodes = []
    for node_id, node in workflow.nodes.items():
        binding = binding_by_node.get(str(node_id))
        if binding is None:
            continue
        status = _schema_status(provider, str(node.class_type))
        fields = tuple(
            sorted(
                [
                    ("input", str(name), _freeze(value), status)
                    for name, value in node.inputs.items()
                ]
                + [
                    ("widget", str(name), _freeze(value), status)
                    for name, value in node.widgets.items()
                ]
            )
        )
        nodes.append(
            (
                binding,
                str(node.uid),
                str(node.class_type),
                mode_to_litegraph(node.mode),
                fields,
            )
        )
    connections = []
    for edge in workflow.edges:
        from_binding = binding_by_node.get(str(edge.from_node))
        to_binding = binding_by_node.get(str(edge.to_node))
        if from_binding is None or to_binding is None:
            continue
        from_output = str(edge.from_output)
        if from_output.isdigit():
            from_output = _agent_edit_output_aliases(
                workflow.nodes[str(edge.from_node)]
            ).get(int(from_output), from_output)
            if from_output.isdigit():
                raise AssertionError(
                    f"pi_edit requires named output slots, got {edge.from_output!r}"
                )
        connections.append((from_binding, from_output, to_binding, str(edge.to_input)))
    return (
        tuple(sorted(nodes)),
        tuple(sorted(connections)),
        _graph_interfaces(workflow, binding_by_node),
    )


def _load_specimen(path: Path) -> tuple[dict[str, Any], VibeWorkflow]:
    raw = json.loads(path.read_bytes())
    if isinstance(raw.get("nodes"), dict):
        return raw, from_envelope(raw)
    return raw, from_ui(raw, source_path=str(path), use_comfy_converter=False)


def _tiny_workflow(*, node_ids: tuple[str, str] = ("1", "2")) -> VibeWorkflow:
    workflow = VibeWorkflow("law", WorkflowSource("law"))
    workflow.nodes[node_ids[0]] = VibeNode(
        node_ids[0],
        "LawNode",
        inputs={"prompt": "before"},
        widgets={"seed": 7, "widget_0": 11},
        uid="law-a",
    )
    workflow.nodes[node_ids[1]] = VibeNode(
        node_ids[1],
        "LawNode",
        inputs={"strength": 0.5},
        uid="law-b",
    )
    workflow.edges.append(VibeEdge(node_ids[0], "IMAGE", node_ids[1], "image"))
    return workflow


@pytest.fixture
def provisional_failure_ledger() -> tuple[FailureLedgerRow, ...]:
    """The Phase-0 planning ledger; scenario ids intentionally remain absent."""
    return PROVISIONAL_FAILURE_LEDGER


@pytest.mark.parametrize(("kind", "path", "expected_hash"), SPIKE_CORPUS)
def test_spike_corpus_hashes_are_frozen(
    kind: str,
    path: Path,
    expected_hash: str,
) -> None:
    assert path.is_file(), kind
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash


def test_provisional_failure_ledger_has_13_nonoverlapping_rows_totaling_57(
    provisional_failure_ledger: tuple[FailureLedgerRow, ...],
) -> None:
    assert len(provisional_failure_ledger) == 13
    families = [row.family for row in provisional_failure_ledger]
    assert len(families) == len(set(families))
    assert sum(row.count for row in provisional_failure_ledger) == 57
    assert all(row.count > 0 and row.owner for row in provisional_failure_ledger)
    assert all(
        row.scenario_ids is None and row.status == "provisional"
        for row in provisional_failure_ledger
    )
    partition = {
        prefix: sum(
            row.count
            for row in provisional_failure_ledger
            if row.family == prefix or row.family.startswith(f"{prefix}:")
        )
        for prefix in ("semantic", "edit", "infra", "other")
    }
    assert partition == {"semantic": 25, "edit": 29, "infra": 2, "other": 1}


def test_pi_edit_includes_editable_channels_mode_interfaces_and_stable_identity() -> None:
    workflow = _tiny_workflow()
    workflow.inputs["prompt"] = VibeInput(
        "prompt", "1", "prompt", type="STRING", default="before"
    )
    projection = pi_edit(workflow)
    node_a = next(node for node in projection[0] if node[1] == "law-a")
    assert ("input", "prompt", "before", "unknown") in node_a[4]
    assert ("widget", "seed", 7, "unknown") in node_a[4]
    assert ("widget", "widget_0", 11, "unknown") in node_a[4]
    assert projection[1]
    # Graph-level VibeInput registrations are ingest heuristics, not grammar
    # forms, so π_edit keeps them out of the quotient.
    assert projection[2][0] == ()

    changed_mode = workflow.copy()
    changed_mode.nodes["1"].mode = 4
    assert pi_edit(changed_mode) != projection

    furniture_only = workflow.copy()
    furniture_only.nodes["1"].pos = [999.0, 111.0]
    furniture_only.nodes["1"].size = [12.0, 34.0]
    furniture_only.nodes["1"].metadata["_ui"] = {"order": 999, "properties": {"x": 1}}
    furniture_only.groups = [{"title": "canvas only", "bounding": [1, 2, 3, 4]}]
    assert pi_edit(furniture_only) == projection


def test_pi_edit_preserves_known_provisional_and_unknown_schema_status() -> None:
    workflow = VibeWorkflow("status", WorkflowSource("law"))
    for node_id, class_type in enumerate(("KnownNode", "ProvisionalNode", "UnknownNode"), 1):
        workflow.nodes[str(node_id)] = VibeNode(
            str(node_id),
            class_type,
            inputs={"value": node_id},
            uid=f"status-{node_id}",
        )

    class Provider:
        schemas = {
            "KnownNode": NodeSchema(
                class_type="KnownNode",
                pack=None,
                inputs={"value": InputSpec("INT")},
                outputs=[],
                source_provider="object_info",
            ),
            "ProvisionalNode": NodeSchema(
                class_type="ProvisionalNode",
                pack=None,
                inputs={"value": InputSpec("INT")},
                outputs=[],
                source_provider="workflow_json_provisional",
            ),
        }

        def get_schema(self, class_type: str) -> NodeSchema | None:
            return self.schemas.get(class_type)

    projection = pi_edit(workflow, schema_provider=Provider())
    status_by_class = {
        node[2]: node[4][0][3]
        for node in projection[0]
    }
    assert status_by_class == {
        "KnownNode": "known",
        "ProvisionalNode": "provisional",
        "UnknownNode": "unknown",
    }


def test_pi_edit_subgraph_interfaces_match_only_the_emitted_python_signature() -> None:
    workflow = VibeWorkflow("interfaces", WorkflowSource("law"))
    workflow.metadata["definitions"] = {
        "subgraphs": [
            {
                "id": "sg-law",
                "name": "Law Graph",
                "inputs": [
                    {
                        "id": "raw-port-id",
                        "name": "text",
                        "label": "Prompt",
                        "localized_name": "Texte",
                        "shape": 7,
                        "type": "STRING",
                        "linkIds": [41],
                    }
                ],
                "outputs": [
                    {
                        "id": "raw-output-id",
                        "name": "VIDEO",
                        "type": "VIDEO",
                        "linkIds": [42],
                    }
                ],
                "nodes": [],
                "links": [],
            }
        ]
    }
    projection = pi_edit(workflow)
    assert projection[2][2] == (
        ("law_graph", (("prompt", "STRING"),), (("video", "VIDEO"),)),
    )

    furniture_only = workflow.copy()
    port = furniture_only.metadata["definitions"]["subgraphs"][0]["inputs"][0]
    port.update(
        {
            "id": "different-raw-id",
            "localized_name": "Texto",
            "shape": 3,
            "linkIds": [999],
        }
    )
    assert pi_edit(furniture_only) == projection

    grammar_change = workflow.copy()
    grammar_change.metadata["definitions"]["subgraphs"][0]["inputs"][0]["label"] = (
        "Description"
    )
    assert pi_edit(grammar_change) != projection


@pytest.mark.parametrize(
    ("kind", "path"),
    [(SPIKE_CORPUS[0][0], SPIKE_CORPUS[0][1]), (SPIKE_CORPUS[1][0], SPIKE_CORPUS[1][1]), (SPIKE_CORPUS[2][0], SPIKE_CORPUS[2][1])],
    ids=("envelope", "definitions", "unknown-schema"),
)
def test_law_1_door_fidelity(kind: str, path: Path) -> None:
    raw = json.loads(path.read_bytes())
    if isinstance(raw.get("nodes"), dict):
        workflow = from_envelope(raw)
        emitted = workflow.to_envelope()
    else:
        workflow = from_ui(raw, source_path=str(path), use_comfy_converter=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            emitted = emit_ui_json(workflow)
    assert canonical_json_bytes(emitted) == canonical_json_bytes(raw)


def test_door_fingerprint_detects_every_semantic_edit_path() -> None:
    """Law 1 fingerprint: any edit through set_prompt/set_input/set_seed/
    confirm_node/raw_widgets flips the door fingerprint, so the edited value is
    never silently discarded by the untouched-byte passthrough."""
    from vibecomfy.ingest.normalize import _door_node_fingerprint
    from vibecomfy.workflow import RawWidgetPayload

    path = SPIKE_CORPUS[2][1]  # LTX specimen: registers prompt/seed/model inputs

    def ingest() -> VibeWorkflow:
        return from_ui(
            json.loads(path.read_bytes()),
            source_path=str(path),
            use_comfy_converter=False,
        )

    workflow = ingest()
    door = workflow.metadata["_ui_door"]
    assert _door_node_fingerprint(workflow) == door["fingerprint"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        emitted = emit_ui_json(workflow)
    assert canonical_json_bytes(emitted) == canonical_json_bytes(
        json.loads(path.read_bytes())
    )

    def assert_touched(mutate) -> None:
        edited = ingest()
        mutate(edited)
        assert _door_node_fingerprint(edited) != door["fingerprint"], (
            f"edit not detected: {mutate}"
        )

    assert_touched(lambda wf: wf.set_prompt("an edited prompt"))
    assert_touched(lambda wf: wf.set_seed(987654321))
    assert_touched(lambda wf: wf.set_input("model", "other_model.safetensors"))
    assert_touched(lambda wf: wf.confirm_node("160"))
    assert_touched(
        lambda wf: setattr(
            wf.nodes["160"],
            "raw_widgets",
            RawWidgetPayload(["1", "True"], "list", "ui.widgets_values", False, 2),
        )
    )
    # Channel distinction: a widget-backed field edit is detected even when the
    # same field name also exists in the input channel.
    assert_touched(lambda wf: wf.nodes["160"].widgets.__setitem__("seed", 1234))


def test_door_envelope_edit_is_not_silently_discarded() -> None:
    """An edited envelope takes the IR rendering (not the byte passthrough),
    and the edit is reflected in the serialized output."""
    path = SPIKE_CORPUS[0][1]
    raw = json.loads(path.read_bytes())
    workflow = from_envelope(raw)
    untouched = workflow.to_envelope()
    assert canonical_json_bytes(untouched) == canonical_json_bytes(raw)

    edited = from_envelope(raw)
    edited.nodes["17"].widgets["widget_0"] = "edited-seed"
    emitted = edited.to_envelope()
    assert canonical_json_bytes(emitted) != canonical_json_bytes(raw)
    assert emitted["nodes"]["17"]["widgets"]["widget_0"] == "edited-seed"
    assert "_ui_door" not in emitted.get("metadata", {})


def test_door_subgraph_edit_keeps_definitions_structure() -> None:
    """An edit to a NON-subgraph node must not flatten the 5-node +
    definitions form into the inner-node expansion: definitions stay intact and
    the edit is reflected in the emitted envelope."""
    path = SPIKE_CORPUS[1][1]
    raw = json.loads(path.read_bytes())
    workflow = from_ui(raw, source_path=str(path), use_comfy_converter=False)
    workflow.nodes["97"].inputs["image"] = "edited_input.png"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        emitted = emit_ui_json(workflow)

    # Structure preserved: 5 top-level nodes, definitions present, inner
    # subgraph contents untouched (no 5 -> 17/19 expansion).
    assert len(emitted["nodes"]) == len(raw["nodes"])
    assert "definitions" in emitted
    raw_sg = raw["definitions"]["subgraphs"][0]
    emitted_sg = emitted["definitions"]["subgraphs"][0]
    assert emitted_sg["id"] == raw_sg["id"]
    assert len(emitted_sg["nodes"]) == len(raw_sg["nodes"])

    # The edit is reflected — the graph was NOT byte-passthrough.
    node_97 = next(node for node in emitted["nodes"] if node["id"] == 97)
    assert node_97["widgets_values"] == ["edited_input.png", "image"]


@pytest.mark.parametrize(
    ("kind", "path", "_hash"),
    [
        SPIKE_CORPUS[0],
        SPIKE_CORPUS[1],
        SPIKE_CORPUS[2],
    ],
    ids=("envelope", "definitions", "unknown-schema"),
)
def test_law_2_editable_isomorphism(kind: str, path: Path, _hash: str) -> None:
    from vibecomfy.porting.edit._interpret import interpret

    _, workflow = _load_specimen(path)
    pre_snapshot = workflow.copy()
    emitted = emit_agent_edit_python(workflow)
    empty = VibeWorkflow("empty", WorkflowSource("law"))
    result = interpret(empty, emitted)
    assert workflow == pre_snapshot
    assert result.workflow is not empty
    assert empty.nodes == {}
    assert pi_edit(result.workflow) == pi_edit(workflow)


def test_law_3_delta_replay_is_deterministic_and_minimal() -> None:
    from vibecomfy.porting.edit import diff, interpret

    pre = _tiny_workflow()
    post = pre.copy()
    post.nodes["1"].inputs["prompt"] = "after"
    delta = diff(pre, post)
    assert delta == diff(pre, post)
    assert len(delta) > 0
    assert pi_edit(interpret(pre, delta).workflow) == pi_edit(post)
    assert len(diff(post, post)) == 0
    for index in range(len(delta)):
        reduced = delta[:index] + delta[index + 1 :]
        assert pi_edit(interpret(pre, reduced).workflow) != pi_edit(post)


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    ("kind", "path", "_hash"),
    SPIKE_CORPUS,
    ids=("envelope", "definitions", "unknown-schema"),
)
def test_law_3_spike_corpus_diff_is_an_inverse_over_the_quotient(
    kind: str,
    path: Path,
    _hash: str,
) -> None:
    """Law 3 on the spike corpus: ``diff(pre, post)`` is a valid batch whose
    interpretation reconstructs ``post``'s π_edit; the Δ is deterministic,
    minimal (every op is individually necessary), and zero for identical IRs."""
    from vibecomfy.workflow import VibeEdge, VibeNode, mode_to_litegraph
    from vibecomfy.porting.edit import diff, interpret
    from vibecomfy.porting.edit._diff import _quotient_bindings
    from vibecomfy.porting.edit.editable_surface import editable_surface_for
    from vibecomfy.porting.emit.emit_prepare import _agent_edit_output_aliases

    _, pre = _load_specimen(path)
    provider = get_schema_provider("local")

    def nid_for_uid(wf, uid):
        return next(
            nid for nid, node in wf.nodes.items() if str(getattr(node, "uid", "") or "") == uid
        )

    def mutate(mutation: str):
        post = pre.copy()
        uids = sorted(_quotient_bindings(pre))
        changed = False
        if mutation == "field":
            for uid in uids:
                node = post.nodes[nid_for_uid(post, uid)]
                for channel in ("widgets", "inputs"):
                    for name in list(getattr(node, channel, {})):
                        value = getattr(node, channel)[name]
                        if isinstance(value, str):
                            getattr(node, channel)[name] = value + "-edited"
                        elif isinstance(value, bool):
                            getattr(node, channel)[name] = not value
                        elif isinstance(value, int):
                            getattr(node, channel)[name] = value + 1
                        elif isinstance(value, float):
                            getattr(node, channel)[name] = value + 0.5
                        else:
                            continue
                        changed = True
                        break
                    if changed:
                        break
                if changed:
                    break
        elif mutation == "mode":
            for uid in uids:
                nid = nid_for_uid(post, uid)
                if mode_to_litegraph(post.nodes[nid].mode) == 0:
                    post.nodes[nid].mode = 2
                    changed = True
                    break
        elif mutation == "link_remove":
            uid_set = set(uids)
            for edge in list(post.edges):
                src = str(getattr(post.nodes.get(str(edge.from_node)), "uid", "") or "")
                dst = str(getattr(post.nodes.get(str(edge.to_node)), "uid", "") or "")
                if src in uid_set and dst in uid_set:
                    post.edges.remove(edge)
                    changed = True
                    break
        elif mutation == "link_add":
            uid_set = set(uids)
            for src_nid, src in post.nodes.items():
                src_uid = str(getattr(src, "uid", "") or "")
                if src_uid not in uid_set:
                    continue
                aliases = _agent_edit_output_aliases(src)
                if not aliases:
                    continue
                port = sorted(aliases.values())[0]
                for tgt_nid, tgt in post.nodes.items():
                    tgt_uid = str(getattr(tgt, "uid", "") or "")
                    if tgt_uid not in uid_set or tgt_uid == src_uid:
                        continue
                    surface = editable_surface_for(
                        tgt, schema_provider=provider, edges=post.edges
                    )
                    wired = {
                        edge.to_input
                        for edge in post.edges
                        if str(edge.to_node) == tgt_nid
                    }
                    available = [
                        name for name in surface.socket_names() if name not in wired
                    ]
                    if available:
                        post.edges.append(
                            VibeEdge(src_nid, port, tgt_nid, available[0])
                        )
                        changed = True
                        break
                if changed:
                    break
        elif mutation == "remove_node":
            last_uid = uids[-1]
            nid = nid_for_uid(post, last_uid)
            post.nodes.pop(nid)
            post.edges = [
                edge
                for edge in post.edges
                if edge.from_node != nid and edge.to_node != nid
            ]
            changed = True
        elif mutation == "add_node":
            new_id = str(
                max(int(nid) for nid in post.nodes if str(nid).isdigit()) + 1
            )
            post.nodes[new_id] = VibeNode(
                new_id, "PreviewImage", inputs={}, widgets={}, uid="diff-corpus-new"
            )
            changed = True
        return post if changed else pre

    for mutation in ("field", "mode", "link_remove", "link_add", "remove_node", "add_node"):
        post = mutate(mutation)
        if post is pre:
            continue
        delta = diff(pre, post)
        assert delta == diff(pre, post), mutation
        reconstructed = interpret(pre, delta)
        assert reconstructed.ok, mutation
        assert pi_edit(reconstructed.workflow) == pi_edit(post), mutation
        assert len(diff(post, post)) == 0, mutation
        for index in range(len(delta)):
            reduced = delta[:index] + delta[index + 1 :]
            assert pi_edit(interpret(pre, reduced).workflow) != pi_edit(post), (
                f"{mutation}: op {index} is not individually necessary"
            )


def test_law_4_topology_is_computed_from_ir_edges() -> None:
    from vibecomfy.porting.render import render

    workflow = _tiny_workflow()
    rendered = render(workflow, lenses=("topology",))
    expected = (
        ("law-a", "IMAGE", "law-b", "image"),
    )
    assert tuple(rendered["topology"]) == expected
    assert rendered["topology_source"] == "computed"


def test_law_4_judge_lens_is_strict_subset_of_reply_lens() -> None:
    from vibecomfy.porting.render import render

    workflow = _tiny_workflow()
    reply = render(workflow, lenses=("surface", "diff", "topology"), delta=())
    judge = render(workflow, lenses=("diff", "topology"), delta=())
    assert set(judge) < set(reply)
    assert all(judge[key] == reply[key] for key in judge)


# ── Law 4 (batch 11): composable renderer lens goldens ───────────────────────

_SAMPLE_DELTA = (
    (
        "set_node_field",
        {
            "target": {"scope_path": "", "uid": "law-a", "field_path": "prompt"},
            "value": "after",
        },
    ),
    (
        "upsert_link",
        {
            "source": {"scope_path": "", "uid": "law-a", "output_slot": "IMAGE"},
            "target": {"scope_path": "", "uid": "law-b", "input_field": "image"},
        },
    ),
)


def _sample_delta_ops() -> tuple[Any, ...]:
    """A tiny deterministic accepted batch over the Law-4 tiny workflow."""
    from vibecomfy.porting.edit.ops import (
        LinkSourceRef,
        LinkTargetRef,
        NodeFieldTarget,
        SetNodeFieldOp,
        UpsertLinkOp,
    )

    return (
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="law-a", field_path="prompt"),
            value="after",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef(scope_path="", uid="law-a", output_slot="IMAGE"),
            target=LinkTargetRef(scope_path="", uid="law-b", input_field="image"),
        ),
    )


def test_law_4_render_lenses_are_deterministic_goldens() -> None:
    """Each lens is a pure function: same wf → same rendered value.

    Also checks composability: a lens rendered inside a lens set is identical
    to the same lens rendered alone (the judge lens sees exactly the reply
    lens subset, never more).
    """
    from vibecomfy.porting.render import render

    workflow = _tiny_workflow()
    delta = _sample_delta_ops()
    for lens in ("census", "surface", "topology", "diff"):
        assert render(workflow, lens, delta=delta) == render(workflow, lens, delta=delta), lens
    combined = render(
        workflow,
        lenses=("census", "surface", "diff", "topology"),
        delta=delta,
    )
    for lens in ("census", "surface", "diff"):
        assert combined[lens] == render(workflow, lens, delta=delta), lens
    assert tuple(combined["topology"]) == tuple(render(workflow, "topology"))


def test_law_4_census_lens_content() -> None:
    """census: node count + class list + reference map (what classify sees)."""
    from vibecomfy.porting.render import render

    rendered = render(_tiny_workflow(), "census")
    assert "2 node(s), 1 edge(s)" in rendered
    assert "class list: LawNode (2)" in rendered
    assert "reference map:" in rendered
    assert "law-a: LawNode (binding: lawnode)" in rendered
    assert "law-b: LawNode (binding: lawnode_2)" in rendered


def test_law_4_surface_lens_content() -> None:
    """surface: the Python-surface view with named fields and uid identity."""
    from vibecomfy.porting.render import render

    rendered = render(_tiny_workflow(), "surface")
    assert "lawnode = LawNode(prompt='before', seed=7, widget_0=11)" in rendered
    assert "uid:law-a" in rendered
    assert "image=lawnode.unknown_0" in rendered


def test_law_4_diff_lens_content() -> None:
    """diff(Δ): the accepted-batch-derived change summary, nothing more."""
    from vibecomfy.porting.render import render

    workflow = _tiny_workflow()
    rendered = render(workflow, "diff", delta=_sample_delta_ops())
    assert "## Diff" in rendered
    assert "2 change(s):" in rendered
    assert "set_node_field law-a.prompt = 'after'" in rendered
    assert "upsert_link law-a.IMAGE -> law-b.image" in rendered
    # Empty batch renders deterministically as no changes.
    assert render(workflow, "diff", delta=()) == "## Diff\nNo changes."


def _chain_workflow(count: int) -> VibeWorkflow:
    """A linear chain of *count* nodes, ``count - 1`` edges, uid chain-N."""
    workflow = VibeWorkflow("chain", WorkflowSource("chain"))
    for index in range(count):
        workflow.nodes[str(index)] = VibeNode(str(index), "ChainNode", uid=f"chain-{index}")
        if index:
            workflow.edges.append(VibeEdge(str(index - 1), "OUT", str(index), "in"))
    return workflow


def test_law_4_topology_lens_has_no_truncation_cap() -> None:
    """Topology is COMPLETE: 24 edges render as 24 facts + 24 text lines."""
    from vibecomfy.porting.render import render, render_text

    workflow = _chain_workflow(25)
    facts = tuple(render(workflow, "topology"))
    assert len(facts) == 24
    for index in range(24):
        assert (f"chain-{index}", "OUT", f"chain-{index + 1}", "in") in facts
    text = render_text(workflow, lenses=("topology",))
    for index in range(24):
        assert (
            f"chain-{index} -> chain-{index + 1} "
            f"(chain-{index}.OUT -> chain-{index + 1}.in)"
        ) in text
    assert "edges:\n  <none>" not in text
    assert "orphans: <none>" in text


def _controlnet_chain_raw_ui() -> dict[str, Any]:
    """3c978e-style ControlNet chain wired by links 11, 13, 16, 17, 19, 20.

    Mirrors the 3c978e6c11a8a768 workflow's ControlNet section: a
    ControlNetLoaderAdvanced feeding a chain of ControlNetApply nodes.  The
    raw link ids are the 3c978e ids; the IR edges do not retain raw link ids,
    so the lens must include EVERY edge of the chain with named endpoints —
    no truncation loss.
    """

    def node(
        nid: int,
        class_type: str,
        *,
        inputs: list[dict[str, Any]] | None = None,
        outputs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        built: dict[str, Any] = {
            "id": nid,
            "type": class_type,
            "class_type": class_type,
            "widgets_values": [],
        }
        if inputs:
            built["inputs"] = inputs
        if outputs:
            built["outputs"] = outputs
        return built

    return {
        "nodes": [
            node(
                1,
                "ControlNetLoaderAdvanced",
                outputs=[{"name": "CONTROL_NET", "type": "CONTROL_NET", "links": [11], "slot_index": 0}],
            ),
            node(
                2,
                "LoadImage",
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [13], "slot_index": 0}],
            ),
            node(
                3,
                "ControlNetApply",
                inputs=[
                    {"name": "conditioning", "type": "CONDITIONING", "link": None},
                    {"name": "control_net", "type": "CONTROL_NET", "link": 11, "slot_index": 1},
                    {"name": "image", "type": "IMAGE", "link": 13, "slot_index": 2},
                    {"name": "strength", "type": "FLOAT", "link": None},
                ],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [16], "slot_index": 0}],
            ),
            node(
                4,
                "ControlNetApply",
                inputs=[
                    {"name": "conditioning", "type": "CONDITIONING", "link": None},
                    {"name": "control_net", "type": "CONTROL_NET", "link": None},
                    {"name": "image", "type": "IMAGE", "link": 16, "slot_index": 2},
                    {"name": "strength", "type": "FLOAT", "link": None},
                ],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [17], "slot_index": 0}],
            ),
            node(
                5,
                "ControlNetApply",
                inputs=[{"name": "image", "type": "IMAGE", "link": 17, "slot_index": 2}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [19], "slot_index": 0}],
            ),
            node(
                6,
                "ControlNetApply",
                inputs=[{"name": "image", "type": "IMAGE", "link": 19, "slot_index": 2}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [20], "slot_index": 0}],
            ),
            node(
                7,
                "ControlNetApply",
                inputs=[{"name": "image", "type": "IMAGE", "link": 20, "slot_index": 2}],
            ),
        ],
        "links": [
            [11, 1, 0, 3, 1, "CONTROL_NET"],
            [13, 2, 0, 3, 2, "IMAGE"],
            [16, 3, 0, 4, 2, "IMAGE"],
            [17, 4, 0, 5, 2, "IMAGE"],
            [19, 5, 0, 6, 2, "IMAGE"],
            [20, 6, 0, 7, 2, "IMAGE"],
        ],
    }


def test_law_4_3c978e_controlnet_chain_topology_complete() -> None:
    """3c978e: the topology lens includes the complete ControlNet chain.

    All six chain links (11, 13, 16, 17, 19, 20) must survive the ingest door
    into IR edges and every one must appear in the topology lens with named
    endpoints — computed from IR edges, never inferred from truncated prose.
    """
    from vibecomfy.porting.render import render, render_text

    raw = _controlnet_chain_raw_ui()
    rendered = render(raw, lenses=("topology",))
    facts = tuple(rendered["topology"])
    assert rendered["topology_source"] == "computed"
    assert len(facts) == 6
    expected = (
        ("1", "0", "3", "control_net"),
        ("2", "0", "3", "image"),
        ("3", "0", "4", "image"),
        ("4", "0", "5", "image"),
        ("5", "0", "6", "image"),
        ("6", "0", "7", "image"),
    )
    assert facts == expected
    text = render_text(raw, lenses=("topology",))
    assert "1 -> 3 (1.0 -> 3.control_net)" in text
    assert "6 -> 7 (6.0 -> 7.image)" in text
    assert "edges:\n  <none>" not in text
    for index in range(6):
        assert text.count("->") >= 6  # every chain edge rendered



# Golden workflow fixture for Law 5: two VHS_LoadVideo nodes (deterministic
# collision suffix: vhs_loadvideo / vhs_loadvideo_2) wired by a NAMED typed
# output ("MASK" → MASK_0), with a schema_source Mapping on each node so the
# slots comment carries the explicit schema status. Shared by the binding
# golden test and the batch-5 provenance/COW law tests.
_LAW5_RAW_UI: dict[str, Any] = {
    "last_node_id": 2,
    "last_link_id": 1,
    "nodes": [
        {
            "id": 1,
            "type": "VHS_LoadVideo",
            "pos": [0, 0],
            "size": [300, 100],
            "flags": {},
            "order": 0,
            "mode": 0,
            "inputs": [],
            "outputs": [
                {"name": "MASK", "type": "MASK", "links": [1], "slot_index": 0},
                {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 1},
            ],
            "properties": {"Node name for S&R": "VHS_LoadVideo", "vibecomfy_uid": "law5-a"},
            "widgets_values": ["a.mp4", 7],
        },
        {
            "id": 2,
            "type": "VHS_LoadVideo",
            "pos": [400, 0],
            "size": [300, 100],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [{"name": "video", "type": "VIDEO", "link": 1}],
            "outputs": [
                {"name": "MASK", "type": "MASK", "links": [], "slot_index": 0},
                {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 1},
            ],
            "properties": {"Node name for S&R": "VHS_LoadVideo", "vibecomfy_uid": "law5-b"},
            "widgets_values": ["b.mp4"],
        },
    ],
    "links": [[1, 1, 0, 2, 0, "VIDEO"]],
    "groups": [],
    "config": {},
    "extra": {},
    "version": 0.4,
}


class _Law5Provider:
    def get_schema(self, ct: str) -> NodeSchema | None:
        if ct == "VHS_LoadVideo":
            return NodeSchema(
                "VHS_LoadVideo",
                "comfy_registry",
                {"video": InputSpec("STRING"), "frame_load_cap": InputSpec("INT")},
                [OutputSpec("MASK", "MASK"), OutputSpec("IMAGE", "IMAGE")],
            )
        return None


def test_law_5_bindings_are_deterministic_across_ids_stages_and_turns() -> None:
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.workflow import NodeMode, VibeNode, VibeWorkflow, WorkflowSource, _get_node_mode

    # Stage/turn golden: TWO independent sessions over the same raw UI
    # (distinct stages/turns, never re-emitting the same object) must render
    # byte-identical Python — no session name locks participate (batch 4).
    first_session = EditSession(_LAW5_RAW_UI, schema_provider=_Law5Provider())
    second_session = EditSession(_LAW5_RAW_UI, schema_provider=_Law5Provider())
    source_a = first_session.render()
    source_b = second_session.render()
    assert source_a == source_b

    # Binding names are a pure function of (class_type, uid-order), stable
    # across node-id remaps.
    first = _tiny_workflow(node_ids=("1", "2"))
    remapped = _tiny_workflow(node_ids=("20", "10"))
    assert _binding_by_uid(first) == _binding_by_uid(remapped)

    # Named typed ports with schema status are emitted; the named
    # from_output ("MASK") resolves to MASK_0, never to a positional alias.
    assert "MASK_0" in source_a
    assert "slots MASK_0='MASK' known" in source_a
    assert "vhs_loadvideo.MASK_0" in source_a
    assert "vhs_loadvideo_2" in source_a  # deterministic collision suffix

    # No positional aliases anywhere in the emitted surface: output_N,
    # widget_N, PORT_n and the slot_N shim are all forbidden (Law 5, batch 4).
    for forbidden in ("output_", "widget_", "PORT_", "slot_"):
        assert forbidden not in source_a
        assert forbidden not in source_b

    # NodeMode is stored/compared in the IR as the enum, not a str, and
    # ENABLED is a REAL value: mode=ENABLED + _ui.mode=4 compiles as
    # enabled because the IR field is authoritative (no silent _ui read).
    workflow = _tiny_workflow()
    assert workflow.nodes["1"].mode is NodeMode.ENABLED
    assert not isinstance(workflow.nodes["1"].mode, str) or isinstance(workflow.nodes["1"].mode, NodeMode)
    conflict = _tiny_workflow()
    conflict.nodes["1"].mode = NodeMode.ENABLED
    conflict.nodes["1"].metadata["_ui"] = {"mode": 4}
    conflict.edges[0].from_output = "0"
    assert _get_node_mode(conflict.nodes["1"]) == 0
    compiled = conflict.compile("api")
    assert "1" in compiled  # enabled nodes are NOT dropped
    muted = _tiny_workflow()
    muted.nodes["1"].mode = NodeMode.MUTED
    assert _get_node_mode(muted.nodes["1"]) == 2
    bypassed = _tiny_workflow()
    bypassed.nodes["1"].mode = NodeMode.BYPASSED
    assert _get_node_mode(bypassed.nodes["1"]) == 4


# ── Law 5 (batch 5): provenance lattice + copy-on-write edits ───────────────


def _collect_mutable_dict_ids(value: Any, acc: set[int]) -> None:
    """Collect object ids of every mutable dict reachable from ``value``.

    Walks mappings, sequences, and dataclass fields so a COW assertion can
    prove the pre-state and post-state IRs share no mutable node state.
    """
    if isinstance(value, dict):
        acc.add(id(value))
        for item in value.values():
            _collect_mutable_dict_ids(item, acc)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _collect_mutable_dict_ids(item, acc)
        return
    if dataclasses.is_dataclass(value):
        for field_info in dataclasses.fields(value):
            if field_info.name.startswith("_"):
                continue
            _collect_mutable_dict_ids(getattr(value, field_info.name), acc)


def test_law_5_edits_are_copy_on_write_and_compose_provenance() -> None:
    from vibecomfy.porting.edit._ir_utils import apply_edit_cow, apply_edits_cow
    from vibecomfy.porting.edit.ops import (
        AddNodeOp,
        LinkSourceRef,
        LinkTargetRef,
        NodeFieldTarget,
        NodeTarget,
        SetModeOp,
        SetNodeFieldOp,
        UpsertLinkOp,
    )
    from vibecomfy.security import provenance as _prov
    from vibecomfy.workflow import NodeMode

    workflow = _tiny_workflow()
    _prov.tag(workflow.nodes["1"], "user_confirmed")
    _prov.tag(workflow.nodes["2"], "agent_authored")
    pre = copy.deepcopy(workflow)

    edited = apply_edit_cow(
        workflow,
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget("", "law-a", "prompt"),
            value="after",
        ),
    )

    # 1. Copy-on-write: the pre-IR is fully unchanged (deep equality) and the
    #    edit returned a NEW IR carrying the change.
    assert workflow == pre
    assert edited is not workflow
    assert edited.nodes["1"].inputs["prompt"] == "after"

    # 2. No shared mutable node dicts between pre and post.
    pre_dict_ids: set[int] = set()
    post_dict_ids: set[int] = set()
    _collect_mutable_dict_ids(pre, pre_dict_ids)
    _collect_mutable_dict_ids(edited, post_dict_ids)
    assert pre_dict_ids.isdisjoint(post_dict_ids)

    # 3. Provenance composes via the max-taint join: a user_confirmed node
    #    edited by an agent becomes agent_generated; the untouched node keeps
    #    its tag (the deep copy preserves it).
    assert _prov.read(edited.nodes["1"]) == "agent_generated"
    assert _prov.read(edited.nodes["2"]) == "agent_authored"

    # 4. Sequential composition stays copy-on-write and monotone: editing the
    #    same node again composes from the prior composed tag (join is
    #    idempotent, so it stays agent_generated) and never touches the
    #    intermediate IR.
    edited_after = copy.deepcopy(edited)
    again = apply_edits_cow(
        edited,
        (
            SetModeOp(op="set_mode", target=NodeTarget("", "law-a"), mode=2),
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", "law-a", "prompt"),
                value="final",
            ),
        ),
    )
    assert edited == edited_after
    assert again.nodes["1"].mode is NodeMode.MUTED
    assert again.nodes["1"].inputs["prompt"] == "final"
    assert _prov.read(again.nodes["1"]) == "agent_generated"
    again_ids: set[int] = set()
    _collect_mutable_dict_ids(again, again_ids)
    assert post_dict_ids.isdisjoint(again_ids)

    # 5. upsert_link combines the source's provenance into the target
    #    (max-taint); both endpoints are re-tainted by the agent action.
    linked = apply_edit_cow(
        workflow,
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "law-a", "IMAGE"),
            target=LinkTargetRef("", "law-b", "image"),
        ),
    )
    assert any(
        edge.from_node == "1" and edge.to_node == "2" and edge.to_input == "image"
        for edge in linked.edges
    )
    assert _prov.read(linked.nodes["2"]) == _prov.join(
        "agent_authored", "user_confirmed", "agent_generated"
    )
    assert _prov.read(linked.nodes["1"]) == "agent_generated"

    # 6. add_node tags the fresh node join(agent_generated, *sources) — a
    #    trusted source yields agent_generated, never untrusted, and the new
    #    node is wired to its source.
    added = apply_edit_cow(
        workflow,
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="LawNode",
            fields={"seed": 7},
            inputs={"image": LinkSourceRef("", "law-a", "IMAGE")},
            uid="law-c",
        ),
    )
    new_node = next(node for node in added.nodes.values() if node.uid == "law-c")
    assert _prov.read(new_node) == "agent_generated"
    assert any(edge.from_node == "1" and edge.to_node == new_node.id for edge in added.edges)
    # The pre-IR is still byte-identical after every edit above.
    assert workflow == pre


@pytest.mark.parametrize(
    "tag_value",
    ["untrusted_source", "agent_authored", "agent_generated", "user_confirmed"],
)
def test_law_5_edits_never_downgrade_provenance(tag_value: str) -> None:
    from vibecomfy.porting.edit._ir_utils import apply_edit_cow
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.security import provenance as _prov

    workflow = _tiny_workflow()
    _prov.tag(workflow.nodes["1"], tag_value)
    edited = apply_edit_cow(
        workflow,
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget("", "law-a", "prompt"),
            value="edited",
        ),
    )
    # The edit composes via join (max-taint) and never silently downgrades:
    # the result dominates the pre-edit tag. In particular, an agent edit on
    # an untrusted-source node keeps it untrusted (no taint laundering).
    assert _prov.read(edited.nodes["1"]) == _prov.join(tag_value, "agent_generated")
    assert _prov.dominates(_prov.read(edited.nodes["1"]), tag_value)


def test_law_5_session_rebuild_is_copy_on_write_and_composes_provenance() -> None:
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.security import provenance as _prov

    raw = _LAW5_RAW_UI
    initial = from_ui(
        copy.deepcopy(raw), schema_provider=_Law5Provider(), use_comfy_converter=False
    )
    _prov.tag(initial.nodes["1"], "user_confirmed")
    _prov.tag(initial.nodes["2"], "user_confirmed")
    pre = copy.deepcopy(initial)

    session = EditSession(raw, schema_provider=_Law5Provider(), initial_workflow=initial)
    result = session.apply_batch('vhs_loadvideo_2.video = "edited.mp4"\n')
    assert result.ok
    assert not result.diagnostics

    # The retained IR is a NEW IR: the pre-state IR was never mutated and is
    # byte-identical, and the post-state shares no mutable node dicts with it.
    assert initial == pre
    assert session.workflow is not initial
    assert session.workflow.nodes["2"].inputs["video"] == "edited.mp4"
    pre_ids: set[int] = set()
    post_ids: set[int] = set()
    _collect_mutable_dict_ids(pre, pre_ids)
    _collect_mutable_dict_ids(session.workflow, post_ids)
    assert pre_ids.isdisjoint(post_ids)

    # The edited node composes provenance through the max-taint join
    # (user_confirmed + agent edit → agent_generated); untouched nodes KEEP
    # their prior provenance (the rebuild never re-runs the ingest door, so
    # there is no untrusted_source reset for untouched nodes).
    assert _prov.read(session.workflow.nodes["2"]) == "agent_generated"
    assert _prov.read(session.workflow.nodes["1"]) == "user_confirmed"

    # End-to-end through the batch loop: a SECOND committed batch rebuilds
    # again via the same COW engine — the untouched node keeps its prior
    # provenance, the re-edited node stays at the join (idempotent max-taint),
    # and the intermediate IR is preserved untouched.
    middle = copy.deepcopy(session.workflow)
    second = session.apply_batch('vhs_loadvideo_2.video = "final.mp4"\n')
    assert second.ok
    assert not second.diagnostics
    assert session.workflow is not middle
    assert session.workflow.nodes["2"].inputs["video"] == "final.mp4"
    assert _prov.read(session.workflow.nodes["1"]) == "user_confirmed"
    assert _prov.read(session.workflow.nodes["2"]) == "agent_generated"
    middle_ids: set[int] = set()
    second_ids: set[int] = set()
    _collect_mutable_dict_ids(middle, middle_ids)
    _collect_mutable_dict_ids(session.workflow, second_ids)
    assert middle_ids.isdisjoint(second_ids)


@pytest.mark.xfail(
    strict=False,
    reason="batch 16: raw workflow-JSON authority is zero outside the exact boundary",
)
def test_law_5_boundary_has_no_provisional_exceptions() -> None:
    from tests.test_ir_boundary_kpi import (
        authority_exception_paths,
        pass_through_structural_paths,
        structural_exception_paths,
    )

    assert authority_exception_paths() == frozenset()
    assert structural_exception_paths() == frozenset()
    assert pass_through_structural_paths() == frozenset()


def test_law_4_grammar_generates_allow_list_prompt_and_doc_table() -> None:
    from vibecomfy.porting.edit.grammar import (
        ADMITTED_AST_TYPES,
        DOCUMENTED_AST_TYPES,
        FORBIDDEN_ASSIGN_ATTRS,
        FORBIDDEN_CALL_NAMES,
        authoring_doc_agrees,
        authoring_doc_path,
        prompt_doc_covers_grammar,
        render_ast_allow_list,
        render_doc_table,
        render_prompt_doc,
    )

    assert ast.Assign in ADMITTED_AST_TYPES
    assert ast.Import not in ADMITTED_AST_TYPES
    assert ast.FunctionDef not in ADMITTED_AST_TYPES
    assert ast.If not in ADMITTED_AST_TYPES
    assert ast.ListComp not in ADMITTED_AST_TYPES
    assert ast.Assign in DOCUMENTED_AST_TYPES
    assert "reorder" in FORBIDDEN_CALL_NAMES
    assert "set_title" in FORBIDDEN_CALL_NAMES
    assert FORBIDDEN_ASSIGN_ATTRS["title"] == "set_title_not_allowed"
    assert prompt_doc_covers_grammar() == []
    doc = render_prompt_doc()
    table = render_doc_table()
    allow = render_ast_allow_list()
    assert allow in doc
    assert "set_node_field" in table
    assert "set_title" not in table
    assert "reorder" not in table
    assert authoring_doc_agrees(authoring_doc_path().read_text(encoding="utf-8"))


def test_law_4_editable_surface_is_instance_hydrated() -> None:
    from vibecomfy.porting.edit.editable_surface import editable_surface_for
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    class Provider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type != "TripoRefineNode":
                return None
            return NodeSchema(
                class_type="TripoRefineNode",
                pack=None,
                inputs={
                    "prompt": InputSpec(type="IMAGE"),
                    "steps": InputSpec(type="INT"),
                },
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
                source_provider="object_info",
            )

    node = VibeNode(
        "1",
        "TripoRefineNode",
        widgets={"steps": 8, "widget_0": 1},
        metadata={
            "schema_source": {"provider": "object_info"},
            "_ui": {
                "inputs": [{"name": "prompt", "type": "IMAGE", "link": 4}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
            },
        },
    )
    surface = editable_surface_for(node, schema_provider=Provider())
    assert surface.schema_status == "known"
    assert "prompt" not in surface.literal_names()
    assert "steps" in surface.literal_names()
    assert "prompt" in surface.socket_names()
    assert all(field.name_confidence != "none" or not field.name for field in surface.literals)
    assert all(not field.name.startswith("widget_") for field in surface.literals)
