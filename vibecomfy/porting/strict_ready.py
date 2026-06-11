from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING
from typing import Any, Iterable, Mapping

from vibecomfy.porting.report import PortIssue
from vibecomfy.utils import find_repo_root

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


STRICT_READY_MISSING_PUBLIC_INPUT = "strict_ready_missing_public_input"
STRICT_READY_BROKEN_PUBLIC_INPUT = "strict_ready_broken_public_input"
STRICT_READY_MISSING_OUTPUT_CONTRACT = "strict_ready_missing_output_contract"
STRICT_READY_UNNAMED_OUTPUT_CONTRACT = "strict_ready_unnamed_output_contract"
STRICT_READY_UNRESOLVED_WIDGETS = "strict_ready_unresolved_widgets"
STRICT_READY_LOAD_FAILED = "strict_ready_load_failed"
STRICT_READY_BUILD_FAILED = "strict_ready_build_failed"
STRICT_READY_COMPILE_FAILED = "strict_ready_compile_failed"
STRICT_READY_HELPER_IN_EMITTED_OUTPUT = "strict_ready_helper_in_emitted_output"
OPAQUE_COMPONENT_NODE_CLASS = "opaque_component_node_class"
HIDDEN_MODEL_FILENAME = "hidden_model_filename"

OPAQUE_COMPONENT_CLASS_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

STRICT_READY_VIOLATION_CODES: frozenset[str] = frozenset(
    {
        STRICT_READY_MISSING_PUBLIC_INPUT,
        STRICT_READY_BROKEN_PUBLIC_INPUT,
        STRICT_READY_MISSING_OUTPUT_CONTRACT,
        STRICT_READY_UNNAMED_OUTPUT_CONTRACT,
        STRICT_READY_UNRESOLVED_WIDGETS,
        STRICT_READY_LOAD_FAILED,
        STRICT_READY_BUILD_FAILED,
        STRICT_READY_COMPILE_FAILED,
        STRICT_READY_HELPER_IN_EMITTED_OUTPUT,
        OPAQUE_COMPONENT_NODE_CLASS,
        HIDDEN_MODEL_FILENAME,
    }
)

DEFAULT_EXCEPTION_PATH = find_repo_root() / "docs" / "strict_ready_exceptions.json"
EXCEPTION_MATCH_KEYS: tuple[str, str, str] = ("ready_id", "violation_code", "target")
ALLOWED_FINAL_CATEGORIES: frozenset[str] = frozenset(
    {"reference", "supplemental", "blocked", "scratchpad-only"}
)


@dataclass(frozen=True, slots=True)
class StrictReadyContext:
    ready_id: str | None = None
    source_path: str | None = None
    mode: str = "strict_ready"
    exceptions_path: Path | None = None
    exceptions: tuple["StrictReadyException", ...] | None = None
    is_post_resolution: bool = False


@dataclass(frozen=True, slots=True)
class StrictReadyException:
    id: str
    ready_id: str
    violation_code: str
    target: str
    owner: str
    ticket: str
    reason: str
    allowed_until: str
    removal_condition: str
    final_category: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "StrictReadyException":
        missing = [
            field
            for field in (
                "id",
                "ready_id",
                "violation_code",
                "target",
                "owner",
                "ticket",
                "reason",
                "allowed_until",
                "removal_condition",
                "final_category",
            )
            if not raw.get(field)
        ]
        if missing:
            raise ValueError(f"strict-ready exception is missing required field(s): {', '.join(missing)}")
        final_category = str(raw["final_category"])
        if final_category not in ALLOWED_FINAL_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_FINAL_CATEGORIES))
            raise ValueError(
                f"strict-ready exception {raw.get('id')!r} has unsupported final_category "
                f"{final_category!r}; expected one of {allowed}"
            )
        return cls(
            id=str(raw["id"]),
            ready_id=str(raw["ready_id"]),
            violation_code=str(raw["violation_code"]),
            target=str(raw["target"]),
            owner=str(raw["owner"]),
            ticket=str(raw["ticket"]),
            reason=str(raw["reason"]),
            allowed_until=str(raw["allowed_until"]),
            removal_condition=str(raw["removal_condition"]),
            final_category=final_category,
        )

    @property
    def match_key(self) -> tuple[str, str, str]:
        return (self.ready_id, self.violation_code, self.target)


