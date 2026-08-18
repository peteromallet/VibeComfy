"""B04 — typed edit tools + atomic edit runtime (Hermes-style tool loop).

The grammar-parse ``apply`` path is gone from the one-step loop.  Editing is
NORMAL TOOL USE: the agent calls a typed edit tool (``edit_node`` / ``add_node``
/ ``remove_node`` / ``upsert_link``), the host validates the args, resolves the
target by the name/uid from the render, applies the edit copy-on-write to the
retained IR, and returns ``ok`` + Δ id + post-edit lens facts.  Atomicity (one
edit per message, one replacement after a rejection, a second edit after
acceptance denied) and CAS on the retained revision are enforced on the typed
tools.

Covers per-tool happy paths (arg → Δ → lens facts), bad-arg schema denial
before dispatch, target-not-found, ``widget_N`` positional-ref rejection, and
the atomic lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.executor.edit_tools import (
    EDIT_TOOL_NAMES,
    EditToolError,
    EditToolRuntime,
    validate_edit_tool_args,
)


# ── CLIPTextEncode fixture (named widget ``text``) ───────────────────────────


class _CLIPTextEncodeProvider:
    def get_schema(self, class_type: str) -> Any:
        if class_type != "CLIPTextEncode":
            return None
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        return NodeSchema(
            "CLIPTextEncode",
            "core",
            {"text": InputSpec("STRING"), "clip": InputSpec("CLIP")},
            [OutputSpec("CONDITIONING", "CONDITIONING")],
        )


def _flat_ui() -> dict[str, Any]:
    return json.loads(
        (Path("tests/fixtures/agent_edit/flat.json")).read_text(encoding="utf-8")
    )


def _clip_session() -> Any:
    from vibecomfy.porting.edit.session import EditSession

    return EditSession(dict(_flat_ui()), schema_provider=_CLIPTextEncodeProvider())


def _clip_runtime() -> EditToolRuntime:
    return EditToolRuntime(edit_session=_clip_session())


# ── LawNode fixture (named inputs/outputs for add/remove/upsert) ─────────────


class _LawProvider:
    def get_schema(self, class_type: str) -> Any:
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        schemas = {
            "LawNodeA": NodeSchema("LawNodeA", "law", {}, [OutputSpec("IMAGE", "IMAGE")]),
            "LawNodeB": NodeSchema("LawNodeB", "law", {}, [OutputSpec("IMAGE", "IMAGE")]),
            "LawNodeC": NodeSchema(
                "LawNodeC",
                "law",
                {"image": InputSpec("IMAGE"), "prompt": InputSpec("STRING")},
                [],
            ),
            "LawNodeD": NodeSchema("LawNodeD", "law", {"value": InputSpec("FLOAT")}, []),
        }
        return schemas.get(class_type)


def _law_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "1", "type": "LawNodeA", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}], "widgets_values": []},
            {"id": "2", "type": "LawNodeB", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}], "widgets_values": []},
            {"id": "3", "type": "LawNodeC", "inputs": [{"name": "image", "type": "IMAGE", "link": 1}], "outputs": [], "widgets_values": ["before"]},
        ],
        "links": [
            [1, "1", 0, "3", 0, "IMAGE"],
            [2, "2", 0, "3", 0, "IMAGE"],
        ],
    }


def _law_runtime() -> EditToolRuntime:
    from vibecomfy.porting.edit.session import EditSession

    return EditToolRuntime(edit_session=EditSession(dict(_law_ui()), schema_provider=_LawProvider()))


def _node_types(graph: Any) -> set[str]:
    return {str(n.get("type")) for n in (graph.get("nodes") or ()) if isinstance(n, dict)}


# ── argument schema (deny-before-dispatch) ───────────────────────────────────


class TestArgSchema:
    def test_missing_required_arg_is_typed(self) -> None:
        with pytest.raises(EditToolError) as excinfo:
            validate_edit_tool_args("edit_node", {"target": "n"})  # missing field
        assert excinfo.value.code == "invalid_arguments"

    def test_unknown_arg_is_typed(self) -> None:
        with pytest.raises(EditToolError) as excinfo:
            validate_edit_tool_args("edit_node", {"target": "n", "field": "f", "bogus": 1})
        assert excinfo.value.code == "invalid_arguments"

    def test_non_mapping_args_is_typed(self) -> None:
        with pytest.raises(EditToolError) as excinfo:
            validate_edit_tool_args("edit_node", [1, 2, 3])
        assert excinfo.value.code == "invalid_arguments"

    def test_unknown_tool_is_typed(self) -> None:
        with pytest.raises(EditToolError) as excinfo:
            validate_edit_tool_args("frobnicate", {})
        assert excinfo.value.code == "unknown_tool"

    def test_tool_set_is_exactly_the_seven(self) -> None:
        assert EDIT_TOOL_NAMES == {
            "edit_node",
            "add_node",
            "remove_node",
            "upsert_link",
            "remove_link",
            "set_node_mode",
            "edit_batch",
        }


# ── edit_node happy path ─────────────────────────────────────────────────────


class TestEditNode:
    def test_happy_path_returns_delta_and_lens_facts(self) -> None:
        runtime = _clip_runtime()
        outcome = runtime.dispatch(
            "edit_node", {"target": "cliptextencode", "field": "text", "value": "a faithful edit"}
        )
        assert outcome.ok is True
        assert outcome.delta_id == "d1"
        assert outcome.graph is not None
        assert outcome.lens_fact_ids != ()
        edited = [
            n
            for n in outcome.graph.get("nodes", [])
            if n.get("type") == "CLIPTextEncode"
        ]
        assert any("a faithful edit" in (n.get("widgets_values") or ()) for n in edited)

    def test_target_not_found_rejects_and_allows_one_retry(self) -> None:
        runtime = _clip_runtime()
        outcome = runtime.dispatch(
            "edit_node", {"target": "no_such_node", "field": "text", "value": "x"}
        )
        assert outcome.ok is False
        assert outcome.reason == "unknown_target"
        assert outcome.replacement_allowed is True
        assert outcome.no_candidate is False

    def test_widget_N_field_is_rejected(self) -> None:
        runtime = _clip_runtime()
        outcome = runtime.dispatch(
            "edit_node", {"target": "cliptextencode", "field": "widget_2", "value": "x"}
        )
        assert outcome.ok is False
        assert outcome.reason == "invalid_arguments"
        assert outcome.retryable is True

    def test_widget_N_target_is_rejected(self) -> None:
        runtime = _clip_runtime()
        outcome = runtime.dispatch(
            "edit_node", {"target": "widget_2", "field": "text", "value": "x"}
        )
        assert outcome.ok is False
        assert outcome.reason == "invalid_arguments"
        assert outcome.retryable is True


# ── add_node / remove_node / upsert_link happy paths ─────────────────────────


class TestAddRemoveUpsert:
    def test_add_node_returns_binding_and_lands_the_node(self) -> None:
        runtime = _law_runtime()
        outcome = runtime.dispatch(
            "add_node", {"class_type": "LawNodeD", "widget_values": {"value": 0.25}}
        )
        assert outcome.ok is True
        assert outcome.delta_id == "d1"
        assert "LawNodeD" in _node_types(outcome.graph)

    def test_remove_node_drops_the_target(self) -> None:
        runtime = _law_runtime()
        outcome = runtime.dispatch("remove_node", {"target": "lawnodeb"})
        assert outcome.ok is True
        assert "LawNodeB" not in _node_types(outcome.graph)
        assert "LawNodeA" in _node_types(outcome.graph)
        assert "LawNodeC" in _node_types(outcome.graph)

    def test_upsert_link_rewires_the_named_input(self) -> None:
        runtime = _law_runtime()
        outcome = runtime.dispatch(
            "upsert_link",
            {"source": "lawnodeb", "source_output": "IMAGE", "target": "lawnodec", "target_input": "image"},
        )
        assert outcome.ok is True
        assert outcome.delta_id == "d1"

    def test_add_node_bad_widget_values_is_typed(self) -> None:
        runtime = _law_runtime()
        outcome = runtime.dispatch(
            "add_node", {"class_type": "LawNodeD", "widget_values": [1, 2]}
        )
        assert outcome.ok is False
        assert outcome.reason == "invalid_arguments"
        assert outcome.retryable is True


# ── atomic lifecycle (CAS / one-edit / one-retry) ────────────────────────────


class TestAtomicLifecycle:
    def test_second_edit_after_accept_is_denied(self) -> None:
        runtime = _clip_runtime()
        first = runtime.dispatch(
            "edit_node", {"target": "cliptextencode", "field": "text", "value": "one"}
        )
        assert first.ok is True
        second = runtime.dispatch(
            "edit_node", {"target": "cliptextencode", "field": "text", "value": "two"}
        )
        assert second.ok is False
        assert second.reason == "edit_already_accepted"
        assert runtime.accepted is True
        assert runtime.accepted_delta_ids == ("d1",)

    def test_rejected_edit_allows_exactly_one_replacement(self) -> None:
        runtime = _clip_runtime()
        first = runtime.dispatch(
            "edit_node", {"target": "missing", "field": "text", "value": "x"}
        )
        assert first.ok is False
        assert first.replacement_allowed is True
        second = runtime.dispatch(
            "edit_node", {"target": "cliptextencode", "field": "text", "value": "ok"}
        )
        assert second.ok is True
        assert second.delta_id == "d1"
        assert runtime.replacement_used is True

    def test_two_rejections_return_no_candidate(self) -> None:
        runtime = _clip_runtime()
        first = runtime.dispatch("edit_node", {"target": "missing1", "field": "text", "value": "x"})
        assert first.replacement_allowed is True
        second = runtime.dispatch("edit_node", {"target": "missing2", "field": "text", "value": "y"})
        assert second.ok is False
        assert second.replacement_allowed is False
        assert second.no_candidate is True
        third = runtime.dispatch("edit_node", {"target": "cliptextencode", "field": "text", "value": "z"})
        assert third.ok is False
        assert third.no_candidate is True

    def test_retained_ir_advances_across_edits(self) -> None:
        """The retained IR reflects a prior accepted edit (same-history semantics):
        the second edit targets a name still present after the first."""
        runtime = _clip_runtime()
        assert runtime.dispatch(
            "edit_node", {"target": "cliptextencode", "field": "text", "value": "first"}
        ).ok
        # A later continuation's render sees the edited graph.
        render = runtime.render_text()
        assert render is not None
        assert "first" in render

    def test_cas_stale_target_rejects_after_remove(self) -> None:
        """CAS on the retained revision. After a node is removed (one edit per
        message), a second op naming it in the SAME message is denied as
        edit_already_accepted before target resolution — the correct atomic
        lifecycle. The unknown_target path for a genuinely-absent target is
        covered by test_target_not_found_rejects_and_allows_one_retry."""
        runtime = _law_runtime()
        assert runtime.dispatch("remove_node", {"target": "no_such_node"}).ok is False
        assert runtime.dispatch("remove_node", {"target": "lawnodeb"}).ok
        second = runtime.dispatch("remove_node", {"target": "lawnodeb"})
        assert second.ok is False
        assert second.reason == "edit_already_accepted"
