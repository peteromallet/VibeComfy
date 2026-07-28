from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence
import ast
import re

from .ledger import EditLedger, ScopeState
from .ops import AddNodeOp, EditOp, LinkSourceRef, LinkTargetRef, NodeFieldTarget, NodeTarget
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import ResolutionContext, to_port_issues
from vibecomfy.schema import InputSpec

VALUE_DEFAULT_FIELDS_MARKER = "__vibecomfy_value_default_fields__"


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return deepcopy(value)


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return deepcopy(value)


def _request_match_is_negated(text: str, start: int) -> bool:
    clause_start = max(
        text.rfind(separator, 0, start)
        for separator in (".", "!", "?", ";", "\n")
    )
    clause_prefix = text[clause_start + 1:start].casefold()
    return re.search(
        r"\b(?:not|never|without|avoid|cannot|can't|won't|don't)\b|"
        r"\bdo\s+not\b",
        clause_prefix,
    ) is not None


@dataclass(frozen=True, slots=True)
class ValueDefaultBinding:
    class_type: str
    source_instance_id: str
    role_label: str
    canonical_field: str
    value: Any
    provenance: str
    confidence: str
    selection_status: str = "ambiguous"
    name_resolution_status: str = "canonical"
    conflict_status: str = "unique_value"
    source_index: int | None = None
    source_shape: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze_value(self.value))

    def thawed_value(self) -> Any:
        return _thaw_value(self.value)


@dataclass(frozen=True, slots=True)
class ValueUserOverride:
    class_type: str
    canonical_field: str
    value: Any
    role_label: str = ""
    source_instance_id: str = ""
    basis: str = "explicit_user_value"

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze_value(self.value))

    def thawed_value(self) -> Any:
        return _thaw_value(self.value)


