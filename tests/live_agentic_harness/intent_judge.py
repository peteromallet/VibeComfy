"""LLM intent judge for live agentic harness artifacts.

Provides a DeepSeek-backed text judge that scores a candidate workflow edit
against the scenario's natural-language intent.  The judge is intentionally
separate from the deterministic assessor so it can be enabled/disabled without
changing the core pass/fail logic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.provider import run_model_turn

_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "text_judge.prompt.md"
_REFUSAL_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "refusal_judge.prompt.md"
_SEMANTIC_PROMPT_PATH = (
    Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "semantic_answer_judge.prompt.md"
)

# ── Law 4 (batch 12): stage/judge lens symmetry ──────────────────────────────
#
# The judge grades against the SAME facts the reply stage saw — the composable
# renderer's output, not a separate raw-graph dump.  The reply's lens set is
# the ceiling (surface + diff + topology); the judge requests a STRICT SUBSET
# of it and the render boundary ENFORCES the subset via ``ceiling=`` (any lens
# outside the reply set raises :class:`LensSubsetViolation`).

_REPLY_LENS_SET: tuple[str, ...] = ("surface", "diff", "topology")
_JUDGE_LENS_SUBSET: tuple[str, ...] = ("diff", "topology")


def _load_prompt() -> str:
    if _PROMPT_PATH.is_file():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback rubric if the canonical prompt is missing.
    return (
        "You are a precise evaluator for ComfyUI workflow edits. Given a natural-language\n"
        "intent, the accepted Δ (the batch statements and delta ops that actually landed),\n"
        "and a structural diff between a pre-edit and post-edit workflow IR, you\n"
        "must determine whether the edit correctly implements the intent.\n\n"
        "The accepted Δ is the canonical change: grade the Δ directly and verify it is\n"
        "what actually changed between pre_ir and post_ir. Claims outside the Δ are invalid.\n\n"
        "Evaluate the edit against exactly four binary criteria:\n"
        "- correct_node_targeted\n"
        "- correct_parameter_changed\n"
        "- value_semantically_matches_intent\n"
        "- no_orphaned_wiring\n\n"
        "Respond with a JSON object and nothing else:\n"
        '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
        '"correct_parameter_changed": true | false, "value_semantically_matches_intent": true | false, '
        '"no_orphaned_wiring": true | false}, "rationale": "<one or two sentences>"}\n'
        "`pass_` must be true if and only if all four criteria are true."
    )


def _load_semantic_prompt() -> str:
    if _SEMANTIC_PROMPT_PATH.is_file():
        return _SEMANTIC_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "You are a precise evaluator for ComfyUI workflow answers. Evaluate the\n"
        "answer against exactly three binary criteria: grounded, relevant, correct.\n"
        "Judge only against structured workflow/schema/UI evidence, never against\n"
        "the answer's own wording. Respond with JSON and nothing else:\n"
        '{"pass_": true | false, "criteria": {"grounded": true | false, '
        '"relevant": true | false, "correct": true | false}, '
        '"rationale": "<one or two sentences>"}\n'
        "`pass_` must be true if and only if all three criteria are true."
    )


def _load_refusal_prompt() -> str:
    if _REFUSAL_PROMPT_PATH.is_file():
        return _REFUSAL_PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback rubric if the canonical prompt is missing.
    return (
        "You are a precise evaluator for ComfyUI workflow edits. A model was asked\n"
        "to perform an edit but refused and left the workflow graph unchanged, citing\n"
        "a reason. You must determine whether that refusal is GROUNDED (the model\n"
        "could not honestly satisfy the intent) or fabricated/unsupported (the model\n"
        "dodged an edit it could have made).\n\n"
        "Evaluate the refusal against exactly four binary criteria:\n"
        "- supported_blocker: the refusal cites a real, supported blocker (for\n"
        "  example, a node class genuinely absent from the installed schema, or a\n"
        "  genuine ambiguity in the request) rather than a made-up constraint.\n"
        "- no_representable_edit: no representable edit to the given workflow could\n"
        "  satisfy the intent, so refusing was the only honest option.\n"
        "- specific_next_action: the refusal states a concrete next action that\n"
        "  would unblock the edit (for example, installing a named custom node, or\n"
        "  answering a named clarifying question).\n"
        "- no_fabricated_inability: the refusal does not falsely claim an inability\n"
        "  (for example, claiming a node is unavailable when the schema contains it,\n"
        "  or claiming the request is ambiguous when it is concrete).\n\n"
        "Respond with a JSON object and nothing else:\n"
        '{"pass_": true | false, "criteria": {"supported_blocker": true | false, '
        '"no_representable_edit": true | false, "specific_next_action": true | false, '
        '"no_fabricated_inability": true | false}, "rationale": "<one or two sentences>"}\n'
        "`pass_` must be true if and only if all four criteria are true."
    )


def _strip_code_fences(text: str) -> str:
    """Strip markdown fences some models wrap JSON responses in."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


