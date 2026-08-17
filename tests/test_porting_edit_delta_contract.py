from __future__ import annotations

import pytest

from vibecomfy.porting.edit.ops import (
    DELTA_DIAGNOSTIC_LEGACY_SHAPE,
    DELTA_DIAGNOSTIC_MALFORMED,
    DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
    DELTA_SCHEMA_VERSION,
    EditOpParseError,
    canonical_op_to_dict,
    ensure_root_scoped_delta_envelope,
    normalize_delta_envelope,
    op_to_dict,
    parse_edit_delta,
)


CANONICAL_OP_CASES = (
    {
        "op": "set_node_field",
        "target": ["", "seed-node", "inputs.seed"],
        "value": 7,
    },
    {
        "op": "set_mode",
        "target": ["", "mute-node"],
        "mode": 4,
    },
    {
        "op": "add_node",
        "scope_path": "",
        "uid": "new-uid",
        "node_id": "9001",
        "class_type": "PreviewImage",
        "fields": {"filename_prefix": "after"},
        "inputs": {"images": ["", "seed-node", "IMAGE"]},
    },
    {
        "op": "upsert_link",
        "from": ["", "seed-node", "IMAGE"],
        "to": ["", "preview-node", "images"],
    },
    {
        "op": "remove_node",
        "target": ["", "old-node"],
    },
    {
        "op": "remove_link",
        "to": ["", "preview-node", "images"],
    },
)


@pytest.mark.parametrize(
    "payload",
    CANONICAL_OP_CASES,
    ids=[case["op"] for case in CANONICAL_OP_CASES],
)
def test_canonical_delta_op_roundtrips_through_parse_normalize_and_serialize(
    payload: dict[str, object],
) -> None:
    parsed_ops = parse_edit_delta([payload])
    assert len(parsed_ops) == 1

    parsed_op = parsed_ops[0]
    assert op_to_dict(parsed_op) == payload
    assert canonical_op_to_dict(parsed_op) == payload

    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [payload],
        }
    )
    assert envelope.to_dict() == {
        "schema_version": DELTA_SCHEMA_VERSION,
        "ops": [payload],
    }

    reparsed = normalize_delta_envelope(envelope.to_dict())
    assert tuple(canonical_op_to_dict(op) for op in reparsed.ops) == (payload,)
    assert reparsed.to_dict() == envelope.to_dict()


def test_canonical_delta_envelope_roundtrips_all_six_ops_together() -> None:
    payload = {
        "schema_version": DELTA_SCHEMA_VERSION,
        "ops": list(CANONICAL_OP_CASES),
    }

    envelope = normalize_delta_envelope(payload)
    reparsed = normalize_delta_envelope(envelope.to_dict())

    assert tuple(canonical_op_to_dict(op) for op in envelope.ops) == CANONICAL_OP_CASES
    assert tuple(canonical_op_to_dict(op) for op in reparsed.ops) == CANONICAL_OP_CASES
    assert reparsed.to_dict() == payload


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("uid", "Canonical add_node ops must include `uid`."),
        ("node_id", "Canonical add_node ops must include `node_id`."),
    ],
)
def test_normalize_delta_envelope_rejects_add_node_missing_required_identity(
    field: str,
    message: str,
) -> None:
    add_node = dict(CANONICAL_OP_CASES[2])
    del add_node[field]

    with pytest.raises(EditOpParseError, match=message) as exc_info:
        normalize_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [add_node],
            }
        )

    assert exc_info.value.code == DELTA_DIAGNOSTIC_MALFORMED
    assert exc_info.value.detail == {"op": "add_node", "field": field}


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            [{"op": "set_node_field", "target": ["", "only-two"], "value": 1}],
            r"target must be a list of length 3",
        ),
        (
            [{"op": "remove_node", "target": "u1"}],
            r"target must be a list of length 2",
        ),
        (
            [{"op": "upsert_link", "from": ["", "u1"], "to": ["", "u2", "images"]}],
            r"from must be a list of length 3",
        ),
        (
            [{"op": "remove_link", "to": ["", "u2"]}],
            r"to must be a list of length 3",
        ),
    ],
)
def test_parse_edit_delta_rejects_bad_target_and_source_shapes(
    payload: list[dict[str, object]],
    match: str,
) -> None:
    with pytest.raises(EditOpParseError, match=match) as exc_info:
        parse_edit_delta(payload)

    assert exc_info.value.code == DELTA_DIAGNOSTIC_MALFORMED


