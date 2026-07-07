from __future__ import annotations

import ast
import json
import re
import textwrap
from typing import Any, Mapping

from vibecomfy.porting.edit.ops import (
    AnchorRef,
    LinkSourceRef,
    NodeTarget,
)
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    infer_add_node_anchor_hint,
)
from vibecomfy.identity.codec import to_raw_name
from vibecomfy.porting.authoring_surface import input_spec_is_socket_only
from vibecomfy.schema import schema_for, socket_types_compatible

from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    StatementResult,
    _ResolvedAddNodeCall,
    _ResolvedGraphName,
    _ResolvedOutputEndpoint,
    _ResolvedTargetField,
    _ExpandedStatement,
    _diag,
)
from vibecomfy.porting.edit._parse import (
    _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    _RAW_COORDINATE_HINT_NAMES,
    _assignment_op_kind,
    _call_name,
    _fold_constant,
    _is_graph_reference_value,
    _resolve_vibecomfy_constructor,
    _unsafe,
)
from vibecomfy.porting.edit._ir_utils import (
    _MISSING_WIDGET_VALUE,
    _canonical_input_name_for_class,
    _input_spec_for_field,
    _known_core_input_socket_type,
    _link_origin,
    _normalize_ir_type,
    _output_slot_name,
    _output_specs,
    _resolve_class_type_from_alias,
    _socket_type_from_widget_value,
    _widget_value_for_field,
)
from vibecomfy.porting.resolution import _find_named_slot

_EXEC_CLASS_TYPE = "vibecomfy.exec"
_OUTPUT_ALIAS_RE = re.compile(r"output_(\d+)\Z")


def _normalize_exec_io_entries(value: Any) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    raw_items: Any
    if isinstance(value, Mapping):
        raw_items = [[name, socket_type] for name, socket_type in value.items()]
    elif isinstance(value, list):
        raw_items = value
    else:
        return entries
    for index, item in enumerate(raw_items):
        name: Any
        socket_type: Any
        if isinstance(item, Mapping):
            name = item.get("name")
            socket_type = item.get("type")
        elif isinstance(item, (list, tuple)) and len(item) >= 1:
            name = item[0]
            socket_type = item[1] if len(item) >= 2 else None
        else:
            continue
        clean_name = str(name or f"value_{index}").strip() or f"value_{index}"
        clean_type = str(socket_type or "*").strip() or "*"
        entries.append((clean_name, clean_type))
    return entries


def _normalize_exec_io(value: Any) -> dict[str, list[tuple[str, str]]] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, Mapping):
        return None
    return {
        "inputs": _normalize_exec_io_entries(value.get("inputs")),
        "outputs": _normalize_exec_io_entries(value.get("outputs")),
    }


def _infer_exec_output_names_from_source(source: Any) -> list[tuple[str, str]]:
    """Best-effort parse of a vibecomfy.exec source body for `return {...}` keys."""
    if not isinstance(source, str) or not source.strip():
        return []
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return []
    keys: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        for key in value.keys:
            name: str | None = None
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                name = key.value
            elif hasattr(ast, "Str") and isinstance(key, ast.Str):  # pragma: no cover - py<3.8
                name = key.s
            if name:
                keys.append((name, "*"))
    return keys


def _infer_exec_io(
    source: Any,
    linked_inputs: Mapping[str, LinkSourceRef],
) -> dict[str, list[tuple[str, str]]] | None:
    """Infer a minimal exec `io` contract from source return keys and wired inputs.

    This is a fallback for agents that omit `io` or leave it empty.  Output names
    are taken from the source body's `return {...}` keys, and input names mirror
    the physical slot names the agent actually wired (``in_0``, ``in_1``, ...),
    which keeps the runtime wrapper signature compatible with the source.
    """
    outputs = _infer_exec_output_names_from_source(source)
    inputs: list[tuple[str, str]] = []
    for slot_name in sorted(linked_inputs.keys()):
        if slot_name.startswith("in_"):
            inputs.append((slot_name, "*"))
    if not inputs and not outputs:
        return None
    return {"inputs": inputs, "outputs": outputs}


def _exec_semantic_slot_name(
    class_type: str,
    io_value: Any,
    slot_name: str,
    *,
    direction: str,
) -> str:
    if class_type != _EXEC_CLASS_TYPE or not isinstance(slot_name, str) or not slot_name:
        return slot_name
    normalized = _normalize_exec_io(io_value)
    if normalized is None:
        return slot_name
    entries = normalized["inputs" if direction == "input" else "outputs"]
    for index, (semantic_name, _socket_type) in enumerate(entries):
        if semantic_name == slot_name:
            prefix = "in" if direction == "input" else "out"
            return f"{prefix}_{index}"
    return slot_name


def _exec_semantic_slot_name_for_node(
    node: Mapping[str, Any],
    class_type: str,
    slot_name: str,
    *,
    direction: str,
) -> str:
    return _exec_semantic_slot_name(
        class_type,
        _widget_value_for_field(node, class_type, "io"),
        slot_name,
        direction=direction,
    )