_EDIT_CRITERION_KEYS = (
    "correct_node_targeted",
    "correct_parameter_changed",
    "value_semantically_matches_intent",
    "no_orphaned_wiring",
)

_REFUSAL_CRITERION_KEYS = (
    "supported_blocker",
    "no_representable_edit",
    "specific_next_action",
    "no_fabricated_inability",
)

_SEMANTIC_CRITERION_KEYS = (
    "grounded",
    "relevant",
    "correct",
)


def _strict_boolean(value: Any) -> bool | None:
    """Return *value* iff it is an explicit JSON boolean (Python ``bool``).

    JSON ``true``/``false`` decode to Python ``bool``.  Anything else —
    including the strings ``"true"``/``"false"`` — is malformed and returns
    None so callers fail closed instead of coercing with ``bool()``.
    """
    if type(value) is bool:
        return value
    return None


def _derive_verdict(parsed: Any, criterion_keys: tuple[str, ...]) -> dict[str, Any]:
    """Normalize a parsed judge response, deriving ``pass_`` from the criteria.

    The model's self-declared ``pass_`` is never trusted: the verdict is True
    only when the response is a JSON object whose ``pass_`` is an explicit
    boolean and every required criterion is an explicit ``true`` boolean.  Any
    criterion that is false, missing, or not a strict boolean (including the
    strings ``"false"``/``"true"``), any non-boolean or absent ``pass_``, and
    any non-object response fail the verdict closed — malformed output is a
    fail, never a pass.  Only genuinely unparsable JSON (json.loads raising
    in the caller) stays undetermined (``pass_`` None).
    """
    if not isinstance(parsed, dict):
        return {"pass_": False, "criteria": {}, "rationale": ""}
    self_declared = _strict_boolean(parsed.get("pass_"))
    criteria_raw = parsed.get("criteria")
    criteria: dict[str, Any] = {}
    if isinstance(criteria_raw, dict):
        for key in criterion_keys:
            value = _strict_boolean(criteria_raw.get(key))
            if value is not None:
                criteria[key] = value
    all_criteria_pass = all(criteria.get(key) is True for key in criterion_keys)
    return {
        "pass_": self_declared is not None and all_criteria_pass,
        "criteria": criteria,
        "rationale": str(parsed.get("rationale", "")),
    }


def _parse_verdict(raw: str) -> dict[str, Any]:
    """Parse the judge's JSON response into a normalized dict.

    ``pass_`` is derived from the criteria (fail closed), never from the
    model's self-declared ``pass_``: it is True iff every required criterion
    is an explicit JSON boolean ``true`` and ``pass_`` itself is an explicit
    boolean.  String-typed booleans, missing criteria, false criteria, and
    contradictory self-declarations all fail closed.
    """
    parsed = json.loads(_strip_code_fences(raw))
    return _derive_verdict(parsed, _EDIT_CRITERION_KEYS)


def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
    """Parse the grounded-refusal judge's JSON response into a normalized dict.

    Same fail-closed contract as :func:`_parse_verdict`: the verdict is
    derived from the four refusal criteria (supported blocker, no
    representable edit, specific next action, no fabricated inability), not
    from the model's self-declared ``pass_``.
    """
    parsed = json.loads(_strip_code_fences(raw))
    return _derive_verdict(parsed, _REFUSAL_CRITERION_KEYS)


def _parse_semantic_verdict(raw: str) -> dict[str, Any]:
    """Parse the semantic-answer judge's JSON response into a normalized dict.

    Same fail-closed contract as :func:`_parse_verdict`: the verdict is
    derived from grounded/relevant/correct, not from the model's
    self-declared ``pass_``. Malformed parsed objects fail; only
    ``json.loads`` raising stays undetermined in the caller.
    """
    parsed = json.loads(_strip_code_fences(raw))
    return _derive_verdict(parsed, _SEMANTIC_CRITERION_KEYS)


