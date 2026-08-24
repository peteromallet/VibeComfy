"""LLM intent judge for live agentic harness artifacts.

Provides a DeepSeek-backed text judge that scores a candidate workflow edit
against the scenario's natural-language intent.  The judge is intentionally
separate from the deterministic assessor so it can be enabled/disabled without
changing the core pass/fail logic.
"""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.provider import run_model_turn
from vibecomfy.porting.edit.constants import MODE_LABELS

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


def _derive_verdict(
    parsed: Any,
    criterion_keys: tuple[str, ...],
    *,
    missing_policy: str = "fail",
) -> dict[str, Any]:
    """Normalize a parsed judge response, deriving ``pass_`` from the criteria.

    The model's self-declared ``pass_`` is never trusted: the verdict is True
    only when the response is a JSON object whose ``pass_`` is an explicit
    boolean and every required criterion is an explicit ``true`` boolean.  Any
    criterion that is false or not a strict boolean (including the strings
    ``"false"``/``"true"``), any non-boolean or absent ``pass_``, and any
    non-object response fail the verdict closed — malformed output is a fail,
    never a pass.  Only genuinely unparsable JSON (json.loads raising in the
    caller) stays undetermined (``pass_`` None).

    ``missing_policy`` selects how an ABSENT (or non-strict-typed) criterion
    is treated.  The grounded-refusal judge uses ``"undetermined"`` (v5-batch-3
    #4 359848: a refusal response that omitted ``no_fabricated_inability``
    fail-closed one criterion short of a flip):
    - ``"fail"`` (default): a missing criterion fails the verdict closed.
    - ``"undetermined"``: a missing criterion yields ``pass_`` None plus a
      ``missing_criteria`` list so the caller can retry; an explicitly
      returned ``False`` still fails.  Missing criteria never pass.
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
    missing = [key for key in criterion_keys if key not in criteria]
    # An explicit returned False is already a decisive hard failure.  Do this
    # before the missing-policy branch so a second absent/malformed criterion
    # cannot mask the failure as retryable/undetermined.
    if any(value is False for value in criteria.values()):
        return {
            "pass_": False,
            "criteria": criteria,
            "rationale": str(parsed.get("rationale", "")),
        }
    if missing_policy == "undetermined" and missing:
        return {
            "pass_": None,
            "criteria": criteria,
            "rationale": str(parsed.get("rationale", "")),
            "missing_criteria": missing,
        }
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

    The verdict is derived from the four refusal criteria (supported blocker,
    no representable edit, specific next action, no fabricated inability), not
    from the model's self-declared ``pass_``.  Unlike the edit/semantic
    judges, a MISSING criterion does not fail-closed: it returns ``pass_``
    None with ``missing_criteria`` so the caller can retry once (v5-batch-3
    #4 359848).  An explicitly returned ``False`` still fails.
    """
    parsed = json.loads(_strip_code_fences(raw))
    return _derive_verdict(parsed, _REFUSAL_CRITERION_KEYS, missing_policy="undetermined")


def _parse_single_json_object(raw: str) -> Any:
    """Parse *raw* as one JSON value, tolerating trailing data.

    Some models append a second JSON object (or trailing prose) after the
    verdict; ``json.loads`` then raises ``JSONDecodeError: Extra data``
    (v5-batch-4 #7 d1caec).  ``raw_decode`` recovers the FIRST complete value
    and ignores everything after it.  Raises ``json.JSONDecodeError`` only
    when no complete value exists (truncated output).
    """
    text = _strip_code_fences(raw)
    value, _ = json.JSONDecoder().raw_decode(text)
    return value


def _parse_semantic_verdict(raw: str) -> dict[str, Any]:
    """Parse the semantic-answer judge's JSON response into a normalized dict.

    Same fail-closed contract as :func:`_parse_verdict`: the verdict is
    derived from grounded/relevant/correct, not from the model's
    self-declared ``pass_``.  The parse tolerates trailing data after the
    first JSON object; only genuinely unparsable output stays undetermined
    in the caller (retried once there).
    """
    parsed = _parse_single_json_object(raw)
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


