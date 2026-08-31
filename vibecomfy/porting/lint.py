"""Ready-template linting helper.

Provides :func:`lint_ready_template` which scans a ready-template source
for 8 convention rules using AST and regex scanning.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LintDiagnostic:
    """One lint finding."""

    severity: str  # "error", "warning", "info"
    path: str
    line: int
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


# Pattern for variable names like cliptextencode_2 (lowercase + integer suffix)
_INTEGER_SUFFIX_RE = re.compile(r"^[a-z]+[a-z0-9]*_\d+$")

# Pattern for n_UUID_ variable names
_N_UUID_RE = re.compile(r"^n_[0-9a-fA-F]{8}[_-]")

# Pattern for _set_id_map(...) calls
_SET_ID_MAP_RE = re.compile(r"_set_id_map\s*\(")

# Pattern for wf.finalize(...) calls
_FINALIZE_RE = re.compile(r"wf\.finalize\s*\(")

# Pattern for raw_call detection
_RAW_CALL_RE = re.compile(r"raw_call\s*\(")


def lint_ready_template(source_text: str, path: str) -> list[LintDiagnostic]:
    """Scan *source_text* for convention violations.

    Returns a list of :class:`LintDiagnostic` instances.
    """
    diagnostics: list[LintDiagnostic] = []
    lines = source_text.splitlines()

    # Rule 1: Integer-suffix variable names (info)
    diagnostics.extend(_check_integer_suffix_names(source_text, path, lines))

    # Rule 2: n_UUID_ variable names (warning)
    diagnostics.extend(_check_n_uuid_names(source_text, path, lines))

    # Rule 3: _set_id_map() calls (warning)
    diagnostics.extend(_check_set_id_map(source_text, path, lines))

    # Rule 4: Duplicate PUBLIC_INPUTS entries (warning)
    diagnostics.extend(_check_duplicate_public_inputs(source_text, path, lines))

    # Rule 5: wf.finalize() with derivable kwargs (info)
    diagnostics.extend(_check_finalize_kwargs(source_text, path, lines))

    # Rule 6: Unwrapped raw_call to typed-wrapper class (error)
    diagnostics.extend(_check_unwrapped_raw_call(source_text, path, lines))

    # Rule 7: _outputs= matching schema names (info)
    diagnostics.extend(_check_outputs_matching_schema(source_text, path, lines))

    # Rule 8: Custom node classes without custom_node_packs provenance (warning)
    diagnostics.extend(_check_missing_custom_node_packs(source_text, path, lines))

    # Rule 9: raw_call for helper/primitive class types (error)
    diagnostics.extend(_check_helper_raw_call(source_text, path, lines))

    return diagnostics


# -- Rule implementations ----------------------------------------------------


def _check_integer_suffix_names(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag variable names matching [a-z]+_\\d+$ pattern."""
    diags: list[LintDiagnostic] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return diags

    seen_vars: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if _INTEGER_SUFFIX_RE.match(node.id) and not node.id.startswith("_"):
                if node.id not in seen_vars:
                    seen_vars.add(node.id)
                    diags.append(
                        LintDiagnostic(
                            severity="info",
                            path=path,
                            line=node.lineno,
                            code="integer_suffix_variable",
                            message=(
                                f"Variable '{node.id}' uses integer suffix — "
                                "consider role-based name"
                            ),
                            detail={"variable": node.id},
                        )
                    )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if _INTEGER_SUFFIX_RE.match(target.id) and not target.id.startswith("_"):
                        if target.id not in seen_vars:
                            seen_vars.add(target.id)
                            diags.append(
                                LintDiagnostic(
                                    severity="info",
                                    path=path,
                                    line=target.lineno,
                                    code="integer_suffix_variable",
                                    message=(
                                        f"Variable '{target.id}' uses integer suffix — "
                                        "consider role-based name"
                                    ),
                                    detail={"variable": target.id},
                                )
                            )

    return diags