@pytest.mark.parametrize(
    "payload",
    [
        [{"op": "rename_everything", "target": ["", "u1"], "value": "x"}],
        [{"op": "noop"}],
        {"schema_version": DELTA_SCHEMA_VERSION, "ops": [{"op": "rename_everything"}]},
    ],
)
def test_delta_contract_rejects_unknown_ops(payload: object) -> None:
    with pytest.raises(EditOpParseError, match="Unsupported edit op") as exc_info:
        if isinstance(payload, dict):
            normalize_delta_envelope(payload)
        else:
            parse_edit_delta(payload)

    assert exc_info.value.code == DELTA_DIAGNOSTIC_MALFORMED


@pytest.mark.parametrize(
    ("payload", "expected_keys"),
    [
        ({"delta_ops": {"ops": []}}, ["delta_ops"]),
        ({"ops": [], "diagnostics": []}, ["diagnostics", "ops"]),
        (
            {"schema_version": DELTA_SCHEMA_VERSION, "ops": [], "automatic_link_removals": []},
            ["automatic_link_removals", "ops"],
        ),
    ],
)
def test_normalize_delta_envelope_rejects_legacy_wrapped_shapes(
    payload: dict[str, object],
    expected_keys: list[str],
) -> None:
    with pytest.raises(EditOpParseError) as exc_info:
        normalize_delta_envelope(payload)

    assert exc_info.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE
    assert exc_info.value.detail == {"keys": expected_keys}


def test_ensure_root_scoped_delta_envelope_reports_non_root_scope_diagnostics() -> None:
    with pytest.raises(
        EditOpParseError,
        match="Non-root scoped apply is unsupported for canonical delta consumers.",
    ) as exc_info:
        ensure_root_scoped_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [
                    {
                        "op": "upsert_link",
                        "from": ["sg:nested", "seed-node", "IMAGE"],
                        "to": ["", "preview-node", "images"],
                    }
                ],
            }
        )

    assert exc_info.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY
    assert exc_info.value.detail == {
        "scope_paths": ["sg:nested"],
        "op": "upsert_link",
    }


# ── T4: Producer / persistence tests ────────────────────────────────────────


def test_add_node_op_to_dict_includes_uid_and_node_id_when_present() -> None:
    """The flat legacy bridge (``op_to_dict``) carries uid/node_id when populated."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={"filename_prefix": "after"},
        inputs={},
        uid="assigned-uid",
        node_id="42",
    )
    payload = op_to_dict(op)
    assert payload["uid"] == "assigned-uid"
    assert payload["node_id"] == "42"


def test_add_node_op_to_dict_omits_uid_and_node_id_when_none() -> None:
    """The flat legacy bridge omits uid/node_id when they are None (pre-apply)."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={},
        inputs={},
    )
    payload = op_to_dict(op)
    assert "uid" not in payload
    assert "node_id" not in payload


def test_canonical_op_to_dict_rejects_add_node_missing_uid() -> None:
    """Strict canonicalisation rejects add_node without uid."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={},
        inputs={},
        node_id="42",
    )
    with pytest.raises(EditOpParseError, match="must include `uid`"):
        canonical_op_to_dict(op)


def test_canonical_op_to_dict_rejects_add_node_missing_node_id() -> None:
    """Strict canonicalisation rejects add_node without node_id."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    op = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="PreviewImage",
        fields={},
        inputs={},
        uid="some-uid",
    )
    with pytest.raises(EditOpParseError, match="must include `node_id`"):
        canonical_op_to_dict(op)


