from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.templates import load_comfy_metadata  # shared cached loader
from vibecomfy.utils import find_repo_root

from vibecomfy.metadata import (
    MODEL_KEYS,
    PROMPT_KEYS,
    PROMPT_NODE_CLASSES,
    SEED_KEYS,
    STEP_KEYS,
    STEPS_NODE_CLASSES,
)


_UNSUPPORTED = object()
_FILENAME_KWARGS = frozenset({
    "unet_name",
    "vae_name",
    "clip_name",
    "clip_name1",
    "clip_name2",
    "lora_name",
    "ckpt_name",
})


def extract_ready_template_contract(path: str | Path) -> dict[str, Any]:
    """Extract cheap public contract metadata from a ready-template source file.

    The extractor is intentionally static: unsupported dynamic values become
    diagnostics instead of guessed descriptor fields.
    """
    source_path = Path(path)
    diagnostics: list[dict[str, Any]] = []
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError) as exc:
        return {
            "public_inputs": [],
            "public_outputs": [],
            "diagnostics": [
                {
                    "code": "static_contract_parse_failed",
                    "severity": "warning",
                    "message": str(exc),
                }
            ],
            "marker": "unknown",
        }

    assignments = _module_assignments(tree, diagnostics)
    metadata = _dict_or_empty(assignments.get("READY_METADATA"))
    metadata = _metadata_with_static_derivations(metadata, source_path, source)
    requirements = _dict_or_empty(assignments.get("READY_REQUIREMENTS"))
    public_inputs: list[dict[str, Any]] = []
    public_outputs: list[dict[str, Any]] = []

    # ── Derive public_inputs from PUBLIC_INPUTS/InputSpec when present ──
    # Generated templates use either ``PUBLIC_INPUT_METADATA`` (canonical
    # post-revert shape) or the legacy ``PUBLIC_INPUTS`` alias.  Try the new
    # name first and fall back to the old.
    public_inputs_dict = assignments.get("PUBLIC_INPUT_METADATA") or assignments.get("PUBLIC_INPUTS")
    if isinstance(public_inputs_dict, dict):
        for name, spec in public_inputs_dict.items():
            if not isinstance(spec, dict):
                continue
            descriptor: dict[str, Any] = {
                "name": str(name),
                "target": {"node_id": str(spec.get("node", "")), "field": str(spec.get("field", ""))},
                "node_id": str(spec.get("node", "")),
                "field": str(spec.get("field", "")),
                "value": spec.get("default"),
                "type": spec.get("type"),
                "default": spec.get("default"),
                "required": spec.get("required", False),
                "range": spec.get("range"),
                "aliases": spec.get("aliases", []),
                "media_semantics": spec.get("media_semantics"),
                "status": "static",
                "source": "InputSpec",
            }
            if descriptor["default"] is None and descriptor["value"] is not None:
                descriptor["default"] = descriptor["value"]
            public_inputs.append(descriptor)
            for alias in descriptor["aliases"]:
                alias_descriptor = dict(descriptor)
                alias_descriptor["name"] = str(alias)
                alias_descriptor["aliases"] = []
                public_inputs.append(alias_descriptor)

    # ── Derive public_outputs from finalize(..., output_node=...) call ──
    _extract_finalize_outputs(tree, assignments, public_outputs, diagnostics)

    # ── Fallback: walk bind_input/bind_output calls (legacy templates) ──
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if call_name in {"bind_input", "template_input", "register_input"}:
            descriptor = _extract_input_call(node, call_name, diagnostics)
            if descriptor is not None:
                public_inputs.append(descriptor)
        elif call_name in {"bind_output", "template_output", "VibeOutput"}:
            descriptor = _extract_output_call(node, call_name, diagnostics)
            if descriptor is not None:
                public_outputs.append(descriptor)
    public_inputs.extend(_infer_common_input_contracts(tree, public_inputs, assignments))

    # Merge requirements from metadata (ReadyMetadata.build may include them)
    meta_reqs = _dict_or_empty(metadata.get("requirements"))
    merged_models = _list_items(requirements.get("models")) + _list_items(meta_reqs.get("models"))
    reqs_normalized, _warnings = normalize_custom_node_requirements(requirements)
    meta_reqs_normalized, _meta_warnings = normalize_custom_node_requirements(meta_reqs)
    merged_custom_nodes = _list_items(reqs_normalized.get("custom_nodes")) + _list_items(meta_reqs_normalized.get("custom_nodes"))
    merged_custom_node_refs = _list_items(reqs_normalized.get("custom_node_refs")) + _list_items(meta_reqs_normalized.get("custom_node_refs"))

    # Also count MODELS assignment for model_count when it's a dict of ModelAsset calls
    models_dict = assignments.get("MODELS")
    models_from_mod = len(models_dict) if isinstance(models_dict, dict) else 0
    model_count = max(len(merged_models), models_from_mod)
    model_assets = [item for item in merged_models if isinstance(item, dict)]
    if not model_assets and isinstance(models_dict, dict):
        model_assets = [item for item in models_dict.values() if isinstance(item, dict)]

    marker = _template_marker(source)
    summary = {
        "public_inputs": public_inputs,
        "public_outputs": public_outputs,
        "diagnostics": diagnostics,
        "marker": marker,
        "readiness_class": _readiness_class(metadata, marker),
        "artifact_expectations": public_outputs,
        "model_count": model_count,
        "custom_nodes": sorted(set(item for item in merged_custom_nodes if isinstance(item, str))),
        "model_assets": model_assets,
        "hardware": metadata.get("hardware") if isinstance(metadata.get("hardware"), dict) else {},
        "python_env": metadata.get("python_env") if isinstance(metadata.get("python_env"), dict) else {},
        "app_active": _is_app_active(metadata),
        "blocked": _has_marker(metadata, "blocked"),
        "reference": _has_marker(metadata, "reference"),
        "supplemental": _has_marker(metadata, "supplemental"),
    }
    if merged_custom_node_refs:
        summary["custom_node_refs"] = merged_custom_node_refs
    return summary


