"""Deep assessment of live agentic run artifacts.

The live agentic harness already verifies flow metadata (real dispatcher,
agentic model behavior, status == success).  This module inspects the actual
run artifacts to catch failures that metadata alone cannot:

* response.ok == false or response.error set
* readiness blockers
* graph unchanged when an edit was expected
* hard diagnostics (severity == error) from agent-edit turns
* upstream dependency failures such as Hivemind HTTP 500
* implementation_result.ok == false
* validation gates that failed for an apply/edit route
* (when enabled) assessment-first research rules: question-before-search,
  query relevance, required-Hivemind invocation, citation resolution to
  returned evidence IDs, no-local-search research path, and evidence-pack
  capture
* (when enabled) an LLM intent judge that scores the edit against the query

The deterministic checks run first. Judges run afterward: grounded-refusal
for allowlisted no-edit candidates, edit-intent for expected graph changes,
and a rubric-driven semantic-answer judge for D13 non-edits. Outages are
undetermined; only ``pass`` satisfies a scenario.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.executor.graph_facts import GraphFieldTarget, compare_effective_field

from .intent_judge import (
    judge_edit_intent,
    judge_grounded_refusal,
    judge_semantic_answer,
)
from .research_assessment import assess_research_evidence
from .lineage_check import assess_artifact_lineage
from .scenario_obligations import (
    descriptor_is_bare_untyped_non_edit,
    expected_no_candidate_contract,
    scenario_expects_graph_changed,
)


_ERROR_SEVERITIES = {"error", "fatal"}

# Response artifacts are untrusted model output. Keep parsing, validation, and
# snapshot construction bounded before any recursive helper can see them.
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_RESPONSE_DEPTH = 256
_MAX_COLLECTION_ITEMS = 10_000
_MAX_STRING_LENGTH = 1_000_000
_MAX_AGGREGATE_VALUES = 100_000
_MAX_OUTCOME_WARNINGS = 256

# Critical upstream failures that should always fail a live run.
_UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Hivemind HTTP error.*500", re.IGNORECASE),
    re.compile(r"HTTP Error 500", re.IGNORECASE),
    re.compile(r"Internal Server Error", re.IGNORECASE),
]

# Soft capacity warnings: surfaced so humans see them, but not treated as hard
# failures on their own (the run may still succeed via fallback evidence).
_SOFT_WARNING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"HTTP Error 429", re.IGNORECASE),
    re.compile(r"Too Many Requests", re.IGNORECASE),
]

# Canonical public route vocabulary (mirrors vibecomfy.executor.contracts).
# Edit routes may land graph changes; non-edit routes never do.  Exemption
# from the landed-count guard is decided from the envelope's canonical route,
# never from the agent's self-declared outcome/reason labels.
_EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise"})
_NON_EDIT_ROUTES = frozenset(
    {
        "clarify",
        "respond",
        "inspect",
        "research",
        "requires_custom_nodes",
    }
)


#: Frozen authoritative object_info cache root (class → pack-cache index).
_OBJECT_INFO_ROOT = (
    Path(__file__).resolve().parents[2]
    / "vibecomfy"
    / "porting"
    / "cache"
    / "object_info"
)


class AssessmentPublicationError(OSError):
    """Raised when a completed assessment cannot replace its canonical artifact."""


class AssessmentArtifactError(RuntimeError):
    """Raised when an ancillary assessment artifact cannot be inspected."""


class _FrozenDict(dict):
    """JSON-compatible dict whose content cannot be mutated."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("response snapshot is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


