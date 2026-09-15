"""Static Python-function authoring for ordinary ``vibecomfy.exec`` nodes.

This module deliberately has no evaluator.  Decorating a function inspects its
source, and calling the resulting proxy only authors an existing exec node.
The original Python body is consequently still evaluated by the normal exec
runtime, subject to that runtime's existing policy.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import textwrap
from dataclasses import dataclass
from functools import update_wrapper
from types import MappingProxyType
from typing import Any, Callable, Mapping

from vibecomfy.blocks import Handles
from vibecomfy.handles import Handle
from vibecomfy.runtime.python_source import (
    SourceCapsule,
    capture_source,
    installed_entrypoint,
)
from vibecomfy.workflow import VibeWorkflow


class PythonAuthoringError(ValueError):
    """A declaration cannot be represented by the static authoring surface."""


@dataclass(frozen=True)
class Port:
    """A named typed port declaration."""

    name: str
    type: str
    default: Any = inspect.Parameter.empty


@dataclass(frozen=True)
class ResultAdapter:
    """A declarative mapping from a function result to named output ports."""

    outputs: tuple[Port, ...]
    mode: str = "mapping"


def result_adapter(*outputs: str | Port, mode: str = "mapping") -> ResultAdapter:
    """Declare how the body result is exposed; never calls a user callable."""
    return ResultAdapter(tuple(_coerce_port(item) for item in outputs), mode=mode)


def outputs(*ports: str | Port, mode: str = "mapping") -> ResultAdapter:
    """Short spelling for :func:`result_adapter`."""
    return result_adapter(*ports, mode=mode)


def port(name: str, type: str = "*") -> Port:
    if not isinstance(name, str) or not name.isidentifier():
        raise PythonAuthoringError(f"port name must be a Python identifier: {name!r}")
    if not isinstance(type, str) or not type.strip():
        raise PythonAuthoringError("port type must be a non-empty string")
    return Port(name, type)


def _coerce_port(value: str | Port) -> Port:
    if isinstance(value, Port):
        return value
    return port(value)


def _coerce_named_port(name: str, value: str | Port) -> Port:
    """Coerce a mapping entry while retaining its mapping key as the name."""
    if isinstance(value, Port):
        if value.name != name:
            raise PythonAuthoringError(
                f"port mapping key {name!r} does not match declared port {value.name!r}"
            )
        return value
    if not isinstance(value, str) or not value.strip():
        raise PythonAuthoringError(f"port {name!r} must declare a non-empty type")
    return port(name, value)


@dataclass(frozen=True)
class PythonNodeSpec:
    identity: str
    source: str
    filename: str
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    spans: Mapping[str, Mapping[str, int]]
    emission: Mapping[str, Any]
    callable_identities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "source": self.source,
            "filename": self.filename,
            "inputs": [_port_dict(item) for item in self.inputs],
            "outputs": [_port_dict(item) for item in self.outputs],
            "spans": {key: dict(value) for key, value in self.spans.items()},
            "emission": dict(self.emission),
            "callable_identities": list(self.callable_identities),
        }


def _port_dict(item: Port) -> dict[str, Any]:
    value = {"name": item.name, "type": item.type}
    if item.default is not inspect.Parameter.empty:
        value["default"] = item.default
    return value


def _annotation_name(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "*"
    if isinstance(annotation, str):
        # ``from __future__ import annotations`` stores a quoted forward
        # annotation.  Strip only that syntax; never resolve/evaluate it.
        if len(annotation) >= 2 and annotation[0] == annotation[-1] and annotation[0] in {"'", '"'}:
            return annotation[1:-1]
        return annotation
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def _identity(fn: Callable[..., Any]) -> str:
    return f"{fn.__module__}.{fn.__qualname__}"


class _CallableCollector(ast.NodeVisitor):
    def __init__(self, identity: str) -> None:
        self.identity = identity
        self.names: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        target = node.func
        if isinstance(target, ast.Name) and target.id == self.identity.rsplit(".", 1)[-1]:
            self.names.add(self.identity)
        elif isinstance(target, ast.Attribute):
            self.names.add(ast.unparse(target))
        self.generic_visit(node)


def _source_and_tree(fn: Callable[..., Any]) -> tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, str]:
    try:
        raw = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError) as exc:
        raise PythonAuthoringError(f"cannot inspect source for {_identity(fn)}") from exc
    tree = ast.parse(raw, filename=inspect.getsourcefile(fn) or "<python_node>")
    candidates = [item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(candidates) != 1 or candidates[0].name != fn.__name__:
        raise PythonAuthoringError("@python_node requires one directly inspectable function definition")
    return raw, candidates[0], inspect.getsourcefile(fn) or "<python_node>"


def analyze_python_node(
    fn: Callable[..., Any], *, result: ResultAdapter | None = None,
    inputs: Mapping[str, str | Port] | None = None,
    outputs_spec: Mapping[str, str | Port] | None = None,
) -> PythonNodeSpec:
    """Statically analyze a declaration without importing or running its body."""
    if not callable(fn):
        raise TypeError("@python_node target must be callable")
    source, tree, filename = _source_and_tree(fn)
    if isinstance(tree, ast.AsyncFunctionDef):
        raise PythonAuthoringError("async @python_node declarations are not supported")
    signature = inspect.signature(fn)
    declared_inputs: list[Port] = []
    input_overrides = inputs or {}
    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            raise PythonAuthoringError("variadic parameters are not supported")
        override = input_overrides.get(parameter.name)
        item = _coerce_named_port(parameter.name, override) if override is not None else Port(
            parameter.name, _annotation_name(parameter.annotation), parameter.default
        )
        if item.name != parameter.name:
            raise PythonAuthoringError(f"input port must retain parameter name {parameter.name!r}")
        declared_inputs.append(item)
    if result is not None and outputs_spec is not None:
        raise PythonAuthoringError("use result= or outputs_spec=, not both")
    if result is not None:
        declared_outputs = result.outputs
    elif outputs_spec is not None:
        declared_outputs = tuple(
            _coerce_named_port(str(name), value)
            for name, value in outputs_spec.items()
        )
    else:
        annotation = signature.return_annotation
        declared_outputs = (Port("result", _annotation_name(annotation)),)
    if not declared_outputs:
        raise PythonAuthoringError("at least one output port is required")
    names = [item.name for item in declared_outputs]
    if len(names) != len(set(names)):
        raise PythonAuthoringError("output port names must be unique")
    collector = _CallableCollector(_identity(fn))
    collector.visit(tree)
    end = getattr(tree, "end_lineno", tree.lineno)
    spans = MappingProxyType({
        "function": MappingProxyType({"start_line": tree.lineno, "start_col": tree.col_offset,
                                       "end_line": end, "end_col": getattr(tree, "end_col_offset", 0)}),
    })
    emission = MappingProxyType({
        "class_type": "vibecomfy.exec", "input_slots": [f"in_{i}" for i in range(len(declared_inputs))],
        "output_slots": [f"out_{i}" for i in range(len(declared_outputs))],
        "source_span": dict(spans["function"]), "result_mode": result.mode if result else "mapping",
        "source_digest": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    })
    return PythonNodeSpec(_identity(fn), source, filename, tuple(declared_inputs), tuple(declared_outputs),
                          spans, emission, tuple(sorted(collector.names)))


class PythonNode:
    """Callable proxy which lowers an analyzed function to one exec node."""

    def __init__(self, fn: Callable[..., Any], spec: PythonNodeSpec) -> None:
        self.function = fn
        self.spec = spec
        update_wrapper(self, fn)

    def __call__(self, workflow: VibeWorkflow, *args: Any, **kwargs: Any) -> Handles:
        if not isinstance(workflow, VibeWorkflow):
            raise TypeError("a VibeWorkflow is required as the first argument")
        node_id = kwargs.pop("_id", None)
        uid = kwargs.pop("_uid", None)
        bound = inspect.signature(self.function).bind(*args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        return _lower_exec_node(
            workflow,
            source=_exec_source(self.spec),
            io={
                "inputs": {item.name: item.type for item in self.spec.inputs},
                "outputs": {item.name: item.type for item in self.spec.outputs},
            },
            values=values,
            metadata={
                "python_authoring": self.spec.to_dict(),
                "vibecomfy_exec": {
                    "mode": "inline",
                    "source_digest": self.spec.emission.get("source_digest"),
                },
            },
            outputs=self.spec.outputs,
            node_id=node_id,
            uid=uid,
        )


class SourcePythonNode:
    """Callable proxy for a complete source capsule or installed entrypoint."""

    def __init__(
        self,
        payload: Mapping[str, Any],
        *,
        identity: str,
        inputs: tuple[Port, ...],
        outputs: tuple[Port, ...],
        mode: str,
    ) -> None:
        self.payload = dict(payload)
        self.identity = identity
        self.inputs = inputs
        self.outputs = outputs
        self.mode = mode
        self.spec = PythonNodeSpec(
            identity=identity,
            source=json.dumps(self.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            filename=f"<{mode}-python-source>",
            inputs=inputs,
            outputs=outputs,
            spans=MappingProxyType({}),
            emission=MappingProxyType({
                "class_type": "vibecomfy.exec",
                "source_mode": mode,
                "source_digest": hashlib.sha256(
                    json.dumps(self.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }),
            callable_identities=(identity,),
        )

    def __call__(self, workflow: VibeWorkflow, *args: Any, **kwargs: Any) -> Handles:
        if not isinstance(workflow, VibeWorkflow):
            raise TypeError("a VibeWorkflow is required as the first argument")
        node_id = kwargs.pop("_id", None)
        uid = kwargs.pop("_uid", None)
        signature = inspect.Signature([
            inspect.Parameter(
                item.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=item.default,
                annotation=item.type,
            )
            for item in self.inputs
        ])
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return _lower_exec_node(
            workflow,
            source=json.dumps(self.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            io={
                "inputs": {item.name: item.type for item in self.inputs},
                "outputs": {item.name: item.type for item in self.outputs},
            },
            values=bound.arguments,
            metadata={
                "python_source": self.payload,
                "vibecomfy_exec": {
                    "mode": self.mode,
                    **({"entrypoint": self.payload.get("entrypoint")} if self.payload.get("entrypoint") else {}),
                },
            },
            outputs=self.outputs,
            node_id=node_id,
            uid=uid,
        )


def _lower_exec_node(
    workflow: VibeWorkflow,
    *,
    source: str,
    io: Mapping[str, Any],
    values: Mapping[str, Any],
    metadata: Mapping[str, Any],
    outputs: tuple[Port, ...],
    node_id: str | None = None,
    uid: str | None = None,
) -> Handles:
    if len(values) > 16 or len(outputs) > 16:
        raise PythonAuthoringError("vibecomfy.exec supports at most 16 declared inputs and outputs")
        # ``vibecomfy.exec`` has a fixed, serialized physical socket pool.  The
        # names in ``io`` are semantic names used inside the source body and
        # on the returned Handles; links must target the corresponding
        # ``in_N`` socket so ComfyUI can actually deliver the value to the
        # node at queue time.
    input_ports = tuple(io.get("inputs", {}).keys())
    node_inputs = {
        f"in_{index}": values[name]
        for index, name in enumerate(input_ports)
    }
    builder = workflow.node(
        "vibecomfy.exec",
        _id=node_id,
        source=source,
        io=json.dumps(io),
        **node_inputs,
    )
    node = workflow.nodes[builder.id]
    if uid is not None:
        node.uid = str(uid)
    node.metadata.update(dict(metadata))
    node.metadata["output_names"] = [item.name for item in outputs]
    node.metadata["output_types"] = [item.type for item in outputs]
    return Handles({
        item.name: Handle(
            node_id=builder.id,
            output_slot=index,
            output_type=item.type,
            name=item.name,
        )
        for index, item in enumerate(outputs)
    })


def _exec_source(spec: PythonNodeSpec) -> str:
    tree = ast.parse(spec.source, filename=spec.filename)
    function = next(item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
    class ReturnAdapter(ast.NodeTransformer):
        def visit_Return(self, node: ast.Return) -> ast.Return:
            self.generic_visit(node)
            if node.value is None:
                return node
            if len(spec.outputs) == 1:
                value = ast.Dict(keys=[ast.Constant(spec.outputs[0].name)], values=[node.value])
            elif spec.emission.get("result_mode") == "tuple":
                value = ast.Dict(
                    keys=[ast.Constant(item.name) for item in spec.outputs],
                    values=[ast.Subscript(value=node.value, slice=ast.Constant(i)) for i in range(len(spec.outputs))],
                )
            else:
                value = node.value
            return ast.copy_location(ast.Return(value=value), node)

    body = ReturnAdapter().visit(ast.Module(body=function.body or [], type_ignores=[])).body
    if not any(isinstance(item, ast.Return) for item in ast.walk(ast.Module(body=body, type_ignores=[]))):
        body.append(ast.Return(value=ast.Dict(keys=[], values=[])))
    return "\n".join(ast.unparse(item) for item in body)


def python_node(_fn: Callable[..., Any] | None = None, *, result: ResultAdapter | None = None,
                inputs: Mapping[str, str | Port] | None = None,
                outputs: Mapping[str, str | Port] | ResultAdapter | None = None,
                outputs_spec: Mapping[str, str | Port] | None = None) -> Any:
    """Decorate a function into a statically analyzed :class:`PythonNode`."""
    if outputs is not None and outputs_spec is not None:
        raise PythonAuthoringError("use outputs= or outputs_spec=, not both")
    declared_outputs = outputs_spec
    declared_result = result
    if isinstance(outputs, ResultAdapter):
        if result is not None:
            raise PythonAuthoringError("use result= or outputs=ResultAdapter, not both")
        declared_result = outputs
    elif outputs is not None:
        declared_outputs = outputs

    def decorate(fn: Callable[..., Any]) -> PythonNode:
        return PythonNode(
            fn,
            analyze_python_node(
                fn,
                result=declared_result,
                inputs=inputs,
                outputs_spec=declared_outputs,
            ),
        )
    return decorate(_fn) if _fn is not None else decorate


def _mapped_ports(value: Mapping[str, str | Port] | ResultAdapter | None, *, label: str) -> tuple[Port, ...]:
    if isinstance(value, ResultAdapter):
        return value.outputs
    if not isinstance(value, Mapping) or not value:
        raise PythonAuthoringError(f"{label} must be a non-empty name-to-type mapping")
    return tuple(_coerce_named_port(str(name), item) for name, item in value.items())


def from_source(
    source: str | SourceCapsule,
    *,
    entrypoint: str,
    inputs: Mapping[str, str | Port],
    outputs: Mapping[str, str | Port] | ResultAdapter,
    result: ResultAdapter | None = None,
    dependencies: tuple[Mapping[str, Any], ...] = (),
    python: str | None = None,
    provenance: str | None = None,
) -> SourcePythonNode:
    """Declare a complete local module/project without importing it."""
    capsule = (
        source
        if isinstance(source, SourceCapsule)
        else capture_source(
            source,
            entrypoint=entrypoint,
            dependencies=dependencies,
            python=python,
            provenance=provenance,
        )
    )
    input_ports = _mapped_ports(inputs, label="inputs")
    output_adapter = result or (outputs if isinstance(outputs, ResultAdapter) else None)
    output_ports = _mapped_ports(outputs, label="outputs") if output_adapter is None else output_adapter.outputs
    payload = capsule.to_payload()
    payload["result"] = {
        "mode": output_adapter.mode if output_adapter is not None else "mapping",
        "outputs": {item.name: item.type for item in output_ports},
    }
    identity = f"source:{capsule.source_id}:{capsule.snapshot_sha256}:{capsule.entrypoint}"
    return SourcePythonNode(
        payload,
        identity=identity,
        inputs=input_ports,
        outputs=output_ports,
        mode="snapshot",
    )


def from_installed(
    *,
    entrypoint: str,
    inputs: Mapping[str, str | Port],
    outputs: Mapping[str, str | Port] | ResultAdapter,
    result: ResultAdapter | None = None,
    revision: str | None = None,
    dependencies: tuple[Mapping[str, Any], ...] = (),
) -> SourcePythonNode:
    """Declare a worker-installed package without importing it at build time."""
    reference = installed_entrypoint(entrypoint, revision=revision, dependencies=dependencies)
    input_ports = _mapped_ports(inputs, label="inputs")
    output_adapter = result or (outputs if isinstance(outputs, ResultAdapter) else None)
    output_ports = _mapped_ports(outputs, label="outputs") if output_adapter is None else output_adapter.outputs
    payload = reference.to_payload()
    payload["result"] = {
        "mode": output_adapter.mode if output_adapter is not None else "mapping",
        "outputs": {item.name: item.type for item in output_ports},
    }
    identity = f"installed:{entrypoint}:{revision or 'unspecified'}"
    return SourcePythonNode(
        payload,
        identity=identity,
        inputs=input_ports,
        outputs=output_ports,
        mode="installed",
    )


# The public spelling intentionally mirrors the requested API while retaining
# a simple function decorator for ordinary declarations.
setattr(python_node, "from_source", from_source)
setattr(python_node, "from_installed", from_installed)


__all__ = [
    "InstalledEntrypoint", "Port", "PythonNode", "PythonNodeSpec", "PythonAuthoringError",
    "ResultAdapter", "SourceCapsule", "SourcePythonNode", "analyze_python_node", "from_installed",
    "from_source", "outputs", "port", "python_node", "result_adapter",
]