def _extract_finalize_outputs(
    tree: ast.Module,
    assignments: dict[str, Any],
    public_outputs: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> None:
    """Derive public outputs from ``finalize(..., output_node=..., ...)`` calls."""
    node_assignments = _node_assignment_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if call_name != "finalize" and not call_name.endswith(".finalize"):
            continue
        output_type = _keyword_literal(node, "output_type", diagnostics, "finalize")
        output_node = _keyword_literal(node, "output_node", diagnostics, "finalize")
        if output_node is None:
            output_node = _keyword_node_ref(node, "output_node", node_assignments)
        if output_node is None:
            output_node = _terminal_output_id_for_type(tree, str(output_type)) if output_type else _single_terminal_output_id(tree)
        if not isinstance(output_node, str):
            continue
        output_kind = _keyword_literal(node, "output_kind", diagnostics, "finalize")
        name = _keyword_literal(node, "name", diagnostics, "finalize")
        mime_type = _keyword_literal(node, "mime_type", diagnostics, "finalize")
        artifact_kind = _keyword_literal(node, "artifact_kind", diagnostics, "finalize")
        filename_prefix = _keyword_literal(node, "filename_prefix", diagnostics, "finalize")
        expected_cardinality = _keyword_literal(node, "expected_cardinality", diagnostics, "finalize")

        descriptor: dict[str, Any] = {
            "name": name,
            "node_id": output_node,
            "output_type": output_type,
            "artifact_kind": artifact_kind or output_kind,
            "mime_type": mime_type,
            "filename_prefix": filename_prefix,
            "expected_cardinality": expected_cardinality,
            "status": "static",
            "source": "finalize",
        }
        public_outputs.append(descriptor)


def _node_assignment_ids(tree: ast.Module) -> dict[str, str]:
    ids: dict[str, str] = {}
    runtime_ids = _node_runtime_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        node_id = runtime_ids.get(id(node.value)) or _node_call_source_id(node.value)
        if node_id is not None:
            ids[node.targets[0].id] = node_id
    return ids


def _node_runtime_ids(tree: ast.Module) -> dict[int, str]:
    calls: list[ast.Call] = []
    build_func = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "build"
        ),
        None,
    )
    search_root: ast.AST = build_func if build_func is not None else tree
    for node in ast.walk(search_root):
        if isinstance(node, ast.Call) and _node_call_class_type(node):
            calls.append(node)
    calls.sort(key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0)))
    runtime_ids: dict[int, str] = {}
    numeric_ids: set[int] = set()
    for call in calls:
        explicit = _node_call_source_id(call)
        if explicit is not None:
            runtime_ids[id(call)] = explicit
            if explicit.isdigit():
                numeric_ids.add(int(explicit))
            continue
        next_id = max(numeric_ids, default=0) + 1
        runtime_ids[id(call)] = str(next_id)
        numeric_ids.add(next_id)
    return runtime_ids


