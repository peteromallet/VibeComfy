from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field, replace
from enum import Enum
import math
import warnings
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy._compile import _resolve as helper_resolve
from vibecomfy._compile import _widgets as widget_aliases
from vibecomfy._compile import _helpers as workflow_helpers
from vibecomfy._compile._graph import is_canonical_api_link
from vibecomfy.errors import VibeComfyError
from vibecomfy.handles import Handle

if TYPE_CHECKING:
    from vibecomfy.schema.provider import SchemaProvider
    from vibecomfy.security.provenance import Provenance


# ComfyUI-specific validation policy lives in the neutral contracts layer.
# Re-exported here so existing `from vibecomfy.workflow import OPAQUE_COMPONENT_CLASS_RE`
# imports keep working.
from vibecomfy.contracts.validation import (  # noqa: E402
    OPAQUE_COMPONENT_CLASS_RE,
    comfyui_node_issue_specs,
)

# WorkflowSummary is the typed contract for LLM-generated summaries stored
# under ``workflow.metadata['summary']``.  Re-exported so consumers can
# import from ``vibecomfy.workflow`` without reaching into contracts.
from vibecomfy.contracts.summary import WorkflowSummary  # noqa: E402, F401


# Stored-envelope format version. The IR is the schema source: writers stamp
# this via ``VibeWorkflow.to_envelope()`` rather than a script-local constant.
FORMAT_VERSION = "1.0"
VIBECOMFY_FORMAT_VERSION = FORMAT_VERSION


def _to_plain(obj: Any) -> Any:
    """Lossless walk of public dataclass fields (skip private ``_`` names)."""
    if dataclasses.is_dataclass(obj):
        result: dict[str, Any] = {}
        for field_info in dataclasses.fields(obj):
            if field_info.name.startswith("_"):
                continue
            value = getattr(obj, field_info.name)
            # New semantic extensions are optional.  Omitting their empty
            # defaults keeps older envelopes byte-compatible while authored
            # recursive/variant data is serialized normally.
            if field_info.name in {
                "definitions", "interfaces", "boundary_ports", "virtual_wires", "variants"
            } and not value:
                continue
            if field_info.name == "default_variant" and value is None:
                continue
            result[field_info.name] = _to_plain(value)
        return result
    if isinstance(obj, dict):
        return {str(key): _to_plain(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(value) for value in obj]
    return obj


def _geometry_error(value: Any) -> str | None:
    """Return why a first-class geometry value is invalid, if it is invalid."""
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2:
        return "must be a list containing exactly two coordinates"
    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
        return "coordinates must be numeric (not booleans)"
    try:
        finite = all(math.isfinite(float(coord)) for coord in value)
    except (OverflowError, TypeError, ValueError):
        finite = False
    if not finite:
        return "coordinates must be finite"
    return None


def _invalid_geometry_details(workflow: "VibeWorkflow") -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for node_id, node in workflow.nodes.items():
        for field_name in ("pos", "size"):
            value = getattr(node, field_name)
            error = _geometry_error(value)
            if error is not None:
                details.append(
                    {
                        "node_id": str(node_id),
                        "field": field_name,
                        "value": value,
                        "reason": error,
                    }
                )
    return details


@dataclass(slots=True)
class WorkflowSource:
    id: str
    path: str | None = None
    source_type: str = "unknown"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowRequirements:
    models: list[str] = field(default_factory=list)
    custom_nodes: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)
    missing_nodes: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RawWidgetPayload:
    values: Any
    shape: str
    source: str
    has_dict_rows: bool
    length: int


# ---------------------------------------------------------------------------
# Node mode (Law 5, batch 4): the IR stores the semantic NodeMode enum; the
# LiteGraph integer (0/2/4) is only an emit-time derivation.  Defined before
# VibeNode so the dataclass default can reference the enum directly.
# ---------------------------------------------------------------------------

_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)


class NodeMode(str, Enum):
    """Semantic node mode carried by the IR (Law 5, batch 4).

    ``VibeNode.mode`` stores the semantic value; the LiteGraph integer
    (0/2/4) is only an emit-time derivation via :func:`mode_to_litegraph`.
    """

    ENABLED = "enabled"
    MUTED = "muted"
    BYPASSED = "bypassed"


def mode_to_litegraph(mode: Any) -> int:
    """Derive the LiteGraph mode integer (0/2/4) from the IR semantic value."""
    if isinstance(mode, NodeMode):
        if mode is NodeMode.MUTED:
            return _MODE_MUTED
        if mode is NodeMode.BYPASSED:
            return _MODE_BYPASS
        return 0
    if isinstance(mode, str):
        if mode in {"muted", "never"}:
            return _MODE_MUTED
        if mode in {"bypassed", "bypass"}:
            return _MODE_BYPASS
        return 0
    if isinstance(mode, int):
        # Legacy/hand-built nodes may still carry the raw integer.
        return mode if mode in (0, _MODE_MUTED, _MODE_BYPASS) else 0
    return 0


def litegraph_to_mode(mode: Any) -> NodeMode:
    """Convert a LiteGraph mode integer (or already-semantic value) to NodeMode."""
    if isinstance(mode, NodeMode):
        return mode
    if isinstance(mode, str):
        if mode in {"never", "muted"}:
            return NodeMode.MUTED
        if mode in {"bypass", "bypassed"}:
            return NodeMode.BYPASSED
        if mode in {"live", "enabled"}:
            return NodeMode.ENABLED
        try:
            return NodeMode(mode)
        except ValueError:
            return NodeMode.ENABLED
    if mode == _MODE_MUTED:
        return NodeMode.MUTED
    if mode == _MODE_BYPASS:
        return NodeMode.BYPASSED
    return NodeMode.ENABLED


def _normalize_native_port_names(
    value: list[str | None] | tuple[str | None, ...] | None,
    *,
    field_name: str,
) -> list[str | None] | None:
    """Validate and detach an exact instance socket-name roster."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be a list or tuple")
    result: list[str | None] = []
    seen: set[str] = set()
    for index, name in enumerate(value):
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"{field_name}[{index}] must be a nonblank string or null"
                )
            if name in seen:
                raise ValueError(f"{field_name} contains duplicate name {name!r}")
            seen.add(name)
        result.append(name)
    return result


@dataclass(slots=True)
class VibeNode:
    id: str
    class_type: str
    pack: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    widgets: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    uid: str = ""
    raw_widgets: RawWidgetPayload | None = None
    mode: "NodeMode" = NodeMode.ENABLED
    pos: list[float] | None = None
    size: list[float] | None = None
    native_input_names: list[str | None] | None = None
    native_output_names: list[str | None] | None = None

    def __post_init__(self) -> None:
        self.native_input_names = _normalize_native_port_names(
            self.native_input_names, field_name="native_input_names"
        )
        self.native_output_names = _normalize_native_port_names(
            self.native_output_names, field_name="native_output_names"
        )

    @property
    def provenance(self) -> str:
        """Read-through to the S4 provenance tag; fail-closed on missing/None."""
        from vibecomfy.security import provenance as _prov

        return _prov.read(self)


@dataclass(slots=True)
class VibeEdge:
    from_node: str
    from_output: str
    to_node: str
    to_input: str


@dataclass(slots=True)
class VibeInput:
    name: str
    node_id: str
    field: str
    value: Any = None
    type: str | None = None
    default: Any = None
    required: bool = False
    range: Any = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    media_semantics: str | None = None
    allow_missing_target: bool = False

    @property
    def media(self) -> str | None:
        return self.media_semantics

    @media.setter
    def media(self, value: str | None) -> None:
        self.media_semantics = value


@dataclass(slots=True)
class VibeOutput:
    node_id: str
    output_type: str
    name: str | None = None
    artifact_kind: str | None = None
    mime_type: str | None = None
    filename_prefix: str | None = None
    expected_cardinality: str | int | None = None


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)


def _graph_integrity_issues(
    nodes: dict[str, VibeNode],
    edges: list[VibeEdge],
) -> list[ValidationIssue]:
    """Return canonical node-identity and edge-endpoint defects."""
    issues: list[ValidationIssue] = []
    node_ids = {str(node_id) for node_id in nodes}
    for mapping_key, node in nodes.items():
        key = str(mapping_key)
        if key != node.id:
            issues.append(
                ValidationIssue(
                    "node_identity_mismatch",
                    f"node mapping key {key!r} must equal node.id {node.id!r}",
                    detail={"mapping_key": key, "node_id": node.id},
                )
            )
    for index, edge in enumerate(edges):
        source_id = str(edge.from_node)
        target_id = str(edge.to_node)
        missing_source = source_id not in node_ids
        missing_target = target_id not in node_ids
        if not missing_source and not missing_target:
            continue
        code = (
            "missing_edge_endpoints"
            if missing_source and missing_target
            else "missing_edge_source"
            if missing_source
            else "missing_edge_target"
        )
        issues.append(
            ValidationIssue(
                code,
                f"edge {index}: endpoint node ids {source_id!r}/{target_id!r} "
                "must exist in nodes",
                detail={
                    "edge_index": index,
                    "source_node_id": source_id,
                    "target_node_id": target_id,
                    "missing_source": missing_source,
                    "missing_target": missing_target,
                },
            )
        )
    return issues


class WorkflowCompileError(VibeComfyError):
    """Compile-time graph assembly failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        next_action: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail or {}
        super().__init__(f"{code}: {message}", next_action=next_action)