def _load_accepted_batch(
    response: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return the accepted Δ from a run response: ``(accepted_batch, delta_envelope)``.

    ``accepted_batch`` is the durable response's accepted Δ — the batch
    statements that succeeded (``ok`` and ``landed`` both true) that the
    reply claims.  Each accepted edit statement carries its landed ``op``
    (the typed op the grammar yielded), so the statements alone are the
    canonical Δ (Law 3); no parallel envelope is required.  ``delta_envelope``
    is derived from those ops (``{"ops": [...]}``).  ``accepted_batch`` is the
    ONE source of the Δ (batch 10) — legacy ``delta_ops_envelope`` /
    ``delta_ops`` / ``batch_turns`` views are never consulted.  Prose is
    never used.
    """
    if not isinstance(response, Mapping):
        return [], None
    accepted: list[dict[str, Any]] = []
    durable_batch = response.get("accepted_batch")
    if isinstance(durable_batch, list):
        accepted = [dict(item) for item in durable_batch if isinstance(item, Mapping)]
    ops = [item["op"] for item in accepted if isinstance(item.get("op"), Mapping)]
    if ops:
        return accepted, {"ops": list(ops)}
    narrative = response.get("narrative_context")
    if isinstance(narrative, Mapping):
        seeded = narrative.get("operations") or narrative.get("landed_operations")
        if isinstance(seeded, list):
            seeded_ops = [
                dict(item)
                for item in seeded
                if isinstance(item, Mapping) and item.get("op")
            ]
            if seeded_ops:
                return accepted, {"ops": seeded_ops, "seed": "narrative_context"}
    return accepted, None


def _resolve_durable_turn_dir(
    output_dir: Path,
    response: Mapping[str, Any] | None,
) -> Path | None:
    """Return the durable per-turn directory for this run, or ``None``.

    DEEP-AUDIT-FIX-2-REVISION-2 seam: *output_dir* when it IS the turn
    directory itself (it carries the immutable ``authority/`` namespace);
    otherwise the production paths stamped into the envelope —
    ``detail_json_path`` or ``session_path + turns/<turn_id>``.  The
    presentation resolver in ``_agentic_replay_service.py`` is deliberately
    NOT consulted: it neither validates transactions nor receipts.
    """
    from vibecomfy.comfy_nodes.agent.authority_receipts import (
        AUTHORITY_NAMESPACE,  # noqa: PLC0415
        AUTHORITY_RECEIPT_FILENAME,  # noqa: PLC0415
    )

    candidates: list[Path] = [Path(output_dir)]
    if isinstance(response, Mapping):
        detail = (
            response.get("detail_json_path")
            or response.get("detail_json_path_resolved")
        )
        if isinstance(detail, str) and detail:
            candidates.append(Path(detail).parent)
        session_path = (
            response.get("session_path")
            or response.get("session_path_resolved")
        )
        turn_id = response.get("turn_id")
        if (
            isinstance(session_path, str)
            and session_path
            and isinstance(turn_id, str)
            and turn_id
        ):
            candidates.append(Path(session_path) / "turns" / turn_id)
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if (candidate / AUTHORITY_NAMESPACE / AUTHORITY_RECEIPT_FILENAME).is_file():
            return candidate
    return None


def _path_identities_agree(
    turn_dir: Path,
    response: Mapping[str, Any] | None,
    lineage: Mapping[str, Any] | None,
) -> bool:
    """True when path-derived identities agree with response + lineage.

    The turn directory layout is ``<root>/<session_id>/turns/<turn_id>``; both
    derived components must match every carrier that claims them.  Empty
    lineage values mean "unknown at this carrier" and are tolerated; known
    values must agree exactly (lineage is an identity fence, never authority).
    """
    path_turn_id = turn_dir.name
    parents = turn_dir.parents
    path_session_id = parents[1].name if len(parents) >= 2 else ""
    if not path_turn_id or not path_session_id:
        return False
    if isinstance(response, Mapping):
        for key, derived in (("session_id", path_session_id), ("turn_id", path_turn_id)):
            claimed = response.get(key)
            if isinstance(claimed, str) and claimed and claimed != derived:
                return False
    if isinstance(lineage, Mapping):
        for key, derived in (("session_id", path_session_id), ("turn_id", path_turn_id)):
            claimed = lineage.get(key)
            if claimed and claimed != derived:
                return False
    return True


def _durable_plan_hash(turn_dir: Path) -> str | None:
    """Read the mint-time plan hash from the durable turn response."""
    try:
        payload = json.loads(
            (turn_dir / "response.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    candidate = payload.get("candidate")
    plan_hash = (
        candidate.get("plan_hash")
        if isinstance(candidate, Mapping)
        else None
    )
    if not isinstance(plan_hash, str) or not plan_hash:
        plan_hash = payload.get("plan_hash")
    return plan_hash if isinstance(plan_hash, str) and plan_hash else None


def _load_persisted_pair_evidence(
    turn_dir: Path,
) -> tuple[Any | None, str | None]:
    """Call the single production persisted-pair loader for *turn_dir*.

    Path-derived session/turn identities are authoritative inputs; every
    binding check runs inside
    ``_artifact_store.load_bound_candidate_replay_evidence``.
    """
    from vibecomfy.comfy_nodes.agent._artifact_store import (  # noqa: PLC0415
        load_bound_candidate_replay_evidence,
    )

    plan_hash = _durable_plan_hash(turn_dir)
    if plan_hash is None:
        return None, "missing_plan_hash"
    return load_bound_candidate_replay_evidence(
        turn_dir,
        session_id=turn_dir.parents[1].name,
        turn_id=turn_dir.name,
        plan_hash=plan_hash,
    )


def _landed_replay_verified(
    evidence: Any | None,
    *,
    assessed_post_graph: Mapping[str, Any],
    lineage: Mapping[str, Any] | None = None,
) -> bool:
    """True only when the FULL persisted-pair chain binds the assessed graph.

    DEEP-AUDIT-FIX-2-REVISION-2: contract validation alone does NOT establish
    receipt or graph binding.  *evidence* is the ``(evidence, reason)`` result
    of the single production loader
    (``_artifact_store.load_bound_candidate_replay_evidence``), which has
    already validated BOTH persisted contracts, bound the complete-canonical
    receipt digest to BOTH transaction fields, enforced the receipt's ACTUAL
    replay verdict (transaction copies cannot override), chained the candidate
    hashes, and reconciled every deterministic session/turn/plan/identity.

    On top of that chain this check binds the candidate authority to the exact
    post graph being graded: the transaction's declared projection family is
    recomputed over ``assessed_post_graph`` and must equal the persisted
    postcondition; layout authority must additionally re-match the structural
    witness postcondition digest so a layout-only comparison can never admit an
    unrelated structural change; and lineage identities must fence the pair.

    Fail-closed: any absent/malformed/unbound evidence returns False.
    """
    if evidence is None:
        return False
    transaction = getattr(evidence, "transaction", None)
    if not isinstance(transaction, Mapping):
        return False
    candidate_authority = transaction.get("candidate_authority")
    if not isinstance(candidate_authority, Mapping):
        return False
    from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (  # noqa: PLC0415
        projection_reference_v1,
    )

    family = candidate_authority.get("operation_family")
    projection = "layout_v1" if family == "layout" else "structural_v1"
    try:
        recomputed_post = projection_reference_v1(assessed_post_graph, projection)
    except Exception:  # noqa: BLE001 - unprojectable evidence stays unverified
        return False
    if candidate_authority.get("postcondition") != recomputed_post:
        return False
    if family == "layout":
        structural_witness = candidate_authority.get("structural_witness")
        try:
            recomputed_structural = projection_reference_v1(
                assessed_post_graph, "structural_v1"
            )
        except Exception:  # noqa: BLE001
            return False
        if (
            not isinstance(structural_witness, Mapping)
            or structural_witness.get("postcondition_digest")
            != recomputed_structural.get("digest")
        ):
            return False
    if isinstance(lineage, Mapping):
        for key in ("session_id", "turn_id"):
            claimed = lineage.get(key)
            bound = transaction.get(key)
            if claimed and bound and claimed != bound:
                return False
    return True


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


def _mode_labels_payload() -> dict[str, str]:
    """Structured MODE_LABELS fact for judge payloads (JSON-safe keys)."""
    return {str(mode): label for mode, label in MODE_LABELS.items()}


def _delta_field_targets(delta_ops: Any) -> list[tuple[str, str]]:
    """Return ``(uid, field_path)`` pairs from set-field ops in the canonical Δ."""
    pairs: list[tuple[str, str]] = []
    if not isinstance(delta_ops, (list, tuple)):
        return pairs
    for op in delta_ops:
        if not isinstance(op, Mapping):
            continue
        target = op.get("target")
        kind = op.get("op")
        if (
            kind in {"set_node_field", "set_field"}
            and isinstance(target, (list, tuple))
            and len(target) >= 3
            and target[1] is not None
            and target[2]
        ):
            pairs.append((str(target[1]), str(target[2])))
            continue
        uid = op.get("uid")
        field = op.get("field_path") or op.get("field")
        if uid is not None and field:
            pairs.append((str(uid), str(field)))
    return pairs


def _delta_uids(delta_ops: Any) -> list[str]:
    """Unique node uids referenced by the canonical Δ."""
    seen: list[str] = []
    for uid, _field in _delta_field_targets(delta_ops):
        if uid not in seen:
            seen.append(uid)
    if not isinstance(delta_ops, (list, tuple)):
        return seen
    for op in delta_ops:
        if not isinstance(op, Mapping):
            continue
        for key in ("target", "from", "to", "source"):
            loc = op.get(key)
            if isinstance(loc, (list, tuple)) and len(loc) >= 2 and loc[1] is not None:
                uid = str(loc[1])
                if uid not in seen:
                    seen.append(uid)
        uid = op.get("uid")
        if uid is not None and str(uid) not in seen:
            seen.append(str(uid))
    return seen


def _named_fields_for_nodes(
    ir: Mapping[str, Any],
    uids: list[str],
    *,
    schema_provider: Any,
) -> dict[str, dict[str, Any]]:
    """``{uid: {field_name: value}}`` from the executor surface for *uids*."""
    nodes = _nodes_by_uid(ir)
    named: dict[str, dict[str, Any]] = {}
    for uid in uids:
        node = nodes.get(uid)
        if node is None:
            continue
        fields = _ui_node_value_fields(node, schema_provider=schema_provider)
        if fields:
            named[uid] = fields
    return named


def _named_fields_for_delta(
    pre_ir: Mapping[str, Any],
    post_ir: Mapping[str, Any],
    delta_ops: Any,
    *,
    schema_provider: Any,
) -> dict[str, dict[str, Any]]:
    """``{uid: {field_name: value}}`` from the post surface for every Δ uid."""
    uids = _delta_uids(delta_ops)
    named = _named_fields_for_nodes(post_ir, uids, schema_provider=schema_provider)
    missing = [uid for uid in uids if uid not in named]
    if missing:
        named.update(
            _named_fields_for_nodes(pre_ir, missing, schema_provider=schema_provider)
        )
    return named


def _outcome_field_targets(response: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """``(uid, field_path)`` pairs from the executor ``outcome.changes`` record."""
    pairs: list[tuple[str, str]] = []
    if not isinstance(response, Mapping):
        return pairs
    outcome = response.get("outcome")
    if not isinstance(outcome, Mapping):
        return pairs
    changes = outcome.get("changes")
    if not isinstance(changes, list):
        return pairs
    for change in changes:
        if not isinstance(change, Mapping):
            continue
        uid = change.get("uid")
        field = change.get("field_path")
        if uid is not None and field:
            pairs.append((str(uid), str(field)))
    return pairs


def _intent_names_field(intent: str, field: str) -> bool:
    """True when *field* appears as a literal token in *intent*."""
    if not intent or not field:
        return False
    return re.search(rf"(?<![\w]){re.escape(field)}(?![\w])", intent) is not None


def _pregrade_parameter_identity(
    intent: str,
    delta_ops: Any,
    named_fields: Mapping[str, Mapping[str, Any]],
    *,
    pre_named_fields: Mapping[str, Mapping[str, Any]] | None = None,
    extra_fields: list[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Pre-grade C2 when intent ∩ Δ ∩ schema share a literal field name.

    Fires only on a literal token match of a Δ/product field against both
    the intent and the executor surface. Does not infer aliases. A
    from_ui-shifted op name (e.g. ``video_frames``) does not block a match
    when the surface on a Δ-touched uid shows the named field actually
    changed.
    """
    matched: list[str] = []
    candidates = list(_delta_field_targets(delta_ops))
    if extra_fields:
        candidates.extend(extra_fields)
    for uid, field in candidates:
        schema_fields = named_fields.get(uid) or {}
        if field not in schema_fields:
            continue
        if not _intent_names_field(intent, field):
            continue
        if field not in matched:
            matched.append(field)
    if pre_named_fields:
        for uid, post_fields in named_fields.items():
            old_fields = pre_named_fields.get(uid) or {}
            for field, new in post_fields.items():
                if field not in old_fields or old_fields[field] == new:
                    continue
                if not _intent_names_field(intent, field):
                    continue
                if field not in matched:
                    matched.append(field)
    if not matched:
        return None
    return {
        "correct_parameter_changed": True,
        "matched_fields": matched,
        "reason": "literal intent∩Δ∩schema field identity",
    }


def _apply_parameter_identity_pregrade(
    verdict: dict[str, Any],
    pregrade: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Force C2 true when the deterministic identity pre-grade fired.

    The LLM rationale cannot override the pre-grade. Remaining criteria
    still decide ``pass_``.
    """
    if not pregrade or pregrade.get("correct_parameter_changed") is not True:
        return verdict
    criteria = dict(verdict.get("criteria") or {})
    criteria["correct_parameter_changed"] = True
    verdict["criteria"] = criteria
    verdict["pass_"] = all(
        criteria.get(key) is True for key in _EDIT_CRITERION_KEYS
    )
    metadata = dict(verdict.get("metadata") or {})
    metadata["pregrade"] = dict(pregrade)
    verdict["metadata"] = metadata
    return verdict


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
        leftover = tuple(
            op
            for op in diff(result.workflow, post_wf)
            if not _spelling_equivalent_leftover(op, result.workflow)
        )
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


_CANONICAL_INT_TEXT_RE = re.compile(r"-?[0-9]+")


def _canonical_edit_value(value: Any) -> Any:
    """Hashable canonical projection whose equality mirrors the edit layer.

    The diff layer compares IR values with plain Python ``!=`` over the
    numeric tower (``1 == 1.0 == True``), while a claimed Δ arrives as JSON
    where the same widget number may be spelled ``30``, ``30.0``, or text
    ``"30"`` and node/slot identities arrive as ints or digit strings.  The
    projection collapses exactly those spellings — never more:

    - bool/int/float collapse to their exact :class:`decimal.Decimal`
      identity, so cross-spelling equality matches diff-layer equality and
      huge seeds stay exact (no float precision loss);
    - a string collapses to its number only when it IS a canonical integer
      spelling (``str(int(text)) == text``); every other string (leading
      zeros, decimal text, names) stays itself;
    - mappings drop ``None``-valued entries — the same absence-vs-default
      equality ``op_to_dict``/``dict.get`` give the diff layer;
    - lists/tuples stay order-significant; any other object projects through
      ``repr``.

    Pure function of the value: same input, same projection (deterministic).
    """
    if isinstance(value, bool):
        return ("n", Decimal(int(value)))
    if isinstance(value, (int, float)):
        return ("n", Decimal(value))
    if isinstance(value, str):
        if _CANONICAL_INT_TEXT_RE.fullmatch(value) and str(int(value)) == value:
            return ("n", Decimal(int(value)))
        return ("s", value)
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                (_canonical_edit_value(str(key)), _canonical_edit_value(item))
                for key, item in value.items()
                if item is not None
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_canonical_edit_value(item) for item in value)
    return ("o", repr(value))


def _spelling_equivalent_leftover(op: Any, workflow: Any) -> bool:
    """True when a replay-vs-post leftover op is pure value-spelling drift.

    ``diff`` compares stored IR values with Python ``!=``, so a claimed
    numeric literal that replayed through the raw apply boundary (e.g. text
    ``"8"`` where the post IR stores ``8``) shows up as a leftover
    ``set_node_field`` even though the edit layer treats the two spellings as
    the same value (window P8 shape).  Only such canonically-equal
    set_node_field leftovers may be dropped; add/remove/link ops and any
    canonically-different value stay — the check remains exactly as strict
    for genuine divergence.
    """
    from vibecomfy.porting.edit.ops import SetNodeFieldOp  # noqa: PLC0415

    if not isinstance(op, SetNodeFieldOp):
        return False
    target_uid = str(getattr(op.target, "uid", "") or "")
    field_path = str(getattr(op.target, "field_path", "") or "")
    if not target_uid or not field_path:
        return False
    for node in getattr(workflow, "nodes", {}).values():
        if str(getattr(node, "uid", "") or "") != target_uid:
            continue
        widgets = dict(getattr(node, "widgets", {}) or {})
        inputs = dict(getattr(node, "inputs", {}) or {})
        # Same channel precedence as the apply boundary: widgets first.
        if field_path in widgets:
            current = widgets[field_path]
        elif field_path in inputs:
            current = inputs[field_path]
        else:
            return False
        return _canonical_edit_value(current) == _canonical_edit_value(op.value)
    return False


def _op_fingerprint(op: Any) -> tuple[Any, ...]:
    """Stable comparable fingerprint of an edit op (dict or typed).

    Two ops fingerprint equal exactly when the edit layer treats them as
    identical statements: same op kind, same targets in their canonical
    string form, and values equal under :func:`_canonical_edit_value`.
    Genuinely different operations — wrong node, wrong field, a different
    target value beyond numeric identity, an extra or missing op — still
    fingerprint apart.
    """
    if isinstance(op, Mapping):
        payload = {key: item for key, item in op.items() if item is not None}
        return (payload.get("op"), _canonical_edit_value(payload))
    try:
        from vibecomfy.porting.edit.ops import SubgraphInterfaceOp, op_to_dict

        if isinstance(op, SubgraphInterfaceOp):
            payload = {
                "op": op.op,
                "action": op.action,
                "name": op.name,
                "inputs": [list(port) for port in op.inputs],
                "outputs": [list(port) for port in op.outputs],
            }
            if op.id is not None:
                payload["id"] = op.id
        else:
            payload = op_to_dict(op)
    except Exception:
        return (getattr(op, "op", type(op).__name__), _canonical_edit_value(str(op)))
    return (payload.get("op"), _canonical_edit_value(payload))


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
    be lifted through the ingest door renders ``None`` for that side; a
    subset violation always propagates.
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


def _run_judge_model_turn(
    task: str,
    *,
    messages: list[dict[str, str]],
    route: str,
    model: str,
) -> tuple[str | None, str | None, float | None]:
    """Run one judge model turn; return ``(raw, error, elapsed_ms)``.

    ``raw`` is the response content, or None (with ``error`` describing why)
    when the model call failed or returned empty content.  ``elapsed_ms`` is
    the call's profiling elapsed time when the provider reported one.  Judge
    runners use this for their one-retry loop on retryable outcomes (missing
    refusal criterion, unparsable semantic JSON).
    """
    try:
        response = run_model_turn(
            task,
            messages=messages,
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"model call failed: {exc}", None
    raw = response.get("content") or ""
    if not raw:
        return None, "model returned empty content", None
    profiling = response.get("_profiling")
    elapsed = profiling.get("elapsed_ms") if isinstance(profiling, Mapping) else None
    return raw, None, elapsed


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

    DEEP-AUDIT-FIX-2-REVISION-2: landed replay authority is never read off the
    response.  The durable turn directory is resolved from *output_dir* / the
    production envelope paths, the single persisted-pair loader validates and
    binds the persisted transaction + receipt, and the candidate postcondition
    projection must recompute over the exact post graph graded here before
    ``judge_graph_pair`` may see ``landed_replay_verified=True``.
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

    schema_provider = get_schema_provider("auto")

    # T5.2: when the run carries a typed artifact lineage manifest, the judge
    # takes the canonical path — every carrier passes the common constructor
    # (mixed UI/API pairs decode per side), and no edit is ever synthesized.
    # Legacy artifacts without lineage keep the historical behavior below,
    # including the RC12b product-diff seed (frozen compatibility surface).
    from .lineage_check import load_artifact_lineage  # noqa: PLC0415

    lineage_manifest, _lineage_provenance = load_artifact_lineage(output_dir, response)
    canonical_mode = lineage_manifest is not None
    if canonical_mode:
        from .semantic_assessor import canonical_semantic_view  # noqa: PLC0415

        pair_lineage = (
            lineage_manifest.get("lineage")
            if isinstance(lineage_manifest, Mapping)
            else None
        )
        try:
            pre_view = canonical_semantic_view(
                pre_ir,
                lineage=pair_lineage if isinstance(pair_lineage, Mapping) else None,
                schema_provider=schema_provider,
                use_comfy_converter=False,
            )
            post_view = canonical_semantic_view(
                post_ir,
                lineage=pair_lineage if isinstance(pair_lineage, Mapping) else None,
                schema_provider=schema_provider,
                use_comfy_converter=False,
            )
        except Exception as exc:  # noqa: BLE001 - undecodable evidence stays undetermined
            return {
                "pass_": None,
                "error": f"undetermined: carrier rejected by common constructor ({exc})",
            }
        pre_wf = pre_view.workflow
        post_wf = post_view.workflow

        # DEEP-AUDIT-FIX-2-REVISION-2: resolve the durable turn, require the
        # path-derived identities to agree with response + canonical lineage,
        # then load the persisted (transaction, receipt) pair through the one
        # production loader.  The verdict upgrade below fires only after every
        # binding — including the postcondition recomputed over THIS post_ir.
        bound_evidence: Any = None
        turn_dir = _resolve_durable_turn_dir(output_dir, response)
        if turn_dir is not None and _path_identities_agree(
            turn_dir, response, pair_lineage
        ):
            bound_evidence, _binding_reason = _load_persisted_pair_evidence(turn_dir)
        landed_verified = _landed_replay_verified(
            bound_evidence,
            assessed_post_graph=post_ir,
            lineage=pair_lineage if isinstance(pair_lineage, Mapping) else None,
        )
    else:
        # Legacy artifacts without typed lineage (non-canonical mode).
        try:
            pre_wf = _to_workflow_ir(pre_ir, schema_provider=schema_provider)
            post_wf = _to_workflow_ir(post_ir, schema_provider=schema_provider)
        except Exception as exc:
            return {"pass_": None, "error": f"failed to canonicalize UI through ingest: {exc}"}

    queue_gate_failed = False
    if isinstance(response, Mapping):
        gates = response.get("gates")
        queue_gate_failed = isinstance(gates, Mapping) and gates.get("queue_validate_ok") is False

    if not delta_ops or queue_gate_failed:
        if canonical_mode:
            from .semantic_assessor import judge_graph_pair, load_accepted_batch_ops  # noqa: PLC0415

            accepted_ops, gate_failed = load_accepted_batch_ops(response)
            if gate_failed:
                return {
                    "pass_": None,
                    "error": "undetermined: withheld_accepted_batch (queue_validate_ok=false)",
                    "metadata": {"verdict": "withheld_accepted_batch"},
                }
            pair_verdict = judge_graph_pair(
                pre_view,
                post_view,
                accepted_ops,
                schema_provider=schema_provider,
                landed_replay_verified=landed_verified,
            )
            if pair_verdict.outcome == "no_edit":
                return {
                    "pass_": False,
                    "criteria": {
                        "correct_node_targeted": False,
                        "correct_parameter_changed": False,
                        "value_semantically_matches_intent": False,
                        "no_orphaned_wiring": False,
                    },
                    "rationale": (
                        "no accepted delta/candidate and the product is "
                        "unchanged; no edit exists to satisfy the intent"
                    ),
                    "metadata": {"verdict": "no_edit", **pair_verdict.detail},
                }
            if pair_verdict.outcome == "undetermined":
                return {
                    "pass_": None,
                    "error": f"undetermined: {pair_verdict.reason}",
                    "metadata": {"verdict_detail": dict(pair_verdict.detail)},
                }
            if pair_verdict.outcome == "applied_unverified":
                # §28 fix 3: landed + replay-verified edit without an accepted
                # Δ envelope.  Still not a pass (no re-derivable delta), but the
                # typed class replaces the bare
                # changed_product_without_accepted_delta undetermined.
                return {
                    "pass_": None,
                    "error": (
                        "undetermined: applied_unverified "
                        f"({pair_verdict.reason})"
                    ),
                    "metadata": {
                        "verdict": "applied_unverified",
                        "verdict_detail": dict(pair_verdict.detail),
                    },
                }
            if pair_verdict.outcome == "delta_replay_mismatch":
                return {
                    "pass_": False,
                    "criteria": {
                        "correct_node_targeted": False,
                        "correct_parameter_changed": False,
                        "value_semantically_matches_intent": False,
                        "no_orphaned_wiring": False,
                    },
                    "rationale": f"delta replay mismatch: {pair_verdict.reason}",
                    "metadata": {"verdict_detail": dict(pair_verdict.detail)},
                }
            # applied_edit: grade against the authoritative accepted batch only.
            delta_ops = [dict(op) for op in accepted_ops]
            delta_envelope = {"ops": list(delta_ops), "seed": "accepted_batch"}
        else:
            # The legacy product-diff seed was removed in B4-REVISION
            # (G5-B4-MUST-004): lineage-less fixtures carry no durable edit
            # authority, so a Δ may never be synthesized from
            # diff(pre_wf, post_wf) — C11 forbids grading a
            # fabricated edit. A withheld accepted_batch (queue_validate_ok
            # false) is contradictory authority evidence and yields
            # ``undetermined``, never a pass.
            if queue_gate_failed:
                return {
                    "pass_": None,
                    "error": (
                        "undetermined: withheld_accepted_batch "
                        "(queue_validate_ok=false)"
                    ),
                    "metadata": {"verdict": "withheld_accepted_batch"},
                }

    from vibecomfy.porting.edit.apply_gate import verify_apply
    from vibecomfy.porting.edit.ops import parse_edit_delta

    try:
        landed = parse_edit_delta(list(delta_ops or []))
    except Exception:
        landed = ()
    apply_gate = verify_apply(
        pre_wf,
        post_wf,
        landed_ops=landed,
        schema_provider=schema_provider,
    )
    if apply_gate.reason == "new_self_loop":
        return {
            "pass_": False,
            "criteria": {
                "correct_node_targeted": False,
                "correct_parameter_changed": False,
                "value_semantically_matches_intent": False,
                "no_orphaned_wiring": False,
            },
            "rationale": "canonical product has a new self-loop; apply-gate refused.",
            "metadata": {"apply_gate": apply_gate.reason},
        }

    delta_replay = _verify_delta_replay(
        pre_ir,
        post_ir,
        delta_ops,
        schema_provider=schema_provider,
    )
    if queue_gate_failed:
        delta_replay = {
            **delta_replay,
            "queue_gate_issue": "queue_validate_ok=false; grading canonical product",
        }
        if delta_replay.get("verified") is False:
            # RC12b: leftover replay of a withheld/stale batch is not a
            # corrupt product. Grade the canonical product; keep the gate
            # as a separate issue.
            delta_replay = {
                **delta_replay,
                "verified": None,
                "withheld_accepted_batch": True,
            }
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
    outcome_fields = _outcome_field_targets(response)
    named_fields = _named_fields_for_delta(
        pre_ir,
        post_ir,
        delta_ops,
        schema_provider=schema_provider,
    )
    extra_uids = [uid for uid, _field in outcome_fields if uid not in named_fields]
    if extra_uids:
        named_fields.update(
            _named_fields_for_nodes(
                post_ir, extra_uids, schema_provider=schema_provider
            )
        )
    pre_named_fields = _named_fields_for_nodes(
        pre_ir,
        list(named_fields),
        schema_provider=schema_provider,
    )
    pregrade = _pregrade_parameter_identity(
        query,
        delta_ops,
        named_fields,
        pre_named_fields=pre_named_fields,
        extra_fields=outcome_fields,
    )
    system_prompt = _load_prompt()
    implementation_payload = _load_implementation_payload(output_dir)
    schema_context = _schema_context_from_payload(implementation_payload) or {}
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
    if pregrade:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Deterministic field-identity pre-grade\n"
            "correct_parameter_changed is already true: the canonical Δ field "
            "name is a literal match against the intent and the executor schema "
            f"({', '.join(pregrade.get('matched_fields') or ())}). Do not fail "
            "that criterion on a field rename. Judge only remaining criteria "
            "(value meaning, wiring, node targeting)."
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
    # Batch 12 (Law 4): the judge's payload is the renderer's lens subset
    # (same facts as the reply) + the accepted Δ.  No raw pre_ir/post_ir
    # dump and no judge-only raw-UI walker: the lens subset is enforced at
    # the render boundary (ceiling=) and the Δ is the canonical
    # accepted_batch only.
    payload: dict[str, Any] = {"nl_intent": query}
    if accepted_batch:
        payload["accepted_batch"] = accepted_batch
    if isinstance(delta_envelope, Mapping):
        payload["delta"] = delta_envelope
    payload["delta_replay"] = delta_replay
    payload["renderer_lenses"] = _render_judge_lens_payload(
        pre_ir, post_ir, delta_ops
    )
    if desired:
        payload["desired_outcome"] = desired
    if schema_context:
        payload["schema_context"] = schema_context
    payload["mode_labels"] = _mode_labels_payload()
    if named_fields:
        payload["named_fields"] = named_fields
    if pregrade:
        payload["pregrade"] = pregrade
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
    return _apply_parameter_identity_pregrade(verdict, pregrade)


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
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    def _call() -> tuple[str | None, str | None, float | None]:
        return _run_judge_model_turn(
            "evaluate whether a workflow-edit refusal is grounded",
            messages=messages,
            route=route,
            model=model,
        )

    raw, error, elapsed_ms = _call()
    if error:
        return {"pass_": None, "error": error}

    try:
        verdict = _parse_refusal_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "pass_": None,
            "error": f"could not parse judge response: {exc}",
            "raw": raw[:500],
        }

    # v5-batch-3 #4 (359848): the refusal response omitted a criterion
    # (no_fabricated_inability) and _derive_verdict fail-closed to pass_=False,
    # one criterion short of an accepted grounded refusal.  A MISSING
    # criterion is retried once — it must never silently fail the verdict;
    # only an explicitly returned False (or a complete response) decides.
    if verdict["pass_"] is None and verdict.get("missing_criteria"):
        raw, error, retry_elapsed = _call()
        if error:
            return {"pass_": None, "error": error}
        elapsed_ms = retry_elapsed
        try:
            verdict = _parse_refusal_verdict(raw)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return {
                "pass_": None,
                "error": f"could not parse judge response on retry: {exc}",
                "raw": raw[:500],
            }
        if verdict.get("missing_criteria"):
            verdict["error"] = (
                "refusal criteria incomplete after retry: missing "
                + ", ".join(sorted(verdict["missing_criteria"]))
            )

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": elapsed_ms,
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
    payload["mode_labels"] = _mode_labels_payload()
    user_content = json.dumps(payload, indent=2)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    def _call() -> tuple[str | None, str | None, float | None]:
        return _run_judge_model_turn(
            "evaluate whether a workflow answer is grounded, relevant, and correct",
            messages=messages,
            route=route,
            model=model,
        )

    raw, error, elapsed_ms = _call()
    if error:
        return {"pass_": None, "error": error}

    try:
        verdict = _parse_semantic_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        # v5-batch-4 #7 (d1caec): the semantic judge emitted a second JSON
        # object ('Extra data: line 10 column 1') and the scenario went
        # undetermined on a parse alone.  The tolerant first-object parse
        # already ran; output that still will not parse is retried once —
        # never hard-fail the scenario on a judge parse.
        raw, error, retry_elapsed = _call()
        if error:
            return {"pass_": None, "error": error}
        elapsed_ms = retry_elapsed
        try:
            verdict = _parse_semantic_verdict(raw)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return {
                "pass_": None,
                "error": f"could not parse judge response after retry: {exc}",
                "raw": raw[:500],
            }

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": elapsed_ms,
    }
    return verdict
