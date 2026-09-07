"""Constructor value-default context for the IR interpreter and batch REPL."""

from __future__ import annotations

import ast
import re
from copy import deepcopy
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

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


def _iter_ui_graphs(raw_ui_json: Mapping[str, Any], scope_path: str = "") -> list[tuple[str, Mapping[str, Any]]]:
    graphs: list[tuple[str, Mapping[str, Any]]] = [(scope_path, raw_ui_json)]
    definitions = raw_ui_json.get("definitions")
    if not isinstance(definitions, Mapping):
        return graphs
    subgraphs = definitions.get("subgraphs")
    if not isinstance(subgraphs, list):
        return graphs
    for index, definition in enumerate(subgraphs):
        if isinstance(definition, Mapping):
            child = f"{scope_path}/sg{index}" if scope_path else f"sg{index}"
            graphs.extend(_iter_ui_graphs(definition, child))
    return graphs


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
        """Rehydrate persisted binding protection from the ingest UI snapshot."""
        from vibecomfy.porting.reorganise.graph_facts import UiGraphIndex

        context = self
        index = UiGraphIndex.ingest(raw_ui_json)
        for (scope_path, uid), node in index.node_index.items():
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


def _values_equal(left: Any, right: Any) -> bool:
    """Compare authority values without bool/int or list/tuple coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return (
            tuple(left.keys()) == tuple(right.keys())
            and all(_values_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _values_equal(a, b) for a, b in zip(left, right)
        )
    return bool(left == right)


def _unique_schema_valid_prior(
    *,
    class_type: str,
    input_name: str,
    spec: InputSpec,
    context: ValueDefaultContext,
) -> tuple[ValueDefaultBinding | None, str]:
    """Select one schema-valid prior; ambiguity never becomes authority."""
    from vibecomfy.porting.edit.validate import validate_literal_value

    valid: list[ValueDefaultBinding] = []
    refused_invalid = False
    for binding in context.selected_bindings(class_type, input_name):
        issues = validate_literal_value(
            value=binding.thawed_value(),
            spec=spec,
            class_type=class_type,
            input_name=input_name,
            context="value_default_prior",
        )
        if any(getattr(issue, "severity", "error") == "error" for issue in issues):
            refused_invalid = True
            continue
        valid.append(binding)
    if not valid:
        reason = "invalid_source_prior" if refused_invalid else "no_eligible_source_prior"
        return None, reason
    first = valid[0].thawed_value()
    if any(not _values_equal(first, item.thawed_value()) for item in valid[1:]):
        return None, "conflicting_source_priors"
    return valid[0], "unique_schema_valid_source_prior"


def bind_add_node_value_defaults(
    *,
    class_type: str,
    scope_path: str,
    uid: str,
    proposed_fields: Mapping[str, Any],
    schema_inputs: Mapping[str, InputSpec],
    context: ValueDefaultContext | None,
) -> tuple[
    dict[str, Any],
    tuple[ValueDefaultReceipt, ...],
    ValueDefaultContext | None,
    tuple[Mapping[str, Any], ...],
]:
    """Resolve constructor literals before the canonical AddNodeOp is built.

    The return value is data only: effective named fields, immutable receipts,
    the next immutable context, and warning records for presentation.  It does
    not inspect UI JSON or mutate a workflow.
    """
    if context is None or not context.active:
        return dict(proposed_fields), (), context, ()

    effective = dict(proposed_fields)
    receipts: list[ValueDefaultReceipt] = []
    warnings: list[Mapping[str, Any]] = []
    consumed: list[str] = []
    for input_name, spec in schema_inputs.items():
        from vibecomfy.porting.authoring_surface import input_spec_is_socket_only

        if input_spec_is_socket_only(spec):
            continue
        override = (
            context.explicit_override(class_type, input_name)
            or context.explicit_request_override(class_type, input_name, spec)
        )
        prior, prior_reason = _unique_schema_valid_prior(
            class_type=class_type,
            input_name=input_name,
            spec=spec,
            context=context,
        )
        chosen = False
        chosen_value: Any = None
        basis = ""
        provenance = ""
        source_instance_id = ""
        role_label = ""
        reason = ""
        if override is not None:
            chosen = True
            chosen_value = override.thawed_value()
            basis = "explicit_user_value"
            provenance = "user"
            source_instance_id = override.source_instance_id
            role_label = override.role_label
            reason = "exact structured user override"
        elif prior is not None:
            chosen = True
            chosen_value = prior.thawed_value()
            basis = "source_prior"
            provenance = prior.provenance
            source_instance_id = prior.source_instance_id
            role_label = prior.role_label
            reason = prior_reason
        elif input_name not in effective and getattr(spec, "default", None) is not None:
            chosen = True
            chosen_value = deepcopy(spec.default)
            basis = "schema_default"
            provenance = "schema_default"
            reason = "authoritative retained schema default"

        if (
            not chosen
            and input_name not in effective
            and bool(getattr(spec, "required", False))
            and getattr(spec, "default", None) is None
        ):
            warnings.append({
                "code": "missing_required_add_node_input",
                "message": f"{class_type} requires input {input_name!r} for add_node.",
                "detail": {
                    "scope_path": scope_path,
                    "class_type": class_type,
                    "input": input_name,
                },
            })

        if input_name in effective:
            proposed_value = effective[input_name]
            if not chosen:
                continue
            if not _values_equal(proposed_value, chosen_value):
                warnings.append({
                    "code": "value_default_literal_normalized",
                    "message": (
                        f"{class_type}.{input_name} proposed {proposed_value!r}; "
                        f"the qualified {basis} value {chosen_value!r} was applied."
                    ),
                    "detail": {
                        "scope_path": scope_path,
                        "class_type": class_type,
                        "field": input_name,
                        "proposed_value": proposed_value,
                        "effective_value": chosen_value,
                        "effective_basis": basis,
                    },
                })
                reason = f"{reason}; conflicting constructor literal normalized"
            else:
                reason = f"{reason}; redundant constructor literal normalized"

        if chosen:
            effective[input_name] = chosen_value
            receipts.append(ValueDefaultReceipt(
                class_type=class_type,
                canonical_field=input_name,
                old_value=None,
                new_value=chosen_value,
                basis=basis,
                provenance=provenance,
                validation_result="passed",
                source_instance_id=source_instance_id,
                role_label=role_label,
                reason=reason,
            ))
            if source_instance_id:
                consumed.append(source_instance_id)

    next_context = context
    if receipts:
        next_context = context.protect_node(
            scope_path=scope_path,
            uid=uid,
            class_type=class_type,
            fields=tuple(receipt.canonical_field for receipt in receipts),
            source_instance_ids=tuple(consumed),
        )
    return effective, tuple(receipts), next_context, tuple(warnings)


def authorize_protected_value_change(
    *,
    context: ValueDefaultContext | None,
    scope_path: str,
    uid: str,
    class_type: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    spec: InputSpec | None,
) -> ValueDefaultReceipt | None:
    """Return a receipt for a protected edit, or ``None`` to refuse it."""
    if (
        context is None
        or not context.active
        or not context.protects(scope_path, uid, class_type, field_name)
    ):
        return ValueDefaultReceipt(
            class_type=class_type,
            canonical_field=field_name,
            old_value=old_value,
            new_value=new_value,
            basis="unprotected",
            provenance="ordinary_edit",
            validation_result="not_required",
        )
    basis = ""
    provenance = ""
    reason = ""
    if _values_equal(old_value, new_value):
        basis = "redundant_existing_value"
        provenance = "existing_bound_value"
        reason = "assignment equals the protected value"
    else:
        override = (
            context.explicit_override(class_type, field_name)
            or context.explicit_request_override(class_type, field_name, spec)
        )
        if override is not None and _values_equal(override.thawed_value(), new_value):
            basis = "explicit_user_value"
            provenance = "user"
            reason = "exact user override matches the proposed value"
        elif spec is not None and getattr(spec, "default", None) is not None:
            from vibecomfy.porting.edit.validate import validate_literal_value

            old_issues = validate_literal_value(
                value=old_value,
                spec=spec,
                class_type=class_type,
                input_name=field_name,
                context="protected_value",
            )
            if (
                any(getattr(issue, "severity", "error") == "error" for issue in old_issues)
                and _values_equal(spec.default, new_value)
            ):
                basis = "schema_correction"
                provenance = "schema_default"
                reason = "protected value invalid under current schema; unique declared-default correction"
    if not basis:
        return None
    return ValueDefaultReceipt(
        class_type=class_type,
        canonical_field=field_name,
        old_value=old_value,
        new_value=new_value,
        basis=basis,
        provenance=provenance,
        validation_result="passed",
        reason=reason,
    )