def _node_call_source_id(node: ast.Call) -> str | None:
    call_name = _call_name(node.func)
    if call_name == "raw_call" and len(node.args) >= 2:
        value = node.args[1]
        if isinstance(value, ast.Constant):
            return str(value.value)
    if call_name == "node" and len(node.args) >= 3:
        value = node.args[2]
        if isinstance(value, ast.Constant):
            return str(value.value)
    for kw in node.keywords:
        if kw.arg == "_id" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def _keyword_node_ref(node: ast.Call, name: str, node_assignments: dict[str, str]) -> str | None:
    for kw in node.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Name):
            return node_assignments.get(kw.value.id)
    return None


def _single_terminal_output_id(tree: ast.Module) -> str | None:
    candidates: list[str] = []
    runtime_ids = _node_runtime_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        node_id = runtime_ids.get(id(node)) or _node_call_source_id(node)
        if node_id is None:
            continue
        class_type = _node_call_class_type(node)
        if class_type and _is_static_terminal_output_class(class_type):
            candidates.append(node_id)
    return candidates[0] if len(candidates) == 1 else None


def _terminal_output_id_for_type(tree: ast.Module, output_type: str) -> str | None:
    candidates: list[str] = []
    runtime_ids = _node_runtime_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        node_id = runtime_ids.get(id(node)) or _node_call_source_id(node)
        if node_id is None:
            continue
        class_type = _node_call_class_type(node)
        if class_type == output_type:
            candidates.append(node_id)
    return candidates[0] if len(candidates) == 1 else None


def _node_call_class_type(node: ast.Call) -> str | None:
    call_name = _call_name(node.func)
    if call_name == "raw_call" and node.args and isinstance(node.args[0], ast.Constant):
        return str(node.args[0].value)
    if call_name == "node" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        return str(node.args[1].value)
    if call_name and call_name[:1].isupper():
        return call_name.rsplit(".", 1)[-1]
    if call_name.endswith(".node") and node.args and isinstance(node.args[0], ast.Constant):
        return str(node.args[0].value)
    return None


def _is_static_terminal_output_class(class_type: str) -> bool:
    lowered = class_type.lower()
    return class_type in {"SaveImage", "PreviewImage", "SaveVideo", "VHS_VideoCombine", "CreateVideo", "SaveAudio", "SaveAudioMP3", "PreviewAudio"} or lowered.startswith(("save", "preview", "create"))


