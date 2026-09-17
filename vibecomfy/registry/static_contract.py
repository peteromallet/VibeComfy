from __future__ import annotations

import ast
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
from vibecomfy.contracts.runtime import RuntimeDependencyError, RuntimeRequirements
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
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


def extract_ready_template_contract(
    path: str | Path,
    *,
    wrapper_class_types: Mapping[str, str] | None = None,
    include_locations: bool = False,
) -> dict[str, Any]:
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
    wrappers = (
        dict(wrapper_class_types)
        if wrapper_class_types is not None
        else resolve_ready_wrapper_class_types_from_trees((tree,))
    )
    metadata = _dict_or_empty(assignments.get("READY_METADATA"))
    metadata = _metadata_with_static_derivations(metadata, source_path, source)
    requirements = _dict_or_empty(assignments.get("READY_REQUIREMENTS"))
    meta_reqs = _dict_or_empty(metadata.get("requirements"))
    runtime_requirements: dict[str, Any] | None = None
    try:
        legacy_env = metadata.get("python_env")
        legacy_commit = metadata.get("comfy_commit")
        runtime = _merge_static_runtime_requirements(
            requirements.get("runtime"),
            meta_reqs.get("runtime"),
            legacy_python_env=legacy_env if isinstance(legacy_env, dict) else None,
            legacy_comfy_commit=legacy_commit if isinstance(legacy_commit, str) else None,
        )
        runtime_requirements = runtime.to_dict() if runtime is not None else None
    except RuntimeDependencyError as exc:
        diagnostics.append({
            "code": "static_runtime_contract_invalid",
            "severity": "error",
            "message": str(exc),
            "location": _source_location(
                source_path,
                _runtime_contract_locations(tree).get("runtime", tree),
                semantic_path="requirements.runtime",
            ),
        })

    # ── Derive public_inputs from PUBLIC_INPUTS/InputSpec when present ──
    # Generated templates use either ``PUBLIC_INPUT_METADATA`` (canonical
    # post-revert shape) or the legacy ``PUBLIC_INPUTS`` alias.  Try the new
    # name first and fall back to the old.
    public_inputs: list[dict[str, Any]] = []
    public_outputs: list[dict[str, Any]] = []
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
    public_inputs.extend(
        _infer_common_input_contracts(
            tree,
            public_inputs,
            assignments,
            wrapper_class_types=wrappers,
        )
    )

    # The runtime declaration may be authored in READY_REQUIREMENTS or in the
    # nested ReadyMetadata requirements block.  Both are declarations, so
    # retain both and surface contradictions instead of silently preferring one.
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
        "runtime": runtime_requirements,
        "app_active": _is_app_active(metadata),
        "blocked": _has_marker(metadata, "blocked"),
        "reference": _has_marker(metadata, "reference"),
        "supplemental": _has_marker(metadata, "supplemental"),
    }
    summary["source_locations"] = _static_source_locations(
        tree,
        source_path,
        wrapper_class_types=wrappers,
    )
    if include_locations:
        summary["diagnostics"] = _diagnostics_with_locations(
            summary["diagnostics"], tree, source_path
        )
    if merged_custom_node_refs:
        summary["custom_node_refs"] = merged_custom_node_refs
    return summary