@dataclass
class VibeWorkflow:
    id: str
    source: WorkflowSource
    nodes: dict[str, VibeNode] = field(default_factory=dict)
    edges: list[VibeEdge] = field(default_factory=list)
    inputs: dict[str, VibeInput] = field(default_factory=dict)
    outputs: list[VibeOutput] = field(default_factory=list)
    requirements: WorkflowRequirements = field(default_factory=WorkflowRequirements)
    metadata: dict[str, Any] = field(default_factory=dict)
    strict_types: bool = False
    groups: list[dict[str, Any]] = field(default_factory=list)
    # Recursive semantics stay on the existing IR.  These are deliberately
    # plain JSON-shaped values, not a second model hierarchy.
    definitions: dict[str, Any] = field(default_factory=dict)
    interfaces: dict[str, Any] = field(default_factory=dict)
    boundary_ports: list[dict[str, Any]] = field(default_factory=list)
    virtual_wires: dict[str, Any] = field(default_factory=dict)
    variants: dict[str, dict[str, object]] = field(default_factory=dict)
    default_variant: str | None = None
    _id_map: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _manual_input_names: set[str] = field(default_factory=set, init=False, repr=False)
    _uid_counter: int = field(default=0, init=False, repr=False)
    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)

    def __enter__(self) -> "VibeWorkflow":
        from vibecomfy.workflow_context import active_workflow, bind_workflow

        # If ``new_workflow()`` already eagerly bound this workflow (the post-
        # revert default for emitted templates), reuse that binding rather than
        # raising — the ``with`` form is purely scoping sugar in that case.
        if self._workflow_context_token is not None and active_workflow() is self:
            return self
        if self._workflow_context_token is not None:
            raise RuntimeError(
                "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
                "block is still active."
            )
        self._workflow_context_token = bind_workflow(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        from vibecomfy.workflow_context import reset_workflow

        token = self._workflow_context_token
        if token is not None:
            reset_workflow(token)
            self._workflow_context_token = None

    def confirm_node(self, node_id: str) -> "VibeWorkflow":
        """Promote ``untrusted_source`` provenance on ``node_id`` → ``user_confirmed``.

        Idempotent on already-trusted nodes. Raises ``KeyError`` if ``node_id``
        is unknown so callers cannot silently confirm a non-existent node.
        """
        from vibecomfy.security import provenance as _prov

        node = self.nodes[node_id]
        _prov.confirm(node)
        return self

    def set_prompt(self, value: str) -> "VibeWorkflow":
        return self.set_input("prompt", value)

    def set_seed(self, value: int) -> "VibeWorkflow":
        return self.set_input("seed", int(value))

    def set_steps(self, value: int) -> "VibeWorkflow":
        return self.set_input("steps", int(value))

    def set_model(self, value: str) -> "VibeWorkflow":
        return self.set_input("model", value)

    def copy(self) -> "VibeWorkflow":
        """Derived, complete deep copy.

        The dataclass walk (``copy.deepcopy``) copies every public field —
        including ``groups`` and per-node ``mode`` — plus the private
        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``).
        A bound workflow's live ``contextvars.Token`` cannot be meaningfully
        deep-copied, so the deepcopy memo maps it to ``None`` up front; every
        clone is therefore unbound (``_workflow_context_token is None``).
        """
        memo = {id(self._workflow_context_token): None}
        return copy.deepcopy(self, memo=memo)

    def identity_issues(self) -> list[ValidationIssue]:
        """Return fail-closed authored identity defects without mutating the IR."""
        from vibecomfy.identity.uid import UIDValidationError, validate_local_uid

        issues: list[ValidationIssue] = []
        if not isinstance(self.id, str) or not self.id.strip():
            issues.append(ValidationIssue("invalid_workflow_id", "workflow id must be a nonblank string"))
        if not isinstance(self.source.id, str) or not self.source.id.strip():
            issues.append(ValidationIssue("invalid_source_id", "source id must be a nonblank string"))
        elif self.source.id != self.id:
            issues.append(
                ValidationIssue(
                    "workflow_identity_mismatch",
                    f"source identity {self.source.id!r} must equal workflow id {self.id!r}",
                    detail={"workflow_id": self.id, "source_id": self.source.id},
                )
            )
        seen: dict[str, str] = {}
        for node_id, node in self.nodes.items():
            try:
                uid = validate_local_uid(node.uid, field=f"node {node_id!r} uid")
            except UIDValidationError as exc:
                issues.append(ValidationIssue("invalid_node_uid", str(exc), detail={"node_id": str(node_id)}))
                continue
            if uid in seen:
                issues.append(
                    ValidationIssue(
                        "duplicate_node_uid",
                        f"duplicate node uid {uid!r} for nodes {seen[uid]!r} and {node_id!r}",
                        detail={"uid": uid, "first_node_id": seen[uid], "node_id": str(node_id)},
                    )
                )
            else:
                seen[uid] = str(node_id)
        return issues

    def validate_identity(self) -> ValidationReport:
        """Validate the durable identity boundary as a standalone gate."""
        issues = self.identity_issues()
        return ValidationReport(ok=not issues, issues=issues)

    def _semantic_source(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Read the Python-owned recursive semantic fields only."""
        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        definitions = self.definitions or metadata.get("definitions") or {}
        virtual_wires = self.virtual_wires or {}
        return definitions, virtual_wires

    @staticmethod
    def _semantic_node_metadata(node: VibeNode) -> dict[str, Any]:
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        rejected = metadata.get("rejected")
        if rejected:
            raise ValueError(f"node {node.id!r} contains rejected metadata")
        semantic = metadata.get("semantic", metadata.get("semantic_metadata", {}))
        if semantic is None:
            return {}
        if not isinstance(semantic, dict):
            raise ValueError(f"node {node.id!r} semantic metadata must be a mapping")
        return copy.deepcopy(semantic)

    def _semantic_edge_records(self) -> list[dict[str, Any]]:
        """Derive edge identity from scoped endpoints; never mint edge UIDs."""
        from vibecomfy.identity.uid import validate_local_uid

        by_id = {str(node_id): node for node_id, node in self.nodes.items()}
        by_uid = {node.uid: node for node in self.nodes.values() if node.uid}
        records: set[tuple[str, str, str, str, str]] = set()
        for edge in self.edges:
            source = str(edge.from_node)
            target = str(edge.to_node)
            if "#" in source or "/" in source or "#" in target or "/" in target:
                raise ValueError("qualified or cross-scope ordinary edge endpoints are not allowed")
            source_node = by_id.get(source) or by_uid.get(source)
            target_node = by_id.get(target) or by_uid.get(target)
            if source_node is None or target_node is None:
                raise ValueError(f"ordinary edge endpoint {source!r}/{target!r} is not local to root scope")
            from_uid = validate_local_uid(source_node.uid, field="edge.from_uid")
            to_uid = validate_local_uid(target_node.uid, field="edge.to_uid")
            record = ("", from_uid, str(edge.from_output), to_uid, str(edge.to_input))
            records.add(record)
        return [
            {
                "scope_path": scope,
                "from_uid": source,
                "from_port": output,
                "to_uid": target,
                "to_port": input_name,
            }
            for scope, source, output, target, input_name in sorted(records)
        ]

    @staticmethod
    def _strip_recursive_presentation(value: Any) -> Any:
        if isinstance(value, dict):
            presentation = {"pos", "size", "properties", "graphUuid", "flags", "order", "color", "bgcolor"}
            return {
                str(key): VibeWorkflow._strip_recursive_presentation(item)
                for key, item in value.items()
                if key not in presentation and not str(key).startswith("_")
            }
        if isinstance(value, list):
            return [VibeWorkflow._strip_recursive_presentation(item) for item in value]
        return value

    def _semantic_definitions(
        self,
        raw: Any,
        parent_scope: tuple[str, ...] = (),
        _active_definition_ids: set[int] | None = None,
    ) -> list[dict[str, Any]]:
        from vibecomfy.identity.scope import compose_scope_path, sg_key
        if not raw:
            return []
        if isinstance(raw, dict) and isinstance(raw.get("subgraphs"), (list, tuple)):
            entries = list(raw["subgraphs"])
        elif isinstance(raw, dict):
            entries = list(raw.values())
        elif isinstance(raw, (list, tuple)):
            entries = list(raw)
        else:
            raise ValueError("definitions must be a JSON-shaped mapping or sequence")
        active = _active_definition_ids if _active_definition_ids is not None else set()
        result: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("each definition must be a mapping")
            identity = id(entry)
            if identity in active:
                raise WorkflowCompileError(
                    "recursive_definition_cycle",
                    "recursive definition object graph cannot be compiled",
                )
            active.add(identity)
            key = entry.get("sg_key")
            derived = sg_key(entry)
            if key is not None and key != derived:
                raise ValueError(f"definition sg_key {key!r} does not match its structural identity")
            key = derived
            scope = compose_scope_path((*parent_scope, key))
            nested = entry.get("definitions")
            # Exclude recursive children from the presentation scrubber; they
            # are walked below with the active object-identity guard.
            clean = self._strip_recursive_presentation(
                {key: value for key, value in entry.items() if key != "definitions"}
            )
            clean["sg_key"] = key
            clean["scope_path"] = scope
            if nested:
                clean["definitions"] = self._semantic_definitions(
                    nested, (*parent_scope, key), active
                )
            result.append(clean)
            active.remove(identity)
        result.sort(key=lambda item: (str(item["scope_path"]), str(item["sg_key"])))
        return result

    def _semantic_definition_nodes(
        self,
        raw: Any,
        parent_scope: tuple[str, ...] = (),
        _active_definition_ids: set[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Flatten definition-local nodes into the same scoped node view."""
        from vibecomfy.identity.scope import compose_scope_path, sg_key
        from vibecomfy.identity.uid import validate_local_uid
        if not raw:
            return []
        if isinstance(raw, dict) and isinstance(raw.get("subgraphs"), (list, tuple)):
            entries = list(raw["subgraphs"])
        elif isinstance(raw, dict):
            entries = list(raw.values())
        elif isinstance(raw, (list, tuple)):
            entries = list(raw)
        else:
            raise ValueError("definitions must be a JSON-shaped mapping or sequence")
        active = _active_definition_ids if _active_definition_ids is not None else set()
        result: list[dict[str, Any]] = []
        for definition in entries:
            if not isinstance(definition, dict):
                continue
            identity = id(definition)
            if identity in active:
                raise WorkflowCompileError(
                    "recursive_definition_cycle",
                    "recursive definition object graph cannot be compiled",
                )
            active.add(identity)
            key = definition.get("sg_key") or sg_key(definition)
            scope = compose_scope_path((*parent_scope, key))
            raw_nodes = definition.get("nodes", [])
            node_entries = list(raw_nodes.values()) if isinstance(raw_nodes, dict) else list(raw_nodes) if isinstance(raw_nodes, (list, tuple)) else []
            for entry in node_entries:
                if not isinstance(entry, dict):
                    continue
                local = entry.get("uid")
                if not isinstance(local, str) or not local.strip():
                    local = entry.get("id")
                uid = validate_local_uid(str(local) if local is not None else "", field="definition node uid")
                result.append({
                    "scope_path": scope,
                    "uid": uid,
                    "class_type": str(entry.get("class_type", entry.get("type", "Unknown"))),
                    "inputs": copy.deepcopy(entry.get("inputs", {})) if isinstance(entry.get("inputs", {}), dict) else {},
                    "widgets": copy.deepcopy(entry.get("widgets", entry.get("widgets_values", {}))),
                    "mode": litegraph_to_mode(entry.get("mode", NodeMode.ENABLED)).value,
                    "metadata": copy.deepcopy(entry.get("semantic", {})) if isinstance(entry.get("semantic", {}), dict) else {},
                })
            nested = definition.get("definitions")
            if nested:
                result.extend(
                    self._semantic_definition_nodes(nested, (*parent_scope, key), active)
                )
            active.remove(identity)
        result.sort(key=lambda item: (item["scope_path"], item["uid"], item["class_type"]))
        return result

    def semantic_projection(self) -> dict[str, Any]:
        """Return the deterministic Python-owned semantic projection."""
        from vibecomfy.identity.uid import validate_local_uid

        issues = self.identity_issues()
        if issues:
            raise ValueError(issues[0].message)
        definitions, virtual_wires = self._semantic_source()
        nodes = []
        for node in self.nodes.values():
            uid = validate_local_uid(node.uid, field=f"node {node.id!r} uid")
            nodes.append(
                {
                    "scope_path": "",
                    "uid": uid,
                    "class_type": node.class_type,
                    "inputs": copy.deepcopy(node.inputs),
                    "widgets": copy.deepcopy(node.widgets),
                    "mode": litegraph_to_mode(node.mode).value,
                    "metadata": self._semantic_node_metadata(node),
                    "native_input_names": copy.deepcopy(node.native_input_names),
                    "native_output_names": copy.deepcopy(node.native_output_names),
                }
            )
        nodes.sort(key=lambda item: (item["scope_path"], item["uid"], item["class_type"]))
        nodes.extend(self._semantic_definition_nodes(definitions))
        nodes.sort(key=lambda item: (item["scope_path"], item["uid"], item["class_type"]))
        node_keys = [(item["scope_path"], item["uid"]) for item in nodes]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("duplicate or colliding scoped node UID")
        semantic_definitions = self._semantic_definitions(definitions)
        definition_keys = [item["scope_path"] for item in semantic_definitions]
        if len(definition_keys) != len(set(definition_keys)):
            raise ValueError("duplicate or colliding subgraph definition identity")
        requirements = {
            field_name: sorted(str(value) for value in getattr(self.requirements, field_name))
            for field_name in ("models", "custom_nodes", "missing_models", "missing_nodes", "unsupported")
        }
        inputs = [
            {
                "name": item.name, "node_id": item.node_id, "field": item.field,
                "type": item.type, "default": copy.deepcopy(item.default),
                "required": item.required, "range": copy.deepcopy(item.range),
                "aliases": sorted(item.aliases), "media_semantics": item.media_semantics,
            }
            for item in self.inputs.values()
        ]
        inputs.sort(key=lambda item: item["name"])
        outputs = [_to_plain(item) for item in self.outputs]
        outputs.sort(key=lambda item: (str(item.get("name") or ""), str(item.get("node_id")), str(item.get("output_type"))))
        variants: dict[str, dict[str, object]] = {}
        for name, overrides in self.variants.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(overrides, dict):
                raise ValueError("variants must be a flat mapping of names to override maps")
            variants[name] = {str(key): copy.deepcopy(overrides[key]) for key in sorted(overrides)}
        if self.default_variant is not None and self.default_variant not in variants:
            raise ValueError(f"default_variant {self.default_variant!r} is not defined")
        projection = {
            "id": self.id,
            "version": FORMAT_VERSION,
            "nodes": nodes,
            "edges": self._semantic_edge_records(),
            "definitions": semantic_definitions,
            "interfaces": copy.deepcopy(self.interfaces),
            "boundary_ports": copy.deepcopy(self.boundary_ports),
            "virtual_wires": copy.deepcopy(virtual_wires),
            "variants": variants,
            "default_variant": self.default_variant,
            "requirements": requirements,
            "inputs": inputs,
            "outputs": outputs,
        }
        return projection

    def semantic_digest(self) -> str:
        from vibecomfy.testing.canonical import canonical_digest
        return canonical_digest(self.semantic_projection())

    # Private spelling retained for callers that treat the projection as an
    # internal compiler leaf; both names intentionally delegate to one source.
    def _semantic_projection(self) -> dict[str, Any]:
        return self.semantic_projection()

    def canonical_semantic_bytes(self) -> bytes:
        from vibecomfy.testing.canonical import canonical_bytes
        return canonical_bytes(self.semantic_projection())

    def _with_selection(self, variant: str | None, run_inputs: dict[str, Any] | None) -> "VibeWorkflow":
        selected = self.default_variant if variant is None else variant
        if selected is None and not run_inputs:
            return self
        if selected is not None and selected not in self.variants:
            raise ValueError(f"unknown workflow variant {selected!r}")
        result = self.copy()
        if selected is not None:
            by_uid = {node.uid: node for node in result.nodes.values()}
            for key, value in result.variants[selected].items():
                if "." not in key:
                    raise ValueError(f"variant override {key!r} must be node_uid.widget")
                uid, field_name = key.rsplit(".", 1)
                node = by_uid.get(uid)
                if node is None and _apply_definition_variant(result, uid, field_name, value):
                    continue
                if node is None:
                    raise ValueError(f"variant override references unknown node UID {uid!r}")
                if field_name in {"__mode__", "mode"}:
                    node.mode = litegraph_to_mode(value)
                elif field_name in {"enabled", "enable", "disabled", "disable"}:
                    node.mode = NodeMode.ENABLED if bool(value) else NodeMode.MUTED
                elif field_name in node.widgets:
                    node.widgets[field_name] = copy.deepcopy(value)
                elif field_name in node.inputs or field_name in (node.native_input_names or ()) or field_name in (node.metadata.get("input_names", ()) if isinstance(node.metadata, dict) else ()):
                    node.inputs[field_name] = copy.deepcopy(value)
                else:
                    raise ValueError(
                        f"variant override field {field_name!r} is not a declared value or mode field"
                    )
        if run_inputs:
            for name, value in run_inputs.items():
                result.set_input(name, value)
        return result

    def to_envelope(self) -> dict[str, Any]:
        """Serialize this IR as the stored vibe envelope.

        Public dataclass fields plus ``vibecomfy_format_version``. No
        ``compiled_api`` — ``compile(\\\"api\\\")`` is a function, not stored data.
        Transport stamps such as ``workflow_id`` are applied by callers after
        this, not here.

        Law 1 (lossless door): when this IR was decoded from a serialized Vibe
        envelope by :func:`from_envelope` and is UNTOUCHED since ingest, the
        raw envelope bytes are reproduced verbatim (``to_envelope(from_envelope(J))
        == J``) — the door-owned wire fields (raw node geometry presence,
        opaque keys, key order) are preserved exactly.  The untouched-graph
        restore decision is door-owned: this serializer delegates the
        fingerprint comparison and raw-byte restore to the ingest door and
        only renders the IR (plus the format stamp) for edited graphs.
        """
        integrity_issues = _graph_integrity_issues(self.nodes, self.edges)
        if integrity_issues:
            raise ValueError(integrity_issues[0].message)
        _raise_embedded_api_links(self, surface="envelope serialization")
        invalid_geometry = _invalid_geometry_details(self)
        if invalid_geometry:
            detail = invalid_geometry[0]
            raise ValueError(
                f"node {detail['node_id']!r}: {detail['field']} {detail['reason']}"
            )
        from vibecomfy.ingest.normalize import (  # noqa: PLC0415
            _restore_untouched_envelope,
        )

        restored = _restore_untouched_envelope(self)
        if restored is not None:
            return restored
        plain = _to_plain(self)
        plain["vibecomfy_format_version"] = FORMAT_VERSION
        # The door blob is door-owned wire data, never stored envelope content.
        metadata_plain = plain.get("metadata")
        if isinstance(metadata_plain, dict):
            metadata_plain.pop("_ui_door", None)
        return plain

    @classmethod
    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
        """Fail-closed decoder for a serialized vibe envelope.

        Rich ``nodes`` + ``edges`` are the only structural authority.
        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
        no partial graph is returned. Implementation is the existing ingest
        decoder — this method does not relax it.
        """
        from vibecomfy.ingest.normalize import _decode_serialized_vibe

        workflow = _decode_serialized_vibe(raw)
        # The ingest door owns legacy decoding, but the semantic extensions
        # are plain top-level IR fields and can be restored here without
        # teaching that compatibility boundary a second recursive model.
        for field_name in ("definitions", "interfaces", "boundary_ports", "virtual_wires", "variants", "default_variant"):
            if field_name in raw:
                setattr(workflow, field_name, copy.deepcopy(raw[field_name]))
        return workflow

    def clone(self) -> "VibeWorkflow":
        return self.copy()

    def finalize_metadata(self) -> "VibeWorkflow":
        from vibecomfy.metadata import OUTPUT_NODE_NAMES, _infer_requirements, _register_common_inputs

        manual_inputs = {
            name: replace(vibe_input)
            for name, vibe_input in self.inputs.items()
            if name in self._manual_input_names and self._input_target_exists(vibe_input)
        }
        self._manual_input_names.intersection_update(manual_inputs)
        self.inputs.clear()
        self.outputs.clear()
        for node_id, node in self.nodes.items():
            _register_common_inputs(self, node_id, node)
            if node.class_type in OUTPUT_NODE_NAMES:
                self.outputs.append(VibeOutput(node_id=node_id, output_type=node.class_type))
        self.inputs.update(manual_inputs)
        self.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
        self.requirements = _infer_requirements(self)
        return self

    def finalize(
        self,
        public_inputs: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
        output_node: Any = None,
        output_kind: str | None = None,
        **bind_kwargs: Any,
    ) -> "VibeWorkflow":
        """Finalize ready-template public inputs and output binding.

        ``metadata`` is optional for the v2.5 method form; when omitted, the
        workflow's current metadata is used. The legacy free function remains
        available in ``vibecomfy.templates.finalize``.
        """
        from vibecomfy.templates import _finalize_impl

        return _finalize_impl(
            self,
            public_inputs,
            dict(self.metadata if metadata is None else metadata),
            output_node=output_node,
            output_kind=output_kind,
            **bind_kwargs,
        )

    def register_input(
        self,
        name: str,
        node_id: str,
        field: str,
        value: Any = None,
        *,
        type: str | None = None,
        default: Any = None,
        required: bool = False,
        range: Any = None,
        aliases: list[str] | tuple[str, ...] | None = None,
        media_semantics: str | None = None,
        media: str | None = None,
        allow_missing_target: bool = False,
    ) -> "VibeWorkflow":
        if media_semantics is not None and media is not None and media_semantics != media:
            raise ValueError(
                f"register_input({name!r}): media_semantics and legacy media "
                "must match when both are provided"
            )
        resolved_media_semantics = media_semantics if media_semantics is not None else media
        alias_tuple = _normalize_input_aliases(aliases)
        self._validate_input_aliases(name, alias_tuple)
        self._validate_input_target(name, node_id, field, allow_missing=allow_missing_target)
        if allow_missing_target:
            node = self.nodes[str(node_id)]
            if field not in node.inputs and field not in node.widgets:
                if not self._is_schema_default_target(str(node_id), field, value):
                    raise ValueError(
                        f"register_input({name!r}): missing target {node.class_type}.{field} "
                        "may only be omitted when its value is the schema default"
                    )
        self.inputs[name] = VibeInput(
            name=name,
            node_id=str(node_id),
            field=field,
            value=value,
            type=type,
            default=value if default is None else default,
            required=required,
            range=range,
            aliases=alias_tuple,
            media_semantics=resolved_media_semantics,
            allow_missing_target=allow_missing_target,
        )
        self._manual_input_names.add(name)
        return self

    def set_input(self, name: str, value: Any) -> "VibeWorkflow":
        target = self._resolve_input(name)
        if target is None:
            raise ValueError(self._unknown_input_message(name))

        node = self.nodes.get(target.node_id)
        if node is None:
            raise ValueError(
                f"set_input({name!r}) cannot update public input {target.name!r}: "
                f"target node {target.node_id!r} is missing from workflow {self.id!r}. "
                f"Registered target: {target.node_id}.{target.field}."
            )
        if target.field in node.inputs:
            node.inputs[target.field] = value
        elif target.field in node.widgets:
            node.widgets[target.field] = value
        elif self._is_valid_missing_target(target):
            node.inputs[target.field] = value
        else:
            available = _format_available_names([*node.inputs.keys(), *node.widgets.keys()])
            raise ValueError(
                f"set_input({name!r}) cannot update public input {target.name!r}: "
                f"target field {target.field!r} is missing from node {target.node_id!r} "
                f"({node.class_type}) in workflow {self.id!r}. "
                f"Available fields on node {target.node_id!r}: {available}."
            )
        target.value = value
        return self

    def _resolve_input(self, name: str) -> VibeInput | None:
        if name in self.inputs:
            return self.inputs[name]
        matches = [item for item in self.inputs.values() if name in item.aliases]
        if len(matches) > 1:
            matched_names = _format_available_names(item.name for item in matches)
            raise ValueError(
                f"Input alias {name!r} is ambiguous in workflow {self.id!r}; "
                f"it matches public inputs: {matched_names}."
            )
        return matches[0] if matches else None

    def _unknown_input_message(self, name: str) -> str:
        available_names = _format_available_names(self.inputs.keys())
        aliases = {
            alias: item.name
            for item in self.inputs.values()
            for alias in item.aliases
        }
        if aliases:
            alias_text = ", ".join(
                f"{alias!r} -> {primary!r}" for alias, primary in sorted(aliases.items())
            )
        else:
            alias_text = "<none>"
        return (
            f"set_input({name!r}) has no registered public input or alias in "
            f"workflow {self.id!r}. Available public inputs: {available_names}. "
            f"Available aliases: {alias_text}. Register the input before calling set_input()."
        )

    def _validate_input_aliases(self, name: str, aliases: tuple[str, ...]) -> None:
        if len(set(aliases)) != len(aliases):
            raise ValueError(f"register_input({name!r}): duplicate aliases are not allowed")
        if name in aliases:
            raise ValueError(f"register_input({name!r}): alias cannot equal its primary input name")
        existing_primary_names = {existing_name for existing_name in self.inputs if existing_name != name}
        if name in {
            alias
            for existing_name, item in self.inputs.items()
            if existing_name != name
            for alias in item.aliases
        }:
            raise ValueError(f"register_input({name!r}): primary input name conflicts with an existing alias")
        primary_conflicts = existing_primary_names.intersection(aliases)
        if primary_conflicts:
            conflict = sorted(primary_conflicts)[0]
            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing primary input")
        existing_aliases = {
            alias
            for existing_name, item in self.inputs.items()
            if existing_name != name
            for alias in item.aliases
        }
        alias_conflicts = existing_aliases.intersection(aliases)
        if alias_conflicts:
            conflict = sorted(alias_conflicts)[0]
            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing alias")

    def _validate_input_target(self, name: str, node_id: str, field: str, *, allow_missing: bool = False) -> None:
        node_key = str(node_id)
        if node_key not in self.nodes:
            raise ValueError(
                f"register_input({name!r}): target node {node_key!r} does not exist "
                f"in workflow {self.id!r}"
            )
        node = self.nodes[node_key]
        if not allow_missing and field not in node.inputs and field not in node.widgets:
            raise ValueError(
                f"register_input({name!r}): field {field!r} not found in "
                f"node {node_key!r} ({node.class_type}) inputs or widgets"
            )

    def _is_schema_default_target(self, node_id: str, field: str, value: Any) -> bool:
        node = self.nodes.get(str(node_id))
        if node is None:
            return False
        from vibecomfy.porting.parity import _is_schema_default_input

        return _is_schema_default_input(node.class_type, field, value)

    def _is_valid_missing_target(self, vibe_input: VibeInput) -> bool:
        node = self.nodes.get(vibe_input.node_id)
        return (
            node is not None
            and vibe_input.allow_missing_target
            and vibe_input.field not in node.inputs
            and vibe_input.field not in node.widgets
            and self._is_schema_default_target(vibe_input.node_id, vibe_input.field, vibe_input.value)
        )

    def _input_target_exists(self, vibe_input: VibeInput) -> bool:
        node = self.nodes.get(vibe_input.node_id)
        return (
            node is not None
            and (
                vibe_input.field in node.inputs
                or vibe_input.field in node.widgets
                or self._is_valid_missing_target(vibe_input)
            )
        )

    def _mint_uid(self, seed: str | None = None) -> str:
        """Mint a never-reused uid using the monotonic counter.

        Counter always increments regardless of whether a seed is provided.
        When seed is given it becomes the local uid component (extrinsic identity).
        When omitted, the counter value provides authored creation-order identity;
        before minting, the counter is reconciled with any pre-existing flat
        auto-minted ``n<positive-integer>`` uids (e.g. imported via envelope
        decode) so the minted uid never collides with one already present.
        The counter only ever moves forward (monotonic).
        """
        from vibecomfy.identity.uid import make_uid
        if seed is None:
            self._reconcile_uid_counter()
        self._uid_counter += 1
        local = seed if seed is not None else f"n{self._uid_counter}"
        return make_uid("", local)

    def _reconcile_uid_counter(self) -> None:
        """Raise ``_uid_counter`` above any existing flat auto-minted ``n<N>`` uids.

        Envelope decode preserves imported uids verbatim while
        ``_uid_counter`` starts at zero, so an unseeded mint would otherwise
        collide with an imported ``n<positive-integer>`` (e.g. ``n1``). Scan
        existing node uids matching the auto-mint shape and move the counter
        forward to the largest N found. Imported uids are never rewritten and
        the counter never decreases (monotonic).
        """
        highest = 0
        for node in self.nodes.values():
            digits = node.uid[1:] if node.uid.startswith("n") else ""
            if digits.isdecimal() and int(digits) > 0:
                highest = max(highest, int(digits))
        if highest >= self._uid_counter:
            self._uid_counter = highest

    def add_node(
        self,
        class_type: str,
        _id: str | None = None,
        *,
        uid: str | None = None,
        _provenance: "Provenance | None" = None,
        **inputs: Any,
    ) -> VibeNode:
        """Add a node to the workflow.

        ``uid`` is keyword-only and sets node.uid verbatim when provided.
        Extrinsic-seed minting via _mint_uid belongs in node()/raw_call callers,
        not here, so add_node stays uid-neutral by default.

        ``_provenance`` is a reserved keyword-only parameter declared BEFORE
        ``**inputs`` so callers cannot accidentally bind it from an inputs
        dict. When ``None`` it falls back to the ``requesting_provenance``
        ContextVar (default ``"agent_authored"``); ingest enters
        ``untrusted_scope()`` to flip it. The resulting tag is written into
        ``node.metadata[PROVENANCE_KEY]`` and is never copied into
        ``node.inputs``. ``_provenance`` is a reserved kwarg name and must not
        be used as a ComfyUI input field.
        """
        from vibecomfy.security.capabilities import capabilities_for, is_side_effecting
        from vibecomfy.security.gate import (
            current_gate_context,
            requesting_provenance,
            require_confirmation,
        )
        from vibecomfy.security.provenance import tag as _tag_provenance

        effective = _provenance if _provenance is not None else requesting_provenance.get()

        # ── S4 capability fence ─────────────────────────────────────────────
        # Edit-time confused-deputy gate. Only the IR write path is gated; the
        # compile path at ``_compile_graphbuilder`` below (GraphBuilder.node
        # from ``comfy_execution.graph_utils``) is INTENTIONALLY NOT gated —
        # gating happens at edit-time, not at compile-time. By the time a
        # workflow compiles, every node has already passed this gate (or was
        # tagged trusted by its authoring path).
        if is_side_effecting(class_type):
            caps = capabilities_for(class_type)
            risky = {
                k: v
                for k, v in inputs.items()
                if not isinstance(v, Handle) and k != "_provenance"
            }
            require_confirmation(
                operation="add_node",
                class_type=class_type,
                provenance=effective,
                capabilities=caps,
                details={"params": risky},
                ctx=current_gate_context(),
            )

        node_id = str(_id) if _id is not None else self._next_node_id()
        if node_id in self.nodes:
            raise ValueError(f"Node id {node_id!r} already exists in workflow {self.id!r}")
        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
        if uid is not None:
            node.uid = uid
        _tag_provenance(node, effective)
        # Defensive: ensure the reserved kwarg never leaked into inputs.
        node.inputs.pop("_provenance", None)
        self.nodes[node_id] = node
        return node

    def node(self, class_type: str, **kwargs: Any) -> "_NodeBuilder":
        pass_raw = bool(kwargs.pop("pass_raw", False))
        explicit_id = kwargs.pop("_id", None)
        explicit_provenance = kwargs.pop("_provenance", None)
        from vibecomfy.templates import coerce_node_kwargs

        kwargs = coerce_node_kwargs(self, class_type, kwargs, pass_raw=pass_raw)
        node = self.add_node(class_type, _id=explicit_id, _provenance=explicit_provenance)
        # Mint extrinsic uid: seed from explicit id when provided, else creation order.
        seed = f"id:{explicit_id}" if explicit_id is not None else None
        node.uid = self._mint_uid(seed=seed)
        for key, value in kwargs.items():
            if isinstance(value, Handle):
                self.connect(value, f"{node.id}.{key}")
            else:
                node.inputs[key] = value
        return _NodeBuilder(workflow=self, node=node)

    def _parse_source_ref(self, ref: str | Handle, *, operation: str) -> tuple[str, str, Handle | None]:
        if isinstance(ref, Handle):
            return str(ref.node_id), str(ref.output_slot), ref
        if not isinstance(ref, str):
            raise ValueError(f"{operation}: source ref must be a Handle or string, got {type(ref).__name__}")
        if not ref:
            raise ValueError(f"{operation}: source ref must not be empty")
        if "." not in ref:
            return ref, "0", None
        node_id, output_slot = ref.split(".", 1)
        if not node_id or not output_slot:
            raise ValueError(
                f"{operation}: malformed source ref {ref!r}; expected 'node_id' or 'node_id.output_slot'"
            )
        return node_id, output_slot, None

    def _parse_target_ref(self, ref: str, *, operation: str) -> tuple[str, str]:
        if not isinstance(ref, str):
            raise ValueError(f"{operation}: target ref must be a string, got {type(ref).__name__}")
        if not ref:
            raise ValueError(f"{operation}: target ref must not be empty")
        if "." not in ref:
            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
        node_id, input_name = ref.split(".", 1)
        if not node_id or not input_name:
            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
        return node_id, input_name

    def connect(self, from_ref: str | Handle, to_ref: str) -> "VibeWorkflow":
        from_node, from_output, from_handle = self._parse_source_ref(from_ref, operation="connect")
        to_node, to_input = self._parse_target_ref(to_ref, operation="connect")
        if self.strict_types:
            self._warn_if_incompatible_connect(from_node, from_output, to_node, to_input, from_handle)
        self.edges.append(VibeEdge(from_node, from_output, to_node, to_input))
        return self

    def _warn_if_incompatible_connect(
        self,
        from_node: str,
        from_output: str,
        to_node: str,
        to_input: str,
        from_handle: Handle | None = None,
    ) -> None:
        output_type = from_handle.output_type if from_handle is not None else None
        if output_type is None:
            output_type = _node_output_type(self.nodes.get(str(from_node)), from_output)
        input_type = _node_input_type(self.nodes.get(str(to_node)), to_input)
        if output_type is None or input_type is None:
            return
        from vibecomfy.schema import socket_types_compatible

        if socket_types_compatible(output_type, input_type):
            return
        warnings.warn(
            (
                f"Strict type warning: connecting {from_node}.{from_output} ({output_type}) "
                f"to {to_node}.{to_input} ({input_type}) may be incompatible."
            ),
            RuntimeWarning,
            stacklevel=3,
        )

    def disconnect(self, to_ref: str) -> bool:
        """Remove the edge whose target matches ``to_ref`` (``"node_id.input_name"``).

        Returns True if an edge was removed, False otherwise.
        """
        to_node, to_input = self._parse_target_ref(to_ref, operation="disconnect")
        for index, edge in enumerate(self.edges):
            if edge.to_node == to_node and edge.to_input == to_input:
                del self.edges[index]
                return True
        return False

    def remove_node(self, node_id: str) -> "VibeWorkflow":
        """Remove a node and all edges attached to it."""
        node_id = str(node_id)
        self.nodes.pop(node_id, None)
        self.edges = [
            edge
            for edge in self.edges
            if str(edge.from_node) != node_id and str(edge.to_node) != node_id
        ]
        self.inputs = {
            name: target
            for name, target in self.inputs.items()
            if str(target.node_id) != node_id
        }
        self.outputs = [
            output
            for output in self.outputs
            if str(output.node_id) != node_id
        ]
        return self

    def replace_edge(self, to_ref: str, new_from_ref: str | Handle) -> "VibeWorkflow":
        """Redirect the edge feeding ``to_ref`` so it now originates from ``new_from_ref``.

        Disconnects the existing edge (if any) and connects the new source. Returns
        ``self`` for chaining.
        """
        self._parse_target_ref(to_ref, operation="replace_edge")
        self._parse_source_ref(new_from_ref, operation="replace_edge")
        self.disconnect(to_ref)
        return self.connect(new_from_ref, to_ref)

    def validate(self, schema_provider: SchemaProvider | None = None) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not self.nodes:
            issues.append(ValidationIssue("empty_workflow", "Workflow contains no nodes."))
        for spec in comfyui_node_issue_specs(
            (node_id, node.class_type, node.inputs, node.metadata)
            for node_id, node in self.nodes.items()
        ):
            issues.append(
                ValidationIssue(
                    spec.code,
                    spec.message,
                    severity=spec.severity,
                    detail=spec.detail,
                )
            )
        issues.extend(_graph_integrity_issues(self.nodes, self.edges))
        for detail in _invalid_geometry_details(self):
            issues.append(
                ValidationIssue(
                    "invalid_geometry",
                    f"Node {detail['node_id']} {detail['field']} {detail['reason']}.",
                    severity="error",
                    detail=detail,
                )
            )
        embedded_links = _embedded_api_link_details(self)
        for detail in embedded_links:
            issues.append(
                ValidationIssue(
                    "embedded_api_link",
                    _embedded_api_link_message(detail, surface="validation"),
                    severity="error",
                    detail=detail,
                )
            )
        api: dict[str, Any] | None = None
        if not embedded_links:
            try:
                api = self.compile(backend="api")
            except Exception as exc:
                detail: dict[str, Any] = {}
                if isinstance(exc, WorkflowCompileError):
                    detail = {"compile_code": exc.code, **exc.detail}
                issues.append(ValidationIssue("api_compile_failed", str(exc), severity="error", detail=detail))
        if schema_provider is not None:
            from vibecomfy.schema.validate import validate_against_schema, validate_api_link_shapes

            issues.extend(validate_against_schema(self, schema_provider, api_dict=api))
            if api is not None:
                issues.extend(validate_api_link_shapes(api, schema_provider))
        return ValidationReport(ok=not any(issue.severity == "error" for issue in issues), issues=issues)

    def runtime_nodes(self) -> dict[str, VibeNode]:
        return workflow_helpers.helper_stripped_nodes(self.nodes)

    def runtime_class_types(self) -> list[str]:
        return workflow_helpers.helper_stripped_class_types(self.nodes)

    def helper_diagnostics(self) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                diagnostic.code,
                diagnostic.message,
                severity=diagnostic.severity,
                detail={
                    **diagnostic.detail,
                    "node_id": diagnostic.node_id,
                    "class_type": diagnostic.class_type,
                },
            )
            for diagnostic in workflow_helpers.collect_helper_diagnostics(self.nodes, self.edges)
        ]

    def _execution_projection(
        self,
        *,
        variant: str | None = None,
        run_inputs: dict[str, Any] | None = None,
    ) -> "_ExecutionProjection":
        """Return the one execution projection for all runtime backends."""
        selected = self._with_selection(variant, run_inputs)
        # The projection is an execution view, never an in-place lowering of
        # authored IR.  This also makes repeated API/GraphBuilder consumers
        # independent even when helper resolution rewrites edges.
        definitions, virtual_wires = selected._semantic_source()
        if definitions:
            # Validate structural identity before any execution lowering.  The
            # compiler does not invent a root-only interpretation for scopes.
            selected._semantic_definitions(definitions)
            # Metadata-held definitions from legacy UI imports are transient
            # replay evidence.  Apply the strict recursive execution gate only
            # when the authored IR opts into the semantic recursive fields.
            if selected.definitions or selected.interfaces or selected.boundary_ports:
                _validate_recursive_execution_contract(definitions, selected.boundary_ports)
        projection_nodes = copy.deepcopy(selected.nodes)
        projection_edges = copy.deepcopy(selected.edges)
        public_input_targets: dict[tuple[str, str], tuple[str, str]] = {}
        if selected.definitions:
            expanded_nodes, expanded_edges, public_input_targets = _expand_authored_definitions(selected, definitions)
            projection_nodes = expanded_nodes
            projection_edges = expanded_edges
            # This validates the authored interface/boundary roster (including
            # unused definitions) without treating it as an execution graph.
            _validate_interface_boundary_contract(selected, projection_nodes)
        _validate_public_io_for_projection(selected, projection_nodes, public_input_targets)
        _bind_public_input_values(selected, projection_nodes, public_input_targets)
        return _execution_projection(
            projection_nodes,
            projection_edges,
            virtual_wires=virtual_wires,
        )

    def compile(
        self,
        backend: str = "api",
        *,
        variant: str | None = None,
        run_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _raise_embedded_api_links(self, surface=f"{backend} compilation")
        if backend == "graphbuilder":
            return self._compile_graphbuilder(variant=variant, run_inputs=run_inputs)
        if backend != "api":
            raise ValueError(f"Unknown compile backend: {backend}")
        selected = self._with_selection(variant, run_inputs)
        projection = selected._execution_projection()
        broadcast_sources = workflow_helpers.collect_broadcast_sources(projection.nodes, projection.edges)
        api: dict[str, Any] = {}
        for node_id, node in projection.nodes.items():
            if _is_compile_stripped_node(node):
                continue
            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), projection.nodes, broadcast_sources)
            inputs.update(_compile_intent_runtime_inputs(node))
            api[str(node_id)] = {"class_type": node.class_type, "inputs": inputs}
        edge_inputs = _compile_resolved_edge_inputs(
            projection.nodes, projection.edges, broadcast_sources, dropped_ids=projection.dropped_ids
        )
        for target_node_id, inputs in edge_inputs.items():
            if target_node_id not in api:
                continue
            api[target_node_id]["inputs"].update(inputs)
        return api

    def export_to_json(self, *, format: str = "api") -> dict[str, Any]:
        if format != "api":
            raise ValueError(f"Unsupported workflow JSON export format: {format!r}")
        return self.compile("api")

    def id_map(self) -> dict[str, str]:
        """Map variable name (as used in build()) to assigned node id."""
        return dict(self._id_map)

    def _set_id_map(self, mapping: dict[str, Any]) -> "VibeWorkflow":
        """Store codemod-emitted variable-name mappings and return ``self``."""
        resolved: dict[str, str] = {}
        metadata_id_map = self.metadata.get("id_map")
        metadata_id_map = metadata_id_map if isinstance(metadata_id_map, dict) else {}
        for name, node_id in mapping.items():
            key = str(name)
            value = str(node_id)
            if value in self.nodes:
                resolved[key] = value
                continue
            metadata_value = metadata_id_map.get(value)
            resolved[key] = str(metadata_value) if metadata_value is not None else value
        self._id_map = resolved
        return self

    def lookup_id(self, node_id: str) -> dict[str, Any]:
        """Return a rich info dict for the node identified by *node_id*.

        Raises ``KeyError`` when *node_id* is absent from the workflow —
        callers asked for a concrete node id.
        """
        nid = str(node_id)
        if nid not in self.nodes:
            raise KeyError(nid)

        node = self.nodes[nid]

        # --- variable_name: reverse lookup from _id_map --------------------
        variable_name: str | None = None
        for name, mapped_id in self._id_map.items():
            if mapped_id == nid:
                variable_name = name
                break

        # --- source_path ---------------------------------------------------
        provenance = node.metadata.get("provenance")
        source_path: str | None = None
        if isinstance(provenance, dict):
            sp = provenance.get("source_path")
            if isinstance(sp, str) and sp:
                source_path = sp
        if source_path is None:
            source_path = self.source.path

        # --- source_line (SD4: null for generated-template nodes) ----------
        source_line: int | None = None
        if isinstance(provenance, dict):
            sl = provenance.get("source_line")
            if isinstance(sl, int) and sl >= 1:
                source_line = sl

        # --- inputs ---------------------------------------------------------
        input_names: list[str] = list(node.inputs.keys())

        # --- widgets --------------------------------------------------------
        widgets: dict[str, Any] = dict(node.widgets)

        # --- public_bindings ------------------------------------------------
        public_bindings: list[dict[str, Any]] = [
            {
                "name": vibe_input.name,
                "field": vibe_input.field,
                "value": vibe_input.value,
                "type": vibe_input.type,
                "default": vibe_input.default,
                "required": vibe_input.required,
            }
            for vibe_input in self.inputs.values()
            if str(vibe_input.node_id) == nid
        ]

        # --- outputs --------------------------------------------------------
        output_type_names: list[str] = [
            output.output_type
            for output in self.outputs
            if str(output.node_id) == nid
        ]

        # --- model_assets ---------------------------------------------------
        model_assets: list[dict[str, Any]] = []
        try:
            from vibecomfy.model_assets import (
                _asset_for_reference,
                _referenced_model_values,
                _unresolved_asset_for_reference,
            )
            from vibecomfy.registry.models_loader import load_registry

            registry = load_registry()
            all_refs = _referenced_model_values(self)
            for ref in all_refs:
                if ref.get("node_id") != nid:
                    continue
                asset = _asset_for_reference(ref, registry=registry)
                if asset is not None:
                    model_assets.append(asset)
                else:
                    model_assets.append(_unresolved_asset_for_reference(ref))
        except Exception:
            # resolve_referenced_assets may fail when registry is unavailable;
            # degrade gracefully and return whatever we can.
            pass

        return {
            "variable_name": variable_name,
            "class_type": node.class_type,
            "source_path": source_path,
            "source_line": source_line,
            "inputs": input_names,
            "widgets": widgets,
            "public_bindings": public_bindings,
            "outputs": output_type_names,
            "model_assets": model_assets,
        }

    def _compile_graphbuilder(
        self,
        *,
        variant: str | None = None,
        run_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            from comfy_execution.graph_utils import GraphBuilder
        except ImportError as exc:
            raise RuntimeError("GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.") from exc

        selected = self._with_selection(variant, run_inputs)
        projection = selected._execution_projection()
        broadcast_sources = workflow_helpers.collect_broadcast_sources(projection.nodes, projection.edges)
        edge_inputs = _compile_resolved_edge_inputs(
            projection.nodes, projection.edges, broadcast_sources, dropped_ids=projection.dropped_ids
        )

        builder = GraphBuilder(prefix="")
        for node_id, node in projection.nodes.items():
            if _is_compile_stripped_node(node):
                continue
            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), projection.nodes, broadcast_sources)
            inputs.update(_compile_intent_runtime_inputs(node))
            inputs.update(edge_inputs.get(str(node_id), {}))
            builder.node(node.class_type, id=str(node_id), **inputs)
        return builder.finalize()

    def _next_node_id(self) -> str:
        numeric = {int(node_id) for node_id in self.nodes if str(node_id).isdigit() and int(node_id) > 0}
        candidate = 1
        while candidate in numeric:
            candidate += 1
        return str(candidate)