class _FrozenList(list):
    """JSON-compatible list whose content cannot be mutated."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("response snapshot is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


def _freeze_json(value: Any) -> Any:
    """Recursively freeze JSON containers while retaining dict/list compatibility."""
    if isinstance(value, dict):
        return _FrozenDict({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze_json(item) for item in value)
    return value


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


_RESPONSE_OUTCOME_KINDS = frozenset(
    {
        # Canonical public outcomes.
        "candidate",
        "candidate_transaction",
        "noop",
        "clarify",
        "error",
        "requires_custom_nodes",
        # Explicitly supported legacy/internal and answer-only variants.
        "edit",
        "edit+clarify",
        "failure",
        "budget",
        "respond",
    }
)


def _field_change_is_well_formed(value: Mapping[str, Any]) -> bool:
    """Return whether *value* is a canonical display ``FieldChange``."""
    return _non_empty_string(value.get("uid")) and _non_empty_string(
        value.get("field_path")
    )


def _parsed_operation_is_well_formed(value: Mapping[str, Any]) -> bool:
    """Validate one raw operation through the canonical edit parser."""
    operation = value.get("op")
    if isinstance(operation, Mapping):
        operation = dict(operation)
    elif isinstance(operation, str):
        operation = dict(value)
    else:
        return False
    # ``parse_edit_delta`` historically obtains set_node_field.value with
    # ``get``; the response contract requires the field to be present even
    # when its value is explicitly null.
    if operation.get("op") == "set_node_field" and "value" not in operation:
        return False
    try:
        from vibecomfy.porting.edit.ops import parse_edit_delta

        parse_edit_delta([operation])
    except Exception:
        return False
    return True


def _change_entry_is_well_formed(value: Any) -> bool:
    """Return whether one outcome change is a canonical field change or op."""
    if not isinstance(value, Mapping) or not value:
        return False
    if "op" in value:
        return _parsed_operation_is_well_formed(value)
    return _field_change_is_well_formed(value)


def _accepted_batch_entry_is_well_formed(value: Any) -> bool:
    """Return whether one accepted-batch entry contains a valid edit op."""
    if not isinstance(value, Mapping):
        return False
    return isinstance(value.get("op"), Mapping) and _parsed_operation_is_well_formed(
        value
    )


def _accepted_batch_is_well_formed(
    response: Mapping[str, Any],
    *,
    allow_non_list: bool = False,
) -> bool:
    """Return whether an explicitly present accepted Δ has its JSON shape."""
    if "accepted_batch" not in response:
        return True
    accepted_batch = response.get("accepted_batch")
    if not isinstance(accepted_batch, list):
        # Only the explicit expected-no-candidate compatibility lane may
        # defer this carrier's classification to its tri-state adjudicator.
        return allow_non_list
    return all(_accepted_batch_entry_is_well_formed(item) for item in accepted_batch)


def _graph_payload_is_well_formed(value: Any) -> bool:
    """Validate a graph through the canonical ingest/import contract."""
    if not isinstance(value, Mapping) or not value:
        return False
    try:
        from vibecomfy.ingest.normalize import from_api, from_envelope, from_ui

        if "prompt" in value:
            prompt = value.get("prompt")
            if not isinstance(prompt, Mapping) or not prompt:
                return False
            _api_graph_structure_is_well_formed(prompt)
            from_api(dict(prompt))
            return True

        nodes = value.get("nodes")
        if isinstance(nodes, list):
            _ui_graph_structure_is_well_formed(value)
            from_ui(dict(value), use_comfy_converter=False)
            return True
        if isinstance(nodes, dict) and (
            "vibecomfy_format_version" in value
            or isinstance(value.get("compiled_api"), dict)
        ):
            from_envelope(dict(value))
            return True

        _api_graph_structure_is_well_formed(value)
        from_api(dict(value))
        return True
    except Exception:
        return False


def _api_graph_structure_is_well_formed(value: Mapping[str, Any]) -> None:
    """Reject empty/non-node API containers before canonical import."""
    if not value or not all(
        isinstance(node, Mapping)
        and _non_empty_string(node.get("class_type"))
        for node in value.values()
    ):
        raise ValueError("API graph must contain non-empty node mappings")
    node_ids = {str(node_id) for node_id in value}
    for node in value.values():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            raise ValueError("API node inputs must be a mapping")
        for link in inputs.values():
            if (
                isinstance(link, list)
                and len(link) == 2
                and isinstance(link[0], str)
                and link[0].lstrip("-").isdigit()
            ):
                if isinstance(link[1], bool) or not isinstance(link[1], int):
                    raise ValueError("API link slot must be an integer")
                if link[0] not in node_ids:
                    raise ValueError("API link source must name an existing node")


def _ui_graph_structure_is_well_formed(value: Mapping[str, Any]) -> None:
    """Validate LiteGraph nodes, links, endpoints, and link references."""
    nodes = value.get("nodes")
    links = value.get("links", [])
    if not isinstance(nodes, list) or not nodes or not isinstance(links, list):
        raise ValueError("UI graph requires non-empty nodes and an optional links list")
    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping) or "id" not in node:
            raise ValueError("UI graph node must be a mapping with an id")
        node_id = node["id"]
        if isinstance(node_id, bool) or not isinstance(node_id, (int, str)):
            raise ValueError("UI graph node id must be an integer or string")
        node_key = str(node_id)
        if not node_key or node_key in node_ids:
            raise ValueError("UI graph node ids must be unique and non-empty")
        node_ids.add(node_key)
        if "type" in node and not _non_empty_string(node["type"]):
            raise ValueError("UI graph node type must be a non-empty string")
        if "class_type" in node and not _non_empty_string(node["class_type"]):
            raise ValueError("UI graph node class_type must be a non-empty string")

    link_ids: set[int] = set()
    for link in links:
        if isinstance(link, list):
            if len(link) < 5:
                raise ValueError("UI graph link tuple is too short")
            link_id, origin_id, origin_slot, target_id, target_slot, *rest = link
            link_type = rest[0] if rest else None
        elif isinstance(link, Mapping):
            required = {"id", "origin_id", "origin_slot", "target_id", "target_slot"}
            if not required <= set(link):
                raise ValueError("UI graph link mapping is incomplete")
            link_id = link["id"]
            origin_id = link["origin_id"]
            origin_slot = link["origin_slot"]
            target_id = link["target_id"]
            target_slot = link["target_slot"]
            link_type = link.get("type")
        else:
            raise ValueError("UI graph links must be tuples or mappings")
        if (
            isinstance(link_id, bool)
            or not isinstance(link_id, int)
            or link_id in link_ids
            or not isinstance(origin_slot, int)
            or isinstance(origin_slot, bool)
            or origin_slot < 0
            or not isinstance(target_slot, int)
            or isinstance(target_slot, bool)
            or target_slot < 0
            or not isinstance(target_id, (int, str))
            or isinstance(target_id, bool)
            or not isinstance(origin_id, (int, str))
            or isinstance(origin_id, bool)
            or str(origin_id) not in node_ids
            or str(target_id) not in node_ids
            or (link_type is not None and not isinstance(link_type, str))
        ):
            raise ValueError("UI graph link has invalid id, slot, type, or endpoint")
        link_ids.add(link_id)
    for node in nodes:
        inputs = node.get("inputs", [])
        if inputs is None:
            continue
        if not isinstance(inputs, list):
            raise ValueError("UI graph node inputs must be a list")
        for input_item in inputs:
            if not isinstance(input_item, Mapping):
                raise ValueError("UI graph input must be a mapping")
            link_id = input_item.get("link")
            if link_id is not None and (
                isinstance(link_id, bool) or not isinstance(link_id, int) or link_id not in link_ids
            ):
                raise ValueError("UI graph input references an unknown link")
            if "name" in input_item and input_item["name"] is not None and not isinstance(
                input_item["name"], str
            ):
                raise ValueError("UI graph input name must be a string")


def _candidate_payload_is_well_formed(
    value: Any,
    *,
    carrier: str | None = None,
) -> bool:
    """Validate one graph or strict candidate-transaction payload."""
    if not isinstance(value, Mapping):
        return False
    if carrier == "candidate_transaction" or "contract_version" in value:
        if value.get("contract_version") != "candidate_transaction_v2":
            return False
        try:
            from vibecomfy.comfy_nodes.agent.candidate_transaction import (
                validate_candidate_transaction,
            )

            return validate_candidate_transaction(value)[0]
        except Exception:
            return False
    graph = value.get("graph") if "graph" in value else value
    return _graph_payload_is_well_formed(graph)


_CANDIDATE_CARRIERS = ("candidate", "candidate_graph", "candidate_transaction", "graph")


def _iter_candidate_carriers(
    response: Mapping[str, Any],
) -> tuple[tuple[str, Any], ...]:
    """Extract all candidate carriers from the response and its outcome."""
    carriers: list[tuple[str, Any]] = [
        (field, response[field]) for field in _CANDIDATE_CARRIERS if field in response
    ]
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        carriers.extend(
            (f"outcome.{field}", outcome[field])
            for field in _CANDIDATE_CARRIERS
            if field in outcome
        )
    return tuple(carriers)


def _candidate_carriers_are_well_formed(response: Mapping[str, Any]) -> bool:
    """Validate every present candidate carrier at its actual nesting path."""
    for field, value in _iter_candidate_carriers(response):
        carrier = field.rsplit(".", 1)[-1]
        if value is None:
            # Presence is authoritative: an explicitly named null carrier is
            # malformed evidence, not an omitted legacy carrier.  Otherwise a
            # response can smuggle a null product alongside graph_unchanged=
            # false and fall through to the legacy landed-count path.
            return False
        if not _candidate_payload_is_well_formed(value, carrier=carrier):
            return False
    return True


def _candidate_transaction_carrier_is_well_formed(
    response: Mapping[str, Any],
) -> bool:
    """Require a strict, present v2 transaction for transaction outcomes."""
    transactions = [
        (field, value)
        for field, value in _iter_candidate_carriers(response)
        if field.rsplit(".", 1)[-1] == "candidate_transaction"
    ]
    return bool(transactions) and any(
        value is not None
        and _candidate_payload_is_well_formed(
            value, carrier="candidate_transaction"
        )
        for _field, value in transactions
    )


_PACK_REF_KEYS = frozenset(
    {"slug", "source", "version", "commit", "url", "path", "name", "registry_id"}
)
_PROVISIONAL_SCHEMA_KEYS = frozenset({"version", "schema", "runnable"})
_RESOLVER_EVIDENCE_KEYS = frozenset(
    {"tier", "source", "endpoint", "cache_hit", "detail", "matched_classes"}
)
_CUSTOM_NODE_CANDIDATE_KEYS = frozenset(
    {
        "pack",
        "expected_classes",
        "validation_mode",
        "evidence",
        "warnings",
        "provisional_schema",
        "runnable",
        "stable_install_hash",
    }
)


def _pack_ref_is_well_formed(value: Any) -> bool:
    if not isinstance(value, Mapping) or not value or set(value) - _PACK_REF_KEYS:
        return False
    if not _non_empty_string(value.get("slug")) or not _non_empty_string(
        value.get("source")
    ):
        return False
    return all(
        field not in value or value[field] is None or _non_empty_string(value[field])
        for field in _PACK_REF_KEYS - {"slug", "source"}
    )


def _provisional_schema_is_well_formed(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) - _PROVISIONAL_SCHEMA_KEYS:
        return False
    if not value:
        return True
    if not _non_empty_string(value.get("version")):
        return False
    schema = value.get("schema")
    if not isinstance(schema, (Mapping, list)):
        return False
    return "runnable" not in value or value["runnable"] is False


def _resolver_evidence_is_well_formed(value: Any) -> bool:
    """Validate serialized resolver evidence through its wire contract."""
    if not isinstance(value, list) or not value:
        return False
    for item in value:
        if not isinstance(item, Mapping) or set(item) - _RESOLVER_EVIDENCE_KEYS:
            return False
        if not all(
            _non_empty_string(item.get(field))
            for field in ("tier", "source", "endpoint")
        ):
            return False
        if "cache_hit" in item and not isinstance(item["cache_hit"], bool):
            return False
        if "detail" in item and not isinstance(item["detail"], Mapping):
            return False
        matched = item.get("matched_classes")
        if matched is not None and (
            not isinstance(matched, list)
            or not all(_non_empty_string(class_name) for class_name in matched)
        ):
            return False
    return True


def _custom_node_candidate_is_well_formed(value: Any) -> bool:
    """Validate one complete serialized resolver candidate."""
    if (
        not isinstance(value, Mapping)
        or set(value) - _CUSTOM_NODE_CANDIDATE_KEYS
    ):
        return False
    expected_classes = value.get("expected_classes")
    if (
        not isinstance(expected_classes, list)
        or not expected_classes
        or len(expected_classes) > _MAX_COLLECTION_ITEMS
        or not all(_non_empty_string(item) for item in expected_classes)
    ):
        return False
    if "pack" in value and not _pack_ref_is_well_formed(value["pack"]):
        return False
    if "provisional_schema" in value and not _provisional_schema_is_well_formed(
        value["provisional_schema"]
    ):
        return False
    if "validation_mode" in value and (
        value["validation_mode"]
        not in {"class_validatable", "evidence_only", "workflow_json_provisional"}
    ):
        return False
    if "stable_install_hash" in value and not _non_empty_string(
        value["stable_install_hash"]
    ):
        return False
    if "runnable" in value and value["runnable"] is not False:
        return False
    if "warnings" in value and (
        not isinstance(value["warnings"], list)
        or len(value["warnings"]) > _MAX_OUTCOME_WARNINGS
        or not all(_non_empty_string(item) for item in value["warnings"])
    ):
        return False
    if "evidence" in value and not _resolver_evidence_is_well_formed(value["evidence"]):
        return False
    return True


def _custom_node_candidates_are_well_formed(
    outcome: Mapping[str, Any],
) -> bool:
    """Validate custom-node candidate evidence and its empty refusal exception."""
    if "candidates" not in outcome:
        return True
    candidates = outcome["candidates"]
    if not isinstance(candidates, list):
        return False
    if len(candidates) > _MAX_COLLECTION_ITEMS:
        return False
    if not candidates:
        return outcome.get("kind") == "requires_custom_nodes"
    return all(_custom_node_candidate_is_well_formed(item) for item in candidates)


def _response_has_candidate_evidence(response: Mapping[str, Any]) -> bool:
    """Return whether a candidate outcome carries product evidence."""
    if not _candidate_carriers_are_well_formed(response):
        return False
    outcome = response.get("outcome")
    if (
        isinstance(outcome, Mapping)
        and outcome.get("kind") == "candidate_transaction"
    ):
        # Transaction outcomes are authoritative and cannot fall back to a
        # graph, legacy candidate, or landed-count claim.
        return _candidate_transaction_carrier_is_well_formed(response)
    carriers = _iter_candidate_carriers(response)
    if any(value is not None for _field, value in carriers):
        return True
    if (
        response.get("graph_unchanged") is False
        and isinstance(outcome, Mapping)
        and outcome.get("kind") in {"candidate", "edit", "edit+clarify"}
    ):
        # A legacy response may omit the graph carrier entirely. Keep that
        # envelope loadable so the assessor's landed-count and edit gates can
        # classify it; any explicitly present malformed carrier fails closed.
        return True
    return False


def _response_has_answer_evidence(
    response: Mapping[str, Any], outcome: Mapping[str, Any]
) -> bool:
    """Return whether an answer/refusal has a structured terminal fact."""
    if any(_non_empty_string(response.get(field)) for field in ("message", "reply")):
        return True
    for field in ("report", "evidence", "artifacts", "change_details"):
        value = response.get(field)
        if isinstance(value, Mapping) and bool(value):
            return True
    for field in ("question", "reason"):
        if _non_empty_string(outcome.get(field)):
            return True
    if "candidates" in outcome and _custom_node_candidates_are_well_formed(outcome):
        return (
            outcome["candidates"] == []
            and outcome.get("kind") == "requires_custom_nodes"
            or bool(outcome["candidates"])
        )
    if "missing_classes" in outcome:
        return bool(outcome["missing_classes"])
    return False


def _response_changes_are_well_formed(response: Mapping[str, Any]) -> bool:
    """Validate direct and outcome change carriers through the edit parser."""
    for owner in (response, response.get("outcome")):
        if not isinstance(owner, Mapping) or "changes" not in owner:
            continue
        changes = owner["changes"]
        if not isinstance(changes, list) or not all(
            _change_entry_is_well_formed(item) for item in changes
        ):
            return False
    return True


def _response_outcome_is_well_formed(
    response: Mapping[str, Any],
) -> bool:
    """Validate outcome discriminants and the facts each kind requires."""
    outcome = response.get("outcome")
    if not isinstance(outcome, Mapping):
        return False
    if "warnings" in outcome:
        warnings = outcome["warnings"]
        if (
            not isinstance(warnings, list)
            or len(warnings) > _MAX_OUTCOME_WARNINGS
            or not all(_non_empty_string(item) for item in warnings)
        ):
            return False
    kind = outcome.get("kind")
    if not _non_empty_string(kind) or kind not in _RESPONSE_OUTCOME_KINDS:
        return False

    if not _candidate_carriers_are_well_formed(response):
        return False
    if not _response_changes_are_well_formed(response):
        return False
    if "question" in outcome and not _non_empty_string(outcome["question"]):
        return False
    if "reason" in outcome and not _non_empty_string(outcome["reason"]):
        return False
    for field in ("failure_kind", "stage", "next_action"):
        if field in outcome and not _non_empty_string(outcome[field]):
            return False
    if "retryable" in outcome and not isinstance(outcome["retryable"], bool):
        return False
    if "graph_unchanged" in outcome and not isinstance(
        outcome["graph_unchanged"], bool
    ):
        return False
    if "changes" in outcome:
        changes = outcome["changes"]
        if changes and kind not in {
            "candidate",
            "candidate_transaction",
            "edit",
            "edit+clarify",
        }:
            return False
    if "missing_classes" in outcome:
        missing_classes = outcome["missing_classes"]
        if (
            not isinstance(missing_classes, list)
            or not missing_classes
            or not all(_non_empty_string(item) for item in missing_classes)
        ):
            return False
    if not _custom_node_candidates_are_well_formed(outcome):
        return False
    if "evidence" in outcome and (
        not isinstance(outcome["evidence"], Mapping) or not outcome["evidence"]
    ):
        return False
    if "clarification" in outcome:
        clarification = outcome["clarification"]
        if not isinstance(clarification, Mapping):
            return False
        if "message" in clarification and not _non_empty_string(
            clarification["message"]
        ):
            return False
    if kind in {"candidate", "candidate_transaction", "edit", "edit+clarify"}:
        if not _response_has_candidate_evidence(response):
            return False
        if kind == "edit+clarify" and not (
            _non_empty_string(outcome.get("question"))
            or _response_has_answer_evidence(response, outcome)
        ):
            return False
    elif kind == "clarify":
        if not (
            _non_empty_string(outcome.get("question"))
            or (
                isinstance(outcome.get("clarification"), Mapping)
                and _non_empty_string(outcome["clarification"].get("message"))
            )
            or _response_has_answer_evidence(response, outcome)
        ):
            return False
    elif kind == "requires_custom_nodes":
        if not _response_has_answer_evidence(response, outcome):
            return False
    elif kind == "respond":
        if (
            response.get("route") != "respond"
            or response.get("graph_unchanged") is not True
        ):
            return False
    elif kind in {"error", "failure"}:
        # Product failures are terminal executor outcomes.  They must carry
        # the failed envelope bit and a non-sparse canonical failure record;
        # an ``ok=true`` label or a lone graph_unchanged/failure_kind field is
        # not enough to establish a real failure.
        if response.get("ok") is not False:
            return False
        failure_kind = outcome.get("failure_kind") or response.get("failure_kind")
        stage = outcome.get("stage") or response.get("failure_stage")
        retryable = outcome.get("retryable")
        next_action = outcome.get("next_action")
        graph_unchanged = outcome.get(
            "graph_unchanged", response.get("graph_unchanged")
        )
        if not (
            _non_empty_string(failure_kind)
            and _non_empty_string(stage)
            and isinstance(retryable, bool)
            and _non_empty_string(next_action)
            and isinstance(graph_unchanged, bool)
        ):
            return False
    elif kind == "budget" and not _response_has_answer_evidence(response, outcome):
        return False
    return True


def _legacy_response_without_outcome_is_valid(response: Mapping[str, Any]) -> bool:
    """Accept only explicit pre-v2 answer/edit/error envelopes without outcomes."""
    if response.get("ok") is False:
        return any(
            _non_empty_string(response.get(field))
            for field in ("error", "failure_message", "message", "failure_kind")
        )
    if response.get("graph_unchanged") is False and _response_has_candidate_evidence(
        response
    ):
        return True
    route = response.get("route")
    return (
        route in {"research", "inspect", "respond"}
        and response.get("graph_unchanged") is True
        and _response_has_answer_evidence(response, {})
    )


def _response_envelope_is_valid(
    response: dict[str, Any],
    *,
    allow_non_list_accepted_batch: bool = False,
) -> bool:
    """Validate every response shape dereferenced by the assessor or its judges."""
    if not _response_tree_is_bounded(response):
        return False
    has_ok = "ok" in response
    if has_ok and not isinstance(response["ok"], bool):
        return False
    if "graph_unchanged" in response and not isinstance(
        response["graph_unchanged"], bool
    ):
        return False
    if "route" in response and not isinstance(response["route"], str):
        return False
    if not _candidate_carriers_are_well_formed(response):
        return False
    if not _response_changes_are_well_formed(response):
        return False
    if not has_ok:
        if "outcome" in response:
            if not _response_outcome_is_well_formed(response):
                return False
        elif not _legacy_response_without_outcome_is_valid(response):
            return False
    elif response["ok"] is True:
        if "outcome" not in response:
            if not _legacy_response_without_outcome_is_valid(response):
                return False
        elif not _response_outcome_is_well_formed(response):
            return False
    elif "outcome" not in response:
        if not _legacy_response_without_outcome_is_valid(response):
            return False
    elif not _response_outcome_is_well_formed(response):
        return False
    elif response["outcome"].get("kind") not in {"error", "failure"}:
        return False


    mapping_fields = (
        "outcome",
        "readiness",
        "gates",
        "artifacts",
        "report",
        "change_details",
        "artifact_lineage",
        "evidence",
        "debug",
        "candidate",
        "candidate_graph",
        "candidate_transaction",
        "graph",
        "narrative_context",
        "apply_eligibility",
        "eligibility",
    )
    for field in mapping_fields:
        if field not in response:
            continue
        if (
            field in {"candidate", "candidate_graph", "candidate_transaction", "graph"}
            and response[field] is None
        ):
            continue
        if not isinstance(response[field], dict):
            return False

    readiness = response.get("readiness")
    if (
        isinstance(readiness, dict)
        and "ready" in readiness
        and not isinstance(readiness["ready"], bool)
    ):
        return False

    gates = response.get("gates")
    if isinstance(gates, dict) and any(
        not isinstance(value, bool) for value in gates.values()
    ):
        return False

    artifacts = response.get("artifacts")
    if isinstance(artifacts, dict):
        for field in ("original_ui", "candidate_ui", "final_ui"):
            if field in artifacts and not isinstance(artifacts[field], str):
                return False

    report = response.get("report")
    if isinstance(report, dict):
        if "executor" in report and not isinstance(report["executor"], dict):
            return False
        executor = report.get("executor")
        if isinstance(executor, dict):
            if "plan" in executor and not isinstance(executor["plan"], dict):
                return False
            plan = executor.get("plan")
            if isinstance(plan, dict):
                if "implement" in plan and not isinstance(plan["implement"], bool):
                    return False
                if "route" in plan and not isinstance(plan["route"], str):
                    return False

    for field in (
        "reply",
        "message",
        "error",
        "failure_kind",
        "failure_stage",
        "failure_message",
        "no_candidate_reason",
        "session_id",
        "turn_id",
        "detail_json_path",
        "detail_json_path_resolved",
        "session_path",
        "session_path_resolved",
        "plan_hash",
    ):
        if (
            field in response
            and response[field] is not None
            and not isinstance(response[field], str)
        ):
            return False
    for field in ("apply_eligible",):
        if field in response and not isinstance(response[field], bool):
            return False

    if not _accepted_batch_is_well_formed(
        response, allow_non_list=allow_non_list_accepted_batch
    ):
        return False
    return True


def _response_tree_is_bounded(value: Any) -> bool:
    """Reject response trees exceeding assessor resource budgets."""
    stack: list[tuple[Any, int]] = [(value, 0)]
    aggregate_values = 0
    while stack:
        current, depth = stack.pop()
        if depth > _MAX_RESPONSE_DEPTH:
            return False
        aggregate_values += 1
        if aggregate_values > _MAX_AGGREGATE_VALUES:
            return False
        if isinstance(current, str):
            if len(current) > _MAX_STRING_LENGTH:
                return False
        elif isinstance(current, dict):
            if len(current) > _MAX_COLLECTION_ITEMS:
                return False
            if aggregate_values + len(current) > _MAX_AGGREGATE_VALUES:
                return False
            for key, item in current.items():
                if not isinstance(key, str) or len(key) > _MAX_STRING_LENGTH:
                    return False
                stack.append((item, depth + 1))
        elif isinstance(current, list):
            if len(current) > _MAX_COLLECTION_ITEMS:
                return False
            if aggregate_values + len(current) > _MAX_AGGREGATE_VALUES:
                return False
            stack.extend((item, depth + 1) for item in current)
    return True


def _response_file_is_bounded(path: Path) -> bool:
    """Check the response artifact size before decoding it."""
    try:
        return path.stat().st_size <= _MAX_RESPONSE_BYTES
    except OSError:
        return False


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON artifact if it exists and is valid."""
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        # Secondary artifacts are still untrusted inputs.  Do not turn a
        # permission/read/decode failure into an absent-artifact fallback;
        # the public assessor converts this into an undetermined publication.
        raise AssessmentArtifactError(f"could not read JSON artifact {path}") from exc
    if not isinstance(payload, dict):
        raise AssessmentArtifactError(f"JSON artifact {path} is not an object")
    return payload