def test_normalize_delta_envelope_non_strict_accepts_add_node_without_identity() -> None:
    """Pre-apply normalization (strict=False) accepts add_node without uid/node_id."""
    add_node_dict = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "PreviewImage",
        "fields": {},
        "inputs": {},
    }
    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [add_node_dict],
        },
        strict=False,
    )
    assert len(envelope.ops) == 1
    # Re-serialized via op_to_dict (tolerant) should match the input
    assert op_to_dict(envelope.ops[0]) == add_node_dict


def test_normalize_delta_envelope_strict_rejects_add_node_without_identity() -> None:
    """Post-apply normalization (strict=True, the default) rejects add_node
    without uid/node_id."""
    add_node_dict = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "PreviewImage",
        "fields": {},
        "inputs": {},
    }
    with pytest.raises(EditOpParseError, match="must include `uid`"):
        normalize_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [add_node_dict],
            },
            strict=True,
        )


def test_add_node_roundtrip_through_non_strict_then_strict_after_populate() -> None:
    """Simulate the pre-apply → apply → post-apply flow: parse without identity,
    populate uid/node_id, then strict-canonicalise successfully."""
    from vibecomfy.porting.edit.ops import AddNodeOp

    # Pre-apply: model returns add_node without uid/node_id
    pre_apply_dict = {
        "op": "add_node",
        "scope_path": "",
        "class_type": "PreviewImage",
        "fields": {"filename_prefix": "after"},
        "inputs": {"images": ["", "seed-node", "IMAGE"]},
    }
    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [pre_apply_dict],
        },
        strict=False,
    )
    pre_op = envelope.ops[0]
    assert isinstance(pre_op, AddNodeOp)
    assert pre_op.uid is None
    assert pre_op.node_id is None

    # Apply assigns uid/node_id (simulated)
    populated_op = AddNodeOp(
        op=pre_op.op,
        scope_path=pre_op.scope_path,
        class_type=pre_op.class_type,
        fields=dict(pre_op.fields),
        inputs=dict(pre_op.inputs),
        anchor=pre_op.anchor,
        uid="minted-uid",
        node_id="101",
    )

    # Post-apply: strict canonicalisation succeeds
    canonical = canonical_op_to_dict(populated_op)
    assert canonical["uid"] == "minted-uid"
    assert canonical["node_id"] == "101"
    assert canonical["scope_path"] == ""
    assert canonical["class_type"] == "PreviewImage"

    # Full envelope roundtrip with strict
    strict_envelope = ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [canonical],
        },
        strict=True,
    )
    assert strict_envelope.to_dict()["ops"] == [canonical]


def test_agent_delta_turn_result_produces_envelope_and_flat_bridge_never_legacy_wrapped() -> None:
    """``AgentDeltaTurnResult.to_dict()`` emits ``delta_ops_envelope`` (canonical)
    and ``delta_ops`` (derived flat legacy bridge), never a legacy wrapped mapping."""
    from vibecomfy.porting.edit.ops import AgentDeltaTurnResult, AddNodeOp

    result = AgentDeltaTurnResult(
        delta=(
            AddNodeOp(
                op="add_node",
                scope_path="",
                class_type="PreviewImage",
                fields={},
                inputs={},
                uid="uid-1",
                node_id="99",
            ),
        ),
        message="added node",
        route="test",
        model="agent-edit-v2",
        audit_metadata={"provider": "test"},
    )
    payload = result.to_dict()

    # Canonical envelope present
    assert "delta_ops_envelope" in payload
    envelope = payload["delta_ops_envelope"]
    assert envelope["schema_version"] == DELTA_SCHEMA_VERSION
    assert len(envelope["ops"]) == 1
    assert envelope["ops"][0]["uid"] == "uid-1"
    assert envelope["ops"][0]["node_id"] == "99"

    # Flat bridge mirrors the envelope ops (key is ``delta`` in to_dict())
    assert "delta" in payload
    assert payload["delta"] == envelope["ops"]

    # Never a legacy wrapped mapping
    assert "delta_ops" not in envelope  # envelope itself is clean
    assert "diagnostics" not in envelope
    assert "automatic_link_removals" not in envelope


