from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from vibecomfy._compile._graph import is_canonical_api_link

from vibecomfy.errors import SchemaValidationError
from vibecomfy.metadata import MODEL_FILE_EXTENSIONS
from vibecomfy.model_assets import _subdir_for_model_reference
from vibecomfy.schema.provider import SchemaProvider, schema_for, schema_registry_empty
from vibecomfy.workflow import ValidationIssue, VibeWorkflow


def format_issue(issue: Any) -> str:
    detail = issue.detail or {}
    location = " ".join(
        f"{key}={detail[key]}" for key in ("node_id", "class_type", "input") if key in detail
    )
    return f"[{issue.code}] {location}: {issue.message}".strip()


def validation_errors_payload(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    """Group concrete validation errors by node for agent feedback payloads."""
    grouped: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for issue in issues:
        if issue.severity != "error":
            continue
        detail = issue.detail or {}
        node_id = detail.get("node_id") or detail.get("to_node") or detail.get("from_node")
        class_type = detail.get("class_type") or detail.get("to_class_type") or detail.get("from_class_type")
        key = (
            str(node_id) if node_id is not None else None,
            str(class_type) if class_type is not None else None,
        )
        entry = grouped.setdefault(
            key,
            {
                "node_id": key[0],
                "class_type": key[1],
                "errors": [],
            },
        )
        entry["errors"].append(
            {
                "code": issue.code,
                "message": issue.message,
                "input": detail.get("input") or detail.get("to_input"),
                "detail": dict(detail),
            }
        )
    return list(grouped.values())


# ── Field-level compatibility policy ─────────────────────────────────────────
#
# Unknown inputs remain validation errors UNLESS a typed, evidence-backed
# entry proves a known version mismatch for that exact (class_type, input)
# field against the static schema. There is no class-wide suppression: a
# compatibility entry covers one field and one set of issue codes, and every
# entry must be cross-referenced from ``docs/node_pack_reconciliation.md``
# (the "Known snapshot drift issues" table) with its root cause.
#
# These entries exist because the static schema snapshot is KNOWN to be stale
# for the runtime the workflow targets (a newer custom-node version added or
# widened the field). Fields with an entry are treated as compatible: they do
# not fail validation and they are NOT proposed for queue normalization
# (dropping or coercing a compatible field would corrupt a payload the runtime
# accepts). Every other field on the same class stays fail-closed.


@dataclass(frozen=True)
class FieldCompatibility:
    """Evidence-backed compatibility allowance for ONE (class_type, input).

    Attributes:
        class_type: The node class the field belongs to.
        input: The exact input/field name on that class.
        reason: Human-readable root cause for the known version mismatch.
        evidence: Pointer to the evidence (documented snapshot drift).
        codes: Issue codes this allowance covers. Defaults to the codes the
            legacy class-wide suppression used to swallow; an entry should
            narrow this when it only addresses one code (e.g. an enum that
            accepts values the snapshot did not capture).
    """

    class_type: str
    input: str
    reason: str
    evidence: str
    codes: tuple[str, ...] = (
        "unknown_input",
        "value_not_in_enum",
        "value_out_of_range",
        "value_type_mismatch",
    )


FIELD_COMPATIBILITY: tuple[FieldCompatibility, ...] = (
    # ComfyUI-WanVideoWrapper — WanVideoModelLoader schema snapshot predates
    # the vace_model optional input added in a newer WanVideoWrapper version.
    FieldCompatibility(
        class_type="WanVideoModelLoader",
        input="vace_model",
        reason=(
            "vace_model is a valid optional input in newer WanVideoWrapper "
            "versions; the runpod snapshot predates it."
        ),
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoModelLoader predates vace_model",
        codes=("unknown_input",),
    ),
    # ComfyUI-WanVideoWrapper — VACE model enum only captures the files present
    # when the snapshot was taken; templates select VACE variants not in it.
    FieldCompatibility(
        class_type="WanVideoVACEModelSelect",
        input="vace_model",
        reason=(
            "The snapshot enum reflects only the files installed when "
            "object_info was captured; templates use WanVideo VACE variants "
            "not listed there."
        ),
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoVACEModelSelect model enum",
        codes=("value_not_in_enum",),
    ),
    # ComfyUI-KJNodes — ImagePadKJ pad_mode accepts RGB strings like
    # '255,255,255'; the snapshot enum only lists named modes.
    FieldCompatibility(
        class_type="ImagePadKJ",
        input="pad_mode",
        reason=(
            "pad_mode accepts RGB strings such as '255,255,255' at runtime; "
            "the snapshot enum only lists the named modes."
        ),
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: ImagePadKJ pad_mode RGB strings",
        codes=("value_not_in_enum",),
    ),
    # ComfyUI-WanVideoWrapper — the WanVideoSampler WIDGET_SCHEMA entry (14
    # items, 0-indexed) predates widgets added at position 14+ in newer
    # versions. The runpod snapshot declares these as optional inputs.
    FieldCompatibility(
        class_type="WanVideoSampler",
        input="cache_args",
        reason="cache_args is an optional input in newer WanVideoWrapper versions not in the 14-item WIDGET_SCHEMA entry.",
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoSampler 14-item WIDGET_SCHEMA misses item at index 14",
        codes=("unknown_input",),
    ),
    FieldCompatibility(
        class_type="WanVideoSampler",
        input="context_options",
        reason="context_options is an optional input in newer WanVideoWrapper versions not in the 14-item WIDGET_SCHEMA entry.",
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoSampler 14-item WIDGET_SCHEMA misses item at index 14",
        codes=("unknown_input",),
    ),
    FieldCompatibility(
        class_type="WanVideoSampler",
        input="experimental_args",
        reason="experimental_args is an optional input in newer WanVideoWrapper versions not in the 14-item WIDGET_SCHEMA entry.",
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoSampler 14-item WIDGET_SCHEMA misses item at index 14",
        codes=("unknown_input",),
    ),
    FieldCompatibility(
        class_type="WanVideoSampler",
        input="feta_args",
        reason="feta_args is an optional input in newer WanVideoWrapper versions not in the 14-item WIDGET_SCHEMA entry.",
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoSampler 14-item WIDGET_SCHEMA misses item at index 14",
        codes=("unknown_input",),
    ),
    FieldCompatibility(
        class_type="WanVideoSampler",
        input="multitalk_embeds",
        reason="multitalk_embeds is an optional input in newer WanVideoWrapper versions not in the 14-item WIDGET_SCHEMA entry.",
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoSampler 14-item WIDGET_SCHEMA misses item at index 14",
        codes=("unknown_input",),
    ),
    FieldCompatibility(
        class_type="WanVideoSampler",
        input="slg_args",
        reason="slg_args is an optional input in newer WanVideoWrapper versions not in the 14-item WIDGET_SCHEMA entry.",
        evidence="docs/node_pack_reconciliation.md — known snapshot drift: WanVideoSampler 14-item WIDGET_SCHEMA misses item at index 14",
        codes=("unknown_input",),
    ),
)

_FIELD_COMPATIBILITY_INDEX: dict[tuple[str, str], frozenset[str]] = {
    (entry.class_type, entry.input): frozenset(entry.codes) for entry in FIELD_COMPATIBILITY
}


def field_compatibility_for(class_type: str, input_name: str) -> FieldCompatibility | None:
    """Return the evidence-backed compatibility entry for a field, if any."""
    for entry in FIELD_COMPATIBILITY:
        if entry.class_type == class_type and entry.input == input_name:
            return entry
    return None


def _field_compatible(class_type: str, input_name: str, code: str) -> bool:
    """Return whether a typed compatibility entry covers this field+code.

    This is the ONLY suppression path left in validation, and it is strictly
    field-level: an entry covers one (class_type, input) and one or more issue
    codes, never a whole class.
    """
    return code in _FIELD_COMPATIBILITY_INDEX.get((class_type, input_name), ())


def validate_against_schema(workflow: VibeWorkflow, provider: SchemaProvider) -> list[ValidationIssue]:
    if schema_registry_empty(provider):
        return []

    issues: list[ValidationIssue] = []
    schema_by_node: dict[str, Any] = {}
    try:
        api_dict = workflow.compile(backend="api")
    except Exception as exc:
        return [ValidationIssue("api_compile_failed", str(exc), severity="warning")]

    return validate_api_against_schema(api_dict, provider)


def validate_api_against_schema(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
    if schema_registry_empty(provider):
        return []

    issues: list[ValidationIssue] = []
    schema_by_node: dict[str, Any] = {}

    for node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        schema = schema_for(provider, class_type)
        if schema is None:
            issues.append(
                ValidationIssue(
                    "unknown_class_type",
                    f"Unknown class_type {class_type} on node {node_id}.",
                    detail={
                        "node_id": str(node_id),
                        "class_type": class_type,
                        "next_action": "vibecomfy schema refresh",
                    },
                )
            )
            continue

        schema_by_node[str(node_id)] = schema
        raw_schema_inputs = getattr(schema, "inputs", {}) or {}
        declared_inputs = set(raw_schema_inputs)
        payload_inputs = node.get("inputs") or {}
        if not isinstance(payload_inputs, dict):
            payload_inputs = {}
        provided_inputs = set(payload_inputs)

        if not raw_schema_inputs:
            continue

        for name, spec in raw_schema_inputs.items():
            if getattr(spec, "required", False) and name not in provided_inputs and getattr(spec, "default", None) is None:
                issues.append(
                    ValidationIssue(
                        "missing_required_input",
                        f"Node {node_id} ({class_type}) is missing required input {name}.",
                        detail={
                            "node_id": str(node_id),
                            "class_type": class_type,
                            "input": name,
                        },
                    )
                )

        for name in sorted(provided_inputs - declared_inputs):
            value = payload_inputs.get(name)
            if _preserve_linked_undeclared_input(name, value):
                continue
            if getattr(schema, "source_provider", None) == "widget_schema" and _is_api_link(value):
                continue
            if (
                not _field_compatible(class_type, name, "unknown_input")
                and not _is_dynamic_payload_input(class_type, name, payload_inputs)
            ):
                issues.append(
                    ValidationIssue(
                        "unknown_input",
                        f"Node {node_id} ({class_type}) has unknown input {name}.",
                        detail={"node_id": str(node_id), "class_type": class_type, "input": name},
                    )
                )

        issues.extend(_validate_dynamic_payload_inputs(node_id=str(node_id), class_type=class_type, inputs=payload_inputs))

        for name in sorted(provided_inputs & declared_inputs):
            value = payload_inputs[name]
            if _is_api_link(value):
                continue
            spec = raw_schema_inputs[name]
            choices = getattr(spec, "choices", None) or []
            if (
                choices
                and value not in choices
                and _coerce_choice_value(value, choices) is _NO_MATCH
                and not _field_compatible(class_type, name, "value_not_in_enum")
                and not _is_dynamic_file_choice(class_type, name)
            ):
                choice_scope = _choice_scope(class_type, name, value)
                if choice_scope == "environment_asset":
                    # Apply-time parity: checkpoint/model/embedding pickers
                    # enumerate the assets installed when object_info was
                    # fetched. A request for a not-yet-installed asset is a
                    # warning (the value is still structurally valid), not a
                    # hard schema error. Semantic enums stay hard errors below.
                    issues.append(
                        ValidationIssue(
                            "value_not_in_enum",
                            f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} is not among the locally installed asset choices.",
                            severity="warning",
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "input": name,
                                "value": _truncate(value),
                                "choices": choices,
                                "choice_scope": choice_scope,
                            },
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            "value_not_in_enum",
                            f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} is not one of the declared choices.",
                            severity="error",
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "input": name,
                                "value": _truncate(value),
                                "choices": choices,
                                "choice_scope": choice_scope,
                            },
                        )
                    )

            min_value = getattr(spec, "min", None)
            max_value = getattr(spec, "max", None)
            if (min_value is not None or max_value is not None) and not _field_compatible(class_type, name, "value_out_of_range"):
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError, OverflowError):
                    continue
                if (min_value is not None and numeric_value < float(min_value)) or (
                    max_value is not None and numeric_value > float(max_value)
                ):
                    issues.append(
                        ValidationIssue(
                            "value_out_of_range",
                            f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} is outside the declared range.",
                            severity="error",
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "input": name,
                                "value": _truncate(value),
                                "min": min_value,
                                "max": max_value,
                            },
                        )
                    )
            expected_type = _primitive_expected_type(getattr(spec, "type", None))
            if expected_type and not _field_compatible(class_type, name, "value_type_mismatch"):
                if not _matches_primitive_type(value, expected_type):
                    issues.append(
                        ValidationIssue(
                            "value_type_mismatch",
                            (
                                f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} "
                                f"does not match declared type {expected_type}."
                            ),
                            severity="error",
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "input": name,
                                "value": _truncate(value),
                                "expected_type": expected_type,
                                "actual_type": type(value).__name__,
                            },
                        )
                    )

    for to_node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        to_schema = schema_by_node.get(str(to_node_id))
        inputs = node.get("inputs") or {}
        if to_schema is None or not isinstance(inputs, dict):
            continue
        for input_name, value in inputs.items():
            if not _is_api_link(value):
                continue
            from_node, from_output = str(value[0]), str(value[1])
            from_schema = schema_by_node.get(from_node)
            if from_schema is None:
                continue
            outputs = getattr(from_schema, "outputs", None) or []
            if not outputs:
                continue
            try:
                output_index = int(from_output)
            except (TypeError, ValueError):
                output_index = None
            # Empty outputs list means the schema does not declare output info
            # (e.g. permissive index synthesized from API workflows). Treat as
            # unknown and skip the output-index bounds check rather than emit a
            # false-positive violation. A truly outputless node would be a
            # leaf sink that never appears as an edge source anyway.
            if output_index is not None and outputs and (output_index < 0 or output_index >= len(outputs)):
                issues.append(
                    ValidationIssue(
                        "invalid_output_index",
                        f"Edge {from_node}.{from_output} -> {to_node_id}.{input_name} references output "
                        f"{from_output}, but {from_schema.class_type} exposes {len(outputs)} output(s).",
                        severity="error",
                        detail={
                            "from_node": from_node,
                            "from_class_type": from_schema.class_type,
                            "from_output": from_output,
                            "output_count": len(outputs),
                            "to_node": str(to_node_id),
                            "to_input": input_name,
                        },
                    )
                )
                continue
            output_type = _edge_output_type(from_schema, from_output)
            input_type = _edge_input_type(to_schema, input_name)
            if output_type and input_type and not socket_types_compatible(output_type, input_type):
                issues.append(
                    ValidationIssue(
                        "type_mismatch",
                        f"Edge {from_node}.{from_output} -> {to_node_id}.{input_name} connects {output_type} to {input_type}.",
                        severity="warning",
                        detail={
                            "from_node": from_node,
                            "from_output": from_output,
                            "to_node": str(to_node_id),
                            "to_input": input_name,
                            "output_type": output_type,
                            "input_type": input_type,
                        },
                    )
                )

    return issues