@dataclass(frozen=True, slots=True)
class ValueDefaultReceipt:
    class_type: str
    canonical_field: str
    old_value: Any
    new_value: Any
    basis: str
    provenance: str
    validation_result: str
    source_instance_id: str = ""
    role_label: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "old_value", _freeze_value(self.old_value))
        object.__setattr__(self, "new_value", _freeze_value(self.new_value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_type": self.class_type,
            "field": self.canonical_field,
            "old_value": _thaw_value(self.old_value),
            "new_value": _thaw_value(self.new_value),
            "basis": self.basis,
            "provenance": self.provenance,
            "validation_result": self.validation_result,
            "source_instance_id": self.source_instance_id,
            "role_label": self.role_label,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ProtectedValueDefaults:
    scope_path: str
    uid: str
    class_type: str
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValueDefaultContext:
    """Immutable authority and source-prior context for constructor binding."""

    bindings: tuple[ValueDefaultBinding, ...] = ()
    user_overrides: tuple[ValueUserOverride, ...] = ()
    selected_instances: tuple[tuple[str, str], ...] = ()
    consumed_instances: tuple[tuple[str, str], ...] = ()
    protected_nodes: tuple[ProtectedValueDefaults, ...] = ()
    user_request: str = ""
    active: bool = True
    allowed_provenance: frozenset[str] = frozenset({"source_template"})

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", tuple(self.bindings))
        object.__setattr__(self, "user_overrides", tuple(self.user_overrides))
        object.__setattr__(
            self,
            "selected_instances",
            tuple((str(class_type), str(instance_id)) for class_type, instance_id in self.selected_instances),
        )
        object.__setattr__(
            self,
            "consumed_instances",
            tuple((str(class_type), str(instance_id)) for class_type, instance_id in self.consumed_instances),
        )
        object.__setattr__(self, "protected_nodes", tuple(self.protected_nodes))
        object.__setattr__(
            self,
            "allowed_provenance",
            frozenset(str(value) for value in self.allowed_provenance),
        )

    @classmethod
    def from_precedent_slices(
        cls,
        precedent_slices: Sequence[Mapping[str, Any]] = (),
        *,
        adaptation_plan: Mapping[str, Any] | None = None,
        user_overrides: Any = None,
        user_request: str = "",
    ) -> "ValueDefaultContext":
        bindings: list[ValueDefaultBinding] = []
        for slice_data in precedent_slices:
            envelope = slice_data.get("binding_envelope")
            if not isinstance(envelope, Mapping):
                continue
            class_type = str(envelope.get("class_type") or slice_data.get("source_class_type") or "")
            selector = envelope.get("selector")
            selector = selector if isinstance(selector, Mapping) else {}
            source_instance_id = str(selector.get("source_instance_id") or "")
            role_label = str(selector.get("role_label") or "")
            selection_status = str(selector.get("selection_status") or "ambiguous")
            fields = envelope.get("fields")
            if not isinstance(fields, (list, tuple)):
                continue
            for field_record in fields:
                if not isinstance(field_record, Mapping) or "value" not in field_record:
                    continue
                bindings.append(ValueDefaultBinding(
                    class_type=class_type,
                    source_instance_id=source_instance_id,
                    role_label=role_label,
                    canonical_field=str(field_record.get("canonical_field") or ""),
                    value=field_record["value"],
                    provenance=str(field_record.get("provenance") or ""),
                    confidence=str(field_record.get("confidence") or ""),
                    selection_status=selection_status,
                    name_resolution_status=str(field_record.get("name_resolution_status") or ""),
                    conflict_status=str(field_record.get("conflict_status") or ""),
                    source_index=(
                        int(field_record["source_index"])
                        if isinstance(field_record.get("source_index"), int)
                        else None
                    ),
                    source_shape=(
                        int(field_record["source_shape"])
                        if isinstance(field_record.get("source_shape"), int)
                        else None
                    ),
                ))

        selected_instances: list[tuple[str, str]] = []
        selected_slice = adaptation_plan.get("selected_slice") if isinstance(adaptation_plan, Mapping) else None
        if isinstance(selected_slice, Mapping):
            selected_class = str(selected_slice.get("source_class_type") or "")
            node_ids = selected_slice.get("node_ids")
            if isinstance(node_ids, (list, tuple)):
                selected_instances.extend(
                    (selected_class, str(node_id))
                    for node_id in node_ids
                    if selected_class and str(node_id)
                )

        overrides: list[ValueUserOverride] = []
        if isinstance(user_overrides, Mapping):
            for class_type, fields in user_overrides.items():
                if not isinstance(fields, Mapping):
                    continue
                overrides.extend(
                    ValueUserOverride(str(class_type), str(field_name), value)
                    for field_name, value in fields.items()
                )
        elif isinstance(user_overrides, (list, tuple)):
            for record in user_overrides:
                if not isinstance(record, Mapping) or "value" not in record:
                    continue
                overrides.append(ValueUserOverride(
                    class_type=str(record.get("class_type") or ""),
                    canonical_field=str(record.get("field") or record.get("canonical_field") or ""),
                    value=record["value"],
                    role_label=str(record.get("role_label") or ""),
                    source_instance_id=str(record.get("source_instance_id") or ""),
                ))
        return cls(
            bindings=tuple(bindings),
            user_overrides=tuple(overrides),
            selected_instances=tuple(selected_instances),
            user_request=str(user_request or ""),
        )

    def selected_bindings(self, class_type: str, canonical_field: str) -> tuple[ValueDefaultBinding, ...]:
        candidates = tuple(
            binding
            for binding in self.bindings
            if binding.class_type == class_type
            and binding.canonical_field == canonical_field
            and binding.provenance in self.allowed_provenance
            and binding.confidence == "high"
            and binding.name_resolution_status == "canonical"
            and (binding.class_type, binding.source_instance_id)
            not in self.consumed_instances
        )
        exact_selected = {
            instance_id
            for selected_class, instance_id in self.selected_instances
            if selected_class == class_type
            and (selected_class, instance_id) not in self.consumed_instances
        }
        if exact_selected:
            if len(exact_selected) != 1:
                return ()
            return tuple(
                binding for binding in candidates
                if binding.source_instance_id in exact_selected
            )
        return tuple(
            binding for binding in candidates
            if binding.selection_status == "unique"
            and binding.conflict_status != "conflicting"
        )

    def explicit_override(self, class_type: str, canonical_field: str) -> ValueUserOverride | None:
        matches = tuple(
            override
            for override in self.user_overrides
            if override.class_type == class_type
            and override.canonical_field == canonical_field
        )
        return matches[0] if len(matches) == 1 else None

    def explicit_request_override(
        self,
        class_type: str,
        canonical_field: str,
        spec: InputSpec | None,
    ) -> ValueUserOverride | None:
        """Conservatively extract an exact field/value from the user request.

        This intentionally recognizes literals only. Phrases such as "more
        steps" or "a better sampler" cannot mint authority.
        """
        text = self.user_request
        if not text.strip():
            return None
        field_words = re.escape(canonical_field.replace("_", " "))
        field_pattern = rf"(?:{field_words}|{re.escape(canonical_field)})"
        literal_pattern = (
            r"(?:\"[^\"\n]*\"|'[^'\n]*'|"
            r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)|true|false|none|null)"
        )
        patterns = (
            rf"\b(?:use|set|with|at|make)\s+(?:the\s+)?{field_pattern}\b"
            rf"\s*(?:=|:|to|is|of)?\s*({literal_pattern})",
            rf"\b{field_pattern}\b\s*(?:=|:|to)\s*({literal_pattern})",
            rf"\b(?:use|set|with|at)\s+({literal_pattern})\s+{field_pattern}s?\b",
        )
        raw_value = None
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match is not None:
                if _request_match_is_negated(text, match.start()):
                    continue
                raw_value = match.group(1)
                break

        choices = list(getattr(spec, "choices", None) or ())
        if raw_value is None and choices:
            for choice in choices:
                if not isinstance(choice, str):
                    continue
                choice_pattern = re.escape(choice)
                choice_matches = (
                    re.search(
                        rf"\b{field_pattern}\b\s*(?:=|:|to|is|of)?\s*{choice_pattern}\b",
                        text,
                        flags=re.IGNORECASE,
                    ),
                    re.search(
                        rf"\b(?:use|set|with)\s+{choice_pattern}\s+{field_pattern}\b",
                        text,
                        flags=re.IGNORECASE,
                    ),
                )
                if any(
                    match is not None
                    and not _request_match_is_negated(text, match.start())
                    for match in choice_matches
                ):
                    return ValueUserOverride(
                        class_type,
                        canonical_field,
                        choice,
                    )
            return None
        if raw_value is None:
            return None

        normalized = raw_value.strip()
        lowered = normalized.casefold()
        if lowered in {"true", "false"}:
            value: Any = lowered == "true"
        elif lowered in {"none", "null"}:
            value = None
        else:
            try:
                value = ast.literal_eval(normalized)
            except (SyntaxError, ValueError):
                return None
        return ValueUserOverride(class_type, canonical_field, value)

    def protects(self, scope_path: str, uid: str, class_type: str, canonical_field: str) -> bool:
        return any(
            protected.scope_path == scope_path
            and protected.uid == uid
            and protected.class_type == class_type
            and canonical_field in protected.fields
            for protected in self.protected_nodes
        )

    def protect_node(
        self,
        *,
        scope_path: str,
        uid: str,
        class_type: str,
        fields: Sequence[str],
        source_instance_ids: Sequence[str] = (),
    ) -> "ValueDefaultContext":
        protected = ProtectedValueDefaults(
            scope_path=scope_path,
            uid=uid,
            class_type=class_type,
            fields=tuple(dict.fromkeys(str(field) for field in fields)),
        )
        consumed = tuple(
            (class_type, str(instance_id))
            for instance_id in source_instance_ids
            if str(instance_id)
        )
        return replace(
            self,
            protected_nodes=(*self.protected_nodes, protected),
            consumed_instances=tuple(dict.fromkeys((*self.consumed_instances, *consumed))),
        )

    def with_graph_protections(self, raw_ui_json: Mapping[str, Any]) -> "ValueDefaultContext":
        """Rehydrate persisted binding protection for a later edit session."""
        context = self
        ledger = EditLedger.ingest(raw_ui_json)
        for scope_path, scope in ledger.scopes.items():
            nodes = scope.graph.get("nodes")
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                properties = node.get("properties")
                protected_fields = (
                    properties.get("vibecomfy_value_default_fields")
                    if isinstance(properties, Mapping)
                    else None
                )
                if not isinstance(protected_fields, list):
                    continue
                uid = properties.get("vibecomfy_uid")
                class_type = node.get("type") or node.get("class_type")
                fields = tuple(
                    str(field)
                    for field in protected_fields
                    if isinstance(field, str) and field
                )
                matching_selected = tuple(
                    instance_id
                    for selected_class, instance_id in context.selected_instances
                    if selected_class == class_type
                )
                if isinstance(uid, str) and isinstance(class_type, str) and fields:
                    context = context.protect_node(
                        scope_path=scope_path,
                        uid=uid,
                        class_type=class_type,
                        fields=fields,
                        source_instance_ids=(
                            matching_selected if len(matching_selected) == 1 else ()
                        ),
                    )
        return context


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    detail: Mapping[str, Any] | None = None,
) -> PortIssue:
    return PortIssue(code=code, message=message, severity=severity, detail=dict(detail or {}))


