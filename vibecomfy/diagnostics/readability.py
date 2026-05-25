"""Readability diagnostics for generated ready-template source code.

First-wave checks detect patterns in emitted Python that signal
opportunities for cleanup or emit-quality regressions.  All five emit at
severity ``warning`` on the first ship so they surface in ``doctor`` and
``port check --strict-ready-template`` without blocking flows.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_UUID_CLASS_TYPE_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_MODEL_FILENAME_RE = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:safetensors|ckpt|pt|pth|onnx|bin|gguf)",
    re.IGNORECASE,
)

_MODEL_INPUT_KEY_HINTS = frozenset(
    {
        "unet_name",
        "clip_name",
        "vae_name",
        "lora_name",
        "model_name",
        "model",
        "checkpoint",
        "ckpt_name",
    }
)

_WIDGET_RE = re.compile(r"widget_(\d+)\s*=")

# Known code names for the static catalog
_KNOWN_CODES: tuple[str, ...] = (
    "avoidable_positional_output",
    "schema_backed_widget_alias_not_resolved",
    "uuid_class_type_in_ready_template",
    "model_filename_not_declared",
    "generated_template_has_local_node_helper",
)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadabilityDiagnostic:
    """A single readability finding in a generated ready template."""

    code: str
    severity: str  # 'warning' | 'error'
    node_id: str | None = None
    field: str | None = None
    message: str = ""
    next_action: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.field is not None:
            payload["field"] = self.field
        if self.next_action is not None:
            payload["next_action"] = self.next_action
        return payload


@dataclass(frozen=True)
class ReadabilitySubcheck:
    """Named subcheck aggregating zero or more ``ReadabilityDiagnostic`` items."""

    name: str
    ok: bool
    findings: list[ReadabilityDiagnostic] = field(default_factory=list)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "findings": [f.to_json() for f in self.findings],
        }


@dataclass(frozen=True)
class ReadabilityReport:
    """Aggregate readability report for a single ready-template source file."""

    workflow: str
    ok: bool
    subchecks: list[ReadabilitySubcheck]
    known_codes: tuple[str, ...] = _KNOWN_CODES

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "ok": self.ok,
            "known_codes": list(self.known_codes),
            "subchecks": [sc.to_json() for sc in self.subchecks],
        }


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _check_avoidable_positional_output(source: str) -> list[ReadabilityDiagnostic]:
    """Flag ``wf.finalize(...)`` calls that omit ``output_node=``."""
    diagnostics: list[ReadabilityDiagnostic] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return diagnostics

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match ``wf.finalize(...)``
        if not _is_wf_finalize_call(node):
            continue
        # Check if ``output_node`` is a keyword argument
        has_output_node = any(
            kw.arg == "output_node" for kw in node.keywords if kw.arg is not None
        )
        if not has_output_node:
            diagnostics.append(
                ReadabilityDiagnostic(
                    code="avoidable_positional_output",
                    severity="warning",
                    node_id=None,
                    field="output_node",
                    message=(
                        "wf.finalize() does not specify output_node; the output node "
                        "is resolved by convention (last save node). Consider adding "
                        "an explicit output_node= kwarg for readability."
                    ),
                    next_action="Add output_node=<var> to the wf.finalize() call.",
                )
            )
    return diagnostics


def _check_schema_backed_widget_alias_not_resolved(
    source: str,
) -> list[ReadabilityDiagnostic]:
    """Flag ``widget_N=`` patterns that the schema could resolve to a canonical name."""
    diagnostics: list[ReadabilityDiagnostic] = []
    for match in _WIDGET_RE.finditer(source):
        idx = match.group(1)
        diagnostics.append(
            ReadabilityDiagnostic(
                code="schema_backed_widget_alias_not_resolved",
                severity="warning",
                node_id=None,
                field=f"widget_{idx}",
                message=(
                    f"Widget alias widget_{idx} used in template source. "
                    "If the schema provides a canonical name for this position, "
                    "the emitter should resolve it."
                ),
                next_action=(
                    "Check that the schema-backed widget alias resolver covers "
                    "this class_type+position pair."
                ),
            )
        )
    return diagnostics


def _check_uuid_class_type_in_ready_template(
    source: str,
) -> list[ReadabilityDiagnostic]:
    """Flag UUID class-type references that represent opaque subgraph nodes."""
    diagnostics: list[ReadabilityDiagnostic] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return diagnostics

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # ``raw_call('ClassName', ...)`` or ``_node(wf, 'ClassName', ...)``
        class_type = _extract_class_type_from_call(node)
        if class_type is not None and _UUID_CLASS_TYPE_RE.match(class_type):
            diagnostics.append(
                ReadabilityDiagnostic(
                    code="uuid_class_type_in_ready_template",
                    severity="warning",
                    node_id=class_type,
                    field=None,
                    message=(
                        f"Opaque component {class_type!r} references a UUID class type. "
                        "Consider materializing it as a named subgraph function."
                    ),
                    next_action=(
                        "Replace or wrap the raw UUID call with a materialized "
                        "subgraph function."
                    ),
                )
            )
    return diagnostics


def _check_model_filename_not_declared(
    source: str,
) -> list[ReadabilityDiagnostic]:
    """Flag model-filename constants that are not declared in the MODELS dict."""
    diagnostics: list[ReadabilityDiagnostic] = []

    # -- find MODEL_FILENAME-like assignments ---------------------------------
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return diagnostics

    # Collect explicit model-filename string constants assigned at module level
    declared_filenames: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, str) and _MODEL_FILENAME_RE.match(
                        node.value.value
                    ):
                        declared_filenames.add(node.value.value)

    # Collect filenames present in the MODELS dict
    models_filenames: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MODELS":
                    if isinstance(node.value, ast.Dict):
                        models_filenames.update(
                            _collect_model_filenames_from_dict(node.value)
                        )

    for fn in sorted(declared_filenames - models_filenames):
        diagnostics.append(
            ReadabilityDiagnostic(
                code="model_filename_not_declared",
                severity="warning",
                node_id=None,
                field=fn,
                message=(
                    f"Model filename {fn!r} is defined as a constant "
                    "but not declared in the MODELS dict."
                ),
                next_action=(
                    f"Add {fn!r} to the MODELS dict so model-resolution "
                    "tooling can track it."
                ),
            )
        )
    return diagnostics


def _check_generated_template_has_local_node_helper(
    source: str,
) -> list[ReadabilityDiagnostic]:
    """Flag subgraph/helper functions defined alongside ``build()``."""
    diagnostics: list[ReadabilityDiagnostic] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return diagnostics

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "build":
            diagnostics.append(
                ReadabilityDiagnostic(
                    code="generated_template_has_local_node_helper",
                    severity="warning",
                    node_id=node.name,
                    field=None,
                    message=(
                        f"Local helper function {node.name!r} is defined in the "
                        "generated template. Consider whether it can be extracted "
                        "to a shared node module."
                    ),
                    next_action=None,
                )
            )
    return diagnostics


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def run_readability_checks(source: str, *, workflow_id: str = "") -> ReadabilityReport:
    """Run all five first-wave readability checks and return a report.

    Checks are ordered deterministically (by code name).  Within each
    subcheck findings are sorted by ``code``, then ``node_id``, then
    ``field`` for snapshot stability.
    """
    checks: list[tuple[str, list[ReadabilityDiagnostic]]] = [
        ("avoidable_positional_output", _check_avoidable_positional_output(source)),
        (
            "schema_backed_widget_alias_not_resolved",
            _check_schema_backed_widget_alias_not_resolved(source),
        ),
        (
            "uuid_class_type_in_ready_template",
            _check_uuid_class_type_in_ready_template(source),
        ),
        ("model_filename_not_declared", _check_model_filename_not_declared(source)),
        (
            "generated_template_has_local_node_helper",
            _check_generated_template_has_local_node_helper(source),
        ),
    ]

    subchecks: list[ReadabilitySubcheck] = []
    for name, findings in checks:
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                f.code or "",
                f.node_id or "",
                f.field or "",
            ),
        )
        subchecks.append(
            ReadabilitySubcheck(
                name=name,
                ok=len(sorted_findings) == 0,
                findings=sorted_findings,
            )
        )

    return ReadabilityReport(
        workflow=workflow_id,
        ok=all(sc.ok for sc in subchecks),
        subchecks=subchecks,
    )


def run_readability_checks_for_file(
    path: str | Path,
    *,
    workflow_id: str = "",
) -> ReadabilityReport:
    """Convenience: read *path*, derive *workflow_id* if empty, and run checks."""
    p = Path(path)
    source = p.read_text(encoding="utf-8")
    wid = workflow_id or p.stem
    return run_readability_checks(source, workflow_id=wid)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _is_wf_finalize_call(call: ast.Call) -> bool:
    """True when *call* looks like ``wf.finalize(...)``."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return (
            isinstance(func.value, ast.Name)
            and func.value.id == "wf"
            and func.attr == "finalize"
        )
    return False


