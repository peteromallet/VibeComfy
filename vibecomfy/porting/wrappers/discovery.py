"""Discover ComfyUI node-class specs for a custom-node pack.

This module is the *ingestion* half of the generalized wrapper-codegen pipeline.
It produces a normalized ``ClassSpec`` list per pack from one of four sources,
in precedence order:

1. ``live`` — fetch ``/object_info`` from a running ComfyUI server.
2. ``cache`` — read ``vibecomfy/porting/cache/object_info/<pack>@<rev>.json``.
3. ``snapshot`` — read ``vibecomfy/porting/object_info/<pack>@<rev>.json``.
4. ``source`` — AST-parse ``custom_nodes/<pack>/**/*.py`` for ``INPUT_TYPES`` /
   ``RETURN_TYPES`` / ``RETURN_NAMES`` declarations (no ``exec``, no
   ``importlib`` — we never load pack code).

Per-pack files in (2)/(3) follow the shape produced by ComfyUI's
``/object_info`` endpoint *filtered to a single pack* (i.e. ``{class_name:
class_info, ...}``). Live mode (1) hits the server's full ``/object_info`` and
filters by ``pack`` field.

The codegen layer consumes ``ClassSpec`` lists; downstream callers should not
care which source the spec came from beyond ``ClassSpec.source_provenance``.

Design caveats — what the four sources *can't* recover:

- **``COMBO`` enum values** are only populated when /object_info is generated
  from a *live runtime* (cache or live). AST source extraction sees the
  ``INPUT_TYPES`` return shape but cannot evaluate function calls that produce
  combo lists (e.g. ``folder_paths.get_filename_list("vae")``). For these
  cases ``InputFieldSpec.options`` is ``None`` rather than the actual values.
- **Class-level decorators** that mutate INPUT_TYPES after the fact are not
  evaluated.
- **Dynamic node registration** (NODE_CLASS_MAPPINGS built at import time from
  generated tables) is not visible to AST parsing without evaluation.

When a downstream pipeline needs the missing data, prefer ``live`` or
``cache``; ``source`` is the offline fallback.
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

from vibecomfy.node_packs import get_known_node_packs


logger = logging.getLogger(__name__)


Source = Literal["live", "cache", "snapshot", "source"]
DEFAULT_PRECEDENCE: tuple[Source, ...] = ("cache", "snapshot", "source")


@dataclass(frozen=True, slots=True)
class InputFieldSpec:
    """Description of one ``INPUT_TYPES`` field on a ComfyUI node class.

    Attributes:
        name: Field name as it appears in ``INPUT_TYPES`` (e.g. ``"seed"``).
        type: ComfyUI socket type (``"INT"``, ``"FLOAT"``, ``"STRING"``,
            ``"MODEL"``, ``"COMBO"``, ...). ``COMBO`` is the type assigned by
            ComfyUI when the input declares a list of allowed values inline.
        required: True for ``required`` fields, False for ``optional``.
        default: Default value if the input declares one. ``None`` means no
            default. Note that ``None`` is also a valid declared default for
            optional sockets — distinguish via ``has_default``.
        has_default: True iff a default was declared.
        options: For ``COMBO`` inputs, the list of allowed string values.
            ``None`` when the combo is generated at runtime (e.g. from a
            folder listing) and the discovery source could not capture the
            values.
        widget_metadata: The full second-element dict from
            ``INPUT_TYPES[required][name]`` (e.g. ``{"min": 0, "max": 100,
            "step": 1, "tooltip": "..."}``). Preserved verbatim for callers
            that want to surface tooltips or validation bounds.
    """

    name: str
    type: str
    required: bool = True
    default: Any = None
    has_default: bool = False
    options: tuple[str, ...] | None = None
    widget_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClassSpec:
    """A normalized description of one ComfyUI node class."""

    pack_slug: str
    class_type: str
    inputs: dict[str, InputFieldSpec]
    outputs: tuple[str, ...]
    output_types: tuple[str, ...]
    is_output_node: bool = False
    category: str | None = None
    display_name: str | None = None
    description: str | None = None
    source_provenance: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_pack(
    pack_slug: str,
    *,
    sources: Sequence[Source] = DEFAULT_PRECEDENCE,
    server_url: str | None = None,
    cache_dir: str | Path = "vibecomfy/porting/cache/object_info",
    snapshot_dir: str | Path = "vibecomfy/porting/object_info",
    custom_nodes_dir: str | Path | None = None,
) -> list[ClassSpec]:
    """Discover all node classes in one pack.

    Tries each source in order; returns the *first* non-empty result. This is
    deliberately not a merge — different sources can disagree on widget
    metadata and we want a single deterministic source of truth per run.
    """
    # Resolve custom_nodes_dir from local-library config when the caller
    # omits it.  Explicit-caller-wins: a caller-supplied value is always used.
    if custom_nodes_dir is None:
        from vibecomfy.local_library import Slot, resolved_path

        configured = resolved_path(Slot.custom_nodes)
        custom_nodes_dir = configured if configured is not None else Path("custom_nodes")
    errors: list[str] = []
    for source in sources:
        try:
            if source == "live":
                if server_url is None:
                    continue
                specs = _discover_live(pack_slug, server_url)
            elif source == "cache":
                specs = _discover_from_object_info_dir(pack_slug, Path(cache_dir), kind="cache")
            elif source == "snapshot":
                specs = _discover_from_object_info_dir(pack_slug, Path(snapshot_dir), kind="snapshot")
            elif source == "source":
                specs = _discover_from_source(pack_slug, Path(custom_nodes_dir))
            else:
                raise ValueError(f"Unknown discovery source: {source!r}")
        except DiscoveryError as exc:
            errors.append(f"{source}: {exc}")
            continue
        if specs:
            return specs
    if errors:
        logger.debug("Discovery failed for %s: %s", pack_slug, "; ".join(errors))
    return []


def discover_all(
    *,
    sources: Sequence[Source] = DEFAULT_PRECEDENCE,
    server_url: str | None = None,
    lockfile: str | Path = "custom_nodes.lock",
    cache_dir: str | Path = "vibecomfy/porting/cache/object_info",
    snapshot_dir: str | Path = "vibecomfy/porting/object_info",
    custom_nodes_dir: str | Path | None = None,
) -> dict[str, list[ClassSpec]]:
    """Discover every pack listed in ``custom_nodes.lock``.

    Packs without any resolvable source produce an empty list in the returned
    dict (so callers can report them as ``no discovery available``).
    """
    # Resolve custom_nodes_dir from local-library config when the caller
    # omits it.  Explicit-caller-wins: a caller-supplied value is always used.
    if custom_nodes_dir is None:
        from vibecomfy.local_library import Slot, resolved_path

        configured = resolved_path(Slot.custom_nodes)
        custom_nodes_dir = configured if configured is not None else Path("custom_nodes")
    pack_slugs = _read_lockfile_pack_slugs(Path(lockfile))
    out: dict[str, list[ClassSpec]] = {}
    for slug in pack_slugs:
        out[slug] = discover_pack(
            slug,
            sources=sources,
            server_url=server_url,
            cache_dir=cache_dir,
            snapshot_dir=snapshot_dir,
            custom_nodes_dir=custom_nodes_dir,
        )
    return out


def known_pack_slug(class_type: str) -> str | None:
    """Return the registered pack slug for a class type, if known.

    Walks the lazy node-pack catalog and returns the first match.
    """
    for pack in get_known_node_packs():
        if class_type in pack.classes:
            return pack.name
    return None


def sha256_of_path(path: str | Path) -> str:
    """Stable SHA-256 hex digest of a file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DiscoveryError(Exception):
    """Raised by an individual discovery source when it cannot operate.

    The orchestrator catches this and moves to the next source. Errors from
    one source should not abort discovery of the whole pack.
    """