def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
    """Fail-closed reader for a serialized vibe envelope.

    Module-level alias of :meth:`VibeWorkflow.from_envelope`.
    """
    return VibeWorkflow.from_envelope(raw)


def _validate_public_io_for_projection(
    workflow: VibeWorkflow,
    nodes: Mapping[str, VibeNode] | None = None,
    public_input_targets: Mapping[tuple[str, str], tuple[str, str]] | None = None,
) -> None:
    nodes = nodes if nodes is not None else workflow.nodes
    public_input_targets = public_input_targets or {}
    seen_outputs: set[str] = set()
    for name, public_input in workflow.inputs.items():
        resolved_target = public_input_targets.get((str(public_input.node_id), str(public_input.field)))
        target = nodes.get(resolved_target[0]) if resolved_target is not None else nodes.get(str(public_input.node_id))
        target_field = resolved_target[1] if resolved_target is not None else public_input.field
        if target is None:
            raise WorkflowCompileError(
                "public_input_missing",
                f"public input {name!r} targets missing node {public_input.node_id!r}",
                next_action="Bind the public input to a node in the same workflow scope.",
            )
        if (
            target_field not in target.inputs
            and target_field not in target.widgets
            and target_field not in (target.native_input_names or ())
            and public_input.field not in (target.metadata.get("input_names", ()) if isinstance(target.metadata, dict) else ())
        ):
            if not workflow._is_valid_missing_target(public_input):
                raise WorkflowCompileError(
                    "public_input_missing",
                    f"public input {name!r} targets missing field {target_field!r}",
                    detail={"node_id": str(public_input.node_id), "field": target_field},
                    next_action="Bind the public input to a declared node input or widget.",
                )


        target_type = _node_input_socket_type(target, target_field)
        if public_input.type is not None and target_type is not None and not _types_match(public_input.type, target_type):
            raise WorkflowCompileError("public_input_incompatible", f"public input {name!r} type {public_input.type!r} is incompatible with {target_type!r}", detail={"node_id": str(public_input.node_id), "field": public_input.field}, next_action="Bind the public input to a compatible socket type.")
        if public_input.type is not None and target_type is None:
            raise WorkflowCompileError("public_input_untyped", f"public input {name!r} has no proven target socket type", detail={"node_id": str(public_input.node_id), "field": public_input.field}, next_action="Declare the target socket type before exposing it publicly.")

    for output in workflow.outputs:
        node_id = str(output.node_id)
        node = nodes.get(node_id)
        if node is None:
            raise WorkflowCompileError("public_output_missing", f"public output targets missing node {node_id!r}", next_action="Bind the public output to a node in the workflow.")
        if mode_to_litegraph(getattr(node, "mode", NodeMode.ENABLED)) in (_MODE_MUTED, _MODE_BYPASS):
            raise WorkflowCompileError(
                "public_output_missing",
                f"public output target {node_id!r} is not executable because its node is muted or bypassed",
                detail={"node_id": node_id, "mode": mode_to_litegraph(getattr(node, "mode", NodeMode.ENABLED))},
                next_action="Expose an enabled producer node as the public output.",
            )
        if output.name:
            if output.name in seen_outputs:
                raise WorkflowCompileError("public_output_duplicate", f"duplicate public output name {output.name!r}")
            seen_outputs.add(output.name)
        # VibeOutput is an artifact/producer contract.  ``name`` is the
        # public artifact route and ``output_type`` describes the producer
        # node, not a Comfy socket.  Socket names/slots belong to Handle and
        # VibeEdge resolution below and must never be inferred here.
        if output.output_type and str(output.output_type) != str(node.class_type):
            raise WorkflowCompileError(
                "public_output_incompatible",
                f"public output producer type {output.output_type!r} does not match node {node.class_type!r}",
                detail={"node_id": node_id, "output": output.name},
                next_action="Bind the public output to its concrete producer node.",
            )
        if output.expected_cardinality is not None:
            declared_cardinality = node.metadata.get("output_cardinality") if isinstance(node.metadata, dict) else None
            if declared_cardinality is None and output.expected_cardinality not in ("one", 1):
                raise WorkflowCompileError("public_output_cardinality", f"public output {output.name or node_id!r} has unproven cardinality {output.expected_cardinality!r}", next_action="Declare the output cardinality in the existing node contract.")
            if declared_cardinality is not None and str(declared_cardinality).lower() != str(output.expected_cardinality).lower():
                raise WorkflowCompileError("public_output_cardinality", f"public output cardinality {output.expected_cardinality!r} does not match {declared_cardinality!r}", next_action="Bind the public output with its declared cardinality.")