def _extract_class_type_from_call(call: ast.Call) -> str | None:
    """Extract the class-type string literal from a ``raw_call('Foo', ...)`` or
    ``_node(wf, 'Foo', ...)`` call."""
    func = call.func
    # raw_call('ClassName', ...)
    if isinstance(func, ast.Name) and func.id == "raw_call":
        if call.args and isinstance(call.args[0], ast.Constant):
            if isinstance(call.args[0].value, str):
                return call.args[0].value
    # _node(wf, 'ClassName', ...)
    if isinstance(func, ast.Name) and func.id == "_node":
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            if isinstance(call.args[1].value, str):
                return call.args[1].value
    return None


def _looks_like_model_filename(value: str) -> bool:
    """Best-effort heuristic for model filenames."""
    return bool(_MODEL_FILENAME_RE.match(value))


def _collect_model_filenames_from_dict(dict_node: ast.Dict) -> set[str]:
    """Walk a ``MODELS`` dict AST and return any string values that look like
    model filenames."""
    filenames: set[str] = set()
    for node in ast.walk(dict_node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _MODEL_FILENAME_RE.search(node.value):
                # Extract just the filename portion from URLs/paths
                val = node.value
                # If it's a URL, take the last path segment
                if "/" in val:
                    val = val.rsplit("/", 1)[-1]
                filenames.add(val)
    return filenames


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = [
    "ReadabilityDiagnostic",
    "ReadabilityReport",
    "ReadabilitySubcheck",
    "run_readability_checks",
    "run_readability_checks_for_file",
]