def compare_public_contracts(
    *,
    static_inputs: list[dict[str, Any]],
    static_outputs: list[dict[str, Any]],
    built_inputs: list[dict[str, Any]],
    built_outputs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compare static and built public contract descriptors by stable keys."""
    static_input_keys = {_input_key(item) for item in static_inputs}
    built_input_keys = {_input_key(item) for item in built_inputs}
    static_output_keys = {_output_key(item) for item in static_outputs}
    built_output_keys = {_output_key(item) for item in built_outputs if item.get("name") is not None}
    return {
        "inputs_only_static": [_input_key_to_dict(key) for key in sorted(static_input_keys - built_input_keys)],
        "inputs_only_built": [_input_key_to_dict(key) for key in sorted(built_input_keys - static_input_keys)],
        "outputs_only_static": [_output_key_to_dict(key) for key in sorted(static_output_keys - built_output_keys)],
        "outputs_only_built": [_output_key_to_dict(key) for key in sorted(built_output_keys - static_output_keys)],
    }


def public_contracts_match(
    *,
    static_inputs: list[dict[str, Any]],
    static_outputs: list[dict[str, Any]],
    built_inputs: list[dict[str, Any]],
    built_outputs: list[dict[str, Any]],
) -> bool:
    comparison = compare_public_contracts(
        static_inputs=static_inputs,
        static_outputs=static_outputs,
        built_inputs=built_inputs,
        built_outputs=built_outputs,
    )
    return all(not values for values in comparison.values())


_KNOWN_TOP_LEVEL_NAMES = frozenset({
    "READY_METADATA",
    "READY_REQUIREMENTS",
    "PUBLIC_INPUTS",
    "PUBLIC_INPUT_METADATA",
    "MODELS",
    "OUTPUT_PREFIX",
    "PRIVATE_KNOBS",
})


def _module_assignments(tree: ast.Module, diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    """Collect module-level assignments for known template top-level names.

    Handles both literal dict assignments and ``ReadyMetadata.build(...)``
    call expressions (which are evaluated into a dict).
    """
    assignments: dict[str, Any] = {}
    # First pass: collect simple ALL_CAPS constant assignments (e.g.
    # ``DEFAULT_SEED = 12345``, ``MODEL_NAME = 'foo.safetensors'``).  Generated
    # templates use these as ``default=`` references inside PUBLIC_INPUT_METADATA
    # InputSpec calls, and ``_literal_value`` resolves ast.Name through the
    # assignments dict.  Without this pass, InputSpec.default references end up
    # as _UNSUPPORTED and the dict-level eval drops the whole entry.
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            if name in _KNOWN_TOP_LEVEL_NAMES:
                continue
            # Heuristic: ALL_CAPS module constants.  Skip class-level definitions.
            if not name.isupper() and "_" not in name:
                continue
            value = _literal_value(node.value, assignments)
            if value is _UNSUPPORTED:
                continue
            assignments[name] = value
    # Two-pass: now collect the named template top-level names that may
    # reference the constants from the first pass.
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in _KNOWN_TOP_LEVEL_NAMES:
                continue
            value = _literal_value(node.value, assignments)
            if value is _UNSUPPORTED:
                diagnostics.append(_diagnostic("static_dynamic_assignment", f"{target.id} contains dynamic values"))
                continue
            assignments[target.id] = value
    return assignments


def _extract_input_call(
    node: ast.Call,
    call_name: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    offset = 1 if call_name in {"bind_input", "template_input"} else 0
    name = _literal_arg_or_keyword(node, offset, "name", diagnostics, call_name)
    node_id = _literal_arg_or_keyword(node, offset + 1, "node_id", diagnostics, call_name)
    field = _literal_arg_or_keyword(node, offset + 2, "field", diagnostics, call_name)
    if not all(isinstance(value, str) for value in (name, node_id, field)):
        return None
    if call_name == "template_input" and field == "widget_0":
        field = "value"
    value = _literal_arg_or_keyword(node, offset + 3, "value", diagnostics, call_name, required=False)
    descriptor = {
        "name": name,
        "target": {"node_id": node_id, "field": field},
        "node_id": node_id,
        "field": field,
        "value": None if value is _UNSUPPORTED else value,
        "type": _keyword_literal(node, "type", diagnostics, call_name),
        "default": _keyword_literal(node, "default", diagnostics, call_name),
        "required": _keyword_literal(node, "required", diagnostics, call_name),
        "range": _keyword_literal(node, "range", diagnostics, call_name),
        "aliases": _keyword_literal(node, "aliases", diagnostics, call_name) or [],
        "media_semantics": _keyword_literal(node, "media_semantics", diagnostics, call_name),
        "status": "static",
        "source": call_name,
    }
    if descriptor["media_semantics"] is None:
        descriptor["media_semantics"] = _keyword_literal(node, "media", diagnostics, call_name)
    if descriptor["default"] is None and value is not _UNSUPPORTED:
        descriptor["default"] = value
    return descriptor


def _extract_output_call(
    node: ast.Call,
    call_name: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    offset = 1 if call_name in {"bind_output", "template_output"} else 0
    node_id = _literal_arg_or_keyword(node, offset, "node_id", diagnostics, call_name)
    if not isinstance(node_id, str):
        return None
    output_type = _literal_arg_or_keyword(node, offset + 1, "output_type", diagnostics, call_name, required=False)
    descriptor = {
        "name": _keyword_literal(node, "name", diagnostics, call_name),
        "node_id": node_id,
        "output_type": _keyword_literal(node, "output_type", diagnostics, call_name)
        or (output_type if output_type is not _UNSUPPORTED else None),
        "artifact_kind": _keyword_literal(node, "artifact_kind", diagnostics, call_name),
        "mime_type": _keyword_literal(node, "mime_type", diagnostics, call_name),
        "filename_prefix": _keyword_literal(node, "filename_prefix", diagnostics, call_name),
        "expected_cardinality": _keyword_literal(node, "expected_cardinality", diagnostics, call_name),
        "status": "static",
        "source": call_name,
    }
    if call_name == "VibeOutput":
        positional_name = _literal_arg_or_keyword(node, offset + 2, "name", diagnostics, call_name, required=False)
        if descriptor["name"] is None and positional_name is not _UNSUPPORTED:
            descriptor["name"] = positional_name
    return descriptor


def _infer_common_input_contracts(
    tree: ast.AST,
    explicit_inputs: list[dict[str, Any]],
    assignments: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    explicit_names = {item.get("name") for item in explicit_inputs if isinstance(item.get("name"), str)}
    inferred: dict[str, dict[str, Any]] = {}
    next_auto_id = 1
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_static_node_call(node)
    ]
    for call in sorted(calls, key=lambda item: (getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
        node_info = _runtime_node_call(call, next_auto_id, assignments)
        if node_info is None:
            continue
        next_auto_id += 1
        class_type = node_info["class_type"]
        node_id = node_info["node_id"]
        for field, value in node_info["inputs"].items():
            input_name = _common_input_name(class_type, field, value)
            if input_name is None or input_name in explicit_names or input_name in inferred:
                continue
            inferred[input_name] = {
                "name": input_name,
                "target": {"node_id": node_id, "field": field},
                "node_id": node_id,
                "field": field,
                "value": value,
                "type": None,
                "default": None,
                "required": False,
                "range": None,
                "aliases": [],
                "media_semantics": None,
                "status": "static",
                "source": "finalize_metadata",
            }
    return [inferred[name] for name in sorted(inferred)]


def _runtime_node_call(node: ast.Call, next_auto_id: int, assignments: dict[str, Any] | None = None) -> dict[str, Any] | None:
    call_name = _call_name(node.func)
    if call_name == "_node":
        class_type = _literal_arg(node, 1, "class_type", [], call_name, required=False)
        node_id = _literal_arg(node, 2, "node_id", [], call_name, required=False)
        keyword_inputs = _literal_keyword_inputs(node, assignments=assignments)
    elif call_name == "ready_node":
        class_type = _literal_arg(node, 1, "class_type", [], call_name, required=False)
        node_id = _keyword_literal(node, "source_id", [], call_name) or str(next_auto_id)
        keyword_inputs = _literal_keyword_inputs(node, excluded={"source_id", "outputs", "extras"}, assignments=assignments)
        extras = _keyword_literal(node, "extras", [], call_name)
        if isinstance(extras, dict):
            keyword_inputs.update({str(key): value for key, value in extras.items()})
    elif call_name == "node":
        # helper: node(wf, 'ClassName', 'node_id', key=value, ...)
        # method: wf.node('ClassName', key=value, ...)
        class_arg_index = 1 if isinstance(node.func, ast.Name) else 0
        node_arg_index = 2 if isinstance(node.func, ast.Name) else -1
        class_type = _literal_arg(node, class_arg_index, "class_type", [], call_name, required=False)
        raw_node_id = (
            _literal_arg(node, node_arg_index, "node_id", [], call_name, required=False)
            if node_arg_index >= 0
            else _UNSUPPORTED
        )
        node_id = str(raw_node_id) if isinstance(raw_node_id, (str, int)) and raw_node_id is not _UNSUPPORTED else str(next_auto_id)
        keyword_inputs = _literal_keyword_inputs(node, assignments=assignments)
    elif _wrapper_class_type(call_name) is not None:
        class_type = _wrapper_class_type(call_name)
        node_id = str(next_auto_id)
        keyword_inputs = _literal_keyword_inputs(node, excluded={"pass_raw"}, assignments=assignments)
    else:
        return None
    if not isinstance(class_type, str) or not isinstance(node_id, str):
        return None
    return {"class_type": class_type, "node_id": node_id, "inputs": keyword_inputs}


def _literal_keyword_inputs(node: ast.Call, *, excluded: set[str] | None = None, assignments: dict[str, Any] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    result: dict[str, Any] = {}
    lookup = assignments or {}
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg in excluded:
            continue
        value = _literal_value(keyword.value, lookup)
        if value is _UNSUPPORTED:
            continue
        value = _coerce_static_node_value(keyword.arg, value)
        result[keyword.arg] = value
    return result


def _coerce_static_node_value(keyword: str, value: Any) -> Any:
    if isinstance(value, dict) and keyword in _FILENAME_KWARGS and isinstance(value.get("filename"), str):
        return value["filename"]
    if isinstance(value, dict) and "default" in value and {"node", "field"}.issubset(value):
        return value.get("default")
    return value


def _is_static_node_call(node: ast.Call) -> bool:
    call_name = _call_name(node.func)
    return call_name in {"_node", "node", "ready_node"} or _wrapper_class_type(call_name) is not None


def _wrapper_class_type(call_name: str) -> str | None:
    if not call_name or call_name in {"InputSpec", "ModelAsset", "ReadyMetadata"}:
        return None
    try:
        from vibecomfy.porting.object_info import get_class
    except ImportError:
        return None
    return call_name if get_class(call_name) is not None else None


def _common_input_name(class_type: str, field: str, value: Any) -> str | None:
    normalized = field.lower()
    if normalized in PROMPT_KEYS and isinstance(value, str) and class_type in PROMPT_NODE_CLASSES:
        return "prompt"
    if normalized in SEED_KEYS and isinstance(value, int) and not isinstance(value, bool):
        return "seed"
    if normalized in STEP_KEYS and isinstance(value, int) and not isinstance(value, bool) and class_type in STEPS_NODE_CLASSES:
        return "steps"
    if normalized in MODEL_KEYS and isinstance(value, str):
        return "model"
    return None


def _literal_arg(
    node: ast.Call,
    index: int,
    field_name: str,
    diagnostics: list[dict[str, Any]],
    call_name: str,
    *,
    required: bool = True,
) -> Any:
    if index >= len(node.args):
        if required:
            diagnostics.append(_diagnostic("static_missing_argument", f"{call_name} missing {field_name!r}"))
        return _UNSUPPORTED
    value = _literal_value(node.args[index], {})
    if value is _UNSUPPORTED and required:
        diagnostics.append(_diagnostic("static_dynamic_value", f"{call_name} has dynamic {field_name!r}"))
    return value


def _literal_arg_or_keyword(
    node: ast.Call,
    index: int,
    field_name: str,
    diagnostics: list[dict[str, Any]],
    call_name: str,
    *,
    required: bool = True,
) -> Any:
    if index < len(node.args):
        return _literal_arg(node, index, field_name, diagnostics, call_name, required=required)
    value = _keyword_literal(node, field_name, diagnostics, call_name)
    if value is None and required:
        diagnostics.append(_diagnostic("static_missing_argument", f"{call_name} missing {field_name!r}"))
        return _UNSUPPORTED
    return value if value is not None else _UNSUPPORTED


def _keyword_literal(
    node: ast.Call,
    name: str,
    diagnostics: list[dict[str, Any]],
    call_name: str,
) -> Any:
    for keyword in node.keywords:
        if keyword.arg != name:
            continue
        value = _literal_value(keyword.value, {})
        if value is _UNSUPPORTED:
            diagnostics.append(_diagnostic("static_dynamic_value", f"{call_name} has dynamic {name!r}"))
            return None
        return value
    return None


def _literal_value(node: ast.AST, assignments: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        values = [_literal_value(item, assignments) for item in node.elts]
        return _UNSUPPORTED if any(value is _UNSUPPORTED for value in values) else values
    if isinstance(node, ast.Tuple):
        values = [_literal_value(item, assignments) for item in node.elts]
        return _UNSUPPORTED if any(value is _UNSUPPORTED for value in values) else tuple(values)
    if isinstance(node, ast.Dict):
        result: dict[Any, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                return _UNSUPPORTED
            key = _literal_value(key_node, assignments)
            value = _literal_value(value_node, assignments)
            if key is _UNSUPPORTED or value is _UNSUPPORTED:
                return _UNSUPPORTED
            result[key] = value
        return result
    if isinstance(node, ast.Name):
        return assignments.get(node.id, _UNSUPPORTED)
    if isinstance(node, ast.Subscript):
        value = _literal_value(node.value, assignments)
        key = _literal_value(node.slice, assignments)
        if isinstance(value, dict) and key is not _UNSUPPORTED:
            return value.get(key, _UNSUPPORTED)
    if isinstance(node, ast.Attribute):
        obj = _literal_value(node.value, assignments)
        if isinstance(obj, dict) and node.attr in obj:
            return obj[node.attr]
        return _UNSUPPORTED
    if isinstance(node, ast.Call):
        return _evaluate_call(node, assignments)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return _UNSUPPORTED


def _evaluate_call(node: ast.Call, assignments: dict[str, Any]) -> Any:
    """Evaluate a function call AST node to a dict for known builders.

    Handles ``ReadyMetadata.build(...)``, ``InputSpec(...)``, and
    ``ModelAsset(...)``.  Returns ``_UNSUPPORTED`` for other calls.
    """
    func_name = _call_qualified_name(node.func)
    if func_name in ("ReadyMetadata.build", "ReadyMetadata.build"):
        return _eval_ready_metadata_build(node, assignments)
    if func_name in ("InputSpec",):
        return _eval_input_spec_call(node, assignments)
    if func_name in ("ModelAsset",):
        return _eval_model_asset_call(node, assignments)
    return _UNSUPPORTED


def _eval_ready_metadata_build(node: ast.Call, assignments: dict[str, Any]) -> dict[str, Any]:
    """Evaluate ``ReadyMetadata.build(**kwargs)`` into a dict of keyword values."""
    result: dict[str, Any] = {}
    for kw in node.keywords:
        if kw.arg is None:
            continue
        value = _literal_value(kw.value, assignments)
        if value is _UNSUPPORTED:
            continue
        result[kw.arg] = value
    template_id = result.get("template_id")
    if isinstance(template_id, str):
        ready_template = _category_qualified_template_id(template_id)
        result.setdefault("ready_template", ready_template)
        result.setdefault("workflow_template", ready_template.rsplit("/", 1)[-1])
    models = result.get("models")
    if isinstance(models, dict):
        result.setdefault("model_assets", [item for item in models.values() if isinstance(item, dict)])
    provenance = result.get("provenance")
    if isinstance(provenance, dict):
        for key, value in provenance.items():
            result.setdefault(str(key), value)
    return result


def _eval_input_spec_call(node: ast.Call, assignments: dict[str, Any]) -> dict[str, Any]:
    """Evaluate ``InputSpec(node=..., field=..., ...)`` into a dict."""
    result: dict[str, Any] = {}
    # Positional args: node, field, default, type
    arg_names = ("node", "field", "default", "type")
    for i, value_node in enumerate(node.args):
        if i < len(arg_names):
            value = _literal_value(value_node, assignments)
            if value is not _UNSUPPORTED:
                result[arg_names[i]] = value
    for kw in node.keywords:
        if kw.arg is None:
            continue
        value = _literal_value(kw.value, assignments)
        if value is not _UNSUPPORTED:
            result[kw.arg] = list(value) if kw.arg == "aliases" and isinstance(value, tuple) else value
    return result


def _eval_model_asset_call(node: ast.Call, assignments: dict[str, Any]) -> dict[str, Any]:
    """Evaluate ``ModelAsset(filename=..., url=..., subdir=..., ...)`` into a dict."""
    result: dict[str, Any] = {}
    # Positional args: filename, url, subdir
    arg_names = ("filename", "url", "subdir")
    for i, value_node in enumerate(node.args):
        if i < len(arg_names):
            value = _literal_value(value_node, assignments)
            if value is not _UNSUPPORTED:
                result[arg_names[i]] = value
    for kw in node.keywords:
        if kw.arg is None:
            continue
        value = _literal_value(kw.value, assignments)
        if value is not _UNSUPPORTED:
            result[kw.arg] = value
    # Map to canonical model asset shape
    filename_val = result.get("filename", result.get("name", ""))
    if not filename_val and isinstance(result.get("url"), str):
        filename_val = Path(urlsplit(result["url"]).path).name
    return {
        "name": filename_val,
        "filename": filename_val,
        "url": result.get("url", ""),
        "subdir": result.get("subdir", ""),
        **({"target_path": result["target_path"]} if isinstance(result.get("target_path"), str) else {}),
        **({"sha256": result["sha256"]} if isinstance(result.get("sha256"), str) else {}),
        **({"hf_revision": result["hf_revision"]} if isinstance(result.get("hf_revision"), str) else {}),
        **({"size_bytes": result["size_bytes"]} if isinstance(result.get("size_bytes"), int) else {}),
        **({"gated": True} if result.get("gated") is True else {}),
    }


def _call_qualified_name(func: ast.AST) -> str:
    """Return the dotted name of a call target (e.g. ``ReadyMetadata.build``)."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = _call_qualified_name(func.value)
        return f"{prefix}.{func.attr}" if prefix else func.attr
    return ""


def _input_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("name") or ""), str(item.get("node_id") or ""), str(item.get("field") or ""))