def _merge_static_runtime_requirements(
    *raw_values: Any,
    legacy_python_env: Mapping[str, Any] | None = None,
    legacy_comfy_commit: str | None = None,
) -> RuntimeRequirements | None:
    merged: dict[str, Any] = {}
    for raw in raw_values:
        if raw is None:
            continue
        current = RuntimeRequirements.from_dict(
            raw,
            legacy_python_env=legacy_python_env,
            legacy_comfy_commit=legacy_comfy_commit,
        )
        if current is None:
            continue
        current_dict = current.to_dict()
        for key, value in current_dict.items():
            if key == "packages" and isinstance(value, Mapping):
                packages = merged.setdefault("packages", {})
                if not isinstance(packages, dict):
                    raise RuntimeDependencyError("runtime packages declaration contradicts its other runtime declaration")
                for name, constraint in value.items():
                    if name in packages and packages[name] != constraint:
                        raise RuntimeDependencyError(
                            f"runtime package {name!r} declarations contradict each other"
                        )
                    packages[name] = constraint
                continue
            if key in merged and merged[key] != value:
                raise RuntimeDependencyError(f"runtime {key} declarations contradict each other")
            merged[key] = value
    return RuntimeRequirements.from_dict(
        merged or None,
        legacy_python_env=legacy_python_env,
        legacy_comfy_commit=legacy_comfy_commit,
    )


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
    allocator = _StaticNodeIdAllocator()
    for call in calls:
        node_id, relocations = allocator.allocate(_node_call_source_id(call))
        if relocations:
            for call_identity, prior_id in tuple(runtime_ids.items()):
                if prior_id in relocations:
                    runtime_ids[call_identity] = relocations[prior_id]
        runtime_ids[id(call)] = node_id
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
    *,
    wrapper_class_types: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    explicit_names = {item.get("name") for item in explicit_inputs if isinstance(item.get("name"), str)}
    inferred: dict[str, dict[str, Any]] = {}
    node_ids = _StaticNodeIdAllocator()
    wrappers = wrapper_class_types or {}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_static_node_call(node, wrappers)
    ]
    for call in sorted(calls, key=lambda item: (getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
        node_info = _runtime_node_call(
            call,
            node_ids,
            assignments,
            wrapper_class_types=wrappers,
        )
        if node_info is None:
            continue
        for old_id, new_id in node_info.pop("relocations", {}).items():
            for descriptor in inferred.values():
                if descriptor.get("node_id") == old_id:
                    descriptor["node_id"] = new_id
                    descriptor["target"] = {
                        **descriptor["target"],
                        "node_id": new_id,
                    }
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


class _StaticNodeIdAllocator:
    """Mirror the ready builder's lowest-free allocation and source-id rename."""

    def __init__(self) -> None:
        self.occupied: set[str] = set()

    def _next(self) -> str:
        candidate = 1
        while str(candidate) in self.occupied:
            candidate += 1
        return str(candidate)

    def allocate(self, explicit: Any = None) -> tuple[str, dict[str, str]]:
        automatic = self._next()
        self.occupied.add(automatic)
        if not isinstance(explicit, (str, int)) or isinstance(explicit, bool):
            return automatic, {}
        source_id = str(explicit)
        relocations: dict[str, str] = {}
        if source_id != automatic and source_id in self.occupied:
            self.occupied.remove(source_id)
            relocated = self._next()
            self.occupied.add(relocated)
            relocations[source_id] = relocated
        self.occupied.remove(automatic)
        self.occupied.add(source_id)
        return source_id, relocations


def _runtime_node_call(
    node: ast.Call,
    node_ids: _StaticNodeIdAllocator,
    assignments: dict[str, Any] | None = None,
    *,
    wrapper_class_types: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    call_name = _call_name(node.func)
    explicit_id: Any = None
    if call_name == "_node":
        class_type = _literal_arg(node, 1, "class_type", [], call_name, required=False)
        explicit_id = _literal_arg(node, 2, "node_id", [], call_name, required=False)
        keyword_inputs = _literal_keyword_inputs(node, assignments=assignments)
    elif call_name == "ready_node":
        class_type = _literal_arg(node, 1, "class_type", [], call_name, required=False)
        explicit_id = _keyword_literal(node, "source_id", [], call_name)
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
        explicit_id = raw_node_id
        keyword_inputs = _literal_keyword_inputs(node, assignments=assignments)
    elif call_name in (wrapper_class_types or {}):
        class_type = (wrapper_class_types or {})[call_name]
        explicit_id = _keyword_literal(node, "_id", [], call_name)
        keyword_inputs = _literal_keyword_inputs(
            node,
            excluded={"_id", "_uid", "_outputs", "_native_ports", "_mode", "pass_raw"},
            assignments=assignments,
        )
    else:
        return None
    if not isinstance(class_type, str):
        return None
    node_id, relocations = node_ids.allocate(explicit_id)
    return {
        "class_type": class_type,
        "node_id": node_id,
        "inputs": keyword_inputs,
        "relocations": relocations,
    }


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


def _is_static_node_call(
    node: ast.Call,
    wrapper_class_types: Mapping[str, str],
) -> bool:
    call_name = _call_name(node.func)
    return call_name in {"_node", "node", "ready_node"} or call_name in wrapper_class_types


_NON_WRAPPER_CALLS = frozenset(
    {
        "InputSpec",
        "ModelAsset",
        "ReadyMetadata",
        "bind_input",
        "bind_output",
        "finalize",
        "new_workflow",
        "node",
        "ready_node",
        "register_input",
        "template_input",
        "template_output",
        "VibeOutput",
    }
)


def _wrapper_call_candidates(tree: ast.AST) -> set[str]:
    return {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for name in [_call_name(node.func)]
        if name and name not in _NON_WRAPPER_CALLS and name != "_node"
    }


def resolve_ready_wrapper_class_types_from_trees(
    trees: Iterable[ast.AST],
) -> dict[str, str]:
    """Resolve every wrapper call in one content-witnessed cache batch."""
    candidates: set[str] = set()
    for tree in trees:
        candidates.update(_wrapper_call_candidates(tree))
    if not candidates:
        return {}
    try:
        from vibecomfy.porting.object_info.consume import get_classes
    except ImportError:
        return {}
    return {name: name for name in get_classes(candidates)}


def resolve_ready_wrapper_class_types(
    paths: Iterable[str | Path],
) -> dict[str, str]:
    """Parse template paths and resolve their wrapper calls as one batch."""
    trees: list[ast.AST] = []
    for path in paths:
        try:
            trees.append(ast.parse(Path(path).read_text(encoding="utf-8")))
        except (OSError, SyntaxError):
            continue
    return resolve_ready_wrapper_class_types_from_trees(trees)


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
        # None is the canonical unresolved state; an absent URL must not be
        # collapsed into a different empty-string representation.
        "url": result.get("url") if "url" in result else None,
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
    out.setdefault("comfy_core", _comfy_core_metadata())
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
    path = _repo_root() / "ready_templates/sources" / "manifests" / "coverage.json"
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


def _comfy_core_metadata() -> dict[str, Any]:
    try:
        data = json.loads((_repo_root() / "vibecomfy" / "comfy_metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    core = data.get("core") if isinstance(data, dict) and isinstance(data.get("core"), dict) else data
    if not isinstance(core, dict):
        return {}
    return {key: value for key, value in core.items() if key in {"version", "commit", "tested_at", "status"}}


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _diagnostic(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": "warning", "message": message}


def _source_location(path: Path, node: ast.AST, *, semantic_path: str | None = None) -> dict[str, Any]:
    location: dict[str, Any] = {
        "source_path": str(path),
        "line": int(getattr(node, "lineno", 1)),
        "column": int(getattr(node, "col_offset", 0)),
        "end_line": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
        "end_column": int(getattr(node, "end_col_offset", getattr(node, "col_offset", 0))),
    }
    if semantic_path is not None:
        location["path"] = semantic_path
    return location


def _diagnostics_with_locations(
    diagnostics: list[dict[str, Any]], tree: ast.AST, path: Path
) -> list[dict[str, Any]]:
    """Attach a best-effort AST location without changing legacy output by default."""
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    result: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        item = dict(diagnostic)
        if "location" not in item:
            needle = str(item.get("message", ""))
            match = next(
                (
                    node
                    for node in calls
                    if _call_name(node.func) and _call_name(node.func) in needle
                ),
                None,
            )
            item["location"] = _source_location(path, match or tree)
        result.append(item)
    return result


def _static_source_locations(
    tree: ast.AST,
    path: Path,
    *,
    wrapper_class_types: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return source locations for authored dependency and graph witnesses."""
    locations: list[dict[str, Any]] = []
    wrappers = wrapper_class_types or {}
    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        for target in assignment.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "MODELS" and isinstance(assignment.value, ast.Dict):
                for key, value in zip(assignment.value.keys, assignment.value.values):
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(value, ast.Call)
                        and _call_qualified_name(value.func) == "ModelAsset"
                    ):
                        locations.append({
                            "kind": "model",
                            **_source_location(path, value, semantic_path=f"MODELS[{json.dumps(str(key.value))}].url"),
                        })
            if target.id in {"READY_METADATA", "READY_REQUIREMENTS"}:
                locations.extend(_requirement_locations(assignment.value, path, target.id))
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        class_type = _node_call_class_type(call)
        name = _call_name(call.func)
        if not class_type or not (
            name in {"node", "raw_call", "_node", "ready_node"}
            or name in wrappers
            or (name and name[:1].isupper() and name not in _NON_WRAPPER_CALLS)
        ):
            continue
        locations.append({
            "kind": "graph_node",
            "class_type": class_type,
            **_source_location(path, call, semantic_path=f"graph[{class_type!r}]"),
        })
    return locations


def _requirement_locations(value: ast.AST, path: Path, owner: str) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    requirement_dict: ast.Dict | None = None
    if isinstance(value, ast.Call):
        for keyword in value.keywords:
            if keyword.arg == "requirements" and isinstance(keyword.value, ast.Dict):
                requirement_dict = keyword.value
                break
    elif isinstance(value, ast.Dict):
        requirement_dict = next(
            (
                nested_value
                for key, nested_value in zip(value.keys, value.values)
                if isinstance(key, ast.Constant)
                and key.value == "requirements"
                and isinstance(nested_value, ast.Dict)
            ),
            None,
        )
    if requirement_dict is None and owner == "READY_REQUIREMENTS" and isinstance(value, ast.Dict):
        requirement_dict = value
    if requirement_dict is None:
        return locations
    for key, nested in zip(requirement_dict.keys, requirement_dict.values):
        if not isinstance(key, ast.Constant) or key.value != "custom_node_refs" or not isinstance(nested, ast.List):
            continue
        for index, item in enumerate(nested.elts):
            if isinstance(item, ast.Dict):
                locations.append({
                    "kind": "custom_node_ref",
                    **_source_location(
                        path,
                        item,
                        semantic_path=(
                            f"{owner}.custom_node_refs[{index}].url"
                            if owner == "READY_REQUIREMENTS"
                            else f"{owner}.requirements.custom_node_refs[{index}].url"
                        ),
                    ),
                })
    return locations


def _runtime_contract_locations(tree: ast.AST) -> dict[str, ast.AST]:
    """Find literal runtime/legacy fields without importing the source."""
    locations: dict[str, ast.AST] = {}
    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        owners = {target.id for target in assignment.targets if isinstance(target, ast.Name)}
        value = assignment.value
        requirement_nodes: list[ast.Dict] = []
        if "READY_REQUIREMENTS" in owners and isinstance(value, ast.Dict):
            requirement_nodes.append(value)
        if "READY_METADATA" in owners:
            if isinstance(value, ast.Call):
                for keyword in value.keywords:
                    if keyword.arg == "requirements" and isinstance(keyword.value, ast.Dict):
                        requirement_nodes.append(keyword.value)
                    elif keyword.arg in {"python_env", "comfy_commit"}:
                        locations.setdefault(f"metadata.{keyword.arg}", keyword.value)
            elif isinstance(value, ast.Dict):
                fields = _dict_field_nodes(value)
                nested = fields.get("requirements")
                if isinstance(nested, ast.Dict):
                    requirement_nodes.append(nested)
                for key in ("python_env", "comfy_commit"):
                    if key in fields:
                        locations.setdefault(f"metadata.{key}", fields[key])
        for requirement in requirement_nodes:
            fields = _dict_field_nodes(requirement)
            if "runtime" in fields:
                locations.setdefault("runtime", fields["runtime"])
                index = sum(
                    1 for key in locations if key == "runtime" or key.startswith("runtime.")
                )
                locations[f"runtime.{index}"] = fields["runtime"]
    return locations


def _runtime_contract_diagnostics(tree: ast.AST, path: Path) -> list[dict[str, Any]]:
    locations = _runtime_contract_locations(tree)
    runtime_node = locations.get("runtime")
    runtime_nodes = [
        node for key, node in locations.items()
        if key == "runtime" or key.startswith("runtime.")
    ]
    legacy_env_node = locations.get("metadata.python_env")
    legacy_commit_node = locations.get("metadata.comfy_commit")
    if runtime_node is None and legacy_env_node is None and legacy_commit_node is None:
        return []
    runtime_raw_values = [_literal_value(node, {}) for node in runtime_nodes]
    legacy_env = _literal_value(legacy_env_node, {}) if legacy_env_node is not None else None
    legacy_commit = _literal_value(legacy_commit_node, {}) if legacy_commit_node is not None else None
    if any(value is _UNSUPPORTED for value in runtime_raw_values) or legacy_env is _UNSUPPORTED or legacy_commit is _UNSUPPORTED:
        node = runtime_node or legacy_env_node or legacy_commit_node or tree
        return [{
            "code": "static_dynamic_value",
            "severity": "error",
            "message": "runtime dependency declaration contains a dynamic value; use literal runtime facts",
            "location": _source_location(path, node, semantic_path="requirements.runtime"),
        }]
    try:
        _merge_static_runtime_requirements(
            *runtime_raw_values,
            legacy_python_env=legacy_env if isinstance(legacy_env, Mapping) else None,
            legacy_comfy_commit=legacy_commit if isinstance(legacy_commit, str) else None,
        )
    except RuntimeDependencyError as exc:
        node = runtime_node or legacy_env_node or legacy_commit_node or tree
        return [{
            "code": "static_runtime_contract_invalid",
            "severity": "error",
            "message": str(exc),
            "location": _source_location(path, node, semantic_path="requirements.runtime"),
        }]
    return []


def reconcile_ready_template_source(
    source: str,
    *,
    source_path: str | Path = "<memory>",
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Statically inspect and narrowly repair authored dependency placeholders.

    Only literal ``ModelAsset`` calls and literal custom-node-ref dictionaries
    are edited.  Dynamic expressions produce diagnostics and are left byte
    unchanged.  The returned source is suitable for an atomic caller write.
    """
    if not isinstance(source, str):
        raise TypeError("source must be text")
    path = Path(source_path)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    expected = (expected_source_sha256 or "").removeprefix("sha256:")
    if expected and expected != digest:
        return {
            "changed": False,
            "source": source,
            "source_sha256": digest,
            "diagnostics": [{
                "code": "source_cas_mismatch",
                "severity": "error",
                "message": "source changed since reconciliation began; no edit was applied",
                "location": {"source_path": str(path)},
            }],
            "edits": [],
            "blockers": [],
        }
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return {
            "changed": False,
            "source": source,
            "source_sha256": digest,
            "diagnostics": [{
                "code": "static_contract_parse_failed",
                "severity": "error",
                "message": str(exc),
                "location": {"source_path": str(path), "line": exc.lineno, "column": exc.offset},
            }],
            "edits": [],
            "blockers": [],
        }

    # Reconciliation is deliberately import-free.  The ordinary contract
    # reader may consult the local schema catalog for wrapper aliases, but a
    # dependency repair must report gaps before any custom-node setup or
    # catalog import is attempted.
    contract = None
    wrappers: dict[str, str] = {}
    edits: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = [
        *_dependency_container_diagnostics(tree, path),
        *_runtime_contract_diagnostics(tree, path),
    ]
    blockers: list[dict[str, Any]] = []

    model_calls = _model_asset_call_records(tree, path)
    for record in model_calls:
        call = record["node"]
        kwargs = record["kwargs"]
        model_path = record["path"]
        revision_name = "hf_revision" if "hf_revision" in kwargs else "revision"
        revision_node = kwargs.get(revision_name)
        if "url" in kwargs:
            url_node = kwargs["url"]
            url = _literal_value(url_node, {})
            if url is _UNSUPPORTED:
                diagnostics.append(_located_diagnostic(
                    "static_dynamic_value", "ModelAsset has dynamic 'url'", path, url_node, model_path + ".url"
                ))
            elif url in (None, ""):
                blockers.append(_dependency_blocker("model_url_missing", "Fill the model URL.", path, url_node, model_path + ".url"))
            if revision_node is not None:
                blockers.extend(_model_selector_blockers(
                    url=url,
                    revision_node=revision_node,
                    path=path,
                    semantic_path=model_path,
                    selector_name=revision_name,
                ))
            continue
        filename = _literal_keyword_value(kwargs.get("filename"), tree)
        subdir = _literal_keyword_value(kwargs.get("subdir"), tree)
        if not isinstance(filename, str) or not filename or not _safe_static_path(filename) or not isinstance(subdir, str) or not subdir or not _safe_static_path(subdir):
            diagnostics.append(_located_diagnostic(
                "static_dynamic_model_asset", "ModelAsset needs explicit safe filename and subdir before url can be inserted", path, call, model_path
            ))
            continue
        edit = _insert_keyword_edit(source, call, "url", "None", path, model_path + ".url")
        edits.append(edit)
        blockers.append(_dependency_blocker("model_url_missing", "Fill the model URL.", path, call, model_path + ".url"))
        if revision_node is not None:
            blockers.extend(_model_selector_blockers(
                url=None,
                revision_node=revision_node,
                path=path,
                semantic_path=model_path,
                selector_name=revision_name,
            ))

    for model_node, model_path in _requirement_model_dicts(tree):
        fields = _dict_field_nodes(model_node)
        url_node = fields.get("url")
        if url_node is None:
            edits.append(_insert_dict_field_edit(source, model_node, "url", "None", path, model_path + ".url"))
            blockers.append(_dependency_blocker("model_url_missing", "Fill the model URL.", path, model_node, model_path + ".url"))
        else:
            url = _literal_value(url_node, {})
            if url is _UNSUPPORTED:
                diagnostics.append(_located_diagnostic("static_dynamic_value", "model requirement has dynamic 'url'", path, url_node, model_path + ".url"))
            elif url in (None, ""):
                blockers.append(_dependency_blocker("model_url_missing", "Fill the model URL.", path, url_node, model_path + ".url"))
        _append_model_requirement_selector_blockers(
            fields,
            path=path,
            model_path=model_path,
            blockers=blockers,
        )

    ref_lists = _custom_ref_lists(tree)
    requirement_dicts = _literal_requirement_dicts(tree)
    placeholder_edit: dict[str, Any] | None = None
    if not ref_lists and requirement_dicts:
        requirement_node, requirement_path = requirement_dicts[0]
        placeholder_edit = _insert_dict_field_edit(
            source,
            requirement_node,
            "custom_node_refs",
            "[]",
            path,
            requirement_path + ".custom_node_refs",
        )
        edits.append(placeholder_edit)
    declared_classes: set[str] = set()
    placeholder_classes: list[str] = []
    for refs_node, refs_path in ref_lists:
        for index, item in enumerate(refs_node.elts):
            if not isinstance(item, ast.Dict):
                diagnostics.append(_located_diagnostic("static_dynamic_value", "custom node ref is not a literal dictionary", path, item, f"{refs_path}[{index}]"))
                continue
            fields = _dict_field_nodes(item)
            _append_node_selector_blockers(
                fields,
                path=path,
                ref_path=f"{refs_path}[{index}]",
                node=item,
                blockers=blockers,
            )
            declared_classes.update(_string_list_value(fields.get("classes")))
            declared_classes.update(_string_list_value(fields.get("class_set")))
            if "url" not in fields:
                edits.append(_insert_dict_field_edit(source, item, "url", "None", path, f"{refs_path}[{index}].url"))
                blockers.append(_dependency_blocker("custom_node_repository_missing", "Fill the custom-node repository URL.", path, item, f"{refs_path}[{index}].url"))
            else:
                url = _literal_value(fields["url"], {})
                if url is _UNSUPPORTED:
                    diagnostics.append(_located_diagnostic("static_dynamic_value", "custom node ref has dynamic 'url'", path, fields["url"], f"{refs_path}[{index}].url"))
                elif url in (None, ""):
                    blockers.append(_dependency_blocker("custom_node_repository_missing", "Fill the custom-node repository URL.", path, fields["url"], f"{refs_path}[{index}].url"))

    graph_classes = _graph_class_records(tree, wrappers)
    try:
        from vibecomfy.node_packs import CORE_COMFY_CLASSES
        core_classes = set(CORE_COMFY_CLASSES)
    except ImportError:
        core_classes = set()
    local_catalog: dict[str, set[str]] = {}
    try:
        # This is only the checked-in/lockfile class catalog; it does not
        # import arbitrary custom-node implementations or perform discovery.
        from vibecomfy.node_packs import get_known_node_packs

        for pack in get_known_node_packs():
            for class_type in pack.classes:
                local_catalog.setdefault(str(class_type), set()).add(str(pack.name))
    except (ImportError, OSError, ValueError, TypeError):
        # A broken optional catalog must not hide source-level gaps.  The
        # authored class list remains sufficient when it is present.
        local_catalog = {}

    class_counts: dict[str, int] = {}
    class_accounting: dict[str, dict[str, Any]] = {}
    next_ref_index = len(ref_lists[0][0].elts) if ref_lists else 0
    for class_type, node in graph_classes:
        class_counts[class_type] = class_counts.get(class_type, 0) + 1
        if class_type in core_classes:
            class_accounting.setdefault(class_type, {"status": "core", "occurrences": 0})["occurrences"] += 1
            continue
        if class_type in declared_classes:
            class_accounting.setdefault(class_type, {"status": "declared", "occurrences": 0})["occurrences"] += 1
            continue
        catalog_matches = sorted(local_catalog.get(class_type, ()))
        if len(catalog_matches) == 1:
            class_accounting.setdefault(class_type, {"status": "local_catalog", "pack": catalog_matches[0], "occurrences": 0})["occurrences"] += 1
            continue
        semantic_path = f"graph[{class_type!r}]"
        detail = {"class_type": class_type, "occurrences": class_counts[class_type]}
        if len(catalog_matches) > 1:
            detail["catalog_matches"] = catalog_matches
        class_accounting[class_type] = {"status": "unaccounted", **detail}
        blockers.append(_dependency_blocker("class_not_accounted_for", "No declared custom-node ref or unambiguous local pack accounts for this class.", path, node, semantic_path, detail=detail))
        if ref_lists:
            refs_node, refs_path = ref_lists[0]
            new_index = next_ref_index
            next_ref_index += 1
            value = repr({"slug": class_type, "source": "git", "url": None, "classes": [class_type]})
            edits.append(_append_list_item_edit(source, refs_node, value, path, f"{refs_path}[{new_index}]"))
            declared_classes.add(class_type)
        elif placeholder_edit is not None:
            placeholder_classes.append(class_type)
            declared_classes.add(class_type)

    if placeholder_edit is not None:
        field = "'custom_node_refs': []"
        prefix = str(placeholder_edit["replacement"]).removesuffix(field)
        values = [
            repr({"slug": class_type, "source": "git", "url": None, "classes": [class_type]})
            for class_type in placeholder_classes
        ]
        placeholder_edit["replacement"] = f"{prefix}'custom_node_refs': [{', '.join(values)}]" if values else f"{prefix}{field}"

    edited_source = _apply_source_edits(source, edits)
    # An inserted placeholder is itself unresolved; callers may still choose
    # to show the complete report before a future run fills it.
    return {
        "changed": edited_source != source,
        "source": edited_source,
        "source_sha256": hashlib.sha256(edited_source.encode("utf-8")).hexdigest(),
        "original_source_sha256": digest,
        "diagnostics": diagnostics,
        "edits": [dict(edit) for edit in edits],
        "blockers": blockers,
        "graph_classes": dict(sorted(class_counts.items())),
        "class_accounting": {key: class_accounting[key] for key in sorted(class_accounting)},
        "locations": contract.get("source_locations", []) if contract else _static_source_locations(tree, path, wrapper_class_types=wrappers),
    }


def reconcile_ready_template_file(
    path: str | Path,
    *,
    expected_source_sha256: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Reconcile one source file and atomically publish only a CAS-valid edit."""
    source_path = Path(path)
    source = source_path.read_text(encoding="utf-8")
    result = reconcile_ready_template_source(
        source,
        source_path=source_path,
        expected_source_sha256=expected_source_sha256,
    )
    if write and result["changed"]:
        current = source_path.read_text(encoding="utf-8")
        if current != source:
            result["changed"] = False
            result["source"] = source
            result["diagnostics"].append({
                "code": "source_cas_mismatch",
                "severity": "error",
                "message": "source changed before atomic publication; no edit was applied",
                "location": {"source_path": str(source_path)},
            })
        else:
            from vibecomfy.porting.object_info.generation import atomic_write_text
            atomic_write_text(source_path, result["source"])
            result["written"] = True
    else:
        result["written"] = False
    return result


def _located_diagnostic(code: str, message: str, path: Path, node: ast.AST, semantic_path: str) -> dict[str, Any]:
    return {"code": code, "severity": "warning", "message": message, "location": _source_location(path, node, semantic_path=semantic_path)}


def _dependency_blocker(code: str, message: str, path: Path, node: ast.AST, semantic_path: str, *, detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "location": _source_location(path, node, semantic_path=semantic_path), "detail": dict(detail or {})}


def _model_selector_blockers(
    *,
    url: Any,
    revision_node: ast.AST,
    path: Path,
    semantic_path: str,
    selector_name: str = "hf_revision",
) -> list[dict[str, Any]]:
    revision = _literal_value(revision_node, {})
    selector_path = semantic_path + "." + selector_name
    if revision is _UNSUPPORTED:
        return [_dependency_blocker(
            "unsupported_model_selector",
            "ModelAsset has a dynamic hf_revision selector; use a literal revision or remove the selector.",
            path,
            revision_node,
            selector_path,
        )]
    if revision in (None, ""):
        return []
    if not isinstance(revision, str):
        return [_dependency_blocker(
            "unsupported_model_selector",
            "ModelAsset hf_revision selector must be a non-empty string or omitted.",
            path,
            revision_node,
            selector_path,
        )]
    if not isinstance(url, str) or not url.strip():
        return []
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        return [_dependency_blocker(
            "unsupported_model_selector",
            f"ModelAsset {selector_name} selector {revision!r} is unsupported: invalid model URL ({exc}).",
            path,
            revision_node,
            selector_path,
        )]
    supported_host = (parsed.hostname or "").lower() in {
        "huggingface.co",
        "www.huggingface.co",
        "hf.co",
        "www.hf.co",
    }
    supported_path = False
    if supported_host:
        parts = parsed.path.split("/")
        for marker in ("resolve", "blob"):
            if marker not in parts:
                continue
            marker_index = parts.index(marker)
            if marker_index + 1 < len(parts) and parts[marker_index + 1]:
                supported_path = True
                break
    if supported_host and supported_path:
        return []
    detail = (
        "only Hugging Face resolve/blob URLs support hf_revision pinning"
        if not supported_host
        else "Hugging Face URL must contain a resolve/<revision>/ or blob/<revision>/ path"
    )
    return [_dependency_blocker(
        "unsupported_model_selector",
        f"ModelAsset hf_revision selector {revision!r} is unsupported: {detail}; use a supported URL or remove hf_revision.",
        path,
        revision_node,
        selector_path,
    )]


def _append_model_requirement_selector_blockers(
    fields: Mapping[str, ast.AST],
    *,
    path: Path,
    model_path: str,
    blockers: list[dict[str, Any]],
) -> None:
    selector_name = "hf_revision" if "hf_revision" in fields else "revision"
    revision_node = fields.get(selector_name)
    if revision_node is None:
        return
    url_node = fields.get("url")
    url = _literal_value(url_node, {}) if url_node is not None else None
    blockers.extend(_model_selector_blockers(
        url=url,
        revision_node=revision_node,
        path=path,
        semantic_path=model_path,
        selector_name=selector_name,
    ))


def _append_node_selector_blockers(
    fields: Mapping[str, ast.AST],
    *,
    path: Path,
    ref_path: str,
    node: ast.Dict,
    blockers: list[dict[str, Any]],
) -> None:
    selector_values: list[str] = []
    for field_name in ("slug", "name"):
        field_node = fields.get(field_name)
        if field_node is None:
            continue
        value = _literal_value(field_node, {})
        if isinstance(value, str) and value.strip():
            selector_values.append(value)
            continue
        blockers.append(_dependency_blocker(
            "unsupported_node_selector",
            f"custom node ref {field_name!r} selector must be a non-empty literal string.",
            path,
            field_node,
            f"{ref_path}.{field_name}",
        ))
    if not selector_values:
        blockers.append(_dependency_blocker(
            "unsupported_node_selector",
            "custom node ref must contain a non-empty literal slug or name selector.",
            path,
            node,
            ref_path,
        ))
    for field_name in ("version", "commit"):
        field_node = fields.get(field_name)
        if field_node is None:
            continue
        value = _literal_value(field_node, {})
        if isinstance(value, str) and value.strip():
            continue
        blockers.append(_dependency_blocker(
            "unsupported_node_selector",
            f"custom node ref {field_name!r} selector must be a non-empty literal string or omitted.",
            path,
            field_node,
            f"{ref_path}.{field_name}",
        ))


def _model_asset_call_records(tree: ast.AST, path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        target_names = {target.id for target in assignment.targets if isinstance(target, ast.Name)}
        if "MODELS" in target_names and isinstance(assignment.value, ast.Dict):
            for key, value in zip(assignment.value.keys, assignment.value.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Call) and _call_qualified_name(value.func) == "ModelAsset":
                    records.append({"node": value, "kwargs": {kw.arg: kw.value for kw in value.keywords if kw.arg}, "path": f"MODELS[{json.dumps(str(key.value))}]"})
    return records


def _dependency_container_diagnostics(tree: ast.AST, path: Path) -> list[dict[str, Any]]:
    """Report dependency containers that static reconciliation cannot inspect."""
    diagnostics: list[dict[str, Any]] = []

    def manual(owner: str, node: ast.AST, detail: str) -> None:
        diagnostics.append(_located_diagnostic(
            "manual_repair_required",
            f"{owner} contains dynamic dependency data ({detail}); manually repair the canonical dependency container.",
            path,
            node,
            owner,
        ))

    def requirement_fields(node: ast.Dict, owner: str) -> None:
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or key.value not in {"models", "custom_node_refs"}:
                continue
            if not isinstance(value, ast.List):
                manual(f"{owner}.{key.value}", value, f"{key.value} is not a literal list")

    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        names = {target.id for target in assignment.targets if isinstance(target, ast.Name)}
        value = assignment.value
        if "MODELS" in names:
            if not isinstance(value, ast.Dict):
                manual("MODELS", value, "MODELS is not a literal mapping")
            else:
                for key, model in zip(value.keys, value.values):
                    if isinstance(key, ast.Constant) and not (
                        isinstance(model, ast.Call)
                        and _call_qualified_name(model.func) == "ModelAsset"
                    ):
                        manual(
                            f"MODELS[{json.dumps(str(key.value))}]",
                            model,
                            "model entry is not a literal ModelAsset",
                        )
        if "READY_REQUIREMENTS" in names:
            if not isinstance(value, ast.Dict):
                manual("READY_REQUIREMENTS", value, "requirements are not a literal mapping")
            else:
                requirement_fields(value, "READY_REQUIREMENTS")
        if "READY_METADATA" not in names:
            continue
        if isinstance(value, ast.Dict):
            for key, nested in zip(value.keys, value.values):
                if not isinstance(key, ast.Constant) or key.value != "requirements":
                    continue
                if not isinstance(nested, ast.Dict):
                    manual("READY_METADATA.requirements", nested, "requirements are not a literal mapping")
                else:
                    requirement_fields(nested, "READY_METADATA.requirements")
        elif isinstance(value, ast.Call):
            for keyword in value.keywords:
                if keyword.arg != "requirements":
                    continue
                if not isinstance(keyword.value, ast.Dict):
                    manual("READY_METADATA.requirements", keyword.value, "requirements are not a literal mapping")
                else:
                    requirement_fields(keyword.value, "READY_METADATA.requirements")
    return diagnostics


def _literal_requirement_dicts(tree: ast.AST) -> list[tuple[ast.Dict, str]]:
    """Return supported literal canonical requirements mappings in source order."""
    found: list[tuple[ast.Dict, str]] = []

    def supported(node: ast.Dict) -> bool:
        return all(
            isinstance(value, ast.List)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant)
            and key.value in {"models", "custom_node_refs"}
        )

    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        names = {target.id for target in assignment.targets if isinstance(target, ast.Name)}
        value = assignment.value
        if "READY_REQUIREMENTS" in names and isinstance(value, ast.Dict) and supported(value):
            found.append((value, "READY_REQUIREMENTS"))
        if "READY_METADATA" not in names:
            continue
        if isinstance(value, ast.Dict):
            for key, nested in zip(value.keys, value.values):
                if isinstance(key, ast.Constant) and key.value == "requirements" and isinstance(nested, ast.Dict) and supported(nested):
                    found.append((nested, "READY_METADATA.requirements"))
        elif isinstance(value, ast.Call):
            for keyword in value.keywords:
                if keyword.arg == "requirements" and isinstance(keyword.value, ast.Dict) and supported(keyword.value):
                    found.append((keyword.value, "READY_METADATA.requirements"))
    unique: dict[int, tuple[ast.Dict, str]] = {id(node): (node, path) for node, path in found}
    return list(unique.values())


def _requirement_model_dicts(tree: ast.AST) -> list[tuple[ast.Dict, str]]:
    """Find literal ``requirements.models`` dictionaries without executing code."""
    records: list[tuple[ast.Dict, str]] = []
    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        owners = [target.id for target in assignment.targets if isinstance(target, ast.Name)]
        if not set(owners) & {"READY_METADATA", "READY_REQUIREMENTS"}:
            continue
        for node in ast.walk(assignment.value):
            if not isinstance(node, ast.Dict):
                continue
            fields = _dict_field_nodes(node)
            models = fields.get("models")
            if not isinstance(models, ast.List):
                continue
            owner = owners[0]
            requirement_prefix = owner if owner == "READY_REQUIREMENTS" else owner + ".requirements"
            for index, item in enumerate(models.elts):
                if isinstance(item, ast.Dict):
                    records.append((item, f"{requirement_prefix}.models[{index}]"))
    return records


def _custom_ref_lists(tree: ast.AST) -> list[tuple[ast.List, str]]:
    found: list[tuple[ast.List, str]] = []
    for assignment in getattr(tree, "body", ()):
        if not isinstance(assignment, ast.Assign):
            continue
        names = [target.id for target in assignment.targets if isinstance(target, ast.Name)]
        if not set(names) & {"READY_METADATA", "READY_REQUIREMENTS"}:
            continue
        for node in ast.walk(assignment.value):
            if not isinstance(node, ast.keyword) or node.arg != "requirements":
                continue
            for nested in ast.walk(node.value):
                if isinstance(nested, ast.Dict):
                    for key, value in zip(nested.keys, nested.values):
                        if isinstance(key, ast.Constant) and key.value == "custom_node_refs" and isinstance(value, ast.List):
                            found.append((value, "READY_METADATA.requirements.custom_node_refs"))
        for node in ast.walk(assignment.value):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "custom_node_refs" and isinstance(value, ast.List):
                        found.append((value, "READY_REQUIREMENTS.custom_node_refs" if "READY_REQUIREMENTS" in names else "READY_METADATA.requirements.custom_node_refs"))
    unique: dict[int, tuple[ast.List, str]] = {id(node): (node, path) for node, path in found}
    return list(unique.values())


def _graph_class_records(tree: ast.AST, wrappers: Mapping[str, str]) -> list[tuple[str, ast.Call]]:
    records: list[tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        class_type = _node_call_class_type(node)
        if not class_type or not name:
            continue
        if name in {"node", "raw_call", "_node", "ready_node"} or name in wrappers or (name[:1].isupper() and name not in _NON_WRAPPER_CALLS):
            records.append((class_type, node))
    return records


def _dict_field_nodes(node: ast.Dict) -> dict[str, ast.AST]:
    return {
        str(key.value): value
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _string_list_value(node: ast.AST | None) -> set[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return set()
    return {str(item.value) for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value}


def _literal_keyword_value(node: ast.AST | None, tree: ast.AST) -> Any:
    if node is None:
        return None
    return _literal_value(node, {})


def _safe_static_path(value: str) -> bool:
    from vibecomfy.templates import _safe_model_relative_path
    return _safe_model_relative_path(value, field="model")


def _offsets(source: str) -> list[int]:
    positions = [0]
    for line in source.splitlines(keepends=True):
        positions.append(positions[-1] + len(line))
    return positions


def _node_end_offset(source: str, node: ast.AST) -> int:
    positions = _offsets(source)
    return positions[int(node.end_lineno) - 1] + int(node.end_col_offset)


def _insert_keyword_edit(source: str, call: ast.Call, name: str, value: str, path: Path, semantic_path: str) -> dict[str, Any]:
    anchor: ast.AST | None = call.keywords[-1].value if call.keywords else (call.args[-1] if call.args else None)
    position = _node_end_offset(source, anchor) if anchor is not None else _node_end_offset(source, call) - 1
    prefix = ", " if anchor is not None else ""
    return {"start": position, "end": position, "replacement": f"{prefix}{name}={value}", "path": semantic_path, "location": _source_location(path, call, semantic_path=semantic_path)}


def _insert_dict_field_edit(source: str, node: ast.Dict, name: str, value: str, path: Path, semantic_path: str) -> dict[str, Any]:
    anchor: ast.AST | None = node.values[-1] if node.values else None
    position = _node_end_offset(source, anchor) if anchor is not None else _node_end_offset(source, node) - 1
    prefix = ", " if anchor is not None else ""
    return {"start": position, "end": position, "replacement": f'{prefix}{name!r}: {value}', "path": semantic_path, "location": _source_location(path, node, semantic_path=semantic_path)}


def _append_list_item_edit(source: str, node: ast.List, value: str, path: Path, semantic_path: str) -> dict[str, Any]:
    anchor: ast.AST | None = node.elts[-1] if node.elts else None
    position = _node_end_offset(source, anchor) if anchor is not None else _node_end_offset(source, node) - 1
    prefix = ", " if anchor is not None else ""
    return {"start": position, "end": position, "replacement": f"{prefix}{value}", "kind": "list_append", "path": semantic_path, "location": _source_location(path, node, semantic_path=semantic_path)}


def _apply_source_edits(source: str, edits: list[dict[str, Any]]) -> str:
    if not edits:
        return source
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for edit in edits:
        grouped.setdefault((int(edit["start"]), int(edit["end"])), []).append(edit)
    merged: list[dict[str, Any]] = []
    for group in grouped.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        if not all(edit.get("kind") == "list_append" for edit in group):
            raise ValueError("multiple static source edits share an unsupported offset")
        replacement = str(group[0]["replacement"])
        has_existing_item = replacement.startswith(", ")
        for edit in group[1:]:
            item = str(edit["replacement"])
            if has_existing_item:
                replacement += item
            else:
                replacement += ", " + item.removeprefix(", ")
        combined = dict(group[0])
        combined["replacement"] = replacement
        merged.append(combined)
    ordered = sorted(merged, key=lambda item: (int(item["start"]), int(item["end"])), reverse=True)
    previous_start = len(source) + 1
    for edit in ordered:
        start, end = int(edit["start"]), int(edit["end"])
        if end > previous_start:
            raise ValueError("overlapping static source edits")
        previous_start = start
        source = source[:start] + str(edit["replacement"]) + source[end:]
    return source


# Short aliases keep the foundation discoverable to callers that describe the
# operation as simply "reconcile source" while the explicit name remains the
# canonical API.
reconcile_source = reconcile_ready_template_source
reconcile_ready_template = reconcile_ready_template_source


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