def test_non_strict_normalize_never_emits_legacy_wrapped_shape() -> None:
    """Even with strict=False, normalization never emits a legacy wrapped
    ``delta_ops`` mapping — it always produces a ``{schema_version, ops}`` envelope."""
    envelope = normalize_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [],
        },
        strict=False,
    )
    payload = envelope.to_dict()
    assert set(payload.keys()) == {"schema_version", "ops"}
    assert "delta_ops" not in payload
    assert "diagnostics" not in payload


# ───────────────────────────────────────────────────────────────────────────
# Batch 9 (Law 3): canonical Δ is the batch value.
#
# ``diff(pre, post)`` returns the minimal deterministic batch (the same six-op
# grammar ``interpret`` accepts) that reconstructs ``post``'s π_edit from
# ``pre``.  No parallel prose/JSON delta representation exists: the Δ IS the
# batch.  The session's accepted batch is the recorded Δ; ``diff`` is the
# generalizer for judge/replay use.
# ───────────────────────────────────────────────────────────────────────────


def _law3_tiny_workflow():
    from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("delta-contract", WorkflowSource("delta-contract"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "LawNode",
        inputs={"prompt": "before"},
        widgets={"seed": 7, "widget_0": 11},
        uid="law-a",
    )
    workflow.nodes["2"] = VibeNode(
        "2", "LawNode", inputs={"strength": 0.5}, uid="law-b"
    )
    workflow.edges.append(VibeEdge("1", "IMAGE", "2", "image"))
    return workflow


def _pi_edit(workflow):
    from tests.test_ir_laws import pi_edit

    return pi_edit(workflow)


def test_diff_returns_a_valid_batch_that_interpret_accepts() -> None:
    """diff(pre, post) is expressed in the SAME grammar interpret accepts and
    replays to post's π_edit — no parallel diff representation."""
    from vibecomfy.porting.edit import diff, interpret
    from vibecomfy.porting.edit.ops import CANONICAL_DELTA_OP_NAMES

    pre = _law3_tiny_workflow()
    post = pre.copy()
    post.nodes["1"].inputs["prompt"] = "after"
    delta = diff(pre, post)
    assert delta
    assert all(op.op in CANONICAL_DELTA_OP_NAMES for op in delta)
    # Same grammar: interpret accepts the typed ops directly.
    result = interpret(pre, delta)
    assert result.ok
    assert _pi_edit(result.workflow) == _pi_edit(post)


def test_diff_inverse_over_field_mode_link_and_node_edits() -> None:
    """interpret(pre, diff(pre, post)) == post over π_edit for every op kind."""
    from vibecomfy.porting.edit import diff, interpret
    from vibecomfy.workflow import NodeMode, VibeEdge, VibeNode

    def remove_link(post):
        post.edges = [
            e for e in post.edges if not (e.to_node == "2" and e.to_input == "image")
        ]

    def remove_node(post):
        post.nodes.pop("2")
        post.edges = [
            e for e in post.edges if e.from_node != "2" and e.to_node != "2"
        ]

    cases = {
        "set_node_field": lambda p: p.nodes["1"].widgets.__setitem__("seed", 99),
        "set_mode": lambda p: setattr(p.nodes["1"], "mode", NodeMode.MUTED),
        "remove_link": remove_link,
        "upsert_link": lambda p: p.edges.__setitem__(
            0, VibeEdge("2", "IMAGE", "1", "prompt")
        ),
        "add_node": lambda p: p.nodes.__setitem__(
            "3",
            VibeNode("3", "PreviewImage", inputs={}, widgets={}, uid="delta-new"),
        ),
        "remove_node": remove_node,
    }
    for label, mutate in cases.items():
        pre = _law3_tiny_workflow()
        post = pre.copy()
        mutate(post)
        delta = diff(pre, post)
        assert delta, label
        result = interpret(pre, delta)
        assert result.ok, label
        assert _pi_edit(result.workflow) == _pi_edit(post), label


def test_diff_is_minimal_deterministic_and_zero_for_identity() -> None:
    """Same (pre, post) → same Δ; every op is individually necessary;
    identical IRs produce the empty batch."""
    from vibecomfy.porting.edit import diff, interpret

    pre = _law3_tiny_workflow()
    post = pre.copy()
    post.nodes["1"].inputs["prompt"] = "after"
    post.nodes["2"].inputs["strength"] = 0.75
    delta = diff(pre, post)
    assert delta == diff(pre, post)
    # Undo round-trip over the quotient: diff(post, pre) replays back to pre.
    undo = interpret(post, diff(post, pre))
    assert undo.ok
    assert _pi_edit(undo.workflow) == _pi_edit(pre)
    assert diff(post, post) == ()
    assert diff(pre, pre) == ()
    for index in range(len(delta)):
        reduced = delta[:index] + delta[index + 1 :]
        assert _pi_edit(interpret(pre, reduced).workflow) != _pi_edit(post)


def test_diff_generalizes_interpret_accepted_batch() -> None:
    """diff(pre, interpret(pre, batch)) produces the Δ equivalent to the
    accepted statements (minimal and deterministic)."""
    from vibecomfy.porting.edit import diff, interpret

    pre = _law3_tiny_workflow()
    batch = (
        'lawnode.prompt = "after"\n'
        "lawnode.seed = 42\n"
        "lawnode.mode = 4\n"
    )
    interpreted = interpret(pre, batch)
    assert interpreted.ok
    delta = diff(pre, interpreted.workflow)
    assert len(delta) == 3  # one op per landed edit statement
    assert {op.op for op in delta} == {"set_node_field", "set_mode"}
    assert _pi_edit(interpret(pre, delta).workflow) == _pi_edit(interpreted.workflow)
    assert delta == diff(pre, interpreted.workflow)


def test_diff_cumulative_replay_and_undo_roundtrip() -> None:
    """Cumulative replay: interpret(pre, Δ1 + Δ2) == wf_2.  Undo: diff walks
    the same chain backwards over the quotient."""
    from vibecomfy.porting.edit import diff, interpret
    from vibecomfy.workflow import VibeEdge, VibeNode

    wf0 = _law3_tiny_workflow()
    post1 = wf0.copy()
    post1.nodes["3"] = VibeNode(
        "3", "PreviewImage", inputs={}, widgets={}, uid="delta-new"
    )
    post1.edges.append(VibeEdge("1", "IMAGE", "3", "images"))
    d1 = diff(wf0, post1)
    wf1 = interpret(wf0, d1).workflow
    assert _pi_edit(wf1) == _pi_edit(post1)

    post2 = wf1.copy()
    post2.nodes["1"].inputs["prompt"] = "final"
    d2 = diff(wf1, post2)
    wf2 = interpret(wf1, d2).workflow
    assert _pi_edit(wf2) == _pi_edit(post2)

    # Cumulative replay: concatenated deltas reach the same quotient.
    combined = interpret(wf0, d1 + d2)
    assert combined.ok
    assert _pi_edit(combined.workflow) == _pi_edit(wf2)

    # Undo: diff(wf2, wf1) then diff(wf1, wf0) walks back to the start.
    back1 = interpret(wf2, diff(wf2, wf1))
    assert _pi_edit(back1.workflow) == _pi_edit(wf1)
    back0 = interpret(back1.workflow, diff(back1.workflow, wf0))
    assert _pi_edit(back0.workflow) == _pi_edit(wf0)


# ───────────────────────────────────────────────────────────────────────────
# Batch 9 fix — Law 3 hard cases (oracle issues 1-3).
# ───────────────────────────────────────────────────────────────────────────


def _law3_roundtrip(pre, post, label: str) -> None:
    """Law 3 on a concrete (pre, post) pair: deterministic, replayable,
    minimal, and zero for identity."""
    from vibecomfy.porting.edit import diff, interpret

    delta = diff(pre, post)
    assert delta == diff(pre, post), label
    result = interpret(pre, delta)
    assert result.ok, label
    assert _pi_edit(result.workflow) == _pi_edit(post), label
    assert diff(post, post) == (), label
    undo = interpret(post, diff(post, pre))
    assert undo.ok, label
    assert _pi_edit(undo.workflow) == _pi_edit(pre), label
    for index in range(len(delta)):
        reduced = delta[:index] + delta[index + 1 :]
        assert _pi_edit(interpret(pre, reduced).workflow) != _pi_edit(post), (
            f"{label}: op {index} is not individually necessary"
        )


def test_diff_preserves_unknown_schema_widgets_through_rebuild() -> None:
    """Law 3 on a widget-set rebuild of an unknown-schema node: the named
    widget fields must survive the diff→interpret round-trip in the WIDGET
    channel (oracle issue 1)."""
    from vibecomfy.porting.edit import diff
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    pre = VibeWorkflow("delta-hard", WorkflowSource("delta-contract"))
    pre.nodes["1"] = VibeNode(
        "1",
        "TotallyUnknownClassABC",
        inputs={"model": "x"},
        widgets={"my_widget": 5, "widget_0": 9},
        uid="law-a",
    )
    post = pre.copy()
    post.nodes["1"].class_type = "TotallyUnknownClassXYZ"  # forces rebuild
    _law3_roundtrip(pre, post, "unknown-schema widget rebuild")
    # The widget channel is preserved by the batch itself (not schema luck).
    add = [op for op in diff(pre, post) if op.op == "add_node"][0]
    assert "my_widget" in add.widget_field_names


def test_diff_add_node_mixed_schema_and_unknown_widgets() -> None:
    """Law 3 for a fresh add-node carrying known-schema widgets, a positional
    widget, and an unknown-schema named widget (oracle issue 1/3)."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    pre = VibeWorkflow("delta-hard", WorkflowSource("delta-contract"))
    pre.nodes["1"] = VibeNode("1", "PreviewImage", inputs={}, widgets={}, uid="law-a")
    post = pre.copy()
    post.nodes["2"] = VibeNode(
        "2",
        "TotallyUnknownMixin",
        inputs={"schema_input": "z"},
        widgets={"known_widget": 3, "widget_0": 11, "mystery_widget": "v"},
        uid="law-b",
    )
    _law3_roundtrip(pre, post, "mixed schema/unknown add-node")


def test_diff_reconstructs_subgraph_interface_deltas() -> None:
    """Law 3 on subgraph signatures: add/change/remove of
    ``metadata["definitions"]`` subgraphs must be carried by the batch
    (oracle issue 2) on the subgraphed_wan specimen."""
    from vibecomfy.porting.edit import diff, interpret
    from tests.test_ir_laws import SPIKE_CORPUS, _load_specimen

    _, pre = _load_specimen(SPIKE_CORPUS[1][1])
    assert (pre.metadata.get("definitions") or {}).get("subgraphs")

    def mutate(mutation: str):
        post = pre.copy()
        subs = post.metadata.setdefault("definitions", {}).setdefault("subgraphs", [])
        if mutation == "change":
            subs[0]["inputs"] = [{"name": "edited_in", "type": "IMAGE", "label": "edited_in"}]
            subs[0]["outputs"] = [{"name": "edited_out", "type": "IMAGE"}]
        elif mutation == "remove":
            subs.pop(0)
        elif mutation == "add":
            subs.append(
                {
                    "id": "sg-extra",
                    "name": "Extra Subgraph",
                    "inputs": [{"name": "in_a", "type": "LATENT", "label": "in_a"}],
                    "outputs": [{"name": "out_a", "type": "LATENT"}],
                    "nodes": [],
                    "links": [],
                }
            )
        return post

    for mutation in ("change", "remove", "add"):
        post = mutate(mutation)
        _law3_roundtrip(pre, post, f"subgraph {mutation}")
        delta = diff(pre, post)
        assert any(op.op == "subgraph_interface" for op in delta), mutation
        # The ops are a valid batch source: interpret applies them.
        assert interpret(pre, delta).ok, mutation