def _choice_scope(class_type: str, input_name: str, value: Any) -> str:
    """Distinguish environment inventory selectors from semantic choices."""
    lowered = input_name.lower()
    if lowered in {
        "sampler",
        "sampler_name",
        "scheduler",
        "scheduler_name",
        "crop",
        "crop_mode",
        "crop_policy",
        "behavior",
        "mode",
        "policy",
    }:
        return "semantic"
    if _subdir_for_model_reference(class_type, input_name) is not None:
        return "environment_asset"
    if isinstance(value, str) and value.lower().endswith(MODEL_FILE_EXTENSIONS):
        return "environment_asset"
    if (
        lowered.startswith("clip_name")
        or lowered == "vae_name"
        or lowered == "lora_name"
        or re.fullmatch(r"lora_\d+", lowered)
    ):
        return "environment_asset"
    return "semantic"


# ── Typed normalization proposal (fail-closed queue preparation) ─────────────
#
# Queue preparation NEVER mutates the compiled payload directly. Any change the
# runtime would need — dropping an input the live schema does not declare, or
# coercing a portable choice string to the exact choice the runtime exposes —
# is first computed as a typed :class:`NormalizationProposal`. Without explicit
# agent approval the queue is REFUSED (no silent deletes, no silent coercion);
# with approval, exactly the proposed operations are applied and recorded as
# evidence.


