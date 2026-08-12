"""B02-C4 — corpus-wide rich-preservation proof harness.

For every serialized-Vibe envelope in ``external_workflows/corpus/*.json``
(a ``vibecomfy_format_version`` + rich ``nodes`` mapping envelope), run the
full canonical pipeline and prove deterministic lossless preservation at every
boundary:

    rich ──convert_to_vibe_format──▶ ir1 ──normalize_agent_edit_graph──▶ canonical
         ──normalize_to_api(use_comfy_converter=False)──▶ api ──convert_to_vibe_format──▶ ir2
         ──emit_ui_json(groups=canonical groups)──▶ reemit
         pin evidence: emit_ui_json(ir1, recovery_report=report, groups=rich groups)

Axes asserted (every mismatch records ``(file, axis, node, expected, actual)``
and fails the run):

  rich→ir1            node id / class_type / stable uid / mode / raw-widgets
                      values+shape+length / widgets_values / non-link furniture
                      (only deterministic id/order/link-id renumbering excluded);
                      edge tuples ``(from_node, from_output, to_node, to_input)``
  rich→canonical      node ids / classes / modes / uids / widgets_values;
                      semantic edge tuples recovered from canonical links via the
                      to-node input names; groups
  rich→ir2            node id / class_type / uid / mode / widgets_values; edges
  canonical idempotence
                      node id/class/mode/uid/widgets_values, groups, and link
                      endpoint+slot topology (link ids/types excluded)
  pin evidence        every ``widget_shape_verdict == "pin_opaque"`` report entry
                      maps to an emitted node whose ``properties.vibecomfy_uid``
                      equals the decoded canonical node uid
  uidless emissions   global blank/missing ``properties.vibecomfy_uid`` count == 0

Expected schema-less warnings are suppressed; exceptions are never swallowed —
a pipeline refusal/exception is recorded as a ``(file, axis, ...)`` mismatch row
and fails the run.

Run as a CLI to get one final JSON summary on stdout:

    .venv/bin/python scripts/check_b02_rich_preservation.py

Exit code is 0 iff zero mismatches and zero uid-less emissions.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any

from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.refuse import RefusedEmit

# Keys whose values are deterministic renumbering artifacts of the canonical
# emission (node ids, draw order, link refs) — excluded from raw-UI furniture
# comparisons by contract.
_RENUMBERED_KEYS: frozenset[str] = frozenset({"id", "order", "link", "links"})

_SCHEMA_LESS_WARNING = "schema-less"


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------


def _strip_renumbered(value: Any) -> Any:
    """Recursively drop deterministic renumbering fields (id/order/link refs)."""
    if isinstance(value, dict):
        return {
            key: _strip_renumbered(item)
            for key, item in value.items()
            if key not in _RENUMBERED_KEYS
        }
    if isinstance(value, list):
        return [_strip_renumbered(item) for item in value]
    return value


def _ui_of(metadata: Any) -> dict[str, Any]:
    ui = metadata.get("_ui") if isinstance(metadata, dict) else None
    return ui if isinstance(ui, dict) else {}


def _mode_of(metadata: Any) -> int:
    """Node mode: raw ``_ui.mode`` when present, else top-level metadata mode, else 0."""
    ui = _ui_of(metadata)
    if "mode" in ui:
        return ui["mode"]
    value = metadata.get("mode")
    return value if isinstance(value, int) else 0


def _widgets_values_of(metadata: Any) -> Any:
    """Raw UI widgets_values evidence; absent/null → no evidence (nothing to preserve)."""
    value = _ui_of(metadata).get("widgets_values")
    return deepcopy(value) if value is not None else None


def _raw_widgets_projection(raw_widgets: Any) -> dict[str, Any] | None:
    """RawWidgetPayload (IR) or raw dict (envelope) → comparable projection."""
    if raw_widgets is None:
        return None
    if not isinstance(raw_widgets, dict):
        return {
            "values": deepcopy(raw_widgets.values),
            "shape": raw_widgets.shape,
            "length": raw_widgets.length,
            "has_dict_rows": raw_widgets.has_dict_rows,
        }
    return {
        "values": deepcopy(raw_widgets.get("values")),
        "shape": raw_widgets.get("shape"),
        "length": raw_widgets.get("length"),
        "has_dict_rows": raw_widgets.get("has_dict_rows"),
    }


def rich_node_projection(node_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Deterministic rich-envelope node projection (the decode input side)."""
    metadata = entry.get("metadata") or {}
    return {
        "id": entry.get("id"),
        "class_type": entry.get("class_type"),
        "uid": entry.get("uid"),
        "mode": _mode_of(metadata),
        "raw_widgets": _raw_widgets_projection(entry.get("raw_widgets")),
        "widgets_values": _widgets_values_of(metadata),
        "furniture": _strip_renumbered(_ui_of(metadata)),
    }


