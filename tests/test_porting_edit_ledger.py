from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.porting.edit.ledger import EditLedger


def _fixture(name: str) -> dict:
    path = Path("tests/fixtures/agent_edit") / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_edit_ledger_stamps_root_fixture_and_resolves_root_nodes() -> None:
    raw = _fixture("flat.json")

    ledger = EditLedger.ingest(raw)

    assert "" in ledger.scopes
    assert ledger.diagnostics == ()
    for node in ledger.graph["nodes"]:
        uid = node["properties"]["vibecomfy_uid"]
        assert uid == str(node["id"])
        assert ledger.resolve_node("", uid) is node


def test_edit_ledger_stamps_subgraph_fixture_and_resolves_subgraph_nodes() -> None:
    raw = _fixture("subgraphed_wan_i2v.json")

    ledger = EditLedger.ingest(raw)

    subgraph_scopes = [scope for scope in ledger.scopes.values() if scope.kind == "subgraph"]
    assert len(subgraph_scopes) == 1

    scope = subgraph_scopes[0]
    assert scope.path_tokens[:2] == ("definitions", "subgraphs")
    assert scope.scope_path

    inner = scope.graph["nodes"][0]
    inner_uid = inner["properties"]["vibecomfy_uid"]
    assert inner_uid == str(inner["id"])
    assert ledger.resolve_node(scope.scope_path, inner_uid) is inner
    assert ledger.qualified_uid(scope.scope_path, inner_uid).endswith(f"#{inner_uid}")


def test_edit_ledger_duplicate_uids_are_suffixed_per_scope_and_reported() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "A", "properties": {"vibecomfy_uid": "dup"}},
            {"id": 2, "type": "B", "properties": {"vibecomfy_uid": "dup"}},
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "name": "Inner",
                    "nodes": [
                        {"id": 10, "type": "C", "properties": {"vibecomfy_uid": "dup"}},
                        {"id": 11, "type": "D", "properties": {"vibecomfy_uid": "dup"}},
                    ],
                    "links": [],
                }
            ]
        },
    }

    ledger = EditLedger.ingest(raw)

    root_uids = [node["properties"]["vibecomfy_uid"] for node in ledger.graph["nodes"]]
    assert root_uids == ["dup", "dup~2"]
    root_diag = next(issue for issue in ledger.diagnostics if issue.detail["scope_path"] == "")
    assert root_diag.code == "duplicate_scope_uid"

    scope = next(scope for scope in ledger.scopes.values() if scope.kind == "subgraph")
    inner_uids = [node["properties"]["vibecomfy_uid"] for node in scope.graph["nodes"]]
    assert inner_uids == ["dup", "dup~2"]
    subgraph_diag = next(
        issue for issue in ledger.diagnostics if issue.detail["scope_path"] == scope.scope_path
    )
    assert subgraph_diag.code == "duplicate_scope_uid"
    assert ledger.resolve_node(scope.scope_path, "dup~2") is scope.graph["nodes"][1]


def test_edit_ledger_counter_seeding_uses_explicit_values_and_mints_globally_unique_ids() -> None:
    raw = {
        "last_node_id": 10,
        "last_link_id": 20,
        "nodes": [{"id": 10, "type": "Root", "properties": {}}],
        "links": [[20, 10, 0, 10, 0, "*"]],
        "definitions": {
            "subgraphs": [
                {
                    "name": "Inner",
                    "state": {"lastNodeId": 7, "lastLinkId": 8},
                    "nodes": [{"id": 7, "type": "InnerNode", "properties": {}}],
                    "links": [{"id": 8, "origin_id": 7, "origin_slot": 0, "target_id": 7, "target_slot": 0, "type": "*"}],
                }
            ]
        },
    }

    ledger = EditLedger.ingest(raw)

    scope = next(scope for scope in ledger.scopes.values() if scope.kind == "subgraph")
    assert ledger.scopes[""].node_counter == 10
    assert ledger.scopes[""].link_counter == 20
    assert scope.node_counter == 7
    assert scope.link_counter == 8

    assert ledger.mint_node_id("") == 11
    assert ledger.mint_node_id(scope.scope_path) == 12
    assert ledger.mint_link_id(scope.scope_path) == 21
    assert ledger.mint_link_id("") == 22


def test_edit_ledger_counter_seeding_falls_back_to_max_existing_ids() -> None:
    raw = {
        "nodes": [{"id": 4, "type": "Root", "properties": {}}],
        "links": [[3, 4, 0, 4, 0, "*"]],
        "definitions": {
            "subgraphs": [
                {
                    "name": "Inner",
                    "nodes": [{"id": 6, "type": "InnerNode", "properties": {}}],
                    "links": [{"id": 9, "origin_id": 6, "origin_slot": 0, "target_id": 6, "target_slot": 0, "type": "*"}],
                }
            ]
        },
    }

    ledger = EditLedger.ingest(raw)

    scope = next(scope for scope in ledger.scopes.values() if scope.kind == "subgraph")
    assert ledger.scopes[""].node_counter == 4
    assert ledger.scopes[""].link_counter == 3
    assert scope.node_counter == 6
    assert scope.link_counter == 9

    assert ledger.mint_node_id("") == 7
    assert ledger.mint_link_id(scope.scope_path) == 10


def test_edit_ledger_mints_never_reused_local_uids_per_scope() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "Root", "properties": {"vibecomfy_uid": "n1"}},
            {"id": 2, "type": "Root", "properties": {"vibecomfy_uid": "custom"}},
        ],
        "links": [],
    }

    ledger = EditLedger.ingest(raw)

    assert ledger.mint_uid("") == "n2"
    assert ledger.mint_uid("") == "n3"