def load_strict_ready_exceptions(path: Path | str | None = None) -> tuple[StrictReadyException, ...]:
    exception_path = Path(path) if path is not None else DEFAULT_EXCEPTION_PATH
    if not exception_path.exists():
        return ()
    payload = json.loads(exception_path.read_text())
    if payload.get("match_keys") and list(payload["match_keys"]) != list(EXCEPTION_MATCH_KEYS):
        raise ValueError(
            f"strict-ready exception match_keys must be {list(EXCEPTION_MATCH_KEYS)!r}; "
            f"got {payload['match_keys']!r}"
        )
    entries = payload.get("exceptions", [])
    if not isinstance(entries, list):
        raise ValueError("strict-ready exceptions payload must contain an exceptions list")
    exceptions = tuple(StrictReadyException.from_mapping(entry) for entry in entries)
    seen: set[tuple[str, str, str]] = set()
    for exception in exceptions:
        if exception.match_key in seen:
            raise ValueError(
                "duplicate strict-ready exception match key: "
                f"{exception.ready_id}:{exception.violation_code}:{exception.target}"
            )
        seen.add(exception.match_key)
    return tuple(sorted(exceptions, key=lambda item: item.match_key))


def validate_strict_ready_workflow(
    workflow: VibeWorkflow,
    context: StrictReadyContext | None = None,
    *,
    api_prompt: Mapping[str, Any] | None = None,
    widget_analysis: Mapping[str, Any] | None = None,
) -> list[PortIssue]:
    """Return strict-ready diagnostics for a built workflow.

    The validator only uses already-built workflow data and optional analysis
    artifacts. It does not discover templates, load plugins, or consult dynamic
    ready roots.
    """
    ctx = context or StrictReadyContext(ready_id=workflow.id, source_path=workflow.source.path)
    api = dict(api_prompt) if api_prompt is not None else _compile_api_prompt(workflow)
    diagnostics: list[PortIssue] = []
    diagnostics.extend(_public_input_diagnostics(workflow))
    diagnostics.extend(_public_output_diagnostics(workflow))
    diagnostics.extend(_opaque_component_diagnostics(workflow))
    diagnostics.extend(_schema_backed_widget_diagnostics(widget_analysis or {}))
    if api is not None:
        diagnostics.extend(_hidden_model_filename_diagnostics(api, workflow))
    if ctx.is_post_resolution:
        diagnostics.extend(_helper_in_emitted_output_diagnostics(workflow))
    return apply_strict_ready_exceptions(diagnostics, ctx)


def apply_strict_ready_exceptions(
    diagnostics: Iterable[PortIssue],
    context: StrictReadyContext | None = None,
) -> list[PortIssue]:
    ctx = context or StrictReadyContext()
    exceptions = ctx.exceptions
    if exceptions is None:
        exceptions = load_strict_ready_exceptions(ctx.exceptions_path)
    by_key = {exception.match_key: exception for exception in exceptions}
    resolved: list[PortIssue] = []
    for issue in diagnostics:
        target = _issue_target(issue)
        ready_id = ctx.ready_id or ""
        match = by_key.get((ready_id, issue.code, target))
        issue.detail = dict(issue.detail or {})
        issue.detail.setdefault("category", "strict_ready")
        issue.detail.setdefault("target", target)
        if ctx.ready_id:
            issue.detail.setdefault("ready_id", ctx.ready_id)
        if match is not None:
            issue.severity = "info"
            issue.detail.update(
                {
                    "exception_id": match.id,
                    "exception_owner": match.owner,
                    "exception_ticket": match.ticket,
                    "exception_allowed_until": match.allowed_until,
                    "exception_final_category": match.final_category,
                }
            )
        resolved.append(issue)
    return sorted(resolved, key=_issue_sort_key)


def _public_input_diagnostics(workflow: VibeWorkflow) -> list[PortIssue]:
    if not workflow.inputs:
        return [
            PortIssue(
                code=STRICT_READY_MISSING_PUBLIC_INPUT,
                message="Strict ready-template policy requires at least one public input.",
                severity="error",
                detail={"target": "public_inputs"},
                recommendation="Bind the required callable inputs with `bind_input(...)` or `wf.register_input(...)`.",
            )
        ]
    issues: list[PortIssue] = []
    for name, public_input in sorted(workflow.inputs.items()):
        node_id = str(public_input.node_id)
        node = workflow.nodes.get(node_id)
        target = f"input:{name}"
        if node is None:
            issues.append(
                PortIssue(
                    code=STRICT_READY_BROKEN_PUBLIC_INPUT,
                    message=f"Public input {name!r} targets missing node {node_id!r}.",
                    severity="error",
                    node_id=node_id,
                    detail={
                        "target": target,
                        "input_name": name,
                        "node_id": node_id,
                        "field": public_input.field,
                    },
                    recommendation="Update the public input binding to target an existing runtime node.",
                )
            )
            continue
        if public_input.field not in node.inputs and public_input.field not in node.widgets:
            issues.append(
                PortIssue(
                    code=STRICT_READY_BROKEN_PUBLIC_INPUT,
                    message=(
                        f"Public input {name!r} targets missing field {public_input.field!r} "
                        f"on node {node_id} ({node.class_type})."
                    ),
                    severity="error",
                    node_id=node_id,
                    class_type=node.class_type,
                    detail={
                        "target": target,
                        "input_name": name,
                        "node_id": node_id,
                        "field": public_input.field,
                    },
                    recommendation="Bind the input to a named node input/widget that exists after build.",
                )
            )
    return issues