def _load_response_json(
    path: Path,
    *,
    allow_non_list_accepted_batch: bool = False,
) -> tuple[dict[str, Any] | None, str]:
    """Parse, validate, and deeply freeze the response evidence exactly once."""
    try:
        if not path.is_file():
            return None, "missing"
        if not _response_file_is_bounded(path):
            return None, "malformed"
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict) or not _response_tree_is_bounded(parsed):
            return None, "malformed"
        if not _response_envelope_is_valid(
            parsed,
            allow_non_list_accepted_batch=allow_non_list_accepted_batch,
        ):
            return None, "malformed"
        return _freeze_json(parsed), "valid"
    except (OSError, UnicodeError, TypeError):
        return None, "unavailable"
    except Exception:
        # JSON parsing, validation, and snapshot construction all operate on
        # hostile untrusted artifacts. Any exception is an unavailable
        # assessment input, never an assessor crash or fallback.
        return None, "malformed"


def _walk(obj: Any) -> Any:
    """Recursively yield every dict/string node in a JSON-like structure."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)
    else:
        yield obj


def _has_successful_candidate(response: Mapping[str, Any]) -> bool:
    """Return true when the response produced an applied candidate graph."""
    if response.get("ok") is not True:
        return False
    if response.get("graph_unchanged") is not False:
        return False
    return isinstance(response.get("candidate_graph"), Mapping) or isinstance(
        response.get("candidate"), Mapping
    )


def _queue_validate_skipped_for_successful_candidate(
    response: Mapping[str, Any],
) -> bool:
    """Return true when queue validation is absent, not failed.

    ``queue_validate_ok`` is fail-closed in the agent-edit gate map.  Some live
    batch paths can return a real changed candidate without running the queue
    stage at all; that missing stage should not be scored the same as a
    concrete queue blocker.
    """
    if not _has_successful_candidate(response):
        return False
    gates = response.get("gates")
    if not isinstance(gates, Mapping) or gates.get("queue_validate_ok") is not False:
        return False
    debug = response.get("debug")
    if not isinstance(debug, Mapping):
        return False
    stage_snapshots = debug.get("stage_snapshots")
    if not isinstance(stage_snapshots, list):
        return False
    stage_names = {
        str(item.get("stage"))
        for item in stage_snapshots
        if isinstance(item, Mapping) and item.get("stage") is not None
    }
    if "queue_validate" in stage_names:
        return False

    def _has_queue_blockers(value: Any) -> bool:
        if isinstance(value, list):
            return bool(value)
        if isinstance(value, tuple):
            return bool(value)
        return False

    report = response.get("report")
    if isinstance(report, Mapping) and _has_queue_blockers(
        report.get("queue_blockers")
    ):
        return False
    if _has_queue_blockers(debug.get("queue_blockers")):
        return False
    return True


def _batch_turn_failed(turn: Mapping[str, Any]) -> bool:
    """Return true for exploratory batch turns that did not contribute edits."""
    if turn.get("batch_ok") is False:
        return True
    if (turn.get("landed_op_count") or 0) == 0 and (
        turn.get("raw_landed_op_count") or 0
    ) == 0:
        for diagnostic in turn.get("diagnostics") or []:
            if (
                isinstance(diagnostic, Mapping)
                and diagnostic.get("severity") in _ERROR_SEVERITIES
            ):
                return True
    return False


def _walk_hard_diagnostic_scope(obj: Any, *, skip_failed_batch_turns: bool) -> Any:
    """Yield nodes for hard-diagnostic checks, excluding failed scratch turns.

    Agent-edit may keep a full transcript of exploratory batch attempts in
    ``change_details.batch_turns`` even when the executor ultimately returns a
    successful candidate from an earlier safe edit. Those failed attempts are
    useful audit trail, but they are not active defects in the applied graph.
    """
    if isinstance(obj, dict):
        yield obj
        for key, value in obj.items():
            if (
                skip_failed_batch_turns
                and key == "batch_turns"
                and isinstance(value, list)
            ):
                for item in value:
                    if isinstance(item, Mapping) and _batch_turn_failed(item):
                        continue
                    yield from _walk_hard_diagnostic_scope(
                        item,
                        skip_failed_batch_turns=skip_failed_batch_turns,
                    )
                continue
            yield from _walk_hard_diagnostic_scope(
                value,
                skip_failed_batch_turns=skip_failed_batch_turns,
            )
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_hard_diagnostic_scope(
                item,
                skip_failed_batch_turns=skip_failed_batch_turns,
            )
    else:
        yield obj


def _collect_hard_diagnostics(
    response: Mapping[str, Any],
    *,
    accepted_safe_refusal: bool = False,
) -> list[str]:
    """Return messages from any object with severity error/fatal."""
    issues: list[str] = []
    skip_failed_batch_turns = (
        _has_successful_candidate(response) or accepted_safe_refusal
    )
    for node in _walk_hard_diagnostic_scope(
        response,
        skip_failed_batch_turns=skip_failed_batch_turns,
    ):
        if not isinstance(node, dict):
            continue
        if node.get("severity") not in _ERROR_SEVERITIES:
            continue
        message = node.get("message")
        if not isinstance(message, str):
            detail = node.get("detail")
            message = (
                json.dumps(detail, sort_keys=True)
                if isinstance(detail, dict)
                else str(node)
            )
        message = message.strip()
        if message and message not in issues:
            issues.append(message)
    return issues


def _collect_pattern_matches(
    response: Mapping[str, Any],
    patterns: list[re.Pattern[str]],
) -> list[str]:
    """Return distinct string values matching any of the supplied patterns."""
    issues: list[str] = []
    seen: set[str] = set()
    for node in _walk(response):
        if not isinstance(node, str):
            continue
        for pattern in patterns:
            if pattern.search(node):
                if node not in seen:
                    seen.add(node)
                    issues.append(node)
                break
    return issues


def _canonical_route(response: Mapping[str, Any]) -> str:
    """Return the canonical public route carried by the response envelope.

    The authoritative field is the top-level ``route`` (written by
    ``AgentTurnResult.to_dict`` in vibecomfy.executor.contracts); the same
    public route is mirrored in ``evidence.classification.route`` and
    ``report.executor.plan.route``.  Missing/non-string routes resolve to
    the empty string so an envelope without a route can never claim a
    non-edit exemption (fail closed).
    """
    route = response.get("route")
    if isinstance(route, str):
        return route
    evidence = response.get("evidence")
    if isinstance(evidence, Mapping):
        classification = evidence.get("classification")
        if isinstance(classification, Mapping) and isinstance(
            classification.get("route"), str
        ):
            return classification["route"]
    report = response.get("report")
    if isinstance(report, Mapping):
        executor = report.get("executor")
        if isinstance(executor, Mapping):
            plan = executor.get("plan")
            if isinstance(plan, Mapping) and isinstance(plan.get("route"), str):
                return plan["route"]
    return ""


def _explicitly_non_edit_route(response: Mapping[str, Any]) -> bool:
    """Return True when the envelope's canonical route is a non-edit route.

    The route is read from the envelope (``response.route``) — never from the
    agent's self-declared ``no_candidate_reason`` / ``outcome.kind``.  An
    edit-route envelope self-labeling ``outcome.kind=clarify`` or
    ``no_candidate_reason=route_not_applyable`` is NOT exempt: a claimed edit
    (graph_unchanged=false) must still be backed by a positive landed count.
    These routes are scored by their own structured checks
    (``no_candidate_reason`` / ``outcome_kind``) and by the route/graph
    consistency check; demanding a positive landed operation count for them
    would be wrong — a truthful non-edit route has no operations to count.
    """
    return _canonical_route(response) in _NON_EDIT_ROUTES


def _landed_operation_count(response: Mapping[str, Any]) -> Any:
    """Return ``change_details.landed_operation_count`` (any JSON value)."""
    change_details = response.get("change_details")
    if isinstance(change_details, Mapping):
        return change_details.get("landed_operation_count")
    return None


def _expected_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
    """Return explicitly accepted public outcome kinds for this scenario."""
    if scenario is None:
        return set()
    assessment = scenario.get("assessment")
    if not isinstance(assessment, Mapping):
        return set()
    raw = assessment.get("expected_outcome_kinds")
    if raw is None:
        raw = assessment.get("expected_outcome_kind")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    return set()


_SAFE_REFUSAL_DEFAULT_KINDS = frozenset({"clarify", "requires_custom_nodes"})


def _scenario_requires_custom_nodes(scenario: Mapping[str, Any] | None) -> bool:
    if not isinstance(scenario, Mapping):
        return False
    tags = scenario.get("_tags")
    return isinstance(tags, Mapping) and tags.get("requires_custom_nodes") is True


def _cited_class_matches_declared(cited: str, declared: str) -> bool:
    """One-way exact/family-prefix class match (ADJUDICATION-4 ruling 1.1b).

    After trimming and case-folding ONLY: ``cited == declared or
    cited.startswith(declared)``.  The DECLARED token may be a family prefix
    of the cited full class name (``Hotshot`` ⊢ ``HotshotXLImg2Img``); the
    reverse is prohibited (``DINO``/``Grounding`` do NOT match
    ``GroundingDINO``, ``SomeGroundingDINOWrapper`` does not either).  No
    inner-substring comparison, no punctuation/fuzzy normalization.
    """
    folded_cited = str(cited).strip().casefold()
    folded_declared = str(declared).strip().casefold()
    if not folded_cited or not folded_declared:
        return False
    return folded_cited == folded_declared or folded_cited.startswith(folded_declared)


def _response_proves_class_absence(response: Mapping[str, Any] | None) -> bool:
    """True when the run proved a named class is absent from schema/runtime."""
    if not isinstance(response, Mapping):
        return False
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        missing = outcome.get("missing_classes")
        if isinstance(missing, (list, tuple)) and any(missing):
            return True
    report = response.get("report")
    if isinstance(report, Mapping):
        blocker = report.get("authoring_blocker")
        if isinstance(blocker, Mapping):
            missing = blocker.get("missing_runtime_classes")
            if isinstance(missing, (list, tuple)) and any(missing):
                return True
    return False


#: Terminal-state ``no_candidate_reason`` labels (renamed per ADJUDICATION-4
#: §2 assessor 5).  They classify how a scoped diff ended; they are NEVER
#: evidence for a declared absence premise.
TERMINAL_NO_CANDIDATE_REASONS = frozenset({"no_changes", "no_graph"})


def _response_cited_missing_classes(response: Mapping[str, Any]) -> tuple[str, ...]:
    """Return class names the envelope's structured fields cite as absent.

    Reads exactly the executor-emitted proof surfaces:
    ``outcome.missing_classes`` (promote_requires_custom_nodes_outcome) and
    ``report.authoring_blocker.missing_runtime_classes``
    (_record_named_schema_absence_blocker).  Prose is never consulted.
    """
    cited: list[str] = []
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        raw = outcome.get("missing_classes")
        if isinstance(raw, (list, tuple)):
            cited.extend(
                item.strip() for item in raw if isinstance(item, str) and item.strip()
            )
    report = response.get("report")
    if isinstance(report, Mapping):
        blocker = report.get("authoring_blocker")
        if isinstance(blocker, Mapping):
            raw = blocker.get("missing_runtime_classes")
            if isinstance(raw, (list, tuple)):
                cited.extend(
                    item.strip()
                    for item in raw
                    if isinstance(item, str) and item.strip()
                )
    return tuple(dict.fromkeys(cited))


def _engine_captured_search_misses(response: Mapping[str, Any]) -> tuple[str, ...]:
    """Return focus-type misses captured by successful schema-search statements.

    RRSYN2-1: reads exactly the engine seam —
    ``change_details.batch_turns[].statements[].detail.missing_classes``
    where the statement is an ``ok`` search query whose detail was written
    by ``vibecomfy.porting.edit._resolve._resolve_query_statement`` from the
    live schema provider.  Failed statements, other statement kinds, and
    prose are never consulted.
    """
    change_details = response.get("change_details")
    if not isinstance(change_details, Mapping):
        return ()
    turns = change_details.get("batch_turns")
    if not isinstance(turns, (list, tuple)):
        return ()
    cited: list[str] = []
    for turn in turns:
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        if not isinstance(statements, (list, tuple)):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            if statement.get("ok") is not True:
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping) or detail.get("query") != "search":
                continue
            raw = detail.get("missing_classes")
            if isinstance(raw, (list, tuple)):
                cited.extend(
                    item.strip()
                    for item in raw
                    if isinstance(item, str) and item.strip()
                )
    return tuple(dict.fromkeys(cited))


def _named_class_absence_evidence(
    response: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[str, str]:
    """Adjudicate named-class absence evidence (ruling 1.1b, RRSYN2-1).

    Returns ``(tri_state, detail)`` with ``tri_state`` in
    ``pass`` | ``undetermined`` | ``fail``.

    * An AUTHORITATIVE carrier is ``report.authoring_blocker`` with
      ``reason == "named_class_absent_from_schema"`` and a
      ``missing_runtime_classes`` list covering EVERY declared token
      (flat list = logical AND) under the one-way prefix rule.
    * RRSYN2-1: engine-captured
      ``change_details.batch_turns[].statements[].detail.missing_classes``
      from SUCCESSFUL schema-search statements is equally authoritative
      tool evidence — it is produced by the same schema-provider seam that
      feeds the blocker, so a leg whose stop never shaped a blocker can
      still ground its declared premise.
    * ``outcome.missing_classes`` is only the public projection: it may
      corroborate but alone is never sufficient; when both public carriers
      exist they must agree on the contract-relevant classes —
      contradiction is a hard failure.
    * Prose-only claims and generic terminal labels
      (``TERMINAL_NO_CANDIDATE_REASONS``) carry no authority here and are
      deliberately never consulted.
    """
    report = response.get("report")
    blocker = report.get("authoring_blocker") if isinstance(report, Mapping) else None
    authoritative: tuple[str, ...] = ()
    malformed_authoritative = False
    wrong_reason = None
    if isinstance(blocker, Mapping):
        reason = blocker.get("reason")
        raw = blocker.get("missing_runtime_classes")
        if isinstance(raw, (list, tuple)):
            authoritative = tuple(
                item.strip() for item in raw if isinstance(item, str) and item.strip()
            )
            if authoritative and reason != "named_class_absent_from_schema":
                wrong_reason = reason
        elif raw is not None:
            malformed_authoritative = True
    if malformed_authoritative:
        return "undetermined", (
            "malformed authoritative carrier: "
            "report.authoring_blocker.missing_runtime_classes is not a list"
        )
    if wrong_reason is not None:
        return "undetermined", (
            "report.authoring_blocker carries missing classes but reason="
            f"{wrong_reason!r} is not 'named_class_absent_from_schema'"
        )

    outcome = response.get("outcome")
    projected: tuple[str, ...] = ()
    if isinstance(outcome, Mapping):
        raw = outcome.get("missing_classes")
        if isinstance(raw, (list, tuple)):
            projected = tuple(
                item.strip() for item in raw if isinstance(item, str) and item.strip()
            )
    engine = _engine_captured_search_misses(response)

    def _covered_tokens(names: tuple[str, ...]) -> set[str]:
        return {
            declared
            for declared in contract["absent_classes"]
            if any(_cited_class_matches_declared(name, declared) for name in names)
        }

    covered_authoritative = _covered_tokens(authoritative)
    covered_projected = _covered_tokens(projected)
    covered_engine = _covered_tokens(engine)
    declared_all = set(contract["absent_classes"])
    if authoritative:
        if projected and covered_projected != covered_authoritative:
            return "fail", (
                "contradictory carriers: authoring_blocker covers declared "
                f"tokens {sorted(covered_authoritative)!r} but the "
                f"outcome.missing_classes projection covers "
                f"{sorted(covered_projected)!r}"
            )
        if covered_authoritative != declared_all:
            if covered_engine == declared_all:
                return "pass", (
                    "authoritative blocker cites only "
                    f"{sorted(covered_authoritative)!r}, but engine-captured "
                    "schema-search statement misses cover every declared "
                    f"absent class {sorted(declared_all)!r} via "
                    f"{sorted(engine)!r}"
                )
            return "undetermined", (
                f"authoritative blocker cites {list(authoritative)!r}, which "
                "does not cover every declared absent class "
                f"{sorted(declared_all)!r}"
            )
        return "pass", (
            "authoritative named-class blocker covers declared absent classes "
            f"{sorted(declared_all)!r} via {sorted(authoritative)!r}"
        )
    if engine:
        if covered_engine == declared_all:
            return "pass", (
                "engine-captured schema-search statement misses cover every "
                f"declared absent class {sorted(declared_all)!r} via "
                f"{sorted(engine)!r}"
            )
        return "undetermined", (
            "engine-captured search misses cite only "
            f"{sorted(covered_engine)!r} of the declared absent classes "
            f"{sorted(declared_all)!r}; partial coverage cannot ground the "
            "contract"
        )
    if projected:
        return "undetermined", (
            "only the public projection (outcome.missing_classes="
            f"{list(projected)!r}) is present; without an authoritative "
            "report.authoring_blocker named-class carrier or engine-captured "
            "schema-search misses it can never ground the contract"
        )
    return "undetermined", (
        "no structured absence evidence: neither "
        "report.authoring_blocker.missing_runtime_classes nor "
        "change_details batch-turn schema-search misses nor "
        "outcome.missing_classes cites the declared absent classes "
        f"{sorted(declared_all)!r}; prose and generic no_candidate_reason "
        "labels carry no adjudicative authority"
    )


def _authoritative_schema_entry(class_type: str) -> Mapping[str, Any] | None:
    """Resolve one class from the frozen authoritative object_info cache.

    Reads ``vibecomfy/porting/cache/object_info/index.json`` (class → cache
    file) and the referenced pack cache.  Unreadable index/cache or unknown
    class returns ``None`` — a schema lookup error grades undetermined, it
    never invents absence.
    """
    if not class_type:
        return None
    index = _load_json(_OBJECT_INFO_ROOT / "index.json")
    if not isinstance(index, Mapping):
        return None
    cache_file = index.get(class_type)
    if not isinstance(cache_file, str) or not cache_file:
        return None
    cache = _load_json(_OBJECT_INFO_ROOT / cache_file)
    if not isinstance(cache, Mapping):
        return None
    entry = cache.get(class_type)
    return entry if isinstance(entry, Mapping) else None


def _schema_surface_members(
    entry: Mapping[str, Any], member_kind: str
) -> tuple[str, ...]:
    """Return the schema member names for one surface of a class entry."""
    if member_kind == "output":
        outputs = entry.get("outputs")
        names: list[str] = []
        if isinstance(outputs, (list, tuple)):
            for item in outputs:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, (list, tuple)) and item:
                    # object_info output rows are [name, type] or [type].
                    head = item[0]
                    tail = item[1] if len(item) > 1 else None
                    if isinstance(tail, str):
                        names.append(str(head))
                    elif isinstance(head, str):
                        names.append(head)
        return tuple(names)
    inputs = entry.get("inputs")
    members: list[str] = []
    if isinstance(inputs, Mapping):
        for group in ("required", "optional"):
            block = inputs.get(group)
            if isinstance(block, Mapping):
                members.extend(str(key) for key in block)
    return tuple(members)


def _scenario_graph_nodes(
    output_dir: Path,
    scenario: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    """Return ``node_id -> class_type`` from the run's source/original graph.

    Prefers the persisted run artifact ``original.ui.json``; falls back to
    the scenario's declared ``workflow_path`` under the repository root.
    ``None`` means no readable graph — evidence-incomplete, never proof of
    absence.
    """
    data = _load_json(Path(output_dir) / "original.ui.json")
    nodes = _extract_graph_nodes(data) if isinstance(data, Mapping) else {}
    if not nodes and isinstance(scenario, Mapping):
        workflow_path = scenario.get("workflow_path")
        if isinstance(workflow_path, str) and workflow_path.strip():
            repo_root = Path(__file__).resolve().parents[2]
            data = _load_json(repo_root / workflow_path)
            nodes = _extract_graph_nodes(data) if isinstance(data, Mapping) else {}
    return nodes or None


def _extract_graph_nodes(data: Any) -> dict[str, str]:
    """Collect ``node_id -> class_type`` from any supported graph shape."""
    nodes: dict[str, str] = {}

    def record(node_id: Any, class_type: Any) -> None:
        if node_id is None or not isinstance(class_type, str) or not class_type:
            return
        nodes[str(node_id)] = class_type

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            if "class_type" in value or "type" in value:
                record(
                    value.get("id"),
                    value.get("class_type") or value.get("type"),
                )
            for key in ("nodes",):
                child = value.get(key)
                if isinstance(child, Mapping):
                    for node_id, node in child.items():
                        if isinstance(node, Mapping):
                            record(
                                node.get("id", node_id),
                                node.get("class_type") or node.get("type"),
                            )
                elif isinstance(child, list):
                    for node in child:
                        if isinstance(node, Mapping):
                            record(
                                node.get("id"),
                                node.get("class_type") or node.get("type"),
                            )
            for child in value.values():
                if isinstance(child, (Mapping, list)):
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return nodes


def _structural_feature_evidence(
    output_dir: Path,
    scenario: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[str, str]:
    """Independently validate typed structural-feature absence evidence.

    ADJUDICATION-4 ruling 1.1d: the envelope carrier
    (``report.authoring_blocker`` with ``reason ==
    "structural_feature_absent"`` + ``feature_absences``) is only a claim;
    every descriptor-required check is re-verified here against the
    source/original graph and the frozen authoritative schema:

    * the referenced class exists in the relevant graph;
    * the exact input/widget/output member is absent from the schema;
    * the reported ``available_members`` agree with the schema;
    * all descriptor-required checks are covered.

    Missing graph/schema, lookup errors, unrelated classes, prose-only
    claims, incomplete checks, or a generic ``no_changes`` label produce
    ``undetermined``; a check claiming absence of a member the schema HAS is
    an explicit contradiction and fails.
    """
    report = response.get("report")
    blocker = report.get("authoring_blocker") if isinstance(report, Mapping) else None
    if not isinstance(blocker, Mapping):
        return "undetermined", (
            "no authoritative structural carrier: report.authoring_blocker is absent"
        )
    if blocker.get("reason") != "structural_feature_absent":
        return "undetermined", (
            "report.authoring_blocker.reason="
            f"{blocker.get('reason')!r} is not 'structural_feature_absent'"
        )
    absences = blocker.get("feature_absences")
    if not isinstance(absences, list):
        return "undetermined", (
            "malformed structural carrier: feature_absences is not a list"
        )

    reported: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for raw_feature in absences:
        if not isinstance(raw_feature, Mapping):
            continue
        feature_name = str(raw_feature.get("feature") or "").strip()
        checks = raw_feature.get("checks")
        if not isinstance(checks, list):
            continue
        for raw_check in checks:
            if not isinstance(raw_check, Mapping):
                continue
            key = (
                feature_name,
                str(raw_check.get("class_type") or "").strip(),
                str(raw_check.get("member_kind") or "").strip(),
                str(raw_check.get("member") or "").strip(),
            )
            if all(key):
                reported[key] = raw_check

    graph_nodes = _scenario_graph_nodes(output_dir, scenario)
    if graph_nodes is None:
        return "undetermined", (
            "source/original graph is unavailable; structural absence cannot "
            "be independently verified"
        )
    graph_classes = set(graph_nodes.values())

    required: list[tuple[str, Mapping[str, Any]]] = []
    for feature in contract["absent_features"]:
        for check in feature["checks"]:
            required.append((str(feature["feature"]), check))
    missing_checks = [
        (feature_name, check)
        for feature_name, check in required
        if (
            feature_name,
            check["class_type"],
            check["member_kind"],
            check["member"],
        )
        not in reported
    ]
    if missing_checks:
        return "undetermined", (
            "incomplete structural evidence: response omits declared checks "
            + ", ".join(
                f"{name}/{check['class_type']}.{check['member']}"
                for name, check in missing_checks
            )
        )

    verified: list[str] = []
    for feature_name, check in required:
        key = (
            feature_name,
            check["class_type"],
            check["member_kind"],
            check["member"],
        )
        entry = _authoritative_schema_entry(check["class_type"])
        if entry is None:
            return "undetermined", (
                f"schema lookup error for {check['class_type']!r} in the "
                "frozen authoritative index; structural absence cannot be "
                f"verified for {key[0]}/{key[1]}.{key[3]}"
            )
        if check["class_type"] not in graph_classes:
            return "undetermined", (
                f"class {check['class_type']!r} does not exist in the "
                "source/original graph; the declared structural check is not "
                "verifiable against this workflow"
            )
        actual_members = _schema_surface_members(entry, check["member_kind"])
        if check["member"] in actual_members:
            return "fail", (
                "contradictory structural evidence: "
                f"{check['class_type']}.{check['member_kind']} "
                f"{check['member']!r} exists in the authoritative schema "
                f"(members: {sorted(actual_members)!r}) but the response "
                "claims it absent"
            )
        reported_check = reported[key]
        if reported_check.get("present") is not False:
            return "undetermined", (
                f"declared check {key[0]}/{key[1]}.{key[3]} does not assert "
                "present=false"
            )
        available = reported_check.get("available_members")
        if not isinstance(available, (list, tuple)):
            return "undetermined", (
                f"declared check {key[0]}/{key[1]}.{key[3]} reports no "
                "available_members; agreement with the schema cannot be "
                "verified"
            )
        normalized_available = sorted(str(item) for item in available)
        if normalized_available != sorted(actual_members):
            return "undetermined", (
                f"declared check {key[0]}/{key[1]}.{key[3]} reports "
                f"available_members={normalized_available!r} but the schema "
                f"attests {sorted(actual_members)!r}"
            )
        verified.append(f"{key[0]}/{key[1]}.{key[3]}")
    return "pass", (
        "all declared structural checks independently verified against the "
        f"source graph and frozen schema: {', '.join(verified)}"
    )


def _assess_expected_no_candidate(
    output_dir: Path,
    scenario: Mapping[str, Any] | None,
    response: Mapping[str, Any] | None,
    contract: Mapping[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Tri-state expected-no-candidate adjudicator (ADJUDICATION-4 §2).

    Replaces the former boolean ``_no_candidate_grounding``: returns
    ``pass`` / ``fail`` / ``undetermined`` plus the structured issues that
    carry the per-facet detail.  Runs BEFORE/OUTSIDE the ``if response is
    not None`` guard in :func:`assess_live_output_dir` so a missing
    response grades ``undetermined`` (issue
    ``expected_no_candidate_response_missing``), never pass.

    RRSYN2-1: grounding is graded by TERMINAL SUBSTANCE — graph_unchanged
    is True, zero accepted/landed operations, a safe-refusal outcome kind,
    and passing typed absence evidence.  The classifier's route label is
    diagnostic only when the closed terminal carries no delta.

    Accepted contracts emit ``expected_no_candidate_grounded`` (info) and
    grade the leg ``outcome_class="expected_no_candidate"``.
    """
    issues: list[dict[str, Any]] = []

    def _add(check: str, severity: str, detail: str) -> None:
        issues.append({"check": check, "severity": severity, "detail": detail})

    if response is None or not isinstance(response, Mapping):
        _add(
            "expected_no_candidate_response_missing",
            "undetermined",
            "Scenario declares an expected-no-candidate contract "
            f"({contract['reason'][:120]!r}...) but response.json is absent "
            "or not a mapping; missing evidence cannot prove the absence "
            "premise.",
        )
        return "undetermined", issues

    if response.get("ok") is False:
        _add(
            "expected_no_candidate_response_ok",
            "error",
            "response.ok is False under a declared expected-no-candidate "
            f"contract: {response.get('error') or response.get('message')}",
        )
        return "fail", issues

    graph_unchanged = response.get("graph_unchanged")
    if graph_unchanged is False:
        _add(
            "expected_no_candidate_graph_unchanged",
            "error",
            "Scenario declares expected-no-candidate "
            f"({contract['reason'][:120]!r}...) but response.graph_unchanged "
            "is False; a fabricated or landed edit contradicts the refusal "
            "contract.",
        )
        return "fail", issues
    if graph_unchanged is not True:
        _add(
            "expected_no_candidate_graph_state_unknown",
            "undetermined",
            "Scenario declares expected-no-candidate but "
            f"response.graph_unchanged is {graph_unchanged!r}; an unknown "
            "edit state cannot prove the absence premise.",
        )
        return "undetermined", issues

    outcome = response.get("outcome") or {}
    outcome_kind = outcome.get("kind") if isinstance(outcome, Mapping) else None
    route = _canonical_route(response)
    kind_ok = (
        isinstance(outcome_kind, str) and outcome_kind in contract["refusal_kinds"]
    )
    # RRSYN2-1: the pass prerequisites are AUTHORITATIVE OUTCOME FACTS —
    # graph_unchanged is True (enforced above), no accepted/landed
    # operations (both ``change_details.landed_operation_count`` AND the
    # sole durable Δ ``response.accepted_batch``), a safe-refusal outcome
    # kind inside the declared terminal set, and passing typed absence
    # evidence.  The classifier's route label is NOT substance: an honest
    # schema-search stop can carry a pre-search ``adapt`` label while
    # closing clarify/requires_custom_nodes with no delta; grading that
    # label as a failure punished truthful refusals
    # (hotshot-16-frames-agent-edit, image-face-detection-949658).
    landed_count = _landed_operation_count(response)
    # A POSITIVE integer landed count is a hard contradiction.  An absent
    # count is not gated here: ``graph_unchanged is True`` is already
    # enforced above (fail-closed), minimal legacy envelopes predate
    # change_details, and no producer lands edits without flipping that flag.
    ops_landed = (
        isinstance(landed_count, int)
        and not isinstance(landed_count, bool)
        and landed_count > 0
    )
    if not kind_ok:
        _add(
            "expected_no_candidate_refusal_kind",
            "error",
            "Declared expected-no-candidate scenario requires outcome.kind "
            f"in {sorted(contract['refusal_kinds'])!r} but got "
            f"{outcome_kind!r}.",
        )
    if ops_landed:
        _add(
            "expected_no_candidate_landed_operations",
            "error",
            "Declared expected-no-candidate scenario landed "
            f"change_details.landed_operation_count={landed_count!r}; an "
            "accepted delta contradicts the refusal contract regardless of "
            f"the {route!r} route label.",
        )
    elif route in _EDIT_ROUTES:
        _add(
            "expected_no_candidate_route_label",
            "info",
            f"Envelope closed on outcome.kind={outcome_kind!r} with zero "
            f"landed operations; the pre-search edit route label {route!r} "
            "is diagnostic only and does not contradict the refusal.",
        )

    # RRSYN2-1 conjunct 2: ``accepted_batch`` is the sole durable Δ.  A
    # grounded no-candidate refusal must carry NO canonical accepted delta:
    # an absent or empty list is clean; a MALFORMED carrier (non-list, or
    # non-mapping entries) or a NON-EMPTY batch contradicts the refusal
    # contract exactly like landed operations do — fail closed.
    accepted_batch = response.get("accepted_batch")
    batch_ok = True
    if accepted_batch is not None:
        if not isinstance(accepted_batch, list) or any(
            not isinstance(item, Mapping) for item in accepted_batch
        ):
            batch_ok = False
            _add(
                "expected_no_candidate_accepted_batch_malformed",
                "error",
                "Declared expected-no-candidate scenario carries a malformed "
                f"response.accepted_batch carrier ({type(accepted_batch).__name__}"
                "); the sole durable Δ must be an absent or empty statement "
                "list when no candidate was accepted.",
            )
        elif accepted_batch:
            batch_ok = False
            _add(
                "expected_no_candidate_accepted_delta",
                "error",
                "Declared expected-no-candidate scenario carried a non-empty "
                f"response.accepted_batch ({len(accepted_batch)} statement(s)); "
                "an accepted delta contradicts the refusal contract regardless "
                f"of the {route!r} route label.",
            )

    mode = contract["evidence_mode"]
    if mode == "named_class":
        evidence_tri, evidence_detail = _named_class_absence_evidence(
            response, contract
        )
    elif mode == "structural_feature":
        evidence_tri, evidence_detail = _structural_feature_evidence(
            output_dir, scenario, response, contract
        )
    else:
        evidence_tri, evidence_detail = (
            "undetermined",
            (
                "contract declares no coherent typed evidence mode "
                f"(evidence_mode={mode!r}); exactly one of named-class tokens or "
                "typed structural checks is required"
            ),
        )
    if evidence_tri == "fail":
        _add(
            "expected_no_candidate_evidence_contradiction",
            "error",
            evidence_detail,
        )
    elif evidence_tri == "undetermined":
        _add(
            "expected_no_candidate_ungrounded",
            "undetermined",
            "Declared expected-no-candidate premise is not grounded: "
            f"{evidence_detail} Declared reason: {contract['reason']}",
        )

    if any(issue["severity"] == "error" for issue in issues):
        return "fail", issues
    if evidence_tri == "pass" and kind_ok and not ops_landed and batch_ok:
        _add(
            "expected_no_candidate_grounded",
            "info",
            f"Accepted grounded no-candidate refusal ({mode} evidence): "
            f"{evidence_detail}; declared reason: {contract['reason']}",
        )
        return "pass", issues
    return "undetermined", issues


