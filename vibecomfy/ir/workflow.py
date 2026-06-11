from __future__ import annotations

import copy
import warnings
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal

from vibecomfy import _helper_resolve as helper_resolve
from vibecomfy import _widget_aliases as widget_aliases
from vibecomfy import _workflow_helpers as workflow_helpers
from vibecomfy.handles import Handle
from vibecomfy.ir.compile import (
    _compile_intent_runtime_inputs,
    _compile_node_inputs,
    _compile_resolved_edge_inputs,
    _compute_dropped_bypassed_ids,
    _format_available_names,
    _is_compile_stripped_node,
    _node_input_type,
    _node_output_names,
    _node_output_type,
    _normalize_input_aliases,
    _resolve_bypass_edges,
    _rewrite_broadcast_links,
)
from vibecomfy.ir.types import (
    RawWidgetPayload,
    ValidationIssue,
    ValidationReport,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    WorkflowCompileError,
    WorkflowRequirements,
    WorkflowSource,
)

if TYPE_CHECKING:
    from vibecomfy.schema.provider import SchemaProvider

from vibecomfy.contracts.validation import (  # noqa: E402
    OPAQUE_COMPONENT_CLASS_RE,
    comfyui_node_issue_specs,
)


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
        """Promote ``untrusted_source`` provenance on ``node_id`` → ``user_confirmed``."""
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
        """Finalize ready-template public inputs and output binding."""
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
    ) -> "VibeWorkflow":
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
            media_semantics=media_semantics,
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
        from vibecomfy.porting.identity.uid import make_uid
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
        from vibecomfy.security.capabilities import capabilities_for, is_side_effecting
        from vibecomfy.security.gate import (
            current_gate_context,
            requesting_provenance,
            require_confirmation,
        )
        from vibecomfy.security.provenance import PROVENANCE_KEY, tag as _tag_provenance

        effective = _provenance if _provenance is not None else requesting_provenance.get()

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
        to_node, to_input = self._parse_target_ref(to_ref, operation="disconnect")
        for index, edge in enumerate(self.edges):
            if edge.to_node == to_node and edge.to_input == to_input:
                del self.edges[index]
                return True
        return False

    def remove_node(self, node_id: str) -> "VibeWorkflow":
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

    def compile(self, backend: Literal["api", "graphbuilder"] = "api") -> dict[str, Any]:
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
        return dict(self._id_map)

    def _set_id_map(self, mapping: dict[str, Any]) -> "VibeWorkflow":
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
        nid = str(node_id)
        if nid not in self.nodes:
            raise KeyError(nid)

        node = self.nodes[nid]

        variable_name: str | None = None
        for name, mapped_id in self._id_map.items():
            if mapped_id == nid:
                variable_name = name
                break

        provenance = node.metadata.get("provenance")
        source_path: str | None = None
        if isinstance(provenance, dict):
            sp = provenance.get("source_path")
            if isinstance(sp, str) and sp:
                source_path = sp
        if source_path is None:
            source_path = self.source.path

        source_line: int | None = None
        if isinstance(provenance, dict):
            sl = provenance.get("source_line")
            if isinstance(sl, int) and sl >= 1:
                source_line = sl

        input_names: list[str] = list(node.inputs.keys())
        widgets: dict[str, Any] = dict(node.widgets)

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

        output_type_names: list[str] = [
            output.output_type
            for output in self.outputs
            if str(output.node_id) == nid
        ]

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