def _output_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("name") or ""), str(item.get("node_id") or ""), str(item.get("output_type") or ""))


def _input_key_to_dict(key: tuple[str, str, str]) -> dict[str, str]:
    name, node_id, field = key
    return {"name": name, "node_id": node_id, "field": field}


def _output_key_to_dict(key: tuple[str, str, str]) -> dict[str, str]:
    name, node_id, output_type = key
    return {"name": name, "node_id": node_id, "output_type": output_type}


def _metadata_with_static_derivations(metadata: dict[str, Any], path: Path, source: str) -> dict[str, Any]:
    if not metadata:
        return metadata
    out = dict(metadata)
    ready_template = out.get("ready_template")
    if not isinstance(ready_template, str) or not ready_template:
        template_id = out.get("template_id")
        if isinstance(template_id, str) and template_id:
            ready_template = _category_qualified_template_id(template_id, path)
        else:
            ready_template = _template_id_from_path(path)
        out["ready_template"] = ready_template
    out.setdefault("workflow_template", str(ready_template).rsplit("/", 1)[-1])
    row = _coverage_manifest_row(str(ready_template))
    if "coverage_tier" not in out and isinstance(row.get("coverage_tier"), str):
        out["coverage_tier"] = row["coverage_tier"]
    if "source_workflow" not in out:
        source_workflow = _source_workflow_from_static(out, row, source)
        if source_workflow:
            out["source_workflow"] = source_workflow
    out.setdefault("vibecomfy_version", _project_version())
    out.setdefault("comfy_core", load_comfy_metadata())
    return out