def _check_n_uuid_names(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag n_UUID_ variable name patterns."""
    diags: list[LintDiagnostic] = []
    for lineno, line in enumerate(lines, start=1):
        for match in _N_UUID_RE.finditer(line):
            diags.append(
                LintDiagnostic(
                    severity="warning",
                    path=path,
                    line=lineno,
                    code="uuid_variable_name",
                    message=(
                        f"Variable name '{match.group()}' matches UUID pattern — "
                        "consider human-readable name"
                    ),
                    detail={"pattern": match.group()},
                )
            )
    return diags


def _check_set_id_map(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag _set_id_map(...) calls in build()."""
    diags: list[LintDiagnostic] = []
    for lineno, line in enumerate(lines, start=1):
        if _SET_ID_MAP_RE.search(line):
            diags.append(
                LintDiagnostic(
                    severity="warning",
                    path=path,
                    line=lineno,
                    code="set_id_map_call",
                    message=(
                        "_set_id_map() call present; v2.6.2 will derive "
                        "UUID mappings at runtime"
                    ),
                    detail={"line": line.strip()},
                )
            )
    return diags


def _check_duplicate_public_inputs(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag duplicate PUBLIC_INPUTS entries with same node+field."""
    diags: list[LintDiagnostic] = []
    # Parse bind_input calls to find duplicates
    bind_calls = re.finditer(
        r"bind_input\s*\(\s*wf\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
        source,
    )
    seen: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for match in bind_calls:
        input_name = match.group(1)
        node_id = match.group(2)
        field = match.group(3)
        key = (node_id, field)

        # Approximate line number
        line_no = source[: match.start()].count("\n") + 1
        seen[key].append((input_name, line_no))

    for (node_id, field), entries in seen.items():
        if len(entries) > 1:
            names = [e[0] for e in entries]
            diags.append(
                LintDiagnostic(
                    severity="warning",
                    path=path,
                    line=min(e[1] for e in entries),
                    code="duplicate_public_input",
                    message=(
                        f"Duplicate PUBLIC_INPUTS — {names[0]!r} and {names[1]!r} "
                        f"bind same (node={node_id!r}, field={field!r})"
                    ),
                    detail={
                        "node_id": node_id,
                        "field": field,
                        "input_names": names,
                    },
                )
            )

    return diags


def _check_finalize_kwargs(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag wf.finalize() calls with derivable kwargs."""
    diags: list[LintDiagnostic] = []
    for match in _FINALIZE_RE.finditer(source):
        line_no = source[: match.start()].count("\n") + 1
        line = lines[line_no - 1] if line_no <= len(lines) else ""

        # Check if the call has any arguments beyond the closing paren
        call_text = source[match.start() :]
        paren_depth = 0
        has_args = False
        for ch in call_text:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    break
            elif paren_depth == 1 and ch not in (" ", "\n", "\t"):
                has_args = True
                break

        if has_args:
            # Count the kwargs
            args_match = re.match(
                r"finalize\s*\(([^)]+)\)",
                call_text[: call_text.index(")") + 1] if ")" in call_text else call_text,
            )
            if args_match:
                args_text = args_match.group(1)
                arg_count = len([a for a in args_text.split(",") if a.strip()])
            else:
                arg_count = 1

            diags.append(
                LintDiagnostic(
                    severity="info",
                    path=path,
                    line=line_no,
                    code="derivable_finalize_kwargs",
                    message=(
                        f"wf.finalize() has {arg_count} derivable kwarg(s); "
                        "consider omitting if they can be inferred"
                    ),
                    detail={"line": line.strip(), "arg_count": arg_count},
                )
            )

    return diags


def _check_unwrapped_raw_call(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag unwrapped raw_call for classes that DO have typed wrappers."""
    diags: list[LintDiagnostic] = []
    # Find raw_call invocations
    for match in _RAW_CALL_RE.finditer(source):
        line_no = source[: match.start()].count("\n") + 1
        line = lines[line_no - 1] if line_no <= len(lines) else ""

        # Extract the class_type argument
        call_text = source[match.start() :]
        args_match = re.search(r"raw_call\s*\(\s*wf\s*,\s*['\"]([^'\"]+)['\"]", call_text)
        if args_match:
            class_type = args_match.group(1)
            if _class_has_typed_wrapper(class_type):
                diags.append(
                    LintDiagnostic(
                        severity="error",
                        path=path,
                        line=line_no,
                        code="unwrapped_raw_call",
                        message=(
                            f"raw_call() for class '{class_type}' which has "
                            "a typed wrapper — use the typed block function instead"
                        ),
                        detail={"class_type": class_type},
                    )
                )

    return diags


def _check_outputs_matching_schema(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag _outputs= tuples that match schema output names (info)."""
    diags: list[LintDiagnostic] = []
    # Find _outputs=(...) patterns
    for match in re.finditer(r"_outputs\s*=\s*\(([^)]*)\)", source):
        line_no = source[: match.start()].count("\n") + 1
        outputs_text = match.group(1)
        output_names = [
            name.strip().strip("'\"")
            for name in outputs_text.split(",")
            if name.strip()
        ]

        if output_names:
            diags.append(
                LintDiagnostic(
                    severity="info",
                    path=path,
                    line=line_no,
                    code="outputs_tuple_matches_schema",
                    message=(
                        f"_outputs=({', '.join(output_names)}) matches schema "
                        "output names — verify they are intentional"
                    ),
                    detail={"output_names": output_names},
                )
            )

    return diags


def _check_missing_custom_node_packs(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag custom node classes used without custom_node_packs provenance."""
    diags: list[LintDiagnostic] = []

    # Find class_type references
    class_refs = re.findall(r"class_type\s*=\s*['\"]([^'\"]+)['\"]", source)
    # Find custom_nodes declarations
    has_custom_nodes = bool(re.search(
        r"['\"]custom_nodes['\"]\s*:\s*\[",
        source,
    ))

    # Known core classes
    core_classes = {
        "CLIPLoader", "CLIPTextEncode", "CLIPVisionEncode", "CLIPVisionLoader",
        "CreateVideo", "CheckpointLoaderSimple", "DualCLIPLoader",
        "ImageScaleBy", "KSampler", "KSamplerSelect", "LoadImage",
        "LoraLoaderModelOnly", "ManualSigmas", "ModelSamplingSD3",
        "PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt",
        "PrimitiveNode", "PrimitiveString", "PrimitiveStringMultiline",
        "RandomNoise", "SamplerCustomAdvanced", "SaveImage", "SaveVideo",
        "UNETLoader", "VAEDecode", "VAEDecodeTiled", "VAELoader",
        "WanImageToVideo", "CFGGuider",
    }

    for ct in class_refs:
        if ct in core_classes or _is_uuid(ct):
            continue
        if not has_custom_nodes:
            # Find the line number
            for lineno, line in enumerate(lines, start=1):
                if f"class_type = '{ct}'" in line or f'class_type = "{ct}"' in line:
                    diags.append(
                        LintDiagnostic(
                            severity="warning",
                            path=path,
                            line=lineno,
                            code="missing_custom_node_packs",
                            message=(
                                f"Custom node class '{ct}' used without "
                                "custom_node_packs provenance in READY_REQUIREMENTS"
                            ),
                            detail={"class_type": ct},
                        )
                    )
                    break

    return diags


# -- Rule 9: helper raw_call detection ---------------------------------------

# Classes that must never appear as the first argument to raw_call() in a
# ready template.  These are resolver-stripped helpers and primitives whose
# presence in emitted source indicates a resolver bug or an unconverted template.
_HELPER_RAW_CALL_CLASSES: frozenset[str] = frozenset(
    {
        "GetNode",
        "SetNode",
        "Reroute",
        "PrimitiveNode",
        "PrimitiveBoolean",
        "PrimitiveInt",
        "PrimitiveFloat",
        "PrimitiveString",
        "PrimitiveStringMultiline",
    }
)


def _check_helper_raw_call(
    source: str, path: str, lines: list[str]
) -> list[LintDiagnostic]:
    """Flag raw_call(...) for resolver-stripped helper/primitive class types."""
    diags: list[LintDiagnostic] = []
    for match in _RAW_CALL_RE.finditer(source):
        line_no = source[: match.start()].count("\n") + 1
        call_text = source[match.start():]
        args_match = re.search(
            r"raw_call\s*\(\s*wf\s*,\s*['\"]([^'\"]+)['\"]", call_text
        )
        if not args_match:
            continue
        class_type = args_match.group(1)
        if class_type not in _HELPER_RAW_CALL_CLASSES:
            continue
        diags.append(
            LintDiagnostic(
                severity="error",
                path=path,
                line=line_no,
                code="helper_raw_call",
                message=(
                    f"raw_call() for helper/primitive class '{class_type}'; "
                    f"these should be eliminated by the resolver before emission"
                ),
                detail={"class_type": class_type},
            )
        )
    return diags


# -- helpers -----------------------------------------------------------------

def _is_uuid(s: str) -> bool:
    """Check if *s* looks like a UUID."""
    return bool(
        re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            s,
        )
    )


# Cache for typed wrapper classes
_TYPED_WRAPPER_CLASSES: frozenset[str] | None = None


def _class_has_typed_wrapper(class_type: str) -> bool:
    """Check if *class_type* has a typed wrapper block function."""
    global _TYPED_WRAPPER_CLASSES
    if _TYPED_WRAPPER_CLASSES is None:
        _TYPED_WRAPPER_CLASSES = _build_typed_wrapper_set()
    return class_type in _TYPED_WRAPPER_CLASSES


def _build_typed_wrapper_set() -> frozenset[str]:
    """Build set of class_types that have typed wrapper blocks."""
    try:
        from vibecomfy.blocks._wrapper_discovery import (
            extract_typed_wrapper_class_types,
            import_block_submodules,
        )

        import_block_submodules()
        from vibecomfy.blocks import registered_blocks
        blocks = dict(registered_blocks())
        return extract_typed_wrapper_class_types(blocks)
    except Exception:
        return frozenset()


__all__ = [
    "LintDiagnostic",
    "lint_ready_template",
]