def _bind_public_input_values(
    workflow: VibeWorkflow,
    nodes: Mapping[str, VibeNode],
    public_input_targets: Mapping[tuple[str, str], tuple[str, str]] | None = None,
) -> None:
    """Apply declared runtime values/defaults to the detached execution view."""
    public_input_targets = public_input_targets or {}
    for public_input in workflow.inputs.values():
        value = public_input.value if public_input.value is not None else public_input.default
        if value is None and public_input.required:
            raise WorkflowCompileError("public_input_required", f"required public input {public_input.name!r} has no runtime value or default", next_action="Supply the required public input before compiling.")
        resolved_target = public_input_targets.get((str(public_input.node_id), str(public_input.field)))
        node = nodes.get(resolved_target[0]) if resolved_target is not None else nodes.get(str(public_input.node_id))
        if node is None:
            continue
        target_field = resolved_target[1] if resolved_target is not None else public_input.field
        if target_field in node.widgets:
            node.widgets[target_field] = copy.deepcopy(value)
        else:
            node.inputs[target_field] = copy.deepcopy(value)


def _validate_interface_boundary_contract(
    workflow: VibeWorkflow, nodes: Mapping[str, VibeNode]
) -> None:
    """Validate the existing interface/boundary records before lowering.

    Native Comfy boundary sentinels are deliberately unsupported; these
    records are still checked so malformed Python contracts cannot silently
    turn into root-only execution.
    """
    interfaces = workflow.interfaces
    if interfaces and not isinstance(interfaces, Mapping):
        raise WorkflowCompileError("interface_malformed", "interfaces must be a mapping")
    declared: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for scope_key, raw in (interfaces.items() if isinstance(interfaces, Mapping) else ()):
        if isinstance(raw, Mapping):
            members: list[Any] = []
            for direction in ("inputs", "outputs"):
                value = raw.get(direction, ())
                if not isinstance(value, (list, tuple)):
                    raise WorkflowCompileError("interface_malformed", f"interface {scope_key!r} {direction} must be a sequence")
                members.extend({"direction": direction[:-1], **member} if isinstance(member, Mapping) else member for member in value)
        elif isinstance(raw, (list, tuple)):
            members = list(raw)
        else:
            raise WorkflowCompileError("interface_malformed", f"interface {scope_key!r} must be a mapping or sequence")
        for member in members:
            if not isinstance(member, Mapping):
                raise WorkflowCompileError("interface_malformed", f"interface {scope_key!r} member must be a mapping")
            name = member.get("name", member.get("interface", member.get("port")))
            direction = str(member.get("direction", "")).lower()
            if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
                raise WorkflowCompileError("interface_malformed", f"interface {scope_key!r} member needs name and direction")
            key = (str(scope_key), name, direction)
            if key in declared:
                raise WorkflowCompileError("interface_duplicate", f"duplicate interface member {key!r}")
            declared[key] = member

    seen_bindings: set[tuple[str, str, str]] = set()
    ports = workflow.boundary_ports
    if ports and not isinstance(ports, (list, tuple)):
        raise WorkflowCompileError("boundary_port_malformed", "boundary_ports must be a sequence")
    from vibecomfy.identity.uid import make_uid
    for port in ports:
        if not isinstance(port, Mapping):
            raise WorkflowCompileError("boundary_port_malformed", "boundary port must be a mapping")
        scope = str(port.get("scope_path", ""))
        name = port.get("name", port.get("interface", port.get("port_name")))
        direction = str(port.get("direction", "")).lower()
        local_node = port.get("node_uid", port.get("node_id", port.get("uid")))
        field_name = port.get("field", port.get("input", port.get("output")))
        if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"} or local_node is None or field_name is None:
            raise WorkflowCompileError("boundary_port_malformed", "boundary port needs scope, name, direction, node, and field")
        key = (scope, name, direction)
        if key in seen_bindings:
            raise WorkflowCompileError("boundary_port_duplicate", f"duplicate boundary binding {key!r}")
        seen_bindings.add(key)
        if declared and key not in declared:
            raise WorkflowCompileError("boundary_port_unbound", f"boundary port {key!r} has no declared interface member")
        if "#" in str(local_node) or "/" in str(local_node):
            raise WorkflowCompileError(
                "boundary_port_cross_scope",
                f"boundary endpoint {local_node!r} must be local to its definition scope",
            )
        qualified = make_uid(scope, str(local_node))
        node = nodes.get(qualified)
        if node is None:
            # Referenced occurrences are expanded under a derived runtime
            # scope, so their definition-semantic boundary rows cannot be
            # looked up by the canonical scope here.  Expansion performs the
            # concrete endpoint check before returning its detached graph.
            continue
        if direction == "input" and _node_input_socket_type(node, field_name) is None:
            raise WorkflowCompileError("boundary_port_untyped", f"boundary input {key!r} has no proven socket type")
        if direction == "output" and _node_output_socket_type(node, field_name) is None:
            raise WorkflowCompileError("boundary_port_untyped", f"boundary output {key!r} has no proven socket type")
        member = declared.get(key)
        if member and member.get("type") is not None:
            actual = _node_input_socket_type(node, field_name) if direction == "input" else _node_output_socket_type(node, field_name)
            if actual is None or not _types_match(member["type"], actual):
                raise WorkflowCompileError("boundary_port_incompatible", f"boundary port {key!r} has incompatible socket type")
    missing_members = sorted(set(declared) - seen_bindings)
    if missing_members:
        raise WorkflowCompileError(
            "interface_unbound",
            f"interface members have no boundary binding: {missing_members!r}",
            next_action="Bind every ordered interface member exactly once.",
        )


def _validate_recursive_execution_contract(definitions: Any, boundary_ports: Any) -> None:
    """Validate the JSON-shaped recursive contract before expansion.

    Definition instances are ordinary nodes whose class/type is a definition
    identity.  ``instances`` was never part of the Python IR; accepting it
    here would create a second occurrence model.  The actual expansion below
    uses the node's existing ``uid`` (or validated ``id``) instead.
    """
    if not isinstance(boundary_ports, (list, tuple)):
        boundary_ports = []

    def entries(raw: Any) -> list[Any]:
        if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), (list, tuple)):
            return list(raw["subgraphs"])
        if isinstance(raw, Mapping):
            return list(raw.values())
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return []

    boundary_keys: set[tuple[str, str, str]] = set()
    for port in boundary_ports:
        if not isinstance(port, Mapping):
            raise WorkflowCompileError("boundary_port_malformed", "boundary port must be a mapping")
        key = (str(port.get("scope_path", "")), str(port.get("name", port.get("uid", ""))), str(port.get("direction", "")))
        if key in boundary_keys:
            raise WorkflowCompileError("boundary_port_duplicate", f"duplicate boundary port {key!r}")
        boundary_keys.add(key)

    def walk(raw: Any) -> None:
        for definition in entries(raw):
            if not isinstance(definition, Mapping):
                continue
            if "instances" in definition or "instance" in definition:
                raise WorkflowCompileError(
                    "recursive_instance_unsupported",
                    "definition instances are not an authored field; occurrences are definition-typed nodes",
                    next_action="Represent each occurrence as an existing node whose class/type matches the definition.",
                )
            links = definition.get("links", [])
            for link in links if isinstance(links, (list, tuple)) else []:
                if isinstance(link, Mapping):
                    origin = link.get("origin_id")
                    target = link.get("target_id")
                elif isinstance(link, (list, tuple)) and len(link) >= 5:
                    origin, target = link[1], link[3]
                else:
                    raise WorkflowCompileError("recursive_link_malformed", "definition link must be a mapping or LiteGraph tuple")
                for endpoint in (origin, target):
                    text = str(endpoint)
                    if text in {"-10", "-20"}:
                        raise WorkflowCompileError(
                            "unsupported_boundary_encoding",
                            "native -10/-20 boundary link has no proven executable realization",
                            detail={"endpoint": text},
                            next_action="Use a Python-owned interface/virtual-wire mapping; native sentinel lowering is unsupported.",
                        )
                    elif "#" in text or "/" in text:
                        raise WorkflowCompileError(
                            "cross_scope_ordinary_edge",
                            f"definition link endpoint {text!r} must be local to its definition scope",
                        )
            walk(definition.get("definitions"))

    walk(definitions)


def _recursive_entries(raw: Any) -> list[Any]:
    if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), (list, tuple)):
        return list(raw["subgraphs"])
    if isinstance(raw, Mapping):
        return list(raw.values())
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _raw_recursive_node(raw_node: Mapping[str, Any], node_id: str) -> VibeNode:
    """Decode one JSON-shaped definition node into the existing VibeNode IR."""
    raw_inputs = raw_node.get("inputs", {})
    input_values: dict[str, Any] = {}
    input_names: list[str | None] = []
    input_types: list[str | None] = []
    if isinstance(raw_inputs, Mapping):
        if any(
            isinstance(value, Mapping)
            and ("type" in value or "name" in value)
            and ("value" in value or "link" in value or "name" in value)
            for value in raw_inputs.values()
        ):
            raise WorkflowCompileError(
                "boundary_port_untyped",
                "mapping-form definition inputs are semantic values, not socket descriptors",
            )
        input_values = copy.deepcopy(dict(raw_inputs))
    elif isinstance(raw_inputs, (list, tuple)):
        for item in raw_inputs:
            if not isinstance(item, Mapping):
                continue
            input_name = item.get("name")
            input_names.append(str(input_name) if input_name is not None else None)
            input_types.append(str(item.get("type")) if item.get("type") is not None else None)
            if input_name is not None and item.get("link") is None and "value" in item:
                input_values[str(input_name)] = copy.deepcopy(item["value"])
    raw_outputs = raw_node.get("outputs", [])
    output_names: list[str | None] = []
    output_types: list[str | None] = []
    if isinstance(raw_outputs, Mapping):
        raise WorkflowCompileError(
            "boundary_port_untyped",
            "mapping-form definition outputs are not a typed socket roster",
        )
    if isinstance(raw_outputs, (list, tuple)):
        for item in raw_outputs:
            if isinstance(item, Mapping):
                output_names.append(str(item.get("name")) if item.get("name") is not None else None)
                output_types.append(str(item.get("type")) if item.get("type") is not None else None)
    widgets = raw_node.get("widgets")
    if not isinstance(widgets, Mapping):
        values = raw_node.get("widgets_values", [])
        widgets = {
            f"widget_{i}": copy.deepcopy(value)
            for i, value in enumerate(values)
        } if isinstance(values, (list, tuple)) else {}
    metadata = copy.deepcopy(raw_node.get("metadata", {})) if isinstance(raw_node.get("metadata"), Mapping) else {}
    if output_names:
        metadata.setdefault("output_names", output_names)
    if output_types:
        metadata.setdefault("output_types", output_types)
    if input_names:
        metadata.setdefault("input_names", input_names)
    if input_types:
        metadata.setdefault("input_types", input_types)
    local_uid = raw_node.get("uid")
    if not isinstance(local_uid, str) or not local_uid.strip():
        local_uid = raw_node.get("id", node_id)
    from vibecomfy.identity.uid import validate_local_uid
    local_uid = validate_local_uid(str(local_uid), field="definition node uid")
    return VibeNode(
        str(node_id),
        str(raw_node.get("class_type", raw_node.get("type", "Unknown"))),
        inputs=input_values,
        widgets=dict(widgets),
        metadata=metadata,
        uid=local_uid,
        mode=litegraph_to_mode(raw_node.get("mode", NodeMode.ENABLED)),
        native_input_names=input_names or None,
        native_output_names=output_names or None,
    )