def _repo_root() -> Path:
    return find_repo_root()


def _template_id_from_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root() / "ready_templates").with_suffix("").as_posix()
    except ValueError:
        return path.stem


def _category_qualified_template_id(template_id: str, path: Path | None = None) -> str:
    if "/" in template_id:
        return template_id
    if path is not None:
        try:
            rel = path.resolve().relative_to(_repo_root() / "ready_templates")
            if len(rel.parts) > 1:
                return f"{rel.parts[0]}/{template_id}"
        except ValueError:
            pass
    return template_id


def _coverage_manifest_row(template_id: str) -> dict[str, Any]:
    path = _repo_root() / "workflow_corpus" / "manifests" / "coverage.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = data.get("workflows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return {}
    short_id = template_id.rsplit("/", 1)[-1]
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidates = {str(row.get("ready_template") or ""), str(row.get("template_id") or ""), str(row.get("id") or "")}
        if isinstance(row.get("media"), str) and isinstance(row.get("id"), str):
            candidates.add(f"{row['media']}/{row['id']}")
        if template_id in candidates or short_id in candidates:
            return dict(row)
    return {}


def _source_workflow_from_static(metadata: dict[str, Any], row: dict[str, Any], source: str) -> str | None:
    provenance = metadata.get("provenance")
    if isinstance(provenance, dict) and isinstance(provenance.get("source_workflow"), str):
        return provenance["source_workflow"]
    for key in ("path", "source_workflow", "workflow_path"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    match = re.search(r"^\s*#\s*ported from\s+(.+?)\s*$", source, flags=re.MULTILINE)
    if match:
        return match.group(1).split(" (", 1)[0].strip()
    match = re.search(r"^\s*Source:\s*(.+?)\s*$", source, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _project_version() -> str:
    try:
        data = tomllib.loads((_repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "0"
    project = data.get("project") if isinstance(data, dict) else None
    version = project.get("version") if isinstance(project, dict) else None
    return str(version) if version else "0"


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _diagnostic(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": "warning", "message": message}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _template_marker(source: str) -> str:
    header = "\n".join(source.splitlines()[:5])
    if "# vibecomfy: manual" in header:
        return "manual"
    if "# vibecomfy: generated" in header:
        return "generated"
    if "# vibecomfy: narrative" in header:
        return "generated"
    return "unmarked"


def _readiness_class(metadata: dict[str, Any], marker: str) -> str:
    if _has_marker(metadata, "blocked"):
        return "blocked"
    if metadata.get("ready_template"):
        return "ready"
    return marker


def _has_marker(metadata: dict[str, Any], marker: str) -> bool:
    markers = metadata.get("markers")
    if isinstance(markers, list) and marker in markers:
        return True
    return metadata.get(marker) is True


def _is_app_active(metadata: dict[str, Any]) -> bool:
    if metadata.get("app_active") is True:
        return True
    return metadata.get("coverage_tier") == "required"
