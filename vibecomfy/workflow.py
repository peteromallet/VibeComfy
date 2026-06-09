from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
import warnings
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from vibecomfy import _helper_resolve as helper_resolve
from vibecomfy import _widget_aliases as widget_aliases
from vibecomfy import _workflow_helpers as workflow_helpers
from vibecomfy.errors import VibeComfyError
from vibecomfy.handles import Handle

if TYPE_CHECKING:
    from vibecomfy.schema.provider import SchemaProvider


# ComfyUI-specific validation policy lives in the neutral contracts layer.
# Re-exported here so existing `from vibecomfy.workflow import OPAQUE_COMPONENT_CLASS_RE`
# imports keep working.
from vibecomfy.contracts.validation import (  # noqa: E402
    OPAQUE_COMPONENT_CLASS_RE,
    comfyui_node_issue_specs,
)


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
    _id_map: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _manual_input_names: set[str] = field(default_factory=set, init=False, repr=False)
    _uid_counter: int = field(default=0, init=False, repr=False)

    def __enter__(self) -> "VibeWorkflow":
        from vibecomfy.workflow_context import active_workflow, bind_workflow

        # If ``new_workflow()`` already eagerly bound this workflow (the post-
        # revert default for emitted templates), reuse that binding rather than
        # raising — the ``with`` form is purely scoping sugar in that case.
        if (
            getattr(self, "_workflow_context_token", None) is not None
            and active_workflow() is self
        ):
            return self
        if getattr(self, "_workflow_context_token", None) is not None:
            raise RuntimeError(
                "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
                "block is still active."
            )
        self._workflow_context_token = bind_workflow(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        from vibecomfy.workflow_context import reset_workflow

        token = getattr(self, "_workflow_context_token", None)
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
        cloned = VibeWorkflow(
            id=self.id,
            source=copy.deepcopy(self.source),
            nodes={
                node_id: VibeNode(
                    id=node.id,
                    class_type=node.class_type,
                    pack=node.pack,
                    inputs=copy.deepcopy(node.inputs),
                    widgets=copy.deepcopy(node.widgets),
                    metadata=copy.deepcopy(node.metadata),
                    uid=node.uid,
                    raw_widgets=copy.deepcopy(node.raw_widgets),
                )
                for node_id, node in self.nodes.items()
            },
            edges=[
                VibeEdge(
                    from_node=edge.from_node,
                    from_output=edge.from_output,
                    to_node=edge.to_node,
                    to_input=edge.to_input,
                )
                for edge in self.edges
            ],
            inputs={
                name: VibeInput(
                    name=vibe_input.name,
                    node_id=vibe_input.node_id,
                    field=vibe_input.field,
                    value=copy.deepcopy(vibe_input.value),
                    type=vibe_input.type,
                    default=copy.deepcopy(vibe_input.default),
                    required=vibe_input.required,
                    range=copy.deepcopy(vibe_input.range),
                    aliases=tuple(vibe_input.aliases),
                    media_semantics=vibe_input.media_semantics,
                )
                for name, vibe_input in self.inputs.items()
            },
            outputs=[
                VibeOutput(
                    node_id=output.node_id,
                    output_type=output.output_type,
                    name=output.name,
                    artifact_kind=output.artifact_kind,
                    mime_type=output.mime_type,
                    filename_prefix=output.filename_prefix,
                    expected_cardinality=copy.deepcopy(output.expected_cardinality),
                )
                for output in self.outputs
            ],
            requirements=WorkflowRequirements(
                models=list(self.requirements.models),
                custom_nodes=list(self.requirements.custom_nodes),
                missing_models=list(self.requirements.missing_models),
                missing_nodes=list(self.requirements.missing_nodes),
                unsupported=list(self.requirements.unsupported),
            ),
            metadata=copy.deepcopy(self.metadata),
            strict_types=self.strict_types,
        )
        cloned._id_map = dict(self._id_map)
        cloned._manual_input_names = set(self._manual_input_names)
        cloned._uid_counter = self._uid_counter
        return cloned

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
            # `vibecomfy.exec` semantic `io.inputs` names stay in node/widget metadata
            # and schema/socket data; finalize_metadata only exposes the established
            # common public-input surface unless a caller registers manual inputs.
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
    ) -> "VibeWorkflow":
        if media_semantics is not None and media is not None and media_semantics != media:
            raise ValueError(
                f"register_input({name!r}): media_semantics and legacy media "
                "must match when both are provided"
            )
        resolved_media_semantics = media_semantics if media_semantics is not None else media
        alias_tuple = _normalize_input_aliases(aliases)
        self._validate_input_aliases(name, alias_tuple)
        self._validate_input_target(name, node_id, field)
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

    def _validate_input_target(self, name: str, node_id: str, field: str) -> None:
        node_key = str(node_id)
        if node_key not in self.nodes:
            raise ValueError(
                f"register_input({name!r}): target node {node_key!r} does not exist "
                f"in workflow {self.id!r}"
            )
        node = self.nodes[node_key]
        if field not in node.inputs and field not in node.widgets:
            raise ValueError(
                f"register_input({name!r}): field {field!r} not found in "
                f"node {node_key!r} ({node.class_type}) inputs or widgets"
            )

    def _input_target_exists(self, vibe_input: VibeInput) -> bool:
        node = self.nodes.get(vibe_input.node_id)
        return node is not None and (vibe_input.field in node.inputs or vibe_input.field in node.widgets)

    def _mint_uid(self, seed: str | None = None) -> str:
        """Mint a never-reused uid using the monotonic counter.

        Counter always increments regardless of whether a seed is provided.
        When seed is given it becomes the local uid component (extrinsic identity).
        When omitted, the counter value provides authored creation-order identity.
        """
        from vibecomfy.porting.uid import make_uid
        self._uid_counter += 1
        local = seed if seed is not None else f"n{self._uid_counter}"
        return make_uid("", local)

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
        from vibecomfy.security.provenance import PROVENANCE_KEY, tag as _tag_provenance

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
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_source", f"Missing source node {edge.from_node}."))
            if edge.to_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_target", f"Missing target node {edge.to_node}."))
        api: dict[str, Any] | None = None
        try:
            api = self.compile(backend="api")
        except Exception as exc:
            detail: dict[str, Any] = {}
            if isinstance(exc, WorkflowCompileError):
                detail = {"compile_code": exc.code, **exc.detail}
            issues.append(ValidationIssue("api_compile_failed", str(exc), severity="error", detail=detail))
        if schema_provider is not None:
            from vibecomfy.schema.validate import validate_against_schema, validate_api_link_shapes

            issues.extend(validate_against_schema(self, schema_provider))
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

    def compile(self, backend: str = "api") -> dict[str, Any]:
        if backend == "graphbuilder":
            return self._compile_graphbuilder()
        if backend != "api":
            raise ValueError(f"Unknown compile backend: {backend}")
        dropped_ids, bypassed_ids = _compute_dropped_bypassed_ids(self.nodes)
        resolved_edges = _resolve_bypass_edges(self.edges, dropped_ids, bypassed_ids)
        broadcast_sources = workflow_helpers.collect_broadcast_sources(self.nodes, resolved_edges)
        api: dict[str, Any] = {}
        for node_id, node in self.nodes.items():
            if _is_compile_stripped_node(node):
                continue
            if str(node_id) in dropped_ids:
                continue
            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), self.nodes, broadcast_sources)
            inputs.update(_compile_intent_runtime_inputs(node))
            api[str(node_id)] = {"class_type": node.class_type, "inputs": inputs}
        edge_inputs = _compile_resolved_edge_inputs(
            self.nodes, resolved_edges, broadcast_sources, dropped_ids=dropped_ids
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

    def _compile_graphbuilder(self) -> dict[str, Any]:
        try:
            from comfy_execution.graph_utils import GraphBuilder
        except ImportError as exc:
            raise RuntimeError("GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.") from exc

        broadcast_sources = workflow_helpers.collect_broadcast_sources(self.nodes, self.edges)
        edge_inputs = _compile_resolved_edge_inputs(self.nodes, self.edges, broadcast_sources)

        builder = GraphBuilder(prefix="")
        for node_id, node in self.nodes.items():
            if _is_compile_stripped_node(node):
                continue
            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), self.nodes, broadcast_sources)
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