def _shorten_query_text(value: Any, *, max_chars: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def _format_compact_sequence(values: Any, *, max_items: int = 16, max_chars: int = 420) -> str:
    if not isinstance(values, (list, tuple)):
        return ""
    rendered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in rendered:
            rendered.append(text)
        if len(rendered) >= max_items:
            break
    suffix = ""
    if len(values) > len(rendered):
        suffix = f", and {len(values) - len(rendered)} more"
    return _shorten_query_text(", ".join(rendered) + suffix, max_chars=max_chars)


def _format_research_query_output(result: Any) -> str:
    lines: list[str] = []
    summary = _shorten_query_text(getattr(result, "summary", ""), max_chars=1200)
    if summary:
        lines.append(summary)
    sources = getattr(result, "sources", ()) or ()
    if sources:
        lines.append("Sources:")
        selected_sources: list[Any] = []
        seen_source_kinds: set[str] = set()
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            selected_sources.append(source)
            seen_source_kinds.add(str(source.get("source") or ""))
            if len(selected_sources) >= 5:
                break
        for source in sources:
            if len(selected_sources) >= 8:
                break
            if not isinstance(source, Mapping):
                continue
            source_kind = str(source.get("source") or "")
            if source_kind and source_kind not in seen_source_kinds:
                selected_sources.append(source)
                seen_source_kinds.add(source_kind)
        for index, source in enumerate(selected_sources, start=1):
            if not isinstance(source, Mapping):
                continue
            title = _shorten_query_text(
                source.get("title")
                or source.get("class_type")
                or source.get("path")
                or source.get("url")
                or source.get("source")
                or f"source {index}",
                max_chars=140,
            )
            descriptor_parts = [
                _shorten_query_text(source.get(key), max_chars=180)
                for key in ("kind", "source_type", "pack", "source_workflow_path", "path", "url")
                if source.get(key)
            ]
            descriptor = f" ({'; '.join(descriptor_parts[:4])})" if descriptor_parts else ""
            description = _shorten_query_text(
                source.get("description") or source.get("snippet") or source.get("summary"),
                max_chars=260,
            )
            line = f"- {title}{descriptor}"
            if description:
                line += f": {description}"
            lines.append(line)
            node_types = _format_compact_sequence(source.get("node_types"))
            if node_types:
                lines.append(f"  node_types: {node_types}")
            key_values = _format_compact_sequence(source.get("key_values"), max_items=12, max_chars=320)
            if key_values:
                lines.append(f"  key_values: {key_values}")
            workflow_schemas = _format_workflow_schema_hints(source.get("workflow_schema"))
            if workflow_schemas:
                lines.extend(f"  {line}" for line in workflow_schemas)
    warnings = getattr(result, "warnings", ()) or ()
    if warnings:
        lines.append("Warnings:")
        for warning in warnings[:5]:
            lines.append(f"- {_shorten_query_text(warning, max_chars=260)}")
    return "\n".join(lines).strip() or "No research findings returned."


def _format_workflow_schema_hints(value: Any, *, max_classes: int = 5) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    lines: list[str] = []
    # Stable neutral presentation order: alphabetical by class_type.
    # No family-token ranking — every entry gets equal presentation weight.
    class_types = sorted(str(key) for key in value)
    for class_type in class_types[:max_classes]:
        info = value.get(class_type)
        if not isinstance(info, Mapping):
            continue
        input_groups = info.get("input")
        required_names: list[str] = []
        optional_names: list[str] = []
        if isinstance(input_groups, Mapping):
            required = input_groups.get("required")
            optional = input_groups.get("optional")
            if isinstance(required, Mapping):
                required_names = sorted(str(name) for name in required)[:8]
            if isinstance(optional, Mapping):
                optional_names = [
                    _format_schema_input_hint(str(name), optional.get(name))
                    for name in sorted(str(name) for name in optional)[:8]
                ]
        outputs = info.get("outputs")
        output_names: list[str] = []
        if isinstance(outputs, list):
            for item in outputs[:8]:
                if isinstance(item, Mapping):
                    output_names.append(str(item.get("name") or item.get("type") or "*"))
                elif item is not None:
                    output_names.append(str(item))
        parts = []
        if required_names:
            parts.append(f"inputs={', '.join(required_names)}")
        if optional_names:
            parts.append(f"widgets={', '.join(optional_names)}")
        if output_names:
            parts.append(f"outputs={', '.join(output_names)}")
        if parts:
            lines.append(f"workflow_schema {class_type}: {'; '.join(parts)}")
    remaining = max(0, len(value) - max_classes)
    if remaining > 0:
        lines.append(f"workflow_schema: and {remaining} more class(es)")
    return lines


def _format_schema_input_hint(name: str, raw_spec: Any) -> str:
    if not isinstance(raw_spec, Mapping) or "default" not in raw_spec:
        return name
    default = raw_spec.get("default")
    if isinstance(default, str):
        rendered = repr(default)
    elif isinstance(default, (int, float, bool)) or default is None:
        rendered = repr(default)
    else:
        return name
    if len(rendered) > 48:
        rendered = rendered[:45] + "..."
    return f"{name}={rendered}"


def _has_concrete_workflow_pattern(result: Any) -> bool:
    for source in getattr(result, "sources", ()) or ():
        if not isinstance(source, Mapping):
            continue
        if source.get("node_types") or source.get("source_workflow_path"):
            return True
        source_kind = str(source.get("source") or "")
        source_type = str(source.get("source_type") or "")
        if source_kind in {"external_workflow", "ready_template", "source_workflow", "hivemind_workflow"}:
            if source_type == "github_workflow_json" or source.get("path"):
                return True
    return False


def _concrete_workflow_node_types(result: Any, *, limit: int = 10) -> tuple[str, ...]:
    node_types: list[str] = []
    for source in getattr(result, "sources", ()) or ():
        if not isinstance(source, Mapping):
            continue
        raw_node_types = source.get("node_types")
        if not isinstance(raw_node_types, (list, tuple)):
            continue
        for raw_node_type in raw_node_types:
            node_type = str(raw_node_type or "").strip()
            if node_type and node_type not in node_types:
                node_types.append(node_type)
            if len(node_types) >= limit:
                return tuple(node_types)
    return tuple(node_types)


def _has_url_only_web_leads(result: Any) -> bool:
    for source in getattr(result, "sources", ()) or ():
        if not isinstance(source, Mapping):
            continue
        if str(source.get("source") or "") != "web":
            continue
        if source.get("url") and not source.get("node_types") and not source.get("source_workflow_path"):
            return True
    return False


def _research_followup_guidance(query: str, sources: tuple[str, ...], result: Any) -> str:
    notes: list[str] = []
    source_set = set(sources)
    if "workflows" in source_set:
        notes.append(
            "Workflow-first check: treat workflow/template results as usable precedent only if they mention "
            "the user's named target technology/model/node family. If results are generic or for another "
            "family, search external workflow/examples next using the named target."
        )
    if "workflows" in source_set and "registry" in source_set:
        notes.append(
            "Research-order check: registry evidence was requested in the same call as workflow evidence. "
            "Do not use registry results as a substitute for workflow context; after an insufficient internal "
            "workflow search, make a separate external workflow/examples call before using registry evidence."
        )
    if "web" in source_set and _has_url_only_web_leads(result) and not _has_concrete_workflow_pattern(result):
        notes.append(
            "External workflow check: these web results are URL/title leads, not yet a workflow pattern. "
            "Before concluding there is no usable precedent, search externally for a workflow JSON, repo example, or page result "
            "that exposes concrete node types and wiring for the named target."
        )
    if "web" in source_set and _has_concrete_workflow_pattern(result):
        node_types = _concrete_workflow_node_types(result)
        node_hint = f" Concrete workflow node types found: {', '.join(node_types)}." if node_types else ""
        notes.append(
            "Concrete workflow pattern found: treat this workflow/example as the pattern evidence now."
            f"{node_hint} Next, apply the smallest defensible adaptation of this pattern to the current graph, "
            "using only authoring signatures exposed in this edit session. "
            "The listed source_workflow_path/path is evidence for the fetched workflow; python() only shows the "
            "current graph. Do not run another research(...) call for the same workflow JSON, switch back to generic "
            "local workflow searches, or use broad custom-node queries such as only the model name."
        )
    if "registry" in source_set and "workflows" not in source_set and "web" not in source_set:
        notes.append(
            "Registry check: use registry/schema evidence to verify node packs or classes already suggested by "
            "workflow/example evidence, not to invent a workflow pattern by itself."
        )
    if not notes:
        return ""
    return "\n\n" + "\n".join(f"{index}. {note}" for index, note in enumerate(notes, start=1))


_RESEARCH_SOURCE_ALIASES: dict[str, str] = {
    "local": "workflows",
    "workflow": "workflows",
    "workflows": "workflows",
    "template": "workflows",
    "templates": "workflows",
    "registry": "registry",
    "comfy-registry": "registry",
    "comfy_registry": "registry",
    "manager": "registry",
    "comfyui-manager": "registry",
    "custom_nodes": "registry",
    "custom-nodes": "registry",
    "hivemind": "messages",
    "message": "messages",
    "messages": "messages",
    "discord": "messages",
    "web": "web",
    "github": "web",
    "internet": "web",
}


def _normalize_research_sources(value: Any) -> tuple[tuple[str, ...] | None, CompactDiagnostic | None]:
    if value is None:
        return None, None
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        return None, _diag(
            "research_sources_not_strings",
            "research(...) sources must be a string or list of strings.",
            severity="error",
        )
    normalized: list[str] = []
    invalid: list[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            invalid.append(repr(item))
            continue
        key = item.strip().casefold()
        source = _RESEARCH_SOURCE_ALIASES.get(key)
        if source is None:
            invalid.append(item)
            continue
        if source not in normalized:
            normalized.append(source)
    if invalid:
        return None, _diag(
            "unsupported_research_source",
            "research(...) sources must be chosen from workflows, registry, messages, or web.",
            severity="error",
            detail={"invalid": invalid, "allowed": ["workflows", "registry", "messages", "web"]},
        )
    return tuple(normalized), None


class _ResolveMixin:
    """Symbolic-name resolution methods — the named M4 seam."""

    def _uid_for_scope(self, scope_path: str, class_type: str) -> str:
        """Best-effort uid lookup for a newly added node by looking at the ledger."""
        # Look for nodes matching class_type that were recently added.
        # The simplest approach: check the most recently added node in the ledger.
        nodes = self.ledger.graph.get("nodes") or []
        for node in reversed(nodes):
            ct = str(node.get("type") or node.get("class_type") or "")
            if ct == class_type:
                uid = node.get("properties", {}).get("vibecomfy_uid", "")
                if uid and uid in self.name_by_uid:
                    return uid
        return ""

    def _resolve_statement(
        self,
        item: "_ExpandedStatement",
        *,
        placement_facts: BatchPlacementFacts,
    ) -> StatementResult:
        statement = item.node
        source = item.source
        env = item.env
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call_name = _call_name(statement.value)
            if call_name == "done":
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="done",
                )
            return self._resolve_query_statement(
                statement_index=item.statement_index,
                source=source,
                call=statement.value,
                env=env,
            )
        if isinstance(statement, ast.Assign):
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                return self._resolve_add_node_statement(
                    statement_index=item.statement_index,
                    source=source,
                    target_name=target.id,
                    value=statement.value,
                    env=env,
                    placement_facts=placement_facts,
                )
            assert isinstance(target, ast.Attribute)
            field_target, target_issues = self._resolve_target_field(target)
            if target_issues:
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind=_assignment_op_kind(statement.value, target_attr=target.attr),
                    diagnostics=tuple(target_issues),
                )
            assert field_target is not None
            rhs = statement.value
            if isinstance(rhs, ast.Constant) and rhs.value is None:
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="remove_link",
                    detail={"resolved_target": field_target, "ast_node": statement, "constant_env": dict(env)},
                )
            if _is_graph_reference_value(rhs):
                endpoint, endpoint_issues = self._resolve_rhs_endpoint(rhs, target=field_target)
                if endpoint_issues:
                    return StatementResult(
                        statement_index=item.statement_index,
                        source=source,
                        ok=False,
                        landed=False,
                        op_kind=_assignment_op_kind(rhs, target_attr=target.attr),
                        diagnostics=tuple(endpoint_issues),
                    )
                assert endpoint is not None
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="upsert_link",
                    detail={"resolved_target": field_target, "resolved_endpoint": endpoint, "ast_node": statement, "constant_env": dict(env)},
                )
            return StatementResult(
                statement_index=item.statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="set_mode" if target.attr == "mode" else "set_node_field",
                detail={"resolved_target": field_target, "ast_node": statement, "constant_env": dict(env)},
            )
        assert isinstance(statement, ast.Delete)
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            node_ref, issues = self._resolve_graph_name(target.id)
        else:
            node_ref, issues = None, [_unsafe(target, "scope_escape_not_allowed", "Only bare graph names may be deleted.")]
        _ = node_ref
        return StatementResult(
            statement_index=item.statement_index,
            source=source,
            ok=not issues,
            landed=False,
            op_kind="remove_node",
            diagnostics=tuple(issues),
            detail={"resolved_node": node_ref, "ast_node": statement, "constant_env": dict(env)}
            if node_ref is not None
            else {"ast_node": statement, "constant_env": dict(env)},
        )

    def _resolve_query_statement(
        self,
        *,
        statement_index: int,
        source: str,
        call: ast.Call,
        env: Mapping[str, Any],
    ) -> StatementResult:
        call_name = _call_name(call)
        if call_name not in {"search", "research", "python"}:
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "unsupported_query_call",
                        "Only search(...), research(...), python(), and done() are supported as top-level query calls.",
                        severity="error",
                        detail={"call": call_name},
                    ),
                ),
            )

        if call_name == "python":
            diagnostics: list[CompactDiagnostic] = []
            if call.args:
                diagnostics.append(
                    _diag("python_arguments_not_allowed", "python() does not accept arguments.", severity="error")
                )
            for keyword in call.keywords:
                if keyword.arg is None:
                    diagnostics.append(
                        _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                    )
                else:
                    diagnostics.append(
                        _diag(
                            "unsupported_python_keyword",
                            f"python() does not accept keyword {keyword.arg!r}.",
                            severity="error",
                            detail={"keyword": keyword.arg},
                        )
                    )
            if diagnostics:
                return StatementResult(
                    statement_index=statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind="query",
                    diagnostics=tuple(diagnostics),
                    detail={"query": "python"},
                )
            try:
                output = self.python()
            except Exception as exc:  # noqa: BLE001 - report query failures in-band
                return StatementResult(
                    statement_index=statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind="query",
                    diagnostics=(
                        _diag(
                            "python_query_failed",
                            f"python() failed: {exc}",
                            severity="error",
                        ),
                    ),
                    detail={"query": "python"},
                )
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="query",
                detail={"query": "python", "query_output": str(output)},
            )

        if call_name == "research":
            diagnostics: list[CompactDiagnostic] = []
            query: str | None = None
            requested_sources: tuple[str, ...] | None = None
            if len(call.args) > 1:
                diagnostics.append(
                    _diag(
                        "research_arguments_not_allowed",
                        "research(...) accepts exactly one string query.",
                        severity="error",
                    )
                )
            elif call.args:
                value, diagnostic = _fold_constant(call.args[0], env=env)
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                elif not isinstance(value, str) or not value.strip():
                    diagnostics.append(
                        _diag(
                            "research_query_not_string",
                            "research(...) query must be a non-empty string.",
                            severity="error",
                        )
                    )
                else:
                    query = value.strip()
            for keyword in call.keywords:
                if keyword.arg is None:
                    diagnostics.append(
                        _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                    )
                    continue
                if keyword.arg not in {"query", "sources"}:
                    diagnostics.append(
                        _diag(
                            "unsupported_research_keyword",
                            f"research(...) does not accept keyword {keyword.arg!r}.",
                            severity="error",
                            detail={"keyword": keyword.arg, "allowed": ["query", "sources"]},
                        )
                    )
                    continue
                if keyword.arg == "sources":
                    value, diagnostic = _fold_constant(keyword.value, env=env)
                    if diagnostic is not None:
                        diagnostics.append(diagnostic)
                        continue
                    requested_sources, source_diagnostic = _normalize_research_sources(value)
                    if source_diagnostic is not None:
                        diagnostics.append(source_diagnostic)
                    continue
                if query is not None:
                    diagnostics.append(
                        _diag(
                            "research_query_duplicated",
                            "research(...) accepts the query either positionally or as query=, not both.",
                            severity="error",
                        )
                    )
                    continue
                value, diagnostic = _fold_constant(keyword.value, env=env)
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                elif not isinstance(value, str) or not value.strip():
                    diagnostics.append(
                        _diag(
                            "research_query_not_string",
                            "research(...) query must be a non-empty string.",
                            severity="error",
                        )
                    )
                else:
                    query = value.strip()
            if query is None and not diagnostics:
                diagnostics.append(
                    _diag(
                        "research_query_required",
                        "research(...) requires a non-empty string query.",
                        severity="error",
                    )
                )
            if diagnostics:
                return StatementResult(
                    statement_index=statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind="query",
                    diagnostics=tuple(diagnostics),
                    detail={"query": "research"},
                )
            assert query is not None
            try:
                import importlib

                research_module = importlib.import_module("vibecomfy.executor.research")
                pack_resolver_module = importlib.import_module("vibecomfy.registry.pack_resolver")
                httpx_module = importlib.import_module("httpx")
                requested_source_tuple = requested_sources or ("workflows",)
                source_set = set(requested_source_tuple)
                registry_resolver = None
                if "registry" in source_set:
                    def registry_resolver(registry_query: str) -> Any:
                        client = httpx_module.Client(timeout=3.0, follow_redirects=True)
                        return pack_resolver_module.resolve_missing_nodes(
                            registry_query,
                            registry_client=client,
                            manager_client=client,
                            github_client=client,
                        )
                output = research_module.research(
                    query,
                    local_limit=5 if "workflows" in source_set else 0,
                    hivemind_timeout=3.0,
                    web_search_timeout=3.0,
                    registry_resolver=registry_resolver,
                    hivemind_client=None if not source_set.intersection({"messages", "workflows"}) else research_module._default_hivemind_client,
                    web_search_client=None if "web" not in source_set else research_module._default_web_search_client,
                )
            except Exception as exc:  # noqa: BLE001 - report query failures in-band
                return StatementResult(
                    statement_index=statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind="query",
                    diagnostics=(
                        _diag(
                            "research_query_failed",
                            f"research(...) failed: {exc}",
                            severity="error",
                        ),
                    ),
                    detail={"query": "research", "research_query": query},
                )
            # ── build inline research detail ────────────────────────────
            detail: dict[str, Any] = {
                "query": "research",
                "research_query": query,
                "research_sources": tuple(source for source in requested_source_tuple if source in source_set),
                "requested_research_sources": requested_source_tuple,
                "resolver_candidates": [
                    source.get("resolver_candidate")
                    for source in getattr(output, "sources", ()) or ()
                    if isinstance(source, Mapping) and isinstance(source.get("resolver_candidate"), Mapping)
                ],
                "workflow_schema_candidates": [
                    {
                        "pack": {
                            "name": source.get("class_type") or source.get("pack") or "workflow_json",
                            "slug": source.get("pack") or "workflow_json",
                            "source": source.get("source") or "external_workflow",
                            "url": source.get("url") or "",
                        },
                        "provisional_schema": {
                            "version": "workflow-json",
                            "schema": {"nodes": source.get("workflow_schema")},
                            "runnable": False,
                        },
                        "expected_classes": source.get("workflow_schema_classes") or [],
                        "validation_mode": "workflow_json_provisional",
                        "warnings": ["Schema derived from workflow JSON UI sockets; runtime node pack is not installed."],
                    }
                    for source in getattr(output, "sources", ()) or ()
                    if isinstance(source, Mapping) and isinstance(source.get("workflow_schema"), Mapping)
                ],
            }
            # ── structured evidence fields (neutral, no recommendation) ─
            precedent_packet = getattr(output, "precedent_packet", None)
            if precedent_packet is not None:
                detail["precedent_packet"] = precedent_packet.to_dict()
            precedent_slices = getattr(output, "precedent_slices", ()) or ()
            if precedent_slices:
                detail["precedent_slices"] = [
                    s.to_dict() for s in precedent_slices
                ]
            adaptation_plan = getattr(output, "adaptation_plan", None)
            if adaptation_plan is not None:
                detail["adaptation_plan"] = adaptation_plan.to_dict()
            # ── formatted evidence/context output ────────────────────────
            detail["query_output"] = (
                _format_research_query_output(output)
                + _research_followup_guidance(query, requested_source_tuple, output)
            )
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="query",
                detail=detail,
            )

        allowed = {"focus_types", "compatible_input_type", "compatible_output_type", "formatted"}
        kwargs: dict[str, Any] = {}
        diagnostics: list[CompactDiagnostic] = []
        for keyword in call.keywords:
            if keyword.arg is None:
                diagnostics.append(
                    _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                )
                continue
            if keyword.arg not in allowed:
                diagnostics.append(
                    _diag(
                        "unsupported_search_keyword",
                        f"search(...) does not accept keyword {keyword.arg!r}.",
                        severity="error",
                        detail={"keyword": keyword.arg, "allowed": sorted(allowed)},
                    )
                )
                continue
            value, diagnostic = _fold_constant(keyword.value, env=env)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
                continue
            kwargs[keyword.arg] = value
        if diagnostics:
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=tuple(diagnostics),
                detail={"query": "search"},
            )

        try:
            output = self.search(
                focus_types=kwargs.get("focus_types"),
                compatible_input_type=kwargs.get("compatible_input_type"),
                compatible_output_type=kwargs.get("compatible_output_type"),
                formatted=True,
            )
        except Exception as exc:  # noqa: BLE001 - report query failures in-band
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "search_query_failed",
                        f"search(...) failed: {exc}",
                        severity="error",
                    ),
                ),
                detail={"query": "search"},
            )

        output_text = str(output)
        focus_types = kwargs.get("focus_types")
        if (
            isinstance(focus_types, (list, tuple))
            and focus_types
            and "No node signature found" in output_text
        ):
            exact_focus = ", ".join(str(item) for item in focus_types if str(item).strip())
            output_text += (
                "\nThis local schema miss does not prove the named external workflow "
                f"or model family is unavailable. Missing class name(s): {exact_focus}. "
                "Do not broaden this into guessed branded constructors. Use workflow "
                "precedent as pattern evidence, but only instantiate classes that appear "
                "in the current signature catalog or another authoring surface exposed "
                "by this edit session."
            )

        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="query",
            detail={"query": "search", "query_output": output_text},
        )

    def _bind_graph_name(self, name: str, uid: str) -> None:
        prior_uid = self.uid_by_name.get(name)
        if prior_uid is not None and self.name_by_uid.get(prior_uid) == name:
            self.name_by_uid.pop(prior_uid, None)
        prior_name = self.name_by_uid.get(uid)
        if prior_name is not None and self.uid_by_name.get(prior_name) == uid:
            self.uid_by_name.pop(prior_name, None)
        self.uid_by_name[name] = uid
        self.name_by_uid[uid] = name
        self.unbound_names.discard(name)

    def _mark_name_unbound(self, name: str) -> None:
        prior_uid = self.uid_by_name.pop(name, None)
        if prior_uid is not None and self.name_by_uid.get(prior_uid) == name:
            self.name_by_uid.pop(prior_uid, None)
        self.unbound_names.add(name)

    def _resolve_add_node_statement(
        self,
        *,
        statement_index: int,
        source: str,
        target_name: str,
        value: ast.expr,
        env: Mapping[str, Any],
        placement_facts: BatchPlacementFacts,
    ) -> StatementResult:
        if target_name.startswith("__"):
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=(
                    _diag("dunder_name_not_allowed", f"Graph name {target_name!r} is not allowed.", severity="error"),
                ),
                detail={"target_name": target_name},
            )
        if not isinstance(value, ast.Call):
            self._mark_name_unbound(target_name)
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=(
                    _diag("expression_not_call", "Only node-construction calls may be assigned to graph names.", severity="error"),
                ),
                detail={"target_name": target_name},
            )
        resolved_call, issues = self._resolve_add_node_call(
            target_name,
            value,
            env=env,
            placement_facts=placement_facts,
        )
        if issues:
            self._mark_name_unbound(target_name)
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=tuple(issues),
                detail={"target_name": target_name, "ast_node": value, "constant_env": dict(env)},
            )
        assert resolved_call is not None
        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="node_call",
            detail={
                "target_name": target_name,
                "ast_node": value,
                "constant_env": dict(env),
                "resolved_add_node": resolved_call,
            },
        )

    def _resolve_add_node_call(
        self,
        target_name: str,
        call: ast.Call,
        *,
        env: Mapping[str, Any],
        placement_facts: BatchPlacementFacts,
    ) -> tuple[_ResolvedAddNodeCall | None, list[CompactDiagnostic]]:
        func = call.func
        class_type, dotted_vibecomfy = _resolve_vibecomfy_constructor(func)
        if dotted_vibecomfy and class_type not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface. Use vibecomfy.exec for executable Python code nodes.",
                )
            ]
        if class_type is None:
            return None, [_unsafe(func, "call_target_not_name", "Node construction calls must target a simple class name.")]
        if class_type.startswith("vibecomfy.") and class_type not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface. Use vibecomfy.exec for executable Python code nodes.",
                )
            ]

        # Reverse-resolve authoring alias (e.g. `checkpointloader_simple` → `CheckpointLoader-Simple`)
        resolved_class_type = _resolve_class_type_from_alias(class_type, self.schema_provider)
        if resolved_class_type is not None and resolved_class_type != class_type:
            class_type = resolved_class_type

        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        fake_target_node = _ResolvedGraphName(
            name=target_name,
            uid="<pending>",
            scope_path="",
            node={},
            class_type=class_type,
        )
        exec_io_value: Any = None
        if class_type == _EXEC_CLASS_TYPE:
            for keyword in call.keywords:
                if keyword.arg != "io":
                    continue
                exec_io_value, _ = _fold_constant(keyword.value, env=env)
                break
        literal_fields: dict[str, Any] = {}
        linked_inputs: dict[str, LinkSourceRef] = {}
        anchor_near: NodeTarget | None = None
        relation: str | None = None
        group_title: str | None = None
        issues: list[CompactDiagnostic] = []

        for keyword in call.keywords:
            if keyword.arg is None:
                issues.append(_unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed."))
                continue
            name = keyword.arg
            if name in _RAW_COORDINATE_HINT_NAMES:
                issues.append(
                    _unsafe(
                        keyword.value,
                        "raw_coordinate_kwarg_not_allowed",
                        f"Raw coordinate kwarg {name!r} is not allowed; use near=..., relation=..., and group=... placement hints.",
                    )
                )
                continue
            if name == "near":
                if not isinstance(keyword.value, ast.Name):
                    issues.append(
                        _unsafe(keyword.value, "invalid_near_hint", "near= must reference a rendered graph name, not a slot or literal.")
                    )
                    continue
                node_ref, near_issues = self._resolve_graph_name(keyword.value.id)
                if near_issues:
                    issues.extend(near_issues)
                    continue
                assert node_ref is not None
                anchor_near = NodeTarget(node_ref.scope_path, node_ref.uid)
                continue
            if name == "relation":
                relation_value, relation_issue = _fold_constant(keyword.value, env=env)
                if relation_issue is not None:
                    issues.append(relation_issue)
                    continue
                if not isinstance(relation_value, str):
                    issues.append(_unsafe(keyword.value, "invalid_relation_hint", "relation= must be a string literal."))
                    continue
                relation = relation_value.strip()
                if relation not in {"near", "right_of", "left_of", "below"}:
                    issues.append(
                        _unsafe(
                            keyword.value,
                            "invalid_relation_hint",
                            "relation= must be one of 'near', 'right_of', 'left_of', or 'below' for Python add-node statements.",
                        )
                    )
                continue
            if name == "group":
                group_value, group_issue = _fold_constant(keyword.value, env=env)
                if group_issue is not None:
                    issues.append(group_issue)
                    continue
                if not isinstance(group_value, str) or not group_value.strip():
                    issues.append(_unsafe(keyword.value, "invalid_group_hint", "group= must be a non-empty string literal."))
                    continue
                group_title = group_value
                continue
            if class_type == _EXEC_CLASS_TYPE:
                name = _exec_semantic_slot_name(
                    class_type,
                    exec_io_value,
                    name,
                    direction="input",
                )
            else:
                name = _canonical_input_name_for_class(schema_inputs, class_type, name)
            if _is_graph_reference_value(keyword.value):
                socket_type = _normalize_ir_type(getattr(_input_spec_for_field(schema_inputs, name), "type", None))
                target = _ResolvedTargetField(node=fake_target_node, field_name=name, socket_type=socket_type)
                endpoint, endpoint_issues = self._resolve_rhs_endpoint(keyword.value, target=target)
                if endpoint_issues:
                    issues.extend(endpoint_issues)
                    continue
                assert endpoint is not None
                linked_inputs[name] = LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, endpoint.slot_name)
                continue
            literal_value, literal_issue = _fold_constant(keyword.value, env=env)
            if literal_issue is not None:
                issues.append(literal_issue)
                continue
            spec = _input_spec_for_field(schema_inputs, name)
            if input_spec_is_socket_only(spec):
                issues.append(
                    _diag(
                        "socket_input_not_literal_widget",
                        f"{class_type}.{name} is an input socket, not a widget; connect a source node instead.",
                        severity="error",
                        detail={
                            "class_type": class_type,
                            "input": name,
                            "target_name": target_name,
                            "input_type": getattr(spec, "type", None),
                        },
                    )
                )
                continue
            literal_fields[name] = literal_value

        if class_type == _EXEC_CLASS_TYPE:
            normalized_io = _normalize_exec_io(exec_io_value)
            if normalized_io is None or (not normalized_io["inputs"] and not normalized_io["outputs"]):
                inferred_io = _infer_exec_io(literal_fields.get("source"), linked_inputs)
                if inferred_io is not None:
                    literal_fields["io"] = {
                        "inputs": [[name, socket_type] for name, socket_type in inferred_io["inputs"]],
                        "outputs": [[name, socket_type] for name, socket_type in inferred_io["outputs"]],
                    }

        if relation is not None and anchor_near is None and group_title is None:
            issues.append(
                _diag(
                    "anchor_target_missing",
                    "relation= requires near=... or group=... to anchor the new node.",
                    severity="error",
                    detail={"class_type": class_type, "target_name": target_name},
                )
            )

        scope_paths = {ref.scope_path for ref in linked_inputs.values()}
        if anchor_near is not None:
            scope_paths.add(anchor_near.scope_path)
        if len(scope_paths) > 1:
            issues.append(
                _diag(
                    "cross_scope_add_node_unsupported",
                    "Add-node statements cannot mix link and anchor references from different scopes.",
                    severity="error",
                    detail={"target_name": target_name, "scope_paths": sorted(scope_paths)},
                )
            )
        if issues:
            return None, issues
        scope_path = next(iter(scope_paths), "")
        anchor = None
        if anchor_near is not None or group_title is not None:
            anchor = AnchorRef(
                relation=(relation or "near"),  # type: ignore[arg-type]
                near=anchor_near,
                group_title=group_title,
            )
        else:
            anchor = self._infer_add_node_anchor(
                target_name=target_name,
                scope_path=scope_path,
                resolved_inputs=linked_inputs,
                placement_facts=placement_facts,
            )
        return (
            _ResolvedAddNodeCall(
                target_name=target_name,
                scope_path=scope_path,
                class_type=class_type,
                fields=literal_fields,
                inputs=linked_inputs,
                anchor=anchor,
            ),
            [],
        )

    @staticmethod
    def _compact_port_issue(issue: Any) -> CompactDiagnostic:
        return CompactDiagnostic(
            code=str(getattr(issue, "code", "edit_apply_error")),
            message=str(getattr(issue, "message", "Edit apply failed.")),
            severity=str(getattr(issue, "severity", "error")),
            detail=dict(getattr(issue, "detail", {}) or {}),
        )

    def _estimate_add_node_width(self, class_type: str) -> int:
        from vibecomfy.porting.layout.sizing import estimate_node_size
        from vibecomfy.workflow import VibeNode

        schema = schema_for(self.schema_provider, class_type)
        return estimate_node_size(VibeNode(id="__batch__", class_type=class_type, uid="__batch__"), schema)[0]

    def _infer_add_node_anchor(
        self,
        *,
        target_name: str,
        scope_path: str,
        resolved_inputs: Mapping[str, LinkSourceRef],
        placement_facts: BatchPlacementFacts,
    ) -> AnchorRef | None:
        hint = infer_add_node_anchor_hint(
            target_name=target_name,
            resolved_inputs=resolved_inputs,
            placement_facts=placement_facts,
            current_input_source_ref=self._current_input_source_ref,
            target_has_any_link=self._target_has_any_link,
            uid_to_name=self.name_by_uid,
        )
        if hint is None:
            return None
        return self._materialize_inferred_anchor(scope_path=scope_path, hint=hint)

    def _materialize_inferred_anchor(
        self,
        *,
        scope_path: str,
        hint: InferredAnchorHint,
    ) -> AnchorRef | None:
        if hint.relation == "between" and hint.between_names is not None:
            left = self._resolve_graph_name_soft(hint.between_names[0])
            right = self._resolve_graph_name_soft(hint.between_names[1])
            if left is None or right is None or left.scope_path != scope_path or right.scope_path != scope_path:
                return None
            return AnchorRef(
                relation="between",
                between=(NodeTarget(left.scope_path, left.uid), NodeTarget(right.scope_path, right.uid)),
            )
        if hint.near_name is None:
            return None
        near = self._resolve_graph_name_soft(hint.near_name)
        if near is None or near.scope_path != scope_path:
            return None
        return AnchorRef(relation=hint.relation, near=NodeTarget(near.scope_path, near.uid))

    def _resolve_graph_name_soft(self, name: str) -> _ResolvedGraphName | None:
        node_ref, issues = self._resolve_graph_name(name)
        if issues:
            return None
        return node_ref

    def _graph_name_exists(self, name: str) -> bool:
        node_ref, issues = self._resolve_graph_name(name)
        return node_ref is not None and not issues

    def _current_input_source_ref(self, target_name: str, target_field: str) -> LinkSourceRef | None:
        target = self._resolve_graph_name_soft(target_name)
        if target is None:
            return None
        inputs = target.node.get("inputs")
        if not isinstance(inputs, list):
            return None
        input_slot = _find_named_slot(inputs, target_field)
        if input_slot is None:
            return None
        link_id = input_slot.get("link")
        if not isinstance(link_id, int):
            return None
        raw_link = self.ledger.resolve_link(target.scope_path, link_id)
        if raw_link is None:
            return None
        origin_id, origin_slot = _link_origin(raw_link)
        if origin_id is None:
            return None
        origin_node = self._node_by_id(target.scope_path, origin_id)
        if origin_node is None:
            return None
        origin_uid = str(origin_node.get("properties", {}).get("vibecomfy_uid") or origin_node.get("id"))
        slot_name = _output_slot_name(origin_node, origin_slot, self.schema_provider)
        output_slot: str | int = slot_name if slot_name is not None else origin_slot
        return LinkSourceRef(target.scope_path, origin_uid, output_slot)

    def _target_has_any_link(self, target_name: str) -> bool:
        target = self._resolve_graph_name_soft(target_name)
        if target is None:
            return False
        inputs = target.node.get("inputs")
        if not isinstance(inputs, list):
            return False
        return any(isinstance(slot, Mapping) and isinstance(slot.get("link"), int) for slot in inputs)

    def _node_by_id(self, scope_path: str, node_id: int) -> Mapping[str, Any] | None:
        scope = self.ledger.scopes.get(scope_path)
        if scope is None:
            return None
        nodes = scope.graph.get("nodes")
        if not isinstance(nodes, list):
            return None
        for node in nodes:
            if isinstance(node, Mapping) and node.get("id") == node_id:
                return node
        return None

    @staticmethod
    def _dependency_cause(statement: StatementResult) -> str | None:
        for diagnostic in statement.diagnostics:
            if diagnostic.code == "unbound_graph_name":
                name = str(diagnostic.detail.get("name", "?"))
                return f"Statement depends on graph name {name!r} whose add-node statement did not land."
        return None

    def _resolve_graph_name(
        self,
        name: str,
    ) -> tuple[_ResolvedGraphName | None, list[CompactDiagnostic]]:
        if name.startswith("__"):
            return None, [_diag("dunder_name_not_allowed", f"Graph name {name!r} is not allowed.", severity="error")]
        if name in self.unbound_names:
            return None, [
                _diag(
                    "unbound_graph_name",
                    f"Graph name {name!r} is currently unbound because its add-node statement did not land.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        uid = self.uid_by_name.get(name)
        if uid is None:
            return None, [
                _diag(
                    "unknown_graph_name",
                    f"Unknown graph name {name!r}. Render the session again if the canvas changed.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        matches = [(scope_path, node) for (scope_path, node_uid), node in self.ledger.node_index.items() if node_uid == uid]
        if not matches:
            return None, [
                _diag(
                    "stale_graph_name",
                    f"Graph name {name!r} still points at uid {uid!r}, but that uid is no longer present.",
                    severity="error",
                    detail={"name": name, "uid": uid},
                )
            ]
        if len(matches) > 1:
            return None, [
                _diag(
                    "scope_escape_not_allowed",
                    f"Graph name {name!r} resolves to multiple scopes; explicit scope paths are not allowed in M1.",
                    severity="error",
                    detail={"name": name, "uid": uid, "scope_paths": [scope for scope, _ in matches]},
                )
            ]
        scope_path, node = matches[0]
        class_type = str(node.get("type") or node.get("class_type") or "")
        return _ResolvedGraphName(name=name, uid=uid, scope_path=scope_path, node=node, class_type=class_type), []

    def _resolve_target_field(
        self,
        target: ast.Attribute,
    ) -> tuple[_ResolvedTargetField | None, list[CompactDiagnostic]]:
        node_ref, issues = self._resolve_attribute_base(target, code_unknown="unknown_target_name")
        if issues:
            return None, issues
        assert node_ref is not None
        if target.attr.startswith("__"):
            return None, [_unsafe(target, "dunder_attribute_not_allowed", "Dunder target attributes are not allowed.")]
        field_name = _exec_semantic_slot_name_for_node(
            node_ref.node,
            node_ref.class_type,
            target.attr,
            direction="input",
        )
        schema = schema_for(self.schema_provider, node_ref.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        field_name = _canonical_input_name_for_class(schema_inputs, node_ref.class_type, field_name)
        schema_input = _input_spec_for_field(schema_inputs, field_name)
        raw_input = _find_named_slot(node_ref.node.get("inputs"), field_name)
        widget_value = _widget_value_for_field(node_ref.node, node_ref.class_type, field_name)
        if raw_input is None and schema_input is None and widget_value is _MISSING_WIDGET_VALUE and field_name != "mode":
            return None, [
                _diag(
                    "unknown_target_field",
                    f"{node_ref.class_type} has no editable field or input named {target.attr!r}.",
                    severity="error",
                    detail={"name": node_ref.name, "uid": node_ref.uid, "field": target.attr},
                )
            ]
        socket_type = _normalize_ir_type(
            getattr(schema_input, "type", None) if schema_input is not None else raw_input.get("type") if isinstance(raw_input, Mapping) else None
        )
        if socket_type is None and widget_value is not _MISSING_WIDGET_VALUE:
            socket_type = _socket_type_from_widget_value(widget_value)
        if socket_type is None or socket_type == "UNKNOWN":
            socket_type = _known_core_input_socket_type(node_ref.class_type, field_name) or socket_type
        return _ResolvedTargetField(node=node_ref, field_name=field_name, socket_type=socket_type), []

    def _resolve_rhs_endpoint(
        self,
        value: ast.expr,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        if isinstance(value, ast.Name):
            node_ref, issues = self._resolve_graph_name(value.id)
            if issues:
                return None, issues
            assert node_ref is not None
            return self._resolve_bare_output(node_ref, target=target)
        assert isinstance(value, ast.Attribute)
        node_ref, issues = self._resolve_attribute_base(value, code_unknown="unknown_source_name")
        if issues:
            return None, issues
        assert node_ref is not None
        if value.attr.startswith("__"):
            return None, [_unsafe(value, "dunder_attribute_not_allowed", "Dunder source attributes are not allowed.")]
        return self._resolve_named_output(node_ref, value.attr, target=target)

    def _resolve_attribute_base(
        self,
        attr: ast.Attribute,
        *,
        code_unknown: str,
    ) -> tuple[_ResolvedGraphName | None, list[CompactDiagnostic]]:
        if isinstance(attr.value, ast.Attribute):
            return None, [
                _unsafe(
                    attr,
                    "scope_escape_not_allowed",
                    "Only one attribute hop is allowed; nested attribute scope escapes are not allowed.",
                )
            ]
        if not isinstance(attr.value, ast.Name):
            return None, [_unsafe(attr, "attribute_base_not_name", "Attribute access must start from a rendered graph name.")]
        node_ref, issues = self._resolve_graph_name(attr.value.id)
        if issues and issues[0].code == "unknown_graph_name":
            issues = [
                _diag(
                    code_unknown,
                    issues[0].message,
                    severity=issues[0].severity,
                    detail=issues[0].detail,
                )
            ]
        return node_ref, issues

    def _resolve_named_output(
        self,
        node_ref: _ResolvedGraphName,
        slot_attr: str,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        slot_attr = _exec_semantic_slot_name_for_node(
            node_ref.node,
            node_ref.class_type,
            slot_attr,
            direction="output",
        )
        raw_outputs = _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
        raw_name_map = {item["name"]: item["name"] for item in raw_outputs if item["name"]}
        try:
            raw_slot = slot_attr if slot_attr in raw_name_map else to_raw_name(slot_attr, context=raw_name_map)
        except (KeyError, ValueError):
            raw_slot = None
        if raw_slot is None:
            alias_match = _OUTPUT_ALIAS_RE.fullmatch(slot_attr)
            if alias_match is not None:
                alias_index = int(alias_match.group(1))
                if 0 <= alias_index < len(raw_outputs):
                    if len(raw_outputs) == 1:
                        item = raw_outputs[alias_index]
                        raw_slot = item["name"]
                    else:
                        return None, [
                            _diag(
                                "ambiguous_output_alias",
                                (
                                    f"{node_ref.class_type}.{slot_attr} is a positional output alias, but this node has "
                                    "multiple named outputs; use the exact output slot name instead."
                                ),
                                severity="error",
                                detail={
                                    "name": node_ref.name,
                                    "uid": node_ref.uid,
                                    "slot": slot_attr,
                                    "slot_index": alias_index,
                                    "available_slots": [item["name"] for item in raw_outputs if item["name"]],
                                },
                            )
                        ]
        if raw_slot is None:
            return None, [
                _diag(
                    "unknown_output_slot",
                    f"{node_ref.class_type} has no output named {slot_attr!r}.",
                    severity="error",
                    detail={
                        "name": node_ref.name,
                        "uid": node_ref.uid,
                        "slot": slot_attr,
                        "available_slots": [item["name"] for item in raw_outputs if item["name"]],
                    },
                )
            ]
        for item in raw_outputs:
            if item["name"] == raw_slot:
                return _ResolvedOutputEndpoint(
                    node=node_ref,
                    slot_name=raw_slot,
                    slot_index=item["index"],
                    socket_type=item["type"],
                ), []
        return None, [
            _diag(
                "unknown_output_slot",
                f"{node_ref.class_type} has no output named {raw_slot!r}.",
                severity="error",
                detail={"name": node_ref.name, "uid": node_ref.uid, "slot": raw_slot},
            )
        ]

    def _resolve_bare_output(
        self,
        node_ref: _ResolvedGraphName,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        if target.socket_type is None:
            return None, [
                _diag(
                    "ambiguous_bare_reference",
                    (
                        f"Bare reference {node_ref.name!r} cannot be resolved for "
                        f"{target.node.class_type}.{target.field_name} without a schema-backed target socket type."
                    ),
                    severity="error",
                    detail={"target_name": target.node.name, "target_field": target.field_name, "source_name": node_ref.name},
                )
            ]
        candidates = [
            item
            for item in _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
            if item["type"] is not None and socket_types_compatible(item["type"], target.socket_type)
        ]
        if len(candidates) != 1:
            return None, [
                _diag(
                    "ambiguous_bare_reference",
                    (
                        f"Bare reference {node_ref.name!r} is ambiguous for "
                        f"{target.node.class_type}.{target.field_name}; expected exactly one compatible output."
                    ),
                    severity="error",
                    detail={
                        "target_name": target.node.name,
                        "target_field": target.field_name,
                        "source_name": node_ref.name,
                        "target_socket_type": target.socket_type,
                        "candidate_slots": [item["name"] for item in candidates],
                    },
                )
            ]
        candidate = candidates[0]
        return _ResolvedOutputEndpoint(
            node=node_ref,
            slot_name=candidate["name"],
            slot_index=candidate["index"],
            socket_type=candidate["type"],
        ), []