def _public_output_diagnostics(workflow: VibeWorkflow) -> list[PortIssue]:
    if not workflow.outputs:
        return [
            PortIssue(
                code=STRICT_READY_MISSING_OUTPUT_CONTRACT,
                message="Strict ready-template policy requires at least one public output contract.",
                severity="error",
                detail={"target": "public_outputs"},
                recommendation="Register the expected artifact with `bind_output(...)`.",
            )
        ]
    issues: list[PortIssue] = []
    for index, output in enumerate(workflow.outputs):
        if output.name:
            continue
        node = workflow.nodes.get(str(output.node_id))
        issues.append(
            PortIssue(
                code=STRICT_READY_UNNAMED_OUTPUT_CONTRACT,
                message=f"Public output {index} on node {output.node_id!r} is missing a semantic name.",
                severity="error",
                node_id=str(output.node_id),
                class_type=node.class_type if node else None,
                detail={"target": f"output:{index}", "node_id": str(output.node_id), "output_type": output.output_type},
                recommendation="Pass a stable semantic `name=` to `bind_output(...)`.",
            )
        )
    return issues


def _opaque_component_diagnostics(workflow: VibeWorkflow) -> list[PortIssue]:
    issues: list[PortIssue] = []
    for node_id, node in sorted(workflow.nodes.items(), key=lambda item: _sort_key(item[0])):
        if not OPAQUE_COMPONENT_CLASS_RE.match(node.class_type):
            continue
        issues.append(
            PortIssue(
                code=OPAQUE_COMPONENT_NODE_CLASS,
                message=f"Node {node_id} has opaque UUID component class {node.class_type!r}.",
                severity="error",
                node_id=str(node_id),
                class_type=node.class_type,
                detail={"target": f"node:{node_id}"},
                recommendation=(
                    "Replace the opaque component runtime node with first-class workflow-builder code "
                    "before promoting a ready template."
                ),
            )
        )
    return issues


def _schema_backed_widget_diagnostics(widget_analysis: Mapping[str, Any]) -> list[PortIssue]:
    unresolved = [dict(item) for item in widget_analysis.get("unresolved_widget_aliases") or []]
    if not unresolved:
        return []
    schema_backed_classes = {
        str(group.get("class_type"))
        for group in widget_analysis.get("suggestions", []) or []
        if group.get("schema_source") != "unavailable" or group.get("suggested_schema_entry") is not None
    }
    blocked = [
        alias for alias in unresolved
        if str(alias.get("class_type")) in schema_backed_classes
    ]
    issues: list[PortIssue] = []
    for alias in sorted(blocked, key=lambda item: (_sort_key(item.get("node_id")), str(item.get("input", "")))):
        node_id = str(alias.get("node_id", ""))
        class_type = str(alias.get("class_type", ""))
        input_name = str(alias.get("input", ""))
        target = f"node:{node_id}.{input_name}"
        issues.append(
            PortIssue(
                code=STRICT_READY_UNRESOLVED_WIDGETS,
                message=(
                    f"Strict ready-template policy found unresolved schema-backed positional widget "
                    f"{input_name!r} on node {node_id} ({class_type})."
                ),
                severity="error",
                node_id=node_id or None,
                class_type=class_type or None,
                detail={
                    "target": target,
                    "input": input_name,
                    "unresolved_total": len(unresolved),
                    "schema_backed_total": len(blocked),
                },
                recommendation=(
                    "Run `vibecomfy port widgets <workflow> --json`, add schema aliases, "
                    "or rewrite the template with named inputs."
                ),
            )
        )
    return issues