def _expand_authored_definitions(
    workflow: VibeWorkflow, definitions: Any
) -> tuple[dict[str, VibeNode], list[VibeEdge], dict[tuple[str, str], tuple[str, str]]]:
    """Expand only referenced definition occurrences into one detached graph.

    The definition and boundary records remain authored JSON-shaped IR.  The
    maps created here are ephemeral compiler state: each occurrence receives a
    derived ``<sg_key>:<uid>`` scope and its shell is replaced by the one
    Python-owned boundary endpoint for each interface member.
    """
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.identity.uid import make_uid, validate_local_uid

    records_by_path: dict[str, dict[str, Any]] = {}
    records_by_key: dict[str, dict[str, Any]] = {}
    records_by_alias: dict[str, dict[str, Any]] = {}

    def index(raw: Any, parent_keys: tuple[str, ...], active_definition_ids: set[int]) -> None:
        for definition in _recursive_entries(raw):
            if not isinstance(definition, Mapping):
                raise WorkflowCompileError("definition_malformed", "each definition must be a mapping")
            identity = id(definition)
            if identity in active_definition_ids:
                raise WorkflowCompileError(
                    "recursive_definition_cycle",
                    "recursive definition object graph cannot be compiled",
                )
            derived = sg_key(definition)
            supplied = definition.get("sg_key")
            if supplied is not None and supplied != derived:
                raise WorkflowCompileError(
                    "definition_identity_mismatch",
                    f"definition sg_key {supplied!r} does not match derived identity {derived!r}",
                )
            path = compose_scope_path((*parent_keys, derived))
            if path in records_by_path:
                raise WorkflowCompileError("definition_scope_collision", f"duplicate definition identity {path!r}")
            if derived in records_by_key:
                raise WorkflowCompileError("definition_scope_collision", f"duplicate definition identity {derived!r}")
            record: dict[str, Any] = {
                "definition": definition,
                "key": derived,
                "path": path,
                "aliases": {},
                "children": {},
            }
            aliases = {derived}
            native_id = definition.get("id")
            if native_id is not None and str(native_id).strip():
                aliases.add(str(native_id))
            for alias in aliases:
                if alias in records_by_alias and records_by_alias[alias] is not record:
                    raise WorkflowCompileError("definition_alias_duplicate", f"duplicate definition alias {alias!r}")
                record["aliases"][alias] = record
                records_by_alias[alias] = record
            records_by_path[path] = record
            records_by_key[derived] = record
            active_definition_ids.add(identity)
            index(definition.get("definitions"), (*parent_keys, derived), active_definition_ids)
            active_definition_ids.remove(identity)

    index(definitions, (), set())

    # Interface records are keyed by canonical definition key in the accepted
    # contract.  Accepting the full structural path/native alias is harmless
    # for nested definitions and keeps old envelopes readable.
    interfaces = workflow.interfaces if isinstance(workflow.interfaces, Mapping) else {}
    interface_by_key: dict[str, list[dict[str, Any]]] = {}
    interface_by_owner: dict[str, list[dict[str, Any]]] = {}
    for raw_key, raw_interface in interfaces.items():
        key = str(raw_key)
        owner = records_by_path.get(key) or records_by_key.get(key) or records_by_alias.get(key)
        if owner is None:
            raise WorkflowCompileError("interface_unknown", f"interface {key!r} has no indexed definition owner")
        if isinstance(raw_interface, Mapping):
            members: list[Any] = []
            for direction in ("inputs", "outputs"):
                values = raw_interface.get(direction, ())
                if not isinstance(values, (list, tuple)):
                    raise WorkflowCompileError("interface_malformed", f"interface {key!r} {direction} must be a sequence")
                members.extend({"direction": direction[:-1], **member} if isinstance(member, Mapping) else member for member in values)
        elif isinstance(raw_interface, (list, tuple)):
            members = list(raw_interface)
        else:
            raise WorkflowCompileError("interface_malformed", f"interface {key!r} must be a mapping or sequence")
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for member in members:
            if not isinstance(member, Mapping):
                raise WorkflowCompileError("interface_malformed", f"interface {key!r} member must be a mapping")
            name = member.get("name", member.get("interface", member.get("port")))
            direction = str(member.get("direction", "")).lower()
            if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
                raise WorkflowCompileError("interface_malformed", f"interface {key!r} member needs name and direction")
            pair = (name, direction)
            if pair in seen:
                raise WorkflowCompileError("interface_duplicate", f"duplicate interface member {(key, *pair)!r}")
            seen.add(pair)
            normalized.append({**dict(member), "name": name, "direction": direction})
        if owner["path"] in interface_by_owner:
            raise WorkflowCompileError("interface_duplicate", f"multiple interfaces identify definition {owner['path']!r}")
        interface_by_key[key] = normalized
        interface_by_owner[owner["path"]] = normalized

    ports = workflow.boundary_ports
    if not isinstance(ports, (list, tuple)):
        raise WorkflowCompileError("boundary_port_malformed", "boundary_ports must be a sequence")
    ports_by_scope: dict[str, list[Mapping[str, Any]]] = {}
    seen_ports: set[tuple[str, str, str]] = set()
    for port in ports:
        if not isinstance(port, Mapping):
            raise WorkflowCompileError("boundary_port_malformed", "boundary port must be a mapping")
        scope = str(port.get("scope_path", ""))
        owner = records_by_path.get(scope) or records_by_key.get(scope) or records_by_alias.get(scope)
        if owner is None:
            raise WorkflowCompileError("boundary_scope_unknown", f"boundary scope {scope!r} has no indexed definition owner")
        name = port.get("name", port.get("interface", port.get("port_name")))
        direction = str(port.get("direction", "")).lower()
        if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
            raise WorkflowCompileError("boundary_port_malformed", "boundary port needs scope, name, direction, node, and field")
        node_ref = port.get("node_uid", port.get("node_id", port.get("uid")))
        field_name = port.get("field", port.get("input", port.get("output", port.get("port"))))
        if node_ref is None or field_name is None:
            raise WorkflowCompileError("boundary_port_malformed", "boundary port needs scope, name, direction, node, and field")
        identity = (scope, name, direction)
        if identity in seen_ports:
            raise WorkflowCompileError("boundary_port_duplicate", f"duplicate boundary binding {identity!r}")
        seen_ports.add(identity)
        ports_by_scope.setdefault(owner["path"], []).append(port)

    for interface_key, members in interface_by_key.items():
        owner = records_by_path.get(interface_key) or records_by_key.get(interface_key) or records_by_alias.get(interface_key)
        owner_path = owner["path"] if owner is not None else interface_key
        present = {(str(p.get("name", p.get("interface", p.get("port_name")))), str(p.get("direction", "")).lower()) for p in ports_by_scope.get(owner_path, ())}
        missing = [(interface_key, name, direction) for name, direction in ((m["name"], m["direction"]) for m in members) if (name, direction) not in present]
        if missing:
            raise WorkflowCompileError("interface_unbound", f"interface members have no boundary binding: {missing!r}")
        for port in ports_by_scope.get(owner_path, ()):
            pair = (str(port.get("name", port.get("interface", port.get("port_name")))), str(port.get("direction", "")).lower())
            if pair not in {(m["name"], m["direction"]) for m in members}:
                raise WorkflowCompileError("boundary_port_unbound", f"boundary port {(interface_key, *pair)!r} has no declared interface member")

    def lookup_interface(record: Mapping[str, Any]) -> list[dict[str, Any]]:
        return interface_by_owner.get(str(record["path"]), [])

    def member_for(members: list[dict[str, Any]], value: Any, direction: str) -> dict[str, Any] | None:
        text = str(value)
        directional = [member for member in members if member["direction"] == direction]
        matches = [
            member
            for index, member in enumerate(directional)
            if member["name"] == text or (text.isdigit() and index == int(text))
        ]
        if len(matches) != 1:
            return None
        return matches[0]

    def parse_link(link: Any) -> tuple[Any, Any, Any, Any]:
        if isinstance(link, Mapping):
            origin = link.get("origin_id", link.get("from_node"))
            origin_slot = link.get("origin_slot", link.get("from_output", 0))
            target = link.get("target_id", link.get("to_node"))
            target_slot = link.get("target_slot", link.get("to_input", 0))
        elif isinstance(link, (list, tuple)) and len(link) >= 5:
            origin, origin_slot, target, target_slot = link[1], link[2], link[3], link[4]
        else:
            raise WorkflowCompileError("recursive_link_malformed", "definition link must be a mapping or LiteGraph tuple")
        return origin, origin_slot, target, target_slot

    all_nodes: dict[str, VibeNode] = {}
    all_edges: list[VibeEdge] = []
    root_targets: dict[tuple[str, str], tuple[str, str]] = {}

    def endpoint_for_shell(context: dict[str, Any], local: str, field: Any, direction: str) -> tuple[str, str]:
        child = context["shells"].get(local)
        if child is None:
            node_id = context["local_to_runtime"].get(local)
            if node_id is None:
                raise WorkflowCompileError("boundary_port_missing", f"boundary endpoint {local!r} is not declared")
            node = all_nodes[node_id]
            if direction == "input":
                if _node_input_socket_type(node, field) is None:
                    raise WorkflowCompileError("boundary_port_untyped", f"boundary input {local!r}.{field!r} has no proven socket type")
            elif _node_output_socket_type(node, field) is None:
                raise WorkflowCompileError("boundary_port_untyped", f"boundary output {local!r}.{field!r} has no proven socket type")
            return node_id, str(field)
        member = member_for(child["members"], field, direction)
        if member is None or (member["name"], direction) not in child["bindings"]:
            raise WorkflowCompileError("boundary_port_missing", f"nested occurrence {local!r} has no {direction} interface {field!r}")
        return child["bindings"][(member["name"], direction)]

    def build_bindings(context: dict[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
        members = context["members"]
        bindings: dict[tuple[str, str], tuple[str, str]] = {}
        raw_scope = context["record"]["key"]
        candidate_ports = list(ports_by_scope.get(context["record"]["path"], ()))
        for member in members:
            rows = [p for p in candidate_ports if str(p.get("name", p.get("interface", p.get("port_name")))) == member["name"] and str(p.get("direction", "")).lower() == member["direction"]]
            if len(rows) != 1:
                raise WorkflowCompileError("interface_unbound", f"interface member {(raw_scope, member['name'], member['direction'])!r} must bind exactly once")
            port = rows[0]
            node_ref = str(port.get("node_uid", port.get("node_id", port.get("uid"))))
            if "#" in node_ref or "/" in node_ref:
                raise WorkflowCompileError("boundary_port_cross_scope", f"boundary endpoint {node_ref!r} is not local to its occurrence scope")
            field_name = port.get("field", port.get("input", port.get("output", port.get("port"))))
            endpoint = endpoint_for_shell(context, node_ref, field_name, member["direction"])
            actual = _node_input_socket_type(all_nodes[endpoint[0]], endpoint[1]) if member["direction"] == "input" else _node_output_socket_type(all_nodes[endpoint[0]], endpoint[1])
            expected = member.get("type")
            if actual is None:
                raise WorkflowCompileError("boundary_port_untyped", f"boundary port {(raw_scope, member['name'], member['direction'])!r} has no proven socket type")
            if expected is not None and not _types_match(expected, actual):
                raise WorkflowCompileError("boundary_port_incompatible", f"boundary port {(raw_scope, member['name'], member['direction'])!r} has incompatible socket type")
            bindings[(member["name"], member["direction"])] = endpoint
        return bindings

    def expand_record(record: dict[str, Any], runtime_segments: tuple[str, ...], canonical_segments: tuple[str, ...], stack: tuple[str, ...]) -> dict[str, Any]:
        if record["path"] in stack:
            raise WorkflowCompileError("recursive_definition_cycle", f"recursive definition cycle through {record['path']!r}")
        runtime_scope = compose_scope_path(runtime_segments)
        definition = record["definition"]
        raw_nodes = definition.get("nodes", [])
        values = list(raw_nodes.values()) if isinstance(raw_nodes, Mapping) else list(raw_nodes) if isinstance(raw_nodes, (list, tuple)) else []
        local_to_runtime: dict[str, str] = {}
        raw_by_local: dict[str, Mapping[str, Any]] = {}
        for ordinal, raw_node in enumerate(values):
            if not isinstance(raw_node, Mapping):
                raise WorkflowCompileError("recursive_node_malformed", f"definition {record['key']!r} node {ordinal} is malformed")
            raw_id = raw_node.get("id", raw_node.get("uid", ordinal))
            uid_candidate = raw_node.get("uid")
            if not isinstance(uid_candidate, str) or not uid_candidate.strip():
                uid_candidate = raw_id
            local = validate_local_uid(str(uid_candidate), field="definition node uid")
            if local in raw_by_local:
                raise WorkflowCompileError("duplicate_scoped_node_uid", f"duplicate node UID {local!r} in definition {record['path']!r}")
            raw_by_local[local] = raw_node
            for alias in {str(raw_id), local}:
                if alias in local_to_runtime:
                    raise WorkflowCompileError("duplicate_scoped_node_uid", f"duplicate node identity {alias!r} in definition {record['path']!r}")
                local_to_runtime[alias] = make_uid(runtime_scope, local)
        context: dict[str, Any] = {"record": record, "runtime_scope": runtime_scope, "members": lookup_interface(record), "local_to_runtime": local_to_runtime, "shells": {}, "bindings": {}}
        occurrence_ids: set[str] = set()
        for local, raw_node in raw_by_local.items():
            class_type = str(raw_node.get("class_type", raw_node.get("type", "Unknown")))
            child = records_by_alias.get(class_type)
            if child is None:
                node = _raw_recursive_node(raw_node, local_to_runtime[local])
                node.id = local_to_runtime[local]
                all_nodes[node.id] = node
                continue
            occurrence_candidate = raw_node.get("uid")
            if not isinstance(occurrence_candidate, str) or not occurrence_candidate.strip():
                occurrence_candidate = raw_node.get("id", "")
            occurrence_uid = validate_local_uid(str(occurrence_candidate), field="instance occurrence uid")
            if occurrence_uid in occurrence_ids:
                raise WorkflowCompileError("occurrence_collision", f"duplicate occurrence identity {occurrence_uid!r} in scope {runtime_scope!r}")
            occurrence_ids.add(occurrence_uid)
            segment = f"{child['key']}:{occurrence_uid}"
            child_context = expand_record(child, (*runtime_segments, segment), (*canonical_segments, child["key"]), (*stack, record["path"]))
            context["shells"][local] = child_context
        context["bindings"] = build_bindings(context) if context["members"] else {}
        for raw_link in definition.get("links", ()) if isinstance(definition.get("links", ()), (list, tuple)) else ():
            origin, origin_slot, target, target_slot = parse_link(raw_link)
            origin_local = validate_local_uid(str(origin), field="definition link origin")
            target_local = validate_local_uid(str(target), field="definition link target")
            if origin_local in context["shells"]:
                member = member_for(context["shells"][origin_local]["members"], origin_slot, "output")
                if member is None:
                    raise WorkflowCompileError("boundary_port_missing", f"occurrence {origin_local!r} has no output interface {origin_slot!r}")
                source = context["shells"][origin_local]["bindings"][(member["name"], "output")]
            else:
                source_id = context["local_to_runtime"].get(origin_local)
                if source_id is None:
                    raise WorkflowCompileError("recursive_link_missing_endpoint", f"definition link endpoint {origin!r} is not declared in scope {record['path']!r}")
                source = (source_id, str(origin_slot))
            if target_local in context["shells"]:
                member = member_for(context["shells"][target_local]["members"], target_slot, "input")
                if member is None:
                    raise WorkflowCompileError("boundary_port_missing", f"occurrence {target_local!r} has no input interface {target_slot!r}")
                target_endpoint = context["shells"][target_local]["bindings"][(member["name"], "input")]
            else:
                target_id = context["local_to_runtime"].get(target_local)
                if target_id is None:
                    raise WorkflowCompileError("recursive_link_missing_endpoint", f"definition link endpoint {target!r} is not declared in scope {record['path']!r}")
                target_node = all_nodes[target_id]
                target_name = target_node.native_input_names[int(target_slot)] if isinstance(target_slot, int) and target_node.native_input_names and 0 <= target_slot < len(target_node.native_input_names) and target_node.native_input_names[target_slot] else str(target_slot)
                target_endpoint = (target_id, str(target_name))
            all_edges.append(VibeEdge(source[0], source[1], target_endpoint[0], target_endpoint[1]))
        return context

    # Root nodes are already VibeNodes.  Only nodes that match a top-level
    # definition alias recurse; ordinary root nodes stay in their authored ID
    # scope and are copied into the detached projection.
    root_occurrences: dict[str, dict[str, Any]] = {}
    root_occurrence_ids: set[str] = set()
    for node_id, authored in workflow.nodes.items():
        class_type = str(authored.class_type)
        record = records_by_alias.get(class_type)
        if record is None:
            all_nodes[str(node_id)] = copy.deepcopy(authored)
            continue
        occurrence_uid = validate_local_uid(str(authored.uid or authored.id), field="instance occurrence uid")
        if occurrence_uid in root_occurrence_ids:
            raise WorkflowCompileError("occurrence_collision", f"duplicate occurrence identity {occurrence_uid!r} in root scope")
        root_occurrence_ids.add(occurrence_uid)
        segment = f"{record['key']}:{occurrence_uid}"
        root_occurrences[str(node_id)] = expand_record(record, (segment,), (record["key"],), ())

    # Rewrite root edges through exactly one boundary endpoint.  The authored
    # occurrence shells are intentionally absent from ``all_nodes``.
    for edge in workflow.edges:
        source_id = str(edge.from_node)
        target_id = str(edge.to_node)
        if source_id in root_occurrences:
            ctx = root_occurrences[source_id]
            member = member_for(ctx["members"], edge.from_output, "output")
            if member is None:
                raise WorkflowCompileError("boundary_port_missing", f"occurrence {source_id!r} has no output interface {edge.from_output!r}")
            source = ctx["bindings"][(member["name"], "output")]
        else:
            if source_id not in all_nodes:
                raise WorkflowCompileError("compiled_edge_missing_endpoint", f"root edge source {source_id!r} is missing")
            source = (source_id, str(edge.from_output))
        if target_id in root_occurrences:
            ctx = root_occurrences[target_id]
            member = member_for(ctx["members"], edge.to_input, "input")
            if member is None:
                raise WorkflowCompileError("boundary_port_missing", f"occurrence {target_id!r} has no input interface {edge.to_input!r}")
            target = ctx["bindings"][(member["name"], "input")]
        else:
            if target_id not in all_nodes:
                raise WorkflowCompileError("compiled_edge_missing_endpoint", f"root edge target {target_id!r} is missing")
            target = (target_id, str(edge.to_input))
        all_edges.append(VibeEdge(source[0], source[1], target[0], target[1]))

    for root_id, context in root_occurrences.items():
        for member in context["members"]:
            if member["direction"] == "input":
                endpoint = context["bindings"].get((member["name"], "input"))
                if endpoint is not None:
                    root_targets[(root_id, member["name"])] = endpoint
    return all_nodes, all_edges, root_targets


def _apply_definition_variant(
    workflow: VibeWorkflow, qualified_uid: str, field_name: str, value: Any
) -> bool:
    """Apply one flat variant override to a structural definition node."""
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.identity.uid import make_uid

    if "#" not in qualified_uid:
        return False

    def entries(raw: Any) -> list[Any]:
        if isinstance(raw, dict) and isinstance(raw.get("subgraphs"), (list, tuple)):
            return list(raw["subgraphs"])
        if isinstance(raw, dict):
            return list(raw.values())
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return []

    def walk(
        raw: Any,
        parent: tuple[str, ...],
        active_definition_ids: set[int],
        active_keys: set[str],
    ) -> bool:
        for definition in entries(raw):
            if not isinstance(definition, dict):
                continue
            identity = id(definition)
            if identity in active_definition_ids:
                raise WorkflowCompileError(
                    "recursive_definition_cycle",
                    "recursive definition object graph cannot be selected",
                )
            key = definition.get("sg_key") or sg_key(definition)
            if key in active_keys:
                raise WorkflowCompileError(
                    "recursive_definition_cycle",
                    f"recursive definition path through {key!r}",
                )
            active_definition_ids.add(identity)
            active_keys.add(str(key))
            scope = compose_scope_path((*parent, key))
            nodes = definition.get("nodes", [])
            node_entries = list(nodes.values()) if isinstance(nodes, dict) else list(nodes) if isinstance(nodes, (list, tuple)) else []
            for node in node_entries:
                if not isinstance(node, dict):
                    continue
                local = node.get("uid")
                if not isinstance(local, str) or not local.strip():
                    local = node.get("id", "")
                local = str(local)
                if make_uid(scope, local) != qualified_uid:
                    continue
                if field_name in {"__mode__", "mode"}:
                    node["mode"] = mode_to_litegraph(value)
                elif field_name in {"enabled", "enable", "disabled", "disable"}:
                    node["mode"] = 0 if bool(value) else _MODE_MUTED
                else:
                    widgets = node.get("widgets")
                    if isinstance(widgets, dict) and field_name in widgets:
                        widgets[field_name] = copy.deepcopy(value)
                    elif field_name in (node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}):
                        node.setdefault("inputs", {})[field_name] = copy.deepcopy(value)
                    else:
                        raise ValueError(
                            f"variant override field {field_name!r} is not a declared value or mode field"
                        )
                active_definition_ids.remove(identity)
                active_keys.remove(str(key))
                return True
            nested = definition.get("definitions")
            if nested and walk(nested, (*parent, key), active_definition_ids, active_keys):
                active_definition_ids.remove(identity)
                active_keys.remove(str(key))
                return True
            active_definition_ids.remove(identity)
            active_keys.remove(str(key))
        return False

    return walk(
        workflow.definitions or workflow.metadata.get("definitions"), (), set(), set()
    )


@dataclass(frozen=True)
class _NodeBuilder:
    workflow: VibeWorkflow
    node: VibeNode

    @property
    def id(self) -> str:
        return self.node.id

    def out(self, slot: int | str) -> Handle:
        output_slot = _socket_index(_node_output_names(self.node), slot)
        if output_slot is None:
            output_names = self.node.metadata.get("output_names")
            if isinstance(output_names, (list, tuple)) and slot in output_names:
                index = output_names.index(slot)
                return Handle(
                    node_id=self.node.id,
                    output_slot=index,
                    output_type=_node_output_type(self.node, index),
                    name=str(slot),
                )
            if isinstance(output_names, (list, tuple)):
                normalized_slot = str(slot).upper()
                normalized_names = [str(name).upper() for name in output_names]
                if normalized_slot in normalized_names:
                    index = normalized_names.index(normalized_slot)
                    return Handle(
                        node_id=self.node.id,
                        output_slot=index,
                        output_type=_node_output_type(self.node, index),
                        name=str(slot),
                    )
            raise NotImplementedError(
                f"Named output {slot!r} is not registered for {self.node.class_type} node {self.node.id}; "
                "register output_names metadata or pass an integer slot. "
                "Full named-output lookup awaits MP-6 schema integration."
            )
        return Handle(node_id=self.node.id, output_slot=output_slot, output_type=_node_output_type(self.node, output_slot))

    def __iter__(self):
        output_names = _node_output_names(self.node)
        if isinstance(output_names, (list, tuple)) and output_names:
            for index, name in enumerate(output_names):
                yield Handle(
                    node_id=self.node.id,
                    output_slot=index,
                    output_type=_node_output_type(self.node, index),
                    name=str(name) if isinstance(name, str) and name else None,
                )
            return
        yield self.out(0)


def _node_output_type(node: VibeNode | None, output_slot: int | str) -> str | None:
    if node is None:
        return None
    output_types = node.metadata.get("output_types")
    try:
        index = int(str(output_slot))
    except (TypeError, ValueError):
        index = None
    if isinstance(output_types, (list, tuple)) and index is not None and 0 <= index < len(output_types):
        value = output_types[index]
        return str(value) if value is not None else None
    schema = _schema_for_node(node)
    outputs = getattr(schema, "outputs", None) or []
    if index is not None and 0 <= index < len(outputs):
        value = getattr(outputs[index], "type", None)
        return str(value) if value is not None else None
    for output in outputs:
        if getattr(output, "name", None) == output_slot:
            value = getattr(output, "type", None)
            return str(value) if value is not None else None
    return None


def _node_output_names(node: VibeNode) -> list[str | None]:
    native_output_names = getattr(node, "native_output_names", None)
    if isinstance(native_output_names, list):
        return list(native_output_names)
    output_names = node.metadata.get("output_names")
    if isinstance(output_names, (list, tuple)) and output_names:
        return [str(name) if name is not None else None for name in output_names]
    schema = _schema_for_node(node)
    outputs = getattr(schema, "outputs", None) or []
    return [
        str(getattr(output, "name", "")) if getattr(output, "name", None) else None
        for output in outputs
    ]


def _node_input_type(node: VibeNode | None, input_name: str) -> str | None:
    if node is None:
        return None
    schema = _schema_for_node(node)
    inputs = getattr(schema, "inputs", {}) or {}
    spec = inputs.get(input_name)
    if spec is None:
        return None
    value = getattr(spec, "type", None)
    return str(value) if value is not None else None


def _schema_for_node(node: VibeNode) -> object | None:
    schema = node.metadata.get("schema")
    if schema is not None:
        return schema
    try:
        from vibecomfy.schema import get_authoring_schema_provider

        return get_authoring_schema_provider().get_schema(node.class_type)
    except Exception:
        return None


def _compile_node_inputs(node: VibeNode) -> dict[str, Any]:
    inputs = dict(node.widgets)
    inputs.update(node.inputs)
    _apply_positional_widget_aliases(inputs, node)
    _drop_unused_positional_aliases(inputs)
    return {
        key: value
        for key, value in inputs.items()
        if not _is_ui_only_prompt_input(key, value)
    }


def _embedded_api_link_details(workflow: VibeWorkflow) -> list[dict[str, Any]]:
    """Describe canonical API links illegally embedded in IR node fields."""
    details: list[dict[str, Any]] = []
    edges_by_target: dict[tuple[str, str], list[list[Any]]] = {}
    for edge in workflow.edges:
        key = (str(edge.to_node), str(edge.to_input))
        try:
            output_slot: Any = int(edge.from_output)
        except (TypeError, ValueError):
            output_slot = str(edge.from_output)
        edges_by_target.setdefault(key, []).append([str(edge.from_node), output_slot])

    for node_id, node in workflow.nodes.items():
        for storage, values in (("inputs", node.inputs), ("widgets", node.widgets)):
            for input_name, value in values.items():
                if not is_canonical_api_link(value):
                    continue
                embedded_source = [str(value[0]), int(value[1])]
                edge_sources = edges_by_target.get((str(node_id), str(input_name)), [])
                if not edge_sources:
                    collision = "none"
                elif all(source == embedded_source for source in edge_sources):
                    collision = "identical"
                else:
                    collision = "conflicting"
                details.append(
                    {
                        "node_id": str(node_id),
                        "input_name": str(input_name),
                        "storage": storage,
                        "embedded_source": embedded_source,
                        "edge_sources": edge_sources,
                        "edge_collision": collision,
                    }
                )
    return details


def _embedded_api_link_message(detail: dict[str, Any], *, surface: str) -> str:
    collision = detail["edge_collision"]
    collision_text = ""
    if collision != "none":
        collision_text = f"; the socket also has {collision} VibeEdge connectivity"
    return (
        f"{surface} rejected node {detail['node_id']!r} input "
        f"{detail['input_name']!r}: embedded Comfy API link "
        f"{detail['embedded_source']!r}{collision_text}. "
        "VibeEdge is the sole IR connectivity authority."
    )


def _raise_embedded_api_links(workflow: VibeWorkflow, *, surface: str) -> None:
    details = _embedded_api_link_details(workflow)
    if not details:
        return
    detail = details[0]
    raise WorkflowCompileError(
        "embedded_api_link",
        _embedded_api_link_message(detail, surface=surface),
        detail=detail,
        next_action=(
            "Normalize raw workflows with from_api()/from_ui(), or replace the embedded "
            "pair with a VibeEdge before continuing."
        ),
    )


def _normalize_input_aliases(aliases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if aliases is None:
        return ()
    return tuple(str(alias) for alias in aliases)


def _format_available_names(names: Any) -> str:
    values = sorted(str(name) for name in names)
    return ", ".join(repr(value) for value in values) if values else "<none>"


def _is_ui_only_prompt_input(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key == "control_after_generate":
        return True
    if key == "add_noise_to_samples" and value == "":
        return True
    if key in {"videopreview", "preview", "preview_image"} and isinstance(value, dict):
        return True
    return False


def _is_ui_only_node(node: VibeNode) -> bool:
    return workflow_helpers.is_helper_class_type(node.class_type)


def _is_compile_stripped_node(node: VibeNode) -> bool:
    if _is_ui_only_node(node):
        return True
    if not _is_intent_node_class_type(node.class_type):
        return False
    return not _is_runtime_backed_code_intent_node(node)


def _is_intent_node_class_type(class_type: str) -> bool:
    try:
        from vibecomfy.contracts.intent_nodes import is_intent_class_type

        return is_intent_class_type(class_type)
    except Exception:
        return class_type in {"vibecomfy.code", "vibecomfy.loop"}


def _is_runtime_backed_code_intent_node(node: VibeNode) -> bool:
    try:
        from vibecomfy.contracts.intent_nodes import (
            KIND_TO_CLASS_TYPE,
            intent_node_payload_from_metadata,
            validate_runtime_code_contract,
        )
    except Exception:
        return False
    if node.class_type != KIND_TO_CLASS_TYPE["code"]:
        return False
    payload = intent_node_payload_from_metadata(node.metadata)
    runtime_result = validate_runtime_code_contract(
        class_type=node.class_type,
        payload=payload,
        require_runtime=True,
    )
    return runtime_result.ok


def _compile_intent_runtime_inputs(node: VibeNode) -> dict[str, Any]:
    try:
        from vibecomfy.contracts.intent_nodes import (
            KIND_TO_CLASS_TYPE,
            intent_node_payload_from_metadata,
            validate_intent_node_contract,
            validate_runtime_code_contract,
        )
    except Exception:
        return {}
    if node.class_type != KIND_TO_CLASS_TYPE["code"]:
        return {}
    payload = intent_node_payload_from_metadata(node.metadata)
    runtime_result = validate_runtime_code_contract(
        class_type=node.class_type,
        payload=payload,
        require_runtime=True,
    )
    if not runtime_result.ok or payload is None or runtime_result.normalized is None:
        return {}
    intent_result = validate_intent_node_contract(
        node_id=node.id,
        class_type=node.class_type,
        metadata=node.metadata,
    )
    intent = payload.get("intent")
    intent = intent if isinstance(intent, dict) else {}
    compiled: dict[str, Any] = {
        "runtime_backed": True,
        **runtime_result.normalized.as_dict(),
        "vibecomfy_uid": node.uid or intent_result.vibecomfy_uid,
        "kind": payload.get("kind"),
        "io": payload.get("io"),
    }
    source = intent.get("source")
    spec = intent.get("spec")
    if isinstance(source, str):
        compiled["source"] = source
    if isinstance(spec, str):
        compiled["spec"] = spec
    return compiled


def _get_node_mode(node: VibeNode) -> int:
    """Read display mode, including captured UI evidence for UI emission."""
    mode = getattr(node, "mode", None)
    ui = node.metadata.get("_ui")
    if isinstance(ui, dict) and isinstance(ui.get("mode"), int):
        return ui["mode"]
    return mode_to_litegraph(mode) if mode is not None else 0


def _compute_dropped_bypassed_ids(
    nodes: dict[str, VibeNode],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return (dropped_ids, bypassed_ids) for compile(api) mode filtering.

    dropped_ids: node ids with mode 2 (muted) or mode 4 (bypassed) — excluded from output.
    bypassed_ids: subset of dropped_ids with mode 4 — edges are rewired around them.
    """
    dropped: set[str] = set()
    bypassed: set[str] = set()
    for node_id, node in nodes.items():
        # UI-captured mode is presentation evidence and never affects
        # execution.  Only the semantic IR field can drop or bypass a node.
        mode = mode_to_litegraph(getattr(node, "mode", None)) if getattr(node, "mode", None) is not None else 0
        if mode in (_MODE_MUTED, _MODE_BYPASS):
            dropped.add(str(node_id))
        if mode == _MODE_BYPASS:
            bypassed.add(str(node_id))
    return frozenset(dropped), frozenset(bypassed)


def _types_match(a: Any, b: Any) -> bool:
    """Match Comfy socket unions and wildcards without coercing literals."""
    if a is None or b is None:
        return False
    a_values = {part.strip().upper() for part in str(a).split(",") if part.strip()}
    b_values = {part.strip().upper() for part in str(b).split(",") if part.strip()}
    if not a_values or not b_values:
        return False
    if "*" in a_values or "*" in b_values or a_values & b_values:
        return True
    # Comfy's widget-facing choice/enum sockets are the same value channel;
    # the installed schema names them differently depending on provider.
    return bool(a_values & {"ENUM", "CHOICE"} and b_values & {"ENUM", "CHOICE"})


def _node_input_socket_type(node: VibeNode | None, input_name: Any) -> str | None:
    if node is None:
        return None
    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    declared = metadata.get("input_types")
    names = getattr(node, "native_input_names", None) or metadata.get("input_names")
    if isinstance(declared, Mapping):
        value = declared.get(str(input_name), declared.get(input_name))
        if value is not None:
            return str(value)
    if isinstance(declared, (list, tuple)):
        index = _socket_index(names, input_name)
        if index is None:
            try:
                index = int(input_name)
            except (TypeError, ValueError):
                index = None
        if index is not None and 0 <= index < len(declared) and declared[index] is not None:
            return str(declared[index])
    schema = _schema_for_node(node)
    inputs = getattr(schema, "inputs", {}) or {}
    spec = inputs.get(str(input_name))
    return str(getattr(spec, "type", None)) if spec is not None and getattr(spec, "type", None) else None


def _node_output_socket_type(node: VibeNode | None, output: Any) -> str | None:
    if node is None:
        return None
    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    declared = metadata.get("output_types")
    index = _socket_index(getattr(node, "native_output_names", None) or metadata.get("output_names"), output)
    if index is None:
        index = _socket_index(None, output)
    if isinstance(declared, Mapping):
        value = declared.get(str(output), declared.get(output))
        if value is not None:
            return str(value)
    if isinstance(declared, (list, tuple)) and index is not None and 0 <= index < len(declared):
        if declared[index] is not None:
            return str(declared[index])
    return _node_output_type(node, index if index is not None else output)


def _socket_index(names: Any, value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    if isinstance(names, (list, tuple)):
        for index, name in enumerate(names):
            if name is not None and str(name).upper() == str(value).upper():
                return index
    return None


def _port_roster(node: Any, direction: str) -> Any:
    field = f"native_{direction}_names"
    roster = getattr(node, field, None)
    if roster is None and isinstance(node, Mapping):
        roster = node.get(field)
    if roster is None:
        metadata = getattr(node, "metadata", None)
        if metadata is None and isinstance(node, Mapping):
            metadata = node.get("metadata")
        if isinstance(metadata, Mapping):
            roster = metadata.get(f"{direction}_names")
    if roster is None and isinstance(node, Mapping):
        raw_sockets = node.get("outputs" if direction == "output" else "inputs")
        if isinstance(raw_sockets, (list, tuple)):
            roster = [
                item.get("name") if isinstance(item, Mapping) else None
                for item in raw_sockets
            ]
    if roster is None and direction == "input":
        inputs = getattr(node, "inputs", None)
        if inputs is None and isinstance(node, Mapping):
            inputs = node.get("inputs")
        if isinstance(inputs, Mapping) and inputs:
            roster = list(inputs)
    return roster


def _port_index_for_node(
    node: Any, value: Any, direction: str, where: str, *, require_roster: bool = False
) -> int:
    """Resolve one authored socket through the single native/metadata roster."""
    roster = _port_roster(node, direction)
    if require_roster and not isinstance(roster, (list, tuple)):
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
            f"cannot derive {direction} port {value!r}: native {direction} roster is missing at {where}",
        )
    if isinstance(roster, (list, tuple)):
        # A roster is evidence, not merely a length hint.  Empty rosters and
        # holes are authoritative; malformed entries must never be converted
        # into a guessed slot or a dictionary-order fallback.
        for position, name in enumerate(roster):
            if name is not None and (not isinstance(name, str) or not name.strip()):
                raise WorkflowCompileError(
                    "unknown_virtual_wire_port",
                    f"{direction} roster entry {position} at {where} is malformed",
                )
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (int, str)):
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
                f"cannot derive from port {value!r} at {where}",
        )
    index: int | None = None
    if isinstance(value, int):
        index = value
    elif value.strip().isdigit():
        index = int(value.strip())
    elif isinstance(roster, (list, tuple)):
        matches = [
            position for position, name in enumerate(roster)
            if name is not None and str(name).casefold() == value.casefold()
        ]
        if len(matches) > 1:
            raise WorkflowCompileError(
                "ambiguous_virtual_wire_port",
                f"cannot derive from port {value!r} at {where}: roster name is ambiguous",
            )
        if matches:
            index = matches[0]
    if index is None:
        if isinstance(roster, (list, tuple)):
            raise WorkflowCompileError(
                "unknown_virtual_wire_port",
                f"cannot derive from port {value!r} from native Python roster at {where}",
            )
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
            f"cannot derive from port {value!r}: native Python roster is missing at {where}",
        )
    if index < 0 or isinstance(roster, (list, tuple)) and (
        index >= len(roster) or roster[index] is None
    ):
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
            f"{direction} port {value!r} at {where} is outside or a hole in the native Python roster",
        )
    return index


def _port_name_for_node(node: Any, index: int, direction: str, where: str) -> str:
    """Return the exact authored field name for one resolved socket."""
    roster = _port_roster(node, direction)
    if not isinstance(roster, (list, tuple)):
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
            f"cannot derive {direction} port name at {where}: native {direction} roster is missing",
        )
    if index < 0 or index >= len(roster) or roster[index] is None:
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
            f"{direction} port {index} at {where} is outside or a hole in the native Python roster",
        )
    name = roster[index]
    if not isinstance(name, str) or not name.strip():
        raise WorkflowCompileError(
            "unknown_virtual_wire_port",
            f"{direction} port {index} at {where} has no exact declared field name",
        )
    return name


def _input_slot_for_node(node: Any, value: Any, where: str = "input") -> int:
    return _port_index_for_node(node, value, "input", where)


def _output_slot_for_node(nodes: Mapping[str, VibeNode] | None, node_id: str, output: Any) -> str:
    node = nodes.get(str(node_id)) if nodes is not None else None
    if node is None:
        raise WorkflowCompileError("unknown_output_handle", f"node {node_id!r} is missing")
    try:
        index = _port_index_for_node(node, output, "output", f"node {node_id!r}")
    except WorkflowCompileError as exc:
        raise WorkflowCompileError(
            "unknown_output_handle",
            str(exc),
            detail={"node_id": node_id, "output": output},
            next_action="Use a declared output name or numeric output index.",
        ) from exc
    return str(index)


def _input_index_for_edge(node: VibeNode | None, edge: VibeEdge) -> int | None:
    if node is None:
        return None
    try:
        return _input_slot_for_node(node, edge.to_input)
    except WorkflowCompileError:
        return None


def _choose_bypass_input_slot(
    bypass_node: VibeNode | None,
    bypass_output: Any,
    feeds: list[VibeEdge],
    nodes: Mapping[str, VibeNode] | None,
    *,
    target_node_id: str,
    target_input: str,
) -> int:
    if bypass_node is None:
        if len(feeds) == 1:
            return 0
        try:
            slot = int(bypass_output)
        except (TypeError, ValueError) as exc:
            raise WorkflowCompileError(
                "bypass_ambiguous",
                f"cannot match bypass output {bypass_output!r} without socket schema",
                next_action="Provide the bypass node input/output socket schema.",
            ) from exc
        if 0 <= slot < len(feeds):
            return slot
        raise WorkflowCompileError("bypass_no_match", f"bypass output {bypass_output!r} has no inbound source")

    target = nodes.get(target_node_id) if nodes is not None else None
    target_type = _node_input_socket_type(target, target_input)
    output_type = _node_output_socket_type(bypass_node, bypass_output)
    indexed: list[tuple[int, VibeEdge]] = []
    for ordinal, feed in enumerate(feeds):
        idx = _input_index_for_edge(bypass_node, feed)
        indexed.append((ordinal if idx is None else idx, feed))
    candidates: list[int] = []
    for ordinal, (input_index, feed) in enumerate(indexed):
        input_type = _node_input_socket_type(bypass_node, feed.to_input)
        source_type = _node_output_socket_type(nodes.get(str(feed.from_node)) if nodes else None, feed.from_output)
        compatible = True
        for left, right in ((input_type, output_type), (input_type, target_type), (source_type, target_type)):
            if left is not None and right is not None and not _types_match(left, right):
                compatible = False
        if compatible:
            candidates.append(ordinal)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise WorkflowCompileError(
            "bypass_ambiguous",
            f"bypassed node {bypass_node.id!r} has multiple compatible inbound sources",
            detail={"node_id": bypass_node.id, "target_node_id": target_node_id, "target_input": target_input},
            next_action="Connect exactly one socket-compatible inbound source.",
        )
    raise WorkflowCompileError(
        "bypass_no_match",
        f"bypassed node {bypass_node.id!r} has no socket-compatible inbound source",
        detail={"node_id": bypass_node.id, "target_node_id": target_node_id, "target_input": target_input},
        next_action="Reconnect the bypassed node with a compatible source socket.",
    )


@dataclass(frozen=True, slots=True)
class _ResolvedVirtualWireLeg:
    wire_name: str
    scope_path: str
    leg_index: int
    occurrence_index: int
    from_node: str
    from_lookup: str
    from_output: str
    from_port: int
    to_node: str
    to_lookup: str
    to_input: str
    to_port: int


def _virtual_wire_nodes(nodes: Mapping[str, Any], scope: str) -> tuple[dict[str, str], dict[str, Any], dict[str, str]]:
    """Build collision-checked local aliases and qualified node objects."""
    from vibecomfy.identity.uid import make_uid

    aliases: dict[str, str] = {}
    aliases_folded: dict[str, str] = {}
    by_qualified: dict[str, Any] = {}
    lookup_by_qualified: dict[str, str] = {}
    for key, node in nodes.items():
        raw_key = str(key)
        key_scope = raw_key.rsplit("#", 1)[0] if "#" in raw_key else scope
        if key_scope != scope:
            continue
        lookup = raw_key if "#" in raw_key else make_uid(scope, raw_key)
        if isinstance(node, Mapping):
            properties = node.get("properties")
            local_uid = node.get("uid")
            if not local_uid and isinstance(properties, Mapping):
                local_uid = properties.get("vibecomfy_uid")
            local_uid = local_uid or node.get("id") or raw_key
        else:
            local_uid = getattr(node, "uid", None) or getattr(node, "id", raw_key)
        qualified = str(local_uid) if "#" in str(local_uid) else make_uid(scope, str(local_uid))
        if qualified in by_qualified:
            raise WorkflowCompileError(
                "virtual_wire_ambiguous_endpoint",
                f"duplicate node UID {local_uid!r} is ambiguous in scope {scope!r}",
            )
        candidates = [raw_key]
        if isinstance(node, Mapping):
            candidates.extend(str(node.get(field)) for field in ("uid", "id") if node.get(field) is not None)
            if isinstance(properties, Mapping) and properties.get("vibecomfy_uid") is not None:
                candidates.append(str(properties["vibecomfy_uid"]))
        else:
            candidates.extend(str(getattr(node, field)) for field in ("uid", "id") if getattr(node, field, None) is not None)
        for alias in candidates:
            if not alias.strip():
                continue
            prior = aliases.get(alias)
            if prior is not None and prior != qualified:
                raise WorkflowCompileError("virtual_wire_ambiguous_endpoint", f"endpoint alias {alias!r} is ambiguous in scope {scope!r}")
            aliases[alias] = qualified
            folded = alias.casefold()
            prior_folded = aliases_folded.get(folded)
            if prior_folded is not None and prior_folded != qualified:
                raise WorkflowCompileError("virtual_wire_ambiguous_endpoint", f"endpoint alias {alias!r} is ambiguous in scope {scope!r}")
            aliases_folded[folded] = qualified
        by_qualified[qualified] = node
        lookup_by_qualified[qualified] = lookup
    # Keep exact aliases in the first map and case-insensitive aliases in the
    # same detached lookup table.  Node identity is local and unambiguous;
    # consumers never need to invent another alias rule.
    aliases.update({key: value for key, value in aliases_folded.items() if key not in aliases})
    return aliases, by_qualified, lookup_by_qualified


def _virtual_wire_alias_values(leg: Mapping[str, Any], prefix: str, field_names: tuple[str, ...]) -> list[Any]:
    values: list[Any] = []
    for field in field_names:
        if field in leg:
            values.append(leg[field])
    nested = leg.get(prefix)
    if isinstance(nested, Mapping):
        for field in ("uid", "node", "id") if prefix in {"from", "to"} else ():
            if field in nested:
                values.append(nested[field])
    return values


def _virtual_wire_port_values(leg: Mapping[str, Any], prefix: str, field_names: tuple[str, ...]) -> list[Any]:
    values = [leg[field] for field in field_names if field in leg]
    nested = leg.get(prefix)
    if isinstance(nested, Mapping):
        values.extend(nested[field] for field in ("port", "output", "input") if field in nested)
    return values


def _resolve_virtual_wire_legs(
    nodes: Mapping[str, Any], virtual_wires: Mapping[str, Any], *, scope_path: str = ""
) -> list[_ResolvedVirtualWireLeg]:
    """Normalize every authored virtual leg through one strict port authority."""
    if not isinstance(virtual_wires, Mapping):
        raise WorkflowCompileError("virtual_wire_malformed", "virtual_wires must be a mapping")
    from vibecomfy.identity.uid import make_uid, parse_uid, validate_local_uid

    result: list[_ResolvedVirtualWireLeg] = []
    for name, raw in sorted(virtual_wires.items(), key=lambda item: str(item[0])):
        if not isinstance(name, str) or not name.strip():
            raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} name must be a nonblank string")
        if not isinstance(raw, Mapping):
            raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} must be a mapping")
        if "channel" in raw or "endpoints" in raw:
            raise WorkflowCompileError("legacy_virtual_wire", f"virtual wire {name!r} uses legacy channel/endpoints evidence; no materialized leg exists")
        if "occurrences" in raw and "legs" not in raw:
            raise WorkflowCompileError("legacy_virtual_wire", f"virtual wire {name!r} uses legacy occurrences; author explicit legs instead")
        legs = raw.get("legs")
        if legs is None:
            raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} lacks explicit legs")
        if not isinstance(legs, (list, tuple)):
            raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} legs must be a list")
        declared_scope = raw.get("scope_path")
        if declared_scope is not None and not isinstance(declared_scope, str):
            raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} scope_path must be a string")
        wire_declares_scope = declared_scope is not None
        if declared_scope is None:
            declared_scope = scope_path
        occurrences_by_leg: dict[tuple[str, int], list[int]] = {}
        records_by_leg: dict[tuple[str, int], _ResolvedVirtualWireLeg] = {}
        resolved_records: list[_ResolvedVirtualWireLeg] = []
        seen_records: set[tuple[int, int, str, int, str, int]] = set()
        for ordinal, authored in enumerate(legs):
            leg: Mapping[str, Any]
            if isinstance(authored, (list, tuple)) and len(authored) == 4:
                leg = {"from_node": authored[0], "from_output": authored[1], "to_node": authored[2], "to_input": authored[3]}
            elif isinstance(authored, Mapping):
                leg = authored
            else:
                raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} leg {ordinal} is a malformed Python leg")
            # Normalized canonical legs carry all seven fields.  Complete
            # unindexed endpoint legs remain accepted as the one compatibility
            # normalization boundary; scope depth alone must not turn those
            # legacy records into a partially canonical record.
            canonical_leg = (
                "scope_path" in leg
                or wire_declares_scope
                or "from_output" in leg
            )
            if canonical_leg:
                required = {"scope_path", "leg_index", "occurrence_index"}
                missing = sorted(required.difference(leg))
                endpoint_aliases = (
                    ("from_node", "from_uid", "origin_id"),
                    ("to_node", "to_uid", "target_id"),
                    ("from_output", "from_port", "origin_slot"),
                    ("to_input", "to_port", "target_slot"),
                )
                missing.extend(
                    "/".join(options)
                    for options in endpoint_aliases
                    if not any(option in leg for option in options)
                )
                if missing:
                    raise WorkflowCompileError(
                        "virtual_wire_malformed",
                        f"virtual wire {name!r} leg {ordinal} lacks canonical field(s): {', '.join(missing)}",
                    )
            legacy_unindexed = not canonical_leg and "leg_index" not in leg and "occurrence_index" not in leg
            leg_index = ordinal if "leg_index" not in leg else leg.get("leg_index")
            occurrence_index = 0 if "occurrence_index" not in leg else leg.get("occurrence_index")
            if isinstance(leg_index, bool) or not isinstance(leg_index, int) or leg_index < 0:
                raise WorkflowCompileError("virtual_wire_index", f"virtual wire {name!r} leg {ordinal} has invalid leg_index")
            if isinstance(occurrence_index, bool) or not isinstance(occurrence_index, int) or occurrence_index < 0:
                raise WorkflowCompileError("virtual_wire_index", f"virtual wire {name!r} leg {ordinal} has invalid occurrence_index")
            scope = leg.get("scope_path", declared_scope)
            if not isinstance(scope, str):
                raise WorkflowCompileError("virtual_wire_cross_scope", f"virtual wire {name!r} leg {ordinal} has an invalid scope")
            if wire_declares_scope and scope != declared_scope:
                raise WorkflowCompileError("virtual_wire_cross_scope", f"virtual wire {name!r} leg {ordinal} crosses scope {declared_scope!r}")
            if scope != scope_path:
                raise WorkflowCompileError("virtual_wire_cross_scope", f"virtual wire {name!r} leg {ordinal} crosses scope {scope_path!r}")
            aliases, by_qualified, lookup_by_qualified = _virtual_wire_nodes(nodes, scope)
            if any(part.startswith("sg") and part[2:].isdigit() for part in scope.split("/") if part):
                raise WorkflowCompileError("ordinal_scope_path", f"virtual wire {name!r} uses an ordinal scope path")
            from_nodes = _virtual_wire_alias_values(leg, "from", ("from_node", "from_uid", "origin_id"))
            to_nodes = _virtual_wire_alias_values(leg, "to", ("to_node", "to_uid", "target_id"))
            if not from_nodes or not to_nodes:
                raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} leg {ordinal} lacks an endpoint")
            def resolve_endpoint(values: list[Any], side: str) -> tuple[str, Any]:
                values = [str(value) if isinstance(value, int) and not isinstance(value, bool) else value for value in values]
                if any(not isinstance(value, str) or not value.strip() for value in values):
                    raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} leg {ordinal} has an invalid {side} endpoint")
                resolved: list[str] = []
                for value in values:
                    if "#" in value:
                        qualified = value
                    else:
                        qualified = aliases.get(value) or aliases.get(value.casefold()) or make_uid(scope, value)
                    if qualified not in by_qualified:
                        raise WorkflowCompileError("virtual_wire_unresolved", f"virtual wire {name!r} leg endpoint is not local to {scope!r}")
                    endpoint_scope, local = parse_uid(qualified)
                    validate_local_uid(local, field=f"virtual wire {side}_uid")
                    if endpoint_scope != scope:
                        raise WorkflowCompileError("virtual_wire_cross_scope", f"virtual wire {name!r} leg {ordinal} crosses scope {scope!r}")
                    resolved.append(qualified)
                if len(set(resolved)) != 1:
                    raise WorkflowCompileError("virtual_wire_conflict", f"virtual wire {name!r} leg {ordinal} has conflicting {side} aliases")
                return resolved[0], by_qualified[resolved[0]]
            source, source_node = resolve_endpoint(from_nodes, "from")
            target, target_node = resolve_endpoint(to_nodes, "to")
            from_values = _virtual_wire_port_values(leg, "from", ("from_output", "from_port", "origin_slot"))
            to_values = _virtual_wire_port_values(leg, "to", ("to_input", "to_port", "target_slot"))
            if not from_values:
                if canonical_leg:
                    raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} leg {ordinal} lacks a source port")
                from_values = [0]
            if not to_values:
                raise WorkflowCompileError("virtual_wire_malformed", f"virtual wire {name!r} leg {ordinal} lacks a port")
            from_indexes = [_port_index_for_node(source_node, value, "output", f"virtual wire {name!r} leg {ordinal}", require_roster=canonical_leg) for value in from_values]
            to_indexes = [_port_index_for_node(target_node, value, "input", f"virtual wire {name!r} leg {ordinal}", require_roster=canonical_leg) for value in to_values]
            if len(set(from_indexes)) != 1 or len(set(to_indexes)) != 1:
                raise WorkflowCompileError("virtual_wire_conflict", f"virtual wire {name!r} leg {ordinal} has conflicting port aliases")
            from_index, to_index = from_indexes[0], to_indexes[0]
            if canonical_leg:
                from_output = _port_name_for_node(source_node, from_index, "output", f"virtual wire {name!r} leg {ordinal}")
                to_input = _port_name_for_node(target_node, to_index, "input", f"virtual wire {name!r} leg {ordinal}")
            else:
                # Complete legacy legs remain a single normalization boundary.
                # When a roster is present, retain its exact semantic field
                # name for downstream display consumers; otherwise preserve
                # the authored compatibility spelling.
                try:
                    from_output = _port_name_for_node(source_node, from_index, "output", f"virtual wire {name!r} leg {ordinal}")
                except WorkflowCompileError:
                    from_output = next((value for value in from_values if isinstance(value, str) and not value.strip().isdigit()), str(from_index))
                try:
                    to_input = _port_name_for_node(target_node, to_index, "input", f"virtual wire {name!r} leg {ordinal}")
                except WorkflowCompileError:
                    to_input = next((value for value in to_values if isinstance(value, str) and not value.strip().isdigit()), str(to_index))
            resolved = _ResolvedVirtualWireLeg(
                name,
                scope,
                leg_index,
                occurrence_index,
                source,
                lookup_by_qualified[source],
                str(from_output),
                from_index,
                target,
                lookup_by_qualified[target],
                str(to_input),
                to_index,
            )
            group = (scope, leg_index)
            occurrences_by_leg.setdefault(group, []).append(occurrence_index)
            record_key = (leg_index, occurrence_index, source, from_index, target, to_index)
            if record_key in seen_records:
                raise WorkflowCompileError("virtual_wire_duplicate", f"virtual wire {name!r} repeats an occurrence")
            seen_records.add(record_key)
            resolved_records.append(resolved)
            prior = records_by_leg.get(group)
            if prior is not None and (prior.from_node, prior.from_port, prior.to_node, prior.to_port) != (source, from_index, target, to_index):
                raise WorkflowCompileError("virtual_wire_conflict", f"virtual wire {name!r} occurrences for leg {leg_index} disagree on endpoints")
            records_by_leg[group] = resolved
        leg_indexes = sorted({leg_index for _scope, leg_index in records_by_leg})
        if leg_indexes != list(range(len(leg_indexes))):
            raise WorkflowCompileError("virtual_wire_index", f"virtual wire {name!r} leg indexes must be contiguous from zero in scope {declared_scope!r}")
        for (_scope, leg_index), occurrence_indexes in occurrences_by_leg.items():
            if sorted(occurrence_indexes) != list(range(len(occurrence_indexes))) or len(occurrence_indexes) != len(set(occurrence_indexes)):
                raise WorkflowCompileError("virtual_wire_index", f"virtual wire {name!r} occurrence indexes for leg {leg_index} must be unique and contiguous from zero")
        result.extend(sorted(resolved_records, key=lambda item: (item.wire_name, item.scope_path, item.leg_index, item.occurrence_index)))
    return result


def _resolve_workflow_virtual_wire_records(workflow: Any) -> dict[tuple[str, str], tuple[_ResolvedVirtualWireLeg, ...]]:
    """Resolve every authored virtual leg for a workflow into detached records.

    This is the shared projection boundary for bundle and UI consumers.  The
    records retain structural scope, local endpoint identity, UI slots, and
    exact API field names; consumers must not decode ports or endpoint aliases
    again.
    """
    from vibecomfy.identity.scope import compose_scope_path, sg_key

    resolved: dict[tuple[str, str], tuple[_ResolvedVirtualWireLeg, ...]] = {}

    def entries(raw: Any) -> list[Mapping[str, Any]]:
        if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), (list, tuple)):
            return [item for item in raw["subgraphs"] if isinstance(item, Mapping)]
        if isinstance(raw, Mapping):
            return [item for item in raw.values() if isinstance(item, Mapping)]
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, Mapping)]
        return []

    def node_map(raw_nodes: Any) -> dict[str, Any]:
        values = raw_nodes.values() if isinstance(raw_nodes, Mapping) else raw_nodes
        if not isinstance(values, (list, tuple)) and not hasattr(values, "__iter__"):
            return {}
        result: dict[str, Any] = {}
        for ordinal, node in enumerate(values):
            if not isinstance(node, Mapping):
                continue
            props = node.get("properties")
            local = node.get("uid")
            if not isinstance(local, str) or not local.strip():
                local = props.get("vibecomfy_uid") if isinstance(props, Mapping) else None
            if not isinstance(local, str) or not local.strip():
                local = node.get("id")
            if local is not None:
                # Keep every source record visible to the shared collision
                # checker.  Keying this temporary map by local UID would
                # overwrite a duplicate before `_virtual_wire_nodes` could
                # reject it.
                result[f"__resolver_node_{ordinal}"] = node
        return result

    def visit(definitions: Any, parent: tuple[str, ...]) -> None:
        for definition in entries(definitions):
            key = sg_key(definition)
            scope = compose_scope_path((*parent, key))
            wires = definition.get("virtual_wires", {})
            if wires not in (None, {}):
                for record in _resolve_virtual_wire_legs(node_map(definition.get("nodes", [])), wires, scope_path=scope):
                    resolved.setdefault((scope, record.wire_name), tuple())
                    resolved[(scope, record.wire_name)] += (record,)
            visit(definition.get("definitions"), (*parent, key))

    root_wires = getattr(workflow, "virtual_wires", {})
    if root_wires == {}:
        metadata = getattr(workflow, "metadata", None)
        if isinstance(metadata, Mapping):
            root_wires = metadata.get("virtual_wires", {})
    if root_wires not in (None, {}):
        for record in _resolve_virtual_wire_legs(getattr(workflow, "nodes", {}), root_wires, scope_path=""):
            resolved.setdefault(("", record.wire_name), tuple())
            resolved[("", record.wire_name)] += (record,)
    definitions = getattr(workflow, "definitions", None)
    if not definitions:
        metadata = getattr(workflow, "metadata", None)
        definitions = metadata.get("definitions", {}) if isinstance(metadata, Mapping) else {}
    visit(definitions, ())
    return {
        key: tuple(sorted(value, key=lambda item: (item.leg_index, item.occurrence_index)))
        for key, value in resolved.items()
    }


def _virtual_wire_edges(
    nodes: Mapping[str, VibeNode], virtual_wires: Mapping[str, Any]
) -> list[VibeEdge]:
    """Materialize explicit Python-owned virtual-wire legs for this view."""
    result: list[VibeEdge] = []
    seen: set[tuple[str, str, int]] = set()
    # Root execution owns root nodes and root virtual wires.  Splitting one
    # authored wire into per-scope fragments before resolution loses index
    # contiguity and lets a nested definition's local IDs leak into the root.
    # Resolve the complete detached record set once, then collapse only the
    # execution endpoint tuple (occurrence identity remains available to UI).
    for leg in _resolve_virtual_wire_legs(nodes, virtual_wires, scope_path=""):
        if (leg.wire_name, leg.scope_path, leg.leg_index) in seen:
            continue
        seen.add((leg.wire_name, leg.scope_path, leg.leg_index))
        result.append(VibeEdge(leg.from_lookup, leg.from_output, leg.to_lookup, leg.to_input))
    return result


@dataclass(frozen=True, slots=True)
class _ExecutionProjection:
    """The mode-aware graph view consumed by execution backends.

    The rich IR remains the authority for envelopes and editor surfaces.  This
    small view is deliberately limited to execution concerns: nodes that never
    execute are omitted and bypass edges are resolved around them.
    """

    nodes: dict[str, VibeNode]
    edges: list[VibeEdge]
    dropped_ids: frozenset[str]
    bypassed_ids: frozenset[str]


def _resolve_projection_helpers(
    nodes: dict[str, VibeNode], edges: list[VibeEdge]
) -> tuple[dict[str, VibeNode], list[VibeEdge]]:
    try:
        helper_resolve.resolve_helpers(nodes, edges, {})
    except helper_resolve.HelperResolveError as exc:
        raise WorkflowCompileError(
            getattr(exc, "code", "helper_edge_unresolved"),
            str(exc),
            next_action=exc.next_action or "Reconnect or remove the unresolved helper chain.",
        ) from exc
    return nodes, edges


def _resolve_bypass_edges(
    edges: list[VibeEdge],
    dropped_ids: frozenset[str],
    bypassed_ids: frozenset[str],
    nodes: Mapping[str, VibeNode] | None = None,
) -> list[VibeEdge]:
    """Rewrite the edge list to remove muted/bypassed nodes.

    Mirrors ComfyUI workflow_convert.py _MODE_NEVER/_MODE_BYPASS semantics:
    - Edges targeting any dropped node are removed.
    - Edges sourcing from muted (mode=2) nodes are removed.
    - Edges sourcing from bypassed (mode=4) nodes are resolved to their bypass
      source using same-slot index matching (output slot N maps to the N-th
      incoming edge, or slot 0 if N is out of range).

    Returns edges unchanged when dropped_ids is empty (byte-identical fast path).
    """
    if not dropped_ids:
        return edges

    incoming: dict[str, list[VibeEdge]] = {}
    for edge in edges:
        incoming.setdefault(str(edge.to_node), []).append(edge)

    def _follow(
        node_id: str,
        from_out: str,
        seen: frozenset[str],
        target_node_id: str,
        target_input: str,
    ) -> tuple[str, str]:
        if node_id in seen:
            raise WorkflowCompileError(
                "bypass_cycle",
                f"bypass cycle while resolving {node_id!r} to {target_node_id!r}.{target_input!r}",
                detail={"node_id": node_id, "target_node_id": target_node_id, "target_input": target_input},
                next_action="Break the bypass cycle or reconnect the target input.",
            )
        if node_id not in dropped_ids:
            return (node_id, _output_slot_for_node(nodes, node_id, from_out))
        if node_id not in bypassed_ids:
            raise WorkflowCompileError(
                "bypass_dangling",
                f"muted node {node_id!r} cannot provide {target_node_id!r}.{target_input!r}",
                detail={"node_id": node_id, "target_node_id": target_node_id, "target_input": target_input},
                next_action="Reconnect the target input or bypass a node with a compatible source.",
            )
        bypass_node = nodes.get(node_id) if nodes is not None else None
        feeds = incoming.get(node_id, [])
        if not feeds:
            raise WorkflowCompileError(
                "bypass_dangling",
                f"bypassed node {node_id!r} has no inbound source",
                detail={"node_id": node_id, "target_node_id": target_node_id, "target_input": target_input},
                next_action="Connect an input to the bypassed node before compiling.",
            )
        slot = _choose_bypass_input_slot(
            bypass_node,
            from_out,
            feeds,
            nodes,
            target_node_id=target_node_id,
            target_input=target_input,
        )
        feed = feeds[slot]
        return _follow(
            str(feed.from_node), feed.from_output, seen | {node_id}, target_node_id, target_input
        )

    result: list[VibeEdge] = []
    for edge in edges:
        from_id = str(edge.from_node)
        to_id = str(edge.to_node)
        if to_id in dropped_ids:
            continue
        if from_id in dropped_ids:
            if from_id not in bypassed_ids:
                continue
            resolved = _follow(
                from_id,
                edge.from_output,
                frozenset(),
                to_id,
                str(edge.to_input),
            )
            nf, no = resolved
            result.append(VibeEdge(nf, no, edge.to_node, edge.to_input))
        else:
            result.append(edge)
    return result


def _execution_projection(
    nodes: dict[str, VibeNode],
    edges: list[VibeEdge],
    *,
    virtual_wires: Mapping[str, Any] | None = None,
) -> _ExecutionProjection:
    """Return the shared mode/bypass/edge projection for execution surfaces."""
    projected_nodes = copy.deepcopy(nodes)
    projected_edges = copy.deepcopy(edges)
    existing_edges = {(e.from_node, e.from_output, e.to_node, e.to_input) for e in projected_edges}
    for virtual_edge in _virtual_wire_edges(projected_nodes, virtual_wires or {}):
        key = (virtual_edge.from_node, virtual_edge.from_output, virtual_edge.to_node, virtual_edge.to_input)
        if key not in existing_edges:
            projected_edges.append(virtual_edge)
            existing_edges.add(key)
        # ``occurrence_index`` is presentation multiplicity.  Once a complete
        # semantic leg has been validated, an exact endpoint tuple is one
        # executable edge even when two semantic legs or an authored edge
        # point at it.  Ordinary authored VibeEdges remain untouched so their
        # cardinality diagnostics are still meaningful.
    dropped_ids, bypassed_ids = _compute_dropped_bypassed_ids(projected_nodes)
    resolved_edges = _resolve_bypass_edges(
        projected_edges, dropped_ids, bypassed_ids, projected_nodes
    )
    projected_nodes, resolved_edges = _resolve_projection_helpers(projected_nodes, resolved_edges)
    projected_nodes = {
        str(node_id): node
        for node_id, node in projected_nodes.items()
        if str(node_id) not in dropped_ids
    }
    return _ExecutionProjection(
        nodes=projected_nodes,
        edges=resolved_edges,
        dropped_ids=dropped_ids,
        bypassed_ids=bypassed_ids,
    )


def _rewrite_broadcast_links(
    inputs: dict[str, Any],
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> dict[str, Any]:
    return {
        key: _resolve_link_value(value, nodes, broadcast_sources)
        for key, value in inputs.items()
    }


def _resolve_edge_source(
    edge: VibeEdge,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> list[Any] | None:
    return helper_resolve.resolve_compile_edge_source(edge, nodes, broadcast_sources)


def _compile_resolved_edge_inputs(
    nodes: dict[str, VibeNode],
    edges: list[VibeEdge],
    broadcast_sources: dict[str, list[Any]],
    *,
    dropped_ids: frozenset[str] = frozenset(),
) -> dict[str, dict[str, list[Any]]]:
    """Build target->input resolved edge mapping shared by compile backends."""
    resolved: dict[str, dict[str, list[Any]]] = {}
    compiled_node_ids = {
        str(node_id)
        for node_id, node in nodes.items()
        if not _is_compile_stripped_node(node) and str(node_id) not in dropped_ids
    }
    target_edges: dict[tuple[str, str], list[int]] = {}
    for edge_index, edge in enumerate(edges):
        target_node_id = str(edge.to_node)
        target_node = nodes.get(target_node_id)
        if target_node is None:
            raise WorkflowCompileError(
                "compiled_edge_missing_endpoint",
                f"Edge target node {target_node_id!r} for input {edge.to_input!r} is missing.",
                detail={"target_node_id": target_node_id, "target_input": edge.to_input},
                next_action="Remove the dangling edge or restore the target node before compiling.",
            )
        if target_node_id not in compiled_node_ids:
            continue
        edge_source = _resolve_compiled_source_ref(
            str(edge.from_node),
            edge.from_output,
            nodes,
            broadcast_sources,
            visited=set(),
            target_node_id=target_node_id,
            target_input=edge.to_input,
        )
        if str(edge_source[0]) not in compiled_node_ids:
            if _can_ignore_compile_stripped_edge(edge, nodes):
                continue
            raise WorkflowCompileError(
                "compiled_edge_missing_endpoint",
                (
                    f"Edge {edge.from_node!r}.{edge.from_output!r} -> "
                    f"{target_node_id!r}.{edge.to_input!r} resolves to stripped or missing "
                    f"source node {edge_source[0]!r}."
                ),
                detail={
                    "source_node_id": str(edge_source[0]),
                    "target_node_id": target_node_id,
                    "target_input": edge.to_input,
                },
                next_action="Reconnect the target input to a runtime node before compiling.",
            )
        target_key = (target_node_id, str(edge.to_input))
        prior_edge_indices = target_edges.setdefault(target_key, [])
        if prior_edge_indices:
            prior_edge_indices.append(edge_index)
            raise WorkflowCompileError(
                "target_input_cardinality",
                (
                    f"Target input {target_node_id!r}.{edge.to_input!r} has multiple "
                    "execution edges; one input accepts exactly one edge."
                ),
                detail={
                    "target_node_id": target_node_id,
                    "target_input": str(edge.to_input),
                    "edge_indices": list(prior_edge_indices),
                    "edge_count": len(prior_edge_indices),
                },
                next_action="Disconnect the extra edge or target a distinct input socket before compiling.",
            )
        prior_edge_indices.append(edge_index)
        resolved.setdefault(target_node_id, {})[edge.to_input] = edge_source
    return resolved


def _can_ignore_compile_stripped_edge(edge: VibeEdge, nodes: dict[str, VibeNode]) -> bool:
    source_node = nodes.get(str(edge.from_node))
    target_node = nodes.get(str(edge.to_node))
    if source_node is None or target_node is None:
        return False
    if not _is_compile_stripped_node(source_node):
        return False
    if _is_ui_only_node(source_node):
        return False
    compiled_inputs = _compile_node_inputs(target_node)
    return str(edge.to_input) in compiled_inputs


def _resolve_compiled_source_ref(
    source_node_id: str,
    source_output: Any,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
    *,
    visited: set[str],
    target_node_id: str,
    target_input: str,
) -> list[Any]:
    source_node = nodes.get(str(source_node_id))
    if source_node is None:
        raise WorkflowCompileError(
            "compiled_edge_missing_endpoint",
            (
                f"Edge source node {source_node_id!r} for "
                f"{target_node_id!r}.{target_input!r} is missing."
            ),
            detail={
                "source_node_id": str(source_node_id),
                "target_node_id": target_node_id,
                "target_input": target_input,
            },
            next_action="Remove the dangling edge or restore the source node before compiling.",
        )

    if not _is_ui_only_node(source_node):
        output_slot = _output_slot_for_node(nodes, source_node_id, source_output)
        return [str(source_node_id), int(output_slot)]

    if source_node.class_type in {"Note", "MarkdownNote"}:
        raise WorkflowCompileError(
            "helper_edge_unresolved",
            (
                f"{source_node.class_type} node {source_node_id!r} is compile-stripped "
                f"but feeds runtime input {target_node_id!r}.{target_input!r}."
            ),
            detail={
                "helper_node_id": str(source_node_id),
                "class_type": source_node.class_type,
                "target_node_id": target_node_id,
                "target_input": target_input,
            },
            next_action="Remove the UI-only helper edge or reconnect the input to a runtime node.",
        )

    if source_node_id in visited:
        raise WorkflowCompileError(
            "helper_edge_cycle",
            (
                f"Helper edge cycle while resolving {source_node_id!r} for "
                f"{target_node_id!r}.{target_input!r}."
            ),
            detail={
                "helper_node_id": str(source_node_id),
                "target_node_id": target_node_id,
                "target_input": target_input,
                "visited": sorted(visited),
            },
            next_action="Break the SetNode/GetNode broadcast cycle before compiling.",
        )
    visited.add(source_node_id)

    name = workflow_helpers.broadcast_name(source_node)
    if not name or name not in broadcast_sources:
        raise WorkflowCompileError(
            "helper_edge_unresolved",
            (
                f"{source_node.class_type} node {source_node_id!r} feeding "
                f"{target_node_id!r}.{target_input!r} has no resolved broadcast source."
            ),
            detail={
                "helper_node_id": str(source_node_id),
                "class_type": source_node.class_type,
                "broadcast": name,
                "target_node_id": target_node_id,
                "target_input": target_input,
            },
            next_action="Add a matching SetNode source or reconnect the input to a runtime node.",
        )
    source = broadcast_sources[name]
    return _resolve_compiled_source_ref(
        str(source[0]),
        source[1],
        nodes,
        broadcast_sources,
        visited=visited,
        target_node_id=target_node_id,
        target_input=target_input,
    )


def _resolve_link_value(
    value: Any,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> Any:
    return helper_resolve.resolve_compile_link_value(value, nodes, broadcast_sources)


def _apply_positional_widget_aliases(inputs: dict[str, Any], node: VibeNode) -> None:
    widget_aliases.apply_positional_widget_aliases(
        inputs,
        node.class_type,
        input_aliases=node.metadata.get("input_aliases"),
    )


def _drop_unused_positional_aliases(inputs: dict[str, Any]) -> None:
    for key in list(inputs):
        if key.startswith("unused_"):
            inputs.pop(key, None)


__all__ = [
    "OPAQUE_COMPONENT_CLASS_RE",
    "RawWidgetPayload",
    "ValidationIssue",
    "ValidationReport",
    "VibeEdge",
    "VibeInput",
    "VibeNode",
    "VibeOutput",
    "VibeWorkflow",
    "WorkflowRequirements",
    "WorkflowSource",
]