def _load_json_mapping(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_ui_pair(
    output_dir: Path,
    response: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Load original.ui.json and final.ui.json (candidate as a final fallback)."""
    artifacts = response.get("artifacts") if isinstance(response, Mapping) else None
    original_path = output_dir / "original.ui.json"
    final_path = output_dir / "final.ui.json"
    candidate_path = output_dir / "candidate.ui.json"
    if isinstance(artifacts, Mapping):
        if isinstance(artifacts.get("original_ui"), str):
            original_path = Path(artifacts["original_ui"])
        if isinstance(artifacts.get("final_ui"), str):
            final_path = Path(artifacts["final_ui"])
        elif isinstance(artifacts.get("candidate_ui"), str):
            candidate_path = Path(artifacts["candidate_ui"])
    original = _load_json_mapping(original_path)
    final = _load_json_mapping(final_path)
    if final is None:
        final = _load_json_mapping(candidate_path)
    return original, final


def _ui_node_inventory(ui: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Structured node inventory from a UI or API-shaped graph. Not prose."""
    if not isinstance(ui, Mapping):
        return []
    inventory: list[dict[str, Any]] = []
    nodes = ui.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            inventory.append(
                {
                    "id": node.get("id"),
                    "type": node.get("type") or node.get("class_type"),
                }
            )
        return inventory
    for key, node in ui.items():
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("class_type") or node.get("type")
        if class_type is None and "inputs" not in node:
            continue
        inventory.append({"id": node.get("id", key), "type": class_type})
    return inventory


def _structured_answer_text(response: Mapping[str, Any] | None) -> str:
    """Return the agent's answer from structured envelope fields only."""
    if not isinstance(response, Mapping):
        return ""
    for key in ("reply", "message"):
        value = response.get(key)
        if isinstance(value, str):
            return value
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        for key in ("answer", "reply", "question"):
            value = outcome.get(key)
            if isinstance(value, str):
                return value
    return ""


def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "implementation_payload.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    graph = payload.get("graph")
    if not isinstance(graph, Mapping):
        return None
    compiled_api = graph.get("compiled_api")
    if not isinstance(compiled_api, Mapping):
        # Sidecar-less envelope: the execution view is derived by compiling the
        # IR (compile("api") is a function, not stored data). Only a graph the
        # decoder accepts yields context; anything else stays context-free.
        try:
            from vibecomfy.ingest.normalize import from_envelope

            compiled_api = from_envelope(dict(graph)).compile("api")
        except Exception:
            return None
    context: dict[str, Any] = {"compiled_api": compiled_api}
    metadata = graph.get("metadata")
    if isinstance(metadata, Mapping):
        widget_index = metadata.get("widget_index") or metadata.get("object_info_index")
        if isinstance(widget_index, Mapping):
            context["widget_index"] = widget_index
    return context


def _ui_nodes_by_id(ui: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    nodes = ui.get("nodes")
    if not isinstance(nodes, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = node.get("id")
        if node_id is not None:
            result[str(node_id)] = node
    return result


def _ui_links_by_id(ui: Mapping[str, Any]) -> dict[Any, Any]:
    links = ui.get("links")
    if not isinstance(links, list):
        return {}
    result: dict[Any, Any] = {}
    for link in links:
        if isinstance(link, list) and link:
            result[link[0]] = link
        elif isinstance(link, Mapping) and "id" in link:
            result[link.get("id")] = link
    return result


def _link_source(link: Any) -> dict[str, Any] | None:
    if isinstance(link, list) and len(link) >= 3:
        return {"node_id": str(link[1]), "slot": link[2]}
    if isinstance(link, Mapping):
        source_id = link.get("origin_id", link.get("source_id", link.get("from_node")))
        source_slot = link.get("origin_slot", link.get("source_slot", link.get("from_slot")))
        if source_id is not None:
            return {"node_id": str(source_id), "slot": source_slot}
    return None


def _linked_inputs_for_node(
    node: Mapping[str, Any],
    *,
    links_by_id: Mapping[Any, Any],
    nodes_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return []
    linked_inputs: list[dict[str, Any]] = []
    for index, input_item in enumerate(inputs):
        if not isinstance(input_item, Mapping):
            continue
        link_id = input_item.get("link")
        if link_id is None:
            continue
        source = _link_source(links_by_id.get(link_id))
        source_node = nodes_by_id.get(source["node_id"]) if source is not None else None
        linked_inputs.append(
            {
                "input_index": index,
                "name": input_item.get("name"),
                "type": input_item.get("type"),
                "link": link_id,
                "source": {
                    **(source or {}),
                    "class_type": source_node.get("type") if isinstance(source_node, Mapping) else None,
                },
            }
        )
    return linked_inputs


def _static_widget_dataflow_context(
    pre_ir: Mapping[str, Any],
    post_ir: Mapping[str, Any],
) -> dict[str, Any] | None:
    pre_nodes = _ui_nodes_by_id(pre_ir)
    post_nodes = _ui_nodes_by_id(post_ir)
    pre_links = _ui_links_by_id(pre_ir)
    post_links = _ui_links_by_id(post_ir)
    widget_deltas: list[dict[str, Any]] = []
    static_removals_with_preserved_dynamic_inputs: list[dict[str, Any]] = []

    for node_id, pre_node in sorted(pre_nodes.items()):
        post_node = post_nodes.get(node_id)
        if post_node is None:
            continue
        pre_widgets = pre_node.get("widgets_values")
        post_widgets = post_node.get("widgets_values")
        if not isinstance(pre_widgets, list) or not isinstance(post_widgets, list):
            continue
        linked_inputs_pre = _linked_inputs_for_node(
            pre_node,
            links_by_id=pre_links,
            nodes_by_id=pre_nodes,
        )
        linked_inputs_post = _linked_inputs_for_node(
            post_node,
            links_by_id=post_links,
            nodes_by_id=post_nodes,
        )
        linked_signature_pre = {
            (item.get("name"), item.get("link"), item.get("source", {}).get("node_id"))
            for item in linked_inputs_pre
        }
        linked_signature_post = {
            (item.get("name"), item.get("link"), item.get("source", {}).get("node_id"))
            for item in linked_inputs_post
        }
        preserved_dynamic_inputs = bool(linked_signature_pre & linked_signature_post)
        for index in range(max(len(pre_widgets), len(post_widgets))):
            old = pre_widgets[index] if index < len(pre_widgets) else None
            new = post_widgets[index] if index < len(post_widgets) else None
            if old == new:
                continue
            delta = {
                "node_id": node_id,
                "class_type": post_node.get("type") or pre_node.get("type"),
                "widget_index": index,
                "old": old,
                "new": new,
                "kind": "static_widget_delta",
                "linked_inputs_pre": linked_inputs_pre,
                "linked_inputs_post": linked_inputs_post,
                "preserved_dynamic_inputs": preserved_dynamic_inputs,
            }
            widget_deltas.append(delta)
            if isinstance(old, str) and old.strip() and (new is None or (isinstance(new, str) and not new.strip())):
                if preserved_dynamic_inputs:
                    static_removals_with_preserved_dynamic_inputs.append(delta)

    if not widget_deltas:
        return None
    return {
        "widget_deltas": widget_deltas,
        "static_widget_removals_with_preserved_dynamic_inputs": static_removals_with_preserved_dynamic_inputs,
        "note": (
            "widgets_values are static node configuration. Linked inputs are dynamic dataflow. "
            "A static text widget removal can be correct when linked dynamic inputs remain connected."
        ),
    }


def _load_accepted_batch(
    response: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return the accepted Δ from a run response: ``(accepted_batch, delta_envelope)``.

    ``accepted_batch`` is the durable response's accepted Δ — the batch
    statements that succeeded (``ok`` and ``landed`` both true) that the
    reply claims.  Each accepted edit statement carries its landed ``op``
    (the typed op the grammar yielded), so the statements alone are the
    canonical Δ (Law 3); no parallel envelope is required.  ``delta_envelope``
    is derived from those ops (``{"ops": [...]}``), with the legacy
    ``delta_ops_envelope`` / ``delta_ops`` views accepted as a fallback for
    older durable artifacts.  Prose is never used.
    """
    if not isinstance(response, Mapping):
        return [], None
    accepted: list[dict[str, Any]] = []
    for turn in response.get("batch_turns") or []:
        if not isinstance(turn, Mapping):
            continue
        envelope = turn.get("delta_ops_envelope")
        turn_ops = envelope.get("ops") if isinstance(envelope, Mapping) else None
        if not isinstance(turn_ops, list):
            flat_ops = turn.get("delta_ops")
            turn_ops = flat_ops if isinstance(flat_ops, list) else ()
        landed_op_iter = iter(
            op for op in turn_ops if isinstance(op, Mapping)
        )
        for statement in turn.get("statements") or []:
            if not isinstance(statement, Mapping):
                continue
            if statement.get("ok") is True and statement.get("landed") is True:
                entry: dict[str, Any] = {
                    "statement_index": statement.get("statement_index"),
                    "source": statement.get("source"),
                    "op_kind": statement.get("op_kind"),
                    "touched_uids": list(statement.get("touched_uids") or ()),
                }
                op = statement.get("op")
                if not isinstance(op, Mapping):
                    op = next(landed_op_iter, None)
                if isinstance(op, Mapping):
                    entry["op"] = op
                accepted.append(entry)
    # The durable top-level accepted_batch (when present) is the single
    # source of truth; batch_turns reconstruction is a fallback for older
    # artifacts.
    durable_batch = response.get("accepted_batch")
    if isinstance(durable_batch, list) and durable_batch:
        accepted = [dict(item) for item in durable_batch if isinstance(item, Mapping)]
    ops = [item["op"] for item in accepted if isinstance(item.get("op"), Mapping)]
    if ops:
        return accepted, {"ops": list(ops)}
    envelope = response.get("delta_ops_envelope")
    if isinstance(envelope, Mapping):
        return accepted, dict(envelope)
    delta_ops = response.get("delta_ops")
    if isinstance(delta_ops, list):
        return accepted, {"ops": list(delta_ops)}
    return accepted, None


def _ui_node_value_fields(node: Mapping[str, Any], *, schema_provider: Any = None) -> dict[str, Any]:
    """Field/value view of a UI node via the EditableSurface (batch 6).

    The surface hydrates the INSTANCE — named ``inputs``, named ``widgets[]``
    AND positional ``widgets_values`` (resolved against the class schema) —
    so typical LiteGraph nodes with positional widget vectors resolve to
    their schema field names instead of failing closed.
    """
    try:
        from vibecomfy.porting.edit.editable_surface import editable_surface_for

        surface = editable_surface_for(node, schema_provider=schema_provider)
        return {
            str(field.name): field.value
            for field in surface.literals
            if field.name
        }
    except Exception:
        return {}


def _to_workflow_ir(ir: Mapping[str, Any], *, schema_provider: Any = None) -> Any:
    """Convert a durable graph view (UI or rich envelope) to a VibeWorkflow IR."""
    from vibecomfy.ingest.normalize import from_envelope, from_ui

    if isinstance(ir.get("nodes"), dict) or "vibecomfy_format_version" in ir:
        return from_envelope(dict(ir))
    return from_ui(
        dict(ir),
        schema_provider=schema_provider,
        use_comfy_converter=False,
    )


def _verify_delta_replay(
    pre_ir: Mapping[str, Any],
    post_ir: Mapping[str, Any],
    delta_ops: Any,
    *,
    schema_provider: Any = None,
) -> dict[str, Any]:
    """Verify the canonical Δ replayable-constructs post from pre (Law 3).

    The judge grades the accepted Δ directly: ``interpret(pre, Δ)`` must
    apply cleanly and reproduce post (``diff(interpret(pre, Δ), post) == ()``),
    and the Δ must equal the canonical diff of the IR pair — i.e. the Δ is
    what actually changed.  When the IR pair cannot be lifted to a
    VibeWorkflow, ``verified`` is None and the LLM judges (with the
    EditableSurface-resolved field values as context).  Returns
    ``{"verified": bool | None, "checked": int, "mismatches": [...]}``.
    """
    if not isinstance(delta_ops, (list, tuple)) or not delta_ops:
        return {"verified": None, "checked": 0, "mismatches": []}
    from vibecomfy.porting.edit._diff import diff
    from vibecomfy.porting.edit._interpret import interpret
    from vibecomfy.porting.edit.ops import parse_edit_delta

    try:
        pre_wf = _to_workflow_ir(pre_ir, schema_provider=schema_provider)
        post_wf = _to_workflow_ir(post_ir, schema_provider=schema_provider)
        ops = parse_edit_delta(list(delta_ops))
    except Exception as exc:
        return {
            "verified": None,
            "checked": 0,
            "mismatches": [],
            "error": f"could not lift IR for replay: {exc}",
        }
    if not ops:
        return {"verified": None, "checked": 0, "mismatches": []}
    mismatches: list[str] = []
    try:
        result = interpret(pre_wf, ops, schema_provider=schema_provider)
    except Exception as exc:
        return {
            "verified": False,
            "checked": len(ops),
            "mismatches": [f"interpret(pre, Δ) raised: {exc}"],
        }
    if not result.ok:
        codes = [diag.code for diag in result.diagnostics]
        mismatches.append(
            "interpret(pre, Δ) failed to apply: " + ", ".join(codes[:4] or ["apply_failed"])
        )
    else:
        leftover = diff(result.workflow, post_wf)
        if leftover:
            mismatches.append(
                f"interpret(pre, Δ) does not reconstruct post: "
                f"{len(leftover)} leftover op(s) in diff(interpret(pre, Δ), post)"
            )
    try:
        expected = diff(pre_wf, post_wf)
        _actual = {_op_fingerprint(op) for op in expected}
        _claimed = {_op_fingerprint(op) for op in ops}
        if _claimed - _actual:
            mismatches.append(
                "Δ claims changes that are not what actually changed between pre_ir and post_ir"
            )
    except Exception:
        pass
    if not mismatches:
        return {"verified": True, "checked": len(ops), "mismatches": []}
    return {
        "verified": False,
        "checked": len(ops),
        "mismatches": mismatches[:8],
    }


def _op_fingerprint(op: Any) -> tuple[Any, ...]:
    """Stable comparable fingerprint of an edit op (dict or typed)."""
    if isinstance(op, Mapping):
        return (op.get("op"), json.dumps(op, sort_keys=True, default=str))
    try:
        from vibecomfy.porting.edit.ops import op_to_dict

        payload = op_to_dict(op)
    except Exception:
        return (getattr(op, "op", type(op).__name__), str(op))
    return (payload.get("op"), json.dumps(payload, sort_keys=True, default=str))


def _nodes_by_uid(ir: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    nodes = ir.get("nodes")
    result: dict[str, Mapping[str, Any]] = {}
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            uid = node.get("properties", {}).get("vibecomfy_uid") if isinstance(node.get("properties"), Mapping) else None
            if uid is None:
                uid = node.get("id")
            if uid is not None:
                result[str(uid)] = node
        return result
    for key, node in ir.items():
        if isinstance(node, Mapping) and node.get("class_type") is not None:
            result[str(node.get("uid") or key)] = node
    return result


def _verify_delta_replay_legacy_removed() -> None:  # pragma: no cover
    """Removed: the homemade UI-widget walker on V2 apply-envelope ops.

    Batch 10 fix: the judge verifies the accepted Δ via
    ``interpret(pre, Δ)`` / ``diff`` (Law 3) — see :func:`_verify_delta_replay`.
    """


def _render_judge_lens_payload(
    pre_ir: Mapping[str, Any],
    post_ir: Mapping[str, Any],
    delta_ops: Any,
) -> dict[str, Any]:
    """Render pre/post through the composable renderer under the judge lens.

    Law 4 (batch 12): the judge grades against the SAME facts the reply
    stage saw — the renderer's lens output, not a separate raw-graph dump.
    The judge's lens set is a strict subset of the reply's
    (``surface`` + ``diff`` + ``topology``) and the render boundary ENFORCES
    the subset via ``ceiling=``: a judge lens outside the reply set raises
    :class:`LensSubsetViolation` (the reply's lens set is the ceiling).
    ``delta_ops`` (the accepted Δ) feeds the ``diff`` lens so the judge's
    view of what changed is identical to the reply's.  A graph that cannot
    be lifted through the ingest door renders ``None`` (the raw pre/post IR
    remain in the payload); a subset violation always propagates.
    """
    from vibecomfy.porting.render import LensSubsetViolation, render_text

    def _render(ir: Mapping[str, Any]) -> str | None:
        try:
            return render_text(
                dict(ir),
                lenses=_JUDGE_LENS_SUBSET,
                delta=delta_ops,
                ceiling=_REPLY_LENS_SET,
            )
        except LensSubsetViolation:
            raise
        except Exception:
            return None

    return {
        "reply_lens_set": list(_REPLY_LENS_SET),
        "judge_lens_subset": list(_JUDGE_LENS_SUBSET),
        "pre": _render(pre_ir),
        "post": _render(post_ir),
    }


def judge_edit_intent(
    output_dir: Path | str,
    scenario: Mapping[str, Any],
    *,
    route: str = "deepseek",
    model: str = "deepseek-v4-pro",
) -> dict[str, Any]:
    """Run the DeepSeek text judge on the candidate edit in *output_dir*.

    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
    If required artifacts are missing or the model call fails, ``pass_`` is None
    and ``error`` describes why.
    """
    output_dir = Path(output_dir)
    query = str(scenario.get("query", "")).strip()
    if not query:
        return {"pass_": None, "error": "scenario has no query"}

    # The durable turn writes UI artifacts under out/editor_sessions; the response
    # JSON carries the exact paths in its artifacts block.
    response_path = output_dir / "response.json"
    original_ui_path: Path | None = None
    candidate_ui_path: Path | None = None
    response: Mapping[str, Any] | None = None
    if response_path.is_file():
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
            artifacts = response.get("artifacts", {}) or {}
            if isinstance(artifacts.get("original_ui"), str):
                original_ui_path = Path(artifacts["original_ui"])
            if isinstance(artifacts.get("candidate_ui"), str):
                candidate_ui_path = Path(artifacts["candidate_ui"])
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback to common in-directory locations if response artifacts are absent.
    if original_ui_path is None:
        original_ui_path = output_dir / "original.ui.json"
    if candidate_ui_path is None:
        candidate_ui_path = output_dir / "candidate.ui.json"
        if not candidate_ui_path.is_file():
            candidate_ui_path = output_dir / "final.ui.json"

    if not original_ui_path.is_file() or not candidate_ui_path.is_file():
        return {
            "pass_": None,
            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
        }

    try:
        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}

    accepted_batch, delta_envelope = _load_accepted_batch(response)
    delta_ops = delta_envelope.get("ops") if isinstance(delta_envelope, Mapping) else None
    from vibecomfy.schema import get_schema_provider  # late import: judge stays light

    delta_replay = _verify_delta_replay(
        pre_ir,
        post_ir,
        delta_ops,
        schema_provider=get_schema_provider("auto"),
    )
    # The Δ is what actually changed: when the deterministic replay of the
    # canonical Δ contradicts the pre/post IR, no edit satisfies the intent —
    # fail closed without a model call (the reply-must-match-diff law).
    if delta_replay.get("verified") is False:
        return {
            "pass_": False,
            "criteria": {
                "correct_node_targeted": False,
                "correct_parameter_changed": False,
                "value_semantically_matches_intent": False,
                "no_orphaned_wiring": False,
            },
            "rationale": "delta replay mismatch: " + "; ".join(delta_replay.get("mismatches") or []),
            "metadata": {"delta_replay": delta_replay},
        }
    system_prompt = _load_prompt()
    implementation_payload = _load_implementation_payload(output_dir)
    schema_context = _schema_context_from_payload(implementation_payload) or {}
    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
    if dataflow_context:
        schema_context["dataflow_context"] = dataflow_context
    if schema_context:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Schema and widget evidence\n"
            "When schema_context is provided, use it to map opaque widget_N fields "
            "to semantic input names. Treat literal widget values as static node "
            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
            "widget's meaning from index order when compiled_api names are available. "
            "If a static widget containing stale or fabricated text is removed while "
            "the relevant linked dynamic input path remains connected, do not treat "
            "that removal as deleting the dynamic dataflow."
        )
    # The judge grades the canonical Δ (the accepted batch) directly: the Δ is
    # what actually changed, so claims outside it are invalid.
    if accepted_batch or isinstance(delta_envelope, Mapping):
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Accepted Δ (the canonical change)\n"
            "The accepted_batch statements below are the ONLY changes that actually "
            "landed (the canonical Δ). Grade the edit against them directly: the Δ is "
            "what actually changed between pre_ir and post_ir, verified by "
            "interpret(pre, Δ) reconstructing post. Do not infer additional edits from "
            "the IR pair that the Δ does not claim, and do not excuse a claimed edit "
            "that the Δ does not contain."
        )
    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
    # present, it grounds the judge on what a GOOD result achieves (the outcome +
    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
    # alternative approaches that reach the same outcome count as correct.
    desired = scenario.get("desired")
    if desired:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
            "The scenario author described what a GOOD result looks like below. Use it to "
            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
            "it fully wired/complete (no dangling or broken connections, existing pipeline "
            "not broken), and is the approach a sensible one?\n\n"
            f"Desired outcome: {desired.get('outcome', '')}\n"
            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
        )
    payload: dict[str, Any] = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
    if accepted_batch:
        payload["accepted_batch"] = accepted_batch
    if isinstance(delta_envelope, Mapping):
        payload["delta"] = delta_envelope
    payload["delta_replay"] = delta_replay
    # Batch 12 (Law 4): the judge's graph window is the renderer's lens
    # output — a strict subset of the reply's lens set, enforced at the
    # render boundary (ceiling=).  The judge grades against the same facts
    # the reply model saw (symmetry), not a separate raw-graph dump.
    payload["renderer_lenses"] = _render_judge_lens_payload(
        pre_ir, post_ir, delta_ops
    )
    if desired:
        payload["desired_outcome"] = desired
    if schema_context:
        payload["schema_context"] = schema_context
    user_content = json.dumps(payload, indent=2)

    try:
        response = run_model_turn(
            "evaluate workflow edit against intent",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:  # noqa: BLE001
        return {"pass_": None, "error": f"model call failed: {exc}"}

    raw = response.get("content") or ""
    if not raw:
        return {"pass_": None, "error": "model returned empty content"}

    try:
        verdict = _parse_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "pass_": None,
            "error": f"could not parse judge response: {exc}",
            "raw": raw[:500],
        }

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
    }
    return verdict


def judge_grounded_refusal(
    output_dir: Path | str,
    scenario: Mapping[str, Any],
    *,
    route: str = "deepseek",
    model: str = "deepseek-v4-pro",
) -> dict[str, Any]:
    """Run the DeepSeek grounded-refusal judge for a desired edit scenario.

    A desired edit may pass on an allowlisted refusal label ONLY when this judge
    confirms the refusal is grounded: the cited blocker is real and supported,
    no representable edit could satisfy the intent, the refusal states a
    specific next action, and it does not fabricate an inability.

    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
    If required artifacts are missing or the model call fails, ``pass_`` is None
    and ``error`` describes why — callers MUST fail closed on that outcome.
    """
    output_dir = Path(output_dir)
    query = str(scenario.get("query", "")).strip()
    if not query:
        return {"pass_": None, "error": "scenario has no query"}

    # The refusal envelope is read from the run's response.json: outcome kind,
    # message, gates, route, evidence.  Only the structured envelope is scored;
    # prose never gates.
    response_path = output_dir / "response.json"
    refusal: dict[str, Any] = {}
    if response_path.is_file():
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            response = None
        if isinstance(response, Mapping):
            refusal = {
                "outcome": response.get("outcome"),
                "message": response.get("message"),
                "no_candidate_reason": response.get("no_candidate_reason"),
                "route": response.get("route"),
                "gates": response.get("gates"),
                "evidence": response.get("evidence"),
                "graph_unchanged": response.get("graph_unchanged"),
            }
    if not isinstance(refusal.get("outcome"), Mapping):
        return {"pass_": None, "error": "response.json is missing a refusal outcome"}

    original_ui, final_ui = _load_ui_pair(output_dir, response if isinstance(response, Mapping) else None)
    node_inventory = _ui_node_inventory(original_ui if original_ui is not None else final_ui)

    system_prompt = _load_refusal_prompt()
    implementation_payload = _load_implementation_payload(output_dir)
    schema_context = _schema_context_from_payload(implementation_payload) or {}
    if schema_context or node_inventory:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Schema and graph evidence\n"
            "When schema_context or node_inventory is provided, use it to verify "
            "whether a cited blocker is real. A 'requires_custom_nodes' refusal is "
            "fabricated if the needed node class actually exists in compiled_api "
            "or in the workflow node inventory. Do not guess from the refusal "
            "message wording when structured schema/graph evidence is available. "
            "Identical refusal prose with contradictory schema or graph evidence "
            "must fail."
        )
    desired = scenario.get("desired")
    payload: dict[str, Any] = {"nl_intent": query, "refusal": refusal}
    if desired:
        payload["desired_outcome"] = desired
    if schema_context:
        payload["schema_context"] = schema_context
    if original_ui is not None:
        payload["original_ui"] = original_ui
    if final_ui is not None:
        payload["final_ui"] = final_ui
    if node_inventory:
        payload["node_inventory"] = node_inventory
    user_content = json.dumps(payload, indent=2)

    try:
        response = run_model_turn(
            "evaluate whether a workflow-edit refusal is grounded",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:  # noqa: BLE001
        return {"pass_": None, "error": f"model call failed: {exc}"}

    raw = response.get("content") or ""
    if not raw:
        return {"pass_": None, "error": "model returned empty content"}

    try:
        verdict = _parse_refusal_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "pass_": None,
            "error": f"could not parse judge response: {exc}",
            "raw": raw[:500],
        }

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
    }
    return verdict


def judge_semantic_answer(
    output_dir: Path | str,
    scenario: Mapping[str, Any],
    *,
    route: str = "deepseek",
    model: str = "deepseek-v4-pro",
) -> dict[str, Any]:
    """Run the rubric-driven semantic-answer judge for a D13 non-edit.

    Criteria are grounded, relevant, and correct. An empty or whitespace-only
    answer fails structurally without a model call. Missing UI evidence or a
    model/parse outage returns ``pass_`` None. Malformed parsed verdicts fail.
    """
    output_dir = Path(output_dir)
    rubric = scenario.get("answer_rubric")
    if not isinstance(rubric, Mapping):
        return {"pass_": None, "error": "scenario has no answer_rubric"}

    query = str(scenario.get("query", "")).strip()
    if not query:
        return {"pass_": None, "error": "scenario has no query"}

    response_path = output_dir / "response.json"
    response = _load_json_mapping(response_path)
    answer = _structured_answer_text(response)
    if not answer.strip():
        return {
            "pass_": False,
            "criteria": {"grounded": False, "relevant": False, "correct": False},
            "rationale": "empty or whitespace-only answer",
        }

    original_ui, final_ui = _load_ui_pair(output_dir, response)
    if original_ui is None or final_ui is None:
        return {
            "pass_": None,
            "error": "missing UI artifacts: original.ui.json / final.ui.json",
        }

    node_inventory = _ui_node_inventory(original_ui)
    required_nodes = rubric.get("required_node_evidence")
    if not isinstance(required_nodes, list):
        required_nodes = []

    system_prompt = _load_semantic_prompt()
    implementation_payload = _load_implementation_payload(output_dir)
    schema_context = _schema_context_from_payload(implementation_payload) or {}
    payload: dict[str, Any] = {
        "nl_intent": query,
        "answer": answer,
        "original_ui": original_ui,
        "final_ui": final_ui,
        "node_inventory": node_inventory,
        "required_node_evidence": required_nodes,
        "expected_criteria": rubric.get("expected_criteria") or [],
        "fail_conditions": rubric.get("fail_conditions") or [],
        "pass_condition": rubric.get("pass_condition") or "",
    }
    if schema_context:
        payload["schema_context"] = schema_context
    user_content = json.dumps(payload, indent=2)

    try:
        model_response = run_model_turn(
            "evaluate whether a workflow answer is grounded, relevant, and correct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:  # noqa: BLE001
        return {"pass_": None, "error": f"model call failed: {exc}"}

    raw = model_response.get("content") or ""
    if not raw:
        return {"pass_": None, "error": "model returned empty content"}

    try:
        verdict = _parse_semantic_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "pass_": None,
            "error": f"could not parse judge response: {exc}",
            "raw": raw[:500],
        }

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": model_response.get("_profiling", {}).get("elapsed_ms"),
    }
    return verdict
