"""Emit a real-Python ready_template module from a VibeWorkflow.

LEGACY WARNING (Sprint 3, 2026-05-15):
    Lines ~1–550 below are a pre-existing standalone emitter implementation that
    is NO LONGER the active code path.  The ACTIVE delegation wrapper lives at
    the bottom of the file (search for ``# --- ACTIVE delegation wrapper ---``).

    The ACTIVE ``format_as_python()`` (which overrides the legacy definition)
    delegates to ``vibecomfy.porting.emitter.emit_ready_template_python()`` —
    the canonical Sprint 3+ emitter.  The legacy body is retained only for
    historical reference and for CLI bootstrapping of templates that still
    define ``NODES`` tuples.  Do NOT extend the legacy path; all new work goes
    into ``vibecomfy/porting/emitter.py``.

Usage as a script:

    python -m tools.format_as_python <ready_template_path>

Prints the regenerated module to stdout. Does NOT write to disk; the
driver (`tools/convert_ready_templates.py`) handles writes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import keyword
import pprint
import re
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.widgets.aliases import resolve_widget_name
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA


# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]


# Top-of-file generator marker.
GENERATED_HEADER = (
    "# vibecomfy: generated\n"
    "# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\n"
)


# Node classes that are pure UI/visual artefacts and must NOT survive into IR.
#
# Strip ONLY MarkdownNote and Note here — they have no runtime semantics and
# are pure documentation. Reroute/PrimitiveNode/GetNode/SetNode/Bypasser
# do show up in legacy API JSON; they participate in the runtime's
# control-flow indirection (custom packs use them as named-variable wires).
# Preserving them is required for roundtrip-equality and runtime behaviour.
UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset(
    {
        "Note",
        "MarkdownNote",
    }
)


# AUTHORED templates with subgraph inlining: tail-call patches that depend
# on specific original node IDs from the source workflow JSON. Generated
# code must preserve IDs and re-emit the patch calls verbatim.
LTX2_3_TAIL_PATCHES: tuple[str, ...] = (
    "from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram",
    "from vibecomfy.patches.requirements import ensure_custom_nodes",
    "from vibecomfy.patches.resolution import resolution",
)


# Sentinel used in the emitted file to mark generated content vs hand-edited.
GENERATED_MARKER_LINES = (
    "# vibecomfy: generated",
    "# vibecomfy: manual",
)


def _is_link(value: Any) -> bool:
    """Match a [node_id, slot] link, including dotted compound IDs (e.g. "238:231")."""
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    nid_s = str(nid)
    # Plain int id, or compound id like "238:231" / "76:67".
    return all(part.isdigit() for part in nid_s.split(":"))


def _safe_var(class_type: str) -> str:
    """Lowercase + underscores form of a class type (no UUID prefixes)."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", class_type.lower())
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _connection_role_name(workflow_nodes: dict, edges_out: dict) -> dict[str, str]:
    """Apply role-from-connection heuristic: CLIPTextEncode ↦ positive/negative."""
    roles: dict[str, str] = {}
    for src_node_id, src_class in [(nid, n.class_type) for nid, n in workflow_nodes.items()]:
        if src_class != "CLIPTextEncode":
            continue
        for to_node, to_input in edges_out.get(src_node_id, []):
            target = workflow_nodes.get(to_node)
            if target is None:
                continue
            if target.class_type == "KSampler" and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
            if target.class_type in ("CFGGuider", "MultimodalGuider") and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
    return roles


def _empty_text_role(workflow_nodes: dict) -> dict[str, str]:
    """Apply role-from-text heuristic: empty CLIPTextEncode prompt → 'negative'."""
    roles: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        text_value = node.inputs.get("text", node.widgets.get("text", node.widgets.get("widget_0")))
        if isinstance(text_value, str) and text_value.strip() == "":
            roles.setdefault(nid, "negative")
    return roles


def _id_sort_key(nid: str) -> tuple:
    """Stable sort key for node ids of form '60' or '76:67' or 'abc'."""
    parts = str(nid).split(":")
    if all(p.isdigit() for p in parts):
        return tuple(int(p) for p in parts)
    return (1 << 31, str(nid))


def _topological_node_order(nodes: dict, edges_in: dict) -> list[str]:
    """Topologically sort node ids: producers before consumers.

    Resolves both edges-in-IR (`workflow.edges`) and link-shaped values still
    living in `node.inputs` so the emitted file can reference variables
    defined earlier in the function.
    """
    # Build incoming-deps map.
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        # From workflow.edges via edges_in.
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        # From link-shaped values in node.inputs / widgets.
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if _is_link(value):
                src = str(value[0])
                if src in nodes:
                    deps[nid].add(src)

    pending = set(nodes.keys())
    out: list[str] = []
    while pending:
        # Pick the node with no remaining unsatisfied deps; tie-break by id.
        ready = sorted(
            (nid for nid in pending if not (deps[nid] - set(out))),
            key=_id_sort_key,
        )
        if not ready:
            # Cycle or unresolved dep — flush remainder in id order.
            out.extend(sorted(pending, key=_id_sort_key))
            break
        for nid in ready:
            out.append(nid)
            pending.discard(nid)
    return out