def _allowed_safe_refusal_outcome_kinds(
    scenario: Mapping[str, Any] | None,
    response: Mapping[str, Any] | None = None,
) -> set[str]:
    """Return no-edit outcome kinds accepted as safe refusals for edit scenarios.

    An explicit scenario allowlist always wins (including an empty list).
    Otherwise default ``clarify`` / ``requires_custom_nodes`` only when the
    scenario is tagged ``requires_custom_nodes`` or the run proved a named
    class is absent. Not a blanket default on every edit scenario.
    """
    if scenario is None:
        return set()
    assessment = scenario.get("assessment")
    raw = None
    if isinstance(assessment, Mapping):
        raw = assessment.get("allow_safe_refusal_outcome_kinds")
        if raw is None:
            raw = assessment.get("allow_safe_refusal_outcome_kind")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    if _scenario_requires_custom_nodes(scenario) or _response_proves_class_absence(
        response
    ):
        return set(_SAFE_REFUSAL_DEFAULT_KINDS)
    return set()


def _assessment_config(scenario: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return the scenario assessment config, if present."""
    if scenario is None:
        return {}
    assessment = scenario.get("assessment")
    return assessment if isinstance(assessment, Mapping) else {}


def _scenario_kind(scenario: Mapping[str, Any] | None) -> str:
    """Classify the scenario as edit, semantic_product, or health_control."""
    if scenario is None:
        return "unknown"
    classification = scenario.get("classification")
    if isinstance(classification, Mapping):
        kind = classification.get("kind")
        if kind in {"health_control", "semantic_product", "edit"}:
            return str(kind)
    if scenario.get("answer_rubric"):
        return "semantic_product"
    return "edit"


def _excluded_from_semantic_product_rates(scenario: Mapping[str, Any] | None) -> bool:
    if scenario is None:
        return False
    classification = scenario.get("classification")
    if isinstance(classification, Mapping) and (
        classification.get("excluded_from_semantic_product_rates") is True
        or classification.get("kind") == "health_control"
    ):
        return True
    return False


def _answer_rubric(scenario: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if scenario is None:
        return None
    rubric = scenario.get("answer_rubric")
    return rubric if isinstance(rubric, Mapping) else None


def _research_payloads(
    output_dir: Path,
    response: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Return every structured research payload captured for this turn."""
    payloads: list[Mapping[str, Any]] = []
    evidence = response.get("evidence")
    if isinstance(evidence, Mapping) and isinstance(evidence.get("research"), Mapping):
        payloads.append(evidence["research"])
    report = response.get("report")
    executor = report.get("executor") if isinstance(report, Mapping) else None
    if isinstance(executor, Mapping) and isinstance(executor.get("research"), Mapping):
        payloads.append(executor["research"])
    artifact = _load_json(output_dir / "research.json")
    if isinstance(artifact, Mapping):
        payloads.append(artifact)
    return payloads


def _assess_executed_research(
    output_dir: Path,
    response: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Require model, tool, and evidence activity for research controls."""
    config = _assessment_config(scenario)
    if config.get("require_executed_research") is not True:
        return []

    report = response.get("report")
    executor = report.get("executor") if isinstance(report, Mapping) else None
    usage = executor.get("deepseek_usage") if isinstance(executor, Mapping) else None
    n_calls = usage.get("n_calls") if isinstance(usage, Mapping) else None
    attempts = executor.get("model_attempts") if isinstance(executor, Mapping) else None
    has_model_call = (
        isinstance(n_calls, int) and not isinstance(n_calls, bool) and n_calls > 0
    ) or (isinstance(attempts, list) and len(attempts) > 0)

    payloads = _research_payloads(output_dir, response)
    tool_calls = max(
        (
            int(payload.get("tool_calls_executed", 0))
            for payload in payloads
            if isinstance(payload.get("tool_calls_executed", 0), int)
            and not isinstance(payload.get("tool_calls_executed", 0), bool)
        ),
        default=0,
    )
    attempts_seen = {
        str(payload.get("research_attempt", "")).strip().casefold()
        for payload in payloads
    }
    has_evidence = any(
        (
            isinstance(payload.get("evidence_artifacts"), int)
            and not isinstance(payload.get("evidence_artifacts"), bool)
            and payload["evidence_artifacts"] > 0
        )
        or bool(payload.get("citations"))
        or bool(payload.get("evidence_pack"))
        for payload in payloads
    )

    issues: list[dict[str, Any]] = []
    if not has_model_call:
        issues.append(
            {
                "check": "research_model_call",
                "severity": "error",
                "detail": "Research-purpose scenario executed no model call (n_calls=0).",
            }
        )
    if tool_calls <= 0:
        issues.append(
            {
                "check": "research_tool_execution",
                "severity": "error",
                "detail": "Research-purpose scenario executed no research tool call.",
            }
        )
    if not payloads or attempts_seen <= {"", "never"} or not has_evidence:
        issues.append(
            {
                "check": "research_evidence_present",
                "severity": "error",
                "detail": (
                    "Research-purpose scenario captured no executed research evidence "
                    "(missing/never attempt or empty evidence ledger)."
                ),
            }
        )
    return issues


def _assess_graph_census_consistency(
    response: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Reject explicit empty-graph prose against a non-empty locked graph."""
    if _assessment_config(scenario).get("require_graph_census_consistency") is not True:
        return []
    graph = scenario.get("graph") if isinstance(scenario, Mapping) else None
    if not isinstance(graph, dict):
        return []
    from vibecomfy.executor.core import _reply_claims_empty_graph
    from vibecomfy.executor.graph_inspection import inspect_graph

    evidence = inspect_graph(graph)
    reply = response.get("reply") or response.get("message") or ""
    if (
        evidence.node_count > 0
        and isinstance(reply, str)
        and _reply_claims_empty_graph(reply)
    ):
        return [
            {
                "check": "graph_census_consistency",
                "severity": "error",
                "detail": (
                    f"Reply claimed an empty/zero graph, but deterministic inspection "
                    f"found {evidence.node_count} nodes and {len(evidence.edges)} edges."
                ),
            }
        ]
    return []


def _tri_state_from_judge(verdict: Mapping[str, Any]) -> str:
    """Map a judge return value to pass|fail|undetermined.

    ``pass_`` True is pass. ``pass_`` False is fail, including malformed
    parsed verdicts. ``pass_`` None (outage, missing evidence, unparsable
    JSON) is undetermined.
    """
    if verdict.get("pass_") is True:
        return "pass"
    if verdict.get("pass_") is False:
        return "fail"
    return "undetermined"


def _record_judge_result(
    *,
    issues: list[dict[str, Any]],
    judge_results: list[dict[str, Any]],
    check: str,
    judge_name: str,
    verdict: Mapping[str, Any],
) -> str:
    """Append a judge result and a matching issue. Return the tri-state."""
    tri = _tri_state_from_judge(verdict)
    judge_results.append(
        {
            "judge": judge_name,
            "verdict": tri,
            "pass_": verdict.get("pass_"),
            "criteria": verdict.get("criteria") or {},
            "rationale": verdict.get("rationale", ""),
            "error": verdict.get("error"),
            # §28 fix 3: additive typed metadata (e.g. verdict class
            # "applied_unverified") so outcome classes survive into the
            # recorded assessment without renaming the tri-state vocabulary.
            "metadata": dict(verdict.get("metadata") or {}),
        }
    )
    if tri == "fail":
        issues.append(
            {
                "check": check,
                "severity": "error",
                "detail": (
                    f"{judge_name} failed: {verdict.get('rationale', 'no rationale')} "
                    f"criteria={verdict.get('criteria')}"
                ),
            }
        )
    elif tri == "pass":
        issues.append(
            {
                "check": check,
                "severity": "info",
                "detail": (
                    f"{judge_name} passed: {verdict.get('rationale', 'no rationale')} "
                    f"criteria={verdict.get('criteria')}"
                ),
            }
        )
    else:
        issues.append(
            {
                "check": check,
                "severity": "undetermined",
                "detail": f"{judge_name} could not run: {verdict.get('error')}",
            }
        )
    return tri


def _effective_edit_targets(
    scenario: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    """Return explicit effective-value targets required by the scenario."""
    assessment = _assessment_config(scenario)
    raw = assessment.get("effective_edit_targets")
    if raw is None:
        raw = assessment.get("effective_targets")
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)]
    return []


def _ui_artifact_path(
    output_dir: Path,
    response: Mapping[str, Any],
    artifact_name: str,
    fallback_name: str,
) -> Path:
    artifacts = response.get("artifacts")
    if isinstance(artifacts, Mapping) and isinstance(artifacts.get(artifact_name), str):
        return Path(artifacts[artifact_name])
    return output_dir / fallback_name


def _load_ui_artifact(
    output_dir: Path,
    response: Mapping[str, Any],
    artifact_name: str,
    fallback_name: str,
) -> Mapping[str, Any] | None:
    path = _ui_artifact_path(output_dir, response, artifact_name, fallback_name)
    loaded = _load_json(path)
    return loaded if isinstance(loaded, Mapping) else None


def _graph_field_target(target: Mapping[str, Any]) -> GraphFieldTarget | None:
    node_id = target.get("node_id")
    if node_id is None:
        return None
    widget_index = target.get("widget_index")
    if isinstance(widget_index, bool) or not isinstance(widget_index, int):
        widget_index = None
    field_name = (
        target.get("field_name")
        or target.get("input_name")
        or target.get("widget_name")
    )
    if not isinstance(field_name, str) or not field_name:
        field_name = None
    if field_name is None and widget_index is None:
        return None
    return GraphFieldTarget(
        node_id=node_id, field_name=field_name, widget_index=widget_index
    )


def _assess_effective_edit_targets(
    output_dir: Path,
    response: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Fail when a claimed parameter target has no effective value change."""
    targets = _effective_edit_targets(scenario)
    if not targets:
        return []

    original_ui = _load_ui_artifact(
        output_dir, response, "original_ui", "original.ui.json"
    )
    candidate_ui = _load_ui_artifact(
        output_dir, response, "candidate_ui", "candidate.ui.json"
    )
    if original_ui is None or candidate_ui is None:
        return [
            {
                "check": "effective_edit",
                "severity": "error",
                "detail": "Scenario requires effective edit checks, but UI artifacts are missing.",
            }
        ]

    issues: list[dict[str, Any]] = []
    for target in targets:
        label = str(
            target.get("label")
            or target.get("input_name")
            or target.get("widget_name")
            or target.get("node_id")
            or "target"
        )
        graph_target = _graph_field_target(target)
        if graph_target is None:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": f"Could not resolve effective edit target {label!r}.",
                }
            )
            continue

        try:
            change = compare_effective_field(original_ui, candidate_ui, graph_target)
        except (KeyError, ValueError) as exc:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": f"Could not resolve effective edit target {label!r}: {exc}.",
                }
            )
            continue

        # B12/B13: a change that lands through a shared linked source is a
        # valid edit — the agent may intentionally edit one source feeding
        # several consumers.  Only when the scenario explicitly opts into
        # isolation (assessment.isolate_shared_effective_sources) is a
        # multi-consumer source change treated as an error.
        isolate_shared_sources = (
            _assessment_config(scenario).get("isolate_shared_effective_sources") is True
        )
        if (
            change.effective_changed is True
            and isolate_shared_sources
            and change.before.source is not None
            and change.after.source is not None
            and str(change.before.source.node_id) == str(change.after.source.node_id)
            and change.before.source.output_slot == change.after.source.output_slot
            and max(
                change.before.source.outgoing_link_count,
                change.after.source.outgoing_link_count,
            )
            > 1
        ):
            issues.append(
                {
                    "check": "shared_effective_source_edit",
                    "severity": "error",
                    "detail": (
                        f"Target {label!r} changed through linked source "
                        f"{change.after.source.node_id!r} output "
                        f"{change.after.source.output_slot}, which has "
                        f"{change.after.source.outgoing_link_count} consumers. "
                        "The scenario requires an isolated source; set "
                        "assessment.isolate_shared_effective_sources=false to allow "
                        "intentional shared-source edits."
                    ),
                }
            )
            continue

        if change.effective_changed is True:
            continue

        if (
            change.raw_changed is True
            and (change.before.overridden or change.after.overridden)
            and change.effective_changed is False
        ):
            issues.append(
                {
                    "check": "inert_effective_edit",
                    "severity": "error",
                    "detail": (
                        f"Changed static widget for linked target {label!r} "
                        f"from {change.before.raw_value!r} to {change.after.raw_value!r}, "
                        f"but the effective linked value remained "
                        f"{change.after.effective_value!r}."
                    ),
                }
            )
        elif change.effective_changed is None:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": (
                        f"Could not prove effective value changed for target {label!r}; "
                        "one or both effective values were unknown."
                    ),
                }
            )
        else:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": (
                        f"Expected effective value change for target {label!r}, "
                        f"but it remained {change.after.effective_value!r}."
                    ),
                }
            )
    return issues


def _assess_live_output_dir(
    output_dir: Path | str,
    scenario: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect live artifacts under *output_dir* and return an assessment.

    The returned dict has:

    * ``passed`` — True iff ``verdict`` is ``pass``.
    * ``verdict`` — ``pass``, ``fail``, or ``undetermined`` (stable vocabulary).
    * ``outcome_class`` — additive honest class for the leg: ``safe_refusal``,
      ``applied-unverified`` (landed + replay-verified edit proven by the FULLY
      BOUND persisted transaction/receipt pair — DEEP-AUDIT-FIX-2-REVISION-2 —
      without an accepted Δ), ``non_edit_route_answered`` (canonical
      research/inspect/respond route correctly made no edit), or ``None``.
    * ``expect_graph_changed`` — whether the scenario expected an edit.
    * ``issue_count`` / ``error_count`` — counts.
    * ``issues`` — list of ``{"check", "severity", "detail"}`` dicts.
    * ``judge_results`` — one entry per judge that ran.
    """
    output_dir = Path(output_dir)
    no_candidate_contract = expected_no_candidate_contract(scenario or {})
    if no_candidate_contract is None:
        response, response_state = _load_response_json(output_dir / "response.json")
    else:
        response, response_state = _load_response_json(
            output_dir / "response.json",
            allow_non_list_accepted_batch=True,
        )
    impl_result = _load_json(output_dir / "implementation_result.json")

    issues: list[dict[str, Any]] = []
    judge_results: list[dict[str, Any]] = []
    if response_state != "valid":
        details = {
            "missing": "response.json is missing; live execution evidence is incomplete.",
            "unavailable": "response.json could not be read; live execution evidence is unavailable.",
            "malformed": "response.json is not a valid response object; live execution evidence is malformed.",
        }
        issues.append(
            {
                "check": f"response_{response_state}",
                "severity": "undetermined",
                "detail": details[response_state],
            }
        )
    expect_graph_changed = scenario_expects_graph_changed(scenario or {})
    expected_outcome_kinds = _expected_outcome_kinds(scenario)
    allowed_safe_refusal_outcome_kinds = _allowed_safe_refusal_outcome_kinds(
        scenario, response=response
    )
    assessment_cfg = _assessment_config(scenario)
    skip_intent_judge = bool(assessment_cfg.get("skip_intent_judge"))
    skip_semantic_judge = bool(assessment_cfg.get("skip_semantic_judge"))
    # The expected-no-candidate compatibility lane was selected before loading
    # the response so its adjudicator can classify a malformed carrier itself.
    if (
        response is not None
        and no_candidate_contract is None
        and not _accepted_batch_is_well_formed(response)
    ):
        issues.append(
            {
                "check": "response_accepted_batch_malformed",
                "severity": "undetermined",
                "detail": (
                    "response.accepted_batch is present but is not a list of "
                    "statement objects; accepted Δ evidence is unavailable."
                ),
            }
        )
    safe_refusal_accepted = False
    refusal_outage = False
    expected_no_candidate_accepted = False
    untyped_non_edit = False
    outcome_kind: Any = None
    non_edit_route = False
    answered_without_edit = False

    # ADJUDICATION-4 §2 (assessor 2/3): the declared expected-no-candidate
    # contract is adjudicated BEFORE/OUTSIDE the response guard so a missing
    # or malformed response grades undetermined — never pass — via
    # ``expected_no_candidate_response_missing``.
    if no_candidate_contract is not None:
        enc_tri, enc_issues = _assess_expected_no_candidate(
            output_dir, scenario, response, no_candidate_contract
        )
        issues.extend(enc_issues)
        if enc_tri == "pass":
            expected_no_candidate_accepted = True

    # ADJUDICATION-4 ruling 1.1f: an edit-kind scenario that merely sets
    # apply=false + expect_graph_changed=false is an invalid untyped non-edit
    # obligation; direct assessor invocation grades it ``undetermined``, never
    # pass.
    if descriptor_is_bare_untyped_non_edit(scenario or {}):
        issues.append(
            {
                "check": "untyped_non_edit_expectation",
                "severity": "undetermined",
                "detail": (
                    "Scenario sets apply=false + expect_graph_changed=false "
                    "without an explicit non-edit lane (health_control / "
                    "answer rubric / answer_only / executed research) or a "
                    "declared expected-no-candidate contract; an untyped "
                    "non-edit obligation can never grade pass."
                ),
            }
        )
        untyped_non_edit = True
    safe_refusal_accepted = False
    refusal_outage = False
    outcome_kind: Any = None
    lineage_assessment: dict[str, Any] = {
        "issues": [],
        "present": False,
        "manifest_digest": None,
        "binding": {},
        "provenance": "absent",
    }

    if response is not None:
        # §28 fix 3: canonical non-edit route recognition.  The envelope's
        # canonical route (research/inspect/respond/clarify/
        # requires_custom_nodes) decides whether a no-edit run is a legitimate
        # outcome class rather than a missing edit; the route is read exactly
        # as everywhere else in this module (_canonical_route machinery).
        non_edit_route = _explicitly_non_edit_route(response)
        answered_without_edit = (
            non_edit_route and response.get("graph_unchanged") is True
        )
        if answered_without_edit:
            issues.append(
                {
                    "check": "non_edit_route_no_edit",
                    "severity": "info",
                    "detail": (
                        f"Canonical non-edit route {non_edit_route!r} completed "
                        "without a graph edit; scored by its structured "
                        "non-edit checks (research evidence, census, rubric), "
                        "not by the expected-edit guards."
                    ),
                }
            )
        outcome = response.get("outcome") or {}
        outcome_kind = outcome.get("kind")
        refusal_candidate = (
            expect_graph_changed
            and response.get("graph_unchanged") is True
            and isinstance(outcome_kind, str)
            and outcome_kind in allowed_safe_refusal_outcome_kinds
        )

        # Universal grounded-refusal adjudication: an allowlisted label is
        # only a candidate. The judge decides pass/fail/undetermined.
        if refusal_candidate:
            refusal_verdict = judge_grounded_refusal(
                output_dir, scenario or {}, response_snapshot=response
            )
            refusal_tri = _record_judge_result(
                issues=issues,
                judge_results=judge_results,
                check="grounded_refusal",
                judge_name="grounded_refusal",
                verdict=refusal_verdict,
            )
            if refusal_tri == "pass":
                safe_refusal_accepted = True
            elif refusal_tri == "undetermined":
                refusal_outage = True

        # Top-level response health.
        if response.get("ok") is False:
            issues.append(
                {
                    "check": "response_ok",
                    "severity": "error",
                    "detail": f"response.ok is False: {response.get('error') or response.get('message')}",
                }
            )
        elif response.get("error"):
            issues.append(
                {
                    "check": "response_error_field",
                    "severity": "error",
                    "detail": f"response.error set: {response['error']}",
                }
            )

        # Readiness is also captured in flow_metadata, but surface it here if
        # the response carries it (e.g. blocked-prerequisite runs).
        readiness = response.get("readiness") or {}
        if readiness.get("ready") is False:
            issues.append(
                {
                    "check": "response_readiness",
                    "severity": "error",
                    "detail": f"Readiness not ready: {readiness.get('reason')}",
                }
            )

        if expect_graph_changed:
            if safe_refusal_accepted:
                issues.append(
                    {
                        "check": "safe_refusal",
                        "severity": "info",
                        "detail": f"Accepted safe refusal outcome.kind={outcome_kind!r}.",
                    }
                )
                # G5-B4-MUST-007: a grounded refusal is honest evidence, but
                # this scenario's obligation requires an EDITED product. The
                # leg records ``undetermined`` — never a pass.
                issues.append(
                    {
                        "check": "safe_refusal_edit_obligation",
                        "severity": "undetermined",
                        "detail": (
                            "scenario obligation requires an edited product; "
                            "an accepted safe refusal records undetermined "
                            "and can never grade pass"
                        ),
                    }
                )
            elif refusal_outage:
                # Outage cannot satisfy the scenario, but must not collapse
                # to a structural graph_changed product-fail.
                pass
            elif response.get("graph_unchanged") is True:
                issues.append(
                    {
                        "check": "graph_changed",
                        "severity": "error",
                        "detail": "Expected graph change but response.graph_unchanged is True.",
                    }
                )

            # G0R structural expected-edit guard: a claimed edit
            # (graph_unchanged is False) must be backed by a positive integer
            # change_details.landed_operation_count.  Missing, malformed, or
            # zero counts fail closed.  Accepted grounded refusals
            # (safe_refusal_accepted) and canonical non-edit routes are
            # exempt — they are scored by their own structured checks.
            route = _canonical_route(response)
            if (
                not safe_refusal_accepted
                and not refusal_outage
                and response.get("graph_unchanged") is False
                and not _explicitly_non_edit_route(response)
            ):
                landed_count = _landed_operation_count(response)
                if not (
                    isinstance(landed_count, int)
                    and not isinstance(landed_count, bool)
                    and landed_count > 0
                ):
                    issues.append(
                        {
                            "check": "landed_operation_count",
                            "severity": "error",
                            "detail": (
                                "Expected edit but change_details.landed_operation_count "
                                f"is {landed_count!r}; a positive integer is required "
                                "when graph_unchanged is false."
                            ),
                        }
                    )

            # G0R route/graph consistency: a canonical non-edit route must
            # never claim graph_unchanged=false.  Non-edit routes are exempt
            # from the landed-count guard only when the graph really is
            # unchanged (or the refusal is authorized above); an edit-route
            # envelope self-relabeled as clarify/respond/failure cannot
            # bypass the structural checks by relabeling alone.
            if (
                not safe_refusal_accepted
                and not refusal_outage
                and response.get("graph_unchanged") is False
                and route in _NON_EDIT_ROUTES
            ):
                issues.append(
                    {
                        "check": "route_graph_consistency",
                        "severity": "error",
                        "detail": (
                            f"Non-edit route {route!r} claimed graph_unchanged=false; "
                            "a non-edit route cannot change the graph."
                        ),
                    }
                )

            no_reason = response.get("no_candidate_reason")
            if (
                not safe_refusal_accepted
                and not refusal_outage
                and no_reason in {"no_changes", "no_candidate"}
            ):
                issues.append(
                    {
                        "check": "no_candidate_reason",
                        "severity": "error",
                        "detail": f"Expected edit but no_candidate_reason={no_reason!r}.",
                    }
                )

            if (
                not safe_refusal_accepted
                and not refusal_outage
                and outcome_kind in {"noop", "requires_custom_nodes"}
            ):
                issues.append(
                    {
                        "check": "outcome_kind",
                        "severity": "error",
                        "detail": f"Expected edit but outcome.kind={outcome_kind!r}.",
                    }
                )

            gates = response.get("gates") or {}
            false_gates = [name for name, value in gates.items() if value is False]
            queue_validate_skipped = _queue_validate_skipped_for_successful_candidate(
                response
            )
            if queue_validate_skipped and "queue_validate_ok" in false_gates:
                false_gates = [
                    name for name in false_gates if name != "queue_validate_ok"
                ]
                issues.append(
                    {
                        "check": "queue_validate_skipped",
                        "severity": "warning",
                        "detail": (
                            "queue_validate_ok was false, but the response contains a changed "
                            "candidate and no queue_validate stage ran; treating this as missing "
                            "queue evidence rather than a concrete queue blocker."
                        ),
                    }
                )
            if false_gates and not safe_refusal_accepted and not refusal_outage:
                issues.append(
                    {
                        "check": "gates",
                        "severity": "error",
                        "detail": f"Expected edit but gates failed: {', '.join(sorted(false_gates))}.",
                    }
                )

            if not safe_refusal_accepted and not refusal_outage:
                issues.extend(
                    _assess_effective_edit_targets(output_dir, response, scenario)
                )
        elif expected_outcome_kinds:
            outcome = response.get("outcome") or {}
            outcome_kind = outcome.get("kind")
            if outcome_kind not in expected_outcome_kinds:
                issues.append(
                    {
                        "check": "outcome_kind",
                        "severity": "error",
                        "detail": (
                            f"Expected outcome.kind in {sorted(expected_outcome_kinds)!r} "
                            f"but got {outcome_kind!r}."
                        ),
                    }
                )

        # Edit-intent judge: score the candidate when an edit is expected and
        # this is not a refusal candidate (refusals were already judged above).
        # Outage is undetermined and cannot satisfy the scenario. Malformed
        # parsed verdicts fail. graph_unchanged=false plus a refusal label is
        # never a safe refusal, so it still hits structural guards and the
        # edit-intent judge.
        if expect_graph_changed and not skip_intent_judge and not refusal_candidate:
            _record_judge_result(
                issues=issues,
                judge_results=judge_results,
                check="intent_judge",
                judge_name="edit_intent",
                verdict=judge_edit_intent(
                    output_dir, scenario or {}, response_snapshot=response
                ),
            )

        # Any hard diagnostic anywhere in the response envelope.
        for msg in _collect_hard_diagnostics(
            response,
            accepted_safe_refusal=safe_refusal_accepted,
        ):
            issues.append(
                {
                    "check": "hard_diagnostic",
                    "severity": "error",
                    "detail": msg,
                }
            )

        # G0-T2: the deterministic message-artifact prose matcher is removed.
        # Scoring is structured-only — prose never gates a scenario. The
        # agent's message always ships as written; the structured
        # cross-checks (graph_changed, outcome_kind, gates, landed counts,
        # effective edits) above remain fully authoritative.

        # Critical upstream failures (Hivemind 500, etc.). Infra is not a
        # product fail: semantic_product rows, successful candidates, and —
        # §28 fix 3 — canonical non-edit-route runs that correctly made no
        # edit keep these as warnings (RC9 / B6 S7).  A research/inspect leg
        # whose question was answered on a truthful non-edit route must not
        # product-fail because transient infra noise crossed the envelope.
        if (
            _scenario_kind(scenario) == "semantic_product"
            or _has_successful_candidate(response)
            or answered_without_edit
        ):
            upstream_severity = "warning"
        else:
            upstream_severity = "error"
        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
            issues.append(
                {
                    "check": "upstream_failure",
                    "severity": upstream_severity,
                    "detail": msg,
                }
            )

        # Capacity/soft warnings: surfaced, but not counted as errors.
        for msg in _collect_pattern_matches(response, _SOFT_WARNING_PATTERNS):
            issues.append(
                {
                    "check": "soft_warning",
                    "severity": "warning",
                    "detail": msg,
                }
            )

        # B12/B13 assessment-first research rules (enabled by
        # assessment.research): question-before-search, query relevance,
        # required-Hivemind invocation, citation resolution to returned
        # evidence IDs, no-local-search research path, and evidence-pack
        # capture.  All are structured-evidence checks — prose never gates.
        issues.extend(assess_research_evidence(response, scenario))
        issues.extend(_assess_executed_research(output_dir, response, scenario))
        issues.extend(_assess_graph_census_consistency(response, scenario))

        # T5.1: digest-linked artifact lineage — validity, scenario binding,
        # and fallback-impersonation checks. Structured evidence only.
        # G5-B4-MUST-003: lineage absence/mismatch is undetermined ONLY for
        # edit scenarios (C11). Health controls and semantic_product without
        # an expected edit do not carry edit authority and are exempt from
        # the lineage-presence gate; fallback-impersonation and binding
        # errors remain hard failures regardless.
        lineage_assessment = assess_artifact_lineage(output_dir, response, scenario)
        lineage_issues = lineage_assessment["issues"]
        kind = _scenario_kind(scenario)
        expect_edit = expect_graph_changed
        if (
            kind in ("health_control", "semantic_product") and not expect_edit
        ) or answered_without_edit:
            # §28 fix 3: a canonical non-edit route that truthfully reports an
            # unchanged graph carries no edit authority either, so the
            # lineage-presence gate cannot apply to it (same parity as the
            # health_control / semantic_product exemption above).
            lineage_issues = [
                iss
                for iss in lineage_issues
                if iss.get("check")
                not in (
                    "artifact_lineage_absent",
                    "artifact_lineage_sidecar_unverified",
                )
            ]

    # Semantic-answer judge runs for every D13 rubric scenario regardless
    # of edit expectation or response presence. Health controls are
    # structurally scored only.
    if (
        _answer_rubric(scenario) is not None
        and not _excluded_from_semantic_product_rates(scenario)
        and not skip_semantic_judge
    ):
        _record_judge_result(
            issues=issues,
            judge_results=judge_results,
            check="semantic_answer",
            judge_name="semantic_answer",
            verdict=judge_semantic_answer(
                output_dir, scenario or {}, response_snapshot=response
            ),
        )

    if impl_result is not None:
        # G0R: the residual "unchanged" substring gate over the
        # implementation_result message is removed — prose never gates
        # scoring.  Only the structured ok flag is authoritative.
        if impl_result.get("ok") is False:
            issues.append(
                {
                    "check": "implementation_result_ok",
                    "severity": "error",
                    "detail": (
                        "implementation_result.ok is False: "
                        f"{impl_result.get('error') or impl_result.get('message', '')}"
                    ),
                }
            )

    # Deduplicate while preserving order.
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue["check"], issue["severity"], issue["detail"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)

    errors = [issue for issue in deduped if issue["severity"] == "error"]
    undetermined_issues = [
        issue for issue in deduped if issue["severity"] == "undetermined"
    ]
    if errors:
        verdict = "fail"
    elif undetermined_issues:
        verdict = "undetermined"
    else:
        verdict = "pass"

    # §28 fix 3: additive outcome-class attribution.  The verdict vocabulary
    # (pass/fail/undetermined) is unchanged; this field only records WHICH
    # honest class the leg fell into so research/inspect no-edit runs and
    # landed-but-not-re-derivable edits are distinguishable from bare
    # undetermined rows.  New classes are additions, never renames.
    if safe_refusal_accepted:
        outcome_class = "safe_refusal"
    elif expected_no_candidate_accepted:
        # ADJUDICATION-4 ruling 1.1: accepted grounded no-candidate legs get
        # their DISTINCT class — never the generic non_edit_route_answered.
        outcome_class = "expected_no_candidate"
    elif any(
        isinstance(judge.get("metadata"), Mapping)
        and judge["metadata"].get("verdict") == "applied_unverified"
        for judge in judge_results
    ):
        outcome_class = "applied-unverified"
    elif answered_without_edit and not untyped_non_edit:
        # Ruling 1.1f: an untyped bare-false leg never claims the honest
        # non-edit class even when its envelope looks like one.
        outcome_class = "non_edit_route_answered"
    else:
        outcome_class = None

    original_ui_path = output_dir / "original.ui.json"
    final_ui_path = output_dir / "final.ui.json"
    assessment = {
        "passed": verdict == "pass",
        "verdict": verdict,
        "outcome_class": outcome_class,
        "expect_graph_changed": expect_graph_changed,
        "expected_outcome_kinds": sorted(expected_outcome_kinds),
        "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
        "issue_count": len(deduped),
        "error_count": len(errors),
        "issues": deduped,
        "judge_results": judge_results,
        "scenario_kind": _scenario_kind(scenario),
        "excluded_from_semantic_product_rates": _excluded_from_semantic_product_rates(
            scenario
        ),
        "artifact_lineage": {
            "present": lineage_assessment["present"],
            "manifest_digest": lineage_assessment["manifest_digest"],
            "binding": lineage_assessment["binding"],
            "provenance": lineage_assessment["provenance"],
        },
        "ui_evidence": {
            "original": original_ui_path.is_file(),
            "final": final_ui_path.is_file(),
        },
    }
    return _publish_assessment(output_dir, assessment)


def _publish_assessment(output_dir: Path | str, assessment: dict[str, Any]) -> dict[str, Any]:
    """Publish one assessment atomically, preserving the stale-on-error rule."""
    output_dir = Path(output_dir)
    assessment_path = output_dir / "assessment.json"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=".assessment.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(
                json.dumps(assessment, indent=2, sort_keys=True, default=str) + "\n"
            )
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, assessment_path)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise AssessmentPublicationError(
            f"failed to publish assessment atomically at {assessment_path}"
        ) from exc
    return assessment