def _hidden_model_filename_diagnostics(
    api_prompt: Mapping[str, Any],
    workflow: VibeWorkflow,
) -> list[PortIssue]:
    from vibecomfy.porting.convert import _looks_like_model_value

    class_widget_aliases = _class_widget_aliases(workflow)
    issues: list[PortIssue] = []
    for node_id, node_payload in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node_payload, Mapping):
            continue
        class_type = str(node_payload.get("class_type", ""))
        inputs = node_payload.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        named_model_values: set[str] = set()
        widget_model_values: dict[int, str] = {}
        for key, value in inputs.items():
            input_name = str(key)
            if not _looks_like_model_value(value):
                continue
            if input_name.startswith("widget_"):
                try:
                    widget_model_values[int(input_name.split("_", 1)[1])] = str(value)
                except ValueError:
                    named_model_values.add(str(value))
            else:
                named_model_values.add(str(value))
        aliases = class_widget_aliases.get(class_type)
        for index, value in sorted(widget_model_values.items()):
            if value in named_model_values:
                continue
            if aliases is not None and 0 <= index < len(aliases) and aliases[index] is not None:
                continue
            input_name = f"widget_{index}"
            target = f"node:{node_id}.{input_name}"
            issues.append(
                PortIssue(
                    code=HIDDEN_MODEL_FILENAME,
                    message=f"Model filename {value!r} is hidden under {input_name} on node {node_id} ({class_type}).",
                    severity="error",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={"target": target, "input": input_name, "model_filename": value},
                    recommendation="Expose model filenames through named fields so model reconciliation can see them.",
                )
            )
    return issues


def _class_widget_aliases(workflow: VibeWorkflow) -> dict[str, list[str | None]]:
    aliases_by_class: dict[str, list[str | None]] = {}
    for node in workflow.nodes.values():
        if node.class_type in aliases_by_class:
            continue
        aliases = node.metadata.get("input_aliases")
        if isinstance(aliases, (list, tuple)) and aliases:
            aliases_by_class[node.class_type] = list(aliases)
    return aliases_by_class


def _helper_in_emitted_output_diagnostics(workflow: VibeWorkflow) -> list[PortIssue]:
    """Flag surviving resolvable-helper class types in post-resolution emitted workflows.

    Gated by ``StrictReadyContext.is_post_resolution`` so raw-source port checks
    (which pass through workbench.py) do not hard-error on helpers that conversion
    is expected to strip.
    """
    from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES

    issues: list[PortIssue] = []
    for node_id, node in sorted(workflow.nodes.items(), key=lambda item: _sort_key(item[0])):
        if node.class_type not in RESOLVABLE_HELPER_CLASS_TYPES:
            continue
        issues.append(
            PortIssue(
                code=STRICT_READY_HELPER_IN_EMITTED_OUTPUT,
                message=(
                    f"Resolvable helper node {node_id} ({node.class_type}) survived to emission; "
                    f"the resolver should have stripped it."
                ),
                severity="error",
                node_id=str(node_id),
                class_type=node.class_type,
                detail={"target": f"node:{node_id}"},
                recommendation=(
                    "Ensure the resolver in port_convert_workflow eliminates all "
                    "RESOLVABLE_HELPER_CLASS_TYPES nodes before emission."
                ),
            )
        )
    return issues


def _compile_api_prompt(workflow: VibeWorkflow) -> dict[str, Any] | None:
    try:
        return workflow.compile("api")
    except Exception:
        return None


def _issue_target(issue: PortIssue) -> str:
    detail_target = (issue.detail or {}).get("target")
    if isinstance(detail_target, str) and detail_target:
        return detail_target
    if issue.node_id:
        return f"node:{issue.node_id}"
    return issue.code


def _issue_sort_key(issue: PortIssue) -> tuple[Any, ...]:
    return (issue.code, _issue_target(issue), _sort_key(issue.node_id or ""), issue.class_type or "")


def _sort_key(value: object) -> tuple[int, object]:
    text = str(value or "")
    return (0, int(text)) if text.isdigit() else (1, text)


__all__ = [
    "ALLOWED_FINAL_CATEGORIES",
    "DEFAULT_EXCEPTION_PATH",
    "EXCEPTION_MATCH_KEYS",
    "HIDDEN_MODEL_FILENAME",
    "OPAQUE_COMPONENT_NODE_CLASS",
    "STRICT_READY_BROKEN_PUBLIC_INPUT",
    "STRICT_READY_BUILD_FAILED",
    "STRICT_READY_COMPILE_FAILED",
    "STRICT_READY_HELPER_IN_EMITTED_OUTPUT",
    "STRICT_READY_LOAD_FAILED",
    "STRICT_READY_MISSING_OUTPUT_CONTRACT",
    "STRICT_READY_MISSING_PUBLIC_INPUT",
    "STRICT_READY_UNNAMED_OUTPUT_CONTRACT",
    "STRICT_READY_UNRESOLVED_WIDGETS",
    "STRICT_READY_VIOLATION_CODES",
    "StrictReadyContext",
    "StrictReadyException",
    "apply_strict_ready_exceptions",
    "load_strict_ready_exceptions",
    "validate_strict_ready_workflow",
]