def _format_value(value: Any) -> str:
    """Pretty-print a literal kwarg value for the emitter."""
    if isinstance(value, str):
        if "\n" in value or len(value) > 70:
            # Use repr but break long strings across lines via Python's auto string concat.
            return repr(value)
        return repr(value)
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, dict, tuple)):
        return repr(value)
    return repr(value)


def _compute_variable_names(workflow_nodes: dict, edges: list) -> dict[str, str]:
    """Assign a stable variable name to each node id."""
    edges_out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        edges_out.setdefault(edge.from_node, []).append((edge.to_node, edge.to_input))

    role_conn = _connection_role_name(workflow_nodes, edges_out)
    role_empty = _empty_text_role(workflow_nodes)

    sorted_ids = sorted(
        workflow_nodes.keys(),
        key=lambda nid: (
            tuple(int(p) if p.isdigit() else (1 << 30, p) for p in str(nid).split(":"))
            if all(p.isdigit() for p in str(nid).split(":"))
            else (1 << 30, str(nid))
        ),
    )

    used: dict[str, int] = {}
    var_names: dict[str, str] = {}

    for nid in sorted_ids:
        node = workflow_nodes[nid]
        if nid in role_conn:
            base = role_conn[nid]
        elif nid in role_empty:
            base = role_empty[nid]
        else:
            base = _safe_var(node.class_type)

        used[base] = used.get(base, 0) + 1
        if used[base] == 1:
            var_names[nid] = base
        else:
            var_names[nid] = f"{base}_{used[base]}"

    # Second pass: if a base name was used only once, drop the suffix.
    # (Already correct above; nothing to do.)
    return var_names


