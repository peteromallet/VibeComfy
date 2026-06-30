"""Execution-plan contracts for precedent-backed agent edits.

This module is intentionally pure contract surface for M1.  Runtime routing,
candidate gating, persistence, and graph-specific evaluators are wired in later
milestones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.executor.graph_inspection import EdgeEvidence, GraphEvidence, NodeEvidence, inspect_graph

from .session import STRUCTURAL_PROJECTION_VERSION, structural_graph_hash

EXECUTION_PLAN_CONTRACT_VERSION = "execution_plan_v1"
PLAN_EVALUATION_CONTRACT_VERSION = "plan_evaluation_v1"

SUPPORTED_EXECUTION_PLAN_CONTRACT_VERSIONS: tuple[str, ...] = (
    EXECUTION_PLAN_CONTRACT_VERSION,
)
SUPPORTED_PLAN_EVALUATION_CONTRACT_VERSIONS: tuple[str, ...] = (
    PLAN_EVALUATION_CONTRACT_VERSION,
)

CURRENT_EXECUTION_PLAN_VERSION = 1
CURRENT_PLAN_EVALUATION_VERSION = 1

VERSION_STATUS_SUPPORTED = "supported"
VERSION_STATUS_NEWER = "newer"
VERSION_STATUS_UNSUPPORTED = "unsupported"
VERSION_STATUS_AMBIGUOUS = "ambiguous"

REQUIRED_CRITICALITIES: tuple[str, ...] = ("required", "critical")
OPTIONAL_CRITICALITIES: tuple[str, ...] = ("recommended", "optional", "advisory")
PLAN_CRITICALITIES: tuple[str, ...] = REQUIRED_CRITICALITIES + OPTIONAL_CRITICALITIES
STEP_STATUSES: tuple[str, ...] = (
    "planned",
    "not_evaluated",
    "satisfied",
    "missing",
    "failed",
    "blocked",
)

SUPPORTED_CONDITION_KINDS: tuple[str, ...] = (
    "required_class",
    "required_value",
    "direct_edge",
    "reachable_path",
    "direct_edge_or_reachable_path",
    "terminal_consumes",
    "active_output_domain",
    "unconsumed_functional_outputs",
    "batch_frame_count",
    "value_or_path_count",
)

UNKNOWN_PLAN_VERSION_CONDITION_ID = "execution_plan_contract_version"
UNKNOWN_EVALUATION_VERSION_CONDITION_ID = "plan_evaluation_contract_version"

_EXECUTION_PLAN_VERSION_RE = re.compile(r"^execution_plan_v(?P<version>[1-9][0-9]*)$")
_PLAN_EVALUATION_VERSION_RE = re.compile(r"^plan_evaluation_v(?P<version>[1-9][0-9]*)$")


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze_jsonish(value[key])
            for key in sorted(value, key=lambda item: str(item))
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_jsonish(item) for item in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_jsonish(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, tuple):
        return [_thaw_jsonish(item) for item in value]
    if isinstance(value, list):
        return [_thaw_jsonish(item) for item in value]
    return value


def _omit_none(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _version_status(
    contract_version: str | None,
    *,
    supported_versions: tuple[str, ...],
    version_re: re.Pattern[str],
    current_version: int,
) -> str:
    if not isinstance(contract_version, str) or not contract_version:
        return VERSION_STATUS_AMBIGUOUS
    if contract_version in supported_versions:
        return VERSION_STATUS_SUPPORTED
    match = version_re.fullmatch(contract_version)
    if not match:
        return VERSION_STATUS_UNSUPPORTED
    version = int(match.group("version"))
    if version > current_version:
        return VERSION_STATUS_NEWER
    return VERSION_STATUS_UNSUPPORTED


def execution_plan_version_status(contract_version: str | None) -> str:
    return _version_status(
        contract_version,
        supported_versions=SUPPORTED_EXECUTION_PLAN_CONTRACT_VERSIONS,
        version_re=_EXECUTION_PLAN_VERSION_RE,
        current_version=CURRENT_EXECUTION_PLAN_VERSION,
    )


def plan_evaluation_version_status(contract_version: str | None) -> str:
    return _version_status(
        contract_version,
        supported_versions=SUPPORTED_PLAN_EVALUATION_CONTRACT_VERSIONS,
        version_re=_PLAN_EVALUATION_VERSION_RE,
        current_version=CURRENT_PLAN_EVALUATION_VERSION,
    )


def is_supported_execution_plan_version(contract_version: str | None) -> bool:
    return execution_plan_version_status(contract_version) == VERSION_STATUS_SUPPORTED


def is_supported_plan_evaluation_version(contract_version: str | None) -> bool:
    return plan_evaluation_version_status(contract_version) == VERSION_STATUS_SUPPORTED


@dataclass(frozen=True)
class SocketRef:
    """Stable-ish reference to a graph node socket or input."""

    node_id: str | None = None
    uid: str | None = None
    var: str | None = None
    class_type: str | None = None
    socket: str | None = None
    input_name: str | None = None
    output_name: str | None = None
    index: int | None = None
    role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _omit_none({
            "node_id": self.node_id,
            "uid": self.uid,
            "var": self.var,
            "class_type": self.class_type,
            "socket": self.socket,
            "input_name": self.input_name,
            "output_name": self.output_name,
            "index": self.index,
            "role": self.role,
        })


@dataclass(frozen=True)
class RoleBinding:
    """Binding from a semantic plan role to an observed graph node."""

    role: str
    node_ref: SocketRef
    class_type: str | None = None
    confidence: str = "unknown"
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", _freeze_jsonish(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return _omit_none({
            "role": self.role,
            "node_ref": self.node_ref.to_dict(),
            "class_type": self.class_type,
            "confidence": self.confidence,
            "evidence": _thaw_jsonish(self.evidence),
        })


@dataclass(frozen=True)
class PlanCondition:
    """A condition that must be evaluated against a candidate graph."""

    condition_id: str
    kind: str
    criticality: str = "required"
    source: SocketRef | None = None
    target: SocketRef | None = None
    expected: Any = None
    class_type: str | None = None
    input_name: str | None = None
    message: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected", _freeze_jsonish(self.expected))
        object.__setattr__(self, "details", _freeze_jsonish(self.details))

    @property
    def is_required(self) -> bool:
        return self.criticality in REQUIRED_CRITICALITIES

    @property
    def supported_kind(self) -> bool:
        return self.kind in SUPPORTED_CONDITION_KINDS

    def to_dict(self) -> dict[str, Any]:
        return _omit_none({
            "id": self.condition_id,
            "kind": self.kind,
            "criticality": self.criticality,
            "source": self.source.to_dict() if self.source is not None else None,
            "target": self.target.to_dict() if self.target is not None else None,
            "expected": _thaw_jsonish(self.expected),
            "class_type": self.class_type,
            "input_name": self.input_name,
            "message": self.message,
            "details": _thaw_jsonish(self.details),
        })


@dataclass(frozen=True)
class PlanStep:
    """An authored action or obligation in an execution plan."""

    step_id: str
    kind: str
    criticality: str = "required"
    status: str = "planned"
    class_type: str | None = None
    assign_to: str | None = None
    schema_source: str | None = None
    runtime_availability: str | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    values: Mapping[str, Any] = field(default_factory=dict)
    conditions: tuple[PlanCondition, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", _freeze_jsonish(self.inputs))
        object.__setattr__(self, "values", _freeze_jsonish(self.values))
        object.__setattr__(self, "conditions", tuple(self.conditions))
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))

    @property
    def is_required(self) -> bool:
        return self.criticality in REQUIRED_CRITICALITIES

    def to_dict(self) -> dict[str, Any]:
        return _omit_none({
            "id": self.step_id,
            "kind": self.kind,
            "criticality": self.criticality,
            "status": self.status,
            "class_type": self.class_type,
            "assign_to": self.assign_to,
            "schema_source": self.schema_source,
            "runtime_availability": self.runtime_availability,
            "inputs": _thaw_jsonish(self.inputs),
            "values": _thaw_jsonish(self.values),
            "conditions": [condition.to_dict() for condition in self.conditions],
            "evidence_refs": list(self.evidence_refs),
        })


@dataclass(frozen=True)
class ExecutionPlan:
    """Authoritative structural obligations for a candidate graph edit."""

    plan_id: str
    goal: str = ""
    source_graph_hash: str | None = None
    candidate_graph_hash: str | None = None
    research_result_hash: str | None = None
    selected_precedent_id: str | None = None
    selected_precedent: Mapping[str, Any] = field(default_factory=dict)
    role_bindings: tuple[RoleBinding, ...] = ()
    required_steps: tuple[PlanStep, ...] = ()
    done_conditions: tuple[PlanCondition, ...] = ()
    active_path_conditions: tuple[PlanCondition, ...] = ()
    blocked_if: tuple[PlanCondition, ...] = ()
    schema_provenance: Mapping[str, Any] = field(default_factory=dict)
    runtime_provenance: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EXECUTION_PLAN_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_precedent", _freeze_jsonish(self.selected_precedent))
        object.__setattr__(self, "role_bindings", tuple(self.role_bindings))
        object.__setattr__(self, "required_steps", tuple(self.required_steps))
        object.__setattr__(self, "done_conditions", tuple(self.done_conditions))
        object.__setattr__(self, "active_path_conditions", tuple(self.active_path_conditions))
        object.__setattr__(self, "blocked_if", tuple(self.blocked_if))
        object.__setattr__(self, "schema_provenance", _freeze_jsonish(self.schema_provenance))
        object.__setattr__(self, "runtime_provenance", _freeze_jsonish(self.runtime_provenance))

    @property
    def supported_contract_version(self) -> bool:
        return is_supported_execution_plan_version(self.contract_version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "plan_id": self.plan_id,
            "goal": self.goal,
            "source_graph_hash": self.source_graph_hash,
            "candidate_graph_hash": self.candidate_graph_hash,
            "research_result_hash": self.research_result_hash,
            "selected_precedent_id": self.selected_precedent_id,
            "selected_precedent": _thaw_jsonish(self.selected_precedent),
            "role_bindings": [binding.to_dict() for binding in self.role_bindings],
            "required_steps": [step.to_dict() for step in self.required_steps],
            "done_conditions": [condition.to_dict() for condition in self.done_conditions],
            "active_path_conditions": [
                condition.to_dict() for condition in self.active_path_conditions
            ],
            "blocked_if": [condition.to_dict() for condition in self.blocked_if],
            "schema_provenance": _thaw_jsonish(self.schema_provenance),
            "runtime_provenance": _thaw_jsonish(self.runtime_provenance),
        }

    def fail_closed_evaluation(
        self,
        *,
        candidate_graph_hash: str | None = None,
        reason: str | None = None,
    ) -> "PlanEvaluation":
        return fail_closed_evaluation_for_plan_version(
            self,
            candidate_graph_hash=candidate_graph_hash,
            reason=reason,
        )


@dataclass(frozen=True)
class PlanEvaluation:
    """Deterministic result of checking a candidate graph against a plan."""

    plan_id: str
    ok: bool
    blocking: bool
    source_graph_hash: str | None = None
    candidate_graph_hash: str | None = None
    selected_precedent_id: str | None = None
    step_status: tuple[Mapping[str, Any], ...] = ()
    failed_conditions: tuple[Mapping[str, Any], ...] = ()
    feedback: str = ""
    schema_provenance: Mapping[str, Any] = field(default_factory=dict)
    runtime_provenance: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = PLAN_EVALUATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "step_status",
            tuple(_freeze_jsonish(status) for status in self.step_status),
        )
        object.__setattr__(
            self,
            "failed_conditions",
            tuple(_freeze_jsonish(condition) for condition in self.failed_conditions),
        )
        object.__setattr__(self, "schema_provenance", _freeze_jsonish(self.schema_provenance))
        object.__setattr__(self, "runtime_provenance", _freeze_jsonish(self.runtime_provenance))

    @property
    def supported_contract_version(self) -> bool:
        return is_supported_plan_evaluation_version(self.contract_version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "plan_id": self.plan_id,
            "ok": self.ok,
            "blocking": self.blocking,
            "source_graph_hash": self.source_graph_hash,
            "candidate_graph_hash": self.candidate_graph_hash,
            "selected_precedent_id": self.selected_precedent_id,
            "step_status": _thaw_jsonish(self.step_status),
            "failed_conditions": _thaw_jsonish(self.failed_conditions),
            "feedback": self.feedback,
            "schema_provenance": _thaw_jsonish(self.schema_provenance),
            "runtime_provenance": _thaw_jsonish(self.runtime_provenance),
        }

    def fail_closed_if_unsupported_version(self) -> "PlanEvaluation":
        if self.supported_contract_version:
            return self
        return fail_closed_evaluation_for_evaluation_version(self)


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _condition_value(condition: PlanCondition | Mapping[str, Any], key: str) -> Any:
    if isinstance(condition, PlanCondition):
        if key == "id":
            return condition.condition_id
        return getattr(condition, key, None)
    if isinstance(condition, Mapping):
        if key == "condition_id":
            return condition.get("condition_id") or condition.get("id")
        if key == "id":
            return condition.get("id") or condition.get("condition_id")
        return condition.get(key)
    return None


def _condition_id(condition: PlanCondition | Mapping[str, Any]) -> str:
    return str(_condition_value(condition, "id") or "unknown_condition")


def _condition_details(condition: PlanCondition | Mapping[str, Any]) -> Mapping[str, Any]:
    details = _condition_value(condition, "details")
    return details if isinstance(details, Mapping) else {}


def _condition_is_required(condition: PlanCondition | Mapping[str, Any]) -> bool:
    criticality = str(_condition_value(condition, "criticality") or "required")
    return criticality in REQUIRED_CRITICALITIES


def _condition_to_dict(condition: PlanCondition | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(condition, PlanCondition):
        return condition.to_dict()
    if isinstance(condition, Mapping):
        return _thaw_jsonish(condition)
    return {"id": _condition_id(condition), "kind": "unknown"}


def _as_socket_ref(value: Any) -> SocketRef | Mapping[str, Any] | None:
    if isinstance(value, SocketRef):
        return value
    if isinstance(value, Mapping):
        return value
    return None


def _socket_value(ref: SocketRef | Mapping[str, Any] | None, key: str) -> Any:
    if ref is None:
        return None
    if isinstance(ref, SocketRef):
        return getattr(ref, key, None)
    return ref.get(key)


def _normalise_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalise_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _class_matches(class_type: str, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, str):
        return class_type == expected or _normalise_token(class_type) == _normalise_token(expected)
    if isinstance(expected, (list, tuple, set, frozenset)):
        return any(_class_matches(class_type, item) for item in expected)
    return False


def _node_matches_ref(node: NodeEvidence, ref: SocketRef | Mapping[str, Any] | None) -> bool:
    if ref is None:
        return True
    ref_ids = (
        _socket_value(ref, "node_id"),
        _socket_value(ref, "uid"),
        _socket_value(ref, "var"),
    )
    usable_ids = {str(value) for value in ref_ids if value is not None}
    if usable_ids and str(node.node_id) not in usable_ids and (node.title or "") not in usable_ids:
        return False
    expected_class = _socket_value(ref, "class_type")
    return _class_matches(node.class_type, expected_class)


def _nodes_matching(
    evidence: GraphEvidence,
    *,
    ref: SocketRef | Mapping[str, Any] | None = None,
    class_type: Any = None,
) -> tuple[NodeEvidence, ...]:
    result = []
    for node in evidence.nodes:
        if ref is not None and not _node_matches_ref(node, ref):
            continue
        if class_type is not None and not _class_matches(node.class_type, class_type):
            continue
        result.append(node)
    return tuple(result)


def _node_by_id(evidence: GraphEvidence) -> dict[int | str, NodeEvidence]:
    return {node.node_id: node for node in evidence.nodes}


def _slot_name_by_index(slots: tuple[Any, ...], index: Any) -> str | None:
    if isinstance(index, int) and 0 <= index < len(slots):
        name = getattr(slots[index], "name", None)
        return str(name) if name is not None else None
    return str(index) if index is not None else None


def _edge_input_name(edge: EdgeEvidence, target: NodeEvidence | None) -> str | None:
    if target is None:
        return None
    for slot in target.input_slots:
        if slot.link_id == edge.link_id:
            return slot.name
    return _slot_name_by_index(target.input_slots, edge.target_slot)


def _edge_output_name(edge: EdgeEvidence, source: NodeEvidence | None) -> str | None:
    if source is None:
        return None
    return _slot_name_by_index(source.output_slots, edge.origin_slot)


def _edge_matches_socket_names(
    edge: EdgeEvidence,
    *,
    source_node: NodeEvidence | None,
    target_node: NodeEvidence | None,
    source_ref: SocketRef | Mapping[str, Any] | None,
    target_ref: SocketRef | Mapping[str, Any] | None,
    input_name: str | None = None,
) -> bool:
    expected_output = _socket_value(source_ref, "output_name") or _socket_value(source_ref, "socket")
    if expected_output is not None:
        actual_output = _edge_output_name(edge, source_node)
        if actual_output is not None and actual_output != expected_output:
            return False
        if actual_output is None and len(source_node.output_slots if source_node else ()) != 1:
            return False

    expected_input = (
        input_name
        or _socket_value(target_ref, "input_name")
        or _socket_value(target_ref, "socket")
    )
    if expected_input is not None:
        actual_input = _edge_input_name(edge, target_node)
        if actual_input != expected_input:
            return False
    return True


def _has_direct_edge(
    evidence: GraphEvidence,
    source_ref: SocketRef | Mapping[str, Any] | None,
    target_ref: SocketRef | Mapping[str, Any] | None,
    *,
    input_name: str | None = None,
) -> bool:
    nodes_by_id = _node_by_id(evidence)
    for edge in evidence.edges:
        source_node = nodes_by_id.get(edge.origin_node)
        target_node = nodes_by_id.get(edge.target_node)
        if source_node is None or target_node is None:
            continue
        if not _node_matches_ref(source_node, source_ref):
            continue
        if not _node_matches_ref(target_node, target_ref):
            continue
        if _edge_matches_socket_names(
            edge,
            source_node=source_node,
            target_node=target_node,
            source_ref=source_ref,
            target_ref=target_ref,
            input_name=input_name,
        ):
            return True
    return False


def _reachable_nodes(
    evidence: GraphEvidence,
    source_ids: set[int | str],
) -> set[int | str]:
    adjacency: dict[int | str, list[int | str]] = {}
    for edge in evidence.edges:
        adjacency.setdefault(edge.origin_node, []).append(edge.target_node)
    visited: set[int | str] = set()
    queue = list(source_ids)
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for next_id in adjacency.get(current, ()):
            if next_id not in visited:
                queue.append(next_id)
    return visited


def _has_reachable_path(
    evidence: GraphEvidence,
    source_ref: SocketRef | Mapping[str, Any] | None,
    target_ref: SocketRef | Mapping[str, Any] | None,
) -> bool:
    source_nodes = _nodes_matching(evidence, ref=source_ref)
    target_nodes = _nodes_matching(evidence, ref=target_ref)
    if not source_nodes or not target_nodes:
        return False
    reachable = _reachable_nodes(evidence, {node.node_id for node in source_nodes})
    return any(node.node_id in reachable for node in target_nodes)


def _is_terminal_class(class_type: str) -> bool:
    lowered = class_type.casefold()
    compact = _normalise_token(class_type)
    explicit = {
        "SaveImage",
        "PreviewImage",
        "SaveVideo",
        "VHS_VideoCombine",
        "CreateVideo",
        "SaveAudio",
        "SaveAudioMP3",
        "PreviewAudio",
    }
    return (
        class_type in explicit
        or lowered.startswith(("save", "preview", "create"))
        or "vhsvideocombine" in compact
    )


def _terminal_domain(node: NodeEvidence) -> str | None:
    compact = _normalise_token(node.class_type)
    if "audio" in compact:
        return "AUDIO"
    if "video" in compact or "vhs" in compact:
        return "VIDEO"
    if "image" in compact:
        return "IMAGE"
    return None


def _linked_input_slots(node: NodeEvidence) -> tuple[str, ...]:
    return tuple(slot.name for slot in node.input_slots if slot.link_id is not None)


def _values_for_node(node: NodeEvidence, field_names: tuple[str, ...]) -> tuple[Any, ...]:
    if not field_names:
        return tuple(widget.value for widget in node.widgets)
    wanted = {str(name) for name in field_names}
    values: list[Any] = []
    for widget in node.widgets:
        if widget.name in wanted or f"widget_{widget.index}" in wanted:
            values.append(widget.value)
    return tuple(values)


def _expected_value_and_fields(
    condition: PlanCondition | Mapping[str, Any],
    *,
    default_fields: tuple[str, ...] = (),
) -> tuple[Any, tuple[str, ...]]:
    expected = _condition_value(condition, "expected")
    details = _condition_details(condition)
    field_names: list[str] = []
    explicit_input = _condition_value(condition, "input_name")
    if explicit_input is not None:
        field_names.append(str(explicit_input))
    for key in ("field", "input", "widget", "value_name"):
        value = details.get(key)
        if isinstance(value, str):
            field_names.append(value)
    fields = details.get("fields") or details.get("inputs") or details.get("widgets")
    if isinstance(fields, (list, tuple)):
        field_names.extend(str(item) for item in fields)
    if isinstance(expected, Mapping):
        for key in ("field", "input", "widget", "value_name"):
            value = expected.get(key)
            if isinstance(value, str):
                field_names.append(value)
        expected = expected.get("value", expected.get("equals", expected.get("expected")))
    if not field_names:
        field_names.extend(default_fields)
    return expected, tuple(dict.fromkeys(field_names))


def _value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        if "equals" in expected:
            return _value_matches(actual, expected["equals"])
        if "value" in expected:
            return _value_matches(actual, expected["value"])
        if "min" in expected or "max" in expected:
            try:
                numeric = float(actual)
            except (TypeError, ValueError):
                return False
            min_value = expected.get("min")
            max_value = expected.get("max")
            if min_value is not None and numeric < float(min_value):
                return False
            if max_value is not None and numeric > float(max_value):
                return False
            return True
    if isinstance(actual, float) and isinstance(expected, int) and actual == expected:
        return True
    if isinstance(actual, int) and isinstance(expected, float) and actual == expected:
        return True
    return actual == expected


def _required_class_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    details = _condition_details(condition)
    expected = (
        _condition_value(condition, "class_type")
        or _condition_value(condition, "expected")
        or details.get("class_type")
        or details.get("classes")
    )
    if expected is None:
        return False
    min_count = details.get("min_count", 1)
    try:
        required_count = int(min_count)
    except (TypeError, ValueError):
        required_count = 1
    return len(_nodes_matching(evidence, class_type=expected)) >= required_count


def _required_value_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    expected, fields = _expected_value_and_fields(condition)
    if expected is None:
        return False
    source_ref = _as_socket_ref(_condition_value(condition, "source"))
    class_type = _condition_value(condition, "class_type") or _condition_details(condition).get("class_type")
    nodes = _nodes_matching(evidence, ref=source_ref, class_type=class_type)
    for node in nodes:
        for value in _values_for_node(node, fields):
            if _value_matches(value, expected):
                return True
    return False


def _terminal_consumes_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    source_ref = _as_socket_ref(_condition_value(condition, "source"))
    target_ref = _as_socket_ref(_condition_value(condition, "target"))
    class_type = _condition_value(condition, "class_type") or _condition_details(condition).get("class_type")
    target_nodes = _nodes_matching(evidence, ref=target_ref, class_type=class_type)
    terminals = tuple(node for node in target_nodes if _is_terminal_class(node.class_type))
    if not terminals and target_ref is None and class_type is None:
        terminals = tuple(node for node in evidence.nodes if _is_terminal_class(node.class_type))
    if not terminals:
        return False
    input_name = _condition_value(condition, "input_name")
    if input_name is not None:
        terminals = tuple(
            node for node in terminals if str(input_name) in _linked_input_slots(node)
        )
        if not terminals:
            return False
    if source_ref is None:
        return any(_linked_input_slots(node) for node in terminals)
    source_nodes = _nodes_matching(evidence, ref=source_ref)
    if not source_nodes:
        return False
    reachable = _reachable_nodes(evidence, {node.node_id for node in source_nodes})
    return any(node.node_id in reachable for node in terminals)


def _active_output_domain_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    expected = _condition_value(condition, "expected") or _condition_details(condition).get("domain")
    if expected is None:
        return False
    expected_domain = str(expected).upper()
    terminal_nodes = tuple(node for node in evidence.nodes if _is_terminal_class(node.class_type))
    for node in terminal_nodes:
        terminal_domain = _terminal_domain(node)
        if terminal_domain is not None:
            if terminal_domain == expected_domain and _linked_input_slots(node):
                return True
            continue
        for slot in (*node.input_slots, *node.output_slots):
            if str(slot.name).upper() == expected_domain:
                return True
    for edge in evidence.edges:
        if edge.link_type is not None and str(edge.link_type).upper() == expected_domain:
            target = _node_by_id(evidence).get(edge.target_node)
            if (
                target is not None
                and _is_terminal_class(target.class_type)
                and _terminal_domain(target) is None
            ):
                return True
    return False


def _unconsumed_functional_outputs_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    details = _condition_details(condition)
    expected = _condition_value(condition, "expected")
    max_count = details.get("max_count", expected if isinstance(expected, int) else 0)
    try:
        allowed = int(max_count)
    except (TypeError, ValueError):
        allowed = 0
    class_type = _condition_value(condition, "class_type") or details.get("class_type") or details.get("classes")
    source_ref = _as_socket_ref(_condition_value(condition, "source"))
    nodes = _nodes_matching(evidence, ref=source_ref, class_type=class_type)
    outgoing = {edge.origin_node for edge in evidence.edges}
    unconsumed = [
        node
        for node in nodes
        if node.output_slots and node.node_id not in outgoing and not _is_terminal_class(node.class_type)
    ]
    return len(unconsumed) <= allowed


_FRAME_COUNT_FIELDS: tuple[str, ...] = (
    "amount",
    "batch_size",
    "context_length",
    "frame_count",
    "frame_load_cap",
    "frames",
    "frames_number",
    "length",
    "num_frames",
)


def _batch_frame_count_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    expected, fields = _expected_value_and_fields(
        condition,
        default_fields=_FRAME_COUNT_FIELDS,
    )
    if expected is None:
        return False
    source_ref = _as_socket_ref(_condition_value(condition, "source"))
    target_ref = _as_socket_ref(_condition_value(condition, "target"))
    class_type = _condition_value(condition, "class_type") or _condition_details(condition).get("class_type")
    nodes = _nodes_matching(evidence, ref=source_ref, class_type=class_type)
    for node in nodes:
        for value in _values_for_node(node, fields):
            if not _value_matches(value, expected):
                continue
            if target_ref is None:
                return True
            target_nodes = _nodes_matching(evidence, ref=target_ref)
            if not target_nodes:
                return False
            reachable = _reachable_nodes(evidence, {node.node_id})
            if any(target.node_id in reachable for target in target_nodes):
                return True
    return False


def _condition_satisfied(
    evidence: GraphEvidence,
    condition: PlanCondition | Mapping[str, Any],
) -> bool:
    kind = str(_condition_value(condition, "kind") or "")
    source_ref = _as_socket_ref(_condition_value(condition, "source"))
    target_ref = _as_socket_ref(_condition_value(condition, "target"))
    input_name = _condition_value(condition, "input_name")
    if kind == "required_class":
        return _required_class_satisfied(evidence, condition)
    if kind == "required_value":
        return _required_value_satisfied(evidence, condition)
    if kind == "direct_edge":
        if source_ref is None or target_ref is None:
            return False
        return _has_direct_edge(evidence, source_ref, target_ref, input_name=input_name)
    if kind == "reachable_path":
        if source_ref is None or target_ref is None:
            return False
        return _has_reachable_path(evidence, source_ref, target_ref)
    if kind == "direct_edge_or_reachable_path":
        if source_ref is None or target_ref is None:
            return False
        return _has_direct_edge(evidence, source_ref, target_ref, input_name=input_name) or _has_reachable_path(
            evidence,
            source_ref,
            target_ref,
        )
    if kind == "terminal_consumes":
        return _terminal_consumes_satisfied(evidence, condition)
    if kind == "active_output_domain":
        return _active_output_domain_satisfied(evidence, condition)
    if kind == "unconsumed_functional_outputs":
        return _unconsumed_functional_outputs_satisfied(evidence, condition)
    if kind in {"batch_frame_count", "value_or_path_count"}:
        return _batch_frame_count_satisfied(evidence, condition)
    return False


def _failure_record(
    condition: PlanCondition | Mapping[str, Any],
    *,
    message: str,
    severity: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    condition_id = _condition_id(condition)
    return _omit_none({
        "condition_id": condition_id,
        "kind": _condition_value(condition, "kind"),
        "severity": severity or ("required" if _condition_is_required(condition) else "advisory"),
        "message": message,
        "condition": _condition_to_dict(condition),
        "evidence": _thaw_jsonish(evidence or {}),
    })


def _condition_message(condition: PlanCondition | Mapping[str, Any], default: str) -> str:
    return str(_condition_value(condition, "message") or default)


def _step_conditions(step: PlanStep | Mapping[str, Any]) -> tuple[PlanCondition | Mapping[str, Any], ...]:
    raw_conditions = _mapping_value(step, "conditions") or ()
    conditions: list[PlanCondition | Mapping[str, Any]] = list(raw_conditions)
    class_type = _mapping_value(step, "class_type")
    if class_type and not conditions:
        step_id = str(_mapping_value(step, "step_id") or _mapping_value(step, "id") or "unknown_step")
        conditions.append(
            PlanCondition(
                condition_id=f"{step_id}.required_class",
                kind="required_class",
                criticality=str(_mapping_value(step, "criticality") or "required"),
                class_type=str(class_type),
                message=f"Required step class {class_type!r} is missing.",
            )
        )
    return tuple(conditions)


def _plan_conditions(plan: ExecutionPlan | Mapping[str, Any]) -> tuple[PlanCondition | Mapping[str, Any], ...]:
    conditions: list[PlanCondition | Mapping[str, Any]] = []
    for key in ("done_conditions", "active_path_conditions"):
        conditions.extend(_mapping_value(plan, key) or ())
    for step in _mapping_value(plan, "required_steps") or ():
        conditions.extend(_step_conditions(step))
    return tuple(conditions)


def _blocked_if_conditions(plan: ExecutionPlan | Mapping[str, Any]) -> tuple[PlanCondition | Mapping[str, Any], ...]:
    return tuple(_mapping_value(plan, "blocked_if") or ())


def _version_failure_condition(
    *,
    condition_id: str,
    contract_version: Any,
    supported_versions: tuple[str, ...],
    reason: str | None = None,
) -> dict[str, Any]:
    message = (
        f"Unsupported contract version {contract_version!r}; "
        f"supported versions: {', '.join(supported_versions)}."
    )
    if reason:
        message = f"{message} {reason}"
    return {
        "condition_id": condition_id,
        "severity": "critical",
        "message": message,
    }


def fail_closed_evaluation_for_plan_version(
    plan: ExecutionPlan | Mapping[str, Any],
    *,
    candidate_graph_hash: str | None = None,
    reason: str | None = None,
) -> PlanEvaluation:
    """Return a blocking evaluation for an unsupported execution-plan version."""

    version = _mapping_value(plan, "contract_version")
    return PlanEvaluation(
        plan_id=str(_mapping_value(plan, "plan_id") or "unknown"),
        ok=False,
        blocking=True,
        source_graph_hash=_mapping_value(plan, "source_graph_hash"),
        candidate_graph_hash=candidate_graph_hash or _mapping_value(plan, "candidate_graph_hash"),
        selected_precedent_id=_mapping_value(plan, "selected_precedent_id"),
        step_status=(),
        failed_conditions=(
            _version_failure_condition(
                condition_id=UNKNOWN_PLAN_VERSION_CONDITION_ID,
                contract_version=version,
                supported_versions=SUPPORTED_EXECUTION_PLAN_CONTRACT_VERSIONS,
                reason=reason,
            ),
        ),
        feedback="plan evaluation blocked: unsupported execution plan contract version.",
        schema_provenance=_mapping_value(plan, "schema_provenance") or {},
        runtime_provenance=_mapping_value(plan, "runtime_provenance") or {},
    )


def fail_closed_evaluation_for_evaluation_version(
    evaluation: PlanEvaluation | Mapping[str, Any],
    *,
    reason: str | None = None,
) -> PlanEvaluation:
    """Return a current-version blocking result for an unsupported evaluation."""

    version = _mapping_value(evaluation, "contract_version")
    return PlanEvaluation(
        plan_id=str(_mapping_value(evaluation, "plan_id") or "unknown"),
        ok=False,
        blocking=True,
        source_graph_hash=_mapping_value(evaluation, "source_graph_hash"),
        candidate_graph_hash=_mapping_value(evaluation, "candidate_graph_hash"),
        selected_precedent_id=_mapping_value(evaluation, "selected_precedent_id"),
        step_status=_mapping_value(evaluation, "step_status") or (),
        failed_conditions=(
            _version_failure_condition(
                condition_id=UNKNOWN_EVALUATION_VERSION_CONDITION_ID,
                contract_version=version,
                supported_versions=SUPPORTED_PLAN_EVALUATION_CONTRACT_VERSIONS,
                reason=reason,
            ),
        ),
        feedback="plan evaluation blocked: unsupported plan evaluation contract version.",
        schema_provenance=_mapping_value(evaluation, "schema_provenance") or {},
        runtime_provenance=_mapping_value(evaluation, "runtime_provenance") or {},
    )


def fail_closed_if_unsupported_plan_version(
    plan: ExecutionPlan | Mapping[str, Any],
    *,
    candidate_graph_hash: str | None = None,
) -> PlanEvaluation | None:
    """Return ``None`` for supported plans, else a blocking evaluation."""

    if is_supported_execution_plan_version(_mapping_value(plan, "contract_version")):
        return None
    return fail_closed_evaluation_for_plan_version(
        plan,
        candidate_graph_hash=candidate_graph_hash,
    )


def fail_closed_if_unsupported_evaluation_version(
    evaluation: PlanEvaluation | Mapping[str, Any],
) -> PlanEvaluation:
    """Return the evaluation when supported, otherwise a blocking replacement."""

    if is_supported_plan_evaluation_version(_mapping_value(evaluation, "contract_version")):
        if isinstance(evaluation, PlanEvaluation):
            return evaluation
        return PlanEvaluation(
            plan_id=str(_mapping_value(evaluation, "plan_id") or "unknown"),
            ok=bool(_mapping_value(evaluation, "ok")),
            blocking=bool(_mapping_value(evaluation, "blocking")),
            source_graph_hash=_mapping_value(evaluation, "source_graph_hash"),
            candidate_graph_hash=_mapping_value(evaluation, "candidate_graph_hash"),
            selected_precedent_id=_mapping_value(evaluation, "selected_precedent_id"),
            step_status=tuple(_mapping_value(evaluation, "step_status") or ()),
            failed_conditions=tuple(_mapping_value(evaluation, "failed_conditions") or ()),
            feedback=str(_mapping_value(evaluation, "feedback") or ""),
            schema_provenance=_mapping_value(evaluation, "schema_provenance") or {},
            runtime_provenance=_mapping_value(evaluation, "runtime_provenance") or {},
            contract_version=str(_mapping_value(evaluation, "contract_version")),
        )
    return fail_closed_evaluation_for_evaluation_version(evaluation)


def evaluate_execution_plan(
    graph: Mapping[str, Any] | None,
    plan: ExecutionPlan | Mapping[str, Any],
    *,
    candidate_graph_hash: str | None = None,
) -> PlanEvaluation:
    """Evaluate a candidate graph against deterministic execution-plan conditions.

    The evaluator is intentionally pure and evidence-driven: topology, values,
    terminals, and frame counts are read from :func:`inspect_graph`, while graph
    identity uses the same structural hash projection as agent session state.
    """

    unsupported = fail_closed_if_unsupported_plan_version(
        plan,
        candidate_graph_hash=candidate_graph_hash,
    )
    if unsupported is not None:
        return unsupported

    evidence = inspect_graph(dict(graph) if isinstance(graph, Mapping) else None)
    computed_graph_hash = structural_graph_hash(graph)
    actual_graph_hash = candidate_graph_hash or computed_graph_hash
    failed_conditions: list[dict[str, Any]] = []

    if isinstance(candidate_graph_hash, str) and computed_graph_hash is not None:
        if candidate_graph_hash != computed_graph_hash:
            failed_conditions.append(
                {
                    "condition_id": "candidate_structural_graph_hash",
                    "kind": "candidate_graph_hash",
                    "severity": "critical",
                    "message": "Candidate graph hash does not match structural graph evidence.",
                    "evidence": {
                        "candidate_graph_hash": candidate_graph_hash,
                        "computed_structural_graph_hash": computed_graph_hash,
                        "structural_projection_version": STRUCTURAL_PROJECTION_VERSION,
                    },
                }
            )

    expected_candidate_hash = _mapping_value(plan, "candidate_graph_hash")
    if isinstance(expected_candidate_hash, str) and actual_graph_hash != expected_candidate_hash:
        failed_conditions.append(
            {
                "condition_id": "plan_candidate_structural_graph_hash",
                "kind": "candidate_graph_hash",
                "severity": "critical",
                "message": "Plan candidate graph hash does not match the evaluated graph.",
                "evidence": {
                    "expected_candidate_graph_hash": expected_candidate_hash,
                    "candidate_graph_hash": actual_graph_hash,
                    "computed_structural_graph_hash": computed_graph_hash,
                    "structural_projection_version": STRUCTURAL_PROJECTION_VERSION,
                },
            }
        )

    step_status: list[dict[str, Any]] = []
    condition_status_by_id: dict[str, bool] = {}

    for condition in _plan_conditions(plan):
        condition_id = _condition_id(condition)
        kind = str(_condition_value(condition, "kind") or "")
        if kind not in SUPPORTED_CONDITION_KINDS:
            condition_status_by_id[condition_id] = False
            failed_conditions.append(
                _failure_record(
                    condition,
                    severity="critical",
                    message=f"Unsupported execution-plan condition kind {kind!r}; failing closed.",
                    evidence={"supported_kinds": SUPPORTED_CONDITION_KINDS},
                )
            )
            continue
        satisfied = _condition_satisfied(evidence, condition)
        condition_status_by_id[condition_id] = satisfied
        if not satisfied:
            failed_conditions.append(
                _failure_record(
                    condition,
                    message=_condition_message(condition, "Required execution-plan condition is not satisfied."),
                    evidence={
                        "node_count": evidence.node_count,
                        "edge_count": len(evidence.edges),
                    },
                )
            )

    for condition in _blocked_if_conditions(plan):
        condition_id = _condition_id(condition)
        kind = str(_condition_value(condition, "kind") or "")
        if kind not in SUPPORTED_CONDITION_KINDS:
            condition_status_by_id[condition_id] = False
            failed_conditions.append(
                _failure_record(
                    condition,
                    severity="critical",
                    message=f"Unsupported blocked-if condition kind {kind!r}; failing closed.",
                    evidence={"supported_kinds": SUPPORTED_CONDITION_KINDS},
                )
            )
            continue
        triggered = _condition_satisfied(evidence, condition)
        condition_status_by_id[condition_id] = not triggered
        if triggered:
            failed_conditions.append(
                _failure_record(
                    condition,
                    severity="critical" if _condition_is_required(condition) else "advisory",
                    message=_condition_message(condition, "Blocked-if execution-plan condition is present."),
                    evidence={
                        "node_count": evidence.node_count,
                        "edge_count": len(evidence.edges),
                    },
                )
            )

    for step in _mapping_value(plan, "required_steps") or ():
        step_id = str(_mapping_value(step, "step_id") or _mapping_value(step, "id") or "unknown_step")
        conditions = _step_conditions(step)
        failed_ids = tuple(
            _condition_id(condition)
            for condition in conditions
            if not condition_status_by_id.get(_condition_id(condition), False)
        )
        if not conditions:
            status = str(_mapping_value(step, "status") or "not_evaluated")
        elif failed_ids:
            status = "missing" if _mapping_value(step, "class_type") else "failed"
        else:
            status = "satisfied"
        step_status.append(
            _omit_none({
                "step_id": step_id,
                "kind": _mapping_value(step, "kind"),
                "criticality": _mapping_value(step, "criticality") or "required",
                "status": status,
                "failed_condition_ids": list(failed_ids) if failed_ids else None,
            })
        )

    blocking = any(str(item.get("severity")) in {"critical", "required"} for item in failed_conditions)
    ok = not failed_conditions
    if failed_conditions:
        failed_ids = ", ".join(str(item.get("condition_id")) for item in failed_conditions)
        feedback = f"plan evaluation failed: {failed_ids}."
    else:
        feedback = "plan evaluation passed."

    runtime_provenance = {
        "evaluator": "evaluate_execution_plan",
        "graph_inspection": {
            "node_count": evidence.node_count,
            "edge_count": len(evidence.edges),
        },
        "structural_graph_hash_version": STRUCTURAL_PROJECTION_VERSION,
    }
    plan_runtime = _mapping_value(plan, "runtime_provenance")
    if isinstance(plan_runtime, Mapping):
        runtime_provenance = {
            **_thaw_jsonish(plan_runtime),
            **runtime_provenance,
        }

    return PlanEvaluation(
        plan_id=str(_mapping_value(plan, "plan_id") or "unknown"),
        ok=ok,
        blocking=blocking,
        source_graph_hash=_mapping_value(plan, "source_graph_hash"),
        candidate_graph_hash=actual_graph_hash,
        selected_precedent_id=_mapping_value(plan, "selected_precedent_id"),
        step_status=tuple(step_status),
        failed_conditions=tuple(failed_conditions),
        feedback=feedback,
        schema_provenance=_mapping_value(plan, "schema_provenance") or {},
        runtime_provenance=runtime_provenance,
    )


__all__ = (
    "CURRENT_EXECUTION_PLAN_VERSION",
    "CURRENT_PLAN_EVALUATION_VERSION",
    "EXECUTION_PLAN_CONTRACT_VERSION",
    "OPTIONAL_CRITICALITIES",
    "PLAN_CRITICALITIES",
    "PLAN_EVALUATION_CONTRACT_VERSION",
    "REQUIRED_CRITICALITIES",
    "STEP_STATUSES",
    "SUPPORTED_CONDITION_KINDS",
    "SUPPORTED_EXECUTION_PLAN_CONTRACT_VERSIONS",
    "SUPPORTED_PLAN_EVALUATION_CONTRACT_VERSIONS",
    "UNKNOWN_EVALUATION_VERSION_CONDITION_ID",
    "UNKNOWN_PLAN_VERSION_CONDITION_ID",
    "ExecutionPlan",
    "PlanCondition",
    "PlanEvaluation",
    "PlanStep",
    "RoleBinding",
    "SocketRef",
    "execution_plan_version_status",
    "fail_closed_evaluation_for_evaluation_version",
    "fail_closed_evaluation_for_plan_version",
    "fail_closed_if_unsupported_evaluation_version",
    "fail_closed_if_unsupported_plan_version",
    "evaluate_execution_plan",
    "is_supported_execution_plan_version",
    "is_supported_plan_evaluation_version",
    "plan_evaluation_version_status",
)