_ctx = ResolutionContext()


_RESOLUTION_CODE_REMAP: dict[str, str] = {"unknown_target": "unknown_node_target"}


def _endpoint_port_issues(result: Any) -> list[PortIssue]:
    """Convert ResolveResult issues for endpoint resolvers, remapping uid error codes."""
    issues = to_port_issues(result)
    return [
        _issue(
            _RESOLUTION_CODE_REMAP.get(i.code, i.code),
            i.message,
            severity=i.severity,
            detail=i.detail,
        )
        for i in issues
    ]


@dataclass(frozen=True, slots=True)
class ResolvedFieldRef:
    target: NodeFieldTarget
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    input_name: str | None
    input_slot_index: int | None
    widget_index: int | None
    widget_key: str | None
    schema_input: InputSpec | None
    automatic_link_removal: int | None = None
    value_default_receipt: ValueDefaultReceipt | None = None


@dataclass(frozen=True, slots=True)
class ResolvedNodeRef:
    target: NodeTarget
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None


@dataclass(frozen=True, slots=True)
class ResolvedLinkEndpoint:
    ref: LinkSourceRef | LinkTargetRef
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    slot_index: int | None
    slot_name: str
    socket_type: str | None


@dataclass(frozen=True, slots=True)
class ResolvedRemoveLinkRef:
    scope_path: str
    link_id: int
    link: Any