def _node_kwargs(node: Any, edges_in: dict, var_names: dict[str, str]) -> list[tuple[str, str]]:
    """Produce ordered (kwarg_name, repr_or_handle_expr) pairs for a node.

    Resolves links from BOTH `workflow.edges` (the canonical place) and
    `node.inputs` (for templates whose IR retained list-shaped link values
    because the upstream `convert_to_vibe_format` didn't strip dotted-id
    links).
    """
    cls = node.class_type

    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    # Build incoming map: edges first, then any list-shaped link still in inputs.
    incoming: dict[str, tuple[str, int]] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str) -> str | None:
        """Resolve a widget_N key to its canonical name, or None to drop it."""
        if not key.startswith("widget_"):
            return key
        try:
            idx = int(key.split("_", 1)[1])
        except ValueError:
            return key
        return resolve_widget_name(cls, idx)

    # Two-phase: collect raw keys and values, then optionally translate
    # widget_X keys to canonical names ONLY when the canonical isn't already
    # in the source (preserves dual-key noise from LEGACY API JSON like
    # `{audio: 'x.wav', widget_0: 'x.wav'}`).
    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            if key not in raw_inputs:
                raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key)
        if translated is None:
            # UI-only widget (e.g. KSampler control_after_generate) — drop entirely.
            continue
        if (
            translated != key
            and translated not in raw_inputs
            and translated not in static_inputs
            and translated not in incoming
        ):
            # Only the widget form exists — promote to canonical for readability.
            static_inputs[translated] = value
        else:
            # Keep raw key (e.g. when canonical exists as link or in raw).
            static_inputs[key] = value

    # Order static inputs: schema order first, then anything else alphabetically.
    if schema:
        ordered_static_keys = [k for k in schema if k in static_inputs]
        ordered_static_keys += sorted(k for k in static_inputs if k not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    for key in ordered_static_keys:
        if key in incoming:
            continue
        if not _is_python_ident(key):
            extras.append((key, _format_value(static_inputs[key])))
            continue
        out.append((key, _format_value(static_inputs[key])))

    # Now emit incoming-edge kwargs, schema-ordered if applicable.
    if schema:
        ordered_incoming = [k for k in schema if k in incoming]
        ordered_incoming += sorted(k for k in incoming if k not in schema_set)
    else:
        ordered_incoming = sorted(incoming.keys())

    for to_input in ordered_incoming:
        from_node, from_slot = incoming[to_input]
        if from_node in var_names:
            expr = f"{var_names[from_node]}.out({from_slot})"
        else:
            expr = f"[{from_node!r}, {from_slot}]"
        if not _is_python_ident(to_input):
            extras.append((to_input, expr))
            continue
        out.append((to_input, expr))

    if extras:
        # Pass non-identifier kwargs as a dict literal via _extras kwarg,
        # which the `_node` helper applies post-construction.
        extras_repr = "{" + ", ".join(f"{k!r}: {v}" for k, v in extras) + "}"
        out.append(("_extras", extras_repr))

    return out


def _format_kwargs_block(
    kwargs: list[tuple[str, str]],
    *,
    indent: str = "    ",
    leading: str,
) -> str:
    """Format a kwargs list as a multi-line call body."""
    if not kwargs:
        return f"{leading})"
    lines = [leading]
    for key, expr in kwargs:
        # Wrap long string literals across multiple lines for readability.
        rendered = expr
        if expr.startswith("'") or expr.startswith('"'):
            # Use Python string concat for long literals to keep line widths sane.
            if len(expr) > 100:
                rendered = expr
        lines.append(f"{indent}{indent}{key}={rendered},")
    lines.append(f"{indent})")
    return "\n".join(lines)


def _format_metadata_dict(name: str, value: dict) -> str:
    """Serialize READY_METADATA / READY_REQUIREMENTS as an assignable dict literal."""
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


def _has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


def format_as_python(
    workflow,
    *,
    ready_metadata: dict,
    ready_requirements: dict,
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict | None = None,
    raw_workflow: dict | None = None,
) -> str:
    """Compatibility wrapper for the package ready-template emitter."""
    from vibecomfy.porting.emitter import emit_ready_template_python

    return emit_ready_template_python(
        workflow,
        ready_metadata=ready_metadata,
        ready_requirements=ready_requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
        apply_overrides=apply_overrides,
        raw_workflow=raw_workflow,
    )


# --- CLI -----------------------------------------------------------------------


def _load_module_from_path(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"_vibecomfy_inspect_{path.stem}", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_workflow_for(
    template_path: Path,
) -> tuple[Any, dict, dict, str, dict[str, tuple[str, str]] | None]:
    """Drive the parser end and return (workflow, metadata, requirements, id, registered_inputs)."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
    from vibecomfy.registry.ready_template import build_authored_ready_workflow

    module = _load_module_from_path(template_path)
    template_id = getattr(module, "READY_METADATA", {}).get("ready_template") or template_path.stem

    if hasattr(module, "API_WORKFLOW"):
        api = dict(module.API_WORKFLOW)
        wf = convert_to_vibe_format(api, source_path=str(template_path), workflow_id=template_id)
        return (
            wf,
            dict(module.READY_METADATA),
            dict(module.READY_REQUIREMENTS),
            template_id,
            None,
        )

    if hasattr(module, "NODES"):
        nodes_tuple = module.NODES
        metadata = dict(module.READY_METADATA)
        # Detect if any class_type is a UUID — needs subgraph inlining.
        has_uuid = any(re.fullmatch(r"[0-9a-f-]{36}", str(c)) for _, c, _ in nodes_tuple)
        if has_uuid:
            source_path = REPO_ROOT / metadata["source_workflow"]
            ui = json.loads(source_path.read_text())
            api = normalize_to_api(ui, use_comfy_converter=False)
            wf = convert_to_vibe_format(api, source_path=str(template_path), workflow_id=template_id)
        else:
            # No UUID — just rebuild via authored path; this gives us a working
            # VibeWorkflow with original IDs preserved.
            registered_inputs = _extract_registered_inputs(template_path)
            wf = build_authored_ready_workflow(
                nodes_tuple,
                metadata,
                source_path=str(template_path),
                workflow_id=template_id,
                requirements=module.READY_REQUIREMENTS,
                registered_inputs=registered_inputs,
            )
            return (
                wf,
                metadata,
                dict(module.READY_REQUIREMENTS),
                template_id,
                registered_inputs,
            )

        registered_inputs = _extract_registered_inputs(template_path)
        return (
            wf,
            metadata,
            dict(module.READY_REQUIREMENTS),
            template_id,
            registered_inputs,
        )

    raise RuntimeError(f"Module {template_path} has neither API_WORKFLOW nor NODES")


def _extract_registered_inputs(path: Path) -> dict[str, tuple[str, str]] | None:
    text = path.read_text()
    m = re.search(r"registered_inputs=(\{[^}]*\})", text)
    if not m:
        return None
    try:
        # Safe-ish eval of a small dict literal of strings/tuples.
        import ast
        return ast.literal_eval(m.group(1))
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit converted ready_template Python.")
    parser.add_argument("template_path", type=Path)
    args = parser.parse_args(argv)

    path = args.template_path.resolve()
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    workflow, metadata, requirements, template_id, registered_inputs = _build_workflow_for(path)
    text = format_as_python(
        workflow,
        ready_metadata=metadata,
        ready_requirements=requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
    )
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