def _same_value(a: Any, b: Any) -> bool:
    """Strict equality that keeps ``True`` distinct from ``1``."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    return a == b


def _canonical_payload(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


@dataclass(frozen=True)
class NormalizationOp:
    """One proposed queue-preparation change for a single node input.

    Attributes:
        node_id: The API node id the change targets.
        class_type: The node's class type.
        field: The input name being changed.
        kind: ``"drop"`` (input is not declared by the live schema) or
            ``"coerce"`` (value normalizes to the exact choice the runtime
            exposes).
        before: The value before the change (``None`` only when the input is
            genuinely absent — drops always carry the current value).
        after: The value after the change; ``None`` for drops.
        reason: Why the change is proposed.
    """

    node_id: str
    class_type: str
    field: str
    kind: str
    before: Any
    after: Any
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", str(self.node_id))
        object.__setattr__(self, "class_type", str(self.class_type))
        object.__setattr__(self, "field", str(self.field))
        kind = str(self.kind)
        if kind not in {"drop", "coerce"}:
            raise ValueError("`kind` must be 'drop' or 'coerce'.")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "reason", str(self.reason))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "class_type": self.class_type,
            "field": self.field,
            "kind": self.kind,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "NormalizationOp":
        if not isinstance(payload, dict):
            raise ValueError("NormalizationOp must be an object.")
        required = {"node_id", "class_type", "field", "kind", "before", "after", "reason"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError("NormalizationOp missing key(s): " + ", ".join(missing))
        return cls(
            node_id=payload["node_id"],
            class_type=payload["class_type"],
            field=payload["field"],
            kind=payload["kind"],
            before=payload["before"],
            after=payload["after"],
            reason=payload["reason"],
        )


@dataclass(frozen=True)
class NormalizationApproval:
    """Explicit approval binding one decision-maker to ONE proposal digest.

    The approval only names the proposal digest, never the changes themselves:
    applying an approval to a different (or mutated) proposal is refused, so an
    approval can never apply a change the agent did not see.
    """

    proposal_digest: str
    granted_by: str = "agent"
    granted_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_digest", str(self.proposal_digest))
        object.__setattr__(self, "granted_by", str(self.granted_by))
        if self.granted_at is not None:
            object.__setattr__(self, "granted_at", str(self.granted_at))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "proposal_digest": self.proposal_digest,
            "granted_by": self.granted_by,
        }
        if self.granted_at is not None:
            payload["granted_at"] = self.granted_at
        return payload

    @classmethod
    def from_dict(cls, payload: Any) -> "NormalizationApproval":
        if not isinstance(payload, dict) or "proposal_digest" not in payload:
            raise ValueError("NormalizationApproval must be an object with proposal_digest.")
        return cls(
            proposal_digest=payload["proposal_digest"],
            granted_by=str(payload.get("granted_by", "agent")),
            granted_at=payload.get("granted_at"),
        )


@dataclass(frozen=True)
class NormalizationProposal:
    """Typed, immutable set of queue-preparation changes (possibly empty)."""

    ops: tuple[NormalizationOp, ...] = ()

    def __post_init__(self) -> None:
        ops = tuple(
            op if isinstance(op, NormalizationOp) else NormalizationOp.from_dict(op)
            for op in self.ops
        )
        object.__setattr__(self, "ops", ops)

    def __bool__(self) -> bool:
        return bool(self.ops)

    def __len__(self) -> int:
        return len(self.ops)

    def to_dict(self) -> dict[str, Any]:
        return {"ops": [op.to_dict() for op in self.ops]}

    @classmethod
    def from_dict(cls, payload: Any) -> "NormalizationProposal":
        raw_ops = payload.get("ops", ()) if isinstance(payload, dict) else ()
        if not isinstance(raw_ops, (list, tuple)):
            raise ValueError("NormalizationProposal.ops must be a list.")
        return cls(tuple(raw_ops))

    def digest(self) -> str:
        """Canonical SHA-256 of the proposal; the approval binds to this."""
        return hashlib.sha256(_canonical_payload(self.to_dict()).encode("utf-8")).hexdigest()

    def approved_by(self, approval: Any) -> bool:
        """Return whether *approval* binds exactly to THIS proposal.

        Accepts a :class:`NormalizationApproval` or a bare digest string. Any
        other value (including ``None``) is treated as "not approved".
        """
        if approval is None:
            return False
        digest = self.digest()
        if isinstance(approval, NormalizationApproval):
            return approval.proposal_digest == digest
        if isinstance(approval, str):
            return approval == digest
        return False

    def refusal_message(self) -> str:
        """Render the refusal diagnostic with node/field/before/after/reason."""
        lines = [f"Queue normalization requires agent approval ({len(self.ops)} change(s)):"]
        for op in self.ops:
            lines.append(
                f"  - node={op.node_id} class={op.class_type} field={op.field} kind={op.kind} "
                f"before={_truncate(op.before)} after={_truncate(op.after)} reason={op.reason}"
            )
        return "\n".join(lines)


class SchemaNormalizationRequired(SchemaValidationError):
    """Queue preparation needs changes the agent has not approved.

    Carries the full typed proposal so a caller can surface every change
    (node/field/before/after/reason) and, once the agent decides, re-queue with
    the matching approval.
    """

    default_next_action = "review the normalization proposal and re-queue with explicit approval"

    def __init__(self, proposal: NormalizationProposal) -> None:
        self.proposal = proposal
        super().__init__(proposal.refusal_message())

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["normalization"] = self.proposal.to_dict()
        return payload


class SchemaNormalizationMismatch(SchemaValidationError):
    """A proposal could not be applied because the payload changed underneath it.

    This is a stale-approval guard: applying an approval must never change a
    different payload than the one the agent approved.
    """

    default_next_action = "re-run queue preparation to obtain a fresh proposal and approval"


def propose_schema_normalization(
    api_dict: dict[str, Any],
    provider: SchemaProvider | None,
) -> NormalizationProposal:
    """Compute, WITHOUT mutating, the changes queue preparation would need.

    Never modifies *api_dict* and never proposes changes for fields covered by
    the field-level compatibility policy (those are known version mismatches —
    dropping or coercing them would corrupt a payload the runtime accepts).
    Returns an empty proposal when the payload already matches the live schema.
    """
    if provider is None or schema_registry_empty(provider):
        return NormalizationProposal()
    ops: list[NormalizationOp] = []
    for node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(class_type, str) or not isinstance(inputs, dict):
            continue
        schema = schema_for(provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) if schema is not None else {}
        if not schema_inputs:
            continue
        for name in sorted(inputs):
            if name in schema_inputs:
                value = inputs[name]
                if _is_api_link(value):
                    continue
                choices = getattr(schema_inputs[name], "choices", None) or []
                coerced = _coerce_choice_value(value, choices)
                if coerced is not _NO_MATCH and not _same_value(coerced, value):
                    ops.append(
                        NormalizationOp(
                            node_id=str(node_id),
                            class_type=class_type,
                            field=name,
                            kind="coerce",
                            before=value,
                            after=coerced,
                            reason=(
                                "portable choice string normalizes to the exact "
                                "choice string the runtime exposes"
                            ),
                        )
                    )
                continue
            value = inputs.get(name)
            if _is_dynamic_payload_input(class_type, name, inputs):
                continue
            if _preserve_linked_undeclared_input(name, value):
                continue
            if getattr(schema, "source_provider", None) == "widget_schema" and _is_api_link(value):
                continue
            if _field_compatible(class_type, name, "unknown_input"):
                continue
            ops.append(
                NormalizationOp(
                    node_id=str(node_id),
                    class_type=class_type,
                    field=name,
                    kind="drop",
                    before=value,
                    after=None,
                    reason=(
                        "input is not declared by the live node schema and "
                        "would be rejected at queue time"
                    ),
                )
            )
    return NormalizationProposal(tuple(ops))


def apply_schema_normalization(
    api_dict: dict[str, Any],
    proposal: NormalizationProposal,
) -> dict[str, Any]:
    """Apply EXACTLY the ops in *proposal* to a deep copy of *api_dict*.

    Each op must still match the current payload (node present, input present,
    value equal to ``op.before``). Any mismatch raises
    :class:`SchemaNormalizationMismatch` instead of applying a different change
    than the one approved. The input mapping is never mutated in place.
    """
    if not proposal.ops:
        return copy.deepcopy(dict(api_dict))
    applied = copy.deepcopy(dict(api_dict))
    for op in proposal.ops:
        node = applied.get(op.node_id)
        if not isinstance(node, dict):
            raise SchemaNormalizationMismatch(
                f"node {op.node_id} no longer exists; the proposal is stale"
            )
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or op.field not in inputs:
            raise SchemaNormalizationMismatch(
                f"node {op.node_id} input {op.field} no longer exists; the proposal is stale"
            )
        current = inputs.get(op.field)
        if not _same_value(current, op.before):
            raise SchemaNormalizationMismatch(
                f"node {op.node_id} input {op.field} changed since approval: "
                f"before={_truncate(op.before)} now={_truncate(current)}"
            )
        if op.kind == "drop":
            del inputs[op.field]
        elif op.kind == "coerce":
            inputs[op.field] = op.after
        else:  # pragma: no cover - NormalizationOp.__post_init__ gates this
            raise ValueError(f"unknown normalization kind: {op.kind}")
    return applied


def validate_api_link_shapes(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        if not isinstance(class_type, str) or not isinstance(inputs, dict):
            continue
        schema = schema_for(provider, class_type)
        raw_schema_inputs = getattr(schema, "inputs", {}) or {}
        for name, value in inputs.items():
            if not isinstance(value, dict):
                continue
            spec = raw_schema_inputs.get(name)
            if _schema_accepts_dict(spec):
                continue
            issues.append(
                ValidationIssue(
                    "invalid_link_shape",
                    f"Node {node_id} ({class_type}) input {name} has dict-shaped link; expected [node_id, output_index].",
                    severity="error",
                    detail={
                        "node_id": str(node_id),
                        "class_type": class_type,
                        "input": name,
                        "value_repr": _truncate(value),
                    },
                )
            )
    return issues


def _incoming_inputs(workflow: VibeWorkflow) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = {}
    for edge in workflow.edges:
        incoming.setdefault(edge.to_node, set()).add(edge.to_input)
    return incoming


_LTX_IMAGE_SLOT_RE = re.compile(r"^num_images\.(?:image|index|strength)_(\d+)$")
_FIXED_SLOT_INPUT_RE = re.compile(r"^in_(\d+)$")
_IMAGE_CONCAT_MULTI_INPUT_RE = re.compile(r"^image_(\d+)$")

# This is a validation-work bound, not a provider-supported count. Provider
# ceilings require authoritative schema data and belong in a separate slice.
_DYNAMIC_VALIDATION_WORK_LIMIT = 4096
_DYNAMIC_VALIDATION_WORK_LIMIT_DIGITS = len(str(_DYNAMIC_VALIDATION_WORK_LIMIT))


def _preserve_linked_undeclared_input(name: str, value: Any) -> bool:
    return bool(_FIXED_SLOT_INPUT_RE.match(name)) and _is_api_link(value)


def _is_dynamic_payload_input(class_type: str, input_name: str, inputs: dict[str, Any] | None = None) -> bool:
    """Return whether an input is generated from a runtime payload count.

    Some custom nodes declare a compact controller input in object_info but
    validate expanded dotted inputs at queue time. These are not UI aliases:
    stripping them changes the executable prompt. Keep this list narrow and
    add class-specific validation below so dynamic inputs remain intentional.
    """

    if class_type == "LTXVImgToVideoInplaceKJ":
        return _ltx_image_slot_index(input_name) is not None
    if class_type == "ImageConcatMulti":
        return _image_concat_multi_input_index(input_name) is not None
    if class_type == "SimpleCalculator" and _has_numbered_prefix(input_name, "input_"):
        return True
    if class_type == "LTXVAddGuide" and _has_numbered_prefix(input_name, "guide_"):
        return True
    if class_type == "SimpleCalculatorKJ":
        return input_name in _simple_calculator_variables(inputs or {})
    return False


def _validate_dynamic_payload_inputs(
    *,
    node_id: str,
    class_type: str,
    inputs: dict[str, Any],
) -> list[ValidationIssue]:
    if class_type == "ImageConcatMulti":
        return _validate_image_concat_multi_inputs(node_id=node_id, class_type=class_type, inputs=inputs)
    if class_type != "LTXVImgToVideoInplaceKJ":
        if class_type in {"SimpleCalculator", "SimpleCalculatorKJ"}:
            return _validate_simple_calculator_variables(node_id=node_id, class_type=class_type, inputs=inputs)
        return []
    raw_count = inputs.get("num_images")
    if raw_count is None or _is_api_link(raw_count):
        return []
    count = _validated_dynamic_count(raw_count, minimum=1)
    if count is None:
        return [
            ValidationIssue(
                "invalid_dynamic_input_count",
                f"Node {node_id} ({class_type}) input num_images must be an integer count.",
                severity="error",
                detail={
                    "node_id": node_id,
                    "class_type": class_type,
                    "input": "num_images",
                    "value": _truncate_dynamic_count_value(raw_count),
                },
            )
        ]

    issues: list[ValidationIssue] = []
    for index in range(1, count + 1):
        for suffix in ("image", "index", "strength"):
            name = f"num_images.{suffix}_{index}"
            if name not in inputs:
                issues.append(
                    ValidationIssue(
                        "missing_dynamic_input",
                        f"Node {node_id} ({class_type}) is missing dynamic input {name}.",
                        severity="error",
                        detail={"node_id": node_id, "class_type": class_type, "input": name},
                    )
                )
    for name in inputs:
        index = _ltx_image_slot_index(name)
        if index is not None and index > count:
            issues.append(
                ValidationIssue(
                    "dynamic_input_exceeds_count",
                    f"Node {node_id} ({class_type}) input {name} exceeds num_images={count}.",
                    severity="error",
                    detail={"node_id": node_id, "class_type": class_type, "input": name, "num_images": count},
                )
            )
    return issues


def _validated_dynamic_count(raw_count: Any, *, minimum: int) -> int | None:
    if type(raw_count) is not int:
        return None
    if raw_count < minimum or raw_count > _DYNAMIC_VALIDATION_WORK_LIMIT:
        return None
    return raw_count


def _bounded_decimal_index(digits: str) -> int | None:
    normalized = digits.lstrip("0")
    if not normalized:
        return None
    if len(normalized) > _DYNAMIC_VALIDATION_WORK_LIMIT_DIGITS:
        return _DYNAMIC_VALIDATION_WORK_LIMIT + 1
    index = int(normalized)
    return index if index >= 1 else None


def _ltx_image_slot_index(name: str) -> int | None:
    match = _LTX_IMAGE_SLOT_RE.match(name)
    return None if match is None else _bounded_decimal_index(match.group(1))


def _image_concat_multi_input_index(name: str) -> int | None:
    match = _IMAGE_CONCAT_MULTI_INPUT_RE.match(name)
    return None if match is None else _bounded_decimal_index(match.group(1))


def _validate_image_concat_multi_inputs(
    *,
    node_id: str,
    class_type: str,
    inputs: dict[str, Any],
) -> list[ValidationIssue]:
    raw_count = inputs.get("inputcount")
    if raw_count is None or _is_api_link(raw_count):
        return []
    count = _validated_dynamic_count(raw_count, minimum=2)
    if count is None:
        return [
            ValidationIssue(
                "invalid_dynamic_input_count",
                f"Node {node_id} ({class_type}) input inputcount must be an integer count.",
                severity="error",
                detail={
                    "node_id": node_id,
                    "class_type": class_type,
                    "input": "inputcount",
                    "value": _truncate_dynamic_count_value(raw_count),
                },
            )
        ]

    issues: list[ValidationIssue] = []
    for index in range(1, count + 1):
        name = f"image_{index}"
        if name not in inputs:
            issues.append(
                ValidationIssue(
                    "missing_dynamic_input",
                    f"Node {node_id} ({class_type}) is missing dynamic input {name}.",
                    severity="error",
                    detail={"node_id": node_id, "class_type": class_type, "input": name},
                )
            )
    for name in inputs:
        index = _image_concat_multi_input_index(name)
        if index is not None and index > count:
            issues.append(
                ValidationIssue(
                    "dynamic_input_exceeds_count",
                    f"Node {node_id} ({class_type}) input {name} exceeds inputcount={count}.",
                    severity="error",
                    detail={"node_id": node_id, "class_type": class_type, "input": name, "inputcount": count},
                )
            )
    return issues


def _simple_calculator_variables(inputs: dict[str, Any]) -> set[str]:
    raw = inputs.get("variables")
    if not isinstance(raw, str):
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _has_numbered_prefix(value: str, prefix: str) -> bool:
    suffix = value.removeprefix(prefix)
    return suffix != value and suffix.isdigit()


def _validate_simple_calculator_variables(
    *,
    node_id: str,
    class_type: str,
    inputs: dict[str, Any],
) -> list[ValidationIssue]:
    variables = _simple_calculator_variables(inputs)
    return [
        ValidationIssue(
            "missing_dynamic_input",
            f"Node {node_id} ({class_type}) is missing dynamic input {name}.",
            severity="error",
            detail={"node_id": node_id, "class_type": class_type, "input": name},
        )
        for name in sorted(variables)
        if name not in inputs
    ]


def _edge_output_type(schema, from_output: str) -> str | None:
    outputs = getattr(schema, "outputs", None) or []
    try:
        index = int(from_output)
    except (TypeError, ValueError):
        index = None
    if index is not None and 0 <= index < len(outputs):
        return _normalize_type(getattr(outputs[index], "type", None))
    for output in outputs:
        if getattr(output, "name", None) == from_output:
            return _normalize_type(getattr(output, "type", None))
    return None


def _edge_input_type(schema, to_input: str) -> str | None:
    spec = (getattr(schema, "inputs", {}) or {}).get(to_input)
    if spec is None:
        return None
    return _normalize_type(getattr(spec, "type", None))


def _normalize_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text in {"*", "UNKNOWN"}:
        return None
    return text


def socket_types_compatible(output_type: Any, input_type: Any) -> bool:
    """Return whether a Comfy output socket type can connect to an input type.

    ComfyUI declares several sockets as comma-delimited unions (e.g. ``Preview3D``
    accepts ``STRING,FILE_3D_GLB,FILE_3D``); compatibility is set intersection
    over the normalized tokens, not whole-string equality.
    """

    output_tokens = _socket_type_tokens(output_type)
    input_tokens = _socket_type_tokens(input_type)
    if output_tokens is None or input_tokens is None:
        return True
    return bool(output_tokens & input_tokens)


_WILDCARD_TYPE_TOKENS = frozenset({"*", "ANY", "UNKNOWN"})


def _socket_type_tokens(value: Any) -> frozenset[str] | None:
    """Return the normalized token set for a (possibly comma-delimited) type.

    ``None`` means unknown/wildcard — the side imposes no constraint, matching
    :func:`_normalize_type` semantics for scalar values.
    """

    if value is None:
        return None
    tokens = frozenset(
        token
        for token in (part.strip().upper() for part in str(value).split(","))
        if token
    )
    if not tokens or tokens & _WILDCARD_TYPE_TOKENS:
        return None
    return tokens


def _primitive_expected_type(value: Any) -> str | None:
    normalized = _normalize_type(value)
    if normalized in {"INT", "INTEGER"}:
        return "INT"
    if normalized in {"FLOAT", "DOUBLE"}:
        return "FLOAT"
    if normalized in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if normalized in {"STR", "STRING"}:
        return "STRING"
    return None


def _matches_primitive_type(value: Any, expected_type: str) -> bool:
    if expected_type == "INT":
        return _is_int_literal(value)
    if expected_type == "FLOAT":
        return _is_float_literal(value)
    if expected_type == "BOOLEAN":
        return _is_boolean_literal(value)
    if expected_type == "STRING":
        return isinstance(value, str)
    return True


def _is_int_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            int(text, 10)
        except ValueError:
            return False
        return True
    return False


def _is_float_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
        except ValueError:
            return False
        return True
    return False


def _is_boolean_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "false"}
    return False


def _is_api_link(value: Any) -> bool:
    return is_canonical_api_link(value)


def _truncate(value: Any, n: int = 120) -> str:
    text = repr(value)
    if len(text) <= n:
        return text
    return text[: max(0, n - 3)] + "..."


def _truncate_dynamic_count_value(value: Any, n: int = 120) -> str:
    """Render a rejected count without expanding hostile values."""
    if isinstance(value, str):
        if len(value) <= n:
            return repr(value)
        return repr(value[: max(0, n - 3)])[:-1] + "..."
    if type(value) is int:
        if -_DYNAMIC_VALIDATION_WORK_LIMIT <= value <= _DYNAMIC_VALIDATION_WORK_LIMIT:
            return repr(value)
        return "<int outside validation work bound>"
    if isinstance(value, (bool, float)):
        return repr(value)
    return f"<{type(value).__name__}>"


_NO_MATCH = object()


def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
    if value in choices:
        return _NO_MATCH
    if not isinstance(value, str):
        return _NO_MATCH
    normalized_value = _portable_choice_key(value)
    basename_value = normalized_value.rsplit("/", 1)[-1]
    matches = [
        choice
        for choice in choices
        if isinstance(choice, str)
        and (
            _portable_choice_key(choice) == normalized_value
            or _portable_choice_key(choice).rsplit("/", 1)[-1] == basename_value
        )
    ]
    return matches[0] if len(matches) == 1 else _NO_MATCH


def _portable_choice_key(value: str) -> str:
    return value.replace("\\", "/").strip()


def _is_dynamic_file_choice(class_type: str, input_name: str) -> bool:
    """Return whether a Comfy enum is a runtime file picker, not a semantic enum.

    Object-info choices for these inputs reflect files present in the active
    input directory when object_info was fetched. Task scratchpads often copy
    images/videos immediately before queueing, so treating stale file-picker
    choices as hard schema errors rejects valid runs. Model/checkpoint enums are
    intentionally not listed here.
    """

    return (class_type, input_name) in {
        ("LoadImage", "image"),
        ("LoadVideo", "video"),
        ("LoadVideo", "file"),
        ("VHS_LoadVideo", "video"),
        ("VHS_LoadVideo", "file"),
    }


def _schema_accepts_dict(spec: Any) -> bool:
    typ = getattr(spec, "type", None)
    if typ is None:
        return False
    return str(typ).strip().upper() in {"DICT", "JSON", "*"}


def advisory_validation_for_precedent(
    issues: list[Any],
    *,
    route: str | None = None,
) -> list[dict[str, Any]]:
    """Build advisory task-satisfaction entries from validation issues.

    When *route* is precedent_research, every validation issue is recast
    as an advisory task-satisfaction entry with satisfaction="advisory"
    so the precedent-adaptation path can surface schema concerns without
    blocking Apply or Queue.

    When *route* is anything else, returns an empty list (issues remain
    structural gate blockers).
    """
    if route != "precedent_research":
        return []
    entries: list[dict[str, Any]] = []
    for issue in issues:
        code = getattr(issue, "code", None) or (issue.get("code") if isinstance(issue, dict) else None)
        message = getattr(issue, "message", None) or (issue.get("message") if isinstance(issue, dict) else str(issue))
        entries.append(
            {
                "check": f"schema:{code}" if code else "schema:validation",
                "status": "advisory",
                "satisfaction": "advisory",
                "description": str(message)[:500],
            }
        )
    return entries