@dataclass(frozen=True)
class _NodeBuilder:
    workflow: VibeWorkflow
    node: VibeNode

    @property
    def id(self) -> str:
        return self.node.id

    def out(self, slot: int | str) -> Handle:
        try:
            output_slot = int(str(slot))
        except ValueError as exc:
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
            ) from exc
        return Handle(node_id=self.node.id, output_slot=output_slot, output_type=_node_output_type(self.node, output_slot))

    def __iter__(self) -> Iterator[Handle]:
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
        return str(class_type) in {
            "vibecomfy.code",
            "vibecomfy.loop",
            "vibecomfy.branch",
            "vibecomfy.workflowref",
        }


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


_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)


def _get_node_mode(node: VibeNode) -> int:
    """Read the litegraph mode (0/2/4) from _ui metadata; defaults to 0."""
    ui = node.metadata.get("_ui")
    if not isinstance(ui, dict):
        return 0
    mode = ui.get("mode", 0)
    return mode if isinstance(mode, int) else 0


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
        mode = _get_node_mode(node)
        if mode in (_MODE_MUTED, _MODE_BYPASS):
            dropped.add(str(node_id))
        if mode == _MODE_BYPASS:
            bypassed.add(str(node_id))
    return frozenset(dropped), frozenset(bypassed)