@dataclass(frozen=True, slots=True)
class ResolvedLinkRewire:
    scope_path: str
    link_id: int
    old_origin_id: int
    new_origin_id: int
    new_origin_slot: int


@dataclass(frozen=True, slots=True)
class ResolvedRemoveNodePlan:
    node_ref: ResolvedNodeRef
    link_ids_to_remove: tuple[int, ...]
    link_rewires: tuple[ResolvedLinkRewire, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedAddNodeSpec:
    op: AddNodeOp
    scope: ScopeState
    schema: Any
    schema_inputs: Mapping[str, InputSpec]
    resolved_inputs: Mapping[str, ResolvedLinkEndpoint]
    resolved_input_specs: Mapping[str, InputSpec]
    value_default_receipts: tuple[ValueDefaultReceipt, ...] = ()
    value_default_fields: tuple[str, ...] = ()
    anchor_near: ResolvedNodeRef | None = None
    anchor_between: tuple[ResolvedNodeRef, ResolvedNodeRef] | None = None
    anchor_group_index: int | None = None
    anchor_group_title: str | None = None


@dataclass(frozen=True, slots=True)
class AppliedAddNodeSpec:
    op: AddNodeOp
    scope_path: str
    uid: str
    node_id: int
    link_ids: tuple[int, ...]
    source_uids: tuple[str, ...]
    group_index: int | None = None
    value_default_receipts: tuple[ValueDefaultReceipt, ...] = ()
    value_default_fields: tuple[str, ...] = ()


ResolvedOp = (
    ResolvedFieldRef
    | ResolvedNodeRef
    | tuple[ResolvedLinkEndpoint, ResolvedLinkEndpoint]
    | ResolvedRemoveLinkRef
    | ResolvedRemoveNodePlan
    | ResolvedAddNodeSpec
    | AppliedAddNodeSpec
)


@dataclass(frozen=True, slots=True)
class ResolveResult:
    ok: bool
    ledger: EditLedger
    diagnostics: tuple[PortIssue, ...]
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyResult:
    ok: bool
    candidate: dict[str, Any] | None
    diagnostics: tuple[PortIssue, ...]
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...] = ()
    mutation_started: bool = False
    guard_result: GuardResult | None = None


@dataclass(frozen=True, slots=True)
class GuardResult:
    ok: bool
    diagnostics: tuple[PortIssue, ...]
    normalize_fallback_used: bool = False
    normalize_allow_list_used: bool = False