# ---------------------------------------------------------------------------
# Source: live /object_info
# ---------------------------------------------------------------------------


def _discover_live(pack_slug: str, server_url: str) -> list[ClassSpec]:
    url = server_url.rstrip("/") + "/object_info"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 — explicit http
            payload = json.loads(resp.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"live fetch failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise DiscoveryError("live response is not a JSON object")
    provenance = f"object_info live {server_url}"
    return _specs_from_object_info(pack_slug, payload, provenance, filter_by_pack=True)


# ---------------------------------------------------------------------------
# Source: cache / static snapshot directories
# ---------------------------------------------------------------------------


_PACK_FILE_RE = re.compile(r"^(?P<slug>.+?)@(?P<rev>[A-Za-z0-9._-]+)\.json$")


def _discover_from_object_info_dir(pack_slug: str, root: Path, *, kind: str) -> list[ClassSpec]:
    if not root.is_dir():
        raise DiscoveryError(f"{kind} dir missing: {root}")
    matches = sorted(root.glob(f"{pack_slug}@*.json"))
    if not matches:
        raise DiscoveryError(f"no {kind} for {pack_slug} in {root}")
    # Prefer the lexicographically last match (newest revision label).
    path = matches[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"{kind} {path} unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise DiscoveryError(f"{kind} {path} is not a JSON object")
    provenance = f"object_info {kind} {path.name} sha256:{sha256_of_path(path)[:12]}"
    # Per-pack files are already filtered, so we accept all top-level entries.
    return _specs_from_object_info(pack_slug, payload, provenance, filter_by_pack=False)


# ---------------------------------------------------------------------------
# Source: AST parse of installed custom-node Python sources
# ---------------------------------------------------------------------------


def _discover_from_source(pack_slug: str, root: Path) -> list[ClassSpec]:
    pack_dir = root / pack_slug
    if not pack_dir.is_dir():
        raise DiscoveryError(f"pack dir missing: {pack_dir}")
    specs: list[ClassSpec] = []
    seen: set[str] = set()
    for py_file in sorted(pack_dir.rglob("*.py")):
        if ".git" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            logger.debug("AST parse skipped for %s: %s", py_file, exc)
            continue
        # Find NODE_CLASS_MAPPINGS in the module (defines the visible class
        # types). For each class def, try to extract INPUT_TYPES / RETURN_TYPES
        # / RETURN_NAMES.
        mappings = _extract_node_class_mappings(tree)
        class_defs = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        rel = py_file.relative_to(pack_dir).as_posix()
        for class_type, class_name in mappings.items():
            if class_type in seen:
                continue
            cls = class_defs.get(class_name)
            if cls is None:
                continue
            spec = _spec_from_ast_class(
                pack_slug=pack_slug,
                class_type=class_type,
                cls_node=cls,
                source_file=f"custom_nodes/{pack_slug}/{rel}",
            )
            if spec is not None:
                specs.append(spec)
                seen.add(class_type)
    if not specs:
        raise DiscoveryError(f"no NODE_CLASS_MAPPINGS extracted from {pack_dir}")
    specs.sort(key=lambda s: s.class_type)
    return specs


def _extract_node_class_mappings(tree: ast.AST) -> dict[str, str]:
    """Extract ``NODE_CLASS_MAPPINGS = {"ClassType": ClassName, ...}`` from a module.

    Only handles the literal-dict form; conditional / generated mappings are
    silently skipped. Returns ``{class_type: class_name}``.
    """
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t for t in node.targets if isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS"]
        if not targets:
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values, strict=False):
            class_type = _string_literal(key)
            class_name = value.id if isinstance(value, ast.Name) else None
            if class_type and class_name:
                out[class_type] = class_name
    return out


def _spec_from_ast_class(
    *,
    pack_slug: str,
    class_type: str,
    cls_node: ast.ClassDef,
    source_file: str,
) -> ClassSpec | None:
    inputs: dict[str, InputFieldSpec] = {}
    outputs: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()
    is_output_node = False
    category: str | None = None

    for item in cls_node.body:
        if isinstance(item, ast.Assign):
            target = item.targets[0] if item.targets else None
            if not isinstance(target, ast.Name):
                continue
            if target.id == "RETURN_TYPES":
                values = _tuple_or_list_strings(item.value)
                if values is not None:
                    output_types = values
            elif target.id == "RETURN_NAMES":
                values = _tuple_or_list_strings(item.value)
                if values is not None:
                    outputs = values
            elif target.id == "OUTPUT_NODE":
                is_output_node = _bool_constant(item.value) or False
            elif target.id == "CATEGORY":
                category = _string_literal(item.value)
        elif isinstance(item, ast.FunctionDef) and item.name == "INPUT_TYPES":
            inputs = _parse_input_types(item)
        elif isinstance(item, ast.FunctionDef) and item.name == "INPUT_TYPES":
            inputs = _parse_input_types(item)
    if not output_types and not inputs:
        return None
    # When RETURN_NAMES is absent, fall back to lower-cased output types.
    if not outputs and output_types:
        outputs = tuple(t.lower() for t in output_types)
    provenance = f"source {source_file}"
    return ClassSpec(
        pack_slug=pack_slug,
        class_type=class_type,
        inputs=inputs,
        outputs=outputs,
        output_types=output_types,
        is_output_node=is_output_node,
        category=category,
        source_provenance=provenance,
    )


def _parse_input_types(func: ast.FunctionDef) -> dict[str, InputFieldSpec]:
    """Best-effort parse of ``INPUT_TYPES`` returning the literal dict.

    Recognized return shape: ``return {"required": {...}, "optional": {...}}``
    where each leaf is either ``("TYPE",)`` or ``("TYPE", {"default": ...})``.
    Anything dynamic (function calls, comprehensions) yields a field with no
    default and no options — the field still appears in the spec but is
    marked as "type unresolved" via empty widget_metadata. Combo-with-list
    inputs (``(["a","b"], {...})``) extract the option list verbatim.
    """
    out: dict[str, InputFieldSpec] = {}
    for stmt in ast.walk(func):
        if not isinstance(stmt, ast.Return):
            continue
        if not isinstance(stmt.value, ast.Dict):
            continue
        for top_key, top_val in zip(stmt.value.keys, stmt.value.values, strict=False):
            section = _string_literal(top_key)
            if section not in {"required", "optional"}:
                continue
            required = section == "required"
            if not isinstance(top_val, ast.Dict):
                continue
            for k, v in zip(top_val.keys, top_val.values, strict=False):
                name = _string_literal(k)
                if not name:
                    continue
                field_spec = _parse_input_field(name, v, required=required)
                if field_spec is not None:
                    out[name] = field_spec
    return out


def _parse_input_field(name: str, value: ast.AST, *, required: bool) -> InputFieldSpec | None:
    # Expected shapes:
    #   ("TYPE",)             -> bare socket
    #   ("TYPE", {...})       -> socket with widget metadata
    #   (["a","b"], {...})    -> combo with explicit options
    #   (<callable>, {...})   -> dynamic combo; mark as COMBO, options None
    if not isinstance(value, (ast.Tuple, ast.List)):
        return InputFieldSpec(name=name, type="UNKNOWN", required=required)
    elts = list(value.elts)
    if not elts:
        return InputFieldSpec(name=name, type="UNKNOWN", required=required)
    first = elts[0]
    widget_meta: dict[str, Any] = {}
    options: tuple[str, ...] | None = None
    type_name = "UNKNOWN"
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        type_name = first.value
    elif isinstance(first, (ast.List, ast.Tuple)):
        # combo literal
        type_name = "COMBO"
        opts = _tuple_or_list_strings(first)
        if opts is not None:
            options = opts
    else:
        # dynamic — likely a function call producing a list at runtime
        type_name = "COMBO"
    if len(elts) >= 2 and isinstance(elts[1], ast.Dict):
        widget_meta = _literal_dict(elts[1]) or {}
    default = widget_meta.get("default")
    has_default = "default" in widget_meta
    return InputFieldSpec(
        name=name,
        type=type_name,
        required=required,
        default=default,
        has_default=has_default,
        options=options,
        widget_metadata=widget_meta,
    )


# ---------------------------------------------------------------------------
# Shared: object_info → ClassSpec
# ---------------------------------------------------------------------------


def _specs_from_object_info(
    pack_slug: str,
    payload: dict[str, Any],
    provenance: str,
    *,
    filter_by_pack: bool,
) -> list[ClassSpec]:
    specs: list[ClassSpec] = []
    for class_type in sorted(payload.keys()):
        info = payload[class_type]
        if not isinstance(info, dict):
            continue
        if filter_by_pack and info.get("pack") not in {pack_slug, pack_slug.lower()}:
            continue
        inputs = _inputs_from_object_info(info)
        outputs_section = info.get("outputs")
        output_types: tuple[str, ...] = ()
        output_names: tuple[str, ...] = ()
        if isinstance(outputs_section, list):
            output_types = tuple(str(item.get("type")) for item in outputs_section if isinstance(item, dict))
            output_names = tuple(str(item.get("name")) for item in outputs_section if isinstance(item, dict))
        elif isinstance(info.get("output"), list):  # legacy /object_info shape
            output_types = tuple(str(t) for t in info["output"])
            output_names = tuple(str(n) for n in info.get("output_name") or output_types)
        specs.append(
            ClassSpec(
                pack_slug=pack_slug,
                class_type=class_type,
                inputs=inputs,
                outputs=output_names,
                output_types=output_types,
                is_output_node=bool(info.get("output_node")),
                category=info.get("category"),
                display_name=info.get("display_name"),
                description=info.get("description"),
                source_provenance=provenance,
            )
        )
    return specs


def _inputs_from_object_info(info: dict[str, Any]) -> dict[str, InputFieldSpec]:
    out: dict[str, InputFieldSpec] = {}
    section_blob = info.get("inputs")
    if not isinstance(section_blob, dict):
        return out
    for section_name in ("required", "optional"):
        section = section_blob.get(section_name)
        if not isinstance(section, dict):
            continue
        required = section_name == "required"
        for name, value in section.items():
            if not isinstance(value, list) or not value:
                continue
            type_value = value[0]
            widget_meta: dict[str, Any] = {}
            options: tuple[str, ...] | None = None
            if len(value) >= 2 and isinstance(value[1], dict):
                widget_meta = dict(value[1])
            if isinstance(type_value, str):
                type_name = type_value
            elif isinstance(type_value, list):
                type_name = "COMBO"
                options = tuple(str(item) for item in type_value)
            else:
                type_name = "UNKNOWN"
            out[name] = InputFieldSpec(
                name=name,
                type=type_name,
                required=required,
                default=widget_meta.get("default"),
                has_default="default" in widget_meta,
                options=options,
                widget_metadata=widget_meta,
            )
    return out


# ---------------------------------------------------------------------------
# AST literal helpers
# ---------------------------------------------------------------------------


def _string_literal(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _bool_constant(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _tuple_or_list_strings(node: ast.AST | None) -> tuple[str, ...] | None:
    if not isinstance(node, (ast.Tuple, ast.List)):
        return None
    out: list[str] = []
    for elt in node.elts:
        s = _string_literal(elt)
        if s is None:
            return None
        out.append(s)
    return tuple(out)


def _literal_dict(node: ast.AST) -> dict[str, Any] | None:
    if not isinstance(node, ast.Dict):
        return None
    out: dict[str, Any] = {}
    for k, v in zip(node.keys, node.values, strict=False):
        key = _string_literal(k)
        if key is None:
            continue
        try:
            out[key] = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            out[key] = None
    return out


# ---------------------------------------------------------------------------
# Lockfile helpers
# ---------------------------------------------------------------------------


def _read_lockfile_pack_slugs(lockfile: Path) -> list[str]:
    if not lockfile.exists():
        return []
    slugs: list[str] = []
    for line in lockfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        slug = line.split()[0]
        if slug:
            slugs.append(slug)
    return slugs


__all__ = [
    "ClassSpec",
    "DEFAULT_PRECEDENCE",
    "DiscoveryError",
    "InputFieldSpec",
    "Source",
    "discover_all",
    "discover_pack",
    "known_pack_slug",
    "sha256_of_path",
]