def _resolve_bypass_edges(
    edges: list[VibeEdge],
    dropped_ids: frozenset[str],
    bypassed_ids: frozenset[str],
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

    def _follow(node_id: str, from_out: str, seen: frozenset[str]) -> tuple[str, str] | None:
        if node_id in seen:
            return None
        if node_id not in dropped_ids:
            return (node_id, from_out)
        if node_id not in bypassed_ids:
            return None  # muted: dead end
        try:
            slot = int(from_out)
        except (TypeError, ValueError):
            slot = 0
        feeds = incoming.get(node_id, [])
        if not feeds:
            return None
        feed = feeds[slot] if slot < len(feeds) else feeds[0]
        return _follow(str(feed.from_node), feed.from_output, seen | {node_id})

    result: list[VibeEdge] = []
    for edge in edges:
        from_id = str(edge.from_node)
        to_id = str(edge.to_node)
        if to_id in dropped_ids:
            continue
        if from_id in dropped_ids:
            if from_id not in bypassed_ids:
                continue
            resolved = _follow(from_id, edge.from_output, frozenset())
            if resolved is None:
                continue
            nf, no = resolved
            result.append(VibeEdge(nf, no, edge.to_node, edge.to_input))
        else:
            result.append(edge)
    return result


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
    for edge in edges:
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
        try:
            output_slot = int(source_output)
        except (TypeError, ValueError) as exc:
            raise WorkflowCompileError(
                "compiled_edge_missing_endpoint",
                (
                    f"Edge source {source_node_id!r}.{source_output!r} for "
                    f"{target_node_id!r}.{target_input!r} has a non-numeric output slot."
                ),
                detail={
                    "source_node_id": str(source_node_id),
                    "source_output": str(source_output),
                    "target_node_id": target_node_id,
                    "target_input": target_input,
                },
                next_action="Use an explicit numeric output slot before compiling.",
            ) from exc
        return [str(source_node_id), output_slot]

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


def _is_api_link(value: Any) -> bool:
    return workflow_helpers.is_api_link(value)


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