def ir_node_projection(node: Any) -> dict[str, Any]:
    """IR (VibeNode) projection mirroring :func:`rich_node_projection`."""
    metadata = node.metadata
    return {
        "id": node.id,
        "class_type": node.class_type,
        "uid": node.uid,
        "mode": _mode_of(metadata),
        "raw_widgets": _raw_widgets_projection(node.raw_widgets),
        "widgets_values": _widgets_values_of(metadata),
        "furniture": _strip_renumbered(_ui_of(metadata)),
    }


def edge_tuple(edge: Any) -> tuple[str, str, str, str]:
    """Exact semantic edge tuple shared by rich envelope edges and IR edges."""
    return (
        str(edge.from_node),
        str(edge.from_output),
        str(edge.to_node),
        str(edge.to_input),
    )


def rich_edge_tuples(rich: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {
        (str(edge["from_node"]), str(edge["from_output"]), str(edge["to_node"]), str(edge["to_input"]))
        for edge in rich.get("edges", [])
    }


def canonical_node_projection(node: dict[str, Any]) -> dict[str, Any]:
    properties = node.get("properties") or {}
    return {
        "id": node.get("id"),
        "class_type": node.get("type"),
        "mode": node.get("mode", 0),
        "uid": properties.get("vibecomfy_uid"),
        "widgets_values": node.get("widgets_values"),
    }


def canonical_nodes_by_id(canonical: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    return {
        node.get("id"): canonical_node_projection(node)
        for node in canonical.get("nodes", [])
    }


def canonical_link_topology(canonical: dict[str, Any]) -> set[tuple[int, int, int, int]]:
    """Canonical link projection: endpoint + slot topology, link ids/types excluded."""
    return {
        (int(link[1]), int(link[2]), int(link[3]), int(link[4]))
        for link in canonical.get("links", [])
    }


def canonical_semantic_edges(canonical: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    """Recover ``(from_node, from_output, to_node, to_input)`` tuples from the
    canonical envelope by resolving each link's target input name through the
    to-node's emitted ``inputs`` entries (link id → name)."""
    link_to_input: dict[int, tuple[str, int]] = {}
    for node in canonical.get("nodes", []):
        for input_entry in node.get("inputs") or []:
            link_id = input_entry.get("link")
            if link_id is not None:
                link_to_input[int(link_id)] = (str(input_entry.get("name", "")), int(node["id"]))
    tuples: set[tuple[str, str, str, str]] = set()
    for link in canonical.get("links", []):
        name, _ = link_to_input.get(int(link[0]), ("", int(link[3])))
        tuples.add((str(link[1]), str(link[2]), str(link[3]), name))
    return tuples


def _canonical_id_of(rich_node_id: str) -> Any:
    """Rich node id → canonical litegraph node id (numeric ids become integers)."""
    return int(rich_node_id) if rich_node_id.isdigit() else rich_node_id


def _record(result: dict[str, Any], axis: str, node: Any, expected: Any, actual: Any) -> None:
    result["mismatches"].append((axis, node, expected, actual))


def _truncate(value: Any, limit: int = 400) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + f"...<{len(text)} bytes>"


# ---------------------------------------------------------------------------
# Per-envelope check
# ---------------------------------------------------------------------------


def _emit(wf: Any, **kwargs: Any) -> dict[str, Any]:
    """emit_ui_json wrapper: schema-less nodes warn per node; those expected
    warnings are suppressed (exceptions are NOT swallowed)."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=_SCHEMA_LESS_WARNING)
        return emit_ui_json(wf, **kwargs)


def check_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    """Run the full preservation pipeline over one rich envelope.

    Returns a per-file result dict with counts and a ``mismatches`` list of
    ``(axis, node, expected, actual)`` rows.  A pipeline refusal/exception is
    recorded as a mismatch row and the remaining axes are skipped — the file
    cannot be preserved, which is itself the finding.
    """
    result: dict[str, Any] = {
        "file": None,
        "rich_nodes": len(raw.get("nodes", {})),
        "rich_edges": len(raw.get("edges", [])),
        "canonical_nodes": 0,
        "canonical_links": 0,
        "groups": 0,
        "pin_opaque": 0,
        "uidless": 0,
        "mismatches": [],
    }

    def fail(axis: str, node: Any, expected: Any, actual: Any) -> dict[str, Any]:
        _record(result, axis, node, expected, actual)
        return result

    ir1 = convert_to_vibe_format(raw)

    # ── pin evidence: emit directly with recovery_report + the rich groups ──
    recovery_report: list[dict[str, Any]] = []
    try:
        pin_envelope = _emit(ir1, recovery_report=recovery_report, groups=raw.get("groups"))
    except RefusedEmit as exc:
        node_id, reason = _refusal_detail(exc)
        return fail("emit_refused", node_id, "emission must succeed", reason)
    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
        return fail("exception", None, "emission must succeed", f"{type(exc).__name__}: {exc}")

    emitted_uids = {
        node.get("properties", {}).get("vibecomfy_uid")
        for node in pin_envelope.get("nodes", [])
    }
    for entry in recovery_report:
        if entry.get("widget_shape_verdict") != "pin_opaque":
            continue
        result["pin_opaque"] += 1
        entry_node_id = str(entry.get("node_id"))
        decoded_uid = ir1.nodes[entry_node_id].uid if entry_node_id in ir1.nodes else None
        if decoded_uid not in emitted_uids:
            _record(
                result,
                "pin.uid_missing",
                entry_node_id,
                f"emitted node with properties.vibecomfy_uid == {decoded_uid!r}",
                "no such emitted node",
            )

    # ── canonicalize + re-ingest + re-emit ──────────────────────────────────
    try:
        canonical = normalize_agent_edit_graph(raw)
        api2 = normalize_to_api(canonical, use_comfy_converter=False)
        ir2 = convert_to_vibe_format(api2)
        reemit = _emit(ir2, groups=canonical.get("groups"))
    except RefusedEmit as exc:
        node_id, reason = _refusal_detail(exc)
        return fail("emit_refused", node_id, "emission must succeed", reason)
    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
        return fail("exception", None, "pipeline must succeed", f"{type(exc).__name__}: {exc}")

    result["canonical_nodes"] = len(canonical.get("nodes", []))
    result["canonical_links"] = len(canonical.get("links", []))
    result["groups"] = len(canonical.get("groups") or [])

    # ── rich → ir1: node projection exact ───────────────────────────────────
    for node_id, entry in raw.get("nodes", {}).items():
        expected = rich_node_projection(node_id, entry)
        actual = ir_node_projection(ir1.nodes[node_id])
        for axis in ("id", "class_type", "uid", "mode", "furniture"):
            if expected[axis] != actual[axis]:
                _record(result, f"rich->ir1.{axis}", node_id, expected[axis], actual[axis])
        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
            _record(result, "rich->ir1.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
        if expected["raw_widgets"] is not None and expected["raw_widgets"] != actual["raw_widgets"]:
            _record(result, "rich->ir1.raw_widgets", node_id, expected["raw_widgets"], actual["raw_widgets"])

    # ── rich → canonical: node ids/classes/modes/uids/widgets exact ─────────
    canonical_by_id = canonical_nodes_by_id(canonical)
    # Numeric rich ids keep their numeric value in the canonical envelope;
    # non-digit ids (typed-wrapper labels like "80:4") are remapped to fresh
    # integers.  The stable uid is the cross-boundary identity: map every rich
    # node to its canonical litegraph id through the emitted uid stamp.
    uid_to_canonical_id = {
        proj["uid"]: canonical_id
        for canonical_id, proj in canonical_by_id.items()
    }

    def canonical_id_of(rich_id: str) -> Any:
        rich_uid = (raw["nodes"][rich_id].get("uid")) if rich_id in raw["nodes"] else None
        mapped = uid_to_canonical_id.get(rich_uid)
        return mapped if mapped is not None else _canonical_id_of(rich_id)

    canonical_ids = set(canonical_by_id)
    expected_ids = {canonical_id_of(node_id) for node_id in raw.get("nodes", {})}
    if canonical_ids != expected_ids:
        _record(
            result,
            "rich->canonical.node_ids",
            None,
            sorted(expected_ids),
            sorted(canonical_ids),
        )
    for node_id, entry in raw.get("nodes", {}).items():
        expected = rich_node_projection(node_id, entry)
        actual = canonical_by_id.get(canonical_id_of(node_id))
        if actual is None:
            _record(result, "rich->canonical.missing_node", node_id, expected["id"], None)
            continue
        for axis in ("class_type", "mode", "uid"):
            if expected[axis] != actual[axis]:
                _record(result, f"rich->canonical.{axis}", node_id, expected[axis], actual[axis])
        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
            _record(result, "rich->canonical.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])

    # ── rich → ir2: node projection exact (ids via the canonical remap) ─────
    for node_id, entry in raw.get("nodes", {}).items():
        expected = rich_node_projection(node_id, entry)
        actual = ir_node_projection(ir2.nodes[str(canonical_id_of(node_id))])
        for axis in ("class_type", "uid", "mode"):
            if expected[axis] != actual[axis]:
                _record(result, f"rich->ir2.{axis}", node_id, expected[axis], actual[axis])
        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
            _record(result, "rich->ir2.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
        # The id axis speaks the canonical id (deterministic renumbering of
        # non-digit ids is the documented exclusion; digit ids keep their value).
        if actual["id"] != str(canonical_id_of(node_id)):
            _record(result, "rich->ir2.id", node_id, str(canonical_id_of(node_id)), actual["id"])

    # ── edge tuples: rich == ir1 == ir2 == canonical (semantic) ─────────────
    rich_edges = rich_edge_tuples(raw)
    ir1_edges = {edge_tuple(edge) for edge in ir1.edges}
    ir2_edges = {edge_tuple(edge) for edge in ir2.edges}
    # ir1 keeps rich ids; ir2 and the canonical envelope speak canonical ids.
    rich_edges_canonical = {
        (str(canonical_id_of(from_node)), from_output, str(canonical_id_of(to_node)), to_input)
        for from_node, from_output, to_node, to_input in rich_edges
    }
    if rich_edges != ir1_edges:
        _record(
            result,
            "rich->ir1.edges",
            None,
            sorted(rich_edges),
            sorted(ir1_edges),
        )
    if rich_edges_canonical != ir2_edges:
        _record(
            result,
            "rich->ir2.edges",
            None,
            sorted(rich_edges_canonical),
            sorted(ir2_edges),
        )
    canonical_edges = canonical_semantic_edges(canonical)
    if rich_edges_canonical != canonical_edges:
        _record(
            result,
            "rich->canonical.edges",
            None,
            sorted(rich_edges_canonical),
            sorted(canonical_edges),
        )

    # ── groups: rich (None ≡ []) == canonical == reemit ─────────────────────
    rich_groups = raw.get("groups") or []
    canonical_groups = canonical.get("groups") or []
    reemit_groups = reemit.get("groups") or []
    if rich_groups != canonical_groups or canonical_groups != reemit_groups:
        _record(
            result,
            "groups",
            None,
            {"rich": rich_groups, "canonical": canonical_groups},
            {"reemit": reemit_groups},
        )

    # ── canonical emission idempotence ──────────────────────────────────────
    reemit_by_id = canonical_nodes_by_id(reemit)
    if set(reemit_by_id) != set(canonical_by_id):
        _record(
            result,
            "canonical.idempotence.node_ids",
            None,
            sorted(canonical_by_id),
            sorted(reemit_by_id),
        )
    for node_id, expected in canonical_by_id.items():
        actual = reemit_by_id.get(node_id)
        if actual is None:
            continue
        for axis in ("class_type", "mode", "uid", "widgets_values"):
            if expected[axis] != actual[axis]:
                _record(result, f"canonical.idempotence.{axis}", node_id, expected[axis], actual[axis])
    if canonical_link_topology(canonical) != canonical_link_topology(reemit):
        _record(
            result,
            "canonical.idempotence.links",
            None,
            sorted(canonical_link_topology(canonical)),
            sorted(canonical_link_topology(reemit)),
        )

    # ── uid-less emissions across every emitted envelope (global must be 0) ─
    for envelope in (canonical, reemit, pin_envelope):
        for node in envelope.get("nodes", []):
            properties = node.get("properties") or {}
            uid = properties.get("vibecomfy_uid")
            if not isinstance(uid, str) or not uid.strip():
                result["uidless"] += 1
                _record(
                    result,
                    "uidless_emission",
                    node.get("id"),
                    "nonblank properties.vibecomfy_uid",
                    uid,
                )

    return result


def _refusal_detail(exc: RefusedEmit) -> tuple[Any, str]:
    """Extract (node_id, reason) from a RefusedEmit diff."""
    for node_id, diff in (exc.diff or {}).items():
        return node_id, str(diff.get("reason") or exc)
    return None, str(exc)


# ---------------------------------------------------------------------------
# Corpus aggregation
# ---------------------------------------------------------------------------


def iter_corpus(corpus_dir: str | Path):
    """Yield ``(path, raw)`` for every serialized-Vibe envelope in the corpus.

    Non-envelope ``*.json`` files (e.g. ``.layout.json`` sidecar stores) are
    skipped and reported in the aggregate ``skipped_non_envelopes`` counter.
    """
    for path in sorted(Path(corpus_dir).glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw.get("nodes"), dict) or "vibecomfy_format_version" not in raw:
            continue
        yield path, raw


def check_corpus(corpus_dir: str | Path = "external_workflows/corpus") -> dict[str, Any]:
    """Run :func:`check_envelope` over the whole corpus and aggregate counts.

    Deterministic: files are processed in sorted order and all set comparisons
    are order-independent.  Returns one summary dict with totals, per-axis
    mismatch counts, and per-file mismatch rows.
    """
    summary: dict[str, Any] = {
        "ok": True,
        "workflows": 0,
        "skipped_non_envelopes": 0,
        "rich_nodes": 0,
        "rich_edges": 0,
        "canonical_nodes": 0,
        "canonical_links": 0,
        "groups": 0,
        "pin_opaque": 0,
        "uidless": 0,
        "mismatch_count": 0,
        "mismatches_by_axis": {},
        "refused_files": [],
        "mismatch_rows": [],
    }
    for path in sorted(Path(corpus_dir).glob("*.json")):
        name = path.name
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
            _record_row(summary, name, "exception", None, "JSON must parse", f"{type(exc).__name__}: {exc}")
            continue
        if not isinstance(raw.get("nodes"), dict) or "vibecomfy_format_version" not in raw:
            summary["skipped_non_envelopes"] += 1
            continue

        summary["workflows"] += 1
        result = check_envelope(raw)
        result["file"] = name
        summary["rich_nodes"] += result["rich_nodes"]
        summary["rich_edges"] += result["rich_edges"]
        summary["canonical_nodes"] += result["canonical_nodes"]
        summary["canonical_links"] += result["canonical_links"]
        summary["groups"] += result["groups"]
        summary["pin_opaque"] += result["pin_opaque"]
        summary["uidless"] += result["uidless"]
        for axis, node, expected, actual in result["mismatches"]:
            _record_row(summary, name, axis, node, expected, actual)
        for axis, node, expected, actual in result["mismatches"]:
            if axis == "emit_refused":
                summary["refused_files"].append([name, _truncate(node), _truncate(actual)])

    summary["mismatch_count"] = len(summary["mismatch_rows"])
    summary["ok"] = summary["mismatch_count"] == 0 and summary["uidless"] == 0
    return summary


def _record_row(
    summary: dict[str, Any],
    file: str,
    axis: str,
    node: Any,
    expected: Any,
    actual: Any,
) -> None:
    summary["mismatches_by_axis"][axis] = summary["mismatches_by_axis"].get(axis, 0) + 1
    summary["mismatch_rows"].append(
        [file, axis, _truncate(node), _truncate(expected), _truncate(actual)]
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-dir",
        default="external_workflows/corpus",
        help="directory of serialized-Vibe corpus envelopes (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    summary = check_corpus(args.corpus_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