def _publish_undetermined_artifact_assessment(
    output_dir: Path | str,
    scenario: Mapping[str, Any] | None,
    error: Exception,
) -> dict[str, Any]:
    """Publish an honest result when an ancillary artifact is unavailable."""
    try:
        expect_graph_changed = scenario_expects_graph_changed(scenario or {})
    except Exception:
        expect_graph_changed = False
    assessment = {
        "passed": False,
        "verdict": "undetermined",
        "outcome_class": None,
        "expect_graph_changed": expect_graph_changed,
        "expected_outcome_kinds": [],
        "allow_safe_refusal_outcome_kinds": [],
        "issue_count": 1,
        "error_count": 0,
        "issues": [
            {
                "check": "ancillary_artifact_unavailable",
                "severity": "undetermined",
                "detail": f"assessor could not inspect an ancillary artifact: {error}",
            }
        ],
        "judge_results": [],
        "scenario_kind": _scenario_kind(scenario),
        "excluded_from_semantic_product_rates": _excluded_from_semantic_product_rates(
            scenario
        ),
        "artifact_lineage": {
            "present": False,
            "manifest_digest": None,
            "binding": {},
            "provenance": "unavailable",
        },
        "ui_evidence": {"original": False, "final": False},
    }
    return _publish_assessment(output_dir, assessment)


def assess_live_output_dir(
    output_dir: Path | str,
    scenario: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess a run and publish undetermined on any ancillary access failure."""
    try:
        return _assess_live_output_dir(output_dir, scenario=scenario)
    except AssessmentPublicationError:
        raise
    except Exception as exc:
        # Artifact presence/read/decode/filesystem failures must not escape the
        # assessor or silently turn into a missing-artifact fallback. Publish
        # the undetermined result through the same atomic path as normal runs.
        return _publish_undetermined_artifact_assessment(output_dir, scenario, exc)
